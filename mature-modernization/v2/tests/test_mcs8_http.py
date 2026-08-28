from __future__ import annotations

import json
import unittest
import urllib.error
import urllib.parse

from app.data.aee_http import AEEDataHTTPError
from app.data.mcs8_http import MCS8DataHTTPClient


class _Response:
    def __init__(self, payload: object) -> None:
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


class MCS8DataHTTPClientTests(unittest.TestCase):
    def test_get_uses_token_header_and_session_id_query(self) -> None:
        captured = {}

        def opener(request, *, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return _Response({"error": 200, "data": []})

        client = MCS8DataHTTPClient(
            base_url="http://mcs8.test.invalid:7712",
            token_provider=lambda: "mcs8-session-token",
            timeout_seconds=7.0,
            opener=opener,
        )
        payload = client.get_json(
            "/api/v1/RecordFileList",
            query={"page": 1, "pagesize": 10},
        )
        request = captured["request"]
        self.assertEqual(payload["error"], 200)
        self.assertEqual(captured["timeout"], 7.0)
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(
            request.get_header("Token"),
            "mcs8-session-token",
        )
        url = request.full_url
        parsed = urllib.parse.urlsplit(url)
        self.assertEqual(parsed.netloc, "mcs8.test.invalid:7712")
        query = urllib.parse.parse_qs(parsed.query)
        self.assertEqual(query["SessionId"], ["mcs8-session-token"])
        self.assertEqual(query["page"], ["1"])

    def test_path_not_allow_listed_raises(self) -> None:
        client = MCS8DataHTTPClient(
            base_url="http://mcs8.test.invalid:7712",
            token_provider=lambda: "token",
            timeout_seconds=5.0,
        )
        with self.assertRaises(AEEDataHTTPError) as ctx:
            client.get_json("/api/private/secret")
        self.assertEqual(ctx.exception.code, "MCS8_DATA_PATH_NOT_ALLOWED")

    def test_http_401_triggers_invalidator_then_retries(self) -> None:
        calls = {"count": 0, "invalidated": 0}

        def opener(request, *, timeout):
            calls["count"] += 1
            raise urllib.error.HTTPError(
                request.full_url,
                401,
                "Unauthorized",
                {},
                None,
            )

        def invalidate() -> None:
            calls["invalidated"] += 1

        client = MCS8DataHTTPClient(
            base_url="http://mcs8.test.invalid:7712",
            token_provider=lambda: "stale-token",
            token_invalidator=invalidate,
            timeout_seconds=5.0,
            opener=opener,
        )
        with self.assertRaises(AEEDataHTTPError) as ctx:
            client.get_json("/api/v1/AlarmList")
        self.assertEqual(ctx.exception.code, "MCS8_DATA_AUTH_EXPIRED")
        self.assertEqual(calls["invalidated"], 1)

    def test_invalid_base_url_rejected(self) -> None:
        with self.assertRaises(ValueError):
            MCS8DataHTTPClient(
                base_url="http://user:pass@mcs8.test.invalid:7712/",
                token_provider=lambda: "token",
                timeout_seconds=5.0,
            )


if __name__ == "__main__":
    unittest.main()
