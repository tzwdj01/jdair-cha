from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from ..config import Settings
from .cache import AsyncTTLCache, CacheResult
from .legacy import (
    LegacyClient,
    LegacyPayloadError,
    LegacyResponse,
    LegacyTransportError,
)
from .trend_store import DeviceTrendStore


SHANGHAI = dt.timezone(dt.timedelta(hours=8), name="Asia/Shanghai")


class DashboardError(RuntimeError):
    pass


class DashboardAuthenticationError(DashboardError):
    pass


class DashboardSourceError(DashboardError):
    pass


@dataclass(frozen=True)
class SourceSpec:
    name: str
    ttl_seconds: int
    loader: Callable[[], Awaitable[LegacyResponse | Any]]


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _integer(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _iso_from_epoch(value: float) -> str:
    return (
        dt.datetime.fromtimestamp(value, dt.timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _parse_datetime(value: Any) -> dt.datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text.replace("/", "-").replace("T", " ").rstrip("Z")
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
    ):
        try:
            parsed = dt.datetime.strptime(normalized[:19], fmt)
            return parsed.replace(tzinfo=SHANGHAI)
        except ValueError:
            continue
    return None


class DashboardService:
    """Read-only M2 metrics layer over the existing production APIs."""

    def __init__(
        self,
        legacy_client: LegacyClient,
        settings: Settings,
        cache: AsyncTTLCache | None = None,
    ) -> None:
        self.legacy_client = legacy_client
        self.settings = settings
        self.cache = cache or AsyncTTLCache(max_entries=256)
        self._background_tasks: set[asyncio.Task[CacheResult]] = set()
        self.trend_store = DeviceTrendStore(settings.dashboard_state_dir)

    async def snapshot(
        self,
        cookie: str,
        *,
        days: int = 3,
        city: str = "",
        force: bool = False,
    ) -> dict[str, Any]:
        if not cookie:
            raise DashboardAuthenticationError(
                "An authenticated CHA session is required."
            )
        days = max(1, min(int(days), 30))
        city = city.strip()
        session_key = hashlib.sha256(cookie.encode("utf-8")).hexdigest()[:24]

        session = await self._source(
            SourceSpec(
                "session",
                self.settings.dashboard_device_ttl_seconds,
                lambda: self.legacy_client.session(cookie),
            ),
            session_key,
            force=force,
        )
        session_payload = session.value
        if not isinstance(session_payload, dict) or not session_payload.get(
            "authenticated"
        ):
            raise DashboardAuthenticationError(
                "The CHA session is missing or expired."
            )

        today = dt.datetime.now(SHANGHAI).date().isoformat()
        specs = [
            SourceSpec(
                "devices",
                self.settings.dashboard_device_ttl_seconds,
                lambda: self.legacy_client.devices(cookie),
            ),
            SourceSpec(
                "video_stats",
                self.settings.dashboard_video_ttl_seconds,
                lambda: self.legacy_client.video_stats(cookie),
            ),
            SourceSpec(
                "flights",
                self.settings.dashboard_flight_ttl_seconds,
                lambda: self.legacy_client.flights(cookie, today),
            ),
            SourceSpec(
                "routine_tasks",
                self.settings.dashboard_routine_ttl_seconds,
                lambda: self.legacy_client.routine_tasks(cookie, today),
            ),
            SourceSpec(
                f"video_trend_{days}d",
                self.settings.dashboard_trend_ttl_seconds,
                lambda: self._load_video_trend(cookie, days),
            ),
        ]
        loaded: dict[str, CacheResult] = {"session": session}
        failed: dict[str, Exception] = {}
        tasks = {
            asyncio.create_task(
                self._source(spec, session_key, force=force),
                name=f"dashboard:{spec.name}",
            ): spec
            for spec in specs
        }
        done, pending = await asyncio.wait(
            tasks,
            timeout=self.settings.dashboard_initial_wait_seconds,
        )
        for task in done:
            spec = tasks[task]
            try:
                loaded[spec.name] = task.result()
            except DashboardAuthenticationError:
                for remaining in pending:
                    remaining.cancel()
                raise
            except Exception as exc:
                failed[spec.name] = exc
        for task in pending:
            spec = tasks[task]
            failed[spec.name] = DashboardSourceError(
                f"{spec.name} is warming in the background"
            )
            self._background_tasks.add(task)
            task.add_done_callback(self._background_done)

        if "devices" not in loaded and any(
            task for task, spec in tasks.items() if spec.name == "devices"
        ):
            device_task = next(
                task for task, spec in tasks.items() if spec.name == "devices"
            )
            try:
                loaded["devices"] = await asyncio.wait_for(
                    asyncio.shield(device_task),
                    timeout=min(3.0, self.settings.legacy_timeout_seconds),
                )
                failed.pop("devices", None)
            except DashboardAuthenticationError:
                raise
            except Exception as exc:
                failed["devices"] = exc

        for task, spec in tasks.items():
            if task.done() and spec.name not in loaded and spec.name not in failed:
                try:
                    loaded[spec.name] = task.result()
                except DashboardAuthenticationError:
                    raise
                except Exception as exc:
                    failed[spec.name] = exc

        devices = loaded.get("devices")
        if devices is None:
            raise DashboardSourceError(
                "The device source is unavailable and no cached value exists."
            )
        device_rows = devices.value if devices and isinstance(devices.value, list) else []
        video_source = loaded.get("video_stats")
        video_available = video_source is not None
        video_stats = (
            video_source.value
            if video_source and isinstance(video_source.value, dict)
            else {}
        )
        flights_source = loaded.get("flights")
        flights_available = flights_source is not None
        flights = (
            flights_source.value
            if flights_source and isinstance(flights_source.value, dict)
            else {}
        )
        routines_source = loaded.get("routine_tasks")
        routines_available = routines_source is not None
        routines = (
            routines_source.value
            if routines_source and isinstance(routines_source.value, dict)
            else {}
        )
        trend_source = loaded.get(f"video_trend_{days}d")
        trend = (
            trend_source.value
            if trend_source and isinstance(trend_source.value, list)
            else []
        )

        normalized_devices = self._normalize_devices(
            device_rows,
            video_stats,
            video_available=video_available,
        )
        available_cities = sorted(
            {
                str(item.get("city") or "未知")
                for item in normalized_devices
            }
        )
        filtered_devices = [
            item
            for item in normalized_devices
            if not city or str(item.get("city") or "未知") == city
        ]
        geography = self._geography(filtered_devices)
        summary = self._summary(
            filtered_devices,
            flights,
            routines,
            geography,
            video_available=video_available,
            flights_available=flights_available,
            routines_available=routines_available,
        )
        try:
            device_trend = await self.trend_store.record(
                total=summary["devices"]["total"],
                online=summary["devices"]["online"],
                offline=summary["devices"]["offline"],
            )
        except OSError:
            device_trend = []
        exceptions = self._exceptions(
            filtered_devices,
            video_available=video_available,
        )
        freshness = self._freshness(specs, loaded, failed)
        points = self._map_points(filtered_devices, geography)

        return {
            "scope": {
                "days": days,
                "city": city,
                "available_cities": available_cities,
                "generated_for": session_payload.get("username", ""),
                "business_timezone": "Asia/Shanghai",
                "files_window_days": 3,
                "video_trend_scope": "global",
                "flight_and_task_scope": "today_global",
            },
            "summary": summary,
            "device_status": {
                "online": summary["devices"]["online"],
                "offline": summary["devices"]["offline"],
                "online_rate": summary["devices"]["online_rate"],
            },
            "device_trend": device_trend,
            "video_trend": trend,
            "geography": geography,
            "map_points": points,
            "coverage": {
                "online_device_rate": summary["devices"]["online_rate"],
                "recent_file_device_rate": summary["files"][
                    "device_coverage_rate"
                ],
                "city_file_coverage_rate": summary["files"][
                    "city_coverage_rate"
                ],
                "flight_reference_rate": None,
                "routine_reference_rate": None,
                "note": (
                    "M2 首版仅统计设备在线与近 3 日文件覆盖；"
                    "航班/任务关联覆盖率待增量索引完成后启用。"
                ),
            },
            "exceptions": exceptions,
            "freshness": freshness,
            "sources": {
                "flights_preview": (flights.get("records") or [])[:6],
                "routine_preview": (routines.get("records") or [])[:6],
            },
        }

    def _background_done(self, task: asyncio.Task[CacheResult]) -> None:
        self._background_tasks.discard(task)
        try:
            task.result()
        except Exception:
            pass

    async def _source(
        self,
        spec: SourceSpec,
        session_key: str,
        *,
        force: bool,
    ) -> CacheResult:
        key = f"{session_key}:{spec.name}"

        async def load() -> Any:
            try:
                value = await spec.loader()
            except LegacyTransportError as exc:
                raise DashboardSourceError(
                    f"{spec.name} is unavailable"
                ) from exc
            if isinstance(value, LegacyResponse):
                if value.status_code in {401, 403}:
                    raise DashboardAuthenticationError(
                        "The CHA session is missing or expired."
                    )
                if value.status_code != 200:
                    raise DashboardSourceError(
                        f"{spec.name} returned HTTP {value.status_code}"
                    )
                try:
                    return value.json()
                except LegacyPayloadError as exc:
                    raise DashboardSourceError(
                        f"{spec.name} returned invalid JSON"
                    ) from exc
            return value

        return await self.cache.get_or_load(
            key,
            spec.ttl_seconds,
            (
                0
                if spec.name == "session"
                else self.settings.dashboard_stale_seconds
            ),
            load,
            force=force,
        )

    async def _load_video_trend(
        self,
        cookie: str,
        days: int,
    ) -> list[dict[str, Any]]:
        today = dt.datetime.now(SHANGHAI).date()

        semaphore = asyncio.Semaphore(4)

        async def load_day(day: dt.date) -> dict[str, Any]:
            async with semaphore:
                start = f"{day.isoformat()} 00:00:00"
                end = f"{day.isoformat()} 23:59:59"
                response = await self.legacy_client.records(
                    cookie,
                    start,
                    end,
                    page=1,
                    page_size=1,
                )
                if response.status_code in {401, 403}:
                    raise DashboardAuthenticationError(
                        "The CHA session is missing or expired."
                    )
                if response.status_code != 200:
                    raise DashboardSourceError(
                        f"records returned HTTP {response.status_code}"
                    )
                payload = response.json()
            return {
                "date": day.isoformat(),
                "label": f"{day.month}/{day.day}",
                "count": _integer(
                    payload.get("recordsTotal", payload.get("total", 0))
                ),
            }

        dates = [
            today - dt.timedelta(days=offset)
            for offset in reversed(range(days))
        ]
        return list(await asyncio.gather(*(load_day(day) for day in dates)))

    def _normalize_devices(
        self,
        devices: list[Any],
        video_stats: dict[str, Any],
        *,
        video_available: bool,
    ) -> list[dict[str, Any]]:
        now = dt.datetime.now(SHANGHAI)
        normalized = []
        for row in devices:
            if not isinstance(row, dict):
                continue
            dev_id = str(row.get("devId") or "").strip()
            if not dev_id:
                continue
            stats = video_stats.get(dev_id) or {}
            last_seen = row.get("lastOnlineTime") or row.get("gpsTime") or ""
            parsed_seen = _parse_datetime(last_seen)
            stale_hours = (
                round((now - parsed_seen).total_seconds() / 3600, 1)
                if parsed_seen
                else None
            )
            normalized.append(
                {
                    "dev_id": dev_id,
                    "name": str(row.get("name") or dev_id),
                    "group": str(row.get("groupName") or "未分组"),
                    "city": str(row.get("city") or "未知"),
                    "warehouse": str(row.get("warehouse") or ""),
                    "online": bool(row.get("online")),
                    "lng": row.get("lng"),
                    "lat": row.get("lat"),
                    "gps_time": str(row.get("gpsTime") or ""),
                    "last_seen": str(last_seen),
                    "stale_hours": stale_hours,
                    "file_count": (
                        _integer(stats.get("count"))
                        if video_available
                        else None
                    ),
                    "size_mb": (
                        round(_number(stats.get("sizeMB")), 2)
                        if video_available
                        else None
                    ),
                }
            )
        return normalized

    def _geography(
        self,
        devices: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "city": "",
                "devices": 0,
                "online": 0,
                "offline": 0,
                "file_count": 0,
                "size_mb": 0.0,
                "file_devices": 0,
            }
        )
        for device in devices:
            city = str(device.get("city") or "未知")
            item = grouped[city]
            item["city"] = city
            item["devices"] += 1
            item["online" if device.get("online") else "offline"] += 1
            if device.get("file_count") is not None:
                item["file_count"] += _integer(device.get("file_count"))
                item["size_mb"] += _number(device.get("size_mb"))
            if (
                device.get("file_count") is not None
                and _integer(device.get("file_count")) > 0
            ):
                item["file_devices"] += 1
        result = []
        for item in grouped.values():
            item["size_mb"] = round(item["size_mb"], 2)
            item["online_rate"] = round(
                item["online"] / item["devices"] * 100,
                1,
            ) if item["devices"] else 0.0
            result.append(item)
        return sorted(
            result,
            key=lambda item: (
                -_integer(item.get("devices")),
                str(item.get("city")),
            ),
        )

    def _summary(
        self,
        devices: list[dict[str, Any]],
        flights: dict[str, Any],
        routines: dict[str, Any],
        geography: list[dict[str, Any]],
        *,
        video_available: bool,
        flights_available: bool,
        routines_available: bool,
    ) -> dict[str, Any]:
        total = len(devices)
        online = sum(1 for item in devices if item.get("online"))
        file_devices = (
            sum(
                1
                for item in devices
                if item.get("file_count") is not None
                and _integer(item.get("file_count")) > 0
            )
            if video_available
            else None
        )
        file_count = (
            sum(_integer(item.get("file_count")) for item in devices)
            if video_available
            else None
        )
        size_mb = (
            sum(_number(item.get("size_mb")) for item in devices)
            if video_available
            else None
        )
        city_file_count = (
            sum(
                1
                for item in geography
                if _integer(item.get("file_count")) > 0
            )
            if video_available
            else None
        )
        return {
            "devices": {
                "total": total,
                "online": online,
                "offline": max(0, total - online),
                "online_rate": round(online / total * 100, 1) if total else 0.0,
            },
            "cities": {"total": len(geography)},
            "files": {
                "count": file_count,
                "size_mb": round(size_mb, 2) if size_mb is not None else None,
                "size_gb": (
                    round(size_mb / 1024, 2)
                    if size_mb is not None
                    else None
                ),
                "devices_with_files": file_devices,
                "devices_without_files": (
                    max(0, total - file_devices)
                    if file_devices is not None
                    else None
                ),
                "device_coverage_rate": (
                    round(file_devices / total * 100, 1)
                    if total and file_devices is not None
                    else (0.0 if video_available else None)
                ),
                "city_coverage_rate": (
                    round(city_file_count / len(geography) * 100, 1)
                    if geography and city_file_count is not None
                    else (0.0 if video_available else None)
                ),
            },
            "operations": {
                "flights_today": (
                    _integer(flights.get("total"))
                    if flights_available
                    else None
                ),
                "routine_tasks_today": (
                    _integer(routines.get("total"))
                    if routines_available
                    else None
                ),
            },
        }

    def _exceptions(
        self,
        devices: list[dict[str, Any]],
        *,
        video_available: bool,
    ) -> dict[str, Any]:
        rows = []
        for item in devices:
            reasons = []
            severity = "info"
            if not item.get("online"):
                reasons.append("设备离线")
                severity = "high"
            if video_available and _integer(item.get("file_count")) == 0:
                reasons.append("近 3 日无文件")
                if severity != "high":
                    severity = "medium"
            stale_hours = item.get("stale_hours")
            if stale_hours is None:
                reasons.append("无定位时间")
                if severity == "info":
                    severity = "medium"
            elif _number(stale_hours) >= 2:
                reasons.append(f"定位已延迟 {_number(stale_hours):.1f} 小时")
                if severity == "info":
                    severity = "medium"
            if reasons:
                rows.append(
                    {
                        "severity": severity,
                        "dev_id": item.get("dev_id"),
                        "name": item.get("name"),
                        "city": item.get("city"),
                        "online": item.get("online"),
                        "file_count": item.get("file_count"),
                        "last_seen": item.get("last_seen"),
                        "reasons": reasons,
                    }
                )
        rank = {"high": 0, "medium": 1, "info": 2}
        rows.sort(
            key=lambda item: (
                rank.get(str(item.get("severity")), 9),
                str(item.get("city")),
                str(item.get("name")),
            )
        )
        return {
            "total": len(rows),
            "offline": sum(1 for item in devices if not item.get("online")),
            "without_recent_files": sum(
                1
                for item in devices
                if video_available and _integer(item.get("file_count")) == 0
            ) if video_available else None,
            "stale_location": sum(
                1
                for item in devices
                if item.get("stale_hours") is None
                or _number(item.get("stale_hours")) >= 2
            ),
            "items": rows[:100],
        }

    def _freshness(
        self,
        specs: list[SourceSpec],
        loaded: dict[str, CacheResult],
        failed: dict[str, Exception],
    ) -> list[dict[str, Any]]:
        labels = {
            "session": "认证会话",
            "devices": "设备与定位",
            "video_stats": "近 3 日文件统计",
            "flights": "今日航班动态",
            "routine_tasks": "今日例行任务",
        }
        ttl_by_name = {spec.name: spec.ttl_seconds for spec in specs}
        rows = []
        for name in ["session", *(spec.name for spec in specs)]:
            result = loaded.get(name)
            error = failed.get(name)
            label = labels.get(
                name,
                "文件趋势" if name.startswith("video_trend_") else name,
            )
            if result:
                status = "stale" if result.stale else "fresh"
                rows.append(
                    {
                        "name": name,
                        "label": label,
                        "status": status,
                        "fetched_at": _iso_from_epoch(
                            result.fetched_at_epoch
                        ),
                        "age_seconds": round(result.age_seconds, 1),
                        "latency_ms": round(result.latency_ms, 1),
                        "cache_hit": result.cache_hit,
                        "ttl_seconds": ttl_by_name.get(
                            name,
                            self.settings.dashboard_device_ttl_seconds,
                        ),
                        "error": result.error,
                    }
                )
            else:
                rows.append(
                    {
                        "name": name,
                        "label": label,
                        "status": "unavailable",
                        "fetched_at": None,
                        "age_seconds": None,
                        "latency_ms": None,
                        "cache_hit": False,
                        "ttl_seconds": ttl_by_name.get(name),
                        "error": str(error)[:180] if error else "unavailable",
                    }
                )
        return rows

    def _map_points(
        self,
        devices: list[dict[str, Any]],
        geography: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        city_summary = {item["city"]: item for item in geography}
        coordinate_groups: dict[str, list[tuple[float, float]]] = defaultdict(list)
        for item in devices:
            try:
                lng = float(item.get("lng"))
                lat = float(item.get("lat"))
            except (TypeError, ValueError):
                continue
            if 70 <= lng <= 140 and 10 <= lat <= 55:
                coordinate_groups[str(item.get("city") or "未知")].append(
                    (lng, lat)
                )
        points = []
        for city, coordinates in coordinate_groups.items():
            summary = city_summary.get(city, {})
            points.append(
                {
                    "city": city,
                    "lng": round(
                        sum(item[0] for item in coordinates)
                        / len(coordinates),
                        5,
                    ),
                    "lat": round(
                        sum(item[1] for item in coordinates)
                        / len(coordinates),
                        5,
                    ),
                    "devices": summary.get("devices", len(coordinates)),
                    "online": summary.get("online", 0),
                    "file_count": summary.get("file_count", 0),
                }
            )
        return sorted(
            points,
            key=lambda item: -_integer(item.get("devices")),
        )
