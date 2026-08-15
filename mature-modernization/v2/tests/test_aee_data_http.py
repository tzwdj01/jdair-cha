from __future__ import annotations

import io
import json
import unittest
import urllib.error

from app.data.aee_http import AEEDataHTTPClient, AEEDataHTTPError


class _Response:
    def __init__(self, payload: object) -> None:
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


class AEEDataHTTPClientTests(unittest.TestCase):
    def test_get_uses_custom_token_header_and_encodes_query(self) -> None:
        captured = {}

        def opener(request, *, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return _Response({"result": 200, "data": []})

        client = AEEDataHTTPClient(
            base_url="http://aee.example.test/",
            token_provider=lambda: "test-access-token",
            timeout_seconds=3.5,
            opener=opener,
        )

        payload = client.get_json(
            "/api/v1/DevOnlineList",
            query={"devId": "WX 1", "page": 1},
        )

        request = captured["request"]
        self.assertEqual(payload["result"], 200)
        self.assertEqual(captured["timeout"], 3.5)
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(
            request.full_url,
            "http://aee.example.test/api/v1/DevOnlineList"
            "?devId=WX+1&page=1",
        )
        self.assertEqual(
            request.get_header("Token"),
            "test-access-token",
        )
        self.assertIsNone(request.data)

    def test_unauthorized_invalidates_and_retries_once(self) -> None:
        tokens = iter(["expired-token", "fresh-token"])
        invalidations = []
        seen_tokens = []

        def opener(request, *, timeout):
            del timeout
            seen_tokens.append(request.get_header("Token"))
            if len(seen_tokens) == 1:
                raise urllib.error.HTTPError(
                    request.full_url,
                    401,
                    "unauthorized",
                    {},
                    io.BytesIO(),
                )
            return _Response({"result": 200})

        client = AEEDataHTTPClient(
            base_url="https://aee.example.test",
            token_provider=lambda: next(tokens),
            token_invalidator=lambda: invalidations.append(True),
            opener=opener,
        )

        self.assertEqual(
            client.get_json("/api/v1/ext/DevTree"),
            {"result": 200},
        )
        self.assertEqual(
            seen_tokens,
            ["expired-token", "fresh-token"],
        )
        self.assertEqual(invalidations, [True])

    def test_forbidden_is_not_retried_or_leaked(self) -> None:
        calls = []
        invalidations = []

        def opener(request, *, timeout):
            del timeout
            calls.append(request)
            raise urllib.error.HTTPError(
                request.full_url,
                403,
                "forbidden token=must-not-leak",
                {},
                io.BytesIO(),
            )

        client = AEEDataHTTPClient(
            base_url="https://aee.example.test",
            token_provider=lambda: "must-not-leak",
            token_invalidator=lambda: invalidations.append(True),
            opener=opener,
        )

        with self.assertRaises(AEEDataHTTPError) as raised:
            client.get_json("/api/v1/AlarmList")

        self.assertEqual(raised.exception.code, "AEE_DATA_FORBIDDEN")
        self.assertEqual(raised.exception.status_code, 403)
        self.assertNotIn("must-not-leak", str(raised.exception))
        self.assertEqual(len(calls), 1)
        self.assertEqual(invalidations, [])

    def test_unknown_path_is_rejected_before_token_access(self) -> None:
        token_calls = []
        client = AEEDataHTTPClient(
            base_url="https://aee.example.test",
            token_provider=lambda: token_calls.append(True) or "token",
        )

        with self.assertRaises(AEEDataHTTPError) as raised:
            client.get_json("/api/v1/RecordFileDel")

        self.assertEqual(
            raised.exception.code,
            "AEE_DATA_PATH_NOT_ALLOWED",
        )
        self.assertEqual(token_calls, [])

    def test_invalid_token_and_response_are_bounded(self) -> None:
        client = AEEDataHTTPClient(
            base_url="https://aee.example.test",
            token_provider=lambda: "",
        )
        with self.assertRaises(AEEDataHTTPError) as missing:
            client.get_json("/api/v1/RecordFileList")
        self.assertEqual(
            missing.exception.code,
            "AEE_DATA_AUTH_NOT_CONFIGURED",
        )

        invalid = AEEDataHTTPClient(
            base_url="https://aee.example.test",
            token_provider=lambda: "token",
            opener=lambda request, timeout: _Response(["not", "envelope"]),
        )
        with self.assertRaises(AEEDataHTTPError) as malformed:
            invalid.get_json("/api/v1/RecordFileList")
        self.assertEqual(
            malformed.exception.code,
            "AEE_DATA_INVALID_RESPONSE",
        )

    def test_token_provider_and_invalidator_failures_are_bounded(self) -> None:
        provider_failure = AEEDataHTTPClient(
            base_url="https://aee.example.test",
            token_provider=lambda: (_ for _ in ()).throw(
                RuntimeError("token=must-not-leak")
            ),
        )
        with self.assertRaises(AEEDataHTTPError) as provider_error:
            provider_failure.get_json("/api/v1/ext/DevTree")
        self.assertEqual(
            provider_error.exception.code,
            "AEE_DATA_AUTH_UNAVAILABLE",
        )
        self.assertNotIn(
            "must-not-leak",
            str(provider_error.exception),
        )

        def unauthorized(request, *, timeout):
            del timeout
            raise urllib.error.HTTPError(
                request.full_url,
                401,
                "unauthorized",
                {},
                io.BytesIO(),
            )

        invalidator_failure = AEEDataHTTPClient(
            base_url="https://aee.example.test",
            token_provider=lambda: "expired-token",
            token_invalidator=lambda: (_ for _ in ()).throw(
                RuntimeError("token=must-not-leak")
            ),
            opener=unauthorized,
        )
        with self.assertRaises(AEEDataHTTPError) as invalidator_error:
            invalidator_failure.get_json("/api/v1/ext/DevTree")
        self.assertEqual(
            invalidator_error.exception.code,
            "AEE_DATA_AUTH_REFRESH_FAILED",
        )
        self.assertNotIn(
            "must-not-leak",
            str(invalidator_error.exception),
        )

    def test_base_url_rejects_credentials_paths_and_non_http(self) -> None:
        invalid_urls = (
            "file:///tmp/aee",
            "https://user:pass@aee.example.test",
            "https://aee.example.test/prefix",
            "https://aee.example.test?token=value",
        )
        for value in invalid_urls:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    AEEDataHTTPClient(
                        base_url=value,
                        token_provider=lambda: "token",
                    )


if __name__ == "__main__":
    unittest.main()
