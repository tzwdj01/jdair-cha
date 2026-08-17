from __future__ import annotations

from ..config import Settings
from ..data.store import (
    InspectionRecordStore,
    InspectionStore,
    MemoryInspectionRecordStore,
    MemoryInspectionStore,
    PostgresInspectionRecordStore,
    PostgresInspectionStore,
)


def build_inspection_store(
    settings: Settings,
) -> InspectionStore | None:
    """Build the inspection store for the current deployment.

    In-memory store is limited to non-production. In production the
    PostgreSQL store is wired only when the explicit production gate
    ``CHA_V2_INSPECTION_STORE_PG_ENABLED=true`` is set (Canary-only); it is
    never enabled by default.
    """

    if settings.inspection_store_pg_enabled:
        return PostgresInspectionStore(schema="inspection")
    if settings.environment == "production":
        return None
    mode = settings.inspection_store_mode.strip().casefold()
    if mode == "memory":
        return MemoryInspectionStore()
    return None


def build_inspection_record_store(
    settings: Settings,
) -> InspectionRecordStore | None:
    """Build the M4 P3 inspection workflow store for the current deployment.

    In-memory store is limited to non-production. In production the
    PostgreSQL-backed workflow store is wired only when the explicit
    production gate ``CHA_V2_INSPECTION_STORE_PG_ENABLED=true`` is set
    (Canary-only); it is never enabled by default.
    """

    if settings.inspection_store_pg_enabled:
        return PostgresInspectionRecordStore(schema="inspection")
    if settings.environment == "production":
        return None
    mode = settings.inspection_store_mode.strip().casefold()
    if mode == "memory":
        return MemoryInspectionRecordStore()
    return None
