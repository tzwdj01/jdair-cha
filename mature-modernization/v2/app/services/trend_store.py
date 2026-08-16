from __future__ import annotations

import asyncio
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any


class DeviceTrendStore:
    """Persist bounded device snapshots without storing source credentials."""

    def __init__(self, state_dir: str, max_points: int = 288) -> None:
        self.path = Path(state_dir) / "device-trend.json"
        self.max_points = max(24, max_points)
        self._lock = asyncio.Lock()

    async def record(
        self,
        *,
        total: int,
        online: int,
        offline: int,
        interval_seconds: int = 300,
    ) -> list[dict[str, Any]]:
        async with self._lock:
            return await asyncio.to_thread(
                self._record_sync,
                total,
                online,
                offline,
                interval_seconds,
            )

    async def read(self) -> list[dict[str, Any]]:
        async with self._lock:
            return await asyncio.to_thread(self._read_sync)

    def _record_sync(
        self,
        total: int,
        online: int,
        offline: int,
        interval_seconds: int,
    ) -> list[dict[str, Any]]:
        rows = self._read_sync()
        now = dt.datetime.now(dt.timezone.utc)
        last = self._parse_timestamp(rows[-1].get("timestamp")) if rows else None
        if last is None or (now - last).total_seconds() >= interval_seconds:
            rows.append(
                {
                    "timestamp": now.isoformat().replace("+00:00", "Z"),
                    "total": int(total),
                    "online": int(online),
                    "offline": int(offline),
                    "online_rate": (
                        round(int(online) / int(total) * 100, 1)
                        if int(total)
                        else 0.0
                    ),
                }
            )
            rows = rows[-self.max_points :]
            self._write_sync(rows)
        return rows

    def _read_sync(self) -> list[dict[str, Any]]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(payload, list):
            return []
        return [item for item in payload if isinstance(item, dict)][
            -self.max_points :
        ]

    def _write_sync(self, rows: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(".tmp")
        temp_path.write_text(
            json.dumps(rows, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        os.replace(temp_path, self.path)

    @staticmethod
    def _parse_timestamp(value: Any) -> dt.datetime | None:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
