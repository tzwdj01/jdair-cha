from __future__ import annotations

import asyncio
import datetime as dt
import os
from typing import Any

try:  # pragma: no cover - exercised only when a PG store is constructed
    import psycopg2
except ImportError:  # pragma: no cover
    psycopg2 = None  # type: ignore[assignment]

from ..inspection_records import (
    AuthorizedUser,
    AuthorizedUserAuditEvent,
    InspectionAuditEvent,
    InspectionRecord,
    InspectionRecordFilter,
    InspectionRecordPage,
    InspectionRecordViewLink,
    is_user_active,
)
from .inspection_repository import InspectionRecordStore
from .pool import PostgresConnectionPool


UTC = dt.timezone.utc


class PostgresInspectionRecordStore(InspectionRecordStore):
    """PostgreSQL-backed InspectionRecordStore (migration 0002)."""

    def __init__(
        self,
        *,
        host: str | None = None,
        port: int | None = None,
        database: str | None = None,
        user: str | None = None,
        password: str | None = None,
        sslmode: str | None = None,
        schema: str = "inspection_rehearsal",
        connect_timeout: int = 10,
    ) -> None:
        self._host = host or os.environ.get("CHA_PG_HOST", "127.0.0.1")
        self._port = port or int(os.environ.get("CHA_PG_PORT", "5432"))
        self._database = database or os.environ.get(
            "CHA_PG_DATABASE",
            "cha_m4_rehearsal",
        )
        self._user = user or os.environ.get("CHA_PG_USER")
        self._password = (
            password
            or os.environ.get("CHA_PG_PASSWORD")
            or os.environ.get("PGPASSWORD")
        )
        self._sslmode = sslmode or os.environ.get("CHA_PG_SSLMODE", "prefer")
        self._schema = schema or os.environ.get("CHA_PG_SCHEMA", "inspection_rehearsal")
        self._connect_timeout = connect_timeout
        if not self._user:
            raise ValueError("CHA_PG_USER is required")
        # Authentication/workflow traffic has a deliberately small bounded
        # pool. Together with the data store (maximum four), the process can
        # use no more than six PostgreSQL connections during this Canary.
        self._pool = PostgresConnectionPool(
            min_connections=1,
            max_connections=2,
            connection_kwargs={
                "host": self._host,
                "port": self._port,
                "dbname": self._database,
                "user": self._user,
                "password": self._password,
                "sslmode": self._sslmode,
                "connect_timeout": self._connect_timeout,
            },
        )

    def _connect(self) -> Any:
        if psycopg2 is None:
            raise ImportError(
                "psycopg2 is required to use PostgresInspectionRecordStore"
            )
        return self._pool.connection()

    def close(self) -> None:
        """Release all pooled workflow/authentication connections."""

        self._pool.close()

    async def health_check(self) -> bool:
        """Check connectivity without returning database diagnostics."""

        return await asyncio.to_thread(self._health_check_sync)

    def _health_check_sync(self) -> bool:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                return cursor.fetchone() == (1,)

    def _qualify(self, table: str) -> str:
        return f'"{self._schema}".{table}'

    def _select(self, sql: str, params: list[Any]) -> list[tuple[Any, ...]]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                return cursor.fetchall()

    async def upsert_authorized_user(self, user: AuthorizedUser) -> int:
        return await asyncio.to_thread(self._upsert_authorized_user_sync, user)

    def _upsert_authorized_user_sync(self, user: AuthorizedUser) -> int:
        sql = f"""
        INSERT INTO {self._qualify('authorized_users')}
            (aee_account_id, username, display_name, department, role,
             enabled, valid_from, valid_until, created_at, updated_at,
             quality_flags)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (aee_account_id) DO UPDATE SET
            username = EXCLUDED.username,
            display_name = EXCLUDED.display_name,
            department = EXCLUDED.department,
            role = EXCLUDED.role,
            enabled = EXCLUDED.enabled,
            valid_from = EXCLUDED.valid_from,
            valid_until = EXCLUDED.valid_until,
            updated_at = EXCLUDED.updated_at,
            quality_flags = EXCLUDED.quality_flags
        """
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    sql,
                    (
                        user.aee_account_id,
                        user.username,
                        user.display_name,
                        user.department,
                        user.role,
                        user.enabled,
                        _opt_utc(user.valid_from),
                        _opt_utc(user.valid_until),
                        _utc(user.created_at),
                        _utc(user.updated_at),
                        list(user.quality_flags),
                    ),
                )
        return 1

    async def get_authorized_user(
        self,
        *,
        aee_account_id: str | None = None,
        username: str | None = None,
    ) -> AuthorizedUser | None:
        return await asyncio.to_thread(
            self._get_authorized_user_sync,
            aee_account_id,
            username,
        )

    def _get_authorized_user_sync(
        self,
        aee_account_id: str | None,
        username: str | None,
    ) -> AuthorizedUser | None:
        if aee_account_id:
            rows = self._select(
                f"SELECT * FROM {self._qualify('authorized_users')} "
                "WHERE aee_account_id = %s",
                [aee_account_id],
            )
        elif username:
            rows = self._select(
                f"SELECT * FROM {self._qualify('authorized_users')} "
                "WHERE username = %s",
                [username],
            )
        else:
            return None
        return _row_to_user(rows[0]) if rows else None

    async def list_authorized_users(
        self,
        *,
        enabled_only: bool = False,
    ) -> tuple[AuthorizedUser, ...]:
        return await asyncio.to_thread(
            self._list_authorized_users_sync,
            enabled_only,
        )

    def _list_authorized_users_sync(
        self,
        enabled_only: bool,
    ) -> tuple[AuthorizedUser, ...]:
        sql = f"SELECT * FROM {self._qualify('authorized_users')}"
        if enabled_only:
            sql += " WHERE enabled = TRUE"
        sql += " ORDER BY username"
        return tuple(_row_to_user(row) for row in self._select(sql, []))

    async def is_account_authorized(
        self,
        *,
        username: str,
        at: dt.datetime,
    ) -> bool:
        return await asyncio.to_thread(
            self._is_account_authorized_sync,
            username,
            at,
        )

    def _is_account_authorized_sync(
        self,
        username: str,
        at: dt.datetime,
    ) -> bool:
        user = self._get_authorized_user_sync(None, username)
        if user is None:
            return False
        return is_user_active(user, at=at)

    async def upsert_inspection_record(self, record: InspectionRecord) -> int:
        return await asyncio.to_thread(
            self._upsert_inspection_record_sync,
            record,
        )

    def _upsert_inspection_record_sync(self, record: InspectionRecord) -> int:
        sql = f"""
        INSERT INTO {self._qualify('inspection_records')}
            (inspection_id, inspector_user_id, inspector_username, device_id,
             inspection_started_at, inspection_ended_at,
             inspection_duration_seconds, aircraft_no, flight_source_id,
             flight_no, routine_task_source_id, maintenance_task_text,
             station, location_text, has_issue, issue_type, issue_level,
             issue_description, remark, status, created_at, created_by,
             updated_at, updated_by, submitted_at, submitted_by,
             corrected_at, corrected_by, correction_reason, quality_flags)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s)
        ON CONFLICT (inspection_id) DO UPDATE SET
            inspector_user_id = EXCLUDED.inspector_user_id,
            inspector_username = EXCLUDED.inspector_username,
            device_id = EXCLUDED.device_id,
            inspection_started_at = EXCLUDED.inspection_started_at,
            inspection_ended_at = EXCLUDED.inspection_ended_at,
            inspection_duration_seconds = EXCLUDED.inspection_duration_seconds,
            aircraft_no = EXCLUDED.aircraft_no,
            flight_source_id = EXCLUDED.flight_source_id,
            flight_no = EXCLUDED.flight_no,
            routine_task_source_id = EXCLUDED.routine_task_source_id,
            maintenance_task_text = EXCLUDED.maintenance_task_text,
            station = EXCLUDED.station,
            location_text = EXCLUDED.location_text,
            has_issue = EXCLUDED.has_issue,
            issue_type = EXCLUDED.issue_type,
            issue_level = EXCLUDED.issue_level,
            issue_description = EXCLUDED.issue_description,
            remark = EXCLUDED.remark,
            status = EXCLUDED.status,
            updated_at = EXCLUDED.updated_at,
            updated_by = EXCLUDED.updated_by,
            submitted_at = EXCLUDED.submitted_at,
            submitted_by = EXCLUDED.submitted_by,
            corrected_at = EXCLUDED.corrected_at,
            corrected_by = EXCLUDED.corrected_by,
            correction_reason = EXCLUDED.correction_reason,
            quality_flags = EXCLUDED.quality_flags
        """
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    sql,
                    (
                        record.inspection_id,
                        record.inspector_user_id,
                        record.inspector_username,
                        record.device_id,
                        _utc(record.inspection_started_at),
                        _utc(record.inspection_ended_at),
                        record.inspection_duration_seconds,
                        record.aircraft_no,
                        record.flight_source_id,
                        record.flight_no,
                        record.routine_task_source_id,
                        record.maintenance_task_text,
                        record.station,
                        record.location_text,
                        record.has_issue,
                        record.issue_type,
                        record.issue_level,
                        record.issue_description,
                        record.remark,
                        record.status,
                        _utc(record.created_at),
                        record.created_by,
                        _utc(record.updated_at),
                        record.updated_by,
                        _opt_utc(record.submitted_at),
                        record.submitted_by,
                        _opt_utc(record.corrected_at),
                        record.corrected_by,
                        record.correction_reason,
                        list(record.quality_flags),
                    ),
                )
        return 1

    async def get_inspection_record(
        self,
        inspection_id: str,
    ) -> InspectionRecord | None:
        return await asyncio.to_thread(
            self._get_inspection_record_sync,
            inspection_id,
        )

    def _get_inspection_record_sync(
        self,
        inspection_id: str,
    ) -> InspectionRecord | None:
        rows = self._select(
            f"SELECT * FROM {self._qualify('inspection_records')} "
            "WHERE inspection_id = %s",
            [inspection_id],
        )
        return _row_to_record(rows[0]) if rows else None

    async def list_inspection_records(
        self,
        record_filter: InspectionRecordFilter,
    ) -> InspectionRecordPage:
        return await asyncio.to_thread(
            self._list_inspection_records_sync,
            record_filter,
        )

    def _list_inspection_records_sync(
        self,
        record_filter: InspectionRecordFilter,
    ) -> InspectionRecordPage:
        clauses: list[str] = []
        params: list[Any] = []
        if record_filter.start is not None:
            clauses.append(
                "COALESCE(submitted_at, inspection_started_at) >= %s"
            )
            params.append(_utc(record_filter.start))
        if record_filter.end is not None:
            clauses.append(
                "COALESCE(submitted_at, inspection_started_at) <= %s"
            )
            params.append(_utc(record_filter.end))
        if record_filter.inspector_username:
            clauses.append("inspector_username = %s")
            params.append(record_filter.inspector_username)
        if record_filter.device_id:
            clauses.append("device_id = %s")
            params.append(record_filter.device_id)
        if record_filter.aircraft_no:
            clauses.append("aircraft_no = %s")
            params.append(record_filter.aircraft_no)
        if record_filter.flight_no:
            clauses.append("flight_no = %s")
            params.append(record_filter.flight_no)
        if record_filter.station:
            clauses.append("station = %s")
            params.append(record_filter.station)
        if record_filter.task_text:
            clauses.append("maintenance_task_text ILIKE %s")
            params.append(f"%{record_filter.task_text}%")
        if record_filter.has_issue is not None:
            clauses.append("has_issue = %s")
            params.append(record_filter.has_issue)
        if record_filter.issue_type:
            clauses.append("issue_type = %s")
            params.append(record_filter.issue_type)
        if record_filter.issue_level:
            clauses.append("issue_level = %s")
            params.append(record_filter.issue_level)
        if record_filter.status:
            clauses.append("status = %s")
            params.append(record_filter.status)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        table = self._qualify("inspection_records")
        total = self._select(
            f"SELECT count(*) FROM {table}{where}",
            params,
        )[0][0]
        order = "COALESCE(submitted_at, inspection_started_at) ASC, inspection_id"
        offset = (record_filter.page - 1) * record_filter.page_size
        rows = self._select(
            f"SELECT * FROM {table}{where} ORDER BY {order} "
            "LIMIT %s OFFSET %s",
            params + [record_filter.page_size, offset],
        )
        return InspectionRecordPage(
            items=tuple(_row_to_record(row) for row in rows),
            total=int(total),
            page=record_filter.page,
            page_size=record_filter.page_size,
        )

    async def link_realtime_view_events(
        self,
        links: tuple[InspectionRecordViewLink, ...],
    ) -> int:
        return await asyncio.to_thread(
            self._link_realtime_view_events_sync,
            links,
        )

    def _link_realtime_view_events_sync(
        self,
        links: tuple[InspectionRecordViewLink, ...],
    ) -> int:
        sql = f"""
        INSERT INTO {self._qualify('inspection_record_views')}
            (inspection_id, realtime_view_event_id)
        VALUES (%s, %s)
        ON CONFLICT (inspection_id, realtime_view_event_id) DO NOTHING
        """
        accepted = 0
        with self._connect() as connection:
            with connection.cursor() as cursor:
                for link in links:
                    cursor.execute(
                        sql,
                        (link.inspection_id, link.realtime_view_event_id),
                    )
                    accepted += cursor.rowcount
        return accepted

    async def fetch_view_links(
        self,
        inspection_id: str,
    ) -> tuple[str, ...]:
        return await asyncio.to_thread(
            self._fetch_view_links_sync,
            inspection_id,
        )

    def _fetch_view_links_sync(
        self,
        inspection_id: str,
    ) -> tuple[str, ...]:
        rows = self._select(
            f"SELECT realtime_view_event_id FROM "
            f"{self._qualify('inspection_record_views')} "
            "WHERE inspection_id = %s ORDER BY realtime_view_event_id",
            [inspection_id],
        )
        return tuple(row[0] for row in rows)

    async def append_audit_event(
        self,
        event: InspectionAuditEvent,
    ) -> int:
        return await asyncio.to_thread(self._append_audit_event_sync, event)

    def _append_audit_event_sync(self, event: InspectionAuditEvent) -> int:
        sql = f"""
        INSERT INTO {self._qualify('inspection_audit_events')}
            (audit_id, inspection_id, action, actor_user_id, actor_username,
             acted_at, summary)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (audit_id) DO NOTHING
        """
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    sql,
                    (
                        event.audit_id,
                        event.inspection_id,
                        event.action,
                        event.actor_user_id,
                        event.actor_username,
                        _utc(event.acted_at),
                        event.summary,
                    ),
                )
        return 1

    async def list_audit_events(
        self,
        inspection_id: str,
    ) -> tuple[InspectionAuditEvent, ...]:
        return await asyncio.to_thread(
            self._list_audit_events_sync,
            inspection_id,
        )

    def _list_audit_events_sync(
        self,
        inspection_id: str,
    ) -> tuple[InspectionAuditEvent, ...]:
        rows = self._select(
            f"SELECT * FROM {self._qualify('inspection_audit_events')} "
            "WHERE inspection_id = %s ORDER BY acted_at, audit_id",
            [inspection_id],
        )
        return tuple(_row_to_audit(row) for row in rows)

    async def append_user_audit_event(
        self,
        event: AuthorizedUserAuditEvent,
    ) -> int:
        return await asyncio.to_thread(
            self._append_user_audit_event_sync,
            event,
        )

    def _append_user_audit_event_sync(
        self,
        event: AuthorizedUserAuditEvent,
    ) -> int:
        sql = f"""
        INSERT INTO {self._qualify('authorized_user_audit_events')}
            (audit_id, action, operator_user_id, operator_username,
             target_username, acted_at, summary)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (audit_id) DO NOTHING
        """
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    sql,
                    (
                        event.audit_id,
                        event.action,
                        event.operator_user_id,
                        event.operator_username,
                        event.target_username,
                        _utc(event.acted_at),
                        event.summary,
                    ),
                )
        return 1

    async def list_user_audit_events(
        self,
        *,
        target_username: str | None = None,
    ) -> tuple[AuthorizedUserAuditEvent, ...]:
        return await asyncio.to_thread(
            self._list_user_audit_events_sync,
            target_username,
        )

    def _list_user_audit_events_sync(
        self,
        target_username: str | None,
    ) -> tuple[AuthorizedUserAuditEvent, ...]:
        sql = f"SELECT * FROM {self._qualify('authorized_user_audit_events')}"
        params: list[Any] = []
        if target_username:
            sql += " WHERE target_username = %s"
            params.append(target_username)
        sql += " ORDER BY acted_at, audit_id"
        return tuple(
            _row_to_user_audit(row)
            for row in self._select(sql, params)
        )


_USER_COLUMNS = (
    "aee_account_id",
    "username",
    "display_name",
    "department",
    "role",
    "enabled",
    "valid_from",
    "valid_until",
    "created_at",
    "updated_at",
    "quality_flags",
)

_RECORD_COLUMNS = (
    "inspection_id",
    "inspector_user_id",
    "inspector_username",
    "device_id",
    "inspection_started_at",
    "inspection_ended_at",
    "inspection_duration_seconds",
    "aircraft_no",
    "flight_source_id",
    "flight_no",
    "routine_task_source_id",
    "maintenance_task_text",
    "station",
    "location_text",
    "has_issue",
    "issue_type",
    "issue_level",
    "issue_description",
    "remark",
    "status",
    "created_at",
    "created_by",
    "updated_at",
    "updated_by",
    "submitted_at",
    "submitted_by",
    "corrected_at",
    "corrected_by",
    "correction_reason",
    "quality_flags",
)

_AUDIT_COLUMNS = (
    "audit_id",
    "inspection_id",
    "action",
    "actor_user_id",
    "actor_username",
    "acted_at",
    "summary",
)

_USER_AUDIT_COLUMNS = (
    "audit_id",
    "action",
    "operator_user_id",
    "operator_username",
    "target_username",
    "acted_at",
    "summary",
)


def _row_to_user(row: tuple[Any, ...]) -> AuthorizedUser:
    values = dict(zip(_USER_COLUMNS, row[1:]))
    return AuthorizedUser(
        aee_account_id=values["aee_account_id"],
        username=values["username"],
        display_name=values["display_name"],
        department=values["department"],
        role=values["role"],
        enabled=bool(values["enabled"]),
        valid_from=_opt_utc(values["valid_from"]),
        valid_until=_opt_utc(values["valid_until"]),
        created_at=_utc(values["created_at"]),
        updated_at=_utc(values["updated_at"]),
        quality_flags=tuple(values["quality_flags"] or ()),
    )


def _row_to_record(row: tuple[Any, ...]) -> InspectionRecord:
    values = dict(zip(_RECORD_COLUMNS, row[1:]))
    return InspectionRecord(
        inspection_id=values["inspection_id"],
        inspector_user_id=values["inspector_user_id"],
        inspector_username=values["inspector_username"],
        device_id=values["device_id"],
        inspection_started_at=_utc(values["inspection_started_at"]),
        inspection_ended_at=_utc(values["inspection_ended_at"]),
        inspection_duration_seconds=float(
            values["inspection_duration_seconds"]
        ),
        aircraft_no=values["aircraft_no"],
        flight_source_id=values["flight_source_id"],
        flight_no=values["flight_no"],
        routine_task_source_id=values["routine_task_source_id"],
        maintenance_task_text=values["maintenance_task_text"],
        station=values["station"],
        location_text=values["location_text"],
        has_issue=bool(values["has_issue"]),
        issue_type=values["issue_type"],
        issue_level=values["issue_level"],
        issue_description=values["issue_description"],
        remark=values["remark"],
        status=values["status"],
        created_at=_utc(values["created_at"]),
        created_by=values["created_by"],
        updated_at=_utc(values["updated_at"]),
        updated_by=values["updated_by"],
        submitted_at=_opt_utc(values["submitted_at"]),
        submitted_by=values["submitted_by"],
        corrected_at=_opt_utc(values["corrected_at"]),
        corrected_by=values["corrected_by"],
        correction_reason=values["correction_reason"],
        quality_flags=tuple(values["quality_flags"] or ()),
    )


def _row_to_audit(row: tuple[Any, ...]) -> InspectionAuditEvent:
    values = dict(zip(_AUDIT_COLUMNS, row[1:]))
    return InspectionAuditEvent(
        audit_id=values["audit_id"],
        inspection_id=values["inspection_id"],
        action=values["action"],
        actor_user_id=values["actor_user_id"],
        actor_username=values["actor_username"],
        acted_at=_utc(values["acted_at"]),
        summary=values["summary"],
    )


def _row_to_user_audit(row: tuple[Any, ...]) -> AuthorizedUserAuditEvent:
    values = dict(zip(_USER_AUDIT_COLUMNS, row[1:]))
    return AuthorizedUserAuditEvent(
        audit_id=values["audit_id"],
        action=values["action"],
        operator_user_id=values["operator_user_id"],
        operator_username=values["operator_username"],
        target_username=values["target_username"],
        acted_at=_utc(values["acted_at"]),
        summary=values["summary"],
    )


def _utc(value: dt.datetime) -> dt.datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(UTC)


def _opt_utc(value: dt.datetime | None) -> dt.datetime | None:
    return _utc(value) if value is not None else None
