from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass
from typing import Iterable


UTC = dt.timezone.utc

RECORD_STATUSES = ("DRAFT", "SUBMITTED", "CORRECTED")
AUDIT_ACTIONS = ("CREATED", "UPDATED", "SUBMITTED", "CORRECTED")
ASSOCIATION_METHODS = (
    "SOURCE_DIRECT",
    "USER_CONFIRMED",
    "MANUAL_ENTRY",
    "DERIVED",
    "UNKNOWN",
)


@dataclass(frozen=True, slots=True)
class AuthorizedUser:
    """CHA-owned access boundary entry.

    An AEE account that has logged in is only allowed to enter CHA when it
    exists here with ``enabled=True`` within its validity window. No AEE
    password and no AEE token are stored.
    """

    aee_account_id: str
    username: str
    display_name: str | None
    department: str | None
    role: str | None
    enabled: bool
    valid_from: dt.datetime | None
    valid_until: dt.datetime | None
    created_at: dt.datetime
    updated_at: dt.datetime
    quality_flags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class InspectionRecord:
    inspection_id: str
    inspector_user_id: str | None
    inspector_username: str
    device_id: str
    inspection_started_at: dt.datetime
    inspection_ended_at: dt.datetime
    inspection_duration_seconds: float
    aircraft_no: str | None
    flight_source_id: str | None
    flight_no: str | None
    routine_task_source_id: str | None
    maintenance_task_text: str | None
    station: str | None
    location_text: str | None
    has_issue: bool
    issue_type: str | None
    issue_level: str | None
    issue_description: str | None
    remark: str | None
    status: str
    created_at: dt.datetime
    created_by: str
    updated_at: dt.datetime
    updated_by: str
    submitted_at: dt.datetime | None
    submitted_by: str | None
    corrected_at: dt.datetime | None
    corrected_by: str | None
    correction_reason: str | None
    quality_flags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class InspectionRecordViewLink:
    inspection_id: str
    realtime_view_event_id: str


@dataclass(frozen=True, slots=True)
class InspectionAuditEvent:
    audit_id: str
    inspection_id: str
    action: str
    actor_user_id: str | None
    actor_username: str
    acted_at: dt.datetime
    summary: str | None


@dataclass(frozen=True, slots=True)
class AuthorizedUserAuditEvent:
    audit_id: str
    action: str
    operator_user_id: str | None
    operator_username: str
    target_username: str
    acted_at: dt.datetime
    summary: str | None


@dataclass(frozen=True, slots=True)
class InspectionRecordFilter:
    start: dt.datetime | None = None
    end: dt.datetime | None = None
    inspector_username: str | None = None
    device_id: str | None = None
    aircraft_no: str | None = None
    flight_no: str | None = None
    station: str | None = None
    task_text: str | None = None
    has_issue: bool | None = None
    issue_type: str | None = None
    issue_level: str | None = None
    status: str | None = None
    page: int = 1
    page_size: int = 20

    def __post_init__(self) -> None:
        if self.page <= 0:
            raise ValueError("page must be positive")
        if not 1 <= self.page_size <= 200:
            raise ValueError("page_size must be within 1..200")


@dataclass(frozen=True, slots=True)
class InspectionRecordPage:
    items: tuple[InspectionRecord, ...]
    total: int
    page: int
    page_size: int


def build_inspection_record(
    *,
    inspector_user_id: str | None,
    inspector_username: str,
    device_id: str,
    inspection_started_at: dt.datetime,
    inspection_ended_at: dt.datetime,
    aircraft_no: str | None = None,
    flight_source_id: str | None = None,
    flight_no: str | None = None,
    routine_task_source_id: str | None = None,
    maintenance_task_text: str | None = None,
    station: str | None = None,
    location_text: str | None = None,
    has_issue: bool = False,
    issue_type: str | None = None,
    issue_level: str | None = None,
    issue_description: str | None = None,
    remark: str | None = None,
    status: str = "DRAFT",
    created_at: dt.datetime | None = None,
    created_by: str | None = None,
    updated_at: dt.datetime | None = None,
    updated_by: str | None = None,
    submitted_at: dt.datetime | None = None,
    submitted_by: str | None = None,
    corrected_at: dt.datetime | None = None,
    corrected_by: str | None = None,
    correction_reason: str | None = None,
    inspection_id: str | None = None,
) -> InspectionRecord:
    """Build a validated InspectionRecord.

    ``inspector_username`` and ``device_id`` are trusted system facts and are
    required; they must come from the CHA session/stream, never from ordinary
    user input. Issue fields are only meaningful when ``has_issue=True``.
    """

    normalized_username = _required_text(inspector_username, "inspector_username")
    normalized_device = _required_text(device_id, "device_id")
    normalized_status = str(status or "").strip().upper()
    if normalized_status not in RECORD_STATUSES:
        raise ValueError(f"status must be one of {RECORD_STATUSES}")

    started = _aware_utc(inspection_started_at, "inspection_started_at")
    ended = _aware_utc(inspection_ended_at, "inspection_ended_at")
    if ended < started:
        raise ValueError("inspection_ended_at must not be before inspection_started_at")
    duration = (ended - started).total_seconds()

    flags: set[str] = set()
    if not has_issue:
        issue_type = issue_level = issue_description = None
    else:
        if not (
            issue_type
            or issue_level
            or issue_description
        ):
            flags.add("issue_true_without_detail")

    now = _aware_utc(created_at or dt.datetime.now(UTC), "created_at")
    updated = _aware_utc(updated_at or now, "updated_at")
    if created_by is None:
        created_by = normalized_username
    if updated_by is None:
        updated_by = normalized_username

    return InspectionRecord(
        inspection_id=inspection_id or f"ins_{uuid.uuid4().hex[:16]}",
        inspector_user_id=_optional_text(inspector_user_id, 128),
        inspector_username=normalized_username[:128],
        device_id=normalized_device[:64],
        inspection_started_at=started,
        inspection_ended_at=ended,
        inspection_duration_seconds=duration,
        aircraft_no=_optional_text(aircraft_no, 64),
        flight_source_id=_optional_text(flight_source_id, 128),
        flight_no=_optional_text(flight_no, 64),
        routine_task_source_id=_optional_text(routine_task_source_id, 128),
        maintenance_task_text=_optional_text(maintenance_task_text, 500),
        station=_optional_text(station, 128),
        location_text=_optional_text(location_text, 500),
        has_issue=bool(has_issue),
        issue_type=_optional_text(issue_type, 64),
        issue_level=_optional_text(issue_level, 32),
        issue_description=_optional_text(issue_description, 2000),
        remark=_optional_text(remark, 2000),
        status=normalized_status,
        created_at=now,
        created_by=created_by[:128],
        updated_at=updated,
        updated_by=updated_by[:128],
        submitted_at=_opt_utc(submitted_at),
        submitted_by=_optional_text(submitted_by, 128),
        corrected_at=_opt_utc(corrected_at),
        corrected_by=_optional_text(corrected_by, 128),
        correction_reason=_optional_text(correction_reason, 500),
        quality_flags=tuple(sorted(flags)),
    )


def build_audit_event(
    *,
    inspection_id: str,
    action: str,
    actor_user_id: str | None,
    actor_username: str,
    acted_at: dt.datetime | None = None,
    summary: str | None = None,
    audit_id: str | None = None,
) -> InspectionAuditEvent:
    normalized_action = str(action or "").strip().upper()
    if normalized_action not in AUDIT_ACTIONS:
        raise ValueError(f"action must be one of {AUDIT_ACTIONS}")
    return InspectionAuditEvent(
        audit_id=audit_id or f"aud_{uuid.uuid4().hex[:16]}",
        inspection_id=_required_text(inspection_id, "inspection_id"),
        action=normalized_action,
        actor_user_id=_optional_text(actor_user_id, 128),
        actor_username=_required_text(actor_username, "actor_username")[:128],
        acted_at=_aware_utc(acted_at or dt.datetime.now(UTC), "acted_at"),
        summary=_optional_text(summary, 500),
    )


def build_user_audit_event(
    *,
    action: str,
    operator_user_id: str | None,
    operator_username: str,
    target_username: str,
    acted_at: dt.datetime | None = None,
    summary: str | None = None,
    audit_id: str | None = None,
) -> AuthorizedUserAuditEvent:
    normalized_action = str(action or "").strip().upper()
    if normalized_action not in {
        "USER_ADDED",
        "USER_UPDATED",
        "USER_ENABLED",
        "USER_DISABLED",
    }:
        raise ValueError("unsupported user audit action")
    return AuthorizedUserAuditEvent(
        audit_id=audit_id or f"uaud_{uuid.uuid4().hex[:16]}",
        action=normalized_action,
        operator_user_id=_optional_text(operator_user_id, 128),
        operator_username=_required_text(
            operator_username,
            "operator_username",
        )[:128],
        target_username=_required_text(
            target_username,
            "target_username",
        )[:128],
        acted_at=_aware_utc(acted_at or dt.datetime.now(UTC), "acted_at"),
        summary=_optional_text(summary, 500),
    )


def build_authorized_user(
    *,
    aee_account_id: str,
    username: str,
    display_name: str | None = None,
    department: str | None = None,
    role: str | None = None,
    enabled: bool = True,
    valid_from: dt.datetime | None = None,
    valid_until: dt.datetime | None = None,
    created_at: dt.datetime | None = None,
    updated_at: dt.datetime | None = None,
) -> AuthorizedUser:
    now = _aware_utc(created_at or dt.datetime.now(UTC), "created_at")
    return AuthorizedUser(
        aee_account_id=_required_text(aee_account_id, "aee_account_id")[:128],
        username=_required_text(username, "username")[:128],
        display_name=_optional_text(display_name, 128),
        department=_optional_text(department, 128),
        role=_optional_text(role, 64),
        enabled=bool(enabled),
        valid_from=_opt_utc(valid_from),
        valid_until=_opt_utc(valid_until),
        created_at=now,
        updated_at=_aware_utc(updated_at or now, "updated_at"),
    )


def is_user_active(
    user: AuthorizedUser,
    *,
    at: dt.datetime | None = None,
) -> bool:
    now = _aware_utc(at or dt.datetime.now(UTC), "at")
    if not user.enabled:
        return False
    if user.valid_from is not None and now < user.valid_from:
        return False
    if user.valid_until is not None and now > user.valid_until:
        return False
    return True


def link_view_events(
    inspection_id: str,
    realtime_view_event_ids: Iterable[str],
) -> tuple[InspectionRecordViewLink, ...]:
    normalized = _required_text(inspection_id, "inspection_id")
    seen: set[str] = set()
    links: list[InspectionRecordViewLink] = []
    for raw in realtime_view_event_ids:
        view_id = _optional_text(raw, 128)
        if view_id is None or view_id in seen:
            continue
        seen.add(view_id)
        links.append(
            InspectionRecordViewLink(
                inspection_id=normalized,
                realtime_view_event_id=view_id,
            )
        )
    return tuple(links)


def _required_text(value: str, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} is required")
    return text


def _optional_text(value: str | None, maximum: int) -> str | None:
    text = str(value or "").strip()
    return text[:maximum] or None


def _aware_utc(value: dt.datetime, name: str) -> dt.datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(UTC)


def _opt_utc(value: dt.datetime | None) -> dt.datetime | None:
    return _aware_utc(value, "timestamp") if value is not None else None
