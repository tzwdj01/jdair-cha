from __future__ import annotations

from typing import Any


async def inspection_postgresql_readiness(
    settings: Any,
    inspection_store: Any | None,
    inspection_record_store: Any | None,
) -> dict[str, Any]:
    """Report the optional M4 PostgreSQL dependency without leaking details.

    The V2 process still serves legacy-compatible endpoints when the
    inspection/dashboard database is unavailable.  This helper therefore
    reports the inspection dependency accurately and lets the caller expose a
    ``degraded`` overall readiness state instead of falsely claiming the
    database is disabled or making Legacy a database-dependent service.
    """

    if not bool(getattr(settings, "inspection_store_pg_enabled", False)):
        return {
            "status": "not_enabled",
            "required": False,
            "impact": "not_applicable",
        }

    if inspection_store is None or inspection_record_store is None:
        return {
            "status": "misconfigured",
            "required": True,
            "impact": "inspection_dashboard_and_workflow",
        }

    try:
        data_ok = await _health_check(inspection_store)
        workflow_ok = await _health_check(inspection_record_store)
    except Exception:
        return {
            "status": "unavailable",
            "required": True,
            "impact": "inspection_dashboard_and_workflow",
        }

    if not (data_ok and workflow_ok):
        return {
            "status": "unavailable",
            "required": True,
            "impact": "inspection_dashboard_and_workflow",
        }

    return {
        "status": "ready",
        "required": True,
        "impact": "inspection_dashboard_and_workflow",
    }


async def _health_check(store: Any) -> bool:
    checker = getattr(store, "health_check", None)
    if not callable(checker):
        return False
    return bool(await checker())
