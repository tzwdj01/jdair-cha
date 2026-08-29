from __future__ import annotations

import asyncio
from typing import Any

from ..data.store import PostgresPoolExhaustedError


DEFAULT_HEALTH_CHECK_TIMEOUT_SECONDS = 1.0


async def inspection_postgresql_readiness(
    settings: Any,
    inspection_store: Any | None,
    inspection_record_store: Any | None,
    *,
    health_check_timeout_seconds: float = DEFAULT_HEALTH_CHECK_TIMEOUT_SECONDS,
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

    if health_check_timeout_seconds <= 0:
        raise ValueError("health_check_timeout_seconds must be positive")

    results = await asyncio.gather(
        _health_check(inspection_store, health_check_timeout_seconds),
        _health_check(inspection_record_store, health_check_timeout_seconds),
        return_exceptions=True,
    )
    if any(
        isinstance(result, (PostgresPoolExhaustedError, asyncio.TimeoutError))
        for result in results
    ):
        return {
            "status": "degraded",
            "required": True,
            "impact": "inspection_dashboard_and_workflow",
        }
    if any(isinstance(result, Exception) for result in results):
        return {
            "status": "unavailable",
            "required": True,
            "impact": "inspection_dashboard_and_workflow",
        }

    data_ok, workflow_ok = (bool(result) for result in results)
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


async def _health_check(store: Any, timeout_seconds: float) -> bool:
    checker = getattr(store, "health_check", None)
    if not callable(checker):
        return False
    return bool(await asyncio.wait_for(checker(), timeout=timeout_seconds))
