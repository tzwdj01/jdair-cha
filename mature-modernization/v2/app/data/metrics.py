from __future__ import annotations

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable, Mapping


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


def _deduplicate_online_events(
    events: Iterable[_OnlineEvent],
) -> list[_OnlineEvent]:
    unique: dict[tuple[str, dt.datetime, int], _OnlineEvent] = {}
    for event in events:
        key = (event.device_id, event.occurred_at, event.status)
        unique.setdefault(key, event)
    return list(unique.values())


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
