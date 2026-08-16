from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable


@dataclass(frozen=True)
class CacheResult:
    value: Any
    fetched_at_epoch: float
    age_seconds: float
    latency_ms: float
    cache_hit: bool
    stale: bool
    error: str | None = None


@dataclass
class _CacheEntry:
    value: Any
    fetched_at_epoch: float
    expires_at_monotonic: float
    latency_ms: float


class AsyncTTLCache:
    """Small process-local cache with per-key locking and stale fallback."""

    def __init__(self, max_entries: int = 128) -> None:
        self.max_entries = max(8, max_entries)
        self._entries: dict[str, _CacheEntry] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def get_or_load(
        self,
        key: str,
        ttl_seconds: int,
        stale_seconds: int,
        loader: Callable[[], Awaitable[Any]],
        *,
        force: bool = False,
    ) -> CacheResult:
        now_monotonic = time.monotonic()
        cached = self._entries.get(key)
        if cached and not force and now_monotonic < cached.expires_at_monotonic:
            return self._result(cached, cache_hit=True, stale=False)

        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            now_monotonic = time.monotonic()
            cached = self._entries.get(key)
            if (
                cached
                and not force
                and now_monotonic < cached.expires_at_monotonic
            ):
                return self._result(cached, cache_hit=True, stale=False)

            started = time.perf_counter()
            try:
                value = await loader()
            except Exception as exc:
                if cached:
                    age_seconds = max(
                        0.0,
                        time.time() - cached.fetched_at_epoch,
                    )
                    if age_seconds <= stale_seconds:
                        return CacheResult(
                            value=cached.value,
                            fetched_at_epoch=cached.fetched_at_epoch,
                            age_seconds=round(age_seconds, 3),
                            latency_ms=cached.latency_ms,
                            cache_hit=True,
                            stale=True,
                            error=self._safe_error(exc),
                        )
                raise

            entry = _CacheEntry(
                value=value,
                fetched_at_epoch=time.time(),
                expires_at_monotonic=time.monotonic() + ttl_seconds,
                latency_ms=(time.perf_counter() - started) * 1000,
            )
            self._entries[key] = entry
            self._prune()
            return self._result(entry, cache_hit=False, stale=False)

    def _result(
        self,
        entry: _CacheEntry,
        *,
        cache_hit: bool,
        stale: bool,
    ) -> CacheResult:
        return CacheResult(
            value=entry.value,
            fetched_at_epoch=entry.fetched_at_epoch,
            age_seconds=round(
                max(0.0, time.time() - entry.fetched_at_epoch),
                3,
            ),
            latency_ms=round(entry.latency_ms, 3),
            cache_hit=cache_hit,
            stale=stale,
        )

    def _prune(self) -> None:
        if len(self._entries) <= self.max_entries:
            return
        ordered = sorted(
            self._entries.items(),
            key=lambda pair: pair[1].fetched_at_epoch,
        )
        for key, _ in ordered[: len(self._entries) - self.max_entries]:
            self._entries.pop(key, None)
            self._locks.pop(key, None)

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        text = str(exc).strip() or exc.__class__.__name__
        return text[:180]
