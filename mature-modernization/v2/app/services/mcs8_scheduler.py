from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ..data.mcs8_adapter import MCS8ReadOnlyDataAdapter
from ..data.mcs8_auth import MCS8AuthError, MCS8ServerAuthProvider
from ..data.mcs8_collector import MCS8InspectionCollector
from ..data.mcs8_http import MCS8DataHTTPClient
from ..data.pagination import CollectedSource
from ..data.store import InspectionStore


UTC = dt.timezone.utc
# The standalone scheduler entrypoint configures this logger at INFO for
# journald.  Do not use the ``uvicorn`` hierarchy here: the entrypoint lowers
# that noisy hierarchy to WARNING and would hide lifecycle evidence.
logger = logging.getLogger("mcs8-scheduler")


@dataclass(frozen=True, slots=True)
class SourceCycleResult:
    source: str
    status: str
    error_code: str | None
    fetched_source_count: int
    stored_count: int
    invalid_row_count: int
    records_total: int | None
    complete: bool
    quality_flags: tuple[str, ...]
    duration_seconds: float
    last_successful_at: dt.datetime | None


@dataclass(frozen=True, slots=True)
class CycleResult:
    cycle_index: int
    started_at: dt.datetime
    finished_at: dt.datetime
    duration_seconds: float
    sources: tuple[SourceCycleResult, ...]
    all_successful: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_index": self.cycle_index,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "duration_seconds": round(self.duration_seconds, 3),
            "all_successful": self.all_successful,
            "sources": [_source_result_to_dict(item) for item in self.sources],
        }


class MCS8ProductionScheduler:
    """Low-rate production scheduler over the MCS8 native channel.

    One cycle = sequential DEVICE snapshot -> MEDIA window -> ALARM window.
    At most one cycle is in flight; the period is configurable and defaults to
    a conservative 600s. Media/Alarm use a bounded lookback window with
    overlap and rely on the store's unique identities for idempotency. Device
    uses the MCS8 snapshot processor (no row growth on unchanged state).

    Authentication is server-side only (``MCS8ServerAuthProvider``), never a
    browser token. The token is reused within a cycle; on rejection the
    provider re-logs in (bounded retries). Secrets are never logged.
    """

    def __init__(
        self,
        *,
        auth: MCS8ServerAuthProvider,
        host: str,
        api_port: int,
        store: InspectionStore,
        lookback_seconds: int,
        overlap_seconds: int,
        state_dir: str,
        source_timezone: dt.tzinfo,
        page_size: int = 1_000,
        max_pages: int = 100,
        max_records: int = 100_000,
        time_type: str | int = 0,
        group_with_child: str | int = 0,
        group_id: str | int = 0,
        include_alarms: bool = True,
        max_login_retries: int = 2,
    ) -> None:
        if not host:
            raise ValueError("MCS8 host is required")
        if api_port <= 0:
            raise ValueError("MCS8 api_port must be positive")
        if lookback_seconds <= 0:
            raise ValueError("lookback_seconds must be positive")
        if overlap_seconds < 0:
            raise ValueError("overlap_seconds must be non-negative")
        if max_login_retries <= 0:
            raise ValueError("max_login_retries must be positive")
        self._auth = auth
        self._host = host
        self._api_port = api_port
        self._store = store
        self._lookback_seconds = lookback_seconds
        self._overlap_seconds = overlap_seconds
        self._state_dir = Path(state_dir)
        self._source_timezone = source_timezone
        self._page_size = page_size
        self._max_pages = max_pages
        self._max_records = max_records
        self._time_type = time_type
        self._group_with_child = group_with_child
        self._group_id = group_id
        self._include_alarms = include_alarms
        self._max_login_retries = max_login_retries
        self._cycle_index = 0
        self._collector: MCS8InspectionCollector | None = None

    def _ensure_token(self) -> str:
        token = self._auth.token
        if token:
            return token
        return self._login_with_bounded_retry()

    def _login_with_bounded_retry(self) -> str:
        last_error: Exception | None = None
        for attempt in range(1, self._max_login_retries + 1):
            try:
                token = self._auth.login()
                logger.info(
                    "mcs8_scheduler_login_succeeded attempt=%d",
                    attempt,
                )
                return token
            except MCS8AuthError as exc:
                last_error = exc
                logger.warning(
                    "mcs8_scheduler_login_failed attempt=%d code=%s",
                    attempt,
                    exc.code,
                )
            except Exception as exc:  # pragma: no cover - defensive
                last_error = exc
                logger.warning(
                    "mcs8_scheduler_login_failed attempt=%d error=%s",
                    attempt,
                    type(exc).__name__,
                )
        raise RuntimeError(
            f"MCS8 login failed after {self._max_login_retries} attempts"
        ) from last_error

    def _build_collector(self) -> MCS8InspectionCollector:
        if self._collector is not None:
            return self._collector
        token = self._ensure_token()
        client = MCS8DataHTTPClient(
            base_url=f"http://{self._host}:{self._api_port}",
            token_provider=lambda: self._auth.token
            or self._login_with_bounded_retry(),
            token_invalidator=self._auth.invalidate,
        )
        adapter = MCS8ReadOnlyDataAdapter(client)
        self._collector = MCS8InspectionCollector(
            adapter,
            self._store,
            source_timezone=self._source_timezone,
            group_id=self._group_id,
            page_size=self._page_size,
            max_pages=self._max_pages,
            max_records=self._max_records,
            time_type=self._time_type,
            group_with_child=self._group_with_child,
            include_alarms=self._include_alarms,
        )
        return self._collector

    async def run_cycle(
        self,
        *,
        observed_at: dt.datetime | None = None,
    ) -> CycleResult:
        """Run one full cycle: DEVICE -> MEDIA -> ALARM sequentially."""

        self._cycle_index += 1
        cycle_index = self._cycle_index
        started = dt.datetime.now(UTC)
        observed = observed_at or started
        results: list[SourceCycleResult] = []
        collector = self._build_collector()

        # 1. DEVICE snapshot (idempotent; no growth on unchanged state)
        device_started = dt.datetime.now(UTC)
        device_source = await collector.collect_device_snapshot(
            observed_at=observed
        )
        results.append(
            _source_result(
                "device_status",
                device_source,
                (dt.datetime.now(UTC) - device_started).total_seconds(),
            )
        )

        # 2. MEDIA then ALARM, bounded window + overlap
        end = observed
        start = end - dt.timedelta(
            seconds=self._lookback_seconds + self._overlap_seconds
        )
        collected = await collector.collect(start, end)
        for name in ("media_files", "alarms"):
            source = collected.get(name)
            if source is None:
                continue
            source_started = dt.datetime.now(UTC)
            stored_count = 0
            if source.status == "ok":
                if name == "media_files":
                    stored_count = await self._store.upsert_media_files(
                        source.rows
                    )
                elif name == "alarms":
                    stored_count = await self._store.upsert_alarm_events(
                        source.rows
                    )
            results.append(
                _source_result(
                    name,
                    source,
                    (dt.datetime.now(UTC) - source_started).total_seconds(),
                    stored_count=stored_count,
                )
            )

        finished = dt.datetime.now(UTC)
        all_successful = all(item.status == "ok" for item in results)
        return CycleResult(
            cycle_index=cycle_index,
            started_at=started,
            finished_at=finished,
            duration_seconds=(finished - started).total_seconds(),
            sources=tuple(results),
            all_successful=all_successful,
        )

    async def run(
        self,
        *,
        period_seconds: int,
        max_cycles: int,
        stop_event: asyncio.Event | None = None,
    ) -> tuple[CycleResult, ...]:
        """Run cycles spaced ``period_seconds`` apart.

        ``max_cycles`` may be 0/negative to run until ``stop_event`` is set
        (long-running systemd service); otherwise it is a positive cap.
        """

        if period_seconds <= 0:
            raise ValueError("period_seconds must be positive")
        stop = stop_event or asyncio.Event()
        completed: list[CycleResult] = []
        while True:
            if stop.is_set():
                break
            next_cycle_index = self._cycle_index + 1
            logger.info(
                "scheduler_cycle_started cycle_index=%d",
                next_cycle_index,
            )
            try:
                result = await self.run_cycle()
            except Exception as exc:
                logger.warning(
                    "scheduler_cycle_failed cycle_index=%d error_type=%s",
                    next_cycle_index,
                    type(exc).__name__,
                )
                raise
            completed.append(result)
            self._write_state(result)
            _log_cycle_completed(result)
            if stop.is_set():
                break
            if max_cycles > 0 and len(completed) >= max_cycles:
                break
            logger.info(
                "scheduler_waiting cycle_index=%d next_cycle_seconds=%d",
                result.cycle_index,
                period_seconds,
            )
            try:
                await asyncio.wait_for(stop.wait(), timeout=period_seconds)
            except asyncio.TimeoutError:
                pass
        return tuple(completed)

    def _state_path(self) -> Path:
        return self._state_dir / "scheduler_state.json"

    def _write_state(self, result: CycleResult) -> None:
        self._state_dir.mkdir(parents=True, exist_ok=True)
        path = self._state_path()
        existing: dict[str, Any] = {}
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            existing = {}
        existing[str(result.cycle_index)] = result.to_dict()
        path.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _source_result(
    name: str,
    source: CollectedSource,
    duration_seconds: float,
    stored_count: int | None = None,
) -> SourceCycleResult:
    stored = stored_count if stored_count is not None else len(source.rows)
    return SourceCycleResult(
        source=name,
        status=source.status,
        error_code=source.error_code,
        fetched_source_count=source.fetched_source_count,
        stored_count=stored,
        invalid_row_count=source.invalid_row_count,
        records_total=source.records_total,
        complete=source.complete,
        quality_flags=source.quality_flags,
        duration_seconds=round(duration_seconds, 3),
        last_successful_at=source.last_successful_at,
    )


def _log_cycle_completed(result: CycleResult) -> None:
    """Emit one bounded, credential-free lifecycle record per cycle."""

    by_source = {item.source: item for item in result.sources}
    device = by_source.get("device_status")
    media = by_source.get("media_files")
    alarms = by_source.get("alarms")
    location_stored = _quality_flag_count(
        device.quality_flags if device else (),
        "device_locations_stored=",
    )
    location_invalid = _quality_flag_count(
        device.quality_flags if device else (),
        "device_locations_invalid=",
    )
    stored_total = sum(item.stored_count for item in result.sources)
    logger.info(
        "scheduler_cycle_completed cycle_index=%d duration_seconds=%.3f "
        "device_status=%s/%d/%d media_files=%s/%d/%d alarms=%s/%d/%d "
        "location_stored=%s location_invalid=%s store_result=%s store_rows=%d",
        result.cycle_index,
        result.duration_seconds,
        device.status if device else "not_reported",
        device.fetched_source_count if device else 0,
        device.stored_count if device else 0,
        media.status if media else "not_reported",
        media.fetched_source_count if media else 0,
        media.stored_count if media else 0,
        alarms.status if alarms else "not_reported",
        alarms.fetched_source_count if alarms else 0,
        alarms.stored_count if alarms else 0,
        location_stored if location_stored is not None else "not_reported",
        location_invalid if location_invalid is not None else "not_reported",
        "ok" if result.all_successful else "partial",
        stored_total,
    )


def _quality_flag_count(
    flags: tuple[str, ...],
    prefix: str,
) -> int | None:
    for flag in flags:
        if not flag.startswith(prefix):
            continue
        try:
            return int(flag.removeprefix(prefix))
        except ValueError:
            return None
    return None


def _source_result_to_dict(item: SourceCycleResult) -> dict[str, Any]:
    return {
        "source": item.source,
        "status": item.status,
        "error_code": item.error_code,
        "fetched_source_count": item.fetched_source_count,
        "stored_count": item.stored_count,
        "invalid_row_count": item.invalid_row_count,
        "records_total": item.records_total,
        "complete": item.complete,
        "quality_flags": list(item.quality_flags),
        "duration_seconds": item.duration_seconds,
        "last_successful_at": (
            item.last_successful_at.isoformat()
            if item.last_successful_at is not None
            else None
        ),
    }
