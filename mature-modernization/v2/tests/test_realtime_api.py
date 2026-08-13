from __future__ import annotations

import asyncio
import http.server
import importlib
import json
import os
import threading
import unittest
from dataclasses import dataclass
from typing import Any
from unittest.mock import patch


class _LegacyHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_args) -> None:
        return

    def do_GET(self) -> None:
        if self.path == "/api/auth/session":
            body = json.dumps(
                {"authenticated": True, "username": "realtime-tester"}
            ).encode()
            status = 200
        elif self.path == "/api/devices":
            body = json.dumps(
                [
                    {
                        "devId": "WXB339",
                        "name": "JDTY02674",
                        "groupName": "维修部",
                        "online": True,
                    },
                    {
                        "devId": "WXB301",
                        "name": "JDTY01828",
                        "groupName": "维修部",
                        "online": False,
                    },
                ]
            ).encode()
            status = 200
        elif self.path == "/":
            body = b"legacy"
            status = 200
        else:
            body = b"not found"
            status = 404
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class _APIAdapter:
    instances: list["_APIAdapter"] = []

    def __init__(self, _session_id, _settings) -> None:
        self.prepared = False
        self.authorized_device = None
        self.disconnect_calls = 0
        self.__class__.instances.append(self)

    async def prepare(self) -> None:
        self.prepared = True

    def authorize_device(self, device_id: str) -> None:
        self.authorized_device = device_id

    def clear_authorized_device(self) -> None:
        self.authorized_device = None

    async def disconnect(self) -> None:
        self.disconnect_calls += 1


@dataclass
class _ASGIResponse:
    status_code: int
    headers: dict[str, str]
    body: bytes

    @property
    def text(self) -> str:
        return self.body.decode("utf-8")

    def json(self) -> dict[str, Any]:
        return json.loads(self.body)


async def _request(
    app,
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
) -> _ASGIResponse:
    body = (
        json.dumps(json_body).encode("utf-8")
        if json_body is not None
        else b""
    )
    raw_headers = [
        (key.lower().encode("latin-1"), value.encode("latin-1"))
        for key, value in (headers or {}).items()
    ]
    if json_body is not None:
        raw_headers.append((b"content-type", b"application/json"))
    raw_headers.append((b"host", b"testserver"))
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "root_path": "",
        "headers": raw_headers,
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
        "state": {},
    }
    request_sent = False
    messages: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        nonlocal request_sent
        if not request_sent:
            request_sent = True
            return {
                "type": "http.request",
                "body": body,
                "more_body": False,
            }
        return {"type": "http.disconnect"}

    async def send(message: dict[str, Any]) -> None:
        messages.append(message)

    await app(scope, receive, send)
    start = next(
        message
        for message in messages
        if message["type"] == "http.response.start"
    )
    response_body = b"".join(
        message.get("body", b"")
        for message in messages
        if message["type"] == "http.response.body"
    )
    response_headers: dict[str, str] = {}
    for key, value in start.get("headers", []):
        name = key.decode("latin-1").lower()
        decoded = value.decode("latin-1")
        response_headers[name] = (
            response_headers[name] + ", " + decoded
            if name in response_headers
            else decoded
        )
    return _ASGIResponse(
        status_code=start["status"],
        headers=response_headers,
        body=response_body,
    )


class RealtimeAPITests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.legacy = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0),
            _LegacyHandler,
        )
        cls.thread = threading.Thread(
            target=cls.legacy.serve_forever,
            daemon=True,
        )
        cls.thread.start()
        host, port = cls.legacy.server_address
        cls.env = patch.dict(
            os.environ,
            {
                "CHA_V2_FEATURE_REALTIME_READONLY": "true",
                "CHA_V2_ALLOWED_HOSTS": "testserver,127.0.0.1,localhost",
                "CHA_V2_LEGACY_BASE_URL": f"http://{host}:{port}",
                "CHA_V2_REALTIME_CLEANUP_INTERVAL_SECONDS": "60",
                "CHA_V2_REALTIME_COMMAND_TIMEOUT_SECONDS": "0.05",
            },
            clear=False,
        )
        cls.env.start()
        main = importlib.import_module("app.main")
        main.realtime_manager.adapter_factory = _APIAdapter
        cls.main = main
        cls.headers = {"cookie": "jdair_mcs8_session=test-session"}

    @classmethod
    def tearDownClass(cls) -> None:
        cls.env.stop()
        cls.legacy.shutdown()
        cls.legacy.server_close()
        cls.thread.join(timeout=2)

    async def request(
        self,
        method: str,
        path: str,
        json_body: dict[str, Any] | None = None,
    ) -> _ASGIResponse:
        return await _request(
            self.main.app,
            method,
            path,
            headers=self.headers,
            json_body=json_body,
        )

    async def test_api_lifecycle_and_feature_page(self) -> None:
        page = await self.request("GET", "/api/v2/realtime")
        self.assertEqual(page.status_code, 200)
        self.assertIn("单设备实时视频", page.text)

        devices = await self.request("GET", "/api/v2/realtime/devices")
        self.assertEqual(devices.status_code, 200)
        self.assertEqual(
            devices.json()["data"]["devices"][0]["device_id"],
            "WXB339",
        )

        created = await self.request(
            "POST",
            "/api/v2/realtime/sessions",
        )
        self.assertEqual(created.status_code, 201)
        session_id = created.json()["data"]["session_id"]
        self.assertIn("HttpOnly", created.headers["set-cookie"])
        self.assertNotIn("token", created.text.lower())

        fetched = await self.request(
            "GET",
            f"/api/v2/realtime/sessions/{session_id}",
        )
        self.assertEqual(fetched.json()["data"]["status"], "READY")

        heartbeat = await self.request(
            "POST",
            f"/api/v2/realtime/sessions/{session_id}/heartbeat",
        )
        self.assertEqual(heartbeat.status_code, 200)

        stream = await self.request(
            "POST",
            f"/api/v2/realtime/sessions/{session_id}/streams",
            {"device_id": "WXB339"},
        )
        self.assertEqual(stream.status_code, 201)
        stream_id = stream.json()["data"]["stream"]["stream_id"]

        second = await self.request(
            "POST",
            f"/api/v2/realtime/sessions/{session_id}/streams",
            {"device_id": "WXB339"},
        )
        self.assertEqual(second.status_code, 409)
        self.assertEqual(
            second.json()["data"]["code"],
            "stream_limit_reached",
        )

        deleted = await self.request(
            "DELETE",
            f"/api/v2/realtime/sessions/{session_id}/streams/{stream_id}",
        )
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(deleted.json()["data"]["streams"], [])

        closed = await self.request(
            "DELETE",
            f"/api/v2/realtime/sessions/{session_id}",
        )
        repeated = await self.request(
            "DELETE",
            f"/api/v2/realtime/sessions/{session_id}",
        )
        self.assertEqual(closed.json()["data"]["status"], "CLOSED")
        self.assertEqual(repeated.json()["data"]["status"], "CLOSED")

    async def test_offline_and_missing_devices_are_rejected(self) -> None:
        created = await self.request(
            "POST",
            "/api/v2/realtime/sessions",
            {"client_label": "device-errors"},
        )
        session_id = created.json()["data"]["session_id"]
        offline = await self.request(
            "POST",
            f"/api/v2/realtime/sessions/{session_id}/streams",
            {"device_id": "WXB301"},
        )
        missing = await self.request(
            "POST",
            f"/api/v2/realtime/sessions/{session_id}/streams",
            {"device_id": "WXB404"},
        )
        self.assertEqual(offline.status_code, 409)
        self.assertEqual(offline.json()["data"]["code"], "device_offline")
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.json()["data"]["code"], "device_not_found")

    async def test_missing_session_is_safe_error(self) -> None:
        response = await self.request(
            "GET",
            "/api/v2/realtime/sessions/missing",
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["data"]["code"], "session_not_found")

    async def test_session_owner_ignores_unrelated_cookie_changes(self) -> None:
        created = await self.request(
            "POST",
            "/api/v2/realtime/sessions",
        )
        session_id = created.json()["data"]["session_id"]
        response = await _request(
            self.main.app,
            "GET",
            f"/api/v2/realtime/sessions/{session_id}",
            headers={
                "cookie": (
                    "jdair_mcs8_session=test-session; ui_theme=night"
                )
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["session_id"], session_id)


if __name__ == "__main__":
    unittest.main()
