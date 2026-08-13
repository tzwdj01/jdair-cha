from __future__ import annotations

import asyncio
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


class LegacyServiceError(RuntimeError):
    """Base error for the compatibility connection to the legacy service."""


class LegacyTransportError(LegacyServiceError):
    """The legacy service could not be reached or completed no response."""


class LegacyPayloadError(LegacyServiceError):
    """The legacy service returned a response that could not be interpreted."""


@dataclass(frozen=True)
class LegacyResponse:
    status_code: int
    content_type: str
    body: bytes
    latency_ms: float

    def json(self) -> Any:
        try:
            return json.loads(self.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LegacyPayloadError(
                "The legacy service did not return valid JSON"
            ) from exc


class LegacyClient:
    """Narrow allow-listed adapter for the existing local CHA service."""

    ALLOWED_PATHS = {
        "/",
        "/api/auth/session",
        "/api/dashboard",
        "/api/devices",
        "/api/video-stats",
        "/api/flights",
        "/api/routine-tasks",
        "/api/records",
    }

    def __init__(self, base_url: str, timeout_seconds: float = 5.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def health(self) -> LegacyResponse:
        return await asyncio.to_thread(self._request, "/", None)

    async def dashboard(self, cookie: str) -> LegacyResponse:
        return await self.get("/api/dashboard", cookie)

    async def session(self, cookie: str) -> LegacyResponse:
        return await self.get("/api/auth/session", cookie)

    async def devices(self, cookie: str) -> LegacyResponse:
        return await self.get("/api/devices", cookie)

    async def video_stats(self, cookie: str) -> LegacyResponse:
        return await self.get("/api/video-stats", cookie)

    async def flights(self, cookie: str, date: str) -> LegacyResponse:
        return await self.get(
            "/api/flights",
            cookie,
            {"date": date, "current": 1, "size": 100},
        )

    async def routine_tasks(
        self,
        cookie: str,
        date: str,
    ) -> LegacyResponse:
        return await self.get(
            "/api/routine-tasks",
            cookie,
            {"date": date, "current": 1, "size": 100},
        )

    async def records(
        self,
        cookie: str,
        start: str,
        end: str,
        *,
        page: int = 1,
        page_size: int = 100,
    ) -> LegacyResponse:
        return await self.get(
            "/api/records",
            cookie,
            {
                "st": start,
                "et": end,
                "page": max(1, page),
                "pagesize": max(1, min(page_size, 100)),
                "mode": "platform",
            },
        )

    async def get(
        self,
        path: str,
        cookie: str | None,
        params: dict[str, Any] | None = None,
    ) -> LegacyResponse:
        query = urllib.parse.urlencode(params or {}, doseq=True)
        target = path if not query else f"{path}?{query}"
        return await asyncio.to_thread(self._request, target, cookie)

    def _request(self, path: str, cookie: str | None) -> LegacyResponse:
        parsed = urllib.parse.urlsplit(path)
        if (
            parsed.scheme
            or parsed.netloc
            or parsed.path not in self.ALLOWED_PATHS
        ):
            raise ValueError("Legacy path is not allow-listed")

        headers = {
            "Accept": "application/json, text/html;q=0.9",
            "User-Agent": "jdair-cha-v2-compat/0.3",
            "X-CHA-Compat-Request": "v2",
        }
        if cookie:
            headers["Cookie"] = cookie

        request = urllib.request.Request(
            self.base_url + path,
            headers=headers,
            method="GET",
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(
                request,
                timeout=self.timeout_seconds,
            ) as response:
                body = response.read()
                status_code = response.status
                content_type = response.headers.get("Content-Type", "")
        except urllib.error.HTTPError as exc:
            body = exc.read()
            status_code = exc.code
            content_type = exc.headers.get("Content-Type", "")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise LegacyTransportError(
                "The legacy service is unavailable"
            ) from exc

        latency_ms = (time.perf_counter() - started) * 1000
        return LegacyResponse(
            status_code=status_code,
            content_type=content_type,
            body=body,
            latency_ms=latency_ms,
        )
