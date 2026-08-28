from __future__ import annotations

import datetime as dt
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from ..data.store import InspectionRecordStore


UTC = dt.timezone.utc
IdentityProvider = Callable[
    [Request],
    Awaitable[tuple[str | None, str]],
]
Envelope = Callable[..., JSONResponse]


class InspectionAccess:
    """Reuse CHA login identity for the small M4 AuthorizedUser boundary.

    The inspection data center has no separate login or RBAC system.  An
    existing CHA session identifies the account, and the durable
    ``AuthorizedUser`` list decides whether that account may access the
    Canary-only dashboard and inspection APIs.
    """

    def __init__(
        self,
        record_store: InspectionRecordStore | None,
        identity: IdentityProvider | None,
        envelope: Envelope,
    ) -> None:
        self._record_store = record_store
        self._identity = identity
        self._envelope = envelope

    async def require_authorized(
        self,
        request: Request,
    ) -> tuple[tuple[str | None, str] | None, JSONResponse | None]:
        """Return the verified CHA identity or a bounded API error response."""

        if self._record_store is None or self._identity is None:
            return None, self._error(
                request,
                "inspection_access_not_configured",
                "Inspection access enforcement is not configured.",
                status_code=503,
            )
        try:
            user_id, username = await self._identity(request)
        except Exception:
            return None, self._error(
                request,
                "unauthorized",
                "session identity unavailable",
                status_code=401,
            )
        if not username or not username.strip():
            return None, self._error(
                request,
                "unauthorized",
                "session has no username",
                status_code=401,
            )
        try:
            authorized = await self._record_store.is_account_authorized(
                username=username,
                at=dt.datetime.now(UTC),
            )
        except Exception:
            return None, self._error(
                request,
                "inspection_authorization_unavailable",
                "Inspection access could not be verified.",
                status_code=503,
            )
        if not authorized:
            return None, self._error(
                request,
                "cha_access_forbidden",
                "current account is not in the CHA authorized user list",
                status_code=403,
            )
        return (user_id, username), None

    async def require_admin(
        self,
        request: Request,
    ) -> tuple[tuple[str | None, str] | None, JSONResponse | None]:
        """Require the existing AuthorizedUser ``admin`` role."""

        identity, error = await self.require_authorized(request)
        if error is not None:
            return None, error
        assert identity is not None
        _user_id, username = identity
        assert self._record_store is not None
        try:
            user = await self._record_store.get_authorized_user(
                username=username
            )
        except Exception:
            return None, self._error(
                request,
                "inspection_authorization_unavailable",
                "Inspection access could not be verified.",
                status_code=503,
            )
        if user is None or str(user.role or "").strip().casefold() != "admin":
            return None, self._error(
                request,
                "admin_forbidden",
                "admin privilege is required",
                status_code=403,
            )
        return identity, None

    def _error(
        self,
        request: Request,
        code: str,
        message: str,
        *,
        status_code: int,
    ) -> JSONResponse:
        return self._envelope(
            request,
            {"code": code, "message": message},
            ok=False,
            status_code=status_code,
        )
