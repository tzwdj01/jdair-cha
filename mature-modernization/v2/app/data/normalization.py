from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any, Iterable, Mapping


UTC = dt.timezone.utc
MEDIA_KIND_BY_CODE = {
    1: "image",
    2: "audio",
    3: "video",
    4: "device_file",
}
RESTRICTED_MEDIA_FIELDS = ("peopleNo", "peopleName", "des")
RESTRICTED_ALARM_FIELDS = ("dealUser", "dealTime", "dealDesc")


@dataclass(frozen=True, slots=True)
class DeviceStatusEvent:
    source_system: str
    source_record_id: str | None
    device_id: str
    group_id: str | None
    device_type_code: int | None
    status_code: int
    online: bool | None
    occurred_at: dt.datetime
    observed_at: dt.datetime
    ingested_at: dt.datetime
    quality_flags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DeviceStatusNormalizationResult:
    events: tuple[DeviceStatusEvent, ...]
    source_row_count: int
    invalid_row_count: int
    quality_flags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MediaFile:
    source_system: str
    source_record_id: str | None
    device_id: str
    group_id: str | None
    device_name_at_capture: str | None
    title: str | None
    file_type_code: int | None
    media_kind: str
    list_type_code: int | None
    source_code: int | None
    upload_status_code: int | None
    file_size_bytes: int | None
    duration_seconds: int | None
    created_at_source: dt.datetime | None
    uploaded_at_source: dt.datetime | None
    work_no: str | None
    people_no: str | None
    people_name: str | None
    description: str | None
    deleted_marker: bool | None
    observed_at: dt.datetime
    ingested_at: dt.datetime
    quality_flags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MediaFileNormalizationResult:
    files: tuple[MediaFile, ...]
    source_row_count: int
    invalid_row_count: int
    restricted_field_row_count: int
    quality_flags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AlarmEvent:
    source_system: str
    source_record_id: str
    device_id: str
    group_id: str | None
    alarm_type_code: int
    alarm_status_code: int | None
    deal_status_code: int | None
    deal_type_code: int | None
    handled: bool | None
    occurred_at: dt.datetime
    handled_at: dt.datetime | None
    handler: str | None
    deal_description: str | None
    deleted_marker: bool | None
    observed_at: dt.datetime
    ingested_at: dt.datetime
    quality_flags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AlarmNormalizationResult:
    events: tuple[AlarmEvent, ...]
    source_row_count: int
    invalid_row_count: int
    restricted_field_row_count: int
    quality_flags: tuple[str, ...]


def normalize_device_status_events(
    rows: Iterable[Mapping[str, Any]],
    *,
    source_timezone: dt.tzinfo,
    observed_at: dt.datetime,
    ingested_at: dt.datetime,
) -> DeviceStatusNormalizationResult:
    observed, ingested = _normalize_lifecycle_times(
        observed_at,
        ingested_at,
    )
    _validate_source_timezone(source_timezone)
    source_rows = list(rows)
    events: list[DeviceStatusEvent] = []
    invalid_row_count = 0

    for row in source_rows:
        device_id = _optional_text(row.get("devId"))
        status_code = _optional_int(row.get("status"))
        occurred_at = _optional_source_time(
            row.get("time"),
            source_timezone=source_timezone,
        )
        if not device_id or status_code is None or occurred_at is None:
            invalid_row_count += 1
            continue

        flags: set[str] = set()
        source_record_id = _optional_text(row.get("id"))
        if source_record_id is None:
            flags.add("source_record_id_missing")

        raw_device_type = row.get("devType")
        device_type_code = _optional_int(raw_device_type)
        if _is_present(raw_device_type) and device_type_code is None:
            flags.add("invalid_device_type_ignored")

        online: bool | None
        if status_code == 1:
            online = True
        else:
            online = None
            flags.add("non_online_status_map_partial")
            flags.add("online_state_unknown")

        events.append(
            DeviceStatusEvent(
                source_system="aee",
                source_record_id=source_record_id,
                device_id=device_id,
                group_id=_optional_text(row.get("groupId")),
                device_type_code=device_type_code,
                status_code=status_code,
                online=online,
                occurred_at=occurred_at,
                observed_at=observed,
                ingested_at=ingested,
                quality_flags=tuple(sorted(flags)),
            )
        )

    result_flags: set[str] = set()
    if invalid_row_count:
        result_flags.add("invalid_rows_ignored")
    if any(
        "non_online_status_map_partial" in event.quality_flags
        for event in events
    ):
        result_flags.add("non_online_status_map_partial")

    return DeviceStatusNormalizationResult(
        events=tuple(events),
        source_row_count=len(source_rows),
        invalid_row_count=invalid_row_count,
        quality_flags=tuple(sorted(result_flags)),
    )


def normalize_media_files(
    rows: Iterable[Mapping[str, Any]],
    *,
    source_timezone: dt.tzinfo,
    observed_at: dt.datetime,
    ingested_at: dt.datetime,
    include_restricted: bool = False,
) -> MediaFileNormalizationResult:
    observed, ingested = _normalize_lifecycle_times(
        observed_at,
        ingested_at,
    )
    _validate_source_timezone(source_timezone)
    source_rows = list(rows)
    files: list[MediaFile] = []
    invalid_row_count = 0
    restricted_field_row_count = 0

    for row in source_rows:
        device_id = _optional_text(
            _first_value(row, ("devId", "DevId", "szIDNO"))
        )
        if not device_id:
            invalid_row_count += 1
            continue

        flags: set[str] = set()
        source_record_id = _optional_text(row.get("id"))
        if source_record_id is None:
            flags.add("source_record_id_missing")
        else:
            flags.add("source_id_scope_unverified")

        file_type_code = _optional_int(row.get("fType"))
        media_kind = MEDIA_KIND_BY_CODE.get(
            file_type_code,
            "unknown",
        )
        if media_kind == "unknown":
            flags.add("unknown_file_type")

        list_type_code = _optional_int(row.get("lType"))
        if list_type_code not in {None, 0, 1}:
            flags.add("unknown_list_type")

        source_code = _optional_int(row.get("source"))
        if source_code is not None:
            flags.add("source_code_map_partial")
        upload_status_code = _optional_int(row.get("upLoadStatus"))
        if upload_status_code is not None:
            flags.add("upload_status_code_map_partial")

        file_size_bytes = _optional_non_negative_int(
            _first_value(row, ("fileLen", "fileSize", "size"))
        )
        if (
            _first_value(row, ("fileLen", "fileSize", "size")) is not None
            and file_size_bytes is None
        ):
            flags.add("invalid_file_size_ignored")

        raw_duration = _first_value(row, ("duration", "videoTime"))
        duration_seconds = _optional_non_negative_int(raw_duration)
        if file_type_code != 3:
            if duration_seconds not in {None, 0}:
                flags.add("non_video_duration_ignored")
            duration_seconds = None
        elif raw_duration is not None and duration_seconds is None:
            flags.add("invalid_video_duration_ignored")

        created_at_source = _optional_source_time(
            _first_value(
                row,
                ("fileTime", "startTime", "beginTime"),
            ),
            source_timezone=source_timezone,
        )
        if (
            _first_value(
                row,
                ("fileTime", "startTime", "beginTime"),
            )
            is not None
            and created_at_source is None
        ):
            flags.add("invalid_created_time_ignored")

        uploaded_at_source = _optional_source_time(
            _first_value(
                row,
                ("upLoadTime", "uploadTime", "endTime"),
            ),
            source_timezone=source_timezone,
        )
        if (
            _first_value(
                row,
                ("upLoadTime", "uploadTime", "endTime"),
            )
            is not None
            and uploaded_at_source is None
        ):
            flags.add("invalid_uploaded_time_ignored")
        if created_at_source is None and uploaded_at_source is None:
            flags.add("media_time_missing")

        restricted_present = any(
            _optional_text(row.get(field)) is not None
            for field in RESTRICTED_MEDIA_FIELDS
        )
        if restricted_present:
            restricted_field_row_count += 1
            if not include_restricted:
                flags.add("restricted_fields_omitted")

        raw_deleted_marker = row.get("isDeleted")
        deleted_marker = _optional_bool_marker(raw_deleted_marker)
        if _is_present(raw_deleted_marker):
            flags.add("deletion_semantics_unverified")
            if deleted_marker is None:
                flags.add("invalid_deleted_marker")

        files.append(
            MediaFile(
                source_system="aee",
                source_record_id=source_record_id,
                device_id=device_id,
                group_id=_optional_text(row.get("groupId")),
                device_name_at_capture=_optional_text(
                    _first_value(
                        row,
                        ("deviceName", "devName"),
                    )
                ),
                title=_optional_text(
                    _first_value(
                        row,
                        ("title", "fileName", "name", "fileTitle"),
                    )
                ),
                file_type_code=file_type_code,
                media_kind=media_kind,
                list_type_code=list_type_code,
                source_code=source_code,
                upload_status_code=upload_status_code,
                file_size_bytes=file_size_bytes,
                duration_seconds=duration_seconds,
                created_at_source=created_at_source,
                uploaded_at_source=uploaded_at_source,
                work_no=_optional_text(row.get("workNo")),
                people_no=(
                    _optional_text(row.get("peopleNo"))
                    if include_restricted
                    else None
                ),
                people_name=(
                    _optional_text(row.get("peopleName"))
                    if include_restricted
                    else None
                ),
                description=(
                    _optional_text(row.get("des"))
                    if include_restricted
                    else None
                ),
                deleted_marker=deleted_marker,
                observed_at=observed,
                ingested_at=ingested,
                quality_flags=tuple(sorted(flags)),
            )
        )

    result_flags: set[str] = set()
    if invalid_row_count:
        result_flags.add("invalid_rows_ignored")
    if restricted_field_row_count and not include_restricted:
        result_flags.add("restricted_fields_omitted")
    if any(
        "source_id_scope_unverified" in item.quality_flags
        for item in files
    ):
        result_flags.add("source_id_scope_unverified")

    return MediaFileNormalizationResult(
        files=tuple(files),
        source_row_count=len(source_rows),
        invalid_row_count=invalid_row_count,
        restricted_field_row_count=restricted_field_row_count,
        quality_flags=tuple(sorted(result_flags)),
    )


def normalize_alarm_events(
    rows: Iterable[Mapping[str, Any]],
    *,
    source_timezone: dt.tzinfo,
    observed_at: dt.datetime,
    ingested_at: dt.datetime,
    include_restricted: bool = False,
) -> AlarmNormalizationResult:
    observed, ingested = _normalize_lifecycle_times(
        observed_at,
        ingested_at,
    )
    _validate_source_timezone(source_timezone)
    source_rows = list(rows)
    events: list[AlarmEvent] = []
    invalid_row_count = 0
    restricted_field_row_count = 0

    for row in source_rows:
        source_record_id = _optional_text(row.get("id"))
        device_id = _optional_text(row.get("devId"))
        alarm_type_code = _optional_int(row.get("alarmType"))
        occurred_at = _optional_source_time(
            row.get("alarmTime"),
            source_timezone=source_timezone,
        )
        if (
            source_record_id is None
            or device_id is None
            or alarm_type_code is None
            or occurred_at is None
        ):
            invalid_row_count += 1
            continue

        flags = {
            "alarm_code_map_partial",
            "alarm_lifecycle_unverified",
            "source_id_scope_unverified",
        }
        raw_alarm_status = _first_value(
            row,
            ("alarmStatus", "status"),
        )
        alarm_status_code = _optional_int(raw_alarm_status)
        if _is_present(raw_alarm_status):
            if alarm_status_code is None:
                flags.add("invalid_alarm_status_ignored")
            else:
                flags.add("alarm_status_map_partial")
            if (
                not _is_present(row.get("alarmStatus"))
                and _is_present(row.get("status"))
            ):
                flags.add("push_status_alias_used")

        raw_deal_status = row.get("dealStatus")
        deal_status_code = _optional_int(raw_deal_status)
        if _is_present(raw_deal_status):
            if deal_status_code is None:
                flags.add("invalid_deal_status_ignored")
            else:
                flags.add("deal_status_map_partial")
                flags.add("handled_state_unknown")

        raw_deal_type = row.get("dealType")
        deal_type_code = _optional_int(raw_deal_type)
        if _is_present(raw_deal_type):
            if deal_type_code is None:
                flags.add("invalid_deal_type_ignored")
            else:
                flags.add("deal_type_map_partial")

        restricted_present = any(
            _is_present(row.get(field))
            for field in RESTRICTED_ALARM_FIELDS
        )
        if restricted_present:
            restricted_field_row_count += 1
            if not include_restricted:
                flags.add("restricted_fields_omitted")

        handled_at = None
        handler = None
        deal_description = None
        if include_restricted:
            handled_at = _optional_source_time(
                row.get("dealTime"),
                source_timezone=source_timezone,
            )
            if (
                _is_present(row.get("dealTime"))
                and handled_at is None
            ):
                flags.add("invalid_deal_time_ignored")
            handler = _optional_text(row.get("dealUser"))
            deal_description = _optional_text(row.get("dealDesc"))

        raw_deleted_marker = row.get("isDeleted")
        deleted_marker = _optional_bool_marker(raw_deleted_marker)
        if _is_present(raw_deleted_marker):
            flags.add("deletion_semantics_unverified")
            if deleted_marker is None:
                flags.add("invalid_deleted_marker")

        events.append(
            AlarmEvent(
                source_system="aee",
                source_record_id=source_record_id,
                device_id=device_id,
                group_id=_optional_text(row.get("groupId")),
                alarm_type_code=alarm_type_code,
                alarm_status_code=alarm_status_code,
                deal_status_code=deal_status_code,
                deal_type_code=deal_type_code,
                handled=None,
                occurred_at=occurred_at,
                handled_at=handled_at,
                handler=handler,
                deal_description=deal_description,
                deleted_marker=deleted_marker,
                observed_at=observed,
                ingested_at=ingested,
                quality_flags=tuple(sorted(flags)),
            )
        )

    result_flags = {
        "alarm_code_map_partial",
        "alarm_lifecycle_unverified",
        "source_id_scope_unverified",
    }
    if invalid_row_count:
        result_flags.add("invalid_rows_ignored")
    if restricted_field_row_count and not include_restricted:
        result_flags.add("restricted_fields_omitted")

    return AlarmNormalizationResult(
        events=tuple(events),
        source_row_count=len(source_rows),
        invalid_row_count=invalid_row_count,
        restricted_field_row_count=restricted_field_row_count,
        quality_flags=tuple(sorted(result_flags)),
    )


def _normalize_lifecycle_times(
    observed_at: dt.datetime,
    ingested_at: dt.datetime,
) -> tuple[dt.datetime, dt.datetime]:
    observed = _require_aware(observed_at, "observed_at").astimezone(UTC)
    ingested = _require_aware(ingested_at, "ingested_at").astimezone(UTC)
    if ingested < observed:
        raise ValueError("ingested_at must not be before observed_at")
    return observed, ingested


def _optional_source_time(
    value: Any,
    *,
    source_timezone: dt.tzinfo,
) -> dt.datetime | None:
    if value is None or value == "":
        return None
    try:
        if isinstance(value, dt.datetime):
            parsed = value
        elif isinstance(value, str):
            parsed = dt.datetime.fromisoformat(
                value.strip().replace("Z", "+00:00")
            )
        else:
            return None
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=source_timezone)
    return parsed.astimezone(UTC)


def _require_aware(value: dt.datetime, name: str) -> dt.datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


def _validate_source_timezone(value: dt.tzinfo) -> None:
    probe = dt.datetime(2000, 1, 1, tzinfo=value)
    if probe.utcoffset() is None:
        raise ValueError("source_timezone must be usable")


def _first_value(
    row: Mapping[str, Any],
    names: tuple[str, ...],
) -> Any:
    for name in names:
        value = row.get(name)
        if value is not None and value != "":
            return value
    return None


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, float) and not value.is_integer():
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_non_negative_int(value: Any) -> int | None:
    parsed = _optional_int(value)
    if parsed is None or parsed < 0:
        return None
    return parsed


def _optional_bool_marker(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"0", "false"}:
            return False
        if normalized in {"1", "true"}:
            return True
    return None


def _is_present(value: Any) -> bool:
    return value is not None and value != ""
