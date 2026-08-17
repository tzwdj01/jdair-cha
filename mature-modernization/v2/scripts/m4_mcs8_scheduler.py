#!/usr/bin/env python3
"""M4 P3.2 production LOW-RATE scheduler canary over the MCS8 native channel.

This runs a conservative periodic collection loop (DEVICE -> MEDIA -> ALARM,
one cycle in flight) against the MCS8 native server channel and persists to
the configured PostgreSQL. It is the production scheduler canary: low rate,
sequential, single-cycle, configurable cadence.

Configuration (never commit credentials; inject from the protected env):

    CHA_V2_MCS8_HOST / WS_PORT / API_PORT / USERNAME / PASSWORD
    CHA_PG_HOST / PORT / DATABASE / USER / PASSWORD / SSLMODE / SCHEMA

Scheduler controls:

    CHA_V2_INSPECTION_SCHEDULER_ENABLED=true        # kill switch (must be true)
    CHA_V2_INSPECTION_SCHEDULER_PERIOD_SECONDS=600  # cadence
    CHA_V2_INSPECTION_SCHEDULER_MAX_CYCLES=6        # cycles per run
    CHA_V2_INSPECTION_SCHEDULER_LOOKBACK_SECONDS=3600
    CHA_V2_INSPECTION_SCHEDULER_OVERLAP_SECONDS=300
    CHA_V2_INSPECTION_SCHEDULER_STATE_DIR=/opt/.../mcs8-scheduler

The scheduler logs bounded, redacted lines (no password/token/SessionId/PG
password). Kill switch: set ``CHA_V2_INSPECTION_SCHEDULER_ENABLED=false`` and
stop the process; existing DB / realtime / Legacy / Dashboard are unaffected.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any


# Make the ``app`` package importable when run as
# ``/opt/jdair-cha/m4-scheduler/scripts/m4_mcs8_scheduler.py`` (the release
# root sits one directory above ``scripts/``).
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.data.mcs8_auth import MCS8ServerAuthProvider  # noqa: E402
from app.data.store import PostgresInspectionStore  # noqa: E402
from app.services.mcs8_scheduler import MCS8ProductionScheduler  # noqa: E402


SHANGHAI = dt.timezone(dt.timedelta(hours=8), name="Asia/Shanghai")


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name, default).strip()
    return value


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)).strip())
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on", "enabled"}


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s %(levelname)s "
            "cha.mcs8.scheduler %(message)s"
        ),
        stream=sys.stdout,
    )
    # keep the noisy upstream logger bounded
    logging.getLogger("uvicorn").setLevel(logging.WARNING)


def _env_required(name: str) -> str:
    value = _env(name)
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


async def _main() -> int:
    _setup_logging()
    logger = logging.getLogger("mcs8-scheduler")

    enabled = _env_bool(
        "CHA_V2_INSPECTION_SCHEDULER_ENABLED",
        False,
    )
    if not enabled:
        logger.info(
            "scheduler_disabled "
            "CHA_V2_INSPECTION_SCHEDULER_ENABLED is not true"
        )
        return 0

    host = _env_required("CHA_V2_MCS8_HOST")
    ws_port = _env_int("CHA_V2_MCS8_WS_PORT", 7711)
    api_port = _env_int("CHA_V2_MCS8_API_PORT", 7712)
    username = _env_required("CHA_V2_MCS8_USERNAME")
    password = _env("CHA_V2_MCS8_PASSWORD")
    if not password:
        raise SystemExit(
            "Missing required environment variable: CHA_V2_MCS8_PASSWORD"
        )

    period = _env_int(
        "CHA_V2_INSPECTION_SCHEDULER_PERIOD_SECONDS",
        600,
    )
    max_cycles = _env_int(
        "CHA_V2_INSPECTION_SCHEDULER_MAX_CYCLES",
        6,
    )
    lookback = _env_int(
        "CHA_V2_INSPECTION_SCHEDULER_LOOKBACK_SECONDS",
        3600,
    )
    overlap = _env_int(
        "CHA_V2_INSPECTION_SCHEDULER_OVERLAP_SECONDS",
        300,
    )
    state_dir = _env(
        "CHA_V2_INSPECTION_SCHEDULER_STATE_DIR",
        "/opt/jdair-cha/v2/data/mcs8-scheduler",
    )
    schema = _env("CHA_PG_SCHEMA", "inspection")

    store = PostgresInspectionStore(schema=schema)
    auth = MCS8ServerAuthProvider(
        host=host,
        ws_port=ws_port,
        username=username,
        password=password,
    )
    scheduler = MCS8ProductionScheduler(
        auth=auth,
        host=host,
        api_port=api_port,
        store=store,
        lookback_seconds=lookback,
        overlap_seconds=overlap,
        state_dir=state_dir,
        source_timezone=SHANGHAI,
        max_login_retries=2,
    )

    logger.info(
        "scheduler_start cycle_period=%ds max_cycles=%d lookback=%ds "
        "overlap=%ds host=%s api_port=%d schema=%s state_dir=%s",
        period,
        max_cycles,
        lookback,
        overlap,
        host,
        api_port,
        schema,
        state_dir,
    )

    started = time.perf_counter()
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signame in ("SIGTERM", "SIGINT"):
        try:
            loop.add_signal_handler(
                getattr(signal, signame),
                stop_event.set,
            )
        except (NotImplementedError, RuntimeError):  # pragma: no cover
            pass
    results = await scheduler.run(
        period_seconds=period,
        max_cycles=max_cycles,
        stop_event=stop_event,
    )
    elapsed = time.perf_counter() - started

    summary: dict[str, Any] = {
        "run_finished_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "elapsed_seconds": round(elapsed, 3),
        "cycles": [result.to_dict() for result in results],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    logger.info(
        "scheduler_finished cycles=%d elapsed_s=%.1f",
        len(results),
        elapsed,
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
