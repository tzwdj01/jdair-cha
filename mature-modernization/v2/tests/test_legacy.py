from __future__ import annotations

import http.server
import json
import threading
import unittest

from app.services.legacy import LegacyClient


class _Handler(http.server.BaseHTTPRequestHandler):
    cookie_seen = ""
    query_seen = ""

    def log_message(self, *_args) -> None:
        return

    def do_GET(self) -> None:
        if self.path == "/":
            body = b"<html>legacy</html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
        elif self.path == "/api/dashboard":
            _Handler.cookie_seen = self.headers.get("Cookie", "")
            body = json.dumps(
                {
                    "devices": {"total": 3, "online": 2, "offline": 1},
                    "cities": ["Beijing"],
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
        elif self.path.startswith("/api/flights?"):
            _Handler.query_seen = self.path
            body = json.dumps({"total": 3, "records": []}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
        else:
            body = b"not found"
            self.send_response(404)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class LegacyClientTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0),
            _Handler,
        )
        cls.thread = threading.Thread(
            target=cls.server.serve_forever,
            daemon=True,
        )
        cls.thread.start()
        host, port = cls.server.server_address
        cls.client = LegacyClient(f"http://{host}:{port}", 2)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    async def test_health_reports_legacy_root(self) -> None:
        result = await self.client.health()
        self.assertEqual(result.status_code, 200)
        self.assertIn("text/html", result.content_type)

    async def test_dashboard_forwards_cookie_and_parses_json(self) -> None:
        result = await self.client.dashboard("cha_session=test")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(_Handler.cookie_seen, "cha_session=test")
        self.assertEqual(result.json()["devices"]["online"], 2)

    async def test_allowlisted_query_is_encoded(self) -> None:
        result = await self.client.flights("cha_session=test", "2026-08-13")
        self.assertEqual(result.status_code, 200)
        self.assertIn("date=2026-08-13", _Handler.query_seen)
        self.assertIn("size=100", _Handler.query_seen)

    async def test_non_allowlisted_path_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            await self.client.get("http://example.com/private", None)


if __name__ == "__main__":
    unittest.main()
