from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from .models import (
    RealtimeSession,
    SessionStatus,
    StreamStatus,
)


COUNTER_NAMES = (
    "realtime_first_frame_timeout_total",
    "realtime_stream_open_total",
    "realtime_stream_close_total",
    "realtime_session_create_total",
    "realtime_session_close_total",
    "realtime_session_timeout_cleanup_total",
    "realtime_abnormal_disconnect_total",
    "realtime_release_failure_total",
    "realtime_screenshot_total",
    "realtime_screenshot_failure_total",
    "realtime_audio_open_total",
    "realtime_audio_close_total",
    "realtime_audio_failure_total",
)


@dataclass
class DurationStat:
    count: int = 0
    total_ms: float = 0.0
    min_ms: float | None = None
    max_ms: float | None = None
    last_ms: float | None = None

    def observe(self, value: float) -> None:
        value = max(0.0, float(value))
        self.count += 1
        self.total_ms += value
        self.min_ms = value if self.min_ms is None else min(self.min_ms, value)
        self.max_ms = value if self.max_ms is None else max(self.max_ms, value)
        self.last_ms = value

    def public(self) -> dict[str, float | int | None]:
        return {
            "count": self.count,
            "last_ms": self._round(self.last_ms),
            "min_ms": self._round(self.min_ms),
            "max_ms": self._round(self.max_ms),
            "avg_ms": (
                round(self.total_ms / self.count, 2) if self.count else None
            ),
        }

    @staticmethod
    def _round(value: float | None) -> float | None:
        return round(value, 2) if value is not None else None


class RealtimeTelemetry:
    """Bounded process-local counters and duration summaries."""

    def __init__(self) -> None:
        self.started_monotonic = time.monotonic()
        self._counters = {name: 0 for name in COUNTER_NAMES}
        self._durations: dict[str, DurationStat] = defaultdict(DurationStat)
        self._connections = {"gateway": 0, "media": 0}

    def increment(self, name: str, amount: int = 1) -> None:
        self._counters[name] = max(0, self._counters.get(name, 0) + amount)

    def observe(self, name: str, duration_ms: float) -> None:
        self._durations[name].observe(duration_ms)

    def connection_opened(self, kind: str) -> None:
        if kind in self._connections:
            self._connections[kind] += 1

    def connection_closed(self, kind: str) -> None:
        if kind in self._connections:
            self._connections[kind] = max(0, self._connections[kind] - 1)

    def adapter_event(
        self,
        event: str,
        *,
        duration_ms: float | None = None,
    ) -> None:
        if event == "gateway_connected":
            self.connection_opened("gateway")
            if duration_ms is not None:
                self.observe("gateway_connect_duration_ms", duration_ms)
        elif event == "gateway_disconnected":
            self.connection_closed("gateway")
        elif event == "media_connected":
            self.connection_opened("media")
            if duration_ms is not None:
                self.observe("media_connect_duration_ms", duration_ms)
        elif event == "media_disconnected":
            self.connection_closed("media")
        elif event == "aee_login_succeeded" and duration_ms is not None:
            self.observe("aee_login_duration_ms", duration_ms)

    def snapshot(
        self,
        sessions: Iterable[RealtimeSession],
        *,
        cleanup_task_running: bool,
    ) -> dict[str, object]:
        session_list = list(sessions)
        active_sessions = [
            item
            for item in session_list
            if item.status != SessionStatus.CLOSED
        ]
        active_streams = [
            stream
            for session in active_sessions
            for stream in session.streams.values()
            if stream.status != StreamStatus.CLOSED
        ]
        gauges = {
            "realtime_active_sessions": len(active_sessions),
            "realtime_active_streams": len(active_streams),
            "realtime_sessions_playing": sum(
                item.status == SessionStatus.PLAYING
                for item in active_sessions
            ),
            "realtime_sessions_degraded": sum(
                item.status == SessionStatus.DEGRADED
                for item in active_sessions
            ),
            "realtime_streams_playing": sum(
                item.status == StreamStatus.PLAYING
                for item in active_streams
            ),
            "realtime_streams_failed": sum(
                item.status == StreamStatus.FAILED
                for item in active_streams
            ),
            "realtime_gateway_connections": self._connections["gateway"],
            "realtime_media_connections": self._connections["media"],
            "realtime_retained_sessions": len(session_list),
        }
        return {
            "uptime_seconds": round(
                time.monotonic() - self.started_monotonic,
                3,
            ),
            "cleanup_task_running": cleanup_task_running,
            "gauges": gauges,
            "counters": dict(self._counters),
            "durations": {
                name: stat.public()
                for name, stat in sorted(self._durations.items())
            },
        }
