from __future__ import annotations

import datetime as dt
import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .normalization import AlarmEvent, DeviceLocationEvent
from .realtime_views import RealtimeViewEvent


UTC = dt.timezone.utc


@dataclass(frozen=True, slots=True)
class DeviceUptimeMetric:
    device_id: str
    group_id: str | None
    window_start: dt.datetime
    window_end: dt.datetime
    online_seconds: int
    offline_transition_count: int
    first_online_at: dt.datetime | None
    last_offline_at: dt.datetime | None
    event_count: int
    quality_flags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DeviceUptimeAggregationResult:
    devices: tuple[DeviceUptimeMetric, ...]
    fetched_count: int
    invalid_row_count: int
    duplicate_event_count: int
    quality_flags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DeviceLocationMetric:
    device_id: str
    event_count: int
    distinct_coordinate_count: int
    first_gps_at: dt.datetime
    last_gps_at: dt.datetime
    source_span_seconds: float
    latest_age_seconds: float
    speed_value_count: int
    direction_value_count: int
    accuracy_value_count: int
    battery_value_count: int
    gps_type_count: int
    network_type_count: int
    quality_flags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DeviceLocationAggregationResult:
    devices: tuple[DeviceLocationMetric, ...]
    window_start: dt.datetime
    window_end: dt.datetime
    source_event_count: int
    included_event_count: int
    duplicate_event_count: int
    updated_observation_count: int
    conflicting_timestamp_count: int
    out_of_window_count: int
    invalid_event_count: int
    partial: bool
    quality_flags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MediaDeviceMetric:
    device_id: str
    group_id: str | None
    total_files: int
    image_count: int
    audio_count: int
    video_count: int
    device_file_count: int
    unknown_type_count: int
    video_duration_seconds: int
    file_size_bytes: int
    quality_flags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MediaAggregationResult:
    devices: tuple[MediaDeviceMetric, ...]
    fetched_count: int
    records_total: int | None
    invalid_row_count: int
    partial: bool
    quality_flags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RealtimeViewDimensionMetric:
    dimension_id: str
    view_count: int
    played_count: int
    first_frame_count: int
    connection_duration_seconds: float
    view_duration_seconds: float
    first_frame_latency_seconds: float
    result_counts: tuple[tuple[str, int], ...]


@dataclass(frozen=True, slots=True)
class RealtimeViewAggregationResult:
    users: tuple[RealtimeViewDimensionMetric, ...]
    devices: tuple[RealtimeViewDimensionMetric, ...]
    event_count: int
    duplicate_event_count: int
    conflicting_stream_count: int
    invalid_event_count: int
    played_count: int
    first_frame_count: int
    connection_duration_seconds: float
    view_duration_seconds: float
    first_frame_latency_seconds: float
    average_first_frame_latency_seconds: float | None
    result_counts: tuple[tuple[str, int], ...]
    error_counts: tuple[tuple[str, int], ...]
    partial: bool
    quality_flags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AlarmDeviceMetric:
    device_id: str
    alarm_count: int
    alarm_type_counts: tuple[tuple[int, int], ...]


@dataclass(frozen=True, slots=True)
class AlarmAggregationResult:
    devices: tuple[AlarmDeviceMetric, ...]
    alarm_count: int
    duplicate_row_count: int
    updated_record_count: int
    conflicting_record_count: int
    alarm_type_counts: tuple[tuple[int, int], ...]
    alarm_status_counts: tuple[tuple[int, int], ...]
    deal_status_counts: tuple[tuple[int, int], ...]
    missing_alarm_status_count: int
    missing_deal_status_count: int
    partial: bool
    quality_flags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _OnlineEvent:
    source_id: str
    device_id: str
    group_id: str | None
    status: int
    occurred_at: dt.datetime


def aggregate_device_uptime(
    rows: Iterable[Mapping[str, Any]],
    *,
    window_start: dt.datetime,
    window_end: dt.datetime,
    source_timezone: dt.tzinfo,
) -> DeviceUptimeAggregationResult:
    """Build range-clipped uptime from AEE-style status/time transition rows.

    Current AEE evidence shows ``status == 1`` is treated as online. The
    complete non-1 status map is not yet verified, so every result carries a
    quality flag documenting that provisional rule.
    """

    start = _require_aware(window_start, "window_start").astimezone(UTC)
    end = _require_aware(window_end, "window_end").astimezone(UTC)
    if end <= start:
        raise ValueError("window_end must be after window_start")

    source_rows = list(rows)
    grouped: dict[str, list[_OnlineEvent]] = defaultdict(list)
    invalid_by_device: dict[str, int] = defaultdict(int)
    invalid_row_count = 0
    for index, row in enumerate(source_rows):
        device_id = str(row.get("devId") or "").strip()
        if not device_id:
            invalid_row_count += 1
            continue
        try:
            occurred_at = _parse_source_time(
                row.get("time"),
                source_timezone=source_timezone,
            )
            status = int(row.get("status"))
        except (TypeError, ValueError):
            invalid_by_device[device_id] += 1
            invalid_row_count += 1
            continue
        source_id = str(row.get("id") or f"row-{index}")
        group_id = _optional_text(row.get("groupId"))
        grouped[device_id].append(
            _OnlineEvent(
                source_id=source_id,
                device_id=device_id,
                group_id=group_id,
                status=status,
                occurred_at=occurred_at,
            )
        )

    metrics: list[DeviceUptimeMetric] = []
    duplicate_event_count = 0
    for device_id, source_events in grouped.items():
        events = _deduplicate_online_events(source_events)
        duplicate_event_count += len(source_events) - len(events)
        events.sort(
            key=lambda item: (
                item.occurred_at,
                0 if item.status == 1 else 1,
                item.status,
                item.source_id,
            )
        )
        group_id = next(
            (item.group_id for item in reversed(events) if item.group_id),
            None,
        )
        before_start = [item for item in events if item.occurred_at < start]
        in_window = [
            item for item in events if start <= item.occurred_at <= end
        ]
        current_online: bool | None = None
        cursor = start
        if before_start:
            current_online = before_start[-1].status == 1

        online_seconds = 0.0
        offline_transition_count = 0
        first_online_at: dt.datetime | None = None
        last_offline_at: dt.datetime | None = None
        flags = {"non_online_status_map_partial"}
        statuses_by_time: dict[dt.datetime, set[int]] = defaultdict(set)
        for event in events:
            statuses_by_time[event.occurred_at].add(event.status)
        if any(len(statuses) > 1 for statuses in statuses_by_time.values()):
            flags.add("conflicting_status_same_time")
        if current_online is None:
            flags.add("missing_start_state")
        elif current_online:
            first_online_at = start
            flags.add("online_at_window_start")
        if invalid_by_device.get(device_id):
            flags.add("invalid_rows_ignored")

        for event in in_window:
            if current_online is True:
                online_seconds += max(
                    0.0,
                    (event.occurred_at - cursor).total_seconds(),
                )
            next_online = event.status == 1
            if next_online and current_online is not True:
                first_online_at = first_online_at or event.occurred_at
            if not next_online and current_online is True:
                offline_transition_count += 1
                last_offline_at = event.occurred_at
            current_online = next_online
            cursor = event.occurred_at

        if current_online is True:
            online_seconds += max(0.0, (end - cursor).total_seconds())
            flags.add("open_interval_clipped_to_window_end")

        metrics.append(
            DeviceUptimeMetric(
                device_id=device_id,
                group_id=group_id,
                window_start=start,
                window_end=end,
                online_seconds=round(online_seconds),
                offline_transition_count=offline_transition_count,
                first_online_at=first_online_at,
                last_offline_at=last_offline_at,
                event_count=len(in_window),
                quality_flags=tuple(sorted(flags)),
            )
        )

    result_flags: set[str] = set()
    if invalid_row_count:
        result_flags.add("invalid_rows_ignored")
    if duplicate_event_count:
        result_flags.add("duplicate_events_removed")
    return DeviceUptimeAggregationResult(
        devices=tuple(sorted(metrics, key=lambda item: item.device_id)),
        fetched_count=len(source_rows),
        invalid_row_count=invalid_row_count,
        duplicate_event_count=duplicate_event_count,
        quality_flags=tuple(sorted(result_flags)),
    )


def aggregate_media_files(
    rows: Iterable[Mapping[str, Any]],
    *,
    records_total: int | None = None,
    query_limit: int | None = None,
) -> MediaAggregationResult:
    """Aggregate AEE RecordFileList rows without page-display rounding."""

    source_rows = list(rows)
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    invalid_row_count = 0
    for row in source_rows:
        device_id = str(row.get("devId") or "").strip()
        if not device_id:
            invalid_row_count += 1
            continue
        grouped[device_id].append(row)

    device_metrics: list[MediaDeviceMetric] = []
    for device_id, device_rows in grouped.items():
        counts = {1: 0, 2: 0, 3: 0, 4: 0}
        unknown_type_count = 0
        video_duration_seconds = 0
        file_size_bytes = 0
        flags: set[str] = set()
        group_id: str | None = None

        for row in device_rows:
            group_id = _optional_text(row.get("groupId")) or group_id
            try:
                file_type = int(row.get("fType"))
            except (TypeError, ValueError):
                file_type = -1
            if file_type in counts:
                counts[file_type] += 1
            else:
                unknown_type_count += 1
                flags.add("unknown_file_type")

            size = _non_negative_int(row.get("fileLen"))
            if size is None:
                flags.add("invalid_file_size_ignored")
            else:
                file_size_bytes += size

            if file_type == 3:
                duration = _non_negative_int(row.get("duration"))
                if duration is None:
                    flags.add("invalid_video_duration_ignored")
                else:
                    video_duration_seconds += duration

        device_metrics.append(
            MediaDeviceMetric(
                device_id=device_id,
                group_id=group_id,
                total_files=len(device_rows),
                image_count=counts[1],
                audio_count=counts[2],
                video_count=counts[3],
                device_file_count=counts[4],
                unknown_type_count=unknown_type_count,
                video_duration_seconds=video_duration_seconds,
                file_size_bytes=file_size_bytes,
                quality_flags=tuple(sorted(flags)),
            )
        )

    fetched_count = len(source_rows)
    partial = bool(
        records_total is not None and records_total > fetched_count
    )
    quality_flags: set[str] = set()
    if partial:
        quality_flags.add("records_total_exceeds_fetched_count")
    if query_limit is not None and fetched_count >= query_limit:
        partial = True
        quality_flags.add("query_limit_reached")
    if invalid_row_count:
        quality_flags.add("rows_without_device_ignored")

    return MediaAggregationResult(
        devices=tuple(
            sorted(device_metrics, key=lambda item: item.device_id)
        ),
        fetched_count=fetched_count,
        records_total=records_total,
        invalid_row_count=invalid_row_count,
        partial=partial,
        quality_flags=tuple(sorted(quality_flags)),
    )


def aggregate_device_locations(
    events: Iterable[DeviceLocationEvent],
    *,
    window_start: dt.datetime,
    window_end: dt.datetime,
    complete: bool = True,
) -> DeviceLocationAggregationResult:
    """Aggregate normalized location events without inventing freshness rules.

    The result exposes event coverage and age as raw durations only. It does
    not classify devices as fresh/stale, infer coordinate systems or expose
    coordinates in the aggregate projection.
    """

    start = _require_aware(window_start, "window_start").astimezone(UTC)
    end = _require_aware(window_end, "window_end").astimezone(UTC)
    if end <= start:
        raise ValueError("window_end must be after window_start")

    source_events = list(events)
    valid_events: list[DeviceLocationEvent] = []
    invalid_event_count = 0
    out_of_window_count = 0
    flags: set[str] = set()
    for event in source_events:
        if not _valid_location_event(event):
            invalid_event_count += 1
            continue
        occurred_at = event.gps_occurred_at.astimezone(UTC)
        if occurred_at < start or occurred_at > end:
            out_of_window_count += 1
            continue
        valid_events.append(event)

    grouped: dict[
        tuple[str, str, str, dt.datetime],
        list[DeviceLocationEvent],
    ] = defaultdict(list)
    for event in valid_events:
        identity = (
            event.source_system,
            event.location_source,
            event.device_id,
            event.gps_occurred_at.astimezone(UTC),
        )
        grouped[identity].append(event)

    selected: list[DeviceLocationEvent] = []
    duplicate_event_count = 0
    updated_observation_count = 0
    conflicting_timestamp_count = 0
    for identity_events in grouped.values():
        unique = list(dict.fromkeys(identity_events))
        duplicate_event_count += len(identity_events) - len(unique)
        coordinates = {
            (event.latitude, event.longitude)
            for event in unique
        }
        if len(coordinates) > 1:
            conflicting_timestamp_count += 1
            continue
        if len(unique) == 1:
            selected.append(unique[0])
            continue

        latest_time = max(
            (event.observed_at, event.ingested_at)
            for event in unique
        )
        latest = [
            event
            for event in unique
            if (event.observed_at, event.ingested_at) == latest_time
        ]
        if len(latest) != 1:
            conflicting_timestamp_count += 1
            continue
        updated_observation_count += 1
        selected.append(latest[0])

    device_groups: dict[str, list[DeviceLocationEvent]] = defaultdict(list)
    for event in selected:
        device_groups[event.device_id].append(event)
        if event.quality_flags:
            flags.add("source_event_quality_flags_present")

    device_metrics: list[DeviceLocationMetric] = []
    for device_id, device_events in device_groups.items():
        ordered = sorted(
            device_events,
            key=lambda event: (
                event.gps_occurred_at,
                event.observed_at,
                event.ingested_at,
            ),
        )
        first_gps_at = ordered[0].gps_occurred_at.astimezone(UTC)
        last_gps_at = ordered[-1].gps_occurred_at.astimezone(UTC)
        device_flags: set[str] = set()
        if any(event.quality_flags for event in ordered):
            device_flags.add("source_event_quality_flags_present")

        device_metrics.append(
            DeviceLocationMetric(
                device_id=device_id,
                event_count=len(ordered),
                distinct_coordinate_count=len(
                    {
                        (event.latitude, event.longitude)
                        for event in ordered
                    }
                ),
                first_gps_at=first_gps_at,
                last_gps_at=last_gps_at,
                source_span_seconds=round(
                    (last_gps_at - first_gps_at).total_seconds(),
                    3,
                ),
                latest_age_seconds=round(
                    (end - last_gps_at).total_seconds(),
                    3,
                ),
                speed_value_count=sum(
                    event.speed_value is not None
                    for event in ordered
                ),
                direction_value_count=sum(
                    event.direction_value is not None
                    for event in ordered
                ),
                accuracy_value_count=sum(
                    event.accuracy_value is not None
                    for event in ordered
                ),
                battery_value_count=sum(
                    event.battery_value is not None
                    for event in ordered
                ),
                gps_type_count=sum(
                    event.gps_type_code is not None
                    for event in ordered
                ),
                network_type_count=sum(
                    event.network_type_code is not None
                    for event in ordered
                ),
                quality_flags=tuple(sorted(device_flags)),
            )
        )

    if invalid_event_count:
        flags.add("invalid_events_excluded")
    if out_of_window_count:
        flags.add("events_outside_window_excluded")
    if duplicate_event_count:
        flags.add("duplicate_events_removed")
    if updated_observation_count:
        flags.add(
            "location_updates_collapsed_to_latest_observation"
        )
    if conflicting_timestamp_count:
        flags.add("same_timestamp_location_conflicts_excluded")
    if not complete:
        flags.add("input_scope_incomplete")

    return DeviceLocationAggregationResult(
        devices=tuple(
            sorted(device_metrics, key=lambda item: item.device_id)
        ),
        window_start=start,
        window_end=end,
        source_event_count=len(source_events),
        included_event_count=len(selected),
        duplicate_event_count=duplicate_event_count,
        updated_observation_count=updated_observation_count,
        conflicting_timestamp_count=conflicting_timestamp_count,
        out_of_window_count=out_of_window_count,
        invalid_event_count=invalid_event_count,
        partial=(
            not complete
            or bool(invalid_event_count)
            or bool(conflicting_timestamp_count)
        ),
        quality_flags=tuple(sorted(flags)),
    )


def aggregate_realtime_views(
    events: Iterable[RealtimeViewEvent],
    *,
    complete: bool = True,
) -> RealtimeViewAggregationResult:
    source_events = list(events)
    grouped: dict[str, list[RealtimeViewEvent]] = defaultdict(list)
    for event in source_events:
        grouped[event.stream_id].append(event)

    accepted: list[RealtimeViewEvent] = []
    duplicate_event_count = 0
    conflicting_stream_count = 0
    for stream_id, stream_events in grouped.items():
        del stream_id
        unique = list(dict.fromkeys(stream_events))
        duplicate_event_count += len(stream_events) - len(unique)
        if len(unique) > 1:
            conflicting_stream_count += 1
            continue
        accepted.append(unique[0])

    result_counts: dict[str, int] = defaultdict(int)
    error_counts: dict[str, int] = defaultdict(int)
    user_groups: dict[str, list[RealtimeViewEvent]] = defaultdict(list)
    device_groups: dict[str, list[RealtimeViewEvent]] = defaultdict(list)
    connection_duration = 0.0
    view_duration = 0.0
    first_frame_latency = 0.0
    first_frame_count = 0
    played_count = 0
    invalid_event_count = 0
    flags: set[str] = set()

    for event in accepted:
        calculated_connection = (
            event.closed_at - event.opened_at
        ).total_seconds()
        if calculated_connection < 0:
            flags.add("negative_connection_duration_event_excluded")
            invalid_event_count += 1
            continue

        calculated_view: float | None = None
        calculated_latency: float | None = None
        if event.first_frame_at is not None:
            calculated_view = (
                event.closed_at - event.first_frame_at
            ).total_seconds()
            calculated_latency = (
                event.first_frame_at - event.opened_at
            ).total_seconds()
            if calculated_view < 0 or calculated_latency < 0:
                flags.add("invalid_first_frame_event_excluded")
                invalid_event_count += 1
                continue

        connection_duration += calculated_connection
        if abs(
            calculated_connection - event.connection_duration_seconds
        ) > 0.001:
            flags.add("connection_duration_mismatch_recalculated")
        if calculated_view is not None and calculated_latency is not None:
            first_frame_count += 1
            view_duration += calculated_view
            first_frame_latency += calculated_latency
            if (
                event.view_duration_seconds is None
                or abs(
                    calculated_view - event.view_duration_seconds
                )
                > 0.001
            ):
                flags.add("view_duration_mismatch_recalculated")
        elif event.view_duration_seconds is not None:
            flags.add("view_duration_without_first_frame_ignored")

        result_counts[event.result] += 1
        if event.result == "played":
            played_count += 1
        elif event.result not in {
            "abnormal_disconnect",
            "cancelled",
            "failed",
            "timeout",
        }:
            flags.add("unknown_realtime_result")
        if event.error_code:
            error_counts[event.error_code] += 1
        if event.quality_flags:
            flags.add("source_event_quality_flags_present")
        user_groups[event.username].append(event)
        device_groups[event.device_id].append(event)

    if duplicate_event_count:
        flags.add("duplicate_events_removed")
    if conflicting_stream_count:
        flags.add("conflicting_streams_excluded")
    if not complete:
        flags.add("input_scope_incomplete")

    average_latency = (
        first_frame_latency / first_frame_count
        if first_frame_count
        else None
    )
    return RealtimeViewAggregationResult(
        users=_aggregate_view_dimensions(user_groups),
        devices=_aggregate_view_dimensions(device_groups),
        event_count=sum(result_counts.values()),
        duplicate_event_count=duplicate_event_count,
        conflicting_stream_count=conflicting_stream_count,
        invalid_event_count=invalid_event_count,
        played_count=played_count,
        first_frame_count=first_frame_count,
        connection_duration_seconds=round(connection_duration, 3),
        view_duration_seconds=round(view_duration, 3),
        first_frame_latency_seconds=round(first_frame_latency, 3),
        average_first_frame_latency_seconds=(
            round(average_latency, 3)
            if average_latency is not None
            else None
        ),
        result_counts=tuple(sorted(result_counts.items())),
        error_counts=tuple(sorted(error_counts.items())),
        partial=(
            not complete
            or bool(conflicting_stream_count)
            or bool(invalid_event_count)
        ),
        quality_flags=tuple(sorted(flags)),
    )


def aggregate_alarm_events(
    events: Iterable[AlarmEvent],
    *,
    complete: bool = True,
) -> AlarmAggregationResult:
    source_events = list(events)
    grouped: dict[
        tuple[str, str, str],
        list[AlarmEvent],
    ] = defaultdict(list)
    for event in source_events:
        identity = (
            event.source_system,
            event.source_record_id,
            event.device_id,
        )
        grouped[identity].append(event)

    selected: list[AlarmEvent] = []
    duplicate_row_count = 0
    updated_record_count = 0
    conflicting_record_count = 0
    for identity_events in grouped.values():
        unique = list(dict.fromkeys(identity_events))
        duplicate_row_count += len(identity_events) - len(unique)
        if len(unique) == 1:
            selected.append(unique[0])
            continue
        latest_time = max(
            (event.observed_at, event.ingested_at)
            for event in unique
        )
        latest = [
            event
            for event in unique
            if (event.observed_at, event.ingested_at) == latest_time
        ]
        if len(latest) != 1:
            conflicting_record_count += 1
            continue
        updated_record_count += 1
        selected.append(latest[0])

    type_counts: dict[int, int] = defaultdict(int)
    status_counts: dict[int, int] = defaultdict(int)
    deal_status_counts: dict[int, int] = defaultdict(int)
    device_groups: dict[str, list[AlarmEvent]] = defaultdict(list)
    missing_alarm_status_count = 0
    missing_deal_status_count = 0
    flags: set[str] = set()

    for event in selected:
        type_counts[event.alarm_type_code] += 1
        device_groups[event.device_id].append(event)
        if event.alarm_status_code is None:
            missing_alarm_status_count += 1
        else:
            status_counts[event.alarm_status_code] += 1
        if event.deal_status_code is None:
            missing_deal_status_count += 1
        else:
            deal_status_counts[event.deal_status_code] += 1
        if event.quality_flags:
            flags.add("source_event_quality_flags_present")

    if duplicate_row_count:
        flags.add("duplicate_rows_removed")
    if updated_record_count:
        flags.add("alarm_updates_collapsed_to_latest_observation")
    if conflicting_record_count:
        flags.add("conflicting_alarm_records_excluded")
    if missing_alarm_status_count:
        flags.add("alarm_status_missing")
    if missing_deal_status_count:
        flags.add("deal_status_missing")
    if not complete:
        flags.add("input_scope_incomplete")

    device_metrics = []
    for device_id, device_events in device_groups.items():
        device_type_counts: dict[int, int] = defaultdict(int)
        for event in device_events:
            device_type_counts[event.alarm_type_code] += 1
        device_metrics.append(
            AlarmDeviceMetric(
                device_id=device_id,
                alarm_count=len(device_events),
                alarm_type_counts=tuple(
                    sorted(device_type_counts.items())
                ),
            )
        )

    return AlarmAggregationResult(
        devices=tuple(
            sorted(device_metrics, key=lambda item: item.device_id)
        ),
        alarm_count=len(selected),
        duplicate_row_count=duplicate_row_count,
        updated_record_count=updated_record_count,
        conflicting_record_count=conflicting_record_count,
        alarm_type_counts=tuple(sorted(type_counts.items())),
        alarm_status_counts=tuple(sorted(status_counts.items())),
        deal_status_counts=tuple(sorted(deal_status_counts.items())),
        missing_alarm_status_count=missing_alarm_status_count,
        missing_deal_status_count=missing_deal_status_count,
        partial=not complete or bool(conflicting_record_count),
        quality_flags=tuple(sorted(flags)),
    )


def _aggregate_view_dimensions(
    groups: Mapping[str, list[RealtimeViewEvent]],
) -> tuple[RealtimeViewDimensionMetric, ...]:
    metrics = []
    for dimension_id, events in groups.items():
        result_counts: dict[str, int] = defaultdict(int)
        connection_duration = 0.0
        view_duration = 0.0
        first_frame_latency = 0.0
        first_frame_count = 0
        played_count = 0
        for event in events:
            result_counts[event.result] += 1
            played_count += event.result == "played"
            connection_duration += max(
                0.0,
                (event.closed_at - event.opened_at).total_seconds(),
            )
            if event.first_frame_at is not None:
                first_frame_count += 1
                view_duration += max(
                    0.0,
                    (
                        event.closed_at - event.first_frame_at
                    ).total_seconds(),
                )
                first_frame_latency += max(
                    0.0,
                    (
                        event.first_frame_at - event.opened_at
                    ).total_seconds(),
                )
        metrics.append(
            RealtimeViewDimensionMetric(
                dimension_id=dimension_id,
                view_count=len(events),
                played_count=played_count,
                first_frame_count=first_frame_count,
                connection_duration_seconds=round(
                    connection_duration,
                    3,
                ),
                view_duration_seconds=round(view_duration, 3),
                first_frame_latency_seconds=round(
                    first_frame_latency,
                    3,
                ),
                result_counts=tuple(sorted(result_counts.items())),
            )
        )
    return tuple(sorted(metrics, key=lambda item: item.dimension_id))


def _deduplicate_online_events(
    events: Iterable[_OnlineEvent],
) -> list[_OnlineEvent]:
    unique: dict[tuple[str, dt.datetime, int], _OnlineEvent] = {}
    for event in events:
        key = (event.device_id, event.occurred_at, event.status)
        unique.setdefault(key, event)
    return list(unique.values())


def _valid_location_event(event: DeviceLocationEvent) -> bool:
    time_values = (
        event.gps_occurred_at,
        event.observed_at,
        event.ingested_at,
    )
    if any(
        value.tzinfo is None or value.utcoffset() is None
        for value in time_values
    ):
        return False
    if event.ingested_at < event.observed_at:
        return False
    if (
        not math.isfinite(event.latitude)
        or not math.isfinite(event.longitude)
    ):
        return False
    if not -90 <= event.latitude <= 90:
        return False
    if not -180 <= event.longitude <= 180:
        return False
    return not (
        abs(event.latitude) < 0.000001
        and abs(event.longitude) < 0.000001
    )


def _parse_source_time(
    value: Any,
    *,
    source_timezone: dt.tzinfo,
) -> dt.datetime:
    if isinstance(value, dt.datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        normalized = value.strip().replace("Z", "+00:00")
        parsed = dt.datetime.fromisoformat(normalized)
    else:
        raise ValueError("missing source time")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=source_timezone)
    return parsed.astimezone(UTC)


def _require_aware(value: dt.datetime, name: str) -> dt.datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _non_negative_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None
