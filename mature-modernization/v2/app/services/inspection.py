from __future__ import annotations

import datetime as dt
from collections import defaultdict
from collections import Counter
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
class HistoricalCoverage:
    """Actual data coverage for a requested window.

    ``completeness`` is one of ``FULL``, ``PARTIAL`` or ``EMPTY`` and is
    derived from distinct business-local calendar days that actually carry
    stored events. A 30-day request with only 3 days of history is reported
    as PARTIAL (3/30), never as a complete 30-day statistic.
    """

    requested_window_days: int
    available_coverage_days: int
    completeness: str
    coverage_start_date: str | None
    coverage_end_date: str | None


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
class DeviceGroupMetric:
    group_id: str | None
    device_count: int
    online_count: int
    offline_count: int
    unknown_count: int
    online_seconds: int


@dataclass(frozen=True, slots=True)
class MediaGroupMetric:
    group_id: str | None
    file_count: int
    video_count: int
    image_count: int
    audio_count: int
    video_duration_seconds: int
    file_size_bytes: int


@dataclass(frozen=True, slots=True)
class DeviceThresholdHit:
    device_id: str
    reference_at: dt.datetime
    age_seconds: float


@dataclass(frozen=True, slots=True)
class DeviceOverview:
    generated_at: dt.datetime
    scope_start: dt.datetime
    scope_end: dt.datetime
    coverage: HistoricalCoverage
    uptime: DeviceUptimeAggregationResult
    latest_by_device: tuple[DeviceLatestStatus, ...]
    groups: tuple[DeviceGroupMetric, ...]
    current_online_count: int
    current_offline_count: int
    current_unknown_count: int


@dataclass(frozen=True, slots=True)
class MediaOverview:
    generated_at: dt.datetime
    scope_start: dt.datetime
    scope_end: dt.datetime
    coverage: HistoricalCoverage
    media: MediaAggregationResult
    groups: tuple[MediaGroupMetric, ...]
    long_no_upload_devices: tuple[DeviceThresholdHit, ...]
    long_no_upload_governed: bool
    latest_uploaded_at: dt.datetime | None
    latest_created_at: dt.datetime | None
    daily_counts: tuple[tuple[str, int], ...]


@dataclass(frozen=True, slots=True)
class RealtimeOverview:
    generated_at: dt.datetime
    scope_start: dt.datetime
    scope_end: dt.datetime
    coverage: HistoricalCoverage
    aggregation: RealtimeViewAggregationResult
    latest_closed_at: dt.datetime | None


@dataclass(frozen=True, slots=True)
class AlarmOverview:
    generated_at: dt.datetime
    scope_start: dt.datetime
    scope_end: dt.datetime
    coverage: HistoricalCoverage
    aggregation: AlarmAggregationResult
    latest_occurred_at: dt.datetime | None


@dataclass(frozen=True, slots=True)
class LocationOverview:
    generated_at: dt.datetime
    scope_start: dt.datetime
    scope_end: dt.datetime
    coverage: HistoricalCoverage
    aggregation: DeviceLocationAggregationResult
    stale_location_devices: tuple[DeviceThresholdHit, ...]
    stale_location_governed: bool


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


@dataclass(frozen=True, slots=True)
class TableQuality:
    table: str
    row_count: int
    rows_with_quality_flags: int
    latest_at: dt.datetime | None
    distinct_device_count: int


@dataclass(frozen=True, slots=True)
class DataQualityOverview:
    generated_at: dt.datetime
    scope_start: dt.datetime
    scope_end: dt.datetime
    tables: tuple[TableQuality, ...]
    quality_flag_counts: tuple[tuple[str, int], ...]
    source_system_counts: tuple[tuple[str, int], ...]
    total_rows: int


@dataclass(frozen=True, slots=True)
class FlightsTasksOverview:
    """Read-only flights / routine-tasks view for the operational dashboard.

    Data comes from the existing CHA business source (Legacy ``/api/flights``
    and ``/api/routine-tasks``), normalized to the shared business contracts.
    This is a read-only reference view for inspectors; it is NOT an automatic
    matcher (no candidate is auto-associated to an inspection record here).
    """

    generated_at: dt.datetime
    scope_date: dt.date
    flights: tuple[tuple[str, str, str, str, str], ...]
    routine_tasks: tuple[tuple[str, str, str, str, str], ...]
    source_flight_count: int
    source_task_count: int
    invalid_flight_row_count: int
    invalid_task_row_count: int
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
        thresholds: Mapping[str, float] | None = None,
        business_client: Any | None = None,
    ) -> None:
        self._store = store
        self._business_tz = business_timezone
        self._thresholds = dict(thresholds or {})
        self._business_client = business_client

    async def device_overview(
        self,
        *,
        start: dt.datetime,
        end: dt.datetime,
        device_ids: Iterable[str] | None = None,
        requested_window_days: int | None = None,
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
            coverage=_historical_coverage(
                (event.occurred_at for event in events),
                window_start=start,
                window_end=end,
                business_tz=self._business_tz,
                requested_window_days=requested_window_days,
            ),
            uptime=uptime,
            latest_by_device=tuple(
                sorted(latest, key=lambda item: item.device_id)
            ),
            groups=_device_groups(latest, uptime.devices),
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
        requested_window_days: int | None = None,
        as_of: dt.datetime | None = None,
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
        as_of_utc = _aware(as_of).astimezone(UTC) if as_of else dt.datetime.now(UTC)
        long_no_upload_hours = self._thresholds.get(
            "long_no_upload_hours"
        )
        governed = long_no_upload_hours is not None
        hits: list[DeviceThresholdHit] = []
        if governed:
            latest_upload_by_device: dict[str, dt.datetime] = {}
            for item in files:
                if item.uploaded_at_source is None:
                    continue
                uploaded = item.uploaded_at_source.astimezone(UTC)
                previous = latest_upload_by_device.get(item.device_id)
                if previous is None or uploaded > previous:
                    latest_upload_by_device[item.device_id] = uploaded
            threshold_seconds = long_no_upload_hours * 3600
            for device_id, last_uploaded in sorted(
                latest_upload_by_device.items()
            ):
                age = (as_of_utc - last_uploaded).total_seconds()
                if age > threshold_seconds:
                    hits.append(
                        DeviceThresholdHit(
                            device_id=device_id,
                            reference_at=last_uploaded,
                            age_seconds=round(age, 3),
                        )
                    )
        return MediaOverview(
            generated_at=dt.datetime.now(UTC),
            scope_start=_aware(start).astimezone(UTC),
            scope_end=_aware(end).astimezone(UTC),
            coverage=_historical_coverage(
                (
                    timestamp
                    for item in files
                    for timestamp in (
                        item.created_at_source,
                        item.uploaded_at_source,
                    )
                    if timestamp is not None
                ),
                window_start=start,
                window_end=end,
                business_tz=self._business_tz,
                requested_window_days=requested_window_days,
            ),
            media=media,
            groups=_media_groups(files),
            long_no_upload_devices=tuple(hits),
            long_no_upload_governed=governed,
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
        requested_window_days: int | None = None,
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
            coverage=_historical_coverage(
                (event.closed_at for event in events),
                window_start=start,
                window_end=end,
                business_tz=self._business_tz,
                requested_window_days=requested_window_days,
            ),
            aggregation=aggregate_realtime_views(events),
            latest_closed_at=max(
                (
                    event.closed_at.astimezone(UTC)
                    for event in events
                ),
                default=None,
            ),
        )

    async def alarm_overview(
        self,
        *,
        start: dt.datetime,
        end: dt.datetime,
        device_ids: Iterable[str] | None = None,
        requested_window_days: int | None = None,
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
            coverage=_historical_coverage(
                (event.occurred_at for event in events),
                window_start=start,
                window_end=end,
                business_tz=self._business_tz,
                requested_window_days=requested_window_days,
            ),
            aggregation=aggregate_alarm_events(events),
            latest_occurred_at=max(
                (
                    event.occurred_at.astimezone(UTC)
                    for event in events
                ),
                default=None,
            ),
        )

    async def location_overview(
        self,
        *,
        start: dt.datetime,
        end: dt.datetime,
        device_ids: Iterable[str] | None = None,
        requested_window_days: int | None = None,
        as_of: dt.datetime | None = None,
    ) -> LocationOverview:
        events = await self._store.fetch_device_location_events(
            start=start,
            end=end,
            device_ids=device_ids,
        )
        aggregation = aggregate_device_locations(
            events,
            window_start=start,
            window_end=end,
        )
        as_of_utc = _aware(as_of).astimezone(UTC) if as_of else dt.datetime.now(UTC)
        stale_location_hours = self._thresholds.get(
            "stale_location_hours"
        )
        governed = stale_location_hours is not None
        hits: list[DeviceThresholdHit] = []
        if governed:
            threshold_seconds = stale_location_hours * 3600
            for metric in aggregation.devices:
                age = (as_of_utc - metric.last_gps_at).total_seconds()
                if age > threshold_seconds:
                    hits.append(
                        DeviceThresholdHit(
                            device_id=metric.device_id,
                            reference_at=metric.last_gps_at,
                            age_seconds=round(age, 3),
                        )
                    )
        return LocationOverview(
            generated_at=dt.datetime.now(UTC),
            scope_start=_aware(start).astimezone(UTC),
            scope_end=_aware(end).astimezone(UTC),
            coverage=_historical_coverage(
                (event.gps_occurred_at for event in events),
                window_start=start,
                window_end=end,
                business_tz=self._business_tz,
                requested_window_days=requested_window_days,
            ),
            aggregation=aggregation,
            stale_location_devices=tuple(hits),
            stale_location_governed=governed,
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

    async def data_quality(
        self,
        *,
        start: dt.datetime,
        end: dt.datetime,
        device_ids: Iterable[str] | None = None,
    ) -> DataQualityOverview:
        start_utc = _aware(start).astimezone(UTC)
        end_utc = _aware(end).astimezone(UTC)
        if end_utc <= start_utc:
            raise ValueError("end must be after start")
        device_filter = tuple(device_ids) if device_ids else None
        status_events = await self._store.fetch_device_status_events(
            start=start,
            end=end,
            device_ids=device_filter,
        )
        location_events = await self._store.fetch_device_location_events(
            start=start,
            end=end,
            device_ids=device_filter,
        )
        media_files = await self._store.fetch_media_files(
            start=start,
            end=end,
            device_ids=device_filter,
        )
        view_events = await self._store.fetch_realtime_view_events(
            start=start,
            end=end,
            device_ids=device_filter,
        )
        alarm_events = await self._store.fetch_alarm_events(
            start=start,
            end=end,
            device_ids=device_filter,
        )

        tables = (
            _table_quality(
                "device_status_events",
                status_events,
                _latest_status_time,
            ),
            _table_quality(
                "device_location_events",
                location_events,
                _latest_location_time,
            ),
            _table_quality(
                "media_files",
                media_files,
                _latest_media_time,
            ),
            _table_quality(
                "realtime_view_events",
                view_events,
                _latest_view_time,
            ),
            _table_quality(
                "alarm_events",
                alarm_events,
                _latest_alarm_time,
            ),
        )

        flag_counts: Counter[str] = Counter()
        source_counts: Counter[str] = Counter()
        total_rows = 0
        for events in (
            status_events,
            location_events,
            media_files,
            view_events,
            alarm_events,
        ):
            for event in events:
                total_rows += 1
                source_counts[event.source_system] += 1
                for flag in event.quality_flags:
                    flag_counts[flag] += 1

        return DataQualityOverview(
            generated_at=dt.datetime.now(UTC),
            scope_start=start_utc,
            scope_end=end_utc,
            tables=tables,
            quality_flag_counts=tuple(sorted(flag_counts.items())),
            source_system_counts=tuple(sorted(source_counts.items())),
            total_rows=total_rows,
        )

    async def flights_tasks_overview(
        self,
        *,
        scope_date: dt.date | None = None,
        business_client_cookie: str = "",
    ) -> FlightsTasksOverview:
        """Return a read-only flights / routine-tasks snapshot for a date.

        Requires an injected ``business_client`` exposing
        ``fetch_flights(date)`` and ``fetch_routine_tasks(date)`` returning
        ``BusinessFlight`` / ``BusinessRoutineTask`` tuples (see
        ``app.services.business_candidates``). When no business client is
        wired the result is empty with an explicit quality flag.
        """

        generated = dt.datetime.now(UTC)
        local_now = generated.astimezone(self._business_tz)
        scope = scope_date or local_now.date()
        business_client = self._business_client
        if business_client is not None and business_client_cookie:
            with_cookie = getattr(business_client, "with_cookie", None)
            if callable(with_cookie):
                business_client = with_cookie(business_client_cookie)
        if business_client is None:
            return FlightsTasksOverview(
                generated_at=generated,
                scope_date=scope,
                flights=(),
                routine_tasks=(),
                source_flight_count=0,
                source_task_count=0,
                invalid_flight_row_count=0,
                invalid_task_row_count=0,
                quality_flags=("business_client_not_wired",),
            )

        flights: list[tuple[str, str, str, str, str]] = []
        tasks: list[tuple[str, str, str, str, str]] = []
        invalid_flights = 0
        invalid_tasks = 0
        flags: set[str] = set()
        try:
            flight_rows = await business_client.fetch_flights(scope)
            task_rows = await business_client.fetch_routine_tasks(scope)
        except Exception:
            return FlightsTasksOverview(
                generated_at=generated,
                scope_date=scope,
                flights=(),
                routine_tasks=(),
                source_flight_count=0,
                source_task_count=0,
                invalid_flight_row_count=0,
                invalid_task_row_count=0,
                quality_flags=("business_source_unavailable",),
            )
        for row in flight_rows:
            flight_no = _safe_text(getattr(row, "flight_no", None))
            if not flight_no:
                invalid_flights += 1
                continue
            flights.append(
                (
                    _safe_text(getattr(row, "source_id", None)),
                    flight_no,
                    _safe_text(getattr(row, "aircraft_no", None)),
                    _safe_text(getattr(row, "departure_city", None))
                    + "→"
                    + _safe_text(getattr(row, "arrival_city", None)),
                    _safe_text(getattr(row, "status_label", None)),
                )
            )
        for row in task_rows:
            task_id = _safe_text(getattr(row, "source_id", None))
            if not task_id:
                invalid_tasks += 1
                continue
            tasks.append(
                (
                    task_id,
                    _safe_text(getattr(row, "aircraft_no", None)),
                    _safe_text(getattr(row, "task_type_name", None))
                    or _safe_text(getattr(row, "task_type", None)),
                    _safe_text(getattr(row, "bay", None)),
                    _safe_text(getattr(row, "task_status_name", None)),
                )
            )
        if invalid_flights:
            flags.add("invalid_flight_rows_ignored")
        if invalid_tasks:
            flags.add("invalid_task_rows_ignored")
        return FlightsTasksOverview(
            generated_at=generated,
            scope_date=scope,
            flights=tuple(sorted(flights)),
            routine_tasks=tuple(sorted(tasks)),
            source_flight_count=len(flight_rows),
            source_task_count=len(task_rows),
            invalid_flight_row_count=invalid_flights,
            invalid_task_row_count=invalid_tasks,
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


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


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
        elif latest.status_code == 0:
            online = False
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


def _device_groups(
    latest: Iterable[DeviceLatestStatus],
    uptime_devices: Iterable[Any],
) -> tuple[DeviceGroupMetric, ...]:
    latest_by_device = {
        item.device_id: item
        for item in latest
    }
    groups: dict[str | None, list[Any]] = defaultdict(list)
    for metric in uptime_devices:
        groups[metric.group_id].append(metric)
    result: list[DeviceGroupMetric] = []
    for group_id, group_metrics in groups.items():
        device_ids = {metric.device_id for metric in group_metrics}
        online = sum(
            1
            for device_id in device_ids
            if latest_by_device.get(device_id)
            and latest_by_device[device_id].latest_online is True
        )
        offline = sum(
            1
            for device_id in device_ids
            if latest_by_device.get(device_id)
            and latest_by_device[device_id].latest_online is False
        )
        unknown = max(
            0,
            len(device_ids) - online - offline,
        )
        online_seconds = sum(
            metric.online_seconds
            for metric in group_metrics
        )
        result.append(
            DeviceGroupMetric(
                group_id=group_id,
                device_count=len(device_ids),
                online_count=online,
                offline_count=offline,
                unknown_count=unknown,
                online_seconds=online_seconds,
            )
        )
    return tuple(
        sorted(
            result,
            key=lambda item: (item.group_id or ""),
        )
    )


def _media_groups(
    files: Iterable[MediaFile],
) -> tuple[MediaGroupMetric, ...]:
    groups: dict[str | None, list[MediaFile]] = defaultdict(list)
    for item in files:
        groups[item.group_id].append(item)
    result: list[MediaGroupMetric] = []
    for group_id, group_files in groups.items():
        video_count = sum(
            1 for item in group_files if item.media_kind == "video"
        )
        image_count = sum(
            1 for item in group_files if item.media_kind == "image"
        )
        audio_count = sum(
            1 for item in group_files if item.media_kind == "audio"
        )
        video_duration_seconds = sum(
            item.duration_seconds or 0
            for item in group_files
            if item.media_kind == "video"
        )
        file_size_bytes = sum(
            item.file_size_bytes or 0
            for item in group_files
        )
        result.append(
            MediaGroupMetric(
                group_id=group_id,
                file_count=len(group_files),
                video_count=video_count,
                image_count=image_count,
                audio_count=audio_count,
                video_duration_seconds=video_duration_seconds,
                file_size_bytes=file_size_bytes,
            )
        )
    return tuple(
        sorted(
            result,
            key=lambda item: (item.group_id or ""),
        )
    )


def _table_quality(
    table: str,
    events: Iterable[object],
    latest_fn,
) -> TableQuality:
    rows = list(events)
    latest_values = [
        value
        for value in (latest_fn(event) for event in rows)
        if value is not None
    ]
    latest_at = max(latest_values).astimezone(UTC) if latest_values else None
    device_ids = {
        getattr(event, "device_id")
        for event in rows
    }
    rows_with_flags = sum(
        1
        for event in rows
        if getattr(event, "quality_flags", ())
    )
    return TableQuality(
        table=table,
        row_count=len(rows),
        rows_with_quality_flags=rows_with_flags,
        latest_at=latest_at,
        distinct_device_count=len(device_ids),
    )


def _latest_status_time(event: object):
    return getattr(event, "occurred_at")


def _latest_location_time(event: object):
    return getattr(event, "gps_occurred_at")


def _latest_media_time(item: object):
    return (
        getattr(item, "created_at_source")
        or getattr(item, "uploaded_at_source")
    )


def _latest_view_time(event: object):
    return getattr(event, "closed_at")


def _latest_alarm_time(event: object):
    return getattr(event, "occurred_at")


def _aware(value: dt.datetime) -> dt.datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("scope times must be timezone-aware")
    return value


def _historical_coverage(
    timestamps: Iterable[dt.datetime],
    *,
    window_start: dt.datetime,
    window_end: dt.datetime,
    business_tz: dt.tzinfo,
    requested_window_days: int | None,
) -> HistoricalCoverage:
    start_utc = _aware(window_start).astimezone(UTC)
    end_utc = _aware(window_end).astimezone(UTC)
    if requested_window_days is None:
        requested_window_days = max(1, round((end_utc - start_utc).days))

    days: set[dt.date] = set()
    for timestamp in timestamps:
        aware = _aware(timestamp)
        if start_utc <= aware.astimezone(UTC) <= end_utc:
            days.add(aware.astimezone(business_tz).date())

    available = len(days)
    if available == 0:
        completeness = "EMPTY"
    elif available >= requested_window_days:
        completeness = "FULL"
    else:
        completeness = "PARTIAL"

    return HistoricalCoverage(
        requested_window_days=requested_window_days,
        available_coverage_days=available,
        completeness=completeness,
        coverage_start_date=(
            min(days).isoformat() if days else None
        ),
        coverage_end_date=(
            max(days).isoformat() if days else None
        ),
    )
