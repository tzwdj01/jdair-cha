from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from typing import Any

from .aee_http import AEEDataHTTPError


READ_ONLY_PATHS = frozenset(
    {
        "/api/v1/DevOnlineList",
        "/api/v1/RecordFileList",
        "/api/v1/AlarmList",
        "/api/GetDevListByGroupId",
        "/api/GetRecordFileList",
        "/api/GetGpsModelList",
    }
)
TokenProvider = Callable[[], str]
TokenInvalidator = Callable[[], None]
URLOpener = Callable[..., Any]


class MCS8DataHTTPClient:
    """Narrow server-side GET transport for the MCS8 native channel.

    The MCS8 native channel (WS login on the SDK port, REST on the API port)
    is the supported server-side data path identified in
    ``docs/aee/M4_P3_2_ACCESS_PATH_DIAGNOSTIC_20260816.md``. It does not go
    through the aee.jdcloud.com JFE front-end, so the CHA production host can
    reach it without the HTTP 493 WAF block.

    Requests carry the MCS8 server token in the custom ``token`` header and
    as the ``SessionId`` query parameter, matching the legacy
    ``call_mcs8_api`` semantics. The caller owns login and token lifecycle;
    this client never receives usernames/passwords and never returns the
    token to an API caller.
    """

    def __init__(
        self,
        *,
        base_url: str,
        token_provider: TokenProvider,
        token_invalidator: TokenInvalidator | None = None,
        timeout_seconds: float = 20.0,
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
                "MCS8_DATA_PATH_NOT_ALLOWED",
                "The requested MCS8 data path is not allow-listed",
            )
        try:
            return self._get_json_once(path, query=query)
        except AEEDataHTTPError as exc:
            if (
                exc.code != "MCS8_DATA_AUTH_EXPIRED"
                or self._token_invalidator is None
            ):
                raise
            try:
                self._token_invalidator()
            except Exception:
                raise AEEDataHTTPError(
                    "MCS8_DATA_AUTH_REFRESH_FAILED",
                    "MCS8 data authentication could not be refreshed",
                ) from None
            return self._get_json_once(path, query=query)

    def _get_json_once(
        self,
        path: str,
        *,
        query: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        token = self._get_token()
        merged_query = dict(query or {})
        merged_query.setdefault("SessionId", token)

        url = self._build_url(path, query=merged_query)
        request = urllib.request.Request(
            url,
            method="GET",
            headers={
                "Accept": "application/json",
                "token": token,
                "User-Agent": "JD-Air-WebPanel/1.0",
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
                    "MCS8_DATA_AUTH_EXPIRED",
                    "MCS8 data authentication was rejected",
                    status_code=401,
                ) from exc
            if status_code == 403:
                raise AEEDataHTTPError(
                    "MCS8_DATA_FORBIDDEN",
                    "MCS8 data access is not permitted",
                    status_code=403,
                ) from exc
            raise AEEDataHTTPError(
                "MCS8_DATA_HTTP_ERROR",
                "MCS8 data request failed",
                status_code=status_code,
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise AEEDataHTTPError(
                "MCS8_DATA_UNAVAILABLE",
                "MCS8 data endpoint is unavailable",
            ) from exc

        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AEEDataHTTPError(
                "MCS8_DATA_INVALID_RESPONSE",
                "MCS8 data endpoint returned invalid JSON",
            ) from exc
        if not isinstance(payload, dict):
            raise AEEDataHTTPError(
                "MCS8_DATA_INVALID_RESPONSE",
                "MCS8 data endpoint returned an invalid envelope",
            )
        return payload

    def _get_token(self) -> str:
        try:
            token = self._token_provider()
        except Exception:
            raise AEEDataHTTPError(
                "MCS8_DATA_AUTH_UNAVAILABLE",
                "MCS8 data authentication is unavailable",
            ) from None
        if (
            not isinstance(token, str)
            or not token.strip()
            or "\r" in token
            or "\n" in token
        ):
            raise AEEDataHTTPError(
                "MCS8_DATA_AUTH_NOT_CONFIGURED",
                "MCS8 data authentication is not configured",
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
        raise ValueError("MCS8 base_url must be a clean HTTP(S) URL")
    return value.strip().rstrip("/")
