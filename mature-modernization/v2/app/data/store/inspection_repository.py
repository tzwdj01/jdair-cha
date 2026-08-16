from __future__ import annotations

import datetime as dt
from abc import ABC, abstractmethod

from ..inspection_records import (
    AuthorizedUser,
    InspectionAuditEvent,
    InspectionRecord,
    InspectionRecordFilter,
    InspectionRecordPage,
    InspectionRecordViewLink,
)


class InspectionRecordStore(ABC):
    """Persistence seam for the CHA inspection workflow (M4 P3).

    Covers CHA-authorized users, InspectionRecord lifecycle, the
    InspectionRecord <-> RealtimeViewEvent link and audit events. Everything
    is non-production until the production activation gate is authorized.
    """

    @abstractmethod
    async def upsert_authorized_user(self, user: AuthorizedUser) -> int:
        """Create or update an authorized user (by aee_account_id)."""

    @abstractmethod
    async def get_authorized_user(
        self,
        *,
        aee_account_id: str | None = None,
        username: str | None = None,
    ) -> AuthorizedUser | None:
        """Return a single authorized user by account id or username."""

    @abstractmethod
    async def list_authorized_users(
        self,
        *,
        enabled_only: bool = False,
    ) -> tuple[AuthorizedUser, ...]:
        """List authorized users, optionally only enabled ones."""

    @abstractmethod
    async def is_account_authorized(
        self,
        *,
        username: str,
        at: dt.datetime,
    ) -> bool:
        """True when the username is enabled and valid at ``at``."""

    @abstractmethod
    async def upsert_inspection_record(self, record: InspectionRecord) -> int:
        """Create or update an InspectionRecord (by inspection_id)."""

    @abstractmethod
    async def get_inspection_record(
        self,
        inspection_id: str,
    ) -> InspectionRecord | None:
        """Return an InspectionRecord by id."""

    @abstractmethod
    async def list_inspection_records(
        self,
        record_filter: InspectionRecordFilter,
    ) -> InspectionRecordPage:
        """Query records with filters and pagination."""

    @abstractmethod
    async def link_realtime_view_events(
        self,
        links: tuple[InspectionRecordViewLink, ...],
    ) -> int:
        """Attach RealtimeViewEvents to an InspectionRecord (idempotent)."""

    @abstractmethod
    async def fetch_view_links(
        self,
        inspection_id: str,
    ) -> tuple[str, ...]:
        """Return linked realtime view event ids for a record."""

    @abstractmethod
    async def append_audit_event(
        self,
        event: InspectionAuditEvent,
    ) -> int:
        """Append an audit event."""

    @abstractmethod
    async def list_audit_events(
        self,
        inspection_id: str,
    ) -> tuple[InspectionAuditEvent, ...]:
        """Return audit events for a record, oldest first."""
