from __future__ import annotations

import datetime as dt
from dataclasses import dataclass


UTC = dt.timezone.utc
KNOWN_CLOSE_REASONS = {
    "abnormal_disconnect",
    "first_frame_timeout",
    "playback_failed",
    "release_failed",
    "server_shutdown",
    "session_close",
    "session_timeout",
    "user_stream_close",
}


@dataclass(frozen=True, slots=True)
class RealtimeViewEvent:
    view_event_id: str
    source_system: str
    username: str
    user_id: str | None
    device_id: str
    session_id: str
    stream_id: str
    opened_at: dt.datetime
    first_frame_at: dt.datetime | None
    closed_at: dt.datetime
    connection_duration_seconds: float
    view_duration_seconds: float | None
    result: str
    error_code: str | None
    width: int | None
    height: int | None
    track_state: str | None
    close_reason: str
    release_mode: str | None
    quality_flags: tuple[str, ...]


def build_realtime_view_event(
    *,
    username: str,
    user_id: str | None,
    device_id: str,
    session_id: str,
    stream_id: str,
    opened_at: dt.datetime,
    first_frame_at: dt.datetime | None,
    closed_at: dt.datetime,
    error_code: str | None,
    width: int | None,
    height: int | None,
    track_state: str | None,
    close_reason: str,
    release_mode: str | None,
) -> RealtimeViewEvent:
    normalized_session_id = _required_text(session_id, "session_id")
    normalized_stream_id = _required_text(stream_id, "stream_id")
    normalized_device_id = _required_text(device_id, "device_id")
    normalized_opened_at = _aware_utc(opened_at, "opened_at")
    normalized_closed_at = _aware_utc(closed_at, "closed_at")
    if normalized_closed_at < normalized_opened_at:
        raise ValueError("closed_at must not be before opened_at")

    flags: set[str] = set()
    normalized_username = str(username or "").strip()
    if not normalized_username:
        normalized_username = "unknown"
        flags.add("username_missing")
    normalized_username = normalized_username[:64]

    normalized_user_id = _optional_text(user_id, maximum=128)
    normalized_error_code = _optional_text(error_code, maximum=64)
    normalized_track_state = _optional_text(track_state, maximum=32)
    normalized_release_mode = _optional_text(release_mode, maximum=64)

    normalized_first_frame_at: dt.datetime | None = None
    if first_frame_at is not None:
        candidate = _aware_utc(first_frame_at, "first_frame_at")
        if candidate < normalized_opened_at:
            flags.add("first_frame_before_open_ignored")
        elif candidate > normalized_closed_at:
            flags.add("first_frame_after_close_ignored")
        else:
            normalized_first_frame_at = candidate

    normalized_close_reason = str(close_reason or "").strip().casefold()
    if normalized_close_reason not in KNOWN_CLOSE_REASONS:
        normalized_close_reason = "unknown"
        flags.add("close_reason_unknown")

    connection_duration = (
        normalized_closed_at - normalized_opened_at
    ).total_seconds()
    view_duration = (
        (
            normalized_closed_at - normalized_first_frame_at
        ).total_seconds()
        if normalized_first_frame_at is not None
        else None
    )
    result = _result(
        first_frame_at=normalized_first_frame_at,
        close_reason=normalized_close_reason,
        error_code=normalized_error_code,
    )
    if normalized_first_frame_at is not None and normalized_error_code:
        flags.add("terminal_error_after_first_frame")
    if normalized_release_mode == "session_disconnect_unconfirmed":
        flags.add("release_unconfirmed")

    return RealtimeViewEvent(
        view_event_id=f"rtv_{normalized_stream_id}",
        source_system="cha_realtime",
        username=normalized_username,
        user_id=normalized_user_id,
        device_id=normalized_device_id,
        session_id=normalized_session_id,
        stream_id=normalized_stream_id,
        opened_at=normalized_opened_at,
        first_frame_at=normalized_first_frame_at,
        closed_at=normalized_closed_at,
        connection_duration_seconds=connection_duration,
        view_duration_seconds=view_duration,
        result=result,
        error_code=normalized_error_code,
        width=_optional_dimension(width),
        height=_optional_dimension(height),
        track_state=normalized_track_state,
        close_reason=normalized_close_reason,
        release_mode=normalized_release_mode,
        quality_flags=tuple(sorted(flags)),
    )


def _result(
    *,
    first_frame_at: dt.datetime | None,
    close_reason: str,
    error_code: str | None,
) -> str:
    if close_reason == "abnormal_disconnect":
        return "abnormal_disconnect"
    if first_frame_at is not None:
        return "played"
    if (
        close_reason == "first_frame_timeout"
        or str(error_code or "").upper() == "FIRST_FRAME_TIMEOUT"
    ):
        return "timeout"
    if error_code or close_reason in {"playback_failed", "release_failed"}:
        return "failed"
    return "cancelled"


def _required_text(value: str, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} is required")
    return text


def _optional_text(value: str | None, *, maximum: int) -> str | None:
    text = str(value or "").strip()
    return text[:maximum] or None


def _aware_utc(value: dt.datetime, name: str) -> dt.datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(UTC)


def _optional_dimension(value: int | None) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
    if parsed is None or parsed <= 0 or parsed > 8192:
        return None
    return parsed
