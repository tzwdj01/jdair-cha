from __future__ import annotations

import sys
from pathlib import Path
import os

# Add offline_geo directory to path for city boundary lookup
_OFFLINE_GEO_DIR = os.path.dirname(os.path.abspath(__file__)) + "/offline_geo"
if str(_OFFLINE_GEO_DIR) not in sys.path:
    sys.path.insert(0, str(_OFFLINE_GEO_DIR))
from offline_geo_lookup import OfflineGeoLookup

import datetime as dt
import base64
import hashlib
import hmac
import json
import math
import os
import subprocess
import re
import secrets
import socket
import struct
import threading
import time
import concurrent.futures
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


APP_DIR = Path(os.environ.get("MCS8_APP_DIR", r"C:\mcs8_x64"))
CONFIG_PATH = APP_DIR / "LocalConfig.xml"
LOG_DIR = APP_DIR / "log"
WEB_DIR = Path(__file__).resolve().parent
HLS_DIR = WEB_DIR / "hls"
FFMPEG_PATH = Path(os.environ.get("MCS8_FFMPEG_PATH", str(APP_DIR / "Streamplay" / "ffmpeg.exe")))
FFPROBE_PATH = Path(os.environ.get("MCS8_FFPROBE_PATH", str(APP_DIR / "Streamplay" / "ffprobe.exe")))
DEVICE_CATALOG_FILE = WEB_DIR / "device_catalog_cache.json"
SDK_DEVICE_EXPORT_FILE = WEB_DIR / "device_catalog_sdk_export.json"
INSPECTION_DB = WEB_DIR / "inspection_records.json"
PANEL_HOST = os.environ.get("MCS8_PANEL_HOST", "127.0.0.1")
PANEL_PORT = int(os.environ.get("MCS8_PANEL_PORT", "8788"))
AMRO_BASE_URL = os.environ.get("AMRO_BASE_URL", "http://jdair.top")
AMRO_USERNAME = os.environ.get("AMRO_USERNAME", "tzwdj01")
AMRO_PASSWORD = os.environ.get("AMRO_PASSWORD", "654268wxy")
DEVICE_CATALOG_CACHE: tuple[float, dict[str, dict[str, Any]]] | None = None
DEVICE_CATALOG_TTL = 30
GROUP_NAMES = {
    "30000002": "维修部",
}

TOOL_XLSX = WEB_DIR / "工具查询结果1782054355162.xlsx"
_tool_warehouse_cache: dict[str, str] | None = None
_video_info_cache: dict[str, dict[str, Any]] = {}
_video_info_lock = threading.Lock()
_flight_day_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_flight_day_cache_lock = threading.Lock()
_flight_day_cache_ttl = 600
_routine_day_cache: dict[tuple[str, int], tuple[float, list[dict[str, Any]]]] = {}
_routine_day_cache_lock = threading.Lock()
_routine_day_cache_ttl = 600
_record_position_cache: dict[tuple[str, str], dict[str, Any]] = {}
_record_position_cache_lock = threading.Lock()
SESSION_COOKIE = "jdair_mcs8_session"
SESSION_TTL_SECONDS = int(os.environ.get("MCS8_WEB_SESSION_TTL", str(12 * 3600)))
AUTH_SESSIONS: dict[str, dict[str, Any]] = {}
AUTH_SESSIONS_LOCK = threading.Lock()
REQUEST_CONTEXT = threading.local()
RECENT_GPS_CITIES_CACHE: dict[str, tuple[float, dict[str, list[dict[str, Any]]]]] = {}
RECENT_GPS_CITIES_TTL = 600
RECENT_GPS_CITIES_INFLIGHT: set[str] = set()
RECENT_GPS_CITIES_LOCK = threading.Lock()

def _clean_warehouse_name(raw: str) -> str:
    """Remove suffixes like airport, base, tool store etc."""
    for suffix in ["机场工具库", "基地工具库", "工具库", "机场", "基地", "库"]:
        if raw.endswith(suffix):
            raw = raw[:-len(suffix)]
            break
    return raw.strip()

def load_tool_warehouses() -> dict[str, str]:
    global _tool_warehouse_cache
    if _tool_warehouse_cache is not None:
        return _tool_warehouse_cache
    result: dict[str, str] = {}
    try:
        import openpyxl
        wb = openpyxl.load_workbook(str(TOOL_XLSX))
        ws = wb.active
        for row in ws.iter_rows(min_row=2, values_only=True):
            barcode = str(row[1] or "").strip()
            warehouse = str(row[8] or "").strip()
            if barcode and warehouse:
                result[barcode] = _clean_warehouse_name(warehouse)
        wb.close()
    except Exception:
        pass
    _tool_warehouse_cache = result
    return result

class MCS8Error(RuntimeError):
    pass


def local_config() -> dict[str, Any]:
    root = ET.parse(CONFIG_PATH).getroot()
    server = root.find(".//ServerModel")
    if server is None:
        raise MCS8Error(f"ServerModel not found in {CONFIG_PATH}.")

    def text(name: str, default: str = "") -> str:
        item = server.find(name)
        return item.text.strip() if item is not None and item.text else default

    def root_text(name: str, default: str = "") -> str:
        item = root.find(name)
        return item.text.strip() if item is not None and item.text else default

    file_port = int(root_text("FilePort", "7707"))
    return {
        "host": text("IpAddress"),
        "sdk_port": int(text("Port", root_text("SdkPort", "7711"))),
        "file_port": file_port,
        "api_port": file_port + 5,
        "username": text("UserName"),
        "password": text("Password"),
        "ssl": text("isSSL", "false").lower() == "true",
    }


def newest_logs(limit: int = 4) -> list[Path]:
    if not LOG_DIR.exists():
        return []
    logs = [p for p in LOG_DIR.rglob("*") if p.is_file() and p.suffix.lower() in {".log", ".txt"}]
    return sorted(logs, key=lambda p: p.stat().st_mtime, reverse=True)[:limit]


def read_recent_logs() -> str:
    chunks: list[str] = []
    for path in newest_logs():
        try:
            chunks.append(path.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            continue
    return "\n".join(chunks)


def _ws_read_exact(sock: socket.socket, buffer: bytearray, size: int) -> bytes:
    while len(buffer) < size:
        chunk = sock.recv(max(4096, size - len(buffer)))
        if not chunk:
            raise MCS8Error("MCS8 WebSocket connection closed.")
        buffer.extend(chunk)
    data = bytes(buffer[:size])
    del buffer[:size]
    return data


def _ws_read_frame(sock: socket.socket, buffer: bytearray) -> tuple[int, bytes]:
    head = _ws_read_exact(sock, buffer, 2)
    opcode = head[0] & 0x0F
    masked = bool(head[1] & 0x80)
    length = head[1] & 0x7F
    if length == 126:
        length = struct.unpack("!H", _ws_read_exact(sock, buffer, 2))[0]
    elif length == 127:
        length = struct.unpack("!Q", _ws_read_exact(sock, buffer, 8))[0]
    mask = _ws_read_exact(sock, buffer, 4) if masked else b""
    payload = _ws_read_exact(sock, buffer, length) if length else b""
    if masked:
        payload = bytes(payload[i] ^ mask[i % 4] for i in range(len(payload)))
    return opcode, payload


def _ws_send_frame(sock: socket.socket, opcode: int, payload: bytes = b"") -> None:
    mask = os.urandom(4)
    header = bytearray([0x80 | opcode])
    length = len(payload)
    if length < 126:
        header.append(0x80 | length)
    elif length < 65536:
        header.append(0x80 | 126)
        header.extend(struct.pack("!H", length))
    else:
        header.append(0x80 | 127)
        header.extend(struct.pack("!Q", length))
    header.extend(mask)
    body = bytes(payload[i] ^ mask[i % 4] for i in range(len(payload)))
    sock.sendall(bytes(header) + body)


def mcs8_ws_login(username: str, password: str) -> dict[str, Any]:
    username = username.strip()
    if not username or not password:
        raise MCS8Error("Username and password are required.")
    cfg = local_config()
    host = cfg["host"]
    port = int(cfg["sdk_port"])
    pwd_md5 = hashlib.md5(password.encode("utf-8")).hexdigest()
    ws_key = base64.b64encode(os.urandom(16)).decode("ascii")
    path = f"/?uid={urllib.parse.quote(username)}&pwd={pwd_md5}"
    request = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {ws_key}\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        "Sec-WebSocket-Protocol: protoo\r\n"
        "Origin: http://aee.jdcloud.com\r\n"
        "User-Agent: JD-Air-WebPanel/1.0\r\n"
        "\r\n"
    ).encode("utf-8")

    with socket.create_connection((host, port), timeout=12) as sock:
        sock.settimeout(2.0)
        sock.sendall(request)
        raw = bytearray()
        deadline = time.time() + 12
        while b"\r\n\r\n" not in raw:
            if time.time() > deadline:
                raise MCS8Error("MCS8 WebSocket handshake timed out.")
            chunk = sock.recv(4096)
            if not chunk:
                raise MCS8Error("MCS8 WebSocket handshake failed.")
            raw.extend(chunk)
        header_raw, rest = bytes(raw).split(b"\r\n\r\n", 1)
        status_line = header_raw.split(b"\r\n", 1)[0].decode("latin1", "replace")
        if " 101 " not in status_line:
            raise MCS8Error(f"MCS8 login failed: {status_line}")

        buffer = bytearray(rest)
        connect_info: dict[str, Any] | None = None
        while time.time() < deadline:
            try:
                opcode, payload = _ws_read_frame(sock, buffer)
            except socket.timeout:
                continue
            if opcode == 8:
                break
            if opcode == 9:
                _ws_send_frame(sock, 10, payload)
                continue
            if opcode != 1:
                continue
            try:
                message = json.loads(payload.decode("utf-8", "replace"))
            except json.JSONDecodeError:
                continue
            if message.get("notification") and message.get("method") == "ConnecteInfo":
                data = message.get("data")
                if isinstance(data, dict):
                    connect_info = data
                    break
            if message.get("response") and message.get("ok") is False:
                raise MCS8Error(str(message.get("errorReason") or message.get("error") or "MCS8 login failed."))

        if not connect_info:
            raise MCS8Error("MCS8 login succeeded but ConnecteInfo was not received.")
        token = connect_info.get("token") or connect_info.get("SessionId") or connect_info.get("sessionId")
        if not token:
            raise MCS8Error("MCS8 login did not return a token.")
        return {
            "username": username,
            "token": str(token),
            "connectInfo": connect_info,
            "server": {"host": host, "sdk_port": port, "api_port": cfg["api_port"], "file_port": cfg["file_port"]},
        }


def _session_public(session: dict[str, Any]) -> dict[str, Any]:
    info = session.get("connectInfo") or {}
    return {
        "authenticated": True,
        "username": session.get("username", ""),
        "loginAt": session.get("loginAt", ""),
        "lastSeen": session.get("lastSeen", ""),
        "server": session.get("server", {}),
        "defaultGroup": info.get("defaultGroup"),
        "groupId": info.get("groupId"),
        "userType": info.get("userType"),
        "media": {
            "mediaIp": info.get("mediaIp"),
            "mediaPort": info.get("mediaPort"),
            "mediaSslPort": info.get("mediaSslPort"),
            "mediaDomain": info.get("mediaDomain"),
        },
        "hasToken": bool(session.get("token")),
        "hasOss": isinstance(info.get("ossServer"), dict),
    }


def create_auth_session(login_result: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    sid = secrets.token_urlsafe(32)
    now = dt.datetime.now().isoformat(timespec="seconds")
    session = {
        "id": sid,
        "username": login_result["username"],
        "token": login_result["token"],
        "connectInfo": login_result.get("connectInfo") or {},
        "server": login_result.get("server") or {},
        "loginAt": now,
        "lastSeen": now,
        "expiresAt": time.time() + SESSION_TTL_SECONDS,
    }
    with AUTH_SESSIONS_LOCK:
        AUTH_SESSIONS[sid] = session
    return sid, session


def get_auth_session(sid: str | None, touch: bool = True) -> dict[str, Any] | None:
    if not sid:
        return None
    with AUTH_SESSIONS_LOCK:
        session = AUTH_SESSIONS.get(sid)
        if not session:
            return None
        if time.time() > float(session.get("expiresAt") or 0):
            AUTH_SESSIONS.pop(sid, None)
            return None
        if touch:
            session["lastSeen"] = dt.datetime.now().isoformat(timespec="seconds")
            session["expiresAt"] = time.time() + SESSION_TTL_SECONDS
        return session


def request_auth_session() -> dict[str, Any] | None:
    return getattr(REQUEST_CONTEXT, "auth_session", None)


def auth_session_token(session_token: str | None = None) -> str | None:
    if session_token:
        return session_token
    session = request_auth_session()
    if session and session.get("token"):
        return str(session["token"])
    return None


def current_session() -> str:
    token = auth_session_token()
    if token:
        return token
    text = read_recent_logs()
    for pattern in (
        r"SessionId=([0-9a-fA-F]+)",
        r'"token"\s*:\s*"([0-9a-fA-F]+)"',
        r'"SessionId"\s*:\s*"([0-9a-fA-F]+)"',
    ):
        matches = re.findall(pattern, text)
        if matches:
            return matches[-1]
    raise MCS8Error("No active MCS8 session was found in logs. Start and log in with MCS8Client.exe once, then refresh.")


def oss_config() -> dict[str, str]:
    session = request_auth_session()
    info = (session or {}).get("connectInfo") or {}
    oss = info.get("ossServer")
    if isinstance(oss, dict):
        access_key = oss.get("accessKey")
        access_secret = oss.get("accessSecret")
        endpoint = oss.get("endPoint") or oss.get("endpoint")
        bucket = oss.get("bucket")
        if access_key and access_secret and endpoint and bucket:
            return {
                "access_key": str(access_key),
                "access_secret": str(access_secret),
                "endpoint": str(endpoint),
                "bucket": str(bucket),
            }
    text = read_recent_logs()
    patterns = {
        "access_key": r'"accessKey"\s*:\s*"([^"]+)"',
        "access_secret": r'"accessSecret"\s*:\s*"([^"]+)"',
        "endpoint": r'"endPoint"\s*:\s*"([^"]+)"',
        "bucket": r'"bucket"\s*:\s*"([^"]+)"',
    }
    result: dict[str, str] = {}
    for key, pattern in patterns.items():
        matches = re.findall(pattern, text)
        if not matches:
            raise MCS8Error("OSS playback configuration was not found in logs. Query records in the desktop client once.")
        result[key] = matches[-1]
    return result


def api_base() -> str:
    cfg = local_config()
    scheme = "https" if cfg["ssl"] else "http"
    return f"{scheme}://{cfg['host']}:{cfg['api_port']}"


def call_mcs8_api(path: str, params: dict[str, str], require_session: bool = True, session_token: str | None = None) -> dict[str, Any]:
    params = dict(params)
    headers = {"User-Agent": "MCS8WebPanel/1.0"}
    if require_session:
        session = auth_session_token(session_token) or current_session()
        params.setdefault("SessionId", session)
        headers["token"] = session
    url = f"{api_base()}{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="ignore")
        raise MCS8Error(f"Remote API HTTP {exc.code}: {raw[:300]}") from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MCS8Error(f"Remote API returned non-JSON data: {raw[:300]}") from exc


def latest_online_devices() -> list[dict[str, Any]]:
    if auth_session_token():
        return []
    text = read_recent_logs()
    matches = re.findall(r'"method"\s*:\s*"allDevOnline"\s*,\s*"data"\s*:\s*(\[.*?\])', text)
    if not matches:
        return []
    try:
        return json.loads(matches[-1])
    except json.JSONDecodeError:
        return []


def latest_status_map() -> dict[str, int]:
    if auth_session_token():
        return {}
    text = read_recent_logs()
    status: dict[str, int] = {}
    for match in re.findall(r'"method"\s*:\s*"DeviceStatus"\s*,\s*"data"\s*:\s*(\{.*?\})', text):
        try:
            payload = json.loads(match)
        except json.JSONDecodeError:
            continue
        for item in payload.get("Content", []):
            dev_id = item.get("DevId")
            if dev_id is not None and "Status" in item:
                status[str(dev_id)] = int(item["Status"])
    return status


def latest_gps_map() -> dict[str, dict[str, Any]]:
    if auth_session_token():
        return {}
    text = read_recent_logs()
    gps: dict[str, dict[str, Any]] = {}
    for match in re.findall(r'"method"\s*:\s*"gpsUpload"\s*,\s*"data"\s*:\s*(\{.*?\})', text):
        try:
            payload = json.loads(match)
        except json.JSONDecodeError:
            continue
        dev_id = payload.get("devId")
        if dev_id:
            gps[str(dev_id)] = payload
    for match in re.findall(r'"method"\s*:\s*"gpsUploadList"\s*,\s*"data"\s*:\s*(\[.*?\])', text):
        try:
            rows = json.loads(match)
        except json.JSONDecodeError:
            continue
        for payload in rows:
            dev_id = payload.get("devId")
            if dev_id:
                gps[str(dev_id)] = payload
    return gps


def valid_coord(lat: Any, lng: Any) -> bool:
    try:
        lat_f = float(lat)
        lng_f = float(lng)
    except (TypeError, ValueError):
        return False
    return -90 <= lat_f <= 90 and -180 <= lng_f <= 180 and not (abs(lat_f) < 0.000001 and abs(lng_f) < 0.000001)


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# Offline geo lookup using city boundary polygons
OFFLINE_GEO_DIR = WEB_DIR / "offline_geo"
_geo_lookup = OfflineGeoLookup(OFFLINE_GEO_DIR / "city_geo_lite_0p005.json.gz")
_gps_city_cache: dict[tuple[float, float], dict[str, Any]] = {}

def get_city_by_gps(lon: float, lat: float) -> dict[str, Any]:
    key = (round(lon, 4), round(lat, 4))
    if key in _gps_city_cache:
        return _gps_city_cache[key]
    result = {"city": "", "distanceKm": None}
    try:
        if not (73.66 < lon < 135.05 and 3.86 < lat < 53.55):
            pass  # outside China
        else:
            geo = _geo_lookup.lookup(lon, lat, coord_type="wgs84")
            if geo:
                result = {"city": geo.get("city", "").rstrip("市"), "distanceKm": 0}
    except Exception:
        pass
    _gps_city_cache[key] = result
    return result

def latest_seen_map() -> dict[str, str]:
    if auth_session_token():
        return {}
    text = read_recent_logs()
    seen: dict[str, str] = {}
    for line in text.splitlines():
        ts_match = re.search(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
        if not ts_match:
            continue
        ts = ts_match.group(1)
        for dev_id in re.findall(r'"(?:devId|DevId|szIDNO)"\s*:\s*"([^"]+)"', line):
            if dev_id:
                seen[str(dev_id)] = ts
        for dev_id in re.findall(r'"DevId"\s*:\s*([0-9A-Za-z_.-]+)', line):
            if dev_id:
                seen[str(dev_id)] = ts
    return seen


def room_to_group(room_id: str) -> tuple[str, str]:
    match = re.match(r"^\d+_(\d+)_(\d+)$", room_id or "")
    if match:
        return match.group(1), match.group(2)
    return "5", room_id


def load_device_catalog_file() -> dict[str, dict[str, Any]]:
    try:
        payload = json.loads(DEVICE_CATALOG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    rows = payload.get("devices") if isinstance(payload, dict) else None
    if not isinstance(rows, dict):
        return {}
    return {str(k): v for k, v in rows.items() if isinstance(v, dict)}


def save_device_catalog_file(catalog: dict[str, dict[str, Any]]) -> None:
    if not catalog:
        return
    payload = {"savedAt": dt.datetime.now().isoformat(timespec="seconds"), "devices": catalog}
    tmp = DEVICE_CATALOG_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp.replace(DEVICE_CATALOG_FILE)


def export_device_catalog_from_sdk() -> dict[str, dict[str, Any]]:
    # SDK export removed
    return {}


def device_catalog() -> dict[str, dict[str, Any]]:
    global DEVICE_CATALOG_CACHE
    now = time.time()
    if DEVICE_CATALOG_CACHE and now - DEVICE_CATALOG_CACHE[0] < DEVICE_CATALOG_TTL:
        return DEVICE_CATALOG_CACHE[1]

    catalog: dict[str, dict[str, Any]] = {}
    api_ok = False
    rows = None
    for attempt in range(2):
        try:
            rows = call_mcs8_api("/api/GetDevListByGroupId", {"groupType": "0", "groupId": "0"})
            api_ok = True
            break
        except Exception:
            if attempt == 0:
                time.sleep(0.5)
    if isinstance(rows, list):
        for row in rows:
            dev_id = str(row.get("szIDNO") or row.get("devId") or row.get("DevId") or "")
            if dev_id:
                catalog[dev_id] = row

    # Keep special devices that appear only in the online feed, such as admin RTSP/GB28181 entries.
    for item in latest_online_devices():
        dev_id = str(item.get("devId") or item.get("DevId") or item.get("szIDNO") or "")
        if dev_id and dev_id not in catalog:
            catalog[dev_id] = dict(item)

    if api_ok and catalog:
        DEVICE_CATALOG_CACHE = (now, catalog)
        save_device_catalog_file(catalog)
    elif not catalog:
        catalog = export_device_catalog_from_sdk()
        if catalog:
            DEVICE_CATALOG_CACHE = (now, catalog)
            save_device_catalog_file(catalog)
        else:
            catalog = load_device_catalog_file()
            if catalog:
                DEVICE_CATALOG_CACHE = (now, catalog)
    return catalog



def recent_gps_cities(catalog: dict[str, dict[str, Any]] | None = None) -> dict[str, list[dict[str, Any]]]:
    """Return per-device unique cities sorted by latest time desc.
    Authenticated sessions query MCS8 GPS API directly; legacy mode falls back to logs.
    """
    token = auth_session_token()
    if token and catalog:
        cache_key = hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]
        cached = RECENT_GPS_CITIES_CACHE.get(cache_key)
        now = time.time()
        if cached and now - cached[0] < RECENT_GPS_CITIES_TTL:
            return cached[1]

        with RECENT_GPS_CITIES_LOCK:
            should_start = cache_key not in RECENT_GPS_CITIES_INFLIGHT
            if should_start:
                RECENT_GPS_CITIES_INFLIGHT.add(cache_key)

        if should_start:
            catalog_snapshot = {str(k): dict(v) for k, v in catalog.items()}
            token_snapshot = token

            def warm_recent_gps_cities() -> None:
                try:
                    end = dt.datetime.now()
                    start = end - dt.timedelta(days=3)
                    st = start.strftime("%Y-%m-%d %H:%M:%S")
                    et = end.strftime("%Y-%m-%d %H:%M:%S")
                    targets: list[str] = []
                    for dev_id, meta in catalog_snapshot.items():
                        group_id = str(meta.get("groupId") or meta.get("GroupId") or meta.get("roomId") or "")
                        device_name = str(meta.get("deviceName") or meta.get("szName") or meta.get("DeviceName") or meta.get("name") or "")
                        if group_id == "30000002" and device_name.upper().startswith("JDTY"):
                            targets.append(str(dev_id))

                    def rows_from_payload_bg(payload: Any) -> list[dict[str, Any]]:
                        if isinstance(payload, list):
                            return [row for row in payload if isinstance(row, dict)]
                        if isinstance(payload, dict):
                            for key in ("data", "list", "rows", "Content", "content"):
                                value = payload.get(key)
                                if isinstance(value, list):
                                    return [row for row in value if isinstance(row, dict)]
                            for value in payload.values():
                                if isinstance(value, list):
                                    return [row for row in value if isinstance(row, dict)]
                        return []

                    def query_device_bg(dev_id: str) -> tuple[str, list[dict[str, Any]]]:
                        try:
                            payload = call_mcs8_api(
                                "/api/GetGpsModelList",
                                {"st": st, "et": et, "devId": dev_id, "page": "1", "pagesize": "1000"},
                                session_token=token_snapshot,
                            )
                            return dev_id, rows_from_payload_bg(payload)
                        except Exception:
                            return dev_id, []

                    result_bg: dict[str, list[dict[str, Any]]] = {}
                    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                        futures = [executor.submit(query_device_bg, dev_id) for dev_id in targets]
                        for future in concurrent.futures.as_completed(futures):
                            dev_id, rows = future.result()
                            city_times: dict[str, str] = {}
                            for item in rows:
                                lng = item.get("lng") or item.get("longitude") or item.get("nJingDu")
                                lat = item.get("lat") or item.get("latitude") or item.get("nWeiDu")
                                ts = str(item.get("gpsTime") or item.get("dateTime") or item.get("time") or "")
                                if lng is None or lat is None:
                                    continue
                                try:
                                    city_info = get_city_by_gps(float(lng), float(lat))
                                except (TypeError, ValueError):
                                    continue
                                city_name = city_info.get("city") if city_info else ""
                                if city_name and (city_name not in city_times or ts > city_times[city_name]):
                                    city_times[city_name] = ts
                            if city_times:
                                result_bg[dev_id] = [{"city": city, "time": ts} for city, ts in sorted(city_times.items(), key=lambda x: x[1], reverse=True)]
                    RECENT_GPS_CITIES_CACHE[cache_key] = (time.time(), result_bg)
                finally:
                    with RECENT_GPS_CITIES_LOCK:
                        RECENT_GPS_CITIES_INFLIGHT.discard(cache_key)

            threading.Thread(target=warm_recent_gps_cities, name="mcs8-recent-gps-cities", daemon=True).start()

        return {}

        end = dt.datetime.now()
        start = end - dt.timedelta(days=3)
        st = start.strftime("%Y-%m-%d %H:%M:%S")
        et = end.strftime("%Y-%m-%d %H:%M:%S")
        targets: list[str] = []
        for dev_id, meta in catalog.items():
            group_id = str(meta.get("groupId") or meta.get("GroupId") or meta.get("roomId") or "")
            device_name = str(meta.get("deviceName") or meta.get("szName") or meta.get("DeviceName") or meta.get("name") or "")
            if group_id == "30000002" and device_name.upper().startswith("JDTY"):
                targets.append(str(dev_id))

        def rows_from_payload(payload: Any) -> list[dict[str, Any]]:
            if isinstance(payload, list):
                return [row for row in payload if isinstance(row, dict)]
            if isinstance(payload, dict):
                for key in ("data", "list", "rows", "Content", "content"):
                    value = payload.get(key)
                    if isinstance(value, list):
                        return [row for row in value if isinstance(row, dict)]
                for value in payload.values():
                    if isinstance(value, list):
                        return [row for row in value if isinstance(row, dict)]
            return []

        def query_device(dev_id: str) -> tuple[str, list[dict[str, Any]]]:
            try:
                payload = call_mcs8_api(
                    "/api/GetGpsModelList",
                    {"st": st, "et": et, "devId": dev_id, "page": "1", "pagesize": "1000"},
                    session_token=token,
                )
                return dev_id, rows_from_payload(payload)
            except Exception:
                return dev_id, []

        result: dict[str, list[dict[str, Any]]] = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(query_device, dev_id) for dev_id in targets]
            for future in concurrent.futures.as_completed(futures):
                dev_id, rows = future.result()
                city_times: dict[str, str] = {}
                for item in rows:
                    lng = item.get("lng") or item.get("longitude") or item.get("nJingDu")
                    lat = item.get("lat") or item.get("latitude") or item.get("nWeiDu")
                    ts = str(item.get("gpsTime") or item.get("dateTime") or item.get("time") or "")
                    if lng is None or lat is None:
                        continue
                    try:
                        city_info = get_city_by_gps(float(lng), float(lat))
                    except (TypeError, ValueError):
                        continue
                    city_name = city_info.get("city") if city_info else ""
                    if city_name and (city_name not in city_times or ts > city_times[city_name]):
                        city_times[city_name] = ts
                if city_times:
                    result[dev_id] = [{"city": city, "time": ts} for city, ts in sorted(city_times.items(), key=lambda x: x[1], reverse=True)]
        RECENT_GPS_CITIES_CACHE[cache_key] = (now, result)
        return result

    """Parse recent GPS uploads from logs,
    return per-device list of unique cities sorted by latest time desc."""
    text = read_recent_logs()
    raw: dict[str, list[tuple[float, float, str]]] = {}
    for match in re.finditer(r'"method"\s*:\s*"gpsUpload"\s*,\s*"data"\s*:\s*(\{.*?\})', text):
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        for item in payload if isinstance(payload, list) else [payload]:
            dev_id = item.get("devId") or item.get("DevId") or ""
            lng = item.get("lng") or item.get("nJingDu")
            lat = item.get("lat") or item.get("nWeiDu")
            ts = item.get("gpsTime") or item.get("time") or ""
            if dev_id and lng is not None and lat is not None:
                try:
                    raw.setdefault(str(dev_id), []).append((round(float(lng), 4), round(float(lat), 4), str(ts)))
                except (ValueError, TypeError):
                    pass

    result: dict[str, list[dict[str, Any]]] = {}
    for dev_id, points in raw.items():
        seen: dict[tuple[float, float], str] = {}
        for lng, lat, ts in points:
            coord = (lng, lat)
            if coord not in seen or ts > seen[coord]:
                seen[coord] = ts
        city_times: dict[str, str] = {}
        for (lng, lat), ts in seen.items():
            city_info = get_city_by_gps(lng, lat)
            if city_info and city_info.get("city"):
                city_name = city_info["city"]
                if city_name not in city_times or ts > city_times[city_name]:
                    city_times[city_name] = ts
        sorted_cities = sorted(city_times.items(), key=lambda x: x[1], reverse=True)
        result[dev_id] = [{"city": city, "time": time} for city, time in sorted_cities]
    return result



def merged_devices() -> list[dict[str, Any]]:
    status = latest_status_map()
    gps = latest_gps_map()
    seen = latest_seen_map()
    catalog = device_catalog()
    recent_cities_map = recent_gps_cities(catalog)
    tool_warehouses = load_tool_warehouses()
    devices = []
    for dev_id, meta in sorted(catalog.items(), key=lambda item: item[0]):
        group_id = str(meta.get("groupId") or meta.get("GroupId") or meta.get("roomId") or "")
        group_name = str(meta.get("groupName") or meta.get("GroupName") or GROUP_NAMES.get(group_id) or group_id or "未分组")
        device_name = meta.get("deviceName") or meta.get("szName") or meta.get("DeviceName", "") or meta.get("name", "")
        # Only include 维修部 (group_id=30000002) devices with JDTY prefix
        if group_id != "30000002" or not str(device_name).upper().startswith("JDTY"):
            continue
        latest_gps = gps.get(dev_id, {})
        lng = latest_gps.get("lng", meta.get("nJingDu", meta.get("lng")))
        lat = latest_gps.get("lat", meta.get("nWeiDu", meta.get("lat")))
        city = get_city_by_gps(lng, lat)
        online_default = int(meta.get("nOnline", meta.get("online", 0)) or 0)
        devices.append(
            {
                "roomId": meta.get("roomId") or (f"20000000_3_{group_id}" if group_id.isdigit() else group_id),
                "groupName": group_name,
                "name": device_name,
                "devId": dev_id,
                "online": status.get(dev_id, online_default) == 1,
                "lng": lng,
                "lat": lat,
                "gpsTime": latest_gps.get("gpsTime") or meta.get("gpsTime"),
                "lastOnlineTime": seen.get(dev_id) or latest_gps.get("gpsTime") or meta.get("gpsTime") or "",
                "city": city["city"],
                "cityDistanceKm": city["distanceKm"],
                "recentCities": recent_cities_map.get(dev_id, []),
                "warehouse": tool_warehouses.get(device_name, ""),
                "catalog": meta,
            }
        )
    return devices


def system_summary() -> dict[str, Any]:
    devices = merged_devices()
    groups: dict[str, dict[str, Any]] = {}
    mapped = 0
    for dev in devices:
        group = dev.get("groupName") or "未分组"
        bucket = groups.setdefault(str(group), {"name": group, "total": 0, "online": 0})
        bucket["total"] += 1
        if dev.get("online"):
            bucket["online"] += 1
        if dev.get("lng") is not None and dev.get("lat") is not None:
            mapped += 1
    return {
        "devices": {"total": len(devices), "online": sum(1 for d in devices if d.get("online")), "mapped": mapped},
        "groups": sorted(groups.values(), key=lambda g: str(g["name"])),
    }


def record_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("data", "Content", "content", "rows", "list"):
        rows = payload.get(key)
        if isinstance(rows, list):
            return [r for r in rows if isinstance(r, dict)]
    return []


def record_total(payload: Any, fallback: int) -> int:
    if isinstance(payload, dict):
        for key in ("recordsTotal", "recordsFiltered", "total", "Total", "count"):
            try:
                return int(payload.get(key))
            except (TypeError, ValueError):
                pass
    return fallback


def record_time_key(row: dict[str, Any]) -> str:
    return str(row.get("startTime") or row.get("fileTime") or row.get("beginTime") or row.get("uploadTime") or row.get("upLoadTime") or "")


def device_city_names(device: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    current = str(device.get("city") or "").strip()
    if current:
        names.add(current)
    for row in device.get("recentCities") or []:
        city = str(row.get("city") or "").strip()
        if city:
            names.add(city)
    return names


def call_record_page(params: dict[str, str]) -> dict[str, Any]:
    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            return call_mcs8_api("/api/GetRecordFileList", params)
        except Exception as exc:
            last_exc = exc
            if attempt == 0:
                time.sleep(0.5)
    raise last_exc or MCS8Error("record query failed")


def query_records(st: str, et: str, q: str, page: int, page_size: int, mode: str = "platform", city: str = "") -> dict[str, Any]:
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    base_params = {"st": st, "et": et, "lt": "-1"}
    devices = merged_devices()
    by_id = {str(d.get("devId", "")): d for d in devices}
    needle = q.strip().lower()
    city = city.strip()
    city_device_ids = {
        str(d.get("devId") or "")
        for d in devices
        if city and city in device_city_names(d) and d.get("devId")
    }
    city_devices = [d for d in devices if str(d.get("devId") or "") in city_device_ids]

    def enrich_row(row: dict[str, Any]) -> dict[str, Any]:
        row_dev = str(row.get("devId") or row.get("DevId") or row.get("szIDNO") or "")
        row_name = str(row.get("deviceName") or row.get("devName") or by_id.get(row_dev, {}).get("name", ""))
        row["devId"] = row_dev
        if row_name:
            row["deviceName"] = row_name
        return row

    if city and not needle:
        direct_ids = sorted(city_device_ids)
        all_rows: list[dict[str, Any]] = []
        partial = False

        def fetch_device_records(device_id: str) -> tuple[list[dict[str, Any]], bool]:
            rows: list[dict[str, Any]] = []
            try:
                first = call_record_page({**base_params, "did": device_id, "page": "1", "pagesize": "100"})
            except Exception:
                return rows, True
            rows.extend(record_rows(first))
            total = record_total(first, len(rows))
            remote_pages = max(1, min(20, math.ceil(total / 100)))
            failed = False
            for remote_page in range(2, remote_pages + 1):
                try:
                    payload = call_record_page(
                        {**base_params, "did": device_id, "page": str(remote_page), "pagesize": "100"}
                    )
                except Exception:
                    failed = True
                    break
                rows.extend(record_rows(payload))
            return rows, failed

        if direct_ids:
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, max(1, len(direct_ids)))) as executor:
                futures = [executor.submit(fetch_device_records, device_id) for device_id in direct_ids]
                for future in concurrent.futures.as_completed(futures):
                    rows, failed = future.result()
                    all_rows.extend(rows)
                    partial = partial or failed

        merged: list[dict[str, Any]] = []
        for row in all_rows:
            row = enrich_row(dict(row))
            row_dev = str(row.get("devId") or "")
            if row_dev in city_device_ids:
                merged.append(row)

        merged.sort(key=record_time_key, reverse=True)
        start = (page - 1) * page_size
        return {
            "data": merged[start:start + page_size],
            "recordsTotal": len(merged),
            "pages": max(1, math.ceil(len(merged) / page_size)),
            "page": page,
            "pageSize": page_size,
            "matchedDevices": [{"devId": str(d.get("devId") or ""), "name": d.get("name", "")} for d in city_devices],
            "matchLimit": len(city_devices),
            "partial": partial,
            "city": city,
            "source": "platform",
            "requestedMode": mode,
            "deviceFileSupported": False,
        }

    if not needle:
        try:
            payload = call_record_page({**base_params, "page": str(page), "pagesize": str(page_size)})
            rows = [enrich_row(dict(row)) for row in record_rows(payload)]
            total = record_total(payload, len(rows))
        except Exception:
            rows = []
            total = 0
        if city:
            matched = [r for r in rows if str(r.get("devId") or r.get("DevId") or r.get("szIDNO") or "") in by_id and by_id.get(str(r.get("devId") or r.get("DevId") or r.get("szIDNO") or ""), {}).get("city", "") == city]
            rows = matched
            total = len(matched)
        return {
            "data": rows,
            "recordsTotal": total,
            "pages": max(1, math.ceil(total / page_size)),
            "page": page,
            "pageSize": page_size,
            "matchedDevices": [],
            "city": city,
            "source": "platform",
            "requestedMode": mode,
            "deviceFileSupported": False,
        }

    matches = [
        d for d in devices
        if needle in str(d.get("devId", "")).lower()
        or needle in str(d.get("name", "")).lower()
        or needle in str(d.get("groupName", "")).lower()
    ]
    if city:
        matches = [d for d in matches if str(d.get("devId") or "") in city_device_ids]
    exact = by_id.get(q.strip())
    if exact and exact not in matches and (not city or str(exact.get("devId") or "") in city_device_ids):
        matches.insert(0, exact)

    match_ids = {str(d.get("devId") or "") for d in matches}
    matched_devices = [{"devId": str(d.get("devId") or ""), "name": d.get("name", "")} for d in matches]
    if not matches and q.strip() and not city:
        match_ids.add(q.strip())
        matched_devices = [{"devId": q.strip(), "name": ""}]

    # The remote API honors `did` but group/name parameters are unreliable.
    # Query each matched device directly so a busy group cannot push another
    # group's records outside the global pagination window.
    direct_ids = sorted(match_ids)
    all_rows: list[dict[str, Any]] = []
    partial = False

    def fetch_device_records(device_id: str) -> tuple[list[dict[str, Any]], bool]:
        rows: list[dict[str, Any]] = []
        try:
            first = call_record_page({**base_params, "did": device_id, "page": "1", "pagesize": "100"})
        except Exception:
            return rows, True
        rows.extend(record_rows(first))
        total = record_total(first, len(rows))
        remote_pages = max(1, min(20, math.ceil(total / 100)))
        failed = False
        for remote_page in range(2, remote_pages + 1):
            try:
                payload = call_record_page(
                    {**base_params, "did": device_id, "page": str(remote_page), "pagesize": "100"}
                )
            except Exception:
                failed = True
                break
            rows.extend(record_rows(payload))
        return rows, failed

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, max(1, len(direct_ids)))) as executor:
        futures = [executor.submit(fetch_device_records, device_id) for device_id in direct_ids]
        for future in concurrent.futures.as_completed(futures):
            rows, failed = future.result()
            all_rows.extend(rows)
            partial = partial or failed

    merged: list[dict[str, Any]] = []
    for row in all_rows:
        row = enrich_row(dict(row))
        row_dev = str(row.get("devId") or "")
        row_name = str(row.get("deviceName") or row.get("devName") or "")
        hay = f"{row_dev} {row_name}".lower()
        if row_dev in match_ids or needle in hay:
            merged.append(row)

    merged.sort(key=record_time_key, reverse=True)
    start = (page - 1) * page_size
    return {
        "data": merged[start:start + page_size],
        "recordsTotal": len(merged),
        "pages": max(1, math.ceil(len(merged) / page_size)),
        "page": page,
        "pageSize": page_size,
        "matchedDevices": matched_devices,
        "matchLimit": len(matched_devices),
        "partial": partial,
        "source": "platform",
        "requestedMode": mode,
        "deviceFileSupported": False,
    }


def query_gps_track(dev_id: str, st: str, et: str, max_points: int = 2000) -> dict[str, Any]:
    dev_id = dev_id.strip()
    if not dev_id:
        raise MCS8Error("Device ID is required for GPS track query.")
    max_points = max(100, min(max_points, 5000))
    payload = call_mcs8_api(
        "/api/GetGpsModelList",
        {"st": st, "et": et, "devId": dev_id, "page": "1", "pagesize": "5000"},
    )
    points: list[dict[str, Any]] = []
    for row in record_rows(payload):
        lat = row.get("lat", row.get("latitude"))
        lng = row.get("lng", row.get("longitude"))
        if not valid_coord(lat, lng):
            continue
        points.append(
            {
                "lat": float(lat),
                "lng": float(lng),
                "time": str(row.get("gpsTime") or row.get("dateTime") or row.get("time") or ""),
                "speed": float(row.get("speed") or 0),
                "direct": float(row.get("direct") or row.get("direction") or 0),
                "accuracy": float(row.get("accuracy") or 0),
                "battery": row.get("battery"),
                "gpsType": row.get("gpsType"),
                "networkType": row.get("netWorkType"),
            }
        )
    points.sort(key=lambda point: point["time"])
    source_count = len(points)
    if len(points) > max_points:
        step = (len(points) - 1) / (max_points - 1)
        points = [points[round(index * step)] for index in range(max_points)]

    distance_km = 0.0
    for previous, current in zip(points, points[1:]):
        segment = haversine_km(previous["lat"], previous["lng"], current["lat"], current["lng"])
        if segment <= 20:
            distance_km += segment
    devices = {str(item.get("devId") or ""): item for item in merged_devices()}
    device = devices.get(dev_id, {})
    return {
        "devId": dev_id,
        "deviceName": device.get("name", ""),
        "points": points,
        "sourceCount": source_count,
        "pointCount": len(points),
        "distanceKm": round(distance_km, 2),
        "maxSpeed": round(max((point["speed"] for point in points), default=0.0), 1),
        "startTime": points[0]["time"] if points else "",
        "endTime": points[-1]["time"] if points else "",
        "recordsTotal": record_total(payload, source_count),
    }


def presign_oss_url(key: str, expires: int = 900) -> str:
    if key.startswith("/"):
        cfg = local_config()
        scheme = "https" if cfg["ssl"] else "http"
        return f"{scheme}://{cfg['host']}:{cfg['file_port']}{key}"
    cfg = oss_config()
    endpoint = cfg["endpoint"]
    bucket = cfg["bucket"]
    region = endpoint.split(".")[1] if endpoint.startswith("s3.") and "." in endpoint else "cn-north-1"
    host = f"{bucket}.{endpoint}"
    now = dt.datetime.now(dt.UTC)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    datestamp = now.strftime("%Y%m%d")
    credential = f"{cfg['access_key']}/{datestamp}/{region}/s3/aws4_request"
    params = {
        "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
        "X-Amz-Credential": credential,
        "X-Amz-Date": amz_date,
        "X-Amz-Expires": str(expires),
        "X-Amz-SignedHeaders": "host",
    }
    canonical_uri = "/" + urllib.parse.quote(key, safe="/")
    canonical_query = "&".join(
        urllib.parse.quote(k, safe="") + "=" + urllib.parse.quote(v, safe="")
        for k, v in sorted(params.items())
    )
    canonical_request = "\n".join(["GET", canonical_uri, canonical_query, f"host:{host}\n", "host", "UNSIGNED-PAYLOAD"])
    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            amz_date,
            f"{datestamp}/{region}/s3/aws4_request",
            hashlib.sha256(canonical_request.encode()).hexdigest(),
        ]
    )

    def sign(key_bytes: bytes, msg: str) -> bytes:
        return hmac.new(key_bytes, msg.encode(), hashlib.sha256).digest()

    signing_key = sign(
        sign(sign(sign(("AWS4" + cfg["access_secret"]).encode(), datestamp), region), "s3"),
        "aws4_request",
    )
    signature = hmac.new(signing_key, string_to_sign.encode(), hashlib.sha256).hexdigest()
    return f"https://{host}{canonical_uri}?{canonical_query}&X-Amz-Signature={signature}"


def video_stream_info(key: str) -> dict[str, Any]:
    with _video_info_lock:
        cached = _video_info_cache.get(key)
    if cached is not None:
        return cached

    result: dict[str, Any] = {
        "key": key,
        "videoCodec": "",
        "audioCodec": "",
        "width": 0,
        "height": 0,
        "needsTranscode": False,
    }
    if not FFMPEG_PATH.exists() or not FFPROBE_PATH.exists():
        return result

    proc = subprocess.run(
        [
            str(FFPROBE_PATH),
            "-v", "error",
            "-show_entries", "stream=codec_type,codec_name,width,height",
            "-of", "json",
            presign_oss_url(key),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if proc.returncode == 0:
        payload = json.loads(proc.stdout or "{}")
        for stream in payload.get("streams", []):
            if stream.get("codec_type") == "video":
                result["videoCodec"] = str(stream.get("codec_name") or "")
                result["width"] = int(stream.get("width") or 0)
                result["height"] = int(stream.get("height") or 0)
            elif stream.get("codec_type") == "audio":
                result["audioCodec"] = str(stream.get("codec_name") or "")
        result["needsTranscode"] = result["videoCodec"].lower() not in {"h264", "avc1", "vp8", "vp9", "av1"}

    with _video_info_lock:
        _video_info_cache[key] = result
    return result


def _repair_amro_text(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return value.encode("gbk").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return value
    if isinstance(value, list):
        return [_repair_amro_text(item) for item in value]
    if isinstance(value, dict):
        return {key: _repair_amro_text(item) for key, item in value.items()}
    return value


def amro_api_get(path: str, params: dict[str, Any]) -> Any:
    query = urllib.parse.urlencode(
        {key: value for key, value in params.items() if value not in {None, ""}}
    )
    url = f"{AMRO_BASE_URL}/api{path}"
    if query:
        url += f"?{query}"
    credentials = base64.b64encode(f"{AMRO_USERNAME}:{AMRO_PASSWORD}".encode("utf-8")).decode("ascii")
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Basic {credentials}",
            "Accept": "application/json",
            "User-Agent": "JD-Air-Maintenance-Panel/1.0",
        },
    )
    payload: dict[str, Any] | None = None
    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
            break
        except (OSError, urllib.error.URLError, TimeoutError) as exc:
            last_exc = exc
            if attempt == 0:
                time.sleep(0.4)
    if payload is None:
        raise last_exc or RuntimeError("AMRO request failed")
    if payload.get("code") != 200:
        raise RuntimeError(payload.get("msg") or f"AMRO request failed: {payload.get('code')}")
    return _repair_amro_text(payload.get("data"))


def query_flight_dynamics(
    date: str,
    keyword: str = "",
    category: int = 0,
    current: int = 1,
    size: int = 20,
    dep_city: str = "",
    arr_city: str = "",
) -> dict[str, Any]:
    date = (date or dt.datetime.now().strftime("%Y-%m-%d")).strip()
    if len(date) == 10:
        date = f"{date} 00:00:00"
    current = max(1, int(current))
    size = max(1, min(int(size), 100))
    keyword = keyword.strip()
    dep_city = dep_city.strip()
    arr_city = arr_city.strip()
    if not keyword and not dep_city and not arr_city:
        return amro_api_get(
            "/amro-app/flight/taskPage",
            {
                "date": date,
                "keyword": keyword,
                "cn": max(0, min(int(category), 2)),
                "current": current,
                "size": size,
            },
        )

    rows = []
    search_date = date[:10]
    for row in flights_for_day(search_date):
        if not isinstance(row, dict):
            continue
        if keyword and _normalize_text(keyword) not in _normalize_text(_flight_search_blob(row)):
            continue
        if int(category) == 1 and str(row.get("dorI") or "").upper() != "D":
            continue
        if int(category) == 2 and str(row.get("dorI") or "").upper() != "I":
            continue
        if dep_city and _normalize_text(dep_city) not in _normalize_text(_flight_location_blob(row, "dep")):
            continue
        if arr_city and _normalize_text(arr_city) not in _normalize_text(_flight_location_blob(row, "arr")):
            continue
        rows.append(row)

    total = len(rows)
    pages = max(1, math.ceil(total / size))
    start = (current - 1) * size
    return {
        "records": rows[start:start + size],
        "total": total,
        "size": size,
        "current": current,
        "pages": pages,
        "orders": [],
        "searchCount": True,
        "optimizeCountSql": True,
    }


def query_flight_detail(flight_id: str) -> dict[str, Any]:
    return amro_api_get("/amro-app/flight/detail", {"id": flight_id})


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "")).lower()


def _flight_location_blob(flight: dict[str, Any], direction: str) -> str:
    if direction == "dep":
        return " ".join(
            str(part or "")
            for part in (
                normalize_flight_city(flight.get("dep3code")),
                flight.get("departureAirport"),
            )
        )
    return " ".join(
        str(part or "")
        for part in (
            normalize_flight_city(flight.get("arr3code")),
            flight.get("arrivalAirport"),
        )
    )


def _flight_search_blob(flight: dict[str, Any]) -> str:
    return " ".join(
        str(part or "")
        for part in (
            flight.get("flightNo"),
            flight.get("acno"),
            normalize_flight_city(flight.get("dep3code")),
            normalize_flight_city(flight.get("arr3code")),
            flight.get("departureAirport"),
            flight.get("arrivalAirport"),
            flight.get("status"),
        )
    )


def query_routine_tasks(
    date: str,
    keyword: str = "",
    category: int = 0,
    task_type: str = "",
    ac_type: str = "",
    status: str = "",
    sit: str = "",
    acno: str = "",
    current: int = 1,
    size: int = 20,
) -> dict[str, Any]:
    date = (date or dt.datetime.now().strftime("%Y-%m-%d")).strip()
    if len(date) == 10:
        date = f"{date} 00:00:00"
    current = max(1, int(current))
    size = max(1, min(int(size), 100))
    keyword = keyword.strip()
    task_type = task_type.strip()
    ac_type = ac_type.strip()
    status = status.strip()
    sit = sit.strip()
    acno = acno.strip()
    category = max(0, min(int(category), 2))

    cache_key = (date[:10], category)
    now = time.time()
    cached_hit = False
    with _routine_day_cache_lock:
        cached = _routine_day_cache.get(cache_key)
        if cached and now - cached[0] < _routine_day_cache_ttl:
            rows = list(cached[1])
            cached_hit = True
        else:
            rows = []
    if not cached_hit:
        first = amro_api_get(
            "/amro-app/lxTask/taskPage",
            {
                "flightDate": date,
                "keyword": "",
                "cn": category,
                "taskType": "",
                "acType": "",
                "isMy": "",
                "sit": "",
                "acno": "",
                "current": 1,
                "size": 100,
            },
        )
        rows.extend(first.get("records") or [])
        pages = max(1, int(first.get("pages") or math.ceil(int(first.get("total") or len(rows)) / 100)))
        for page in range(2, min(pages, 10) + 1):
            payload = amro_api_get(
                "/amro-app/lxTask/taskPage",
                {
                    "flightDate": date,
                    "keyword": "",
                    "cn": category,
                    "taskType": "",
                    "acType": "",
                    "isMy": "",
                    "sit": "",
                    "acno": "",
                    "current": page,
                    "size": 100,
                },
            )
            rows.extend(payload.get("records") or [])
        with _routine_day_cache_lock:
            _routine_day_cache[cache_key] = (now, rows)

    filtered: list[dict[str, Any]] = []
    keyword_blob = _normalize_text(keyword)
    sit_blob = _normalize_text(sit)
    acno_blob = _normalize_text(acno)
    for row in rows:
        if not isinstance(row, dict):
            continue
        if keyword_blob and keyword_blob not in _normalize_text(_routine_flight_blob(row)):
            continue
        if task_type and str(row.get("taskType") or "") != task_type:
            continue
        if ac_type and str(row.get("acType") or "") != ac_type:
            continue
        if status and str(row.get("tasksts") or "") != status:
            continue
        if sit_blob and all(
            sit_blob != _normalize_text(city)
            for city in _routine_outbound_cities(row)
        ):
            continue
        if acno_blob and acno_blob not in _normalize_text(row.get("acno")):
            continue
        filtered.append(row)

    total = len(filtered)
    filter_options = {
        "acnos": sorted(
            {str(row.get("acno") or "").strip() for row in rows if str(row.get("acno") or "").strip()},
            key=_normalize_text,
        ),
        "sites": sorted(
            {
                city
                for row in rows
                for city in _routine_outbound_cities(row)
            },
            key=_normalize_text,
        ),
    }
    return {
        "records": filtered[(current - 1) * size:(current - 1) * size + size],
        "total": total,
        "size": size,
        "current": current,
        "pages": max(1, math.ceil(total / size)),
        "statusFilter": status,
        "filterOptions": filter_options,
    }


def _routine_outbound_cities(row: dict[str, Any]) -> list[str]:
    route = str(row.get("outFlight") or "").strip()
    if not route or route in {"-", "--"}:
        return []
    cities: list[str] = []
    for city in re.split(r"\s*(?:-|—|–|→|>|/|至)\s*", route):
        city = city.strip()
        if city and city not in {"-", "--"} and city not in cities:
            cities.append(city)
    return cities


def _routine_flight_blob(row: dict[str, Any]) -> str:
    return " ".join(
        str(part or "")
        for part in (
            row.get("inFlightNo"),
            row.get("inFlight"),
            row.get("outFlightNo"),
            row.get("outFlight"),
        )
    )


def parse_routine_route(route: Any) -> tuple[str, str]:
    text = str(route or "").strip()
    if not text or text in {"-", "--"}:
        return "", ""
    parts = [
        normalize_flight_city(part.strip())
        for part in re.split(r"\s*(?:-|—|–|→|>|/|至)\s*", text)
        if part.strip() and part.strip() not in {"-", "--"}
    ]
    if len(parts) < 2:
        return "", ""
    return parts[0], parts[-1]


def query_routine_task_detail(task_id: str) -> dict[str, Any]:
    detail = amro_api_get("/amro-app/lxTask/taskDetail", {"id": task_id})
    if not isinstance(detail, dict):
        return {"taskid": task_id}
    try:
        process = amro_api_get(
            "/amro-app/lxTask/stepDetail",
            {"taskid": task_id, "tasksts": str(detail.get("tasksts") or "")},
        )
        if isinstance(process, dict):
            detail["processDetail"] = process
    except Exception:
        detail["processDetail"] = {}
    return detail


def parse_local_datetime(value: Any) -> dt.datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    text = text.replace("T", " ").split(".", 1)[0]
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S"):
        try:
            return dt.datetime.strptime(text, pattern)
        except ValueError:
            continue
    return None


def record_shoot_datetime(item: dict[str, Any]) -> dt.datetime | None:
    for key in ("startTime", "fileTime", "beginTime", "shootTime"):
        parsed = parse_local_datetime(item.get(key))
        if parsed:
            return parsed
    title = str(item.get("title") or item.get("fileName") or item.get("name") or "")
    match = re.search(r"_(\d{8})_(\d{6})(?:_|\.|$)", title)
    if match:
        try:
            return dt.datetime.strptime("".join(match.groups()), "%Y%m%d%H%M%S")
        except ValueError:
            pass
    return None


_FLIGHT_CITY_ALIASES = {
    "大兴": "北京",
    "首都": "北京",
    "廊坊": "北京",
    "浦东": "上海",
    "虹桥": "上海",
    "萧山": "杭州",
    "宝安": "深圳",
    "白云": "广州",
    "双流": "成都",
    "天府": "成都",
    "江北": "重庆",
    "重庆城区": "重庆",
    "滨海": "天津",
    "胶东": "青岛",
    "禄口": "南京",
    "咸阳": "西安",
    "高崎": "厦门",
    "周水子": "大连",
    "龙嘉": "长春",
    "太平": "哈尔滨",
    "新郑": "郑州",
    "昌北": "南昌",
    "栎社": "宁波",
    "硕放": "无锡",
}


def normalize_flight_city(value: Any) -> str:
    city = str(value or "").strip()
    for suffix in ("市", "机场"):
        if city.endswith(suffix):
            city = city[:-len(suffix)].strip()
    return _FLIGHT_CITY_ALIASES.get(city, city)


def flights_for_day(date_text: str) -> list[dict[str, Any]]:
    now = time.time()
    with _flight_day_cache_lock:
        cached = _flight_day_cache.get(date_text)
        if cached and now - cached[0] < _flight_day_cache_ttl:
            return cached[1]

    first = query_flight_dynamics(date_text, "", 0, 1, 100)
    rows = list(first.get("records") or first.get("data") or [])
    pages = max(1, int(first.get("pages") or math.ceil(int(first.get("total") or len(rows)) / 100)))
    for page in range(2, min(pages, 10) + 1):
        payload = query_flight_dynamics(date_text, "", 0, page, 100)
        rows.extend(payload.get("records") or payload.get("data") or [])

    with _flight_day_cache_lock:
        _flight_day_cache[date_text] = (now, rows)
    return rows


def routine_tasks_for_reference_day(date_text: str) -> list[dict[str, Any]]:
    payload = query_routine_tasks(date_text, "", 0, "", "", "", "", "", 1, 100)
    rows = list(payload.get("records") or [])
    pages = max(1, int(payload.get("pages") or 1))
    for page in range(2, min(pages, 10) + 1):
        page_payload = query_routine_tasks(date_text, "", 0, "", "", "", "", "", page, 100)
        rows.extend(page_payload.get("records") or [])
    unique: dict[str, dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, dict):
            key = str(row.get("taskid") or row.get("id") or f"{row.get('acno')}|{row.get('inFlightNo')}|{row.get('outFlightNo')}|{row.get('flightDate')}")
            unique[key] = row
    return list(unique.values())


def flights_near_day(shoot_time: dt.datetime) -> list[dict[str, Any]]:
    dates = [
        (shoot_time.date() + dt.timedelta(days=offset)).isoformat()
        for offset in (-1, 0, 1)
    ]
    rows: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(flights_for_day, date_text) for date_text in dates]
        for future in futures:
            try:
                rows.extend(future.result())
            except Exception:
                continue
    unique: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get("flightId") or f"{row.get('flightNo')}|{row.get('std')}|{row.get('acno')}")
        unique[key] = row
    return list(unique.values())


def nearest_record_position(dev_id: str, shoot_time: dt.datetime) -> dict[str, Any]:
    cache_key = (dev_id, shoot_time.strftime("%Y-%m-%d %H:%M"))
    with _record_position_cache_lock:
        cached = _record_position_cache.get(cache_key)
        if cached is not None:
            return cached

    result: dict[str, Any] = {"lat": None, "lng": None, "gpsTime": "", "source": ""}
    if dev_id:
        st = (shoot_time - dt.timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
        et = (shoot_time + dt.timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
        try:
            payload = call_mcs8_api(
                "/api/GetGpsModelList",
                {"st": st, "et": et, "devId": dev_id, "page": "1", "pagesize": "5000"},
            )
            nearest: tuple[float, dict[str, Any], dt.datetime] | None = None
            for row in record_rows(payload):
                lat = row.get("lat", row.get("latitude"))
                lng = row.get("lng", row.get("longitude"))
                gps_time = parse_local_datetime(row.get("gpsTime") or row.get("dateTime") or row.get("time"))
                if not gps_time or not valid_coord(lat, lng):
                    continue
                distance = abs((gps_time - shoot_time).total_seconds())
                if nearest is None or distance < nearest[0]:
                    nearest = (distance, row, gps_time)
            if nearest and nearest[0] <= 7200:
                _, row, gps_time = nearest
                result = {
                    "lat": float(row.get("lat", row.get("latitude"))),
                    "lng": float(row.get("lng", row.get("longitude"))),
                    "gpsTime": gps_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "source": "附近GPS",
                }
        except Exception:
            pass

    with _record_position_cache_lock:
        _record_position_cache[cache_key] = result
    return result


def warm_record_position_cache(
    items: list[dict[str, Any]],
    shoot_times: list[dt.datetime | None],
) -> None:
    grouped: dict[str, list[dt.datetime]] = {}
    for item, shoot_time in zip(items, shoot_times):
        if not shoot_time or valid_coord(
            item.get("lat", item.get("latitude")),
            item.get("lng", item.get("longitude")),
        ):
            continue
        dev_id = str(item.get("devId") or item.get("DevId") or item.get("szIDNO") or "")
        if not dev_id:
            continue
        cache_key = (dev_id, shoot_time.strftime("%Y-%m-%d %H:%M"))
        with _record_position_cache_lock:
            if cache_key in _record_position_cache:
                continue
        grouped.setdefault(dev_id, []).append(shoot_time)

    def warm_device(pair: tuple[str, list[dt.datetime]]) -> None:
        dev_id, times = pair
        unique_times = sorted(set(times))
        st = (unique_times[0] - dt.timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
        et = (unique_times[-1] + dt.timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
        points: list[tuple[dt.datetime, float, float]] = []
        try:
            payload = call_mcs8_api(
                "/api/GetGpsModelList",
                {"st": st, "et": et, "devId": dev_id, "page": "1", "pagesize": "5000"},
            )
            for row in record_rows(payload):
                lat = row.get("lat", row.get("latitude"))
                lng = row.get("lng", row.get("longitude"))
                gps_time = parse_local_datetime(row.get("gpsTime") or row.get("dateTime") or row.get("time"))
                if gps_time and valid_coord(lat, lng):
                    points.append((gps_time, float(lat), float(lng)))
        except Exception:
            points = []

        updates: dict[tuple[str, str], dict[str, Any]] = {}
        for shoot_time in unique_times:
            cache_key = (dev_id, shoot_time.strftime("%Y-%m-%d %H:%M"))
            nearest = min(
                points,
                key=lambda point: abs((point[0] - shoot_time).total_seconds()),
                default=None,
            )
            if nearest and abs((nearest[0] - shoot_time).total_seconds()) <= 7200:
                updates[cache_key] = {
                    "lat": nearest[1],
                    "lng": nearest[2],
                    "gpsTime": nearest[0].strftime("%Y-%m-%d %H:%M:%S"),
                    "source": "附近GPS",
                }
            else:
                updates[cache_key] = {"lat": None, "lng": None, "gpsTime": "", "source": ""}
        with _record_position_cache_lock:
            _record_position_cache.update(updates)

    if grouped:
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(6, len(grouped))) as executor:
            list(executor.map(warm_device, grouped.items()))


def record_position_and_city(item: dict[str, Any], shoot_time: dt.datetime) -> dict[str, Any]:
    lat = item.get("lat", item.get("latitude"))
    lng = item.get("lng", item.get("longitude"))
    source = "录像坐标"
    gps_time = shoot_time.strftime("%Y-%m-%d %H:%M:%S")
    if not valid_coord(lat, lng):
        fallback = nearest_record_position(
            str(item.get("devId") or item.get("DevId") or item.get("szIDNO") or ""),
            shoot_time,
        )
        lat, lng = fallback.get("lat"), fallback.get("lng")
        source = str(fallback.get("source") or "")
        gps_time = str(fallback.get("gpsTime") or "")
    if not valid_coord(lat, lng):
        return {"city": "", "lat": None, "lng": None, "source": "", "gpsTime": ""}
    city_info = get_city_by_gps(float(lng), float(lat))
    return {
        "city": normalize_flight_city(city_info.get("city")),
        "lat": float(lat),
        "lng": float(lng),
        "source": source,
        "gpsTime": gps_time,
    }


def flight_clock(value: Any) -> str:
    parsed = parse_local_datetime(value)
    return parsed.strftime("%H:%M") if parsed else "--"


def candidate_time(
    flight: dict[str, Any],
    actual_key: str,
    estimate_key: str,
    planned_key: str,
) -> tuple[dt.datetime | None, str]:
    actual = parse_local_datetime(flight.get(actual_key))
    if actual:
        return actual, "实际"
    estimated = parse_local_datetime(flight.get(estimate_key))
    if estimated:
        return estimated, "预计"
    return parse_local_datetime(flight.get(planned_key)), "计划"


def flight_match_score(minutes: int, time_kind: str) -> int:
    if minutes <= 30:
        score = 96
    elif minutes <= 60:
        score = 90
    elif minutes <= 120:
        score = 78
    elif minutes <= 240:
        score = 62
    else:
        score = 45
    if time_kind == "实际" or str(time_kind).startswith("实"):
        score += 2
    elif time_kind == "计划" or str(time_kind).startswith("计"):
        score -= 3
    return max(0, min(99, score))


def make_flight_candidate(
    flight: dict[str, Any],
    relation: str,
    minutes: int,
    time_kind: str,
) -> dict[str, Any]:
    return {
        "flightId": str(flight.get("flightId") or ""),
        "acno": str(flight.get("acno") or "--"),
        "flightNo": str(flight.get("flightNo") or "--"),
        "departure": str(flight.get("dep3code") or "--"),
        "arrival": str(flight.get("arr3code") or "--"),
        "departureTime": f"{flight_clock(flight.get('std'))} / {flight_clock(flight.get('atd'))}",
        "arrivalTime": f"{flight_clock(flight.get('sta'))} / {flight_clock(flight.get('ata'))}",
        "relation": relation,
        "minutes": minutes,
        "timeKind": time_kind,
        "score": flight_match_score(minutes, time_kind),
        "status": str(flight.get("status") or ""),
    }


def routine_reference_time(task: dict[str, Any], direction: str) -> tuple[dt.datetime | None, str, str]:
    if direction == "out":
        parsed = parse_local_datetime(task.get("outDate"))
        date_type = str(task.get("outDateType") or "")
        if date_type == "2":
            return parsed, "实飞", "outDate"
        if date_type == "1":
            return parsed, "计飞", "outDate"
        if date_type == "3":
            return parsed, "预计", "outDate"
        if parsed:
            return parsed, "出港", "outDate"
        return None, "", "outDate"
    parsed = parse_local_datetime(task.get("inDate"))
    date_type = str(task.get("inDateType") or "")
    if date_type == "2":
        return parsed, "实达", "inDate"
    if date_type == "1":
        return parsed, "计达", "inDate"
    if date_type == "3":
        return parsed, "预计", "inDate"
    if parsed:
        return parsed, "进港", "inDate"
    return None, "", "inDate"


def routine_start_direction(task: dict[str, Any], directions: list[str]) -> str:
    task_type = str(task.get("taskType") or "").upper()
    if task_type == "AF" and "in" in directions:
        return "in"
    if task_type == "AP" and "out" in directions:
        return "out"
    if "out" in directions:
        return "out"
    return directions[0] if directions else "out"


def make_routine_reference_candidate(
    task: dict[str, Any],
    direction: str,
    relation: str,
    minutes: int,
    time_kind: str,
    reference_value: Any | None = None,
    score_bonus: int = 0,
) -> dict[str, Any]:
    if direction == "out":
        dep_city, arr_city = parse_routine_route(task.get("outFlight"))
        flight_no = str(task.get("outFlightNo") or "--")
        departure_time = f"{time_kind} {flight_clock(reference_value if reference_value is not None else task.get('outDate'))}"
        arrival_time = "--"
    else:
        dep_city, arr_city = parse_routine_route(task.get("inFlight"))
        flight_no = str(task.get("inFlightNo") or "--")
        departure_time = "--"
        arrival_time = f"{time_kind} {flight_clock(reference_value if reference_value is not None else task.get('inDate'))}"
    score = max(0, min(99, flight_match_score(minutes, time_kind) + score_bonus))
    return {
        "source": "routine",
        "taskId": str(task.get("taskid") or ""),
        "acno": str(task.get("acno") or "--"),
        "flightNo": flight_no,
        "departure": dep_city or "--",
        "arrival": arr_city or "--",
        "departureTime": departure_time,
        "arrivalTime": arrival_time,
        "timeDisplay": departure_time if direction == "out" else arrival_time,
        "relation": relation,
        "minutes": minutes,
        "timeKind": time_kind,
        "score": score,
        "taskType": str(task.get("taskTypeName") or task.get("taskType") or "--"),
        "wxWorker": str(task.get("wxWorker") or "--"),
        "fxWorker": str(task.get("fxWorker") or "--"),
        "bay": str(task.get("bay") or "--"),
        "status": str(task.get("taskstsName") or task.get("tasksts") or ""),
    }


def match_record_flight_reference(item: dict[str, Any], flights: list[dict[str, Any]]) -> dict[str, Any]:
    shoot_time = record_shoot_datetime(item)
    if not shoot_time:
        return {"city": "", "shootTime": "", "certainty": "无法判断", "reason": "缺少拍摄时间", "candidates": []}
    position = record_position_and_city(item, shoot_time)
    city = normalize_flight_city(position.get("city"))
    if not city:
        return {
            "city": "",
            "shootTime": shoot_time.strftime("%Y-%m-%d %H:%M:%S"),
            "certainty": "无法判断",
            "reason": "拍摄时刻附近无有效定位",
            "position": position,
            "candidates": [],
        }

    candidates: list[dict[str, Any]] = []
    for flight in flights:
        if flight.get("taskid") or flight.get("inFlight") is not None or flight.get("outFlight") is not None:
            out_dep_city, _ = parse_routine_route(flight.get("outFlight"))
            matched_directions: list[str] = []
            if out_dep_city == city:
                matched_directions.append("out")
                departure_time, time_kind, _ = routine_reference_time(flight, "out")
                if departure_time:
                    minutes = round((departure_time - shoot_time).total_seconds() / 60)
                    if 0 <= minutes <= 360:
                        candidates.append(make_routine_reference_candidate(flight, "out", "起飞前", minutes, time_kind))

            _, in_arr_city = parse_routine_route(flight.get("inFlight"))
            if in_arr_city == city:
                matched_directions.append("in")
                arrival_time, time_kind, _ = routine_reference_time(flight, "in")
                if arrival_time:
                    minutes = round((shoot_time - arrival_time).total_seconds() / 60)
                    if 0 <= minutes <= 360:
                        candidates.append(make_routine_reference_candidate(flight, "in", "到达后", minutes, time_kind))

            start_plan_time = parse_local_datetime(flight.get("startPlanDate"))
            if start_plan_time and matched_directions:
                minutes = round(abs((shoot_time - start_plan_time).total_seconds()) / 60)
                if minutes <= 360:
                    relation = "计划开始后" if shoot_time >= start_plan_time else "计划开始前"
                    direction = routine_start_direction(flight, matched_directions)
                    candidates.append(
                        make_routine_reference_candidate(
                            flight,
                            direction,
                            relation,
                            minutes,
                            "计划开始",
                            flight.get("startPlanDate"),
                            score_bonus=5,
                        )
                    )
            continue

        status = str(flight.get("status") or "")
        dep_city = normalize_flight_city(flight.get("dep3code"))
        arr_city = normalize_flight_city(flight.get("arr3code"))

        if dep_city == city:
            departure_time, time_kind = candidate_time(flight, "atd", "etd", "std")
            if departure_time:
                minutes = round((departure_time - shoot_time).total_seconds() / 60)
                if 0 <= minutes <= 360 and ("取消" not in status or flight.get("atd")):
                    candidates.append(make_flight_candidate(flight, "起飞前", minutes, time_kind))

        if arr_city == city:
            arrival_time, time_kind = candidate_time(flight, "ata", "eta", "sta")
            if arrival_time:
                minutes = round((shoot_time - arrival_time).total_seconds() / 60)
                if 0 <= minutes <= 360 and ("取消" not in status or flight.get("ata")):
                    candidates.append(make_flight_candidate(flight, "到达后", minutes, time_kind))

    candidates.sort(key=lambda row: (-int(row["score"]), int(row["minutes"]), row["flightNo"]))
    if not candidates:
        return {
            "city": city,
            "shootTime": shoot_time.strftime("%Y-%m-%d %H:%M:%S"),
            "certainty": "暂无候选",
            "reason": "同城例行任务不在计划开始、起飞前或到达后 6 小时窗口内",
            "position": position,
            "candidates": [],
        }

    top = candidates[0]
    second = candidates[1] if len(candidates) > 1 else None
    clear = int(top["score"]) >= 90 and (second is None or int(top["score"]) - int(second["score"]) >= 12)
    selected = candidates[:1] if clear else candidates[:3]
    certainty = "较明确" if clear else ("低置信候选" if len(selected) == 1 else "多个候选")
    return {
        "city": city,
        "shootTime": shoot_time.strftime("%Y-%m-%d %H:%M:%S"),
        "certainty": certainty,
        "reason": (
            f"{top['relation']}{top['minutes']}分钟，优先采用{top['timeKind']}时刻"
            if clear
            else (
                "仅有一个时间距离较远的候选，请结合画面中的机号确认"
                if len(selected) == 1
                else "多个同城航班时间接近，请结合画面中的机号确认"
            )
        ),
        "position": position,
        "candidates": selected,
    }


def match_record_flight_references(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    safe_items = [item for item in items[:100] if isinstance(item, dict)]
    parsed_times = [record_shoot_datetime(item) for item in safe_items]
    shoot_days = sorted({value.date() for value in parsed_times if value})
    needed_reference_days = sorted(
        {
            (shoot_day + dt.timedelta(days=offset)).isoformat()
            for shoot_day in shoot_days
            for offset in (-1, 0, 1)
        }
    )
    reference_rows_by_date: dict[str, list[dict[str, Any]]] = {}
    max_workers = min(8, max(1, len(needed_reference_days) + 1))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        gps_future = executor.submit(warm_record_position_cache, safe_items, parsed_times)
        reference_futures = {
            date_text: executor.submit(routine_tasks_for_reference_day, date_text)
            for date_text in needed_reference_days
        }
        for date_text, future in reference_futures.items():
            try:
                reference_rows_by_date[date_text] = future.result()
            except Exception:
                reference_rows_by_date[date_text] = []
        gps_future.result()

    reference_rows_by_day: dict[str, list[dict[str, Any]]] = {}
    for shoot_day in shoot_days:
        rows: list[dict[str, Any]] = []
        for offset in (-1, 0, 1):
            date_text = (shoot_day + dt.timedelta(days=offset)).isoformat()
            rows.extend(reference_rows_by_date.get(date_text, []))
        unique: dict[str, dict[str, Any]] = {}
        for row in rows:
            key = str(row.get("taskid") or row.get("flightId") or f"{row.get('flightNo')}|{row.get('std')}|{row.get('acno')}")
            unique[key] = row
        reference_rows_by_day[shoot_day.isoformat()] = list(unique.values())

    def match_one(pair: tuple[dict[str, Any], dt.datetime | None]) -> dict[str, Any]:
        item, shoot_time = pair
        flights = reference_rows_by_day.get(shoot_time.date().isoformat(), []) if shoot_time else []
        try:
            return match_record_flight_reference(item, flights)
        except Exception as exc:
            return {
                "city": "",
                "shootTime": shoot_time.strftime("%Y-%m-%d %H:%M:%S") if shoot_time else "",
                "certainty": "匹配失败",
                "reason": str(exc),
                "candidates": [],
            }

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(6, max(1, len(safe_items)))) as executor:
        return list(executor.map(match_one, zip(safe_items, parsed_times)))



























HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>京东航空维修部视频记录系统</title>
  <link rel="stylesheet" href="leaflet.css">
  <script src="leaflet.js"></script>
  <style>
    :root { font-family: "Microsoft YaHei", Arial, sans-serif; color: #1f2b36; background: #eef2f5; }
    * { box-sizing: border-box; }
    body { margin: 0; }
    header { min-height: 58px; background: #12395a; color: #fff; display: grid; grid-template-columns: 280px 1fr auto; align-items: center; gap: 14px; padding: 0 18px; }
    h1 { font-size: 18px; margin: 0; font-weight: 650; white-space: nowrap; }
    h2 { font-size: 16px; margin: 0; font-weight: 650; }
    h3 { font-size: 14px; margin: 0; font-weight: 650; }
    button, input, select { font: inherit; }
    button { border: 1px solid #276b9d; background: #287bb6; color: #fff; border-radius: 4px; padding: 7px 11px; cursor: pointer; }
    button.secondary { background: #fff; color: #245d88; border-color: #b8cad8; }
    button.ghost { background: transparent; color: #dcecf8; border-color: rgba(255,255,255,.24); }
    button:disabled { opacity: .5; cursor: not-allowed; }
    input, select { border: 1px solid #c6d4df; border-radius: 4px; padding: 7px 9px; min-width: 120px; background: #fff; }
    .topnav { display: flex; gap: 8px; flex-wrap: wrap; }
    .topnav button.active { background: #fff; color: #12395a; border-color: #fff; }
    .status { color: #d9e8f2; font-size: 13px; text-align: right; }
    .login-screen { position: fixed; inset: 0; z-index: 5000; display: flex; align-items: center; justify-content: center; background: linear-gradient(135deg, #0d314f 0%, #12395a 45%, #e9f1f7 45%, #f7fafc 100%); padding: 24px; }
    .login-card { width: min(420px, 94vw); background: rgba(255,255,255,.96); border: 1px solid rgba(255,255,255,.7); box-shadow: 0 18px 50px rgba(13,49,79,.28); border-radius: 12px; padding: 26px; display: grid; gap: 16px; }
    .login-card h2 { font-size: 22px; color: #12395a; }
    .login-card p { margin: 0; color: #5f7385; font-size: 13px; line-height: 1.6; }
    .login-form { display: grid; gap: 12px; }
    .login-form label { display: grid; gap: 6px; color: #354c60; font-size: 13px; font-weight: 650; }
    .login-form input { width: 100%; min-width: 0; padding: 10px 11px; }
    .login-actions { display: flex; gap: 10px; align-items: center; justify-content: space-between; }
    .login-error { color: #b23b3b; font-size: 13px; min-height: 18px; }
    .login-screen.hidden { display: none; }
    .layout { height: calc(100vh - 58px); display: grid; grid-template-columns: 322px 1fr; min-height: 680px; }
    aside { border-right: 1px solid #d4dee7; background: #f8fafc; overflow: auto; position: relative; }
    aside.collapsed { width: 0 !important; min-width: 0 !important; overflow: hidden; border-right: none; padding: 0; }
        aside.collapsed * { visibility: hidden; }
    .layout:has(> aside.collapsed) { grid-template-columns: 0px 1fr; }
    .sidebar-toggle-btn { position: fixed; top: 70px; left: 0; z-index: 2000; min-width: 94px; height: 38px; padding: 0 12px; background: #12395a; color: #fff; border: none; border-radius: 0 6px 6px 0; cursor: pointer; font-size: 13px; font-weight: 650; display: flex; align-items: center; justify-content: center; box-shadow: 2px 2px 8px rgba(0,0,0,0.3); white-space: nowrap; }
    .sidebar-toggle-btn:hover { background: #1a5a8a; }
    .layout { transition: grid-template-columns 0.3s; }
    .side-head { padding: 12px; border-bottom: 1px solid #dde6ee; display: grid; gap: 10px; }
    .summary { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
    .metric { background: #fff; border: 1px solid #dbe5ed; border-radius: 6px; padding: 8px; }
    .metric strong { display: block; font-size: 20px; }
    .metric span { color: #607386; font-size: 12px; }
    .workbench-top { display: grid; grid-template-columns: minmax(340px, .8fr) minmax(280px, 1.6fr); gap: 8px; align-items: stretch; }
    .workbench-card { border: 1px solid #dce6ee; background: #f8fafc; border-radius: 6px; padding: 7px; min-width: 0; }
    .workbench-card h3 { margin-bottom: 5px; display: flex; align-items: center; gap: 10px; color: #38536a; }
    .workbench-metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 5px; }
    .workbench-metrics .metric { padding: 5px 7px; }
    .workbench-metrics .metric strong { font-size: 16px; line-height: 1.05; }
    .workbench-metrics .metric span { font-size: 11px; }
    .compact-city-buttons { display: flex; flex-wrap: wrap; gap: 5px; max-height: 48px; overflow: auto; padding-right: 2px; }
    .compact-city-buttons button { padding: 3px 7px; font-size: 12px; line-height: 1.15; }
    .side-tabs { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
    .side-tabs button.active { background: #1d628f; color: #fff; }
    .tree { padding: 8px 10px 18px; }
    .group { border-bottom: 1px solid #e5edf3; padding: 8px 0; }
    .group-title { display: flex; justify-content: space-between; align-items: center; color: #324b61; font-weight: 650; margin-bottom: 6px; }
    .device-row { width: 100%; border: 0; background: transparent; color: #233747; display: grid; grid-template-columns: 1fr auto; gap: 8px; text-align: left; padding: 7px 5px; border-radius: 4px; }
    .device-row:hover, .device-row.active { background: #e8f2fb; }
    .dot { width: 8px; height: 8px; border-radius: 999px; display: inline-block; margin-right: 5px; background: #b64b4b; }
    .dot.on { background: #159260; }
    .muted { color: #657789; font-size: 12px; }
    .gps-city { color: #c0392b; font-size: 12px; font-weight: 600; }
    .wh-city { color: #1a8a4a; font-size: 12px; font-weight: 600; }
    .legend { display: flex; gap: 12px; font-size: 12px; padding: 4px 8px; background: #f0f4f8; border-radius: 4px; margin: 4px 0 6px; }
    .legend span { display: flex; align-items: center; gap: 3px; }
    .legend .dot-gps { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #c0392b; }
    .legend .dot-wh { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #1a8a4a; }
    main { min-width: 0; overflow: auto; padding: 12px; }
    .view { display: none; min-height: 100%; }
    .view.active { display: grid; gap: 12px; }
    .panel { background: #fff; border: 1px solid #d9e3eb; border-radius: 6px; min-width: 0; }
    .panel-head { min-height: 44px; padding: 10px 12px; border-bottom: 1px solid #e2e9ef; display: flex; align-items: center; justify-content: space-between; gap: 10px; }
    .panel-body { padding: 12px; }
    .toolbar { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
    .map-shell { min-height: 520px; display: grid; grid-template-columns: 1fr 260px; }
    .map { position: relative; overflow: hidden; min-height: 520px; background:
      linear-gradient(90deg, rgba(255,255,255,.24) 1px, transparent 1px) 0 0/48px 48px,
      linear-gradient(rgba(255,255,255,.22) 1px, transparent 1px) 0 0/48px 48px,
      linear-gradient(135deg, #d7e8ee, #e8efe3 48%, #d9e9f2); }
    .map::before { content: ""; position: absolute; inset: 38px 70px 70px 42px; border: 1px dashed rgba(67,99,120,.35); border-radius: 45% 55% 48% 52%; transform: rotate(-9deg); }
    .map.leaflet-ready::before { display: none; }
    .leaflet-container { font: inherit; }
    .marker { position: absolute; transform: translate(-50%, -100%); border: 0; color: #fff; padding: 0; background: transparent; }
    .pin { display: grid; place-items: center; width: 26px; height: 26px; border-radius: 50% 50% 50% 0; transform: rotate(-45deg); background: #b14c4c; box-shadow: 0 4px 10px rgba(0,0,0,.25); }
    .pin.on { background: #137e58; }
    .pin span { transform: rotate(45deg); font-size: 11px; font-weight: 700; }
    .label { position: absolute; top: 28px; left: 50%; transform: translateX(-50%); background: rgba(255,255,255,.9); color: #1f2b36; border: 1px solid #cdd9e2; border-radius: 4px; padding: 2px 5px; white-space: nowrap; font-size: 12px; }
    .map-side { border-left: 1px solid #dce6ee; background: #f8fafc; padding: 12px; display: grid; align-content: start; gap: 10px; }
    .layer-list label { display: block; margin: 6px 0; }
    .track-controls { display: grid; gap: 7px; }
    .track-controls input { min-width: 0; width: 100%; }
    .track-actions { display: grid; grid-template-columns: 1fr auto; gap: 7px; }
    .dispatch-wrap { max-height: 330px; overflow: auto; }
    .dispatch-wrap td, .dispatch-wrap th { white-space: nowrap; }
    .pager { display: flex; align-items: center; justify-content: flex-end; gap: 8px; padding: 10px 0 0; color: #4f6273; }
    .file-layout { display: flex; flex-direction: column; gap: 12px; }
    .file-bottom { display: grid; grid-template-columns: 1fr 240px; gap: 12px; }
    .file-bottom > * { min-width: 0; }
    .records-wrap { width: 100%; max-width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch; }
    .records-wrap table { min-width: 0; }
    .records-table { table-layout: fixed; }
    .records-table th, .records-table td { white-space: normal; overflow-wrap: anywhere; word-break: break-word; line-height: 1.35; }
    .records-table th:nth-child(1), .records-table td:nth-child(1) { width: 72px; }
    .records-table th:nth-child(2), .records-table td:nth-child(2) { width: 88px; }
    .records-table th:nth-child(3), .records-table td:nth-child(3) { width: 20%; }
    .records-table th:nth-child(4), .records-table td:nth-child(4) { width: 72px; }
    .records-table th:nth-child(5), .records-table td:nth-child(5) { width: 76px; }
    .records-table th:nth-child(6), .records-table td:nth-child(6),
    .records-table th:nth-child(7), .records-table td:nth-child(7) { width: 96px; }
    .records-table th:nth-child(8), .records-table td:nth-child(8) { width: 18%; }
    .records-table th:nth-child(9), .records-table td:nth-child(9) { width: 86px; }
    .records-table .metric-cell span,
    .records-table .time-cell span { display: block; }
    .records-table .flight-ref { min-width: 0; max-width: none; }
    .record-action-buttons { display: grid; gap: 6px; justify-items: stretch; }
    .record-action-buttons button { width: 100%; padding-left: 6px; padding-right: 6px; }
    .player-bar { display: flex; justify-content: space-between; align-items: center; gap: 10px; padding: 8px 10px; border: 1px solid #dce6ee; border-radius: 6px; background: #f8fbfd; color: #334b5d; }
    .player-bar strong { font-size: 14px; margin-right: 8px; color: #163a54; }
    .player-bar span { color: #687b8b; font-size: 12px; }
    .player-bar button { flex: 0 0 auto; }
    .player-wrap { --playlist-width: 200px; background: #0a0e14; border-radius: 6px; padding: 6px; min-height: 560px; display: grid; grid-template-columns: minmax(360px, 1fr) 8px var(--playlist-width); gap: 6px; align-items: stretch; }
    .player-wrap.player-empty { display: none; min-height: 0; background: #111820; }
    .player-wrap.player-empty.playlist-expanded { display: block; }
    .player-wrap.player-empty .player-grid,
    .player-wrap.player-empty .player-resizer { display: none; }
    .player-wrap.playlist-collapsed { grid-template-columns: minmax(360px, 1fr); }
    .player-wrap.playlist-collapsed .player-side,
    .player-wrap.playlist-collapsed .player-resizer { display: none; }
    .player-wrap.has-multi { min-height: 0; }
    .player-grid { display: grid; gap: 4px; min-width: 0; min-height: 540px; align-content: start; }
    .player-wrap.has-multi .player-grid { min-height: 0; }
    .player-grid.single-player { align-content: stretch; grid-auto-rows: minmax(540px, 1fr); }
    .player-grid.multi-player { align-content: start; grid-auto-rows: auto; }
    .player-cell { position: relative; background: #000; border-radius: 4px; overflow: hidden; min-width: 0; max-width: 100%; min-height: 0; }
    .player-grid.single-player .player-cell { min-height: 540px; height: 100%; }
    .player-grid.multi-player .player-cell { aspect-ratio: 16 / 9; height: auto; }
    .player-grid video { width: 100%; min-width: 0; max-width: 100%; max-height: none; height: 100%; object-fit: contain; display: block; background: #000; }
    .player-resizer { width: 8px; min-width: 8px; cursor: col-resize; border-radius: 999px; background: linear-gradient(180deg, rgba(74,97,116,.18), rgba(141,160,176,.38), rgba(74,97,116,.18)); position: relative; }
    .player-resizer::after { content: ""; position: absolute; inset: 42% 2px; border-left: 1px solid rgba(255,255,255,.35); border-right: 1px solid rgba(255,255,255,.35); }
    .player-resizer:hover, .player-resizer.active { background: #287bb6; }
    .player-wrap.resizing { user-select: none; cursor: col-resize; }
    .player-wrap.resizing video { pointer-events: none; }
    .player-side { width: 100%; display: flex; flex-direction: column; gap: 6px; overflow-y: auto; max-height: 440px; padding: 4px; background: #111820; border-radius: 4px; }
    .player-wrap.player-empty.playlist-expanded .player-side { max-height: 180px; }
    .player-side h3 { color: #a0b0c0; font-size: 12px; margin: 0; padding: 2px 4px; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { border-bottom: 1px solid #e5edf3; padding: 8px; text-align: left; vertical-align: top; }
    th { color: #4b6072; background: #f7fafc; font-weight: 650; }
    video { width: 100%; max-height: 200px; background: #0c1117; border-radius: 4px; }
    pre { white-space: pre-wrap; overflow-wrap: anywhere; background: #f7f9fb; padding: 10px; border-radius: 4px; border: 1px solid #e0e6ec; margin: 0; max-height: 260px; overflow: auto; }
    .error { border-color: #e2aaaa; background: #fff7f7; color: #7c2424; }
    .ok { color: #087a49; font-weight: 650; }
    .off { color: #a33434; font-weight: 650; }
    .flight-table-wrap { overflow: auto; max-height: calc(100vh - 250px); }
    .flight-table-wrap th, .flight-table-wrap td { white-space: nowrap; }
    .flight-status { display: inline-block; padding: 2px 8px; border-radius: 999px; font-weight: 650; background: #eef2f5; color: #4f6273; }
    .flight-status.normal { background: #e8f7ef; color: #087a49; }
    .flight-status.delay { background: #fff0ed; color: #c24736; }
    .flight-status.cancel { background: #edf0f3; color: #66717b; }
    .flight-summary { display: flex; gap: 16px; flex-wrap: wrap; color: #516678; font-size: 13px; }
    .flight-detail-grid { display: grid; grid-template-columns: repeat(4, minmax(140px, 1fr)); gap: 10px; margin-bottom: 12px; }
    .flight-detail-grid > div { background: #f7fafc; border: 1px solid #e0e8ef; border-radius: 5px; padding: 8px; }
    .flight-detail-grid label { display: block; color: #6b7e8f; font-size: 11px; margin-bottom: 3px; }
    .routine-status { display: inline-block; padding: 2px 8px; border-radius: 999px; font-weight: 650; background: #edf1f4; color: #5d6b77; }
    .routine-status.pending { background: #fff3da; color: #9a6500; }
    .routine-status.working { background: #e6f1ff; color: #0b5fa5; }
    .routine-status.done { background: #e8f7ef; color: #087a49; }
    .routine-flow { display: flex; align-items: center; gap: 4px; overflow-x: auto; margin: 4px 0 14px; padding-bottom: 4px; }
    .routine-flow span { flex: 0 0 auto; padding: 6px 10px; border-radius: 999px; background: #edf1f4; color: #75828d; font-size: 12px; }
    .routine-flow span.done { background: #e8f7ef; color: #087a49; }
    .routine-flow span.current { background: #1769aa; color: #fff; }
    .routine-flow i { color: #a7b3bc; font-style: normal; }
    .flight-ref { min-width: 245px; max-width: 340px; font-size: 12px; line-height: 1.45; }
    .flight-ref-head { color: #496172; margin-bottom: 3px; }
    .flight-ref-item { border-top: 1px dashed #d9e3ea; padding-top: 4px; margin-top: 4px; }
    .flight-ref-item strong { color: #0b5fa5; }
    .flight-ref-meta { color: #486577; }
    .flight-ref-reason { color: #7b5b1b; }
    .flight-ref-empty { color: #83919d; }
    @media (max-width: 1180px) {
      header { grid-template-columns: 1fr auto; padding: 9px 12px; gap: 8px 12px; }
      .topnav { grid-column: 1 / -1; order: 3; }
      .status { align-self: center; }
      .layout { height: calc(100dvh - 106px); min-height: 600px; grid-template-columns: 280px 1fr; }
      .map-shell { grid-template-columns: minmax(0, 1fr) 230px; }
      .file-bottom { grid-template-columns: 1fr; }
      .flight-detail-grid { grid-template-columns: repeat(2, minmax(120px, 1fr)); }
      .sidebar-toggle-btn { top: 112px; }
    }
    @media (max-width: 700px) {
      .workbench-top { grid-template-columns: 1fr; }
    }
    @media (max-width: 900px) {
      body { overflow-x: hidden; }
      header { display: flex; flex-wrap: wrap; align-items: center; position: relative; z-index: 1000; }
      header h1 { flex: 1 1 auto; font-size: 16px; }
      .status { flex: 0 1 auto; font-size: 11px; }
      .topnav { order: 3; width: 100%; flex-wrap: nowrap; overflow-x: auto; padding-bottom: 2px; scrollbar-width: thin; -webkit-overflow-scrolling: touch; }
      .topnav button { flex: 0 0 auto; min-height: 40px; }
      .layout, .layout:has(> aside.collapsed) { height: auto; min-height: calc(100dvh - 112px); display: block; }
      aside { position: fixed; inset: 0 auto 0 0; z-index: 1800; width: min(86vw, 322px); padding-top: 54px; box-shadow: 5px 0 18px rgba(0,0,0,.28); transform: none; }
      aside.collapsed { display: none; width: min(86vw, 322px) !important; transform: none; }
      .sidebar-toggle-btn { top: 116px; min-width: 100px; height: 40px; }
      main { width: 100%; padding: 8px; overflow: visible; }
      .map-shell { grid-template-columns: 1fr; }
      .map, .map-shell { min-height: 440px; }
      .map-side { border-left: 0; border-top: 1px solid #dce6ee; }
      .player-bar { align-items: stretch; flex-direction: column; }
      .player-bar button { width: 100%; }
      .player-wrap { grid-template-columns: 1fr; min-height: 0; }
      .player-grid { min-height: 320px; }
      .player-grid > div { min-height: 280px; }
      .player-resizer { display: none; }
      .player-side { width: 100%; max-height: 180px; }
      .toolbar input, .toolbar select { flex: 1 1 145px; min-width: 0; }
      .toolbar button { min-height: 40px; }
      .panel-head { align-items: flex-start; flex-wrap: wrap; }
      .flight-table-wrap { max-height: none; }
    }
    @media (max-width: 600px) {
      header { padding: 8px; gap: 7px; }
      header h1 { width: 100%; flex-basis: 100%; text-align: center; font-size: 15px; }
      .status { width: 100%; text-align: center; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .topnav { gap: 6px; }
      .topnav button { padding: 7px 10px; font-size: 13px; }
      .sidebar-toggle-btn { top: 128px; min-width: 96px; font-size: 12px; }
      main { padding: 6px; }
      .panel-body { padding: 8px; }
      .compact-city-buttons { max-height: 58px; }
      .metric { padding: 7px; }
      .metric strong { font-size: 18px; }
      .map, .map-shell { min-height: 360px; }
      .player-grid { min-height: 210px; }
      .player-grid > div { min-height: 210px !important; height: auto !important; aspect-ratio: 16 / 9; }
      .player-grid video { min-height: 0 !important; max-height: none; }
      .flight-detail-grid { grid-template-columns: 1fr; }
      .toolbar { gap: 6px; }
      .toolbar input, .toolbar select { flex-basis: calc(50% - 4px); width: calc(50% - 4px); }
      .toolbar button { flex: 1 1 auto; }
      .pager { justify-content: center; flex-wrap: wrap; }
      .flight-summary { gap: 8px; font-size: 12px; }
      .records-wrap { margin: 0 -2px; width: calc(100% + 4px); }
    }

    /* 2026 layout redesign: presentation only; API routes and data behavior remain unchanged. */
    :root {
      color-scheme: dark;
      --bg: #07101e;
      --bg-soft: #0a1627;
      --surface: #0d1b2d;
      --surface-2: #102238;
      --surface-3: #142b44;
      --line: #203a56;
      --line-soft: rgba(102, 157, 204, .18);
      --text: #e6f1fb;
      --muted-text: #8ea8be;
      --accent: #26a7ff;
      --accent-strong: #087fd0;
      --accent-soft: rgba(38, 167, 255, .14);
      --success: #35d49a;
      --danger: #ff6874;
      --warning: #f6bd4b;
      --shadow: 0 12px 32px rgba(0, 0, 0, .22);
      font-family: "Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", Arial, sans-serif;
      color: var(--text);
      background: var(--bg);
    }
    html, body { min-height: 100%; background: var(--bg); }
    body {
      color: var(--text);
      background:
        radial-gradient(circle at 88% -10%, rgba(31, 126, 191, .20), transparent 32%),
        linear-gradient(180deg, #07101e, #091525 62%, #07111f);
    }
    button {
      min-height: 36px;
      border: 1px solid #218fd7;
      background: linear-gradient(180deg, #168edc, #0876bd);
      color: #fff;
      border-radius: 6px;
      padding: 7px 13px;
      font-weight: 650;
      transition: border-color .18s, background .18s, color .18s, transform .18s, box-shadow .18s;
    }
    button:hover:not(:disabled) {
      border-color: #59bdff;
      background: linear-gradient(180deg, #20a1f4, #087ac3);
      box-shadow: 0 6px 16px rgba(8, 127, 208, .22);
      transform: translateY(-1px);
    }
    button.secondary {
      background: #11253b;
      color: #bcd2e4;
      border-color: #294a67;
    }
    button.secondary:hover:not(:disabled),
    button.secondary.active {
      background: var(--accent-soft);
      color: #73c8ff;
      border-color: #248fd3;
      box-shadow: none;
    }
    button.ghost {
      background: rgba(255,255,255,.025);
      color: #b8cee1;
      border-color: rgba(167, 202, 230, .20);
      box-shadow: none;
    }
    button.ghost:hover:not(:disabled) {
      background: rgba(38, 167, 255, .12);
      color: #fff;
      border-color: rgba(72, 183, 255, .55);
      box-shadow: none;
    }
    button.ghost.danger:hover:not(:disabled) {
      background: rgba(255, 104, 116, .11);
      color: #ff9fa7;
      border-color: rgba(255, 104, 116, .5);
    }
    input, select {
      min-height: 36px;
      border: 1px solid #29445f;
      border-radius: 6px;
      color: #dceaf5;
      background: #0a1727;
      outline: none;
      transition: border-color .18s, box-shadow .18s, background .18s;
    }
    input::placeholder { color: #607b92; }
    input:focus, select:focus {
      border-color: #2daaff;
      background: #0c1d30;
      box-shadow: 0 0 0 3px rgba(38, 167, 255, .12);
    }
    select option { background: #0c1b2c; color: #e5f1fa; }
    .app-header {
      height: 70px;
      min-height: 70px;
      position: relative;
      z-index: 2100;
      grid-template-columns: 308px minmax(420px, 1fr) auto;
      gap: 22px;
      padding: 0 18px;
      border-bottom: 1px solid #1a3957;
      background:
        linear-gradient(90deg, rgba(22, 91, 142, .14), transparent 30%),
        rgba(6, 17, 31, .97);
      box-shadow: 0 6px 22px rgba(0, 0, 0, .24);
    }
    .brand { display: flex; align-items: center; gap: 11px; min-width: 0; }
    .brand-mark {
      width: 38px;
      height: 38px;
      flex: 0 0 38px;
      display: grid;
      place-items: center;
      border: 1px solid rgba(91, 195, 255, .58);
      border-radius: 8px;
      color: #8bd5ff;
      background: linear-gradient(145deg, rgba(38, 167, 255, .22), rgba(21, 75, 119, .12));
      box-shadow: inset 0 0 18px rgba(38, 167, 255, .10);
      font-size: 13px;
      font-weight: 800;
      letter-spacing: .8px;
    }
    .brand h1 { color: #f1f8fe; font-size: 17px; letter-spacing: .4px; }
    .brand p { margin: 4px 0 0; color: #6f8da6; font-size: 11px; letter-spacing: 1.6px; }
    .topnav {
      height: 100%;
      justify-content: center;
      align-items: stretch;
      gap: 2px;
      flex-wrap: nowrap;
    }
    .topnav button {
      min-width: 94px;
      height: 100%;
      padding: 0 17px;
      position: relative;
      border: 0;
      border-radius: 0;
      color: #8faabe;
      background: transparent;
      box-shadow: none;
      font-size: 14px;
    }
    .topnav button:hover:not(:disabled) {
      color: #d9efff;
      background: rgba(38, 167, 255, .07);
      border: 0;
      box-shadow: none;
      transform: none;
    }
    .topnav button.active {
      color: #eaf7ff;
      border: 0;
      background: linear-gradient(180deg, rgba(38, 167, 255, .11), rgba(38, 167, 255, .02));
    }
    .topnav button.active::after {
      content: "";
      position: absolute;
      height: 3px;
      left: 18px;
      right: 18px;
      bottom: 0;
      border-radius: 3px 3px 0 0;
      background: #31b3ff;
      box-shadow: 0 0 12px rgba(49, 179, 255, .75);
    }
    .header-actions { display: flex; align-items: center; justify-content: flex-end; gap: 7px; }
    .header-actions button { min-height: 34px; padding: 6px 10px; font-size: 12px; white-space: nowrap; }
    .status {
      max-width: 190px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      color: #7896ad;
      font-size: 12px;
    }
    .sidebar-toggle-btn {
      position: static;
      min-width: 94px;
      height: 34px;
      padding: 6px 10px;
      display: inline-flex;
      box-shadow: none;
      border-radius: 6px;
      font-size: 12px;
    }
    .layout {
      height: calc(100vh - 70px);
      min-height: 650px;
      grid-template-columns: 306px minmax(0, 1fr);
      transition: grid-template-columns .25s ease;
    }
    aside {
      border-right: 1px solid #1d3852;
      background:
        linear-gradient(180deg, rgba(19, 43, 67, .64), rgba(9, 24, 40, .94)),
        #0a1727;
      scrollbar-color: #2d526e transparent;
    }
    .side-head {
      padding: 15px 13px 13px;
      border-bottom: 1px solid var(--line-soft);
      gap: 11px;
      background: rgba(9, 23, 39, .66);
      backdrop-filter: blur(8px);
      position: sticky;
      top: 0;
      z-index: 3;
    }
    .side-title { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
    .side-title > div { display: grid; gap: 3px; }
    .side-title strong { color: #e8f4fc; font-size: 14px; }
    .side-title span:not(.live-badge) { color: #708da5; font-size: 11px; }
    .live-badge {
      padding: 3px 8px;
      border: 1px solid rgba(53, 212, 154, .38);
      border-radius: 999px;
      color: #63e2b3;
      background: rgba(53, 212, 154, .09);
      font-size: 11px;
    }
    .summary { gap: 7px; }
    .metric {
      position: relative;
      overflow: hidden;
      border: 1px solid #203d59;
      border-radius: 7px;
      background: linear-gradient(155deg, rgba(25, 58, 87, .88), rgba(11, 29, 47, .92));
      box-shadow: inset 0 1px rgba(255,255,255,.025);
    }
    .metric::after {
      content: "";
      position: absolute;
      right: -12px;
      bottom: -14px;
      width: 38px;
      height: 38px;
      border-radius: 50%;
      background: rgba(38, 167, 255, .07);
    }
    .metric strong { color: #eef9ff; font-weight: 720; letter-spacing: .3px; }
    .metric span { color: #7895ac; }
    .side-tabs { gap: 7px; }
    .side-tabs button { min-height: 32px; padding: 5px 9px; }
    .side-tabs button.active { background: rgba(38, 167, 255, .14); color: #78cbff; border-color: #278ed0; }
    .legend {
      color: #718ba0;
      background: rgba(13, 35, 56, .72);
      border: 1px solid rgba(53, 88, 116, .50);
    }
    .tree { padding: 7px 10px 24px; }
    .group { border-bottom-color: rgba(82, 123, 155, .16); }
    .group-title { color: #9bb6ca; font-size: 12px; letter-spacing: .3px; }
    .device-row {
      color: #bed1df;
      border: 1px solid transparent;
      padding: 8px 7px;
      border-radius: 6px;
    }
    .device-row:hover, .device-row.active {
      border-color: rgba(38, 167, 255, .25);
      background: rgba(38, 167, 255, .09);
      box-shadow: none;
      transform: none;
    }
    .muted { color: #6f899e; }
    .gps-city { color: #ff8c91; }
    .wh-city { color: #45d89b; }
    .ok { color: #43dba2; }
    .off { color: #ff7780; }
    main {
      padding: 15px;
      background:
        linear-gradient(rgba(51, 110, 154, .025) 1px, transparent 1px) 0 0/32px 32px,
        linear-gradient(90deg, rgba(51, 110, 154, .025) 1px, transparent 1px) 0 0/32px 32px;
      scrollbar-color: #2d526e transparent;
    }
    .view.active { gap: 11px; align-content: start; }
    .view-heading {
      min-height: 57px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 2px 3px 3px;
    }
    .view-heading > div { display: grid; gap: 3px; }
    .view-heading h2 { color: #edf8ff; font-size: 20px; letter-spacing: .5px; }
    .view-heading p { margin: 0; color: #718ca2; font-size: 12px; }
    .eyebrow { color: #3eacee; font-size: 9px; font-weight: 750; letter-spacing: 2px; }
    .panel {
      border: 1px solid #1c3852;
      border-radius: 8px;
      background: linear-gradient(155deg, rgba(15, 34, 55, .97), rgba(10, 26, 43, .96));
      box-shadow: var(--shadow);
    }
    .panel-head {
      min-height: 47px;
      padding: 10px 13px;
      border-bottom: 1px solid rgba(76, 123, 158, .20);
      background: rgba(20, 47, 72, .30);
    }
    .panel-head h2 {
      color: #dfeef8;
      font-size: 15px;
    }
    .panel-head h2::before {
      content: "";
      display: inline-block;
      width: 3px;
      height: 14px;
      margin-right: 8px;
      border-radius: 2px;
      vertical-align: -2px;
      background: #2fb2ff;
      box-shadow: 0 0 9px rgba(47, 178, 255, .55);
    }
    .panel-body { padding: 13px; }
    .workbench-top { grid-template-columns: minmax(410px, .9fr) minmax(330px, 1.35fr); gap: 10px; }
    .workbench-card {
      padding: 11px;
      border: 1px solid #203c57;
      border-radius: 7px;
      background: rgba(11, 29, 47, .80);
    }
    .workbench-card h3 { color: #9fb9cc; margin-bottom: 8px; }
    .workbench-metrics { gap: 7px; }
    .workbench-metrics .metric { padding: 9px 10px; }
    .workbench-metrics .metric strong { color: #f1f9ff; font-size: 20px; }
    .compact-city-buttons { max-height: 64px; gap: 6px; }
    .compact-city-buttons button { background: #10263c; color: #a9c2d5; border-color: #27455f; }
    .toolbar { gap: 7px; }
    .query-toolbar {
      padding: 10px;
      border: 1px solid rgba(59, 103, 137, .38);
      border-radius: 7px;
      background: rgba(7, 20, 34, .52);
    }
    .player-bar {
      border-color: #28435d;
      background: linear-gradient(90deg, rgba(22, 61, 91, .60), rgba(11, 29, 47, .72));
      color: #aac0d1;
    }
    .player-bar strong { color: #e2f3ff; }
    .player-bar span { color: #7691a6; }
    .player-wrap { border: 1px solid #1c3349; background: #03070c; box-shadow: inset 0 0 28px rgba(0,0,0,.45); }
    .player-side { background: #08121e; }
    .map-shell { grid-template-columns: minmax(0, 1fr) 280px; }
    .map-side {
      border-left-color: #213c55;
      color: #a9bfd0;
      background: rgba(9, 25, 42, .96);
    }
    .map-side h3 { color: #d4e6f2; }
    .layer-list label { color: #9cb5c8; }
    table { color: #b7cad9; }
    th, td { border-bottom-color: rgba(73, 113, 144, .20); }
    th {
      color: #8faabe;
      background: #10243a;
      position: sticky;
      top: 0;
      z-index: 2;
    }
    tbody tr { transition: background .16s; }
    tbody tr:hover { background: rgba(38, 167, 255, .055); }
    pre {
      border-color: #233f59;
      color: #aac0d0;
      background: #091727;
    }
    .error { border-color: rgba(255, 104, 116, .45); background: rgba(87, 24, 31, .34); color: #ffb2b8; }
    .pager { color: #7994a9; }
    .flight-summary { color: #7f9aaf; }
    .flight-status { background: #182b3c; color: #a4b7c6; }
    .flight-status.normal { background: rgba(53, 212, 154, .12); color: #62dfb0; }
    .flight-status.delay { background: rgba(255, 104, 116, .12); color: #ff9199; }
    .flight-status.cancel { background: rgba(136, 157, 174, .12); color: #99adbc; }
    .flight-detail-grid > div {
      border-color: #233f59;
      background: #0b1b2c;
    }
    .flight-detail-grid label { color: #7892a6; }
    .routine-status { background: #172c40; color: #a6bbca; }
    .routine-status.pending { background: rgba(246, 189, 75, .12); color: #f5c866; }
    .routine-status.working { background: rgba(38, 167, 255, .13); color: #6dc6ff; }
    .routine-status.done { background: rgba(53, 212, 154, .12); color: #62dfb0; }
    .routine-flow span { background: #14293d; color: #829aae; }
    .routine-flow span.done { background: rgba(53, 212, 154, .12); color: #62dfb0; }
    .routine-flow span.current { background: #1188d2; color: #fff; }
    .flight-ref-head { color: #90aabd; }
    .flight-ref-item { border-top-color: #27435b; }
    .flight-ref-item strong { color: #62c2fb; }
    .flight-ref-meta { color: #7895a9; }
    .flight-ref-reason { color: #d9b45d; }
    .flight-ref-empty { color: #627e93; }
    .leaflet-control-zoom a,
    .leaflet-control-layers {
      color: #dcecf7 !important;
      background: #0d2032 !important;
      border-color: #294861 !important;
    }
    .leaflet-popup-content-wrapper, .leaflet-popup-tip { background: #0d2032; color: #dcecf7; }
    .login-screen {
      background:
        linear-gradient(rgba(31, 104, 153, .07) 1px, transparent 1px) 0 0/42px 42px,
        linear-gradient(90deg, rgba(31, 104, 153, .07) 1px, transparent 1px) 0 0/42px 42px,
        radial-gradient(circle at 22% 22%, rgba(26, 131, 198, .30), transparent 31%),
        linear-gradient(145deg, #050c17, #0a1c2e 62%, #07111f);
    }
    .login-card {
      width: min(430px, 94vw);
      border: 1px solid #264966;
      border-radius: 10px;
      color: var(--text);
      background: rgba(9, 24, 40, .96);
      box-shadow: 0 28px 70px rgba(0, 0, 0, .48), inset 0 1px rgba(255,255,255,.035);
    }
    .login-card::before {
      content: "JDAIR · INSPECTION";
      color: #2faaf3;
      font-size: 10px;
      font-weight: 750;
      letter-spacing: 2.2px;
    }
    .login-card h2 { color: #eff8ff; }
    .login-card p { color: #7892a6; }
    .login-form label { color: #9eb5c7; }
    .login-error { color: #ff8f97; }

    @media (max-width: 1280px) {
      .app-header { grid-template-columns: 282px minmax(360px, 1fr) auto; gap: 10px; padding: 0 12px; }
      .topnav button { min-width: 82px; padding: 0 10px; }
      .status { display: none; }
      .layout { grid-template-columns: 280px minmax(0, 1fr); }
      .workbench-top { grid-template-columns: 1fr; }
    }
    @media (max-width: 980px) {
      .app-header {
        height: auto;
        min-height: 112px;
        display: grid;
        grid-template-columns: 1fr auto;
        padding: 9px 10px 0;
        gap: 7px 10px;
      }
      .brand { min-width: 0; }
      .brand p { display: none; }
      .header-actions { min-width: 0; }
      .header-actions button { min-width: 0; }
      .topnav {
        grid-column: 1 / -1;
        order: 3;
        height: 48px;
        justify-content: flex-start;
        overflow-x: auto;
      }
      .topnav button { height: 48px; flex: 0 0 auto; }
      .layout, .layout:has(> aside.collapsed) {
        height: calc(100dvh - 112px);
        min-height: 560px;
        display: block;
      }
      aside {
        inset: 112px auto 0 0;
        width: min(88vw, 306px);
        padding-top: 0;
        z-index: 2050;
        box-shadow: 8px 0 28px rgba(0,0,0,.48);
      }
      aside.collapsed { width: min(88vw, 306px) !important; }
      main { height: 100%; overflow: auto; }
      .map-shell { grid-template-columns: 1fr; }
      .map-side { border-left: 0; border-top: 1px solid #213c55; }
    }
    @media (max-width: 640px) {
      .app-header { min-height: 116px; padding: 8px 8px 0; }
      .brand-mark { width: 32px; height: 32px; flex-basis: 32px; }
      .brand h1 { width: auto; font-size: 14px; text-align: left; }
      .header-actions { gap: 4px; }
      .header-actions button { padding: 5px 7px; font-size: 11px; }
      .header-actions .danger { display: none; }
      .topnav { height: 50px; }
      .topnav button { height: 50px; min-height: 50px; padding: 0 12px; }
      .layout, .layout:has(> aside.collapsed) { min-height: calc(100dvh - 116px); }
      aside { inset: 116px auto 0 0; }
      main { padding: 8px; }
      .view-heading { min-height: 50px; align-items: flex-start; }
      .view-heading h2 { font-size: 18px; }
      .view-heading p { display: none; }
      .query-toolbar { padding: 8px; }
      .workbench-metrics { grid-template-columns: repeat(2, 1fr); }
      .panel { border-radius: 7px; }
    }
</style>
</head>
<body>
<div id="loginScreen" class="login-screen">
  <section class="login-card">
    <div>
      <h2>维修质量安全监察登录</h2>
      <p>仅供内部使用，请勿泄露账号密码。</p>
    </div>
    <form id="loginForm" class="login-form">
      <label>用户名
        <input id="loginUser" autocomplete="username" placeholder="例如 lijian.1023">
      </label>
      <label>密码
        <input id="loginPass" type="password" autocomplete="current-password" placeholder="请输入 MCS8 密码">
      </label>
      <div class="login-actions">
        <button id="loginBtn" type="submit">登录系统</button>
      </div>
      <div id="loginError" class="login-error"></div>
    </form>
  </section>
</div>
<header class="app-header">
  <div class="brand">
    <span class="brand-mark" aria-hidden="true">JD</span>
    <div>
      <h1>维修质量安全监察平台</h1>
      <p>视频记录与运行保障</p>
    </div>
  </div>
  <nav class="topnav" aria-label="主功能导航">
    <button id="nav-dashboard" class="active" onclick="showView('dashboard')">监察工作台</button>
    <button id="nav-map" onclick="showView('map')">指挥调度</button>
    <button id="nav-flights" onclick="showView('flights')">航班动态</button>
    <button id="nav-routine" onclick="showView('routine')">例行任务</button>
  </nav>
  <div class="header-actions">
    <div id="status" class="status"></div>
    <button id="sidebarToggle" class="sidebar-toggle-btn ghost" onclick="toggleSidebar()" aria-expanded="true" aria-controls="sidebar">一键折叠 ◀</button>
    <button class="ghost" onclick="loadAll()">刷新数据</button>
    <button class="ghost danger" onclick="logoutMcs8()">退出</button>
  </div>
</header>
<div class="layout">
  <aside id="sidebar">
    <div class="side-head">
      <div class="side-title">
        <div>
          <strong>终端设备</strong>
          <span>设备状态与位置索引</span>
        </div>
        <span class="live-badge">实时</span>
      </div>
      <div class="summary">
        <div class="metric"><strong id="metricTotal">0</strong><span>设备</span></div>
        <div class="metric"><strong id="metricOnline">0</strong><span>在线</span></div>
        <div class="metric"><strong id="metricMapped">0</strong><span>定位</span></div>
      </div>
      <input id="deviceSearch" placeholder="设备编号、名称、城市、仓库" oninput="renderDeviceTree();renderMap();renderDispatchTable()">
      <div class="legend"><span><span class="dot-gps"></span>GPS定位地址</span><span><span class="dot-wh"></span>工具库存地址</span></div>
      <div class="side-tabs">
        <button id="filterAll" class="secondary active" onclick="setOnlineFilter('all')">不限</button>
        <button id="filterOnline" class="secondary" onclick="setOnlineFilter('online')">在线</button>
      </div>
    </div>
    <div id="deviceTree" class="tree"></div>
  </aside>
  <main>
    <section id="view-map" class="view">
      <div class="view-heading">
        <div><span class="eyebrow">COMMAND CENTER</span><h2>指挥调度</h2></div>
        <p>查看设备位置、在线状态与历史轨迹</p>
      </div>
      <div class="panel">
        <div class="panel-head">
          <h2>设备定位</h2>
        </div>
        <div class="map-shell">
          <div id="map" class="map"></div>
          <div class="map-side">
            <h3>地图图层</h3>
            <div class="layer-list">
              <label><input type="radio" name="layer" value="gaode_vec" checked onchange="switchMapLayer(this.value)"> 高德地图</label>
              <label><input type="radio" name="layer" value="gaode_img" onchange="switchMapLayer(this.value)"> 高德影像</label>
              
            </div>
            <h3>调度状态</h3>
            <pre id="mapInfo">请选择设备或工具。</pre>
            <h3>历史轨迹</h3>
            <div class="track-controls">
              <input id="trackDev" placeholder="设备编号">
              <input id="trackStart" type="datetime-local">
              <input id="trackEnd" type="datetime-local">
              <div class="track-actions">
                <button onclick="loadGpsTrack()">查询轨迹</button>
                <button class="secondary" onclick="clearGpsTrack()">清除</button>
              </div>
            </div>
            <pre id="trackInfo">选择设备后可查询历史 GPS 轨迹。</pre>
          </div>
        </div>
      </div>
      <div class="panel">
        <div class="panel-head">
          <h2>设备调度状态表</h2>
          <div class="muted">GPS 城市为本地近似识别，最后上线优先取最近日志时间，其次取 GPS 时间。</div>
        </div>
        <div class="panel-body dispatch-wrap">
          <table>
            <thead><tr><th>状态</th><th>设备编号</th><th>设备名称</th><th>组</th><th>GPS城市</th><th>仓库</th><th>GPS</th><th>GPS时间</th><th>最后上线</th><th>视频</th><th>操作</th></tr></thead>
            <tbody id="dispatchTable"></tbody>
          </table>
        </div>
      </div>
    </section>

    <section id="view-dashboard" class="view active">
      <div class="view-heading">
        <div><span class="eyebrow">INSPECTION OVERVIEW</span><h2>监察工作台</h2></div>
        <p>设备运行概览与视频记录集中查询</p>
      </div>
      <div class="panel">
        <div class="panel-body workbench-top">
          <div class="workbench-card">
            <h3>设备情况</h3>
            <div class="workbench-metrics">
              <div class="metric"><strong id="dashTotalDev">0</strong><span>设备总数</span></div>
              <div class="metric"><strong id="dashOnlineDev">0</strong><span>在线设备</span></div>
              <div class="metric"><strong id="dashOfflineDev">0</strong><span>离线设备</span></div>
              <div class="metric"><strong id="dashCities">0</strong><span>覆盖城市</span></div>
            </div>
          </div>
          <div class="workbench-card">
            <h3>快捷查询城市视频 <span id="dashRefreshTimer" style="font-size:12px;color:#607386;font-weight:normal;"></span></h3>
            <div id="dashCityBtns" class="compact-city-buttons"></div>
          </div>
        </div>
      </div>
      <div class="panel">
        <div class="panel-head">
          <h2>视频记录查询</h2>
          <div class="toolbar">
            <button class="secondary active" id="tabPlatform" onclick="setFileMode('platform')">平台文件</button>
            <button class="secondary" id="tabDevice" onclick="setFileMode('device')">设备文件</button>
          </div>
        </div>
        <div class="panel-body" style="display:flex;flex-direction:column;gap:10px;">
          <div id="playerBar" class="player-bar">
            <div><strong>视频播放区</strong><span id="playerStateText">未播放视频，播放窗口已隐藏</span></div>
            <button class="secondary" id="togglePlaylistBtn" onclick="togglePlaylistPanel()">展开播放列表</button>
          </div>
          <div id="playerWrap" class="player-wrap player-empty playlist-collapsed">
            <div id="multiPlayer" class="player-grid" style="grid-template-columns:1fr;"></div>
            <div id="playerResizeHandle" class="player-resizer" title="拖动调整播放区和播放列表宽度"></div>
            <div id="playerSide" class="player-side">
              <div style="display:flex;justify-content:space-between;align-items:center;">
                <h3>播放列表</h3>
                <button class="secondary" onclick="clearMultiPlayer()" style="font-size:11px;padding:3px 6px;">清空</button>
              </div>
              <div id="playlist" style="flex:1;overflow-y:auto;"></div>
              <div style="padding:4px;border-top:1px solid #2a3540;">
                <span id="playerCount" style="font-size:11px;color:#6a7a8a;display:block;text-align:center;margin-top:3px;"></span>
              </div>
            </div>
          </div>
          <div id="fileInfo" style="font-size:13px;color:#607386;">点击“高清播放”可直接连接视频原存储地址；也可添加多个视频到列表。</div>
          <div class="file-bottom">
            <div>
              <div class="toolbar query-toolbar">
                <select id="timePreset" onchange="applyPreset()">
                  <option value="today">今天</option>
                  <option value="3d" selected>近3天</option>
                  <option value="custom">自定义</option>
                </select>
                <select id="timeType">
                  <option value="shoot">拍摄时间</option>
                  <option value="upload">上传时间</option>
                </select>
                <input id="start" type="datetime-local" step="1" onchange="byId('timePreset').value='custom'">
                <input id="end" type="datetime-local" step="1" onchange="byId('timePreset').value='custom'">
                <select id="fileCity" onchange="recordPage=1;loadRecords()" style="min-width:80px;">
                  <option value="">全部城市</option>
                </select>
                <button class="secondary" onclick="resetRecordFilters()">重置</button>
                <select id="fileGroup" onchange="recordPage=1;loadRecords()">
                  <option value="">全部分组</option>
                </select>
                <input id="dev" placeholder="设备编号或名称" onkeydown="if(event.key==='Enter'){recordPage=1;loadRecords()}">
                <select id="pageSize" onchange="recordPage=1;loadRecords()">
                  <option value="25" selected>25 条</option>
                  <option value="50">50 条</option>
                  <option value="100">100 条</option>
                </select>
                <button onclick="recordPage=1;loadRecords()">查 询</button>
              </div>
              <div class="records-wrap">
                <table class="records-table">
                  <thead><tr><th>设备编号</th><th>设备名称</th><th>文件标题</th><th>文件类型</th><th>大小/时长</th><th>拍摄时间</th><th>上传时间</th><th>参考信息</th><th>操作</th></tr></thead>
                  <tbody id="records"></tbody>
                </table>
              </div>
              <div class="pager">
                <button class="secondary" id="prevPage" onclick="changeRecordPage(-1)">上一页</button>
                <span id="pageInfo">第 1 页</span>
                <button class="secondary" id="nextPage" onclick="changeRecordPage(1)">下一页</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section id="view-flights" class="view">
      <div class="view-heading">
        <div><span class="eyebrow">FLIGHT OPERATION</span><h2>航班动态</h2></div>
        <p>按日期和航班条件检索运行动态</p>
      </div>
      <div class="panel">
        <div class="panel-head">
          <h2>航班动态</h2>
          <div class="flight-summary">
            <span id="flightTotal">共 0 条</span>
            <span id="flightUpdated">尚未查询</span>
          </div>
        </div>
        <div class="panel-body">
          <div class="toolbar query-toolbar" style="margin-bottom:12px;">
            <input id="flightDate" type="date">
            <input id="flightKeyword" style="width:260px;" placeholder="搜索机号、航班号、出发或到达" onkeydown="if(event.key==='Enter'){flightPage=1;loadFlights()}">
            <select id="flightCategory">
              <option value="0">全部航班</option>
              <option value="1">国内航班</option>
              <option value="2">国际航班</option>
            </select>
            <select id="flightPageSize" onchange="flightPage=1;loadFlights()">
              <option value="20" selected>20 条</option>
              <option value="50">50 条</option>
              <option value="100">100 条</option>
            </select>
            <button onclick="flightPage=1;loadFlights()">查询</button>
            <button class="secondary" onclick="resetFlightSearch()">今天</button>
          </div>
          <div class="flight-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>类别</th><th>机号</th><th>航班号</th><th>出发</th><th>到达</th>
                  <th>计/实飞</th><th>计/实达</th><th>状态</th><th>DD</th><th>FC</th><th>非维修</th><th>操作</th>
                </tr>
              </thead>
              <tbody id="flightRows"><tr><td colspan="12"><pre>请选择日期后查询。</pre></td></tr></tbody>
            </table>
          </div>
          <div class="pager">
            <button class="secondary" id="flightPrev" onclick="changeFlightPage(-1)">上一页</button>
            <span id="flightPageInfo">第 1 页</span>
            <button class="secondary" id="flightNext" onclick="changeFlightPage(1)">下一页</button>
          </div>
        </div>
      </div>
      <div class="panel" id="flightDetailPanel" style="display:none;">
        <div class="panel-head">
          <h2>航班详情</h2>
          <button class="secondary" onclick="byId('flightDetailPanel').style.display='none'">关闭</button>
        </div>
        <div class="panel-body" id="flightDetail"></div>
      </div>
    </section>

    <section id="view-routine" class="view">
      <div class="view-heading">
        <div><span class="eyebrow">ROUTINE TASKS</span><h2>例行任务</h2></div>
        <p>按日期、机号、站点和任务状态统一筛选</p>
      </div>
      <div class="panel">
        <div class="panel-head">
          <h2>例行任务</h2>
          <div class="flight-summary">
            <span id="routineTotal">共 0 条</span>
            <span id="routineUpdated">尚未查询</span>
          </div>
        </div>
        <div class="panel-body">
          <div class="toolbar query-toolbar" style="margin-bottom:12px;">
            <button class="secondary" onclick="shiftRoutineDate(-1)">前一天</button>
            <input id="routineDate" type="date" onchange="routinePage=1;loadRoutineTasks()">
            <button class="secondary" onclick="resetRoutineSearch()">今天</button>
            <button class="secondary" onclick="shiftRoutineDate(1)">后一天</button>
            <input id="routineKeyword" style="width:150px;" placeholder="搜索航班号" onkeydown="if(event.key==='Enter'){routinePage=1;loadRoutineTasks()}">
            <select id="routineAcno" onchange="routinePage=1;loadRoutineTasks()">
              <option value="">全部机号</option>
            </select>
            <select id="routineSite" onchange="routinePage=1;loadRoutineTasks()">
              <option value="">全部站点</option>
            </select>
            <select id="routineCategory" onchange="routinePage=1;loadRoutineTasks()">
              <option value="0">全部任务</option>
              <option value="1">国内任务</option>
              <option value="2">国际任务</option>
            </select>
            <select id="routineTaskType" onchange="routinePage=1;loadRoutineTasks()">
              <option value="">全部类型</option>
              <option value="AP">航前</option>
              <option value="TR">过站</option>
              <option value="AF">航后</option>
              <option value="GZ">日检</option>
              <option value="AOG">停场</option>
            </select>
            <select id="routineAcType" onchange="routinePage=1;loadRoutineTasks()">
              <option value="">全部机型</option>
              <option value="B737NG">B737NG</option>
              <option value="A330">A330</option>
            </select>
            <select id="routineStatus" onchange="routinePage=1;loadRoutineTasks()">
              <option value="">全部状态</option>
              <option value="0">待派工</option>
              <option value="1">待确认</option>
              <option value="2">生产准备</option>
              <option value="4">待到位</option>
              <option value="5">重复检查</option>
              <option value="6">航材工具清点</option>
              <option value="7">待放行</option>
              <option value="8">已放行</option>
              <option value="9">已交接</option>
            </select>
            <select id="routinePageSize" onchange="routinePage=1;loadRoutineTasks()">
              <option value="20" selected>20 条</option>
              <option value="50">50 条</option>
              <option value="100">100 条</option>
            </select>
            <button onclick="routinePage=1;loadRoutineTasks()">查询</button>
            <button class="secondary" onclick="clearRoutineFilters()">清除筛选</button>
          </div>
          <div class="flight-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>任务类型</th><th>机号/机型</th><th>进港航班/时间</th><th>出港航班/时间</th>
                  <th>机位</th><th>计划开始</th><th>状态</th><th>维修人员</th><th>放行人员</th>
                  <th>包/FC/DD/NRC</th><th>操作</th>
                </tr>
              </thead>
              <tbody id="routineRows"><tr><td colspan="11"><pre>请选择日期后查询。</pre></td></tr></tbody>
            </table>
          </div>
          <div class="pager">
            <button class="secondary" id="routinePrev" onclick="changeRoutinePage(-1)">上一页</button>
            <span id="routinePageInfo">第 1 页</span>
            <button class="secondary" id="routineNext" onclick="changeRoutinePage(1)">下一页</button>
          </div>
        </div>
      </div>
      <div class="panel" id="routineDetailPanel" style="display:none;">
        <div class="panel-head">
          <h2>例行任务详情</h2>
          <button class="secondary" onclick="byId('routineDetailPanel').style.display='none'">关闭</button>
        </div>
        <div class="panel-body" id="routineDetail"></div>
      </div>
    </section>
  </main>
</div>

<script>
const byId = id => document.getElementById(id);
let devices = [];
let selectedDev = "";
let onlineFilter = "all";
let fileMode = "platform";
let playlist = [];
let playlistExpanded = false;
let recordPage = 1;
let recordTotal = 0;
let flightPage = 1;
let flightTotal = 0;
let flightsLoaded = false;
let routinePage = 1;
let routineTotal = 0;
let routineLoaded = false;
let recordReferenceGeneration = 0;
let recordsLoaded = false;
let deviceVideoStats = {};
let leafletMap = null;
let leafletLayer = null;
let leafletTrackLayer = null;
let appStarted = false;


let gpsTrack = null;
let operationalRefreshTimer = null;

const APP_BASE = location.pathname === "/demo" || location.pathname.startsWith("/demo/") ? "/demo" : "";
function appUrl(path) {
  const normalized = String(path || "");
  return APP_BASE + (normalized.startsWith("/") ? normalized : "/" + normalized);
}

function showLogin(message) {
  const screen = byId("loginScreen");
  if (screen) screen.classList.remove("hidden");
  if (message) byId("loginError").textContent = message;
}

function hideLogin() {
  const screen = byId("loginScreen");
  if (screen) screen.classList.add("hidden");
  byId("loginError").textContent = "";
}

async function checkAuthSession() {
  try {
    const r = await fetch(appUrl("/api/auth/session"), {cache: "no-store"});
    const data = await r.json();
    if (data && data.authenticated) {
      byId("status").textContent = "已登录：" + (data.username || "");
      hideLogin();
      return true;
    }
  } catch (err) {
    console.warn("auth check failed", err);
  }
  showLogin("");
  return false;
}

async function loginMcs8(event) {
  if (event) event.preventDefault();
  const btn = byId("loginBtn");
  const errEl = byId("loginError");
  const username = String(byId("loginUser").value || "").trim();
  const password = String(byId("loginPass").value || "");
  if (!username || !password) {
    errEl.textContent = "请输入用户名和密码";
    return;
  }
  btn.disabled = true;
  errEl.textContent = "正在连接 MCS8...";
  try {
    const r = await fetch(appUrl("/api/login"), {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({username, password})
    });
    const data = await r.json();
    if (!r.ok || !data.ok) throw new Error(data.message || data.error || "登录失败");
    byId("loginPass").value = "";
    byId("status").textContent = "已登录：" + ((data.session && data.session.username) || username);
    hideLogin();
    startApp();
  } catch (err) {
    errEl.textContent = err.message || String(err);
  } finally {
    btn.disabled = false;
  }
}

async function logoutMcs8() {
  try {
    await fetch(appUrl("/api/logout"), {method: "POST"});
  } catch (err) {}
  location.reload();
}

async function startApp() {
  if (appStarted) return;
  appStarted = true;
  await loadAll();
  operationalRefreshTimer = setInterval(function() {
    loadSummary();
    loadDevices();
  }, 30000);
}

async function initAuth() {
  if (byId("loginForm")) byId("loginForm").addEventListener("submit", loginMcs8);
  if (await checkAuthSession()) startApp();
}

const pad = n => String(n).padStart(2, "0");
const fmt = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
const fmtDateTimeLocal = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;

function apiDateTimeValue(id) {
  const raw = String(byId(id).value || "").trim();
  if (!raw) return "";
  const value = raw.replace("T", " ");
  return /^\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}$/.test(value) ? value + ":00" : value;
}

function recordCityNames(d) {
  const set = new Set();
  if (d && d.city) set.add(d.city);
  const recent = (d && d.recentCities) || [];
  for (var i = 0; i < recent.length; i++) {
    if (recent[i] && recent[i].city) set.add(recent[i].city);
  }
  return Array.from(set);
}

async function getJson(url) {
  const r = await fetch(appUrl(url));
  if (r.status === 401) {
    showLogin("登录已失效，请重新登录");
    throw new Error("请先登录");
  }
  const data = await r.json();
  const remoteOk = data && (data.error === 200 || data.error === "200" || data.enterCode === "200");
  if (!r.ok || (data && data.error && !remoteOk)) throw new Error(data.msg || data.error || r.statusText);
  return data;
}

function esc(v) {
  return String(v ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function hasGps(d) {
  const lng = Number(d.lng), lat = Number(d.lat);
  return Number.isFinite(lng) && Number.isFinite(lat) && Math.abs(lng) > 0.000001 && Math.abs(lat) > 0.000001;
}

function showError(el, err) {
  el.innerHTML = `<pre class="error">${esc(err.message || err)}</pre>`;
}



// Dashboard & city filter functions  
var dashCities = [];

function clearMultiPlayer() {
  document.getElementById("multiPlayer").innerHTML = "";
  updatePlayerCount();
}

function setPlaylistExpanded(expanded) {
  playlistExpanded = !!expanded;
  updatePlayerCount();
}

function togglePlaylistPanel() {
  setPlaylistExpanded(!playlistExpanded);
}

function updatePlayerCount() {
  var n = (document.getElementById("multiPlayer")?.querySelectorAll("video")?.length) || 0;
  var el = document.getElementById("playerCount");
  if (el) el.textContent = n + "个视频";
  var g = document.getElementById("multiPlayer");
  if (!g) return;
  var wrap = document.getElementById("playerWrap");
  var stateText = document.getElementById("playerStateText");
  var toggleBtn = document.getElementById("togglePlaylistBtn");
  g.dataset.count = String(n);
  g.classList.toggle("single-player", n === 1);
  g.classList.toggle("multi-player", n > 1);
  if (wrap) {
    wrap.classList.toggle("player-empty", n === 0);
    wrap.classList.toggle("playlist-expanded", playlistExpanded);
    wrap.classList.toggle("playlist-collapsed", !playlistExpanded);
    wrap.classList.toggle("has-single", n === 1);
    wrap.classList.toggle("has-multi", n > 1);
  }
  if (stateText) {
    stateText.textContent = n
      ? `正在播放 ${n} 个视频${playlistExpanded ? "，播放列表已展开" : "，播放列表已折叠"}`
      : "未播放视频，播放窗口已隐藏";
  }
  if (toggleBtn) {
    toggleBtn.textContent = playlistExpanded ? "折叠播放列表" : "展开播放列表";
  }
  if (n === 0) {
    g.style.gridTemplateColumns = "1fr";
    g.style.gridTemplateRows = "auto";
  } else if (n === 1) {
    g.style.gridTemplateColumns = "1fr";
    g.style.gridTemplateRows = "minmax(540px,1fr)";
  } else if (n === 2) {
    g.style.gridTemplateColumns = "repeat(2,minmax(0,1fr))";
    g.style.gridTemplateRows = "auto";
  } else if (n <= 4) {
    g.style.gridTemplateColumns = "repeat(2,minmax(0,1fr))";
    g.style.gridTemplateRows = "auto";
  } else {
    g.style.gridTemplateColumns = "repeat(3,minmax(0,1fr))";
    g.style.gridTemplateRows = "auto";
  }
  if (wrap && playlistExpanded && n > 0) {
    applyPlayerSideWidth(playerSideWidth, false);
  }
}

var playerSideWidth = 200;
try {
  playerSideWidth = Number(localStorage.getItem("playerSideWidth") || playerSideWidth) || playerSideWidth;
} catch(e) {}

function applyPlayerSideWidth(width, persist) {
  var wrap = byId("playerWrap");
  if (!wrap) return;
  if (wrap.classList.contains("playlist-collapsed") || wrap.classList.contains("player-empty")) {
    wrap.style.removeProperty("--playlist-width");
    return;
  }
  if (window.matchMedia("(max-width: 900px)").matches) {
    wrap.style.removeProperty("--playlist-width");
    return;
  }
  var total = wrap.getBoundingClientRect().width || 0;
  var minSide = 150;
  var maxSide = Math.max(minSide, total - 420);
  var next = Math.min(maxSide, Math.max(minSide, Number(width) || playerSideWidth || 200));
  playerSideWidth = next;
  wrap.style.setProperty("--playlist-width", Math.round(next) + "px");
  if (persist) {
    try { localStorage.setItem("playerSideWidth", String(Math.round(next))); } catch(e) {}
  }
}

function initPlayerResizer() {
  var handle = byId("playerResizeHandle");
  var side = byId("playerSide");
  var wrap = byId("playerWrap");
  if (!handle || !side || !wrap || handle.dataset.bound === "1") return;
  handle.dataset.bound = "1";
  handle.addEventListener("pointerdown", function(e) {
    if (window.matchMedia("(max-width: 900px)").matches) return;
    e.preventDefault();
    var startX = e.clientX;
    var startWidth = side.getBoundingClientRect().width || playerSideWidth;
    handle.classList.add("active");
    wrap.classList.add("resizing");
    try { handle.setPointerCapture(e.pointerId); } catch(err) {}

    function onMove(ev) {
      applyPlayerSideWidth(startWidth - (ev.clientX - startX), false);
    }
    function onUp() {
      handle.classList.remove("active");
      wrap.classList.remove("resizing");
      applyPlayerSideWidth(playerSideWidth, true);
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    }
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  });
  applyPlayerSideWidth(playerSideWidth, false);
}

var dashCountdown = 60;
var dashCountdownTimer = null;

function startDashCountdown() {
  dashCountdown = 60;
  if (dashCountdownTimer) clearInterval(dashCountdownTimer);
  dashCountdownTimer = setInterval(function() {
    dashCountdown--;
    var el = document.getElementById("dashRefreshTimer");
    if (el) el.textContent = dashCountdown > 0 ? (dashCountdown + "s 后刷新") : "加载中...";
    if (dashCountdown <= 0) {
      clearInterval(dashCountdownTimer);
      loadDashboard();
    }
  }, 1000);
}

function loadDashboard() {
  return getJson("/api/dashboard").then(function(data){
    document.getElementById("dashTotalDev").textContent = data.devices.total;
    document.getElementById("dashOnlineDev").textContent = data.devices.online;
    document.getElementById("dashOfflineDev").textContent = data.devices.offline;
    document.getElementById("dashCities").textContent = data.cities.length;
    dashCities = data.cities || [];
    renderDashBtns();
    startDashCountdown();
  }).catch(function(){});
}

function renderDashBtns() {
  var el = document.getElementById("dashCityBtns");
  if (!el) return;
  el.innerHTML = "";
  var citySet = new Set(dashCities || []);
  for (var i = 0; i < devices.length; i++) {
    recordCityNames(devices[i]).forEach(function(city) { citySet.add(city); });
  }
  var allCities = Array.from(citySet).filter(Boolean);
  if (!allCities.length) {
    el.innerHTML = "<span class='muted'>无城市数据</span>";
    return;
  }
  var cityCounts = {};
  for (var i = 0; i < devices.length; i++) {
    recordCityNames(devices[i]).forEach(function(cn) {
      cityCounts[cn] = (cityCounts[cn] || 0) + 1;
    });
  }
  var sorted = allCities.slice().sort(function(a, b) { return (cityCounts[b] || 0) - (cityCounts[a] || 0) || a.localeCompare(b, "zh-CN"); });
  var countReady = devices.length > 0;
  for (var i = 0; i < sorted.length; i++) {
    (function(city) {
      var cnt = cityCounts[city] || 0;
      var btn = document.createElement("button");
      btn.textContent = countReady ? city + " (" + cnt + "\u53f0)" : city;
      btn.onclick = function() { quickCity(city); };
      el.appendChild(btn);
    })(sorted[i]);
  }
}

function quickCity(c) {
  showView("dashboard");
  var sel = document.getElementById("fileCity");
  var devInput = document.getElementById("dev");
  var groupSel = document.getElementById("fileGroup");
  if (devInput) devInput.value = "";
  if (groupSel) groupSel.value = "";
  if (sel) sel.value = c;
  document.getElementById("timePreset").value = "3d";
  applyPreset();
  recordPage = 1;
  loadRecords();
}

function showView(name) {
  document.querySelectorAll(".view").forEach(function(v){v.classList.remove("active");});
  document.querySelectorAll(".topnav button").forEach(function(v){v.classList.remove("active");});
  var el = document.getElementById("view-" + name);
  if (el) el.classList.add("active");
  var btn = document.getElementById("nav-" + name);
  if (btn) btn.classList.add("active");
  if (name === "map" && leafletMap) setTimeout(function(){leafletMap.invalidateSize();},0);
  if (name === "dashboard") { loadDashboard(); if (!recordsLoaded) loadRecords(); }
  if (name === "flights" && !flightsLoaded) { resetFlightSearch(); }
  if (name === "routine" && !routineLoaded) { resetRoutineSearch(); }
}

async function loadHealth() {
  try {
    var data = await getJson("/api/health");
    var user = data.auth && data.auth.authenticated ? data.auth.username : "未登录";
    document.getElementById("status").textContent = data.server.host + ":" + data.server.api_port + " | " + user + " | session " + (data.has_session ? "ok" : "missing");
  } catch (err) {
    document.getElementById("status").textContent = String(err.message || err);
  }
}

async function loadSummary() {
  try {
    var data = await getJson("/api/summary");
    document.getElementById("metricTotal").textContent = data.devices.total;
    document.getElementById("metricOnline").textContent = data.devices.online;
    document.getElementById("metricMapped").textContent = data.devices.mapped;
  } catch(e) {}
}

async function loadDevices() {
  try {
    devices = await getJson("/api/devices");
    if (!selectedDev && devices[0]) selectedDev = devices[0].devId;
    renderDeviceTree();
    populateFileGroups();
    renderDashBtns();
    renderMap();
    renderDispatchTable();
  } catch (err) {
    showError(document.getElementById("deviceTree"), err);
  }
}

function filteredDevices() {
  var q = document.getElementById("deviceSearch").value.trim().toLowerCase();
  return devices.filter(function(d) {
    var hay = (d.devId || "") + " " + (d.name || "") + " " + (d.groupName || "") + " " + (d.roomId || "") + " " + (d.city || "") + " " + (d.warehouse || "");
    var rcs = d.recentCities || [];
    for (var i = 0; i < rcs.length; i++) hay += " " + (rcs[i].city || "");
    return (onlineFilter === "all" || d.online) && (!q || hay.toLowerCase().includes(q));
  });
}

function populateFileGroups() {
  var citySel = document.getElementById("fileCity");
  if (citySel) {
    var curCity = citySel.value;
    var citySet = new Set();
    devices.forEach(function(d) {
      recordCityNames(d).forEach(function(city) { citySet.add(city); });
    });
    var cities = Array.from(citySet).filter(Boolean).sort(function(a, b) { return a.localeCompare(b, "zh-CN"); });
    citySel.innerHTML = "<option value=''>全部城市</option>" + cities.map(function(ct){return "<option value='" + esc(ct) + "'>" + esc(ct) + "</option>";}).join("");
    if (cities.indexOf(curCity) >= 0) citySel.value = curCity;
  }
  var select = document.getElementById("fileGroup");
  var cur = select.value;
  var grps = [...new Set(devices.map(function(d){return d.groupName || d.roomId || "";}).filter(Boolean))].sort();
  select.innerHTML = "<option value=''>全部分组</option>" + grps.map(function(g){return "<option value='" + esc(g) + "'>" + esc(g) + "</option>";}).join("");
  if (grps.indexOf(cur) >= 0) select.value = cur;
}
function renderDeviceTree() {
  const groups = new Map();
  for (const d of filteredDevices()) {
    const g = d.groupName || d.roomId || "未分组";
    if (!groups.has(g)) groups.set(g, []);
    groups.get(g).push(d);
  }
  byId("deviceTree").innerHTML = groups.size ? Array.from(groups.entries()).map(([name, rows]) => `
    <div class="group">
      <div class="group-title"><span>${esc(name)}</span><span class="muted">${rows.filter(d => d.online).length}/${rows.length}</span></div>
      ${rows.map(d => `<button class="device-row ${d.devId === selectedDev ? "active" : ""}" onclick="selectDevice('${encodeURIComponent(d.devId)}')">
        <span><span class="dot ${d.online ? "on" : ""}"></span>${esc(d.name || d.devId || "-")}<br><span class="muted">${esc(d.devId || "")}</span><br>${d.city ? `<span class="gps-city">${esc(d.city)}</span>` : ""}${d.warehouse ? `<br><span class="wh-city">${esc(d.warehouse)}</span>` : ""}${d.recentCities && d.recentCities.length > 1 ? `<br><span class="muted" style="font-size:11px">历史: ${esc(d.recentCities.map(function(c){return c.city;}).join(" > "))}</span>` : ""}</span>
        <span class="${d.online ? "ok" : "off"}">${d.online ? "在线" : "离线"}</span>
      </button>`).join("")}
    </div>`).join("") : `<pre>没有匹配的设备。</pre>`;
}

function setSidebarCollapsed(collapsed) {
  var aside = byId("sidebar");
  var btn = byId("sidebarToggle");
  aside.classList.toggle("collapsed", collapsed);
  btn.textContent = collapsed ? "展开侧栏 ▶" : "一键折叠 ◀";
  btn.setAttribute("aria-expanded", collapsed ? "false" : "true");
  setTimeout(function() { if (leafletMap) leafletMap.invalidateSize(); }, 350);
}

function toggleSidebar() {
  setSidebarCollapsed(!byId("sidebar").classList.contains("collapsed"));
}

function syncSidebarForViewport() {
  const mobile = window.matchMedia("(max-width: 900px)").matches;
  const previous = byId("sidebar").dataset.mobileMode;
  if (previous !== String(mobile)) {
    byId("sidebar").dataset.mobileMode = String(mobile);
    setSidebarCollapsed(mobile);
  }
}

function setOnlineFilter(value) {
  onlineFilter = value;
  byId("filterAll").classList.toggle("active", value === "all");
  byId("filterOnline").classList.toggle("active", value === "online");
  renderDeviceTree();
  renderMap();
  renderDispatchTable();
}

function selectDevice(dev) {
  selectedDev = decodeURIComponent(dev);
  byId("dev").value = selectedDev;
  byId("trackDev").value = selectedDev;
  showView("map");
  renderDeviceTree();
  renderMap();
  renderDispatchTable();
  byId("mapInfo").textContent = deviceInfo(selectedDev);
  var selDev = devices.find(function(x) { return x.devId === selectedDev; });
  if (selDev && hasGps(selDev) && leafletMap) {
    setTimeout(function(){ leafletMap.invalidateSize(); leafletMap.setView([Number(selDev.lat), Number(selDev.lng)], 14); }, 100);
  }
}
function deviceInfo(devId) {
  const d = devices.find(x => x.devId === devId);
  if (!d) return "请选择设备。";
  var info = `设备：${d.name || d.devId}\n编号：${d.devId}\n组：${d.groupName || d.roomId || "-"}\n状态：${d.online ? "在线" : "离线"}\n城市：${d.city || "-"}${d.cityDistanceKm != null ? `（约 ${d.cityDistanceKm} km）` : ""}\nGPS：${d.lng ?? "-"}, ${d.lat ?? "-"}\nGPS时间：${d.gpsTime || "-"}\n最后上线：${d.lastOnlineTime || "-"}`;
  var vs = deviceVideoStats[devId];
  if (vs) {
    info += `\n近3天视频：${vs.count} 个`;
  }
  return info;
}

function renderMap() {
  const rows = filteredDevices().filter(hasGps);
  if (window.L) {
    renderLeafletMap(rows);
    return;
  }
  renderFallbackMap(rows);
}

function renderLeafletMap(rows) {
  const el = byId("map");
  el.classList.add("leaflet-ready");
  if (!leafletMap) {
    el.innerHTML = "";
    leafletMap = L.map(el, { preferCanvas: true, zoomControl: true, attributionControl: false }).setView([32.03, 121.06], 8);
    window.mapLayers = {
      "gaode_vec": L.tileLayer("https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}", { maxZoom: 18, subdomains: ["1","2","3"], attribution: "" }),
      "gaode_img": L.tileLayer("https://webst0{s}.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}", { maxZoom: 18, subdomains: ["1","2","3"], attribution: "" }),

    };
    window.currentLayer = window.mapLayers["gaode_vec"].addTo(leafletMap);
    leafletLayer = L.layerGroup().addTo(leafletMap);
    leafletTrackLayer = L.layerGroup().addTo(leafletMap);
    window.switchMapLayer = function(value) {
      if (window.currentLayer) leafletMap.removeLayer(window.currentLayer);
      window.currentLayer = window.mapLayers[value];
      window.currentLayer.addTo(leafletMap);
    };
    // Monitor layer radio buttons for change
    document.querySelectorAll('input[name="layer"]').forEach(function(el) {
      el.addEventListener("change", function() {
        if (this.checked) switchMapLayer(this.value);
      });
    });
  }
  leafletLayer.clearLayers();
  if (!rows.length) {
    renderGpsTrack();
    byId("mapInfo").textContent = "当前设备没有可用 GPS 点位。";
    return;
  }
  const bounds = [];
  for (const d of rows) {
    const lat = Number(d.lat), lng = Number(d.lng);
    bounds.push([lat, lng]);
    const marker = L.circleMarker([lat, lng], {
      radius: d.devId === selectedDev ? 9 : 7,
      color: d.online ? "#0d6f50" : "#9c3f3f",
      weight: d.devId === selectedDev ? 3 : 2,
      fillColor: d.online ? "#18a66f" : "#c25757",
      fillOpacity: .88
    }).addTo(leafletLayer);
    marker.bindPopup(`<strong>${esc(d.name || d.devId)}</strong><br>编号：${esc(d.devId || "")}<br>状态：${d.online ? "在线" : "离线"}<br>城市：${esc(d.city || "-")}<br>GPS：${lng.toFixed(6)}, ${lat.toFixed(6)}<br>最后上线：${esc(d.lastOnlineTime || "-")}`);
    marker.on("click", () => selectDevice(encodeURIComponent(d.devId)));
    if (d.devId === selectedDev) {
      marker.openPopup();
    }
  }
  if (selectedDev) {
    const sel = rows.find(d => d.devId === selectedDev) || devices.find(d => d.devId === selectedDev);
    if (sel && hasGps(sel)) {
      leafletMap.setView([Number(sel.lat), Number(sel.lng)], 14);
    } else if (bounds.length > 0) {
      leafletMap.fitBounds(bounds, { padding: [28, 28], maxZoom: 14 });
    }
  } else if (bounds.length === 1) {
    leafletMap.setView(bounds[0], 12);
  } else {
    leafletMap.fitBounds(bounds, { padding: [28, 28], maxZoom: 14 });
  }
  renderGpsTrack();
  setTimeout(() => leafletMap.invalidateSize(), 0);
}

function renderFallbackMap(rows) {
  byId("map").classList.remove("leaflet-ready");
  const lngs = rows.map(d => Number(d.lng));
  const lats = rows.map(d => Number(d.lat));
  const minLng = Math.min(...lngs, 0), maxLng = Math.max(...lngs, 1);
  const minLat = Math.min(...lats, 0), maxLat = Math.max(...lats, 1);
  byId("map").innerHTML = rows.map((d, i) => {
    const x = 8 + ((Number(d.lng) - minLng) / Math.max(.000001, maxLng - minLng)) * 84;
    const y = 88 - ((Number(d.lat) - minLat) / Math.max(.000001, maxLat - minLat)) * 76;
    return `<button class="marker" style="left:${x}%;top:${y}%" onclick="selectDevice('${encodeURIComponent(d.devId)}')" title="${esc(d.name || d.devId)}">
      <span class="pin ${d.online ? "on" : ""}"><span>${i + 1}</span></span>
      ${statusLabels ? `<span class="label">${esc(d.name || d.devId)}</span>` : ""}
    </button>`;
  }).join("") || `<pre style="position:absolute;left:20px;top:20px;">当前设备没有可用 GPS 点位。</pre>`;
}

function renderDispatchTable() {
  const rows = filteredDevices();
  byId("dispatchTable").innerHTML = rows.length ? rows.map(d => {
    const cityHtml = d.city ? `<span class="gps-city">${esc(d.city)}</span>${d.cityDistanceKm != null ? ` <span class="muted">/ ${esc(d.cityDistanceKm)}km</span>` : ""}` : `<span class="muted">-</span>`;
    const whHtml = d.warehouse ? `<span class="wh-city">${esc(d.warehouse)}</span>` : `<span class="muted">-</span>`;
    const gps = hasGps(d) ? `${Number(d.lng).toFixed(6)}, ${Number(d.lat).toFixed(6)}` : "-";
    return `<tr class="${d.devId === selectedDev ? "active" : ""}">
      <td><span class="${d.online ? "ok" : "off"}">${d.online ? "在线" : "离线"}</span></td>
      <td>${esc(d.devId || "")}</td>
      <td>${esc(d.name || "")}</td>
      <td>${esc(d.groupName || d.roomId || "-")}</td>
      <td>${cityHtml}</td>
      <td>${whHtml}</td>
      <td>${esc(gps)}</td>
      <td>${esc(d.gpsTime || "-")}</td>
      <td>${esc(d.lastOnlineTime || "-")}</td>
      <td style="text-align:center;color:#287bb6;font-weight:600;">${(function(){var v=deviceVideoStats[d.devId];return v?v.count:"-"})()}</td>
      <td class="toolbar"><button onclick="selectDevice('${encodeURIComponent(d.devId)}')">定位</button><button class="secondary" onclick="openGpsTrack('${encodeURIComponent(d.devId)}')">轨迹</button></td>
    </tr>`;
  }).join("") : `<tr><td colspan="11"><pre>没有匹配的设备。</pre></td></tr>`;
}

function toLocalInput(date) {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

function applyTrackPreset() {
  const end = new Date();
  const start = new Date(end);
  start.setHours(start.getHours() - 24);
  byId("trackStart").value = toLocalInput(start);
  byId("trackEnd").value = toLocalInput(end);
}

function openGpsTrack(dev) {
  selectDevice(dev);
  byId("trackDev").value = decodeURIComponent(dev);
  loadGpsTrack();
}

async function loadGpsTrack() {
  const dev = byId("trackDev").value.trim() || selectedDev;
  if (!dev) return;
  try {
    byId("trackInfo").textContent = "正在查询轨迹...";
    const q = new URLSearchParams({
      dev,
      st: byId("trackStart").value.replace("T", " ") + ":00",
      et: byId("trackEnd").value.replace("T", " ") + ":00",
      maxpoints: "2000"
    });
    gpsTrack = await getJson("/api/gps-track?" + q.toString());
    renderGpsTrack();
    const sampled = gpsTrack.sourceCount > gpsTrack.pointCount ? `，地图抽样 ${gpsTrack.pointCount} 点` : "";
    byId("trackInfo").textContent = `${gpsTrack.deviceName || gpsTrack.devId}\n轨迹点：${gpsTrack.sourceCount}${sampled}\n里程：约 ${gpsTrack.distanceKm} km\n最高速度：${gpsTrack.maxSpeed} km/h\n开始：${gpsTrack.startTime || "-"}\n结束：${gpsTrack.endTime || "-"}`;
  } catch (err) {
    gpsTrack = null;
    showError(byId("trackInfo"), err);
  }
}

function renderGpsTrack() {
  if (!leafletMap || !leafletTrackLayer) return;
  leafletTrackLayer.clearLayers();
  const points = gpsTrack?.points || [];
  if (!points.length) return;
  const latlngs = points.map(point => [Number(point.lat), Number(point.lng)]);
  L.polyline(latlngs, { color: "#e2512f", weight: 4, opacity: .88 }).addTo(leafletTrackLayer);
  const first = points[0], last = points[points.length - 1];
  L.circleMarker(latlngs[0], { radius: 7, color: "#087a49", fillColor: "#12a66d", fillOpacity: 1 })
    .bindPopup(`起点<br>${esc(first.time || "")}`).addTo(leafletTrackLayer);
  L.circleMarker(latlngs[latlngs.length - 1], { radius: 7, color: "#a33434", fillColor: "#dc5b4f", fillOpacity: 1 })
    .bindPopup(`终点<br>${esc(last.time || "")}`).addTo(leafletTrackLayer);
  leafletMap.fitBounds(latlngs, { padding: [30, 30], maxZoom: 16 });
}

function clearGpsTrack() {
  gpsTrack = null;
  if (leafletTrackLayer) leafletTrackLayer.clearLayers();
  byId("trackInfo").textContent = "选择设备后可查询历史 GPS 轨迹。";
  renderMap();
}


function setFileMode(mode) {
  fileMode = mode;
  byId("tabPlatform").classList.toggle("active", mode === "platform");
  byId("tabDevice").classList.toggle("active", mode === "device");
  byId("fileInfo").textContent = mode === "platform"
    ? "平台文件：通过服务器录像接口查询。"
    : "设备文件：当前 SDK 的设备存储枚举接口未实现，先按设备精确查询已上传到平台的录像，并标记为平台回退结果。";
  recordPage = 1;
  loadRecords();
}

function applyPreset() {
  const now = new Date();
  const start = new Date(now);
  if (byId("timePreset").value === "today") start.setHours(0, 0, 0, 0);
  if (byId("timePreset").value === "3d") start.setDate(start.getDate() - 3);
  byId("start").value = fmtDateTimeLocal(start);
  byId("end").value = fmtDateTimeLocal(now);
}

function formatRecordSize(value) {
  const size = Number(value || 0);
  if (!Number.isFinite(size) || size <= 0) return "-";
  return (size / (1024 * 1024)).toFixed(size >= 100 * 1024 * 1024 ? 0 : 1) + " MB";
}

function formatRecordDuration(value) {
  const seconds = Number(value || 0);
  if (!Number.isFinite(seconds) || seconds <= 0) return "-";
  const minutes = seconds / 60;
  return minutes >= 10 ? minutes.toFixed(0) + " min" : minutes.toFixed(1) + " min";
}

function formatRecordMetrics(item) {
  const sizeText = formatRecordSize(item.fileSize || item.fileLen || item.size || 0);
  const durationText = formatRecordDuration(item.duration || item.videoTime || 0);
  if (sizeText === "-" && durationText === "-") return "-";
  if (sizeText === "-") return durationText;
  if (durationText === "-") return sizeText;
  return sizeText + " / " + durationText;
}

function formatRecordMetricsHtml(item) {
  const sizeText = formatRecordSize(item.fileSize || item.fileLen || item.size || 0);
  const durationText = formatRecordDuration(item.duration || item.videoTime || 0);
  if (sizeText === "-" && durationText === "-") return "-";
  if (sizeText === "-") return `<span>${esc(durationText)}</span>`;
  if (durationText === "-") return `<span>${esc(sizeText)}</span>`;
  return `<span>${esc(sizeText)}</span><span>${esc(durationText)}</span>`;
}

function formatRecordTimeHtml(value) {
  const text = String(value || "").trim();
  if (!text) return "-";
  const normalized = text.replace("T", " ");
  const parts = normalized.split(/\\s+/);
  if (parts.length >= 2) {
    return `<span>${esc(parts[0])}</span><span>${esc(parts.slice(1).join(" "))}</span>`;
  }
  return esc(text);
}

function resetRecordFilters() {
  byId("fileCity").value = "";
  byId("fileGroup").value = "";
  byId("dev").value = "";
  recordPage = 1;
  loadRecords();
}

function renderFlightReference(ref) {
  if (!ref || !Array.isArray(ref.candidates) || !ref.candidates.length) {
    const city = ref && ref.city ? esc(ref.city) + " · " : "";
    const reason = ref && ref.reason ? esc(ref.reason) : "暂无可用参考信息";
    return `<div class="flight-ref-empty">${city}${reason}</div>`;
  }
  const head = `<div class="flight-ref-head"><strong>${esc(ref.city || "未知城市")}</strong> · ${esc(ref.certainty || "候选")}</div>`;
  const rows = ref.candidates.map(function(candidate) {
    const timeLine = candidate.timeDisplay
      ? esc(candidate.timeDisplay)
      : `${esc(candidate.departureTime || "--")} · ${esc(candidate.arrivalTime || "--")}`;
    const taskLine = candidate.taskType || candidate.wxWorker || candidate.fxWorker
      ? `<br><span class="flight-ref-meta">任务：${esc(candidate.taskType || "--")}　维修：${esc(candidate.wxWorker || "--")}　放行：${esc(candidate.fxWorker || "--")}</span>`
      : "";
    return `<div class="flight-ref-item">
      <strong>${esc(candidate.acno || "--")} · ${esc(candidate.flightNo || "--")}</strong><br>
      ${esc(candidate.departure || "--")}→${esc(candidate.arrival || "--")}
      ${timeLine ? `<br>${timeLine}` : ""}${taskLine}<br>
      <span class="flight-ref-reason">${esc(candidate.relation || "")}${esc(candidate.minutes)}分钟（${esc(candidate.timeKind || "")}）</span>
    </div>`;
  }).join("");
  return head + rows;
}

async function loadRecordFlightReferences(list, generation) {
  const items = list.map(function(item) {
    return {
      devId: item.devId || item.DevId || item.szIDNO || "",
      title: item.fileName || item.name || item.fileTitle || "",
      startTime: item.startTime || item.fileTime || item.beginTime || "",
      fileTime: item.fileTime || "",
      lat: item.lat ?? item.latitude,
      lng: item.lng ?? item.longitude
    };
  });
  try {
    const response = await fetch(appUrl("/api/record-flight-references"), {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({items: items})
    });
    const payload = await response.json();
    if (response.status === 401) {
      showLogin("登录已失效，请重新登录");
      throw new Error("请先登录");
    }
    if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
    if (generation !== recordReferenceGeneration) return;
    (payload.data || []).forEach(function(ref, index) {
      const cell = document.getElementById(`flight-ref-${generation}-${index}`);
      if (cell) cell.innerHTML = renderFlightReference(ref);
    });
  } catch (err) {
    if (generation !== recordReferenceGeneration) return;
    list.forEach(function(_, index) {
      const cell = document.getElementById(`flight-ref-${generation}-${index}`);
      if (cell) cell.innerHTML = `<div class="flight-ref-empty">参考信息载入失败：${esc(err.message || err)}</div>`;
    });
  }
}

async function loadRecords() {
  try {
    const size = Number(byId("pageSize").value || 25);
    const search = byId("dev").value.trim() || byId("fileGroup").value;
    const q = new URLSearchParams({ st: apiDateTimeValue("start"), et: apiDateTimeValue("end"), q: search, page: recordPage, pagesize: size, mode: fileMode });
    var cityFil = document.getElementById("fileCity");
    if (cityFil && cityFil.value) q.set("city", cityFil.value);
    const data = await getJson("/api/records?" + q.toString());
    const list = data.data || data.Content || data.content || [];
    recordTotal = Number(data.recordsTotal || data.total || list.length || 0);
    const totalPages = Number(data.pages || Math.max(1, Math.ceil(recordTotal / size)));
    byId("pageInfo").textContent = `第 ${recordPage} / ${totalPages} 页，共 ${recordTotal} 条`;
    byId("prevPage").disabled = recordPage <= 1;
    byId("nextPage").disabled = recordPage >= totalPages;
    if (fileMode === "device") {
      byId("fileInfo").textContent = data.deviceFileSupported
        ? "设备文件：已从设备存储返回结果。"
        : `设备文件：厂商 SDK 未实现设备存储枚举；当前展示平台精确查询回退结果。匹配设备 ${data.matchedDevices?.length || 0} 台，平台录像 ${recordTotal} 条。`;
    }
    const referenceGeneration = ++recordReferenceGeneration;
    byId("records").innerHTML = list.length ? list.map((item, index) => {
      const key = item.ossObjctName || item.ossObjectName || item.filePath || item.path || "";
      const dev = item.devId || item.DevId || item.szIDNO || "";
      const title = item.fileName || item.name || item.fileTitle || key || "-";
      return `<tr>
        <td>${esc(dev)}</td><td>${esc(item.deviceName || item.devName || "")}</td><td class="file-title-cell">${esc(title)}</td><td>${esc(item.fileType || item.type || item.fType || "视频/普通文件")}${fileMode === "device" ? " / 平台回退" : ""}</td>
        <td class="metric-cell">${formatRecordMetricsHtml(item)}</td><td class="time-cell">${formatRecordTimeHtml(item.startTime || item.fileTime || item.beginTime || "")}</td><td class="time-cell">${formatRecordTimeHtml(item.uploadTime || item.upLoadTime || item.endTime || "")}</td>
        <td class="flight-ref" id="flight-ref-${referenceGeneration}-${index}"><span class="flight-ref-empty">正在匹配航班…</span></td>
        <td><div class="record-action-buttons">${key ? `<button onclick="playOriginal('${encodeURIComponent(key)}')">高清播放</button><button class="secondary" onclick="addPlaylist(${index}, '${encodeURIComponent(key)}', '${encodeURIComponent(title)}')">添加</button>` : ""}<button class="secondary" onclick="noteRecord('${encodeURIComponent(title)}')">标注</button></div></td>
      </tr>`;
    }).join("") : `<tr><td colspan="9"><pre>${fileMode === "device" ? "没有查到该设备已上传的平台录像。厂商当前 SDK 未实现设备存储文件枚举，离线设备也无法直接读取本机文件。" : "没有查到录像，或当前账号没有返回录像数据。"}</pre></td></tr>`;
    recordsLoaded = true;
    if (list.length) loadRecordFlightReferences(list, referenceGeneration);
  } catch (err) {
    showError(byId("records"), err);
  }
}

function changeRecordPage(delta) {
  const size = Number(byId("pageSize").value || 25);
  const totalPages = Math.max(1, Math.ceil(recordTotal / size));
  recordPage = Math.min(totalPages, Math.max(1, recordPage + delta));
  loadRecords();
}

function addPlaylist(index, key, title) {
  playlist.push({ key: decodeURIComponent(key), title: decodeURIComponent(title) });
  renderPlaylist();
  setPlaylistExpanded(true);
  playOriginal(key);
}

function renderPlaylist() {
  var el = byId("playlist");
  if (!playlist.length) { el.innerHTML = '<div style="color:#556;font-size:12px;padding:8px">暂无视频</div>'; return; }
  el.innerHTML = playlist.map(function(item, idx) {
    return `<div style="display:flex;justify-content:space-between;align-items:center;padding:4px 6px;border-bottom:1px solid #1e2a34;font-size:12px;color:#b0c0d0;"><span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${idx+1}. ${esc(item.title)}</span><button onclick="playOriginal('${encodeURIComponent(item.key)}')" style="font-size:10px;padding:2px 6px;">高清</button></div>`;
  }).join("");
}

function noteRecord(title) {
  byId("fileInfo").textContent = `标注：${decodeURIComponent(title)}。当前先记录入口，后续可接入原系统标注接口。`;
}

function createPlayerShell() {
  var container = byId("multiPlayer");
  var vidId = "vid_" + Date.now() + "_" + Math.floor(Math.random() * 1000);
  var wrapper = document.createElement("div");
  var closeBtn = document.createElement("button");
  var video = document.createElement("video");
  var overlay = document.createElement("div");
  wrapper.className = "player-cell";
  wrapper.id = vidId + "_wrap";
  closeBtn.textContent = "\u00d7";
  closeBtn.style.cssText = "position:absolute;top:4px;right:4px;z-index:20;background:rgba(0,0,0,.6);color:#fff;border:0;border-radius:3px;padding:2px 8px;cursor:pointer;font-size:12px;line-height:1;";
  closeBtn.onclick = function() { if (wrapper.parentNode) wrapper.parentNode.removeChild(wrapper); updatePlayerCount(); };
  overlay.style.cssText = "position:absolute;inset:0;display:flex;align-items:center;justify-content:center;flex-direction:column;color:#aaa;font-size:13px;z-index:10;background:rgba(0,0,0,0.5);";
  overlay.innerHTML = '<div style="font-size:13px;color:#aaa;">正在准备视频...</div>';
  video.id = vidId;
  video.controls = true;
  video.playsInline = true;
  video.setAttribute("playsinline", "");
  video.setAttribute("webkit-playsinline", "");
  video.setAttribute("x5-playsinline", "");
  video.preload = "metadata";
  video.className = "player-video";
  wrapper.appendChild(closeBtn);
  wrapper.appendChild(overlay);
  wrapper.appendChild(video);
  container.appendChild(wrapper);
  updatePlayerCount();
  return { wrapper: wrapper, video: video, overlay: overlay };
}

async function play(key) {
  key = decodeURIComponent(key);
  var shell = createPlayerShell();
  var video = shell.video;
  var overlay = shell.overlay;
  video.muted = true;
  video.preload = "auto";
  var playStarted = false;
  function startPlay() {
    if (playStarted) return;
    playStarted = true;
    video.muted = false;
    video.play().then(function() { overlay.style.display = "none"; }).catch(function() {
      video.muted = true;
      video.play().then(function() { overlay.style.display = "none"; }).catch(function() {});
    });
  }
  video.onloadeddata = function() { startPlay(); };
  video.onerror = function() {
    overlay.innerHTML = '<div style="font-size:16px;color:#c55;">视频加载失败</div><div style="margin-top:8px;font-size:12px;cursor:pointer;color:#aaa;">点击重试</div>';
    overlay.style.display = "flex";
    overlay.onclick = function() {
      overlay.innerHTML = '<div style="font-size:13px;color:#aaa;">加载中...</div>';
      playStarted = false;
      video.src = video.src;
      video.load();
    };
  };
  try {
    var info = await getJson("/api/video-info?key=" + encodeURIComponent(key));
    video.src = appUrl(info.needsTranscode ? "/transcode-video?key=" : "/proxy-video?key=") + encodeURIComponent(key);
    overlay.innerHTML = info.needsTranscode
      ? '<div style="font-size:13px;color:#ddd;">正在转换 H.265 视频，请稍候...</div>'
      : '<div style="font-size:48px;cursor:pointer;line-height:1;margin-bottom:8px;">\u25b6</div><div>点击播放</div>';
    overlay.onclick = function() { startPlay(); };
    video.load();
  } catch (err) {
    overlay.innerHTML = '<div style="font-size:16px;color:#c55;">无法读取视频信息</div>';
  }
};

function playOriginal(key) {
  key = decodeURIComponent(key);
  var shell = createPlayerShell();
  var video = shell.video;
  var overlay = shell.overlay;
  var directUrl = "";
  video.muted = false;
  video.preload = "metadata";

  function refreshDirectUrl() {
    directUrl = appUrl("/play?key=" + encodeURIComponent(key) + "&t=" + Date.now());
    video.src = directUrl;
    video.load();
  }

  function startDirectPlay() {
    overlay.innerHTML = '<div style="font-size:13px;color:#ddd;">正在连接原始高清视频...</div>';
    overlay.style.display = "flex";
    if (!video.src) refreshDirectUrl();
    var promise = video.play();
    if (promise && promise.then) {
      promise.then(function() {
        overlay.style.display = "none";
      }).catch(function() {
        overlay.innerHTML = '<div style="font-size:48px;line-height:1;margin-bottom:8px;">▶</div><div>点击播放原始高清视频</div>';
      });
    }
  }

  video.onplaying = function() { overlay.style.display = "none"; };
  video.onerror = function() {
    overlay.innerHTML = '<div style="font-size:16px;color:#e39a9a;">高清源加载失败</div><div style="margin-top:8px;font-size:12px;">点击重新获取播放地址</div>';
    overlay.style.display = "flex";
    overlay.onclick = function() {
      refreshDirectUrl();
      startDirectPlay();
    };
  };
  overlay.innerHTML = '<div style="font-size:48px;line-height:1;margin-bottom:8px;">▶</div><div>原始画质 · 不占服务器视频带宽</div>';
  overlay.onclick = startDirectPlay;
  refreshDirectUrl();
  startDirectPlay();
  byId("fileInfo").textContent = "高清播放：浏览器直接连接视频原存储地址，云服务器仅提供播放地址跳转。";
}


async function loadDeviceVideoStats() {
  try {
    var stats = await getJson("/api/video-stats");
    deviceVideoStats = stats;
    renderDispatchTable();
    if (selectedDev) {
      byId("mapInfo").textContent = deviceInfo(selectedDev);
    }
  } catch(e) {
    console.error("video stats load failed", e);
  }
}

function flightTime(value) {
  if (!value) return "--";
  var text = String(value);
  return text.length >= 16 ? text.slice(11, 16) : text;
}

function flightStatusClass(status) {
  if (status === "正常") return "normal";
  if (status === "延误" || status === "返航" || status === "备降" || status === "滑回") return "delay";
  if (status === "取消") return "cancel";
  return "";
}

function resetFlightSearch() {
  var now = new Date();
  byId("flightDate").value = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
  byId("flightKeyword").value = "";
  byId("flightCategory").value = "0";
  flightPage = 1;
  loadFlights();
}

async function loadFlights() {
  var rowsEl = byId("flightRows");
  rowsEl.innerHTML = `<tr><td colspan="12"><pre>正在查询航班动态...</pre></td></tr>`;
  try {
    var size = Number(byId("flightPageSize").value || 20);
    var q = new URLSearchParams({
      date: byId("flightDate").value,
      keyword: byId("flightKeyword").value.trim(),
      category: byId("flightCategory").value,
      current: flightPage,
      size: size
    });
    var data = await getJson("/api/flights?" + q.toString());
    var records = data.records || [];
    flightTotal = Number(data.total || 0);
    var pages = Number(data.pages || Math.max(1, Math.ceil(flightTotal / size)));
    byId("flightTotal").textContent = `共 ${flightTotal} 条`;
    byId("flightUpdated").textContent = `更新于 ${new Date().toLocaleTimeString("zh-CN", {hour12:false})}`;
    byId("flightPageInfo").textContent = `第 ${flightPage} / ${pages} 页`;
    byId("flightPrev").disabled = flightPage <= 1;
    byId("flightNext").disabled = flightPage >= pages;
    rowsEl.innerHTML = records.length ? records.map(function(item) {
      return `<tr>
        <td>${item.dorI === "D" ? "国内" : "国际"}</td>
        <td>${esc(item.acno || "--")}</td>
        <td><strong>${esc(item.flightNo || "--")}</strong></td>
        <td>${esc(item.dep3code || item.departureAirport || "--")}</td>
        <td>${esc(item.arr3code || item.arrivalAirport || "--")}</td>
        <td>${esc(flightTime(item.std))} / ${esc(flightTime(item.atd))}</td>
        <td>${esc(flightTime(item.sta))} / ${esc(flightTime(item.ata))}</td>
        <td><span class="flight-status ${flightStatusClass(item.status)}">${esc(item.status || "--")}</span></td>
        <td>${esc(item.dd || 0)}</td>
        <td>${esc(item.fc || 0)}</td>
        <td>${esc(item.nonWork || 0)}</td>
        <td><button class="secondary" onclick="loadFlightDetail('${encodeURIComponent(item.flightId || "")}')">详情</button></td>
      </tr>`;
    }).join("") : `<tr><td colspan="12"><pre>没有查到符合条件的航班。</pre></td></tr>`;
    flightsLoaded = true;
  } catch (err) {
    rowsEl.innerHTML = `<tr><td colspan="12"><pre class="error">${esc(err.message || err)}</pre></td></tr>`;
  }
}

function changeFlightPage(delta) {
  var size = Number(byId("flightPageSize").value || 20);
  var pages = Math.max(1, Math.ceil(flightTotal / size));
  flightPage = Math.min(pages, Math.max(1, flightPage + delta));
  loadFlights();
}

async function loadFlightDetail(encodedId) {
  var flightId = decodeURIComponent(encodedId);
  var panel = byId("flightDetailPanel");
  var target = byId("flightDetail");
  panel.style.display = "block";
  target.innerHTML = `<pre>正在加载航班详情...</pre>`;
  try {
    var data = await getJson("/api/flight-detail?id=" + encodeURIComponent(flightId));
    var fields = [
      ["航班号", data.flightNo], ["机号", data.acno], ["航班日期", data.flightDate],
      ["航段", `${data.dep3code || "--"} → ${data.arr3code || "--"}`],
      ["计划起飞", data.std], ["实际起飞", data.atd],
      ["计划到达", data.sta], ["实际到达", data.ata],
      ["状态", data.flightStatus || data.status], ["国内/国际", data.dorI === "D" ? "国内" : "国际"],
      ["跟机人员", (data.focUserList || []).length], ["DD", data.dd || (data.ddList || []).length || 0],
      ["FC", data.fc || (data.fcList || []).length || 0], ["非维修", data.nonWork || (data.nonWorkList || []).length || 0]
    ];
    target.innerHTML = `<div class="flight-detail-grid">${fields.map(function(pair) {
      return `<div><label>${esc(pair[0])}</label><strong>${esc(pair[1] ?? "--")}</strong></div>`;
    }).join("")}</div>`;
    panel.scrollIntoView({behavior:"smooth", block:"start"});
  } catch (err) {
    target.innerHTML = `<pre class="error">${esc(err.message || err)}</pre>`;
  }
}

function routineStatusClass(taskStatus) {
  const status = String(taskStatus ?? "");
  if (status === "8" || status === "9") return "done";
  if (status === "0" || status === "1") return "pending";
  return "working";
}

function routineDateType(value, direction) {
  const labels = direction === "in"
    ? {"1":"计达", "2":"实达", "3":"预达"}
    : {"1":"计飞", "2":"实飞", "3":"预飞"};
  return labels[String(value || "")] || "时间";
}

function resetRoutineSearch() {
  const now = new Date();
  byId("routineDate").value = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
  byId("routineKeyword").value = "";
  byId("routineAcno").value = "";
  byId("routineSite").value = "";
  byId("routineCategory").value = "0";
  byId("routineTaskType").value = "";
  byId("routineAcType").value = "";
  byId("routineStatus").value = "";
  routinePage = 1;
  loadRoutineTasks();
}

function clearRoutineFilters() {
  byId("routineKeyword").value = "";
  byId("routineAcno").value = "";
  byId("routineSite").value = "";
  byId("routineCategory").value = "0";
  byId("routineTaskType").value = "";
  byId("routineAcType").value = "";
  byId("routineStatus").value = "";
  routinePage = 1;
  loadRoutineTasks();
}

function shiftRoutineDate(days) {
  const value = byId("routineDate").value;
  const date = value ? new Date(value + "T00:00:00") : new Date();
  date.setDate(date.getDate() + days);
  byId("routineDate").value = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
  routinePage = 1;
  loadRoutineTasks();
}

function updateRoutineSelect(id, values, emptyLabel) {
  const select = byId(id);
  const selected = select.value;
  const options = [`<option value="">${esc(emptyLabel)}</option>`].concat(
    (values || []).map(function(value) {
      return `<option value="${esc(value)}">${esc(value)}</option>`;
    })
  );
  select.innerHTML = options.join("");
  if ((values || []).includes(selected)) select.value = selected;
}

async function loadRoutineTasks() {
  const rowsEl = byId("routineRows");
  rowsEl.innerHTML = `<tr><td colspan="11"><pre>正在查询例行任务...</pre></td></tr>`;
  try {
    const size = Number(byId("routinePageSize").value || 20);
    const q = new URLSearchParams({
      date: byId("routineDate").value,
      keyword: byId("routineKeyword").value.trim(),
      category: byId("routineCategory").value,
      taskType: byId("routineTaskType").value,
      acType: byId("routineAcType").value,
      status: byId("routineStatus").value,
      sit: byId("routineSite").value,
      acno: byId("routineAcno").value,
      current: routinePage,
      size: size
    });
    const data = await getJson("/api/routine-tasks?" + q.toString());
    const filterOptions = data.filterOptions || {};
    updateRoutineSelect("routineAcno", filterOptions.acnos || [], "全部机号");
    updateRoutineSelect("routineSite", filterOptions.sites || [], "全部站点");
    const records = data.records || [];
    routineTotal = Number(data.total || 0);
    const pages = Number(data.pages || Math.max(1, Math.ceil(routineTotal / size)));
    byId("routineTotal").textContent = `共 ${routineTotal} 条`;
    byId("routineUpdated").textContent = `更新于 ${new Date().toLocaleTimeString("zh-CN", {hour12:false})}`;
    byId("routinePageInfo").textContent = `第 ${routinePage} / ${pages} 页`;
    byId("routinePrev").disabled = routinePage <= 1;
    byId("routineNext").disabled = routinePage >= pages;
    rowsEl.innerHTML = records.length ? records.map(function(item) {
      const inInfo = item.inFlightNo
        ? `<strong>${esc(item.inFlightNo)}</strong><br>${esc(item.inFlight || "--")}<br><span class="muted">${esc(routineDateType(item.inDateType, "in"))} ${esc(item.inDate || "--")}</span>`
        : "--";
      const outInfo = item.outFlightNo
        ? `<strong>${esc(item.outFlightNo)}</strong><br>${esc(item.outFlight || "--")}<br><span class="muted">${esc(routineDateType(item.outDateType, "out"))} ${esc(item.outDate || "--")}</span>`
        : "--";
      return `<tr>
        <td><strong>${esc(item.taskTypeName || item.taskType || "--")}</strong></td>
        <td><strong>${esc(item.acno || "--")}</strong><br><span class="muted">${esc(item.acType || "--")}</span></td>
        <td>${inInfo}</td>
        <td>${outInfo}</td>
        <td>${esc(item.bay || "待定")}</td>
        <td>${esc(item.startPlanDate || "--")}</td>
        <td><span class="routine-status ${routineStatusClass(item.tasksts)}">${esc(item.taskstsName || "--")}</span></td>
        <td>${esc(item.wxWorker || "--")}</td>
        <td>${esc(item.fxWorker || "--")}</td>
        <td>${esc(item.workPackage || 0)} / ${esc(item.fc || 0)} / ${esc(item.dd || 0)} / ${esc(item.nonWork || 0)}</td>
        <td><button class="secondary" onclick="loadRoutineDetail('${encodeURIComponent(item.taskid || "")}')">详情</button></td>
      </tr>`;
    }).join("") : `<tr><td colspan="11"><pre>没有查到符合条件的例行任务。</pre></td></tr>`;
    routineLoaded = true;
  } catch (err) {
    rowsEl.innerHTML = `<tr><td colspan="11"><pre class="error">${esc(err.message || err)}</pre></td></tr>`;
  }
}

function changeRoutinePage(delta) {
  const size = Number(byId("routinePageSize").value || 20);
  const pages = Math.max(1, Math.ceil(routineTotal / size));
  routinePage = Math.min(pages, Math.max(1, routinePage + delta));
  loadRoutineTasks();
}

function routineWorkflowHtml(statusValue) {
  const stages = [
    ["0", "派工"], ["1", "确认"], ["2", "生产准备"], ["4", "到位"],
    ["5", "重复检查"], ["6", "航材工具"], ["7", "放行"], ["8", "交接"]
  ];
  const status = String(statusValue ?? "");
  const finished = status === "9";
  const currentIndex = finished ? stages.length : Math.max(0, stages.findIndex(function(stage){ return stage[0] === status; }));
  return `<div class="routine-flow">${stages.map(function(stage, index) {
    const cls = finished || index < currentIndex ? "done" : (index === currentIndex ? "current" : "");
    return `${index ? "<i>›</i>" : ""}<span class="${cls}">${esc(stage[1])}</span>`;
  }).join("")}</div>`;
}

async function loadRoutineDetail(encodedId) {
  const taskId = decodeURIComponent(encodedId);
  const panel = byId("routineDetailPanel");
  const target = byId("routineDetail");
  panel.style.display = "block";
  target.innerHTML = `<pre>正在加载例行任务详情...</pre>`;
  try {
    const data = await getJson("/api/routine-task-detail?id=" + encodeURIComponent(taskId));
    const process = data.processDetail || {};
    const fields = [
      ["任务编号", data.taskid], ["任务类型", data.taskTypeName || data.taskType],
      ["机号", data.acno], ["机型", data.acType], ["发动机型号", data.engType],
      ["航班日期", data.flightDate], ["任务状态", data.taskstsName],
      ["机位", data.bay || "待定"], ["计划开始", data.startPlanDate], ["COBT", data.cobt],
      ["进港航班", data.inFlightNo], ["进港航段", data.inFlight],
      [routineDateType(data.inDateType, "in"), data.inDate],
      ["出港航班", data.outFlightNo], ["出港航段", data.outFlight],
      [routineDateType(data.outDateType, "out"), data.outDate],
      ["维修人员", data.wxWorker], ["放行人员", data.fxWorker],
      ["工作包", data.workPackage || 0], ["FC", data.fc || 0], ["DD", data.dd || 0],
      ["非例行项", data.nonWork || 0], ["已完成非例行", data.doneNonWork || 0],
      ["重复工作", data.repeatWork || 0], ["流程备注", process.memo]
    ];
    target.innerHTML = routineWorkflowHtml(data.tasksts) + `<div class="flight-detail-grid">${fields.map(function(pair) {
      return `<div><label>${esc(pair[0])}</label><strong>${esc(pair[1] ?? "--")}</strong></div>`;
    }).join("")}</div>`;
    panel.scrollIntoView({behavior:"smooth", block:"start"});
  } catch (err) {
    target.innerHTML = `<pre class="error">${esc(err.message || err)}</pre>`;
  }
}


function jumpToCityVideos(city) {
  showView("dashboard");
  var sel = document.getElementById("fileCity");
  var devInput = document.getElementById("dev");
  var groupSel = document.getElementById("fileGroup");
  if (devInput) devInput.value = "";
  if (groupSel) groupSel.value = "";
  if (sel) sel.value = city;
  document.getElementById("timePreset").value = "3d";
  applyPreset();
  recordPage = 1;
  loadRecords();
}

function jumpToDeviceVideos(devId) {
  showView("dashboard");
  var devInput = document.getElementById("dev");
  if (devInput) devInput.value = devId;
  document.getElementById("timePreset").value = "3d";
  applyPreset();
  recordPage = 1;
  loadRecords();
}

async function loadAll() {
  var shouldLoadRecords = byId("view-dashboard")?.classList.contains("active") && !recordsLoaded;
  if (shouldLoadRecords) loadRecords();
  await loadDevices();
  loadSummary();
  loadDashboard();
  loadHealth();
  setTimeout(loadDeviceVideoStats, 300);
}

applyPreset();
applyTrackPreset();
renderPlaylist();
updatePlayerCount();
initPlayerResizer();
syncSidebarForViewport();
window.addEventListener("resize", function() {
  syncSidebarForViewport();
  applyPlayerSideWidth(playerSideWidth, false);
});
initAuth();
// Retry map rendering if Leaflet loaded later
setTimeout(function() { if (typeof L !== "undefined" && !leafletMap) { renderMap(); } }, 1000);
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def send_bytes(self, data: bytes, content_type: str, status: int = 200, headers: dict[str, str] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, payload: object, status: int = 200, headers: dict[str, str] | None = None) -> None:
        self.send_bytes(json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8", status, headers)

    def cookie_session_id(self) -> str:
        raw = self.headers.get("Cookie", "")
        jar = cookies.SimpleCookie()
        try:
            jar.load(raw)
        except cookies.CookieError:
            return ""
        morsel = jar.get(SESSION_COOKIE)
        return morsel.value if morsel else ""

    def current_auth_session(self) -> dict[str, Any] | None:
        session = get_auth_session(self.cookie_session_id())
        REQUEST_CONTEXT.auth_session = session
        return session

    def require_auth(self) -> dict[str, Any] | None:
        session = self.current_auth_session()
        if not session:
            self.send_json({"error": "unauthorized", "message": "请先登录"}, 401)
            return None
        return session

    def clear_request_context(self) -> None:
        REQUEST_CONTEXT.auth_session = None

    def session_cookie_header(self, sid: str, max_age: int = SESSION_TTL_SECONDS) -> str:
        return f"{SESSION_COOKIE}={sid}; Path=/; Max-Age={max_age}; HttpOnly; SameSite=Lax"


    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        try:
            length = int(self.headers.get("Content-Length", 0) or 0)
            if length > 1024 * 1024:
                self.send_json({"error": "invalid request body"}, 400)
                return
            payload = json.loads(self.rfile.read(length).decode("utf-8")) if length > 0 else {}
            if parsed.path == "/api/login":
                if not isinstance(payload, dict):
                    self.send_json({"error": "invalid request body"}, 400)
                    return
                username = str(payload.get("username") or "").strip()
                password = str(payload.get("password") or "")
                try:
                    login_result = mcs8_ws_login(username, password)
                except Exception as exc:
                    self.send_json({"error": "login_failed", "message": str(exc)}, 401)
                    return
                sid, session = create_auth_session(login_result)
                REQUEST_CONTEXT.auth_session = session
                self.send_json({"ok": True, "session": _session_public(session)}, headers={"Set-Cookie": self.session_cookie_header(sid)})
                return
            if parsed.path == "/api/logout":
                sid = self.cookie_session_id()
                with AUTH_SESSIONS_LOCK:
                    AUTH_SESSIONS.pop(sid, None)
                self.send_json({"ok": True}, headers={"Set-Cookie": self.session_cookie_header("", 0)})
                return

            if not self.require_auth():
                return
            if parsed.path == "/api/record-flight-references":
                items = payload.get("items", []) if isinstance(payload, dict) else []
                if not isinstance(items, list):
                    self.send_json({"error": "items must be a list"}, 400)
                    return
                self.send_json({"data": match_record_flight_references(items)})
                return
            self.send_json({"error": "not found"}, 404)
        except json.JSONDecodeError:
            self.send_json({"error": "invalid json"}, 400)
        except Exception as exc:
            self.send_json({"error": str(exc)}, 500)
        finally:
            self.clear_request_context()




    def do_HEAD(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        if parsed.path in {"/transcode-video", "/proxy-video"} and not self.require_auth():
            return
        if parsed.path == "/transcode-video":
            self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        if parsed.path == "/proxy-video":
            key = query.get("key", [""])[0]
            if not key:
                self.send_response(400)
                self.end_headers()
                return
            try:
                req = urllib.request.Request(presign_oss_url(key))
                req.add_header("Range", "bytes=0-0")
                with urllib.request.urlopen(req, timeout=30) as resp:
                    content_type = resp.headers.get("Content-Type", "video/mp4")
                    if key.lower().endswith(".mp4"):
                        content_type = "video/mp4"
                    self.send_response(200)
                    self.send_header("Content-Type", content_type)
                    content_range = resp.headers.get("Content-Range", "")
                    content_length = content_range.rsplit("/", 1)[-1] if "/" in content_range else resp.headers.get("Content-Length")
                    if content_length:
                        self.send_header("Content-Length", content_length)
                    self.send_header("Accept-Ranges", "bytes")
                    self.end_headers()
                return
            except Exception:
                self.send_response(502)
                self.end_headers()
                return
        self.send_response(200)
        self.end_headers()
        self.clear_request_context()


    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        try:
            if parsed.path == "/api/auth/session":
                session = self.current_auth_session()
                self.send_json(_session_public(session) if session else {"authenticated": False})
                return
            protected = (
                parsed.path.startswith("/api/")
                or parsed.path in {"/play", "/proxy-video", "/transcode-video"}
                or parsed.path.startswith("/hls/")
            )
            if protected and not self.require_auth():
                return
            if parsed.path == "/":
                self.send_bytes(HTML.encode("utf-8"), "text/html; charset=utf-8")
            elif parsed.path == "/api/health":
                session = None
                try:
                    session = current_session()
                except MCS8Error:
                    pass
                cfg = local_config()
                self.send_json(
                    {
                        "server": {"host": cfg["host"], "sdk_port": cfg["sdk_port"], "api_port": cfg["api_port"]},
                        "auth": _session_public(self.current_auth_session()) if self.current_auth_session() else {"authenticated": False},
                        "has_session": bool(session),
                    }
                )
            elif parsed.path == "/api/summary":
                self.send_json(system_summary())
            elif parsed.path == "/api/devices":
                self.send_json(merged_devices())
            elif parsed.path == "/api/device-catalog":
                self.send_json(device_catalog())
            elif parsed.path == "/api/records":
                page = int(query.get("page", ["1"])[0] or "1")
                page_size = int(query.get("pagesize", ["25"])[0] or "25")
                city = query.get("city", [""])[0].strip()
                q = query.get("q", query.get("dev", [""]))[0].strip()
                mode = query.get("mode", ["platform"])[0].strip()
                self.send_json(query_records(query.get("st", [""])[0], query.get("et", [""])[0], q, page, page_size, mode, city))
            elif parsed.path == "/api/gps-track":
                dev = query.get("dev", [""])[0].strip()
                max_points = int(query.get("maxpoints", ["2000"])[0] or "2000")
                self.send_json(
                    query_gps_track(
                        dev,
                        query.get("st", [""])[0],
                        query.get("et", [""])[0],
                        max_points,
                    )
                )
            elif parsed.path == "/leaflet.js":
                target = WEB_DIR / "leaflet.js"
                self.send_bytes(target.read_bytes(), "application/javascript")
            elif parsed.path == "/leaflet.css":
                target = WEB_DIR / "leaflet.css"
                self.send_bytes(target.read_bytes(), "text/css")
            elif parsed.path.startswith("/hls/"):
                rel = urllib.parse.unquote(parsed.path[len("/hls/") :])
                target = (HLS_DIR / rel).resolve()
                if HLS_DIR.resolve() not in target.parents and target != HLS_DIR.resolve():
                    self.send_json({"error": "invalid hls path"}, 400)
                    return
                if not target.exists() or not target.is_file():
                    self.send_json({"error": "hls file not found"}, 404)
                    return
                suffix = target.suffix.lower()
                content_type = (
                    "application/vnd.apple.mpegurl" if suffix == ".m3u8"
                    else "video/mp2t" if suffix == ".ts"
                    else "image/jpeg" if suffix in {".jpg", ".jpeg"}
                    else "application/octet-stream"
                )
                self.send_bytes(target.read_bytes(), content_type)
            elif parsed.path == "/play":
                key = query.get("key", [""])[0]
                if not key:
                    self.send_json({"error": "missing recording object key"}, 400)
                    return
                self.send_response(302)
                self.send_header("Location", presign_oss_url(key))
                self.end_headers()
            elif parsed.path == "/api/dashboard":
                self.send_json(dashboard_stats())
            elif parsed.path == "/api/inspection/list":
                self.send_json({"data": load_inspections()})
            elif parsed.path == "/api/inspection/save":
                length = int(self.headers.get("Content-Length", 0))
                if length > 0:
                    body = self.rfile.read(length).decode("utf-8")
                    record = json.loads(body)
                    result = save_inspection(record)
                    self.send_json({"ok": True, "data": result})
                else:
                    self.send_json({"error": "empty body"}, 400)
            elif parsed.path == "/api/video-stats":
                self.send_json(video_stats_all())
            elif parsed.path == "/api/flights":
                self.send_json(
                    query_flight_dynamics(
                        query.get("date", [""])[0],
                        query.get("keyword", [""])[0],
                        int(query.get("category", ["0"])[0] or "0"),
                        int(query.get("current", ["1"])[0] or "1"),
                        int(query.get("size", ["20"])[0] or "20"),
                        query.get("depCity", [""])[0],
                        query.get("arrCity", [""])[0],
                    )
                )
            elif parsed.path == "/api/flight-detail":
                flight_id = query.get("id", [""])[0].strip()
                if not flight_id:
                    self.send_json({"error": "missing flight id"}, 400)
                    return
                self.send_json(query_flight_detail(flight_id))
            elif parsed.path == "/api/routine-tasks":
                self.send_json(
                    query_routine_tasks(
                        query.get("date", [""])[0],
                        query.get("keyword", [""])[0],
                        int(query.get("category", ["0"])[0] or "0"),
                        query.get("taskType", [""])[0],
                        query.get("acType", [""])[0],
                        query.get("status", [""])[0],
                        query.get("sit", [""])[0],
                        query.get("acno", [""])[0],
                        int(query.get("current", ["1"])[0] or "1"),
                        int(query.get("size", ["20"])[0] or "20"),
                    )
                )
            elif parsed.path == "/api/routine-task-detail":
                task_id = query.get("id", [""])[0].strip()
                if not task_id:
                    self.send_json({"error": "missing routine task id"}, 400)
                    return
                self.send_json(query_routine_task_detail(task_id))
            elif parsed.path == "/api/video-info":
                key = query.get("key", [""])[0]
                if not key:
                    self.send_json({"error": "missing key"}, 400)
                    return
                self.send_json(video_stream_info(key))
            elif parsed.path == "/transcode-video":
                key = query.get("key", [""])[0]
                if not key:
                    self.send_json({"error": "missing key"}, 400)
                    return
                if not FFMPEG_PATH.exists():
                    self.send_json({"error": "ffmpeg not found"}, 500)
                    return
                process = subprocess.Popen(
                    [
                        str(FFMPEG_PATH),
                        "-hide_banner", "-loglevel", "error",
                        "-i", presign_oss_url(key),
                        "-map", "0:v:0",
                        "-map", "0:a:0?",
                        "-vf", "scale=-2:720",
                        "-c:v", "libx264",
                        "-preset", "ultrafast",
                        "-tune", "zerolatency",
                        "-pix_fmt", "yuv420p",
                        "-c:a", "aac",
                        "-b:a", "96k",
                        "-movflags", "frag_keyframe+empty_moov+default_base_moof",
                        "-f", "mp4",
                        "pipe:1",
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    bufsize=0,
                )
                self.send_response(200)
                self.send_header("Content-Type", "video/mp4")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Transfer-Encoding", "chunked")
                self.send_header("Connection", "keep-alive")
                self.end_headers()
                try:
                    assert process.stdout is not None
                    while True:
                        chunk = process.stdout.read(65536)
                        if not chunk:
                            break
                        self.wfile.write(f"{len(chunk):X}\r\n".encode("ascii"))
                        self.wfile.write(chunk)
                        self.wfile.write(b"\r\n")
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass
                finally:
                    try:
                        self.wfile.write(b"0\r\n\r\n")
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        pass
                    if process.poll() is None:
                        process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
            elif parsed.path == "/proxy-video":
                key = query.get("key", [""])[0]
                if not key:
                    self.send_json({"error": "missing key"}, 400)
                    return
                try:
                    url = presign_oss_url(key)
                    req = urllib.request.Request(url)
                    range_header = self.headers.get("Range")
                    if range_header:
                        req.add_header("Range", range_header)
                    with urllib.request.urlopen(req, timeout=60) as resp:
                        ct = resp.headers.get("Content-Type", "video/mp4")
                        lk = key.lower()
                        if lk.endswith(".mp4"): ct = "video/mp4"
                        elif lk.endswith(".m3u8"): ct = "application/vnd.apple.mpegurl"
                        elif lk.endswith(".ts"): ct = "video/mp2t"
                        status = resp.status
                        self.send_response(status)
                        self.send_header("Content-Type", ct)
                        cl = resp.headers.get("Content-Length")
                        if cl:
                            self.send_header("Content-Length", cl)
                        cr = resp.headers.get("Content-Range")
                        if cr:
                            self.send_header("Content-Range", cr)
                        self.send_header("Accept-Ranges", "bytes")
                        self.send_header("Access-Control-Allow-Origin", "*")
                        self.end_headers()
                        while True:
                            chunk = resp.read(65536)
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                except Exception as e:
                    self.send_json({"error": str(e)}, 502)
            else:
                self.send_json({"error": "not found"}, 404)
        except Exception as exc:
            self.send_json({"error": str(exc)}, 500)
        finally:
            self.clear_request_context()


def load_inspections() -> list[dict[str, any]]:
    try:
        with open(INSPECTION_DB, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return []

def save_inspection(record: dict) -> dict:
    records = load_inspections()
    record["id"] = record.get("id", str(int(__import__("time").time() * 1000)))
    record["createdAt"] = record.get("createdAt", str(__import__("datetime").datetime.now().isoformat(timespec="seconds")))
    existing = [i for i, r in enumerate(records) if r.get("id") == record["id"]]
    if existing:
        records[existing[0]] = record
    else:
        records.append(record)
    with open(INSPECTION_DB, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    return record

def dashboard_stats() -> dict:
    devices = merged_devices()
    total = len(devices)
    online = sum(1 for d in devices if d.get("online"))
    offline = total - online
    cities = sorted({city for d in devices for city in device_city_names(d)})
    return {"devices": {"total": total, "online": online, "offline": offline}, "cities": cities}


def video_stats_all() -> dict:
    """Return video counts for all devices in 3 days. Uses a single paginated scan."""
    now = dt.datetime.now()
    st = (now - dt.timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
    et = now.strftime("%Y-%m-%d %H:%M:%S")
    result = {}
    # Fetch page by page, but only extract devId + size (lightweight)
    page = 1
    page_size = 200
    while True:
        data = query_records(st, et, "", page, page_size, "platform", "")
        records = data.get("data", []) or data.get("Content", []) or data.get("content", [])
        if not records:
            break
        for rec in records:
            dev_id = str(rec.get("devId", "") or rec.get("DevId", "") or rec.get("szIDNO", ""))
            if not dev_id:
                continue
            if dev_id not in result:
                result[dev_id] = {"count": 0, "sizeMB": 0}
            result[dev_id]["count"] += 1
            try:
                size = int(rec.get("fileSize", 0) or rec.get("fileLen", 0) or rec.get("size", 0) or 0)
                result[dev_id]["sizeMB"] += size / (1024 * 1024)
            except (ValueError, TypeError):
                pass
        total = data.get("recordsTotal", 0) or data.get("total", 0)
        if page * page_size >= total:
            break
        page += 1
        if page > 50:
            break
    return result

def main() -> None:
    HLS_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((PANEL_HOST, PANEL_PORT), Handler)
    print(f"MCS8 web panel: http://{PANEL_HOST}:{PANEL_PORT}/")
    server.serve_forever()


if __name__ == "__main__":
    main()
