from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import struct
import time
import urllib.parse
from typing import Any, Callable


SocketFactory = Callable[[str, int], socket.socket]


class MCS8AuthError(RuntimeError):
    """CHA-owned bounded error for the MCS8 native login channel."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _ws_read_exact(
    sock: socket.socket,
    buffer: bytearray,
    size: int,
) -> bytes:
    while len(buffer) < size:
        chunk = sock.recv(max(4096, size - len(buffer)))
        if not chunk:
            raise MCS8AuthError(
                "MCS8_AUTH_CONNECTION_CLOSED",
                "MCS8 WebSocket connection closed during login",
            )
        buffer.extend(chunk)
    data = bytes(buffer[:size])
    del buffer[:size]
    return data


def _ws_read_frame(
    sock: socket.socket,
    buffer: bytearray,
) -> tuple[int, bytes]:
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
        payload = bytes(
            payload[i] ^ mask[i % 4]
            for i in range(len(payload))
        )
    return opcode, payload


def _ws_send_frame(
    sock: socket.socket,
    opcode: int,
    payload: bytes = b"",
) -> None:
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


class MCS8ServerAuthProvider:
    """MCS8 native login provider (WS handshake -> server session token).

    This mirrors the already production-verified MCS8 login semantics used by
    the legacy panel (``mcs8_ws_login``): a raw WebSocket handshake to the
    MCS8 SDK port carrying ``uid`` + md5 password, followed by the
    ``ConnecteInfo`` notification that carries the server token/session.

    The provider never logs or returns the password, and the returned token
    is only held in memory for the guarded MCS8 data transport. Endpoint
    values come from configuration, never from hardcoded constants.
    """

    def __init__(
        self,
        *,
        host: str,
        ws_port: int,
        username: str,
        password: str,
        timeout_seconds: float = 12.0,
        socket_factory: SocketFactory | None = None,
    ) -> None:
        if not host:
            raise ValueError("MCS8 host is required")
        if ws_port <= 0:
            raise ValueError("MCS8 ws_port must be positive")
        if not username or not password:
            raise ValueError("MCS8 username and password are required")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._host = host
        self._ws_port = ws_port
        self._username = username.strip()
        self._password = password
        self._timeout_seconds = timeout_seconds
        self._socket_factory = socket_factory or (
            lambda host, port: socket.create_connection(
                (host, port),
                timeout=self._timeout_seconds,
            )
        )
        self._token: str | None = None
        self._connect_info: dict[str, Any] = {}
        self._last_login_at: float | None = None

    @property
    def token(self) -> str | None:
        return self._token

    @property
    def has_token(self) -> bool:
        return bool(self._token)

    def invalidate(self) -> None:
        self._token = None
        self._connect_info = {}
        self._last_login_at = None

    def login(self) -> str:
        """Perform the MCS8 WS login and return the server session token."""

        username = self._username
        pwd_md5 = hashlib.md5(self._password.encode("utf-8")).hexdigest()
        ws_key = base64.b64encode(os.urandom(16)).decode("ascii")
        path = f"/?uid={urllib.parse.quote(username)}&pwd={pwd_md5}"
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {self._host}:{self._ws_port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {ws_key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "Sec-WebSocket-Protocol: protoo\r\n"
            "Origin: http://aee.jdcloud.com\r\n"
            "User-Agent: JD-Air-WebPanel/1.0\r\n"
            "\r\n"
        ).encode("utf-8")

        sock = self._socket_factory(self._host, self._ws_port)
        try:
            sock.settimeout(self._timeout_seconds)
            sock.sendall(request)
            raw = bytearray()
            deadline = time.time() + self._timeout_seconds
            while b"\r\n\r\n" not in raw:
                if time.time() > deadline:
                    raise MCS8AuthError(
                        "MCS8_AUTH_HANDSHAKE_TIMEOUT",
                        "MCS8 WebSocket handshake timed out",
                    )
                chunk = sock.recv(4096)
                if not chunk:
                    raise MCS8AuthError(
                        "MCS8_AUTH_HANDSHAKE_FAILED",
                        "MCS8 WebSocket handshake failed",
                    )
                raw.extend(chunk)
            header_raw, rest = bytes(raw).split(b"\r\n\r\n", 1)
            status_line = header_raw.split(b"\r\n", 1)[0].decode(
                "latin1",
                "replace",
            )
            if " 101 " not in status_line:
                raise MCS8AuthError(
                    "MCS8_AUTH_LOGIN_REJECTED",
                    f"MCS8 login failed: {status_line}",
                )

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
                if (
                    message.get("notification")
                    and message.get("method") == "ConnecteInfo"
                ):
                    data = message.get("data")
                    if isinstance(data, dict):
                        connect_info = data
                        break
                if message.get("response") and message.get("ok") is False:
                    raise MCS8AuthError(
                        "MCS8_AUTH_LOGIN_REJECTED",
                        str(
                            message.get("errorReason")
                            or message.get("error")
                            or "MCS8 login failed"
                        ),
                    )

            if not connect_info:
                raise MCS8AuthError(
                    "MCS8_AUTH_CONNECT_INFO_MISSING",
                    "MCS8 login succeeded but ConnecteInfo was not received",
                )
            token = (
                connect_info.get("token")
                or connect_info.get("SessionId")
                or connect_info.get("sessionId")
            )
            if not token:
                raise MCS8AuthError(
                    "MCS8_AUTH_TOKEN_MISSING",
                    "MCS8 login did not return a token",
                )
            self._token = str(token)
            self._connect_info = connect_info
            self._last_login_at = time.time()
            return self._token
        finally:
            try:
                sock.close()
            except OSError:
                pass
