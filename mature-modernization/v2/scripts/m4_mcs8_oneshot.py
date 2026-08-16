#!/usr/bin/env python3
"""M4 P3.2 production ONE SHOT over the MCS8 native server channel.

This is a standalone, read-mostly collector that:

* logs in to the MCS8 native server over WS (SDK port) to obtain a session
  token;
* collects DEVICE (current status snapshot), MEDIA (bounded window) and
  ALARM (bounded window) from the MCS8 native REST API port;
* persists normalized rows into the configured PostgreSQL
  (cha_m4 / inspection) through the existing InspectionStore.

Device semantics are honest polling semantics: the first observation of a
device is an INITIAL_OBSERVATION; later snapshots that are unchanged produce
no event; a changed state produces exactly one CHA_OBSERVED_TRANSITION. It
never fabricates an upstream-native transition and never claims full native
event coverage.

Usage (never commit credentials; inject from the protected environment):

    CHA_V2_MCS8_HOST=... CHA_V2_MCS8_WS_PORT=7711 \
    CHA_V2_MCS8_API_PORT=7712 CHA_V2_MCS8_USERNAME=... \
    CHA_V2_MCS8_PASSWORD=... \
    CHA_PG_HOST=... CHA_PG_PORT=5432 CHA_PG_DATABASE=cha_m4 \
    CHA_PG_USER=cha_m4_app CHA_PG_PASSWORD=... CHA_PG_SCHEMA=inspection \
    python m4_mcs8_oneshot.py --media-start 2026-08-16T00:00:00+08:00 \
      --media-end 2026-08-16T23:59:59+08:00

The script never writes tokens, passwords or cookies to stdout/logs, and it
does not enable any scheduler.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import os
import sys
from typing import Any

from app.data.mcs8_adapter import MCS8ReadOnlyDataAdapter
from app.data.mcs8_auth import MCS8ServerAuthProvider
from app.data.mcs8_collector import MCS8InspectionCollector
from app.data.mcs8_http import MCS8DataHTTPClient
from app.data.store import PostgresInspectionStore


UTC = dt.timezone.utc
SHANGHAI = dt.timezone(dt.timedelta(hours=8), name="Asia/Shanghai")


def _env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def _parse_window(value: str) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=SHANGHAI)
    return parsed.astimezone(UTC)


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    mcs8_host = _env("CHA_V2_MCS8_HOST")
    mcs8_ws_port = int(os.getenv("CHA_V2_MCS8_WS_PORT", "7711"))
    mcs8_api_port = int(os.getenv("CHA_V2_MCS8_API_PORT", "7712"))
    mcs8_username = _env("CHA_V2_MCS8_USERNAME")
    mcs8_password = os.getenv("CHA_V2_MCS8_PASSWORD", "")
    if not mcs8_password:
        raise SystemExit(
            "Missing required environment variable: CHA_V2_MCS8_PASSWORD"
        )

    store = PostgresInspectionStore(schema=args.schema)

    auth = MCS8ServerAuthProvider(
        host=mcs8_host,
        ws_port=mcs8_ws_port,
        username=mcs8_username,
        password=mcs8_password,
    )
    token = auth.login()
    client = MCS8DataHTTPClient(
        base_url=f"http://{mcs8_host}:{mcs8_api_port}",
        token_provider=lambda: token,
        token_invalidator=auth.invalidate,
    )
    adapter = MCS8ReadOnlyDataAdapter(client)
    collector = MCS8InspectionCollector(
        adapter,
        store,
        source_timezone=SHANGHAI,
        include_alarms=True,
    )

    media_start = _parse_window(args.media_start)
    media_end = _parse_window(args.media_end)
    if media_end <= media_start:
        raise SystemExit("media-end must be after media-start")

    report: dict[str, Any] = {
        "window": {
            "start": media_start.isoformat(),
            "end": media_end.isoformat(),
            "timezone": str(SHANGHAI),
        },
        "sources": {},
    }

    if not args.skip_device:
        device_source = await collector.collect_device_snapshot()
        report["sources"]["device_status"] = {
            "source": "device_status",
            "status": device_source.status,
            "error_code": device_source.error_code,
            "records_total": device_source.records_total,
            "fetched_source_count": device_source.fetched_source_count,
            "stored_count": len(device_source.rows),
            "invalid_row_count": device_source.invalid_row_count,
            "complete": device_source.complete,
            "quality_flags": list(device_source.quality_flags),
        }

    collected = await collector.collect(media_start, media_end)
    for name, source in collected.items():
        stored_count = 0
        if name == "media_files" and source.status == "ok":
            stored_count = await store.upsert_media_files(source.rows)
        elif name == "alarms" and source.status == "ok":
            stored_count = await store.upsert_alarm_events(source.rows)
        report["sources"][name] = {
            "source": name,
            "status": source.status,
            "error_code": source.error_code,
            "records_total": source.records_total,
            "fetched_source_count": source.fetched_source_count,
            "stored_count": stored_count,
            "invalid_row_count": source.invalid_row_count,
            "complete": source.complete,
            "quality_flags": list(source.quality_flags),
        }

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--media-start",
        required=True,
        help="Media/alarm window start (ISO-8601, local/Shanghai ok)",
    )
    parser.add_argument(
        "--media-end",
        required=True,
        help="Media/alarm window end (ISO-8601, local/Shanghai ok)",
    )
    parser.add_argument(
        "--schema",
        default="inspection",
        help="PostgreSQL schema (default: inspection)",
    )
    parser.add_argument(
        "--skip-device",
        action="store_true",
        help="Skip the DEVICE snapshot collection",
    )
    args = parser.parse_args()
    report = asyncio.run(_run(args))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
