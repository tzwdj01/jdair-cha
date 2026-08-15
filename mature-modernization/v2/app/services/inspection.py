from __future__ import annotations

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from ..data.metrics import (
    AlarmAggregationResult,
    DeviceLocationAggregationResult,
    DeviceUptimeAggregationResult,
    MediaAggregationResult,
    RealtimeViewAggregationResult,
    aggregate_alarm_events,
    aggregate_device_locations,
    aggregate_device_uptime,
    aggregate_media_files,
    aggregate_realtime_views,
)
from ..data.normalization import DeviceStatusEvent, MediaFile
from ..data.store import InspectionStore


UTC = dt.timezone.utc
SHANGHAI = dt.timezone(dt.timedelta(hours=8), name="Asia/Shanghai")


@dataclass(frozen=True, slots=True)
class DeviceLatestStatus:
    device_id: str
    latest_status_code: int | None
    latest_online: bool | None
    latest_occurred_at: dt.datetime | None
    last_online_at: dt.datetime | None
    last_offline_at: dt.datetime | None
    quality_flags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DeviceOverview:
    generated_at: dt.datetime
    scope_start: dt.datetime
    scope_end: dt.datetime
    uptime: DeviceUptimeAggregationResult
    latest_by_device: tuple[DeviceLatestStatus, ...]
    current_online_count: int
    current_offline_count: int
    current_unknown_count: int


@dataclass(frozen=True, slots=True)
class MediaOverview:
    generated_at: dt.datetime
    scope_start: dt.datetime
    scope_end: dt.datetime
    media: MediaAggregationResult
    latest_uploaded_at: dt.datetime | None
    latest_created_at: dt.datetime | None
    daily_counts: tuple[tuple[str, int], ...]


@dataclass(frozen=True, slots=True)
class RealtimeOverview:
    generated_at: dt.datetime
    scope_start: dt.datetime
    scope_end: dt.datetime
    aggregation: RealtimeViewAggregationResult


@dataclass(frozen=True, slots=True)
class AlarmOverview:
    generated_at: dt.datetime
    scope_start: dt.datetime
    scope_end: dt.datetime
    aggregation: AlarmAggregationResult


@dataclass(frozen=True, slots=True)
class LocationOverview:
    generated_at: dt.datetime
    scope_start: dt.datetime
    scope_end: dt.datetime
    aggregation: DeviceLocationAggregationResult


@dataclass(frozen=True, slots=True)
class LocationPointSummary:
    gps_occurred_at: dt.datetime
    speed_value: float | None
    direction_value: float | None
    accuracy_value: float | None
    battery_value: float | None
    gps_type_code: int | str | None
    network_type_code: int | str | None
    quality_flags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DeviceTimeline:
    device_id: str
    scope_start: dt.datetime
    scope_end: dt.datetime
    status_events: tuple[DeviceStatusEvent, ...]
    media_files: tuple[MediaFile, ...]
    location_points: tuple[LocationPointSummary, ...]
    status_event_count: int
    media_file_count: int
    location_point_count: int
    coordinates_restricted: bool
    quality_flags: tuple[str, ...]


class InspectionDataService:
    """Read-only page-oriented data service over the InspectionStore.

    Every value comes from durable store rows and deterministic aggregation.
    No metric is invented and no missing source is converted to zero. Threshold
    based classifications (long-time offline, long-time no upload, stale
    location) are intentionally not produced until a governed threshold
    exists; raw coverage/age values are exposed instead.
    """

    def __init__(
        self,
        store: InspectionStore,
        business_timezone: dt.tzinfo = SHANGHAI,
    ) -> None:
        self._store = store
        self._business_tz = business_timezone

    async def device_overview(
        self,
        *,
        start: dt.datetime,
        end: dt.datetime,
        device_ids: Iterable[str] | None = None,
    ) -> DeviceOverview:
        events = await self._store.fetch_device_status_events(
            start=start,
            end=end,
            device_ids=device_ids,
        )
        uptime = aggregate_device_uptime(
            _project_status_events(events),
            window_start=start,
            window_end=end,
            source_timezone=UTC,
        )
        latest = _latest_status_by_device(events)
        online = sum(
            1
            for item in latest
            if item.latest_online is True
        )
        offline = sum(
            1
            for item in latest
            if item.latest_online is False
        )
        unknown = sum(
            1
            for item in latest
            if item.latest_online is None
        )
        return DeviceOverview(
            generated_at=dt.datetime.now(UTC),
            scope_start=_aware(start).astimezone(UTC),
            scope_end=_aware(end).astimezone(UTC),
            uptime=uptime,
            latest_by_device=tuple(
                sorted(latest, key=lambda item: item.device_id)
            ),
            current_online_count=online,
            current_offline_count=offline,
            current_unknown_count=unknown,
        )

    async def media_overview(
        self,
        *,
        start: dt.datetime,
        end: dt.datetime,
        device_ids: Iterable[str] | None = None,
    ) -> MediaOverview:
        files = await self._store.fetch_media_files(
            start=start,
            end=end,
            device_ids=device_ids,
        )
        media = aggregate_media_files(
            _project_media_files(files),
            records_total=len(files),
        )
        latest_uploaded = max(
            (
                item.uploaded_at_source
                for item in files
                if item.uploaded_at_source is not None
            ),
            default=None,
        )
        latest_created = max(
            (
                item.created_at_source
                for item in files
                if item.created_at_source is not None
            ),
            default=None,
        )
        return MediaOverview(
            generated_at=dt.datetime.now(UTC),
            scope_start=_aware(start).astimezone(UTC),
            scope_end=_aware(end).astimezone(UTC),
            media=media,
            latest_uploaded_at=(
                latest_uploaded.astimezone(UTC)
                if latest_uploaded is not None
                else None
            ),
            latest_created_at=(
                latest_created.astimezone(UTC)
                if latest_created is not None
                else None
            ),
            daily_counts=_daily_media_counts(
                files,
                business_tz=self._business_tz,
            ),
        )

    async def realtime_overview(
        self,
        *,
        start: dt.datetime,
        end: dt.datetime,
        device_ids: Iterable[str] | None = None,
        usernames: Iterable[str] | None = None,
    ) -> RealtimeOverview:
        events = await self._store.fetch_realtime_view_events(
            start=start,
            end=end,
            device_ids=device_ids,
            usernames=usernames,
        )
        return RealtimeOverview(
            generated_at=dt.datetime.now(UTC),
            scope_start=_aware(start).astimezone(UTC),
            scope_end=_aware(end).astimezone(UTC),
            aggregation=aggregate_realtime_views(events),
        )

    async def alarm_overview(
        self,
        *,
        start: dt.datetime,
        end: dt.datetime,
        device_ids: Iterable[str] | None = None,
    ) -> AlarmOverview:
        events = await self._store.fetch_alarm_events(
            start=start,
            end=end,
            device_ids=device_ids,
        )
        return AlarmOverview(
            generated_at=dt.datetime.now(UTC),
            scope_start=_aware(start).astimezone(UTC),
            scope_end=_aware(end).astimezone(UTC),
            aggregation=aggregate_alarm_events(events),
        )

    async def location_overview(
        self,
        *,
        start: dt.datetime,
        end: dt.datetime,
        device_ids: Iterable[str] | None = None,
    ) -> LocationOverview:
        events = await self._store.fetch_device_location_events(
            start=start,
            end=end,
            device_ids=device_ids,
        )
        return LocationOverview(
            generated_at=dt.datetime.now(UTC),
            scope_start=_aware(start).astimezone(UTC),
            scope_end=_aware(end).astimezone(UTC),
            aggregation=aggregate_device_locations(
                events,
                window_start=start,
                window_end=end,
            ),
        )

    async def device_timeline(
        self,
        *,
        device_id: str,
        start: dt.datetime,
        end: dt.datetime,
    ) -> DeviceTimeline:
        normalized_device_id = str(device_id or "").strip()
        if not normalized_device_id:
            raise ValueError("device_id is required")
        status_events = await self._store.fetch_device_status_events(
            start=start,
            end=end,
            device_ids=[normalized_device_id],
        )
        media_files = await self._store.fetch_media_files(
            start=start,
            end=end,
            device_ids=[normalized_device_id],
        )
        location_events = await self._store.fetch_device_location_events(
            start=start,
            end=end,
            device_ids=[normalized_device_id],
        )
        location_points = tuple(
            sorted(
                (
                    LocationPointSummary(
                        gps_occurred_at=event.gps_occurred_at.astimezone(
                            UTC
                        ),
                        speed_value=event.speed_value,
                        direction_value=event.direction_value,
                        accuracy_value=event.accuracy_value,
                        battery_value=event.battery_value,
                        gps_type_code=event.gps_type_code,
                        network_type_code=event.network_type_code,
                        quality_flags=event.quality_flags,
                    )
                    for event in location_events
                ),
                key=lambda item: (
                    item.gps_occurred_at,
                    str(item.speed_value or ""),
                ),
            )
        )
        flags: set[str] = set()
        for events in (
            status_events,
            media_files,
            location_events,
        ):
            if any(getattr(event, "quality_flags", ()) for event in events):
                flags.add("source_event_quality_flags_present")
        return DeviceTimeline(
            device_id=normalized_device_id,
            scope_start=_aware(start).astimezone(UTC),
            scope_end=_aware(end).astimezone(UTC),
            status_events=tuple(
                sorted(
                    status_events,
                    key=lambda event: (
                        event.occurred_at,
                        event.observed_at,
                    ),
                )
            ),
            media_files=tuple(
                sorted(
                    media_files,
                    key=lambda item: (
                        item.created_at_source or item.uploaded_at_source,
                        item.observed_at,
                    ),
                )
            ),
            location_points=location_points,
            status_event_count=len(status_events),
            media_file_count=len(media_files),
            location_point_count=len(location_points),
            coordinates_restricted=True,
            quality_flags=tuple(sorted(flags)),
        )


def _project_status_events(
    events: Iterable[DeviceStatusEvent],
) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    for event in events:
        rows.append(
            {
                "devId": event.device_id,
                "groupId": event.group_id,
                "id": event.source_record_id,
                "status": event.status_code,
                "time": event.occurred_at,
            }
        )
    return rows


def _project_media_files(
    files: Iterable[MediaFile],
) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    for item in files:
        rows.append(
            {
                "devId": item.device_id,
                "groupId": item.group_id,
                "fType": item.file_type_code,
                "fileLen": item.file_size_bytes,
                "duration": item.duration_seconds,
            }
        )
    return rows


def _latest_status_by_device(
    events: Iterable[DeviceStatusEvent],
) -> list[DeviceLatestStatus]:
    grouped: dict[str, list[DeviceStatusEvent]] = defaultdict(list)
    for event in events:
        grouped[event.device_id].append(event)

    result: list[DeviceLatestStatus] = []
    for device_id, device_events in grouped.items():
        ordered = sorted(
            device_events,
            key=lambda event: (
                event.occurred_at,
                event.observed_at,
                event.ingested_at,
            ),
        )
        latest = ordered[-1]
        online: bool | None
        flags: set[str] = set()
        if latest.status_code == 1:
            online = True
        else:
            online = None
            flags.add("non_online_status_map_partial")
            flags.add("online_state_unknown")
        online_times = [
            event.occurred_at
            for event in ordered
            if event.status_code == 1
        ]
        offline_times = [
            event.occurred_at
            for event in ordered
            if event.status_code != 1
        ]
        if latest.quality_flags:
            flags.update(latest.quality_flags)
        result.append(
            DeviceLatestStatus(
                device_id=device_id,
                latest_status_code=latest.status_code,
                latest_online=online,
                latest_occurred_at=latest.occurred_at.astimezone(UTC),
                last_online_at=(
                    max(online_times).astimezone(UTC)
                    if online_times
                    else None
                ),
                last_offline_at=(
                    max(offline_times).astimezone(UTC)
                    if offline_times
                    else None
                ),
                quality_flags=tuple(sorted(flags)),
            )
        )
    return result


def _daily_media_counts(
    files: Iterable[MediaFile],
    *,
    business_tz: dt.tzinfo,
) -> tuple[tuple[str, int], ...]:
    counts: dict[str, int] = defaultdict(int)
    for item in files:
        time_value = item.created_at_source or item.uploaded_at_source
        if time_value is None:
            continue
        day = time_value.astimezone(business_tz).date().isoformat()
        counts[day] += 1
    return tuple(sorted(counts.items()))


def _aware(value: dt.datetime) -> dt.datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("scope times must be timezone-aware")
    return value
