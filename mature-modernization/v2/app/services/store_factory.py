from __future__ import annotations

from ..config import Settings
from ..data.store import (
    InspectionRecordStore,
    InspectionStore,
    MemoryInspectionRecordStore,
    MemoryInspectionStore,
)


def build_inspection_store(
    settings: Settings,
) -> InspectionStore | None:
    """Build the inspection store for the current deployment.

    Only the in-memory store is available today and it is intentionally
    limited to non-production environments: it is process-local and loses all
    history on restart, so it must never be used as a durable production data
    asset. Production deployments return ``None`` until a durable PostgreSQL
    store is wired and rehearsed.
    """

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

    Only the in-memory store is available for non-production today; a durable
    PostgreSQL-backed workflow store is wired after the P2.5 rehearsal gate.
    Production returns ``None`` until explicitly authorized.
    """

    if settings.environment == "production":
        return None
    mode = settings.inspection_store_mode.strip().casefold()
    if mode == "memory":
        return MemoryInspectionRecordStore()
    return None
