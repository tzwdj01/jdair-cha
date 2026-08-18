from __future__ import annotations

import datetime as dt
import json
import os
import unittest
from typing import Any
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.inspections import create_inspections_router
from app.config import Settings
from app.data.inspection_records import build_authorized_user
from app.data.store import MemoryInspectionRecordStore
from app.services.business_candidates import (
    BusinessCandidate,
    BusinessCandidateResult,
)
from app.services.inspection_records import InspectionRecordService


UTC = dt.timezone.utc


class _ASGIResponse:
    def __init__(self, status_code: int, body: bytes) -> None:
        self.status_code = status_code
        self.body = body

    def json(self) -> dict[str, Any]:
        return json.loads(self.body)


async def _request(app, method: str, path: str, body: dict | None = None):
    path_without_query = path.split("?")[0]
    query = path.split("?", 1)[1] if "?" in path else ""
    payload = json.dumps(body).encode() if body is not None else b""
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path_without_query,
        "raw_path": path_without_query.encode("ascii"),
        "query_string": query.encode("ascii"),
        "root_path": "",
        "headers": [(b"host", b"testserver"), (b"content-type", b"application/json")],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
        "state": {},
    }
    sent = False
    messages: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        nonlocal sent
        if not sent:
            sent = True
            return {
                "type": "http.request",
                "body": payload,
                "more_body": False,
            }
        return {"type": "http.disconnect"}

    async def send(message: dict[str, Any]) -> None:
        messages.append(message)

    await app(scope, receive, send)
    start = next(
        m for m in messages if m["type"] == "http.response.start"
    )
    body = b"".join(
        m.get("body", b"")
        for m in messages
        if m["type"] == "http.response.body"
    )
    return _ASGIResponse(status_code=start["status"], body=body)


def _settings() -> Settings:
    with patch.dict(
        os.environ,
        {"CHA_V2_FEATURE_INSPECTION_V2": "true"},
        clear=False,
    ):
        return Settings.from_env()


def _envelope(request, data, *, ok=True, status_code=200) -> JSONResponse:
    del request
    return JSONResponse(
        status_code=status_code,
        content={"ok": ok, "data": data},
    )


class _Identity:
    def __init__(self, username: str) -> None:
        self.username = username

    async def __call__(self, request):
        del request
        return None, self.username


def _app(username: str = "inspector-a", candidate_service=None):
    store = MemoryInspectionRecordStore()
    service = InspectionRecordService(store)
    app = FastAPI()
    app.include_router(
        create_inspections_router(
            _settings(),
            service,
            store,
            _envelope,
            _Identity(username),
            candidate_service,
        )
    )
    return app, store


async def _seed_authorized(store) -> None:
    await store.upsert_authorized_user(
        build_authorized_user(
            aee_account_id="acc-admin",
            username="admin-a",
            role="admin",
            enabled=True,
        )
    )
    await store.upsert_authorized_user(
        build_authorized_user(
            aee_account_id="acc-a",
            username="inspector-a",
            enabled=True,
        )
    )
    await store.upsert_authorized_user(
        build_authorized_user(
            aee_account_id="acc-b",
            username="inspector-b",
            enabled=True,
        )
    )


class InspectionsAPITests(unittest.IsolatedAsyncioTestCase):
    async def test_unauthorized_account_is_rejected(self) -> None:
        app, store = _app(username="hacker")
        await _seed_authorized(store)
        response = await _request(
            app,
            "POST",
            "/api/v2/inspections",
            {
                "device_id": "WXB353",
                "inspection_started_at": "2026-08-15T02:00:00Z",
                "inspection_ended_at": "2026-08-15T02:30:00Z",
            },
        )
        self.assertEqual(response.status_code, 403)

    async def test_feature_disabled_returns_404(self) -> None:
        with patch.dict(
            os.environ,
            {"CHA_V2_FEATURE_INSPECTION_V2": ""},
            clear=False,
        ):
            from app.config import Settings as S2

            store = MemoryInspectionRecordStore()
            app = FastAPI()
            app.include_router(
                create_inspections_router(
                    S2.from_env(),
                    InspectionRecordService(store),
                    store,
                    _envelope,
                    _Identity("inspector-a"),
                )
            )
        response = await _request(app, "GET", "/api/v2/inspections")
        self.assertEqual(response.status_code, 404)

    async def test_full_workflow_via_api(self) -> None:
        app, store = _app()
        await _seed_authorized(store)
        created = await _request(
            app,
            "POST",
            "/api/v2/inspections",
            {
                "device_id": "WXB353",
                "inspection_started_at": "2026-08-15T02:00:00Z",
                "inspection_ended_at": "2026-08-15T02:45:00Z",
                "aircraft_no": "B-1234",
                "station": "PEK",
                "has_issue": True,
                "issue_type": "battery",
                "issue_level": "warning",
                "issue_description": "low battery",
                "realtime_view_event_ids": ["rtv_stream-1"],
            },
        )
        self.assertEqual(created.status_code, 201)
        inspection_id = created.json()["data"]["inspection"]["record"]["inspection_id"]
        self.assertEqual(
            created.json()["data"]["inspection"]["record"]["inspector_username"],
            "inspector-a",
        )

        detail = await _request(
            app,
            "GET",
            f"/api/v2/inspections/{inspection_id}",
        )
        self.assertEqual(detail.status_code, 200)

        submitted = await _request(
            app,
            "POST",
            f"/api/v2/inspections/{inspection_id}/submit",
        )
        self.assertEqual(submitted.status_code, 200)
        self.assertEqual(
            submitted.json()["data"]["inspection"]["record"]["status"],
            "SUBMITTED",
        )

        corrected = await _request(
            app,
            "POST",
            f"/api/v2/inspections/{inspection_id}/correct",
            {"correction_reason": "level fix", "issue_level": "critical"},
        )
        self.assertEqual(corrected.status_code, 200)
        self.assertEqual(
            corrected.json()["data"]["inspection"]["record"]["status"],
            "CORRECTED",
        )

        listing = await _request(
            app,
            "GET",
            "/api/v2/inspections?days=7",
        )
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()["data"]["total"], 1)

        metrics = await _request(
            app,
            "GET",
            "/api/v2/inspections/metrics?days=7",
        )
        self.assertEqual(metrics.status_code, 200)
        self.assertEqual(
            metrics.json()["data"]["metrics"]["total_count"],
            1,
        )

    async def test_csv_export_excludes_secrets(self) -> None:
        app, store = _app()
        await _seed_authorized(store)
        await _request(
            app,
            "POST",
            "/api/v2/inspections",
            {
                "device_id": "WXB353",
                "inspection_started_at": "2026-08-15T02:00:00Z",
                "inspection_ended_at": "2026-08-15T02:45:00Z",
                "aircraft_no": "B-1234",
            },
        )
        response = await _request(
            app,
            "GET",
            "/api/v2/inspections/export?fmt=csv&days=7",
        )
        self.assertEqual(response.status_code, 200)
        text = response.body.decode("utf-8")
        self.assertIn("inspection_id", text)
        self.assertIn("B-1234", text)
        for forbidden in (
            "password",
            "token",
            "cookie",
            "secret",
            "credential",
        ):
            self.assertNotIn(forbidden, text.lower())

    async def test_authorized_user_admin_maintenance(self) -> None:
        app, store = _app(username="admin-a")
        await _seed_authorized(store)

        listing = await _request(
            app,
            "GET",
            "/api/v2/inspections/authorized-users",
        )
        self.assertEqual(listing.status_code, 200)
        usernames = {
            item["username"]
            for item in listing.json()["data"]["items"]
        }
        self.assertIn("inspector-a", usernames)

        added = await _request(
            app,
            "POST",
            "/api/v2/inspections/authorized-users",
            {
                "aee_account_id": "acc-new",
                "username": "inspector-new",
                "role": "inspector",
                "enabled": True,
            },
        )
        self.assertEqual(added.status_code, 201)
        self.assertTrue(
            await store.is_account_authorized(
                username="inspector-new",
                at=dt.datetime.now(UTC),
            )
        )

        disabled = await _request(
            app,
            "POST",
            "/api/v2/inspections/authorized-users/inspector-new/disable",
        )
        self.assertEqual(disabled.status_code, 200)
        self.assertFalse(
            await store.is_account_authorized(
                username="inspector-new",
                at=dt.datetime.now(UTC),
            )
        )

        audit = await store.list_user_audit_events(
            target_username="inspector-new",
        )
        actions = [event.action for event in audit]
        self.assertEqual(
            actions,
            ["USER_ADDED", "USER_DISABLED"],
        )
        self.assertEqual(audit[0].operator_username, "admin-a")

    async def test_non_admin_cannot_manage_users(self) -> None:
        app, store = _app(username="inspector-a")
        await _seed_authorized(store)
        response = await _request(
            app,
            "GET",
            "/api/v2/inspections/authorized-users",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json()["data"]["code"],
            "admin_forbidden",
        )

    async def test_candidates_returns_reference_items(self) -> None:
        class _FakeCandidateService:
            async def find_candidates(self, **kwargs):
                return BusinessCandidateResult(
                    candidates=(
                        BusinessCandidate(
                            source="flight",
                            source_id="f1",
                            aircraft_no="B-1234",
                            flight_no="JD5101",
                            station="PEK",
                            task_type=None,
                            task_text="JD5101 PEK→SHA",
                            time_start=dt.datetime(
                                2026, 8, 18, 2, 0, tzinfo=UTC
                            ),
                            time_end=None,
                            source_updated_at=dt.datetime(
                                2026, 8, 18, 2, 0, tzinfo=UTC
                            ),
                            association_method="SOURCE_DIRECT",
                            evidence=("flight_live_fields",),
                        ),
                    ),
                    fetched_at=dt.datetime(2026, 8, 18, 2, 0, tzinfo=UTC),
                    requested_aircraft="B-1234",
                    requested_station=None,
                )

        app, store = _app(candidate_service=_FakeCandidateService())
        await _seed_authorized(store)
        response = await _request(
            app,
            "GET",
            (
                "/api/v2/inspections/candidates"
                "?started_at=2026-08-18T02:00:00%2B00:00"
                "&aircraft=B-1234"
            ),
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["candidates"][0]["flight_no"], "JD5101")
        self.assertEqual(data["requested_aircraft"], "B-1234")

    async def test_candidates_unavailable_returns_503(self) -> None:
        app, store = _app(candidate_service=None)
        await _seed_authorized(store)
        response = await _request(
            app,
            "GET",
            "/api/v2/inspections/candidates",
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["data"]["code"],
            "candidate_source_unavailable",
        )

    async def test_candidates_requires_authorized(self) -> None:
        app, store = _app(username="not-in-list", candidate_service=object())
        await _seed_authorized(store)
        response = await _request(
            app,
            "GET",
            "/api/v2/inspections/candidates",
        )
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
