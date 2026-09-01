from __future__ import annotations

import asyncio
import datetime as dt
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


UTC = dt.timezone.utc


def utc_now() -> dt.datetime:
    return dt.datetime.now(UTC)


def iso_datetime(value: dt.datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


class SessionStatus(StrEnum):
    CREATING = "CREATING"
    READY = "READY"
    PLAYING = "PLAYING"
    DEGRADED = "DEGRADED"
    CLOSING = "CLOSING"
    CLOSED = "CLOSED"
    FAILED = "FAILED"


class StreamStatus(StrEnum):
    CONNECTING = "CONNECTING"
    WAITING_FIRST_FRAME = "WAITING_FIRST_FRAME"
    PLAYING = "PLAYING"
    DEGRADED = "DEGRADED"
    CLOSING = "CLOSING"
    CLOSED = "CLOSED"
    FAILED = "FAILED"


@dataclass
class RealtimeStream:
    stream_id: str
    device_id: str
    status: StreamStatus
    created_at: dt.datetime
    updated_at: dt.datetime
    first_frame_at: dt.datetime | None = None
    width: int | None = None
    height: int | None = None
    track_state: str | None = None
    error_code: str | None = None
    release_mode: str | None = None
    runtime_state: str = "AUTHORIZED"
    audio_status: str = "OFF"
    audio_track_state: str | None = None
    audio_codec: str | None = None
    audio_error_code: str | None = None
    closed_at: dt.datetime | None = None
    view_close_reason: str | None = None
    view_error_code: str | None = None
    view_event_finalized: bool = False

    def public(self) -> dict[str, Any]:
        return {
            "stream_id": self.stream_id,
            "device_id": self.device_id,
            "kind": "video",
            "status": self.status.value,
            "created_at": iso_datetime(self.created_at),
            "updated_at": iso_datetime(self.updated_at),
            "first_frame_at": iso_datetime(self.first_frame_at),
            "width": self.width,
            "height": self.height,
            "track_state": self.track_state,
            "error_code": self.error_code,
            "release_mode": self.release_mode,
            "runtime_state": self.runtime_state,
            "audio": {
                "status": self.audio_status,
                "track_state": self.audio_track_state,
                "codec": self.audio_codec,
                "error_code": self.audio_error_code,
            },
            "closed_at": iso_datetime(self.closed_at),
        }


@dataclass
class RealtimeSession:
    session_id: str
    owner_key: str
    owner_name: str
    lease_hash: str
    status: SessionStatus
    created_at: dt.datetime
    last_heartbeat_at: dt.datetime
    expires_at: dt.datetime
    adapter: Any
    updated_at: dt.datetime
    device_scope: str = "all"
    connection_reusable: bool = False
    closed_at: dt.datetime | None = None
    streams: dict[str, RealtimeStream] = field(default_factory=dict)
    control_socket: Any = None
    pending_commands: dict[str, asyncio.Future[dict[str, Any]]] = field(
        default_factory=dict
    )
    operation_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def public(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "status": self.status.value,
            "created_at": iso_datetime(self.created_at),
            "updated_at": iso_datetime(self.updated_at),
            "last_heartbeat_at": iso_datetime(self.last_heartbeat_at),
            "expires_at": iso_datetime(self.expires_at),
            "closed_at": iso_datetime(self.closed_at),
            "connection_reusable": self.connection_reusable,
            "device_scope": self.device_scope,
            "audio_enabled": bool(
                getattr(
                    getattr(self.adapter, "settings", None),
                    "feature_realtime_audio",
                    False,
                )
            ),
            "max_streams": getattr(
                getattr(self.adapter, "settings", None),
                "realtime_max_streams_per_session",
                1,
            ),
            "streams": [
                stream.public()
                for stream in sorted(
                    self.streams.values(),
                    key=lambda item: item.created_at,
                )
            ],
        }
