from __future__ import annotations

import base64
import json
import socket
import struct
import unittest

from app.data.mcs8_auth import MCS8AuthError, MCS8ServerAuthProvider


def _server_frame(payload: bytes) -> bytes:
    header = bytearray([0x81])
    length = len(payload)
    if length < 126:
        header.append(length)
    elif length < 65536:
        header.append(126)
        header.extend(struct.pack("!H", length))
    else:
        header.append(127)
        header.extend(struct.pack("!Q", length))
    return bytes(header) + payload


class _FakeSocket:
    def __init__(
        self,
        *,
        handshake: bytes,
        frames: list[bytes],
        fail_after_handshake: bool = False,
    ) -> None:
        self._handshake = bytearray(handshake)
        self._stream = bytearray(b"".join(frames))
        self._fail_after_handshake = fail_after_handshake
        self._sent = bytearray()
        self.timeout = None

    def settimeout(self, value: float) -> None:
        self.timeout = value

    def sendall(self, data: bytes) -> None:
        self._sent.extend(data)

    def recv(self, size: int) -> bytes:
        if self._handshake:
            chunk = bytes(self._handshake[:size])
            del self._handshake[:size]
            return chunk
        if self._fail_after_handshake:
            return b""
        if not self._stream:
            return b""
        chunk = bytes(self._stream[:size])
        del self._stream[:size]
        return chunk

    def close(self) -> None:
        pass


def _connect_info_frame(token: str) -> bytes:
    payload = json.dumps(
        {
            "notification": True,
            "method": "ConnecteInfo",
            "data": {"token": token, "defaultGroup": 30000002},
        }
    ).encode("utf-8")
    return _server_frame(payload)


class MCS8ServerAuthProviderTests(unittest.TestCase):
    def _provider(self, socket_factory) -> MCS8ServerAuthProvider:
        return MCS8ServerAuthProvider(
            host="116.198.18.19",
            ws_port=7711,
            username="mcs8-test-user",
            password="test-password",
            timeout_seconds=2.0,
            socket_factory=socket_factory,
        )

    def test_login_returns_token_and_uses_md5_password(self) -> None:
        handshake = b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n\r\n"
        fake = _FakeSocket(
            handshake=handshake,
            frames=[_connect_info_frame("server-token-123")],
        )

        def factory(host: str, port: int) -> socket.socket:
            self.assertEqual(host, "116.198.18.19")
            self.assertEqual(port, 7711)
            return fake  # type: ignore[return-value]

        provider = self._provider(factory)
        token = provider.login()
        self.assertEqual(token, "server-token-123")
        self.assertTrue(provider.has_token)
        request_text = bytes(fake._sent).decode("utf-8", "replace")
        self.assertIn("GET /?uid=mcs8-test-user&pwd=", request_text)
        self.assertNotIn("test-password", request_text)
        self.assertIn("Sec-WebSocket-Protocol: protoo", request_text)

    def test_login_rejected_raises_bounded_error(self) -> None:
        fake = _FakeSocket(
            handshake=b"HTTP/1.1 401 Unauthorized\r\n\r\n",
            frames=[],
        )

        def factory(host: str, port: int) -> socket.socket:
            return fake  # type: ignore[return-value]

        provider = self._provider(factory)
        with self.assertRaises(MCS8AuthError) as ctx:
            provider.login()
        self.assertEqual(ctx.exception.code, "MCS8_AUTH_LOGIN_REJECTED")

    def test_invalidate_clears_token(self) -> None:
        handshake = b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n\r\n"
        fake = _FakeSocket(
            handshake=handshake,
            frames=[_connect_info_frame("server-token-123")],
        )
        provider = self._provider(lambda host, port: fake)  # type: ignore[arg-type]
        provider.login()
        self.assertTrue(provider.has_token)
        provider.invalidate()
        self.assertFalse(provider.has_token)
        self.assertIsNone(provider.token)


if __name__ == "__main__":
    unittest.main()
