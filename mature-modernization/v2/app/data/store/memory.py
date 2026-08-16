from __future__ import annotations

import datetime as dt
from typing import Iterable

from ..normalization import (
    AlarmEvent,
    DeviceLocationEvent,
    DeviceStatusEvent,
    MediaFile,
)
from ..realtime_views import RealtimeViewEvent
from .repository import InspectionStore


UTC = dt.timezone.utc


class MemoryInspectionStore(InspectionStore):
    """In-memory InspectionStore for tests and local development.

    Not a production substitute for PostgreSQL. It exists to validate the
    repository contract and to support deterministic unit tests without a
    database runtime.
    """

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._status: dict[tuple, DeviceStatusEvent] = {}
        self._location: dict[tuple, DeviceLocationEvent] = {}
        self._media: dict[tuple, MediaFile] = {}
        self._media_rows: list[MediaFile] = []
        self._views: dict[str, RealtimeViewEvent] = {}
        self._alarms: dict[tuple, AlarmEvent] = {}

    async def upsert_device_status_events(
        self,
        events: Iterable[DeviceStatusEvent],
    ) -> int:
        accepted = 0
        for event in events:
            _validate_status(event)
            key = (
                event.source_system,
                event.device_id,
                _utc(event.occurred_at),
                event.status_code,
                event.source_record_id or "",
            )
            current = self._status.get(key)
            if current is None or _newer_observation(event, current):
                self._status[key] = event
            accepted += 1
        return accepted

    async def fetch_device_status_events(
        self,
        *,
        start: dt.datetime,
        end: dt.datetime,
        device_ids: Iterable[str] | None = None,
        source_system: str | None = None,
    ) -> tuple[DeviceStatusEvent, ...]:
        start_utc, end_utc = _window(start, end)
        allowed = _id_set(device_ids)
        rows = [
            event
            for event in self._status.values()
            if (
                start_utc
                <= _utc(event.occurred_at)
                <= end_utc
                and (allowed is None or event.device_id in allowed)
                and (source_system is None or event.source_system == source_system)
            )
        ]
        rows.sort(
            key=lambda item: (
                _utc(item.occurred_at),
                item.device_id,
                _utc(item.observed_at),
            )
        )
        return tuple(rows)

    async def fetch_latest_device_statuses(
        self,
        *,
        device_ids: Iterable[str] | None = None,
        source_system: str | None = None,
    ) -> dict[str, DeviceStatusEvent]:
        allowed = _id_set(device_ids)
        latest: dict[str, DeviceStatusEvent] = {}
        for event in self._status.values():
            if allowed is not None and event.device_id not in allowed:
                continue
            if source_system is not None and event.source_system != source_system:
                continue
            current = latest.get(event.device_id)
            if current is None or _newer_observation(event, current):
                latest[event.device_id] = event
        return latest

    async def upsert_device_location_events(
        self,
        events: Iterable[DeviceLocationEvent],
    ) -> int:
        accepted = 0
        for event in events:
            _validate_location(event)
            key = (
                event.source_system,
                event.location_source,
                event.device_id,
                _utc(event.gps_occurred_at),
                event.latitude,
                event.longitude,
            )
            current = self._location.get(key)
            if current is None or _newer_observation(event, current):
                self._location[key] = event
            accepted += 1
        return accepted

    async def fetch_device_location_events(
        self,
        *,
        start: dt.datetime,
        end: dt.datetime,
        device_ids: Iterable[str] | None = None,
        source_system: str | None = None,
    ) -> tuple[DeviceLocationEvent, ...]:
        start_utc, end_utc = _window(start, end)
        allowed = _id_set(device_ids)
        rows = [
            event
            for event in self._location.values()
            if (
                start_utc
                <= _utc(event.gps_occurred_at)
                <= end_utc
                and (allowed is None or event.device_id in allowed)
                and (source_system is None or event.source_system == source_system)
            )
        ]
        rows.sort(
            key=lambda item: (
                _utc(item.gps_occurred_at),
                item.device_id,
                _utc(item.observed_at),
            )
        )
        return tuple(rows)

    async def upsert_media_files(
        self,
        files: Iterable[MediaFile],
    ) -> int:
        accepted = 0
        for item in files:
            _validate_media(item)
            if item.source_record_id:
                key = (
                    item.source_system,
                    item.source_record_id,
                    item.device_id,
                )
                current = self._media.get(key)
                if current is None or _newer_observation(item, current):
                    self._media[key] = item
            else:
                self._media_rows.append(item)
            accepted += 1
        return accepted

    async def fetch_media_files(
        self,
        *,
        start: dt.datetime,
        end: dt.datetime,
        device_ids: Iterable[str] | None = None,
        source_system: str | None = None,
    ) -> tuple[MediaFile, ...]:
        start_utc, end_utc = _window(start, end)
        allowed = _id_set(device_ids)
        rows = list(self._media.values()) + list(self._media_rows)

        def in_window(item: MediaFile) -> bool:
            time_value = item.created_at_source or item.uploaded_at_source
            if time_value is None:
                return False
            return start_utc <= _utc(time_value) <= end_utc

        rows = [
            item
            for item in rows
            if (
                in_window(item)
                and (allowed is None or item.device_id in allowed)
                and (source_system is None or item.source_system == source_system)
            )
        ]
        rows.sort(
            key=lambda item: (
                _utc(item.created_at_source or item.uploaded_at_source),
                item.device_id,
                _utc(item.observed_at),
            )
        )
        return tuple(rows)

    async def upsert_realtime_view_events(
        self,
        events: Iterable[RealtimeViewEvent],
    ) -> int:
        accepted = 0
        for event in events:
            _validate_view(event)
            if event.stream_id in self._views:
                continue
            self._views[event.stream_id] = event
            accepted += 1
        return accepted

    async def fetch_realtime_view_events(
        self,
        *,
        start: dt.datetime,
        end: dt.datetime,
        device_ids: Iterable[str] | None = None,
        usernames: Iterable[str] | None = None,
    ) -> tuple[RealtimeViewEvent, ...]:
        start_utc, end_utc = _window(start, end)
        allowed_devices = _id_set(device_ids)
        allowed_users = _id_set(usernames)
        rows = [
            event
            for event in self._views.values()
            if (
                start_utc <= _utc(event.closed_at) <= end_utc
                and (
                    allowed_devices is None
                    or event.device_id in allowed_devices
                )
                and (allowed_users is None or event.username in allowed_users)
            )
        ]
        rows.sort(
            key=lambda item: (
                _utc(item.opened_at),
                item.device_id,
                item.stream_id,
            )
        )
        return tuple(rows)

    async def upsert_alarm_events(
        self,
        events: Iterable[AlarmEvent],
    ) -> int:
        accepted = 0
        for event in events:
            _validate_alarm(event)
            key = (
                event.source_system,
                event.source_record_id,
                event.device_id,
                _utc(event.occurred_at),
                event.alarm_type_code,
            )
            current = self._alarms.get(key)
            if current is None or _newer_observation(event, current):
                self._alarms[key] = event
            accepted += 1
        return accepted

    async def fetch_alarm_events(
        self,
        *,
        start: dt.datetime,
        end: dt.datetime,
        device_ids: Iterable[str] | None = None,
        source_system: str | None = None,
    ) -> tuple[AlarmEvent, ...]:
        start_utc, end_utc = _window(start, end)
        allowed = _id_set(device_ids)
        rows = [
            event
            for event in self._alarms.values()
            if (
                start_utc
                <= _utc(event.occurred_at)
                <= end_utc
                and (allowed is None or event.device_id in allowed)
                and (source_system is None or event.source_system == source_system)
            )
        ]
        rows.sort(
            key=lambda item: (
                _utc(item.occurred_at),
                item.device_id,
                _utc(item.observed_at),
            )
        )
        return tuple(rows)


def _window(
    start: dt.datetime,
    end: dt.datetime,
) -> tuple[dt.datetime, dt.datetime]:
    start_utc = _aware(start, "start")
    end_utc = _aware(end, "end")
    if end_utc <= start_utc:
        raise ValueError("end must be after start")
    return start_utc, end_utc


def _id_set(values: Iterable[str] | None) -> set[str] | None:
    if values is None:
        return None
    return set(values)


def _utc(value: dt.datetime) -> dt.datetime:
    return _aware(value, "timestamp").astimezone(UTC)


def _aware(value: dt.datetime, name: str) -> dt.datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


def _newer_observation(
    candidate: object,
    current: object,
) -> bool:
    candidate_time = _observation_time(candidate)
    current_time = _observation_time(current)
    return candidate_time > current_time


def _observation_time(event: object) -> tuple[dt.datetime, dt.datetime]:
    observed = getattr(event, "observed_at")
    ingested = getattr(event, "ingested_at")
    return (_utc(observed), _utc(ingested))


def _validate_status(event: DeviceStatusEvent) -> None:
    _require_times(event, ("occurred_at", "observed_at", "ingested_at"))


def _validate_location(event: DeviceLocationEvent) -> None:
    _require_times(
        event,
        ("gps_occurred_at", "observed_at", "ingested_at"),
    )


def _validate_media(item: MediaFile) -> None:
    _require_times(item, ("observed_at", "ingested_at"))
    if item.created_at_source is not None:
        _aware(item.created_at_source, "created_at_source")
    if item.end_at_source is not None:
        _aware(item.end_at_source, "end_at_source")
    if item.uploaded_at_source is not None:
        _aware(item.uploaded_at_source, "uploaded_at_source")


def _validate_view(event: RealtimeViewEvent) -> None:
    _require_times(event, ("opened_at", "closed_at"))
    if event.first_frame_at is not None:
        _aware(event.first_frame_at, "first_frame_at")


def _validate_alarm(event: AlarmEvent) -> None:
    _require_times(
        event,
        ("occurred_at", "observed_at", "ingested_at"),
    )
    if event.handled_at is not None:
        _aware(event.handled_at, "handled_at")


def _require_times(
    event: object,
    names: tuple[str, ...],
) -> None:
    for name in names:
        _aware(getattr(event, name), name)
