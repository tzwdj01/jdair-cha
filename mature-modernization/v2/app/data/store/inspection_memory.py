from __future__ import annotations

import datetime as dt
from typing import Iterable

from ..inspection_records import (
    AuthorizedUser,
    InspectionAuditEvent,
    InspectionRecord,
    InspectionRecordFilter,
    InspectionRecordPage,
    InspectionRecordViewLink,
    is_user_active,
)
from .inspection_repository import InspectionRecordStore


UTC = dt.timezone.utc


class MemoryInspectionRecordStore(InspectionRecordStore):
    """In-memory InspectionRecordStore for tests and local development."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._users: dict[str, AuthorizedUser] = {}
        self._users_by_username: dict[str, AuthorizedUser] = {}
        self._records: dict[str, InspectionRecord] = {}
        self._views: dict[tuple[str, str], InspectionRecordViewLink] = {}
        self._audit: dict[str, InspectionAuditEvent] = {}

    async def upsert_authorized_user(self, user: AuthorizedUser) -> int:
        self._users[user.aee_account_id] = user
        self._users_by_username[user.username] = user
        return 1

    async def get_authorized_user(
        self,
        *,
        aee_account_id: str | None = None,
        username: str | None = None,
    ) -> AuthorizedUser | None:
        if aee_account_id:
            return self._users.get(aee_account_id)
        if username:
            return self._users_by_username.get(username)
        return None

    async def list_authorized_users(
        self,
        *,
        enabled_only: bool = False,
    ) -> tuple[AuthorizedUser, ...]:
        users = tuple(self._users.values())
        if enabled_only:
            users = tuple(user for user in users if user.enabled)
        return tuple(sorted(users, key=lambda user: user.username))

    async def is_account_authorized(
        self,
        *,
        username: str,
        at: dt.datetime,
    ) -> bool:
        user = self._users_by_username.get(username)
        if user is None:
            return False
        return is_user_active(user, at=at)

    async def upsert_inspection_record(self, record: InspectionRecord) -> int:
        self._records[record.inspection_id] = record
        return 1

    async def get_inspection_record(
        self,
        inspection_id: str,
    ) -> InspectionRecord | None:
        return self._records.get(inspection_id)

    async def list_inspection_records(
        self,
        record_filter: InspectionRecordFilter,
    ) -> InspectionRecordPage:
        items = list(self._records.values())
        if record_filter.start is not None:
            start = record_filter.start.astimezone(UTC)
            items = [
                item
                for item in items
                if (
                    item.submitted_at or item.inspection_started_at
                ).astimezone(UTC) >= start
            ]
        if record_filter.end is not None:
            end = record_filter.end.astimezone(UTC)
            items = [
                item
                for item in items
                if (
                    item.submitted_at or item.inspection_started_at
                ).astimezone(UTC) <= end
            ]
        if record_filter.inspector_username:
            items = [
                item
                for item in items
                if item.inspector_username == record_filter.inspector_username
            ]
        if record_filter.device_id:
            items = [item for item in items if item.device_id == record_filter.device_id]
        if record_filter.aircraft_no:
            items = [item for item in items if item.aircraft_no == record_filter.aircraft_no]
        if record_filter.flight_no:
            items = [item for item in items if item.flight_no == record_filter.flight_no]
        if record_filter.station:
            items = [item for item in items if item.station == record_filter.station]
        if record_filter.task_text:
            needle = record_filter.task_text.casefold()
            items = [
                item
                for item in items
                if (
                    item.maintenance_task_text or ""
                ).casefold().find(needle) >= 0
            ]
        if record_filter.has_issue is not None:
            items = [item for item in items if item.has_issue == record_filter.has_issue]
        if record_filter.issue_type:
            items = [item for item in items if item.issue_type == record_filter.issue_type]
        if record_filter.issue_level:
            items = [item for item in items if item.issue_level == record_filter.issue_level]
        if record_filter.status:
            items = [item for item in items if item.status == record_filter.status]

        items.sort(
            key=lambda item: (
                item.submitted_at or item.inspection_started_at,
                item.inspection_id,
            )
        )
        total = len(items)
        start_index = (record_filter.page - 1) * record_filter.page_size
        page_items = tuple(items[start_index : start_index + record_filter.page_size])
        return InspectionRecordPage(
            items=page_items,
            total=total,
            page=record_filter.page,
            page_size=record_filter.page_size,
        )

    async def link_realtime_view_events(
        self,
        links: tuple[InspectionRecordViewLink, ...],
    ) -> int:
        accepted = 0
        for link in links:
            key = (link.inspection_id, link.realtime_view_event_id)
            if key in self._views:
                continue
            self._views[key] = link
            accepted += 1
        return accepted

    async def fetch_view_links(
        self,
        inspection_id: str,
    ) -> tuple[str, ...]:
        return tuple(
            sorted(
                link.realtime_view_event_id
                for (record_id, _), link in self._views.items()
                if record_id == inspection_id
            )
        )

    async def append_audit_event(
        self,
        event: InspectionAuditEvent,
    ) -> int:
        self._audit[event.audit_id] = event
        return 1

    async def list_audit_events(
        self,
        inspection_id: str,
    ) -> tuple[InspectionAuditEvent, ...]:
        events = [
            event
            for event in self._audit.values()
            if event.inspection_id == inspection_id
        ]
        return tuple(sorted(events, key=lambda event: event.acted_at))
