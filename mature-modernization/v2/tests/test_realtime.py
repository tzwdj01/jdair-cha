from __future__ import annotations

import asyncio
import datetime as dt
import json
import os
import unittest
from unittest.mock import patch

from app.config import Settings
from app.realtime.aee_adapter import AEEAdapter, redact_upstream_error
from app.realtime.errors import RealtimeError
from app.realtime.models import SessionStatus, StreamStatus
from app.realtime.session_manager import RealtimeSessionManager


REALTIME_ENV = {
    "CHA_V2_FEATURE_REALTIME_READONLY": "true",
    "CHA_V2_REALTIME_SESSION_TTL_SECONDS": "60",
    "CHA_V2_REALTIME_CLEANUP_INTERVAL_SECONDS": "60",
    "CHA_V2_REALTIME_CLOSED_RETENTION_SECONDS": "60",
    "CHA_V2_REALTIME_COMMAND_TIMEOUT_SECONDS": "0.05",
}


class FakeAdapter:
    instances: list["FakeAdapter"] = []

    def __init__(self, session_id: str, _settings: Settings) -> None:
        self.session_id = session_id
        self.prepared = False
        self.authorized_device = None
        self.disconnect_calls = 0
        self.proxy_calls = 0
        self.__class__.instances.append(self)

    async def prepare(self) -> None:
        self.prepared = True

    def authorize_device(self, device_id: str) -> None:
        self.authorized_device = device_id

    def clear_authorized_device(self) -> None:
        self.authorized_device = None

    async def disconnect(self) -> None:
        self.disconnect_calls += 1

    async def proxy(self, _kind, _socket, *, proxy_host: str) -> None:
        del proxy_host
        self.proxy_calls += 1


class FakeControlSocket:
    def __init__(self) -> None:
        self.commands: list[dict] = []
        self.close_calls = 0

    async def send_json(self, command: dict) -> None:
        self.commands.append(command)

    async def close(self, code: int = 1000) -> None:
        del code
        self.close_calls += 1


class RealtimeSessionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        FakeAdapter.instances.clear()
        self.env_patch = patch.dict(os.environ, REALTIME_ENV, clear=False)
        self.env_patch.start()
        self.settings = Settings.from_env()
        self.manager = RealtimeSessionManager(
            self.settings,
            adapter_factory=FakeAdapter,
        )

    def tearDown(self) -> None:
        self.env_patch.stop()

    async def create(self):
        return await self.manager.create_session(
            owner_key="owner-a",
            owner_name="tester",
        )

    async def test_create_query_and_heartbeat(self) -> None:
        session, _ = await self.create()
        self.assertEqual(session.status, SessionStatus.READY)
        before = session.last_heartbeat_at
        await asyncio.sleep(0)
        heartbeat = await self.manager.heartbeat(
            session.session_id,
            owner_key="owner-a",
        )
        self.assertGreaterEqual(heartbeat.last_heartbeat_at, before)
        fetched = await self.manager.get_session(
            session.session_id,
            owner_key="owner-a",
        )
        self.assertEqual(fetched.session_id, session.session_id)

    async def test_add_stream_and_reject_second_stream(self) -> None:
        session, _ = await self.create()
        stream = await self.manager.add_stream(
            session.session_id,
            owner_key="owner-a",
            device_id="WXB339",
        )
        self.assertTrue(FakeAdapter.instances[0].prepared)
        self.assertEqual(
            FakeAdapter.instances[0].authorized_device,
            "WXB339",
        )
        self.assertEqual(stream.status, StreamStatus.CONNECTING)
        with self.assertRaises(RealtimeError) as context:
            await self.manager.add_stream(
                session.session_id,
                owner_key="owner-a",
                device_id="WXB301",
            )
        self.assertEqual(context.exception.code, "stream_limit_reached")

    async def test_delete_stream_falls_back_to_media_disconnect(self) -> None:
        session, _ = await self.create()
        stream = await self.manager.add_stream(
            session.session_id,
            owner_key="owner-a",
            device_id="WXB339",
        )
        result = await self.manager.delete_stream(
            session.session_id,
            stream.stream_id,
            owner_key="owner-a",
        )
        self.assertEqual(result.status, SessionStatus.READY)
        self.assertFalse(result.connection_reusable)
        self.assertEqual(result.streams, {})
        self.assertEqual(FakeAdapter.instances[0].disconnect_calls, 1)

    async def test_delete_stream_uses_browser_release_ack(self) -> None:
        session, _ = await self.create()
        stream = await self.manager.add_stream(
            session.session_id,
            owner_key="owner-a",
            device_id="WXB339",
        )
        await self.manager.handle_client_event(
            session.session_id,
            event="room_joined",
            stream_id=stream.stream_id,
            error_code=None,
            details={},
        )
        socket = FakeControlSocket()
        session.control_socket = socket
        task = asyncio.create_task(
            self.manager.delete_stream(
                session.session_id,
                stream.stream_id,
                owner_key="owner-a",
            )
        )
        while not socket.commands:
            await asyncio.sleep(0)
        await self.manager.handle_control_message(
            session.session_id,
            {
                "type": "ack",
                "command_id": socket.commands[0]["command_id"],
                "ok": True,
            },
        )
        await task
        self.assertIsNone(FakeAdapter.instances[0].authorized_device)
        self.assertTrue(session.connection_reusable)

    async def test_close_is_idempotent(self) -> None:
        session, _ = await self.create()
        await self.manager.add_stream(
            session.session_id,
            owner_key="owner-a",
            device_id="WXB339",
        )
        first = await self.manager.close_session(
            session.session_id,
            owner_key="owner-a",
        )
        second = await self.manager.close_session(
            session.session_id,
            owner_key="owner-a",
        )
        self.assertIs(first, second)
        self.assertEqual(second.status, SessionStatus.CLOSED)
        self.assertEqual(FakeAdapter.instances[0].disconnect_calls, 1)

    async def test_illegal_session_and_owner_are_rejected(self) -> None:
        with self.assertRaises(RealtimeError) as missing:
            await self.manager.get_session("missing", owner_key="owner-a")
        self.assertEqual(missing.exception.code, "session_not_found")
        session, _ = await self.create()
        with self.assertRaises(RealtimeError) as forbidden:
            await self.manager.get_session(
                session.session_id,
                owner_key="owner-b",
            )
        self.assertEqual(forbidden.exception.code, "session_forbidden")

    async def test_client_first_frame_updates_observable_state(self) -> None:
        session, _ = await self.create()
        stream = await self.manager.add_stream(
            session.session_id,
            owner_key="owner-a",
            device_id="WXB339",
        )
        await self.manager.handle_client_event(
            session.session_id,
            event="first_frame",
            stream_id=stream.stream_id,
            error_code=None,
            details={
                "width": 1920,
                "height": 1080,
                "track_state": "live",
            },
        )
        self.assertEqual(session.status, SessionStatus.PLAYING)
        self.assertEqual(session.connection_reusable, False)
        self.assertEqual(stream.status, StreamStatus.PLAYING)
        self.assertEqual(stream.width, 1920)
        self.assertEqual(stream.track_state, "live")

        await self.manager.handle_client_event(
            session.session_id,
            event="room_joined",
            stream_id=stream.stream_id,
            error_code=None,
            details={},
        )
        self.assertTrue(session.connection_reusable)

    async def test_expired_session_is_force_closed_without_zombie(self) -> None:
        session, _ = await self.create()
        await self.manager.add_stream(
            session.session_id,
            owner_key="owner-a",
            device_id="WXB339",
        )
        session.expires_at = session.created_at - dt.timedelta(seconds=1)
        await self.manager.cleanup_expired()
        self.assertEqual(session.status, SessionStatus.CLOSED)
        self.assertEqual(session.streams, {})
        self.assertEqual(FakeAdapter.instances[0].disconnect_calls, 1)

    async def test_control_disconnect_forces_upstream_release(self) -> None:
        session, _ = await self.create()
        stream = await self.manager.add_stream(
            session.session_id,
            owner_key="owner-a",
            device_id="WXB339",
        )
        socket = FakeControlSocket()
        session.control_socket = socket
        await self.manager.detach_control(session.session_id, socket)
        self.assertEqual(session.status, SessionStatus.DEGRADED)
        self.assertEqual(stream.status, StreamStatus.DEGRADED)
        self.assertFalse(session.connection_reusable)
        self.assertEqual(FakeAdapter.instances[0].disconnect_calls, 1)

    async def test_unexpected_media_proxy_close_releases_session(self) -> None:
        session, _ = await self.create()
        stream = await self.manager.add_stream(
            session.session_id,
            owner_key="owner-a",
            device_id="WXB339",
        )
        await self.manager.proxy_websocket(
            session.session_id,
            kind="media",
            socket=object(),
            proxy_host="cha.example",
        )
        self.assertEqual(session.status, SessionStatus.DEGRADED)
        self.assertEqual(stream.status, StreamStatus.DEGRADED)
        self.assertFalse(session.connection_reusable)
        self.assertEqual(FakeAdapter.instances[0].disconnect_calls, 1)

    async def test_proxy_runtime_error_is_wrapped_and_released(self) -> None:
        session, _ = await self.create()
        stream = await self.manager.add_stream(
            session.session_id,
            owner_key="owner-a",
            device_id="WXB339",
        )

        async def fail_proxy(*_args, **_kwargs) -> None:
            raise RuntimeError("token=must-not-leak")

        session.adapter.proxy = fail_proxy
        with self.assertRaisesRegex(
            RuntimeError,
            "AEE media relay failed",
        ):
            await self.manager.proxy_websocket(
                session.session_id,
                kind="media",
                socket=object(),
                proxy_host="cha.example",
            )
        self.assertEqual(session.status, SessionStatus.DEGRADED)
        self.assertEqual(stream.status, StreamStatus.DEGRADED)
        self.assertEqual(FakeAdapter.instances[0].disconnect_calls, 1)


class AEEAdapterTests(unittest.TestCase):
    def test_upstream_urls_are_redacted(self) -> None:
        redacted = redact_upstream_error(
            "ws://host/?token=abc&pwd=def&sessionId=ghi"
        )
        self.assertNotIn("abc", redacted)
        self.assertNotIn("def", redacted)
        self.assertNotIn("ghi", redacted)

    def test_connect_info_is_rewritten_without_real_token(self) -> None:
        with patch.dict(
            os.environ,
            {
                **REALTIME_ENV,
                "CHA_V2_AEE_API_BASE_URL": "http://aee.example",
                "CHA_V2_AEE_GATEWAY_HOST": "gateway.example",
                "CHA_V2_AEE_USERNAME": "server-user",
                "CHA_V2_AEE_PASSWORD": "server-password",
            },
            clear=False,
        ):
            adapter = AEEAdapter("session-1", Settings.from_env())
        message = adapter._capture_and_rewrite_gateway(
            (
                '{"request":true,"method":"ConnecteInfo","data":{'
                '"mediaIp":"10.0.0.8","mediaPort":7710,'
                '"mediaDomain":"media.example","mediaSslPort":7705,'
                '"token":"real-media-token","devid":"server-user",'
                '"userType":5,"ftp":{"pwd":"ftp-secret"},'
                '"ossServer":{"accessSecret":"oss-secret"}}}'
            ),
            "cha.example",
        )
        self.assertNotIn("real-media-token", message)
        self.assertNotIn("server-user", message)
        self.assertNotIn("ftp-secret", message)
        self.assertNotIn("oss-secret", message)
        self.assertIn("cha-realtime-proxy", message)
        self.assertIn('"devid":"cha-realtime"', message)
        self.assertIn(
            "/ws/v2/realtime/session-1/media",
            message,
        )
        self.assertEqual(adapter._media_info["token"], "real-media-token")

    def test_media_allowlist_accepts_only_selected_receive_video(self) -> None:
        with patch.dict(
            os.environ,
            {
                **REALTIME_ENV,
                "CHA_V2_AEE_API_BASE_URL": "http://aee.example",
                "CHA_V2_AEE_ORIGIN": "http://aee.example",
                "CHA_V2_AEE_GATEWAY_HOST": "gateway.example",
                "CHA_V2_AEE_USERNAME": "server-user",
                "CHA_V2_AEE_PASSWORD": "server-password",
            },
            clear=False,
        ):
            adapter = AEEAdapter("session-1", Settings.from_env())
        adapter.authorize_device("WXB339")
        adapter._validate_client_message(
            "media",
            json.dumps(
                {
                    "request": True,
                    "method": "createWebRtcTransport",
                    "data": {"producing": False, "consuming": True},
                }
            ),
        )
        adapter._validate_client_message(
            "media",
            json.dumps(
                {
                    "request": True,
                    "method": "mediaMonitor",
                    "data": {
                        "kind": "video",
                        "devId": "WXB339",
                        "streamType": 2,
                    },
                }
            ),
        )
        with self.assertRaisesRegex(RuntimeError, "one live video"):
            adapter._validate_client_message(
                "media",
                json.dumps(
                    {
                        "request": True,
                        "method": "mediaMonitor",
                        "data": {
                            "kind": "video",
                            "devId": "WXB339",
                            "streamType": 2,
                        },
                    }
                ),
            )
        adapter._validate_client_message(
            "media",
            json.dumps(
                {
                    "request": True,
                    "method": "closeMediaMonitor",
                    "data": {
                        "kind": "video",
                        "devId": "WXB339",
                        "streamType": 2,
                    },
                }
            ),
        )
        adapter._validate_client_message(
            "media",
            json.dumps(
                {
                    "request": True,
                    "method": "join",
                    "data": {
                        "displayName": "browser",
                        "rtpCapabilities": {},
                    },
                }
            ),
        )
        adapter._validate_client_message(
            "media",
            json.dumps(
                {
                    "request": True,
                    "method": "mediaMonitor",
                    "data": {
                        "kind": "video",
                        "devId": "WXB339",
                        "streamType": 2,
                    },
                }
            ),
        )
        with self.assertRaisesRegex(
            RuntimeError,
            "selected live video",
        ):
            adapter._validate_client_message(
                "media",
                json.dumps(
                    {
                        "request": True,
                        "method": "mediaMonitor",
                        "data": {
                            "kind": "audio",
                            "devId": "WXB339",
                            "streamType": 0,
                        },
                    }
                ),
            )
        with self.assertRaisesRegex(RuntimeError, "not allowed"):
            adapter._validate_client_message(
                "media",
                json.dumps(
                    {
                        "request": True,
                        "method": "playCtrl",
                        "data": {},
                    }
                ),
            )
        with self.assertRaisesRegex(RuntimeError, "mcs8_admin"):
            adapter._validate_client_message(
                "media",
                json.dumps(
                    {
                        "request": True,
                        "method": "getRouterRtpCapabilities",
                        "data": {"roomId": "another-room"},
                    }
                ),
            )

    def test_gateway_allows_only_protoo_responses(self) -> None:
        with patch.dict(
            os.environ,
            {
                **REALTIME_ENV,
                "CHA_V2_AEE_API_BASE_URL": "http://aee.example",
                "CHA_V2_AEE_ORIGIN": "http://aee.example",
                "CHA_V2_AEE_GATEWAY_HOST": "gateway.example",
                "CHA_V2_AEE_USERNAME": "server-user",
                "CHA_V2_AEE_PASSWORD": "server-password",
            },
            clear=False,
        ):
            adapter = AEEAdapter("session-1", Settings.from_env())
        adapter._validate_client_message(
            "gateway",
            json.dumps({"response": True, "id": 1, "ok": True}),
        )
        with self.assertRaisesRegex(RuntimeError, "not allowed"):
            adapter._validate_client_message(
                "gateway",
                json.dumps(
                    {"request": True, "method": "deviceControl", "data": {}}
                ),
            )


if __name__ == "__main__":
    unittest.main()
