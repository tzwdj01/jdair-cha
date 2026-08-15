from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from typing import Any


READ_ONLY_PATHS = frozenset(
    {
        "/api/v1/AlarmList",
        "/api/v1/DevOnlineList",
        "/api/v1/RecordFileList",
        "/api/v1/ext/DevTree",
    }
)
TokenProvider = Callable[[], str]
TokenInvalidator = Callable[[], None]
URLOpener = Callable[..., Any]


class AEEDataHTTPError(RuntimeError):
    """Bounded CHA-owned error for the read-only AEE data transport."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class AEEDataHTTPClient:
    """Narrow server-side GET transport for evidenced AEE data endpoints.

    The caller owns login and in-memory token lifecycle. This client never
    receives usernames/passwords and never returns the token to an API caller.
    Static AEE evidence shows that data requests use the access token in the
    custom ``token`` header. A live token-only integration test is still
    required before production ingestion is enabled.
    """

    def __init__(
        self,
        *,
        base_url: str,
        token_provider: TokenProvider,
        token_invalidator: TokenInvalidator | None = None,
        timeout_seconds: float = 10.0,
        opener: URLOpener = urllib.request.urlopen,
    ) -> None:
        self._base_url = _normalize_base_url(base_url)
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._token_provider = token_provider
        self._token_invalidator = token_invalidator
        self._timeout_seconds = timeout_seconds
        self._opener = opener

    def get_json(
        self,
        path: str,
        *,
        query: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if path not in READ_ONLY_PATHS:
            raise AEEDataHTTPError(
                "AEE_DATA_PATH_NOT_ALLOWED",
                "The requested AEE data path is not allow-listed",
            )

        try:
            return self._get_json_once(path, query=query)
        except AEEDataHTTPError as exc:
            if (
                exc.code != "AEE_DATA_AUTH_EXPIRED"
                or self._token_invalidator is None
            ):
                raise
            try:
                self._token_invalidator()
            except Exception:
                raise AEEDataHTTPError(
                    "AEE_DATA_AUTH_REFRESH_FAILED",
                    "AEE data authentication could not be refreshed",
                ) from None
            return self._get_json_once(path, query=query)

    def _get_json_once(
        self,
        path: str,
        *,
        query: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        token = self._get_token()

        url = self._build_url(path, query=query)
        request = urllib.request.Request(
            url,
            method="GET",
            headers={
                "Accept": "application/json",
                "token": token,
                "User-Agent": "Mozilla/5.0 CHA-Inspection-Data/0.1",
            },
        )
        try:
            with self._opener(
                request,
                timeout=self._timeout_seconds,
            ) as response:
                body = response.read()
        except urllib.error.HTTPError as exc:
            status_code = exc.code
            exc.close()
            if status_code == 401:
                raise AEEDataHTTPError(
                    "AEE_DATA_AUTH_EXPIRED",
                    "AEE data authentication was rejected",
                    status_code=401,
                ) from exc
            if status_code == 403:
                raise AEEDataHTTPError(
                    "AEE_DATA_FORBIDDEN",
                    "AEE data access is not permitted",
                    status_code=403,
                ) from exc
            raise AEEDataHTTPError(
                "AEE_DATA_HTTP_ERROR",
                "AEE data request failed",
                status_code=status_code,
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise AEEDataHTTPError(
                "AEE_DATA_UNAVAILABLE",
                "AEE data endpoint is unavailable",
            ) from exc

        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AEEDataHTTPError(
                "AEE_DATA_INVALID_RESPONSE",
                "AEE data endpoint returned invalid JSON",
            ) from exc
        if not isinstance(payload, dict):
            raise AEEDataHTTPError(
                "AEE_DATA_INVALID_RESPONSE",
                "AEE data endpoint returned an invalid envelope",
            )
        return payload

    def _get_token(self) -> str:
        try:
            token = self._token_provider()
        except Exception:
            raise AEEDataHTTPError(
                "AEE_DATA_AUTH_UNAVAILABLE",
                "AEE data authentication is unavailable",
            ) from None
        if (
            not isinstance(token, str)
            or not token.strip()
            or "\r" in token
            or "\n" in token
        ):
            raise AEEDataHTTPError(
                "AEE_DATA_AUTH_NOT_CONFIGURED",
                "AEE data authentication is not configured",
            )
        return token.strip()

    def _build_url(
        self,
        path: str,
        *,
        query: Mapping[str, Any] | None,
    ) -> str:
        url = self._base_url + path
        if not query:
            return url
        return url + "?" + urllib.parse.urlencode(query, doseq=True)


def _normalize_base_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value.strip())
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ValueError("base_url must be an HTTP(S) origin")
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, "", "", "")
    )
