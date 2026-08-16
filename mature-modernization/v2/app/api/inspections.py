from __future__ import annotations

import datetime as dt
import io
import json
from collections.abc import Awaitable, Callable
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, Field

from ..config import Settings
from ..data.inspection_records import (
    InspectionRecordFilter,
    build_authorized_user,
    build_user_audit_event,
)
from ..data.store import InspectionRecordStore
from ..services.inspection_records import InspectionRecordService


UTC = dt.timezone.utc
IdentityProvider = Callable[
    [Request],
    Awaitable[tuple[str | None, str]],
]
Envelope = Callable[..., JSONResponse]
TEMPLATE_PATH = (
    Path(__file__).resolve().parents[1] / "templates" / "inspections.html"
)


class CreateDraftBody(BaseModel):
    device_id: str
    inspection_started_at: dt.datetime
    inspection_ended_at: dt.datetime
    aircraft_no: str | None = None
    flight_source_id: str | None = None
    flight_no: str | None = None
    routine_task_source_id: str | None = None
    maintenance_task_text: str | None = None
    station: str | None = None
    location_text: str | None = None
    has_issue: bool = False
    issue_type: str | None = None
    issue_level: str | None = None
    issue_description: str | None = None
    remark: str | None = None
    realtime_view_event_ids: list[str] = Field(default_factory=list)


class UpdateDraftBody(BaseModel):
    aircraft_no: str | None = None
    flight_source_id: str | None = None
    flight_no: str | None = None
    routine_task_source_id: str | None = None
    maintenance_task_text: str | None = None
    station: str | None = None
    location_text: str | None = None
    has_issue: bool | None = None
    issue_type: str | None = None
    issue_level: str | None = None
    issue_description: str | None = None
    remark: str | None = None
    realtime_view_event_ids: list[str] | None = None


class CorrectBody(BaseModel):
    correction_reason: str
    aircraft_no: str | None = None
    flight_source_id: str | None = None
    flight_no: str | None = None
    routine_task_source_id: str | None = None
    maintenance_task_text: str | None = None
    station: str | None = None
    location_text: str | None = None
    has_issue: bool | None = None
    issue_type: str | None = None
    issue_level: str | None = None
    issue_description: str | None = None
    remark: str | None = None


class AuthorizedUserBody(BaseModel):
    aee_account_id: str
    username: str
    display_name: str | None = None
    department: str | None = None
    role: str | None = None
    enabled: bool = True
    valid_from: dt.datetime | None = None
    valid_until: dt.datetime | None = None


def create_inspections_router(
    settings: Settings,
    service: InspectionRecordService,
    record_store: InspectionRecordStore,
    envelope: Envelope,
    identity: IdentityProvider,
) -> APIRouter:
    """CHA inspection workflow API (M4 P3, non-production feature-gated).

    Every endpoint enforces the CHA authorized-user boundary: the current
    authenticated username must exist in the AuthorizedUser list with
    ``enabled=True``. ``inspector_username`` is always derived server-side
    from the session, never from the client body.
    """

    router = APIRouter()

    async def require_authorized(
        request: Request,
    ) -> tuple[tuple[str | None, str] | None, JSONResponse | None]:
        """Return (identity, error); error is None when authorized."""

        try:
            user_id, username = await identity(request)
        except Exception:
            return None, envelope(
                request,
                {"code": "unauthorized", "message": "session identity unavailable"},
                ok=False,
                status_code=401,
            )
        if not username or not username.strip():
            return None, envelope(
                request,
                {"code": "unauthorized", "message": "session has no username"},
                ok=False,
                status_code=401,
            )
        authorized = await record_store.is_account_authorized(
            username=username,
            at=dt.datetime.now(UTC),
        )
        if not authorized:
            return None, envelope(
                request,
                {
                    "code": "cha_access_forbidden",
                    "message": "current account is not in the CHA authorized user list",
                },
                ok=False,
                status_code=403,
            )
        return (user_id, username), None

    async def require_admin(
        request: Request,
    ) -> tuple[tuple[str | None, str] | None, JSONResponse | None]:
        identity, error = await require_authorized(request)
        if error is not None:
            return None, error
        user_id, username = identity
        user = await record_store.get_authorized_user(username=username)
        if user is None or str(user.role or "").strip().casefold() != "admin":
            return None, envelope(
                request,
                {
                    "code": "admin_forbidden",
                    "message": "admin privilege is required",
                },
                ok=False,
                status_code=403,
            )
        return (user_id, username), None

    async def _record_user_audit(
        *,
        operator_user_id: str | None,
        operator_username: str,
        target_username: str,
        action: str,
        summary: str | None,
    ) -> None:
        await record_store.append_user_audit_event(
            build_user_audit_event(
                action=action,
                operator_user_id=operator_user_id,
                operator_username=operator_username,
                target_username=target_username,
                summary=summary,
            )
        )

    def require_admin_route(request: Request):
        blocked = gate(request)
        if blocked is not None:
            return blocked
        return None

    def gate(request: Request) -> JSONResponse:
        if not settings.feature_inspection_v2:
            return envelope(
                request,
                {"code": "feature_disabled", "feature": "inspection_v2"},
                ok=False,
                status_code=404,
            )
        return None  # type: ignore[return-value]

    def parse_scope(request: Request, days: int):
        end = dt.datetime.now(UTC)
        start = end - dt.timedelta(days=max(1, min(days, 90)))
        return start, end, days

    @router.get("/api/v2/dashboard/inspections", response_class=HTMLResponse)
    async def inspections_page(request: Request) -> HTMLResponse:
        if not settings.feature_inspection_v2:
            return HTMLResponse(
                status_code=404,
                content="<meta charset='utf-8'><h1>监察记录页未启用</h1>",
            )
        try:
            html = TEMPLATE_PATH.read_text(encoding="utf-8")
        except OSError:
            return HTMLResponse(
                status_code=500,
                content="Inspection template unavailable.",
            )
        return HTMLResponse(
            content=html.replace(
                "{{CHA_V2_VERSION}}",
                settings.version,
            ).replace("{{CHA_V2_BUILD}}", settings.build)
        )

    @router.get("/api/v2/inspections")
    async def list_inspections(
        request: Request,
        start: str | None = Query(None),
        end: str | None = Query(None),
        days: int = Query(7, ge=1, le=90),
        inspector: str = Query("", max_length=128),
        device: str = Query("", max_length=64),
        aircraft: str = Query("", max_length=64),
        flight: str = Query("", max_length=64),
        station: str = Query("", max_length=128),
        task: str = Query("", max_length=500),
        has_issue: bool | None = Query(None),
        issue_type: str = Query("", max_length=64),
        issue_level: str = Query("", max_length=32),
        status: str = Query("", max_length=16),
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=200),
    ) -> JSONResponse:
        blocked = gate(request)
        if blocked is not None:
            return blocked
        _identity, _auth_error = await require_authorized(request)
        if _auth_error is not None:
            return _auth_error
        user_id, username = _identity
        parsed_start: dt.datetime | None = None
        parsed_end: dt.datetime | None = None
        if start:
            parsed_start = _parse_iso(start)
        if end:
            parsed_end = _parse_iso(end)
        if parsed_start is None or parsed_end is None:
            parsed_end = dt.datetime.now(UTC)
            parsed_start = parsed_end - dt.timedelta(
                days=max(1, min(days, 90))
            )
        if parsed_start >= parsed_end:
            return envelope(
                request,
                {"code": "invalid_scope"},
                ok=False,
                status_code=400,
            )
        record_filter = InspectionRecordFilter(
            start=parsed_start,
            end=parsed_end,
            inspector_username=inspector or None,
            device_id=device or None,
            aircraft_no=aircraft or None,
            flight_no=flight or None,
            station=station or None,
            task_text=task or None,
            has_issue=has_issue,
            issue_type=issue_type or None,
            issue_level=issue_level or None,
            status=status.upper() or None,
            page=page,
            page_size=page_size,
        )
        result = await service.list(record_filter)
        return envelope(
            request,
            {
                "items": _json_safe(result.items),
                "total": result.total,
                "page": result.page,
                "page_size": result.page_size,
                "scope": {
                    "start": parsed_start.isoformat(),
                    "end": parsed_end.isoformat(),
                },
            },
        )

    @router.get("/api/v2/inspections/export")
    async def export_inspections(
        request: Request,
        fmt: str = Query("csv"),
        start: str | None = Query(None),
        end: str | None = Query(None),
        days: int = Query(7, ge=1, le=90),
        inspector: str = Query("", max_length=128),
        device: str = Query("", max_length=64),
        aircraft: str = Query("", max_length=64),
        station: str = Query("", max_length=128),
        has_issue: bool | None = Query(None),
        status: str = Query("", max_length=16),
    ) -> Response:
        blocked = gate(request)
        if blocked is not None:
            return blocked
        _identity, _auth_error = await require_authorized(request)
        if _auth_error is not None:
            return _auth_error
        user_id, username = _identity
        parsed_end = _parse_iso(end) if end else dt.datetime.now(UTC)
        parsed_start = (
            _parse_iso(start)
            if start
            else parsed_end - dt.timedelta(days=max(1, min(days, 90)))
        )
        result = await service.list(
            InspectionRecordFilter(
                start=parsed_start,
                end=parsed_end,
                inspector_username=inspector or None,
                device_id=device or None,
                aircraft_no=aircraft or None,
                station=station or None,
                has_issue=has_issue,
                status=status.upper() or None,
                page=1,
                page_size=200,
            )
        )
        return _export_response(
            request,
            result.items,
            fmt=fmt,
            filename="inspection_records",
        )

    @router.get("/api/v2/inspections/metrics")
    async def inspections_metrics(
        request: Request,
        days: int = Query(7, ge=1, le=90),
    ) -> JSONResponse:
        blocked = gate(request)
        if blocked is not None:
            return blocked
        _identity, _auth_error = await require_authorized(request)
        if _auth_error is not None:
            return _auth_error
        user_id, username = _identity
        start, end, requested_days = parse_scope(request, days)
        metrics = await service.dashboard_metrics(start=start, end=end)
        return envelope(
            request,
            {
                "metrics": _json_safe(metrics),
                "scope": {
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "days": requested_days,
                },
            },
        )

    @router.get("/api/v2/inspections/authorized-users")
    async def list_authorized_users(request: Request) -> JSONResponse:
        blocked = require_admin_route(request)
        if blocked is not None:
            return blocked
        identity, error = await require_admin(request)
        if error is not None:
            return error
        users = await record_store.list_authorized_users()
        return envelope(
            request,
            {
                "items": [
                    {
                        "username": user.username,
                        "aee_account_id": user.aee_account_id,
                        "display_name": user.display_name,
                        "department": user.department,
                        "role": user.role,
                        "enabled": user.enabled,
                    }
                    for user in users
                ]
            },
        )

    @router.post("/api/v2/inspections/authorized-users")
    async def add_authorized_user(
        request: Request,
        body: AuthorizedUserBody,
    ) -> JSONResponse:
        blocked = require_admin_route(request)
        if blocked is not None:
            return blocked
        operator_id, operator_name, auth_error = await _admin_identity(request)
        if auth_error is not None:
            return auth_error
        user = build_authorized_user(
            aee_account_id=body.aee_account_id,
            username=body.username,
            display_name=body.display_name,
            department=body.department,
            role=body.role,
            enabled=body.enabled,
            valid_from=body.valid_from,
            valid_until=body.valid_until,
        )
        await record_store.upsert_authorized_user(user)
        await _record_user_audit(
            operator_user_id=operator_id,
            operator_username=operator_name,
            target_username=user.username,
            action="USER_ADDED",
            summary=f"role={user.role or ''} enabled={user.enabled}",
        )
        return envelope(
            request,
            {"username": user.username, "enabled": user.enabled},
            status_code=201,
        )

    @router.post("/api/v2/inspections/authorized-users/{username}/enable")
    async def enable_authorized_user(
        request: Request,
        username: str,
    ) -> JSONResponse:
        return await _set_user_enabled(request, username, enabled=True)

    @router.post("/api/v2/inspections/authorized-users/{username}/disable")
    async def disable_authorized_user(
        request: Request,
        username: str,
    ) -> JSONResponse:
        return await _set_user_enabled(request, username, enabled=False)

    async def _set_user_enabled(
        request: Request,
        username: str,
        *,
        enabled: bool,
    ) -> JSONResponse:
        blocked = require_admin_route(request)
        if blocked is not None:
            return blocked
        operator_id, operator_name, auth_error = await _admin_identity(request)
        if auth_error is not None:
            return auth_error
        user = await record_store.get_authorized_user(username=username)
        if user is None:
            return envelope(
                request,
                {"code": "not_found"},
                ok=False,
                status_code=404,
            )
        updated = build_authorized_user(
            aee_account_id=user.aee_account_id,
            username=user.username,
            display_name=user.display_name,
            department=user.department,
            role=user.role,
            enabled=enabled,
            valid_from=user.valid_from,
            valid_until=user.valid_until,
            created_at=user.created_at,
        )
        await record_store.upsert_authorized_user(updated)
        await _record_user_audit(
            operator_user_id=operator_id,
            operator_username=operator_name,
            target_username=user.username,
            action="USER_ENABLED" if enabled else "USER_DISABLED",
            summary=None,
        )
        return envelope(
            request,
            {"username": user.username, "enabled": enabled},
        )

    async def _admin_identity(
        request: Request,
    ) -> tuple[str | None, str, JSONResponse | None]:
        identity, error = await require_admin(request)
        if error is not None:
            return None, "", error
        user_id, username = identity
        return user_id, username, None

    @router.post("/api/v2/inspections")
    async def create_draft(
        request: Request,
        body: CreateDraftBody,
    ) -> JSONResponse:
        blocked = gate(request)
        if blocked is not None:
            return blocked
        _identity, _auth_error = await require_authorized(request)
        if _auth_error is not None:
            return _auth_error
        user_id, username = _identity
        try:
            detail = await service.create_draft(
                inspector_user_id=user_id,
                inspector_username=username,
                device_id=body.device_id,
                inspection_started_at=body.inspection_started_at,
                inspection_ended_at=body.inspection_ended_at,
                aircraft_no=body.aircraft_no,
                flight_source_id=body.flight_source_id,
                flight_no=body.flight_no,
                routine_task_source_id=body.routine_task_source_id,
                maintenance_task_text=body.maintenance_task_text,
                station=body.station,
                location_text=body.location_text,
                has_issue=body.has_issue,
                issue_type=body.issue_type,
                issue_level=body.issue_level,
                issue_description=body.issue_description,
                remark=body.remark,
                realtime_view_event_ids=body.realtime_view_event_ids,
            )
        except ValueError as exc:
            return envelope(
                request,
                {"code": "invalid_record", "message": str(exc)},
                ok=False,
                status_code=400,
            )
        return envelope(
            request,
            {"inspection": _json_safe(detail)},
            status_code=201,
        )

    @router.get("/api/v2/inspections/{inspection_id}")
    async def get_inspection(
        request: Request,
        inspection_id: str,
    ) -> JSONResponse:
        blocked = gate(request)
        if blocked is not None:
            return blocked
        _identity, _auth_error = await require_authorized(request)
        if _auth_error is not None:
            return _auth_error
        user_id, username = _identity
        try:
            detail = await service.get(inspection_id)
        except KeyError:
            return envelope(
                request,
                {"code": "not_found"},
                ok=False,
                status_code=404,
            )
        return envelope(request, {"inspection": _json_safe(detail)})

    @router.patch("/api/v2/inspections/{inspection_id}")
    async def update_draft(
        request: Request,
        inspection_id: str,
        body: UpdateDraftBody,
    ) -> JSONResponse:
        blocked = gate(request)
        if blocked is not None:
            return blocked
        _identity, _auth_error = await require_authorized(request)
        if _auth_error is not None:
            return _auth_error
        user_id, username = _identity
        try:
            detail = await service.update_draft(
                inspection_id=inspection_id,
                editor_user_id=user_id,
                editor_username=username,
                aircraft_no=body.aircraft_no,
                flight_source_id=body.flight_source_id,
                flight_no=body.flight_no,
                routine_task_source_id=body.routine_task_source_id,
                maintenance_task_text=body.maintenance_task_text,
                station=body.station,
                location_text=body.location_text,
                has_issue=body.has_issue,
                issue_type=body.issue_type,
                issue_level=body.issue_level,
                issue_description=body.issue_description,
                remark=body.remark,
                realtime_view_event_ids=body.realtime_view_event_ids,
            )
        except KeyError:
            return envelope(
                request,
                {"code": "not_found"},
                ok=False,
                status_code=404,
            )
        except ValueError as exc:
            return envelope(
                request,
                {"code": "invalid_state", "message": str(exc)},
                ok=False,
                status_code=400,
            )
        return envelope(request, {"inspection": _json_safe(detail)})

    @router.post("/api/v2/inspections/{inspection_id}/submit")
    async def submit_inspection(
        request: Request,
        inspection_id: str,
    ) -> JSONResponse:
        blocked = gate(request)
        if blocked is not None:
            return blocked
        _identity, _auth_error = await require_authorized(request)
        if _auth_error is not None:
            return _auth_error
        user_id, username = _identity
        try:
            detail = await service.submit(
                inspection_id=inspection_id,
                submitter_user_id=user_id,
                submitter_username=username,
            )
        except KeyError:
            return envelope(
                request,
                {"code": "not_found"},
                ok=False,
                status_code=404,
            )
        except ValueError as exc:
            return envelope(
                request,
                {"code": "invalid_state", "message": str(exc)},
                ok=False,
                status_code=400,
            )
        return envelope(request, {"inspection": _json_safe(detail)})

    @router.post("/api/v2/inspections/{inspection_id}/correct")
    async def correct_inspection(
        request: Request,
        inspection_id: str,
        body: CorrectBody,
    ) -> JSONResponse:
        blocked = gate(request)
        if blocked is not None:
            return blocked
        _identity, _auth_error = await require_authorized(request)
        if _auth_error is not None:
            return _auth_error
        user_id, username = _identity
        try:
            detail = await service.correct(
                inspection_id=inspection_id,
                corrector_user_id=user_id,
                corrector_username=username,
                correction_reason=body.correction_reason,
                aircraft_no=body.aircraft_no,
                flight_source_id=body.flight_source_id,
                flight_no=body.flight_no,
                routine_task_source_id=body.routine_task_source_id,
                maintenance_task_text=body.maintenance_task_text,
                station=body.station,
                location_text=body.location_text,
                has_issue=body.has_issue,
                issue_type=body.issue_type,
                issue_level=body.issue_level,
                issue_description=body.issue_description,
                remark=body.remark,
            )
        except KeyError:
            return envelope(
                request,
                {"code": "not_found"},
                ok=False,
                status_code=404,
            )
        except ValueError as exc:
            return envelope(
                request,
                {"code": "invalid_state", "message": str(exc)},
                ok=False,
                status_code=400,
            )
        return envelope(request, {"inspection": _json_safe(detail)})

    return router


def _parse_iso(value: str) -> dt.datetime | None:
    try:
        parsed = dt.datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _json_safe(value: Any) -> Any:
    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, dt.datetime):
        return value.isoformat().replace("+00:00", "Z")
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


EXPORT_COLUMNS = (
    ("inspection_id", "inspection_id"),
    ("监察日期", "inspection_date"),
    ("监察人", "inspector_username"),
    ("账号", "inspector_user_id"),
    ("设备", "device_id"),
    ("飞机号", "aircraft_no"),
    ("航班号", "flight_no"),
    ("站点", "station"),
    ("维修任务", "maintenance_task_text"),
    ("开始时间", "inspection_started_at"),
    ("结束时间", "inspection_ended_at"),
    ("监察时长", "inspection_duration_seconds"),
    ("是否有问题", "has_issue"),
    ("问题类型", "issue_type"),
    ("问题等级", "issue_level"),
    ("问题描述", "issue_description"),
    ("备注", "remark"),
    ("记录状态", "status"),
)


def _export_response(
    request: Request,
    records: tuple[Any, ...],
    *,
    fmt: str,
    filename: str,
) -> Response:
    rows = [_record_row(record) for record in records]
    normalized = fmt.strip().lower()
    if normalized == "xlsx":
        return _xlsx_response(request, rows, filename)
    return _csv_response(request, rows, filename)


def _record_row(record: Any) -> dict[str, Any]:
    started = record.inspection_started_at
    return {
        "inspection_id": record.inspection_id,
        "inspection_date": started.astimezone(UTC).date().isoformat(),
        "inspector_username": record.inspector_username,
        "inspector_user_id": record.inspector_user_id or "",
        "device_id": record.device_id,
        "aircraft_no": record.aircraft_no or "",
        "flight_no": record.flight_no or "",
        "station": record.station or "",
        "maintenance_task_text": record.maintenance_task_text or "",
        "inspection_started_at": started.isoformat(),
        "inspection_ended_at": record.inspection_ended_at.isoformat(),
        "inspection_duration_seconds": record.inspection_duration_seconds,
        "has_issue": "是" if record.has_issue else "否",
        "issue_type": record.issue_type or "",
        "issue_level": record.issue_level or "",
        "issue_description": record.issue_description or "",
        "remark": record.remark or "",
        "status": record.status,
    }


def _csv_response(
    request: Request,
    rows: list[dict[str, Any]],
    filename: str,
) -> Response:
    import csv

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([label for label, _ in EXPORT_COLUMNS])
    for row in rows:
        writer.writerow([row[key] for _, key in EXPORT_COLUMNS])
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                f"attachment; filename={filename}.csv"
            )
        },
    )


def _xlsx_response(
    request: Request,
    rows: list[dict[str, Any]],
    filename: str,
) -> Response:
    from openpyxl import Workbook
    from openpyxl.styles import Font

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "inspection_records"
    sheet.append([label for label, _ in EXPORT_COLUMNS])
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for row in rows:
        sheet.append([row[key] for _, key in EXPORT_COLUMNS])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return Response(
        content=buffer.getvalue(),
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": (
                f"attachment; filename={filename}.xlsx"
            )
        },
    )
