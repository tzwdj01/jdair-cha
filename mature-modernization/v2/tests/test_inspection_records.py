from __future__ import annotations

import datetime as dt
import unittest

from app.data.inspection_records import (
    InspectionRecordFilter,
    build_authorized_user,
    is_user_active,
)
from app.data.store import MemoryInspectionRecordStore
from app.services.inspection_records import InspectionRecordService


UTC = dt.timezone.utc
SH = dt.timezone(dt.timedelta(hours=8))


def _start():
    return dt.datetime(2026, 8, 15, 2, 0, tzinfo=UTC)


class InspectionRecordWorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.store = MemoryInspectionRecordStore()
        self.service = InspectionRecordService(self.store, business_timezone=SH)

    async def _draft(self, device="WXB353", **kwargs):
        return await self.service.create_draft(
            inspector_user_id=None,
            inspector_username="inspector-a",
            device_id=device,
            inspection_started_at=_start(),
            inspection_ended_at=_start() + dt.timedelta(minutes=30),
            **kwargs,
        )

    async def test_draft_lifecycle_create_update_submit_correct(self) -> None:
        detail = await self._draft(
            aircraft_no="B-1234",
            station="PEK",
            has_issue=True,
            issue_type="battery",
            issue_level="warning",
            issue_description="low battery",
            realtime_view_event_ids=["rtv_stream-1", "rtv_stream-1"],
        )
        record = detail.record
        self.assertEqual(record.status, "DRAFT")
        self.assertEqual(record.inspection_duration_seconds, 1800)
        self.assertEqual(record.has_issue, True)
        self.assertEqual(detail.realtime_view_event_ids, ("rtv_stream-1",))
        self.assertEqual(detail.audit_events[0].action, "CREATED")
        created_at = record.created_at
        submitted_at_probe = record.submitted_at
        self.assertIsNone(submitted_at_probe)

        updated = await self.service.update_draft(
            inspection_id=record.inspection_id,
            editor_user_id=None,
            editor_username="inspector-a",
            remark="re-check",
        )
        self.assertEqual(updated.record.remark, "re-check")
        self.assertEqual(updated.record.status, "DRAFT")
        self.assertEqual(updated.record.created_at, created_at)
        actions = [event.action for event in updated.audit_events]
        self.assertEqual(actions, ["CREATED", "UPDATED"])

        submitted = await self.service.submit(
            inspection_id=record.inspection_id,
            submitter_user_id=None,
            submitter_username="inspector-a",
        )
        self.assertEqual(submitted.record.status, "SUBMITTED")
        self.assertIsNotNone(submitted.record.submitted_at)
        self.assertEqual(submitted.record.submitted_by, "inspector-a")
        self.assertEqual(submitted.record.created_at, created_at)
        actions = [event.action for event in submitted.audit_events]
        self.assertEqual(actions, ["CREATED", "UPDATED", "SUBMITTED"])

        with self.assertRaises(ValueError):
            await self.service.update_draft(
                inspection_id=record.inspection_id,
                editor_user_id=None,
                editor_username="inspector-a",
            )

        corrected = await self.service.correct(
            inspection_id=record.inspection_id,
            corrector_user_id=None,
            corrector_username="inspector-b",
            correction_reason="wrong issue level",
            issue_level="critical",
        )
        self.assertEqual(corrected.record.status, "CORRECTED")
        self.assertEqual(corrected.record.issue_level, "critical")
        self.assertEqual(corrected.record.corrected_by, "inspector-b")
        self.assertEqual(corrected.record.created_at, created_at)
        self.assertEqual(corrected.record.submitted_by, "inspector-a")
        actions = [event.action for event in corrected.audit_events]
        self.assertEqual(
            actions,
            ["CREATED", "UPDATED", "SUBMITTED", "CORRECTED"],
        )

    async def test_list_filters_and_pagination(self) -> None:
        await self._draft(device="WXB353", aircraft_no="B-1234", has_issue=True)
        await self._draft(device="WXB353", aircraft_no="B-1234", has_issue=False)
        await self._draft(device="WXB301", aircraft_no="B-5678", has_issue=True)
        submitted = await self.service.list(
            InspectionRecordFilter(
                start=_start() - dt.timedelta(hours=1),
                end=_start() + dt.timedelta(hours=1),
                device_id="WXB353",
                page=1,
                page_size=10,
            )
        )
        self.assertEqual(submitted.total, 2)
        issues = await self.service.list(
            InspectionRecordFilter(
                has_issue=True,
                page=1,
                page_size=10,
            )
        )
        self.assertEqual(issues.total, 2)
        paged = await self.service.list(
            InspectionRecordFilter(page=1, page_size=1)
        )
        self.assertEqual(paged.total, 3)
        self.assertEqual(len(paged.items), 1)

    async def test_dashboard_metrics_use_submitted_records(self) -> None:
        # draft should be excluded from metrics
        await self._draft(device="WXB353", has_issue=False)
        detail = await self._draft(
            device="WXB353",
            aircraft_no="B-1234",
            station="PEK",
            routine_task_source_id="task-1",
            has_issue=True,
            issue_type="battery",
            issue_level="warning",
        )
        await self.service.submit(
            inspection_id=detail.record.inspection_id,
            submitter_user_id=None,
            submitter_username="inspector-a",
        )
        metrics = await self.service.dashboard_metrics(
            start=dt.datetime.now(UTC) - dt.timedelta(days=1),
            end=dt.datetime.now(UTC) + dt.timedelta(days=1),
        )
        self.assertEqual(metrics.total_count, 1)
        self.assertEqual(metrics.participant_count, 1)
        self.assertEqual(metrics.aircraft_count, 1)
        self.assertEqual(metrics.flight_count, 0)
        self.assertEqual(metrics.task_count, 1)
        self.assertEqual(metrics.issue_found_count, 1)
        self.assertEqual(metrics.no_issue_count, 0)
        self.assertEqual(metrics.issue_rate, 1.0)
        self.assertEqual(
            metrics.issue_type_counts,
            (("battery", 1),),
        )
        self.assertEqual(metrics.issue_device_ranking, (("WXB353", 1),))

    async def test_authorized_user_activity_window(self) -> None:
        now = dt.datetime(2026, 8, 15, 12, tzinfo=UTC)
        user = build_authorized_user(
            aee_account_id="acc-1",
            username="inspector-a",
            enabled=True,
            valid_from=now - dt.timedelta(days=1),
            valid_until=now + dt.timedelta(days=1),
        )
        await self.store.upsert_authorized_user(user)
        self.assertTrue(
            await self.store.is_account_authorized(username="inspector-a", at=now)
        )
        self.assertFalse(
            await self.store.is_account_authorized(
                username="inspector-a",
                at=now + dt.timedelta(days=2),
            )
        )
        self.assertFalse(
            await self.store.is_account_authorized(
                username="unknown",
                at=now,
            )
        )
        self.assertFalse(is_user_active(user, at=now + dt.timedelta(days=2)))


if __name__ == "__main__":
    unittest.main()
