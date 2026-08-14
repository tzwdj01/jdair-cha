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
                    {
                        "devId": "WXB337",
                        "name": "JDTY02673",
                        "groupName": "Maintenance",
                        "online": True,
                    },
                    {
                        "devId": "WXB342",
                        "name": "JDTY03099",
                        "groupName": "Maintenance",
                        "online": True,
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

    def __init__(self, _session_id, settings) -> None:
        self.settings = settings
        self.prepared = False
        self.authorized_devices: set[str] = set()
        self.disconnect_calls = 0
        self.__class__.instances.append(self)

    async def prepare(self) -> None:
        self.prepared = True

    def authorize_device(self, device_id: str) -> None:
        self.authorized_devices.add(device_id)

    def clear_authorized_device(self, device_id: str | None = None) -> None:
        if device_id is None:
            self.authorized_devices.clear()
        else:
            self.authorized_devices.discard(device_id)

    async def disconnect(self) -> None:
        self.disconnect_calls += 1

    async def proxy(self, _kind, socket, *, proxy_host: str) -> None:
        del proxy_host
        await socket.accept(subprotocol="protoo")


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
    scheme: str = "http",
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
        "scheme": scheme,
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


async def _websocket_exchange(
    app,
    path: str,
    *,
    cookie: str,
    origin: str | None,
) -> list[dict[str, Any]]:
    headers = [
        (b"host", b"testserver"),
        (b"cookie", cookie.encode("latin-1")),
    ]
    if origin is not None:
        headers.append((b"origin", origin.encode("latin-1")))
    scope = {
        "type": "websocket",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "scheme": "ws",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "root_path": "",
        "headers": headers,
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
        "subprotocols": ["protoo"],
        "state": {},
    }
    incoming = [
        {"type": "websocket.connect"},
        {"type": "websocket.disconnect", "code": 1000},
    ]
    messages: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        if incoming:
            return incoming.pop(0)
        await asyncio.sleep(0)
        return {"type": "websocket.disconnect", "code": 1000}

    async def send(message: dict[str, Any]) -> None:
        messages.append(message)

    await app(scope, receive, send)
    return messages


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
                "CHA_V2_REALTIME_MAX_STREAMS_PER_SESSION": "2",
                "CHA_V2_REALTIME_MAX_SESSIONS_PER_OWNER": "10",
                "CHA_V2_REALTIME_SESSION_CREATE_LIMIT": "100",
                "CHA_V2_REALTIME_MAX_RETAINED_SESSIONS": "32",
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
        self.assertIn("实时视频监察", page.text)
        self.assertIn('id="videoGrid"', page.text)
        self.assertIn("multistream_runtime.js", page.text)

        devices = await self.request("GET", "/api/v2/realtime/devices")
        self.assertEqual(devices.status_code, 200)
        self.assertIn(
            "WXB339",
            {
                item["device_id"]
                for item in devices.json()["data"]["devices"]
            },
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
        self.assertEqual(
            stream.json()["data"]["connection"]["max_streams"],
            2,
        )
        self.assertTrue(
            stream.json()["data"]["connection"]["runtime_path"].endswith(
                "multistream_runtime.js"
            )
        )

        second = await self.request(
            "POST",
            f"/api/v2/realtime/sessions/{session_id}/streams",
            {"device_id": "WXB339"},
        )
        self.assertEqual(second.status_code, 409)
        self.assertEqual(
            second.json()["data"]["code"],
            "duplicate_device",
        )

        deleted = await self.request(
            "DELETE",
            f"/api/v2/realtime/sessions/{session_id}/streams/{stream_id}",
        )
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(
            deleted.json()["data"]["streams"][0]["status"],
            "CLOSED",
        )

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

    async def test_api_enforces_configured_active_stream_limit(self) -> None:
        created = await self.request(
            "POST",
            "/api/v2/realtime/sessions",
        )
        session_id = created.json()["data"]["session_id"]
        first = await self.request(
            "POST",
            f"/api/v2/realtime/sessions/{session_id}/streams",
            {"device_id": "WXB339"},
        )
        second = await self.request(
            "POST",
            f"/api/v2/realtime/sessions/{session_id}/streams",
            {"device_id": "WXB337"},
        )
        limited = await self.request(
            "POST",
            f"/api/v2/realtime/sessions/{session_id}/streams",
            {"device_id": "WXB342"},
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(limited.status_code, 409)
        self.assertEqual(
            limited.json()["data"]["code"],
            "stream_limit_reached",
        )
        await self.request(
            "DELETE",
            f"/api/v2/realtime/sessions/{session_id}",
        )

    async def test_receive_only_audio_routes_are_feature_gated(self) -> None:
        created = await self.request(
            "POST",
            "/api/v2/realtime/sessions",
        )
        session_id = created.json()["data"]["session_id"]
        first = await self.request(
            "POST",
            f"/api/v2/realtime/sessions/{session_id}/streams",
            {"device_id": "WXB339"},
        )
        first_id = first.json()["data"]["stream"]["stream_id"]
        disabled = await self.request(
            "POST",
            (
                f"/api/v2/realtime/sessions/{session_id}/streams/"
                f"{first_id}/audio"
            ),
            {},
        )
        self.assertEqual(disabled.status_code, 404)
        self.assertEqual(disabled.json()["data"]["code"], "audio_disabled")

        object.__setattr__(
            self.main.settings,
            "feature_realtime_audio",
            True,
        )
        try:
            enabled = await self.request(
                "POST",
                (
                    f"/api/v2/realtime/sessions/{session_id}/streams/"
                    f"{first_id}/audio"
                ),
                {},
            )
            self.assertEqual(enabled.status_code, 200)
            self.assertTrue(enabled.json()["data"]["audio_enabled"])
            self.assertEqual(
                enabled.json()["data"]["streams"][0]["audio"]["status"],
                "OPENING",
            )
            second = await self.request(
                "POST",
                f"/api/v2/realtime/sessions/{session_id}/streams",
                {"device_id": "WXB337"},
            )
            second_id = second.json()["data"]["stream"]["stream_id"]
            limited = await self.request(
                "POST",
                (
                    f"/api/v2/realtime/sessions/{session_id}/streams/"
                    f"{second_id}/audio"
                ),
                {},
            )
            self.assertEqual(limited.status_code, 409)
            self.assertEqual(
                limited.json()["data"]["code"],
                "audio_stream_limit_reached",
            )
        finally:
            object.__setattr__(
                self.main.settings,
                "feature_realtime_audio",
                False,
            )
            await self.request(
                "DELETE",
                f"/api/v2/realtime/sessions/{session_id}",
            )

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

    async def test_diagnostics_requires_auth_and_is_redacted(self) -> None:
        missing = await _request(
            self.main.app,
            "GET",
            "/api/v2/realtime/diagnostics",
        )
        self.assertEqual(missing.status_code, 401)
        response = await self.request(
            "GET",
            "/api/v2/realtime/diagnostics",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertIn("runtime", data)
        serialized = json.dumps(data).lower()
        for forbidden in (
            "session_id",
            "stream_id",
            "device_id",
            "password",
            "authorization",
            "connecteinfo",
            "gateway_url",
            "media_url",
            "cookie",
        ):
            self.assertNotIn(forbidden, serialized)
        self.assertTrue(response.json()["meta"]["request_id"])

    async def test_realtime_api_rejects_missing_login(self) -> None:
        response = await _request(
            self.main.app,
            "GET",
            "/api/v2/realtime/devices",
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json()["data"]["code"],
            "authentication_required",
        )

    async def test_realtime_health_does_not_probe_aee(self) -> None:
        await self.main.realtime_manager.start()
        try:
            response = await _request(
                self.main.app,
                "GET",
                "/api/v2/realtime/health",
            )
            self.assertEqual(response.status_code, 503)
            data = response.json()["data"]
            self.assertEqual(data["upstream_probe"], "not_performed")
            self.assertEqual(data["session_manager"], "running")
            self.assertFalse(data["configured"])
        finally:
            await self.main.realtime_manager.shutdown()

    async def test_session_owner_cannot_be_replayed_by_other_login(
        self,
    ) -> None:
        created = await self.request(
            "POST",
            "/api/v2/realtime/sessions",
        )
        session_id = created.json()["data"]["session_id"]
        forbidden = await _request(
            self.main.app,
            "GET",
            f"/api/v2/realtime/sessions/{session_id}",
            headers={"cookie": "jdair_mcs8_session=other-login"},
        )
        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(
            forbidden.json()["data"]["code"],
            "session_forbidden",
        )
        await self.request(
            "DELETE",
            f"/api/v2/realtime/sessions/{session_id}",
        )

    async def test_lease_cookie_security_attributes(self) -> None:
        secure = await _request(
            self.main.app,
            "POST",
            "/api/v2/realtime/sessions",
            headers=self.headers,
            scheme="https",
        )
        cookie = secure.headers["set-cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("Secure", cookie)
        self.assertIn("SameSite=strict", cookie)
        session_id = secure.json()["data"]["session_id"]
        await self.request(
            "DELETE",
            f"/api/v2/realtime/sessions/{session_id}",
        )

    async def test_websocket_origin_policy_for_all_endpoints(self) -> None:
        for endpoint in ("control", "gateway", "media"):
            created = await self.request(
                "POST",
                "/api/v2/realtime/sessions",
            )
            session_id = created.json()["data"]["session_id"]
            lease_cookie = created.headers["set-cookie"].split(";", 1)[0]
            path = f"/ws/v2/realtime/{session_id}/{endpoint}"

            valid = await _websocket_exchange(
                self.main.app,
                path,
                cookie=lease_cookie,
                origin="http://testserver",
            )
            self.assertTrue(
                any(item["type"] == "websocket.accept" for item in valid),
                endpoint,
            )
            await self.request(
                "DELETE",
                f"/api/v2/realtime/sessions/{session_id}",
            )

            for rejected_origin in (
                "https://attacker.example",
                None,
            ):
                rejected_session = await self.request(
                    "POST",
                    "/api/v2/realtime/sessions",
                )
                rejected_id = rejected_session.json()["data"]["session_id"]
                rejected_cookie = rejected_session.headers[
                    "set-cookie"
                ].split(";", 1)[0]
                rejected = await _websocket_exchange(
                    self.main.app,
                    f"/ws/v2/realtime/{rejected_id}/{endpoint}",
                    cookie=rejected_cookie,
                    origin=rejected_origin,
                )
                self.assertTrue(
                    any(
                        item["type"] == "websocket.close"
                        and item.get("code") == 4403
                        for item in rejected
                    ),
                    (endpoint, rejected_origin),
                )
                await self.request(
                    "DELETE",
                    f"/api/v2/realtime/sessions/{rejected_id}",
                )

    async def test_websocket_rejects_wrong_and_closed_lease(self) -> None:
        owner = await self.request(
            "POST",
            "/api/v2/realtime/sessions",
        )
        other = await _request(
            self.main.app,
            "POST",
            "/api/v2/realtime/sessions",
            headers={"cookie": "jdair_mcs8_session=other-login"},
        )
        owner_id = owner.json()["data"]["session_id"]
        owner_cookie = owner.headers["set-cookie"].split(";", 1)[0]
        other_cookie = other.headers["set-cookie"].split(";", 1)[0]
        path = f"/ws/v2/realtime/{owner_id}/control"

        wrong = await _websocket_exchange(
            self.main.app,
            path,
            cookie=other_cookie,
            origin="http://testserver",
        )
        self.assertTrue(
            any(
                item["type"] == "websocket.close"
                and item.get("code") == 4403
                for item in wrong
            )
        )
        await self.request(
            "DELETE",
            f"/api/v2/realtime/sessions/{owner_id}",
        )
        replay = await _websocket_exchange(
            self.main.app,
            path,
            cookie=owner_cookie,
            origin="http://testserver",
        )
        self.assertTrue(
            any(
                item["type"] == "websocket.close"
                and item.get("code") == 4403
                for item in replay
            )
        )
        other_id = other.json()["data"]["session_id"]
        await _request(
            self.main.app,
            "DELETE",
            f"/api/v2/realtime/sessions/{other_id}",
            headers={"cookie": "jdair_mcs8_session=other-login"},
        )


if __name__ == "__main__":
    unittest.main()
