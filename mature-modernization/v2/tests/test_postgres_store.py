from __future__ import annotations

import datetime as dt
import os
import unittest

from app.data.realtime_views import build_realtime_view_event
from app.data.store import PostgresInspectionStore


UTC = dt.timezone.utc


def _pg_available() -> bool:
    """True when a rehearsal PostgreSQL is reachable via CHA_PG_* env."""

    if not (os.environ.get("CHA_PG_HOST") and os.environ.get("CHA_PG_USER")):
        return False
    if not (os.environ.get("CHA_PG_PASSWORD") or os.environ.get("PGPASSWORD")):
        return False
    try:
        import psycopg2

        connection = psycopg2.connect(
            host=os.environ["CHA_PG_HOST"],
            port=int(os.environ.get("CHA_PG_PORT", "5432")),
            dbname=os.environ.get("CHA_PG_DATABASE", "cha_m4_rehearsal"),
            user=os.environ["CHA_PG_USER"],
            password=os.environ.get("CHA_PG_PASSWORD") or os.environ.get(
                "PGPASSWORD"
            ),
            connect_timeout=3,
        )
        connection.close()
        return True
    except Exception:
        return False


PG_AVAILABLE = _pg_available()


@unittest.skipUnless(PG_AVAILABLE, "no rehearsal PostgreSQL available")
class PostgresInspectionStoreTests(unittest.IsolatedAsyncioTestCase):
    """Live round-trip against an isolated rehearsal PostgreSQL.

    This test only runs when ``CHA_PG_*`` points at a reachable rehearsal
    database (it never touches production). It applies the migration, then
    verifies upsert/fetch/idempotency semantics of the repository.
    """

    async def asyncSetUp(self) -> None:
        self.store = PostgresInspectionStore()
        # clean the rehearsal tables so the test is repeatable
        connection = self.store._connect()
        connection.autocommit = True
        with connection.cursor() as cursor:
            for table in (
                "device_status_events",
                "device_location_events",
                "media_files",
                "realtime_view_events",
                "alarm_events",
            ):
                cursor.execute(f"TRUNCATE {self.store._qualify(table)}")
        connection.close()

    async def test_status_upsert_fetch_and_idempotency(self) -> None:
        start = dt.datetime(2026, 8, 15, 0, tzinfo=UTC)
        end = dt.datetime(2026, 8, 15, 4, tzinfo=UTC)
        events = (
            _status_event("s-1", "WX1", 1, start, start, start),
            _status_event("s-2", "WX2", 0, start + dt.timedelta(minutes=1), start, start),
        )
        self.assertEqual(
            await self.store.upsert_device_status_events(events),
            2,
        )
        rows = await self.store.fetch_device_status_events(
            start=start,
            end=end,
        )
        self.assertEqual(len(rows), 2)
        # re-upsert the same rows -> no growth
        await self.store.upsert_device_status_events(events)
        rows_again = await self.store.fetch_device_status_events(
            start=start,
            end=end,
        )
        self.assertEqual(len(rows_again), 2)

    async def test_media_upsert_and_realtime_first_wins(self) -> None:
        start = dt.datetime(2026, 8, 15, 0, tzinfo=UTC)
        end = dt.datetime(2026, 8, 15, 4, tzinfo=UTC)
        files = (
            _media_file("file-1", "WX1", start, start + dt.timedelta(seconds=10)),
            _media_file("file-1", "WX1", start, start + dt.timedelta(seconds=10)),
        )
        self.assertEqual(
            await self.store.upsert_media_files(files),
            2,
        )
        media_rows = await self.store.fetch_media_files(
            start=start,
            end=end,
        )
        self.assertEqual(len(media_rows), 1)  # same source id collapses

        view = build_realtime_view_event(
            username="tester",
            user_id=None,
            device_id="WX1",
            session_id="session-1",
            stream_id="stream-1",
            opened_at=start,
            first_frame_at=start + dt.timedelta(seconds=2),
            closed_at=start + dt.timedelta(seconds=12),
            error_code=None,
            width=1920,
            height=1080,
            track_state="live",
            close_reason="session_close",
            release_mode="session_disconnect",
        )
        self.assertEqual(
            await self.store.upsert_realtime_view_events((view,)),
            1,
        )
        # second finalization of the same stream is ignored (first wins)
        self.assertEqual(
            await self.store.upsert_realtime_view_events((view,)),
            1,
        )
        views = await self.store.fetch_realtime_view_events(
            start=start,
            end=end,
        )
        self.assertEqual(len(views), 1)


def _status_event(
    source_id: str,
    device_id: str,
    status: int,
    occurred_at: dt.datetime,
    observed_at: dt.datetime,
    ingested_at: dt.datetime,
):
    from app.data.normalization import DeviceStatusEvent

    return DeviceStatusEvent(
        source_system="aee",
        source_record_id=source_id,
        device_id=device_id,
        group_id=None,
        device_type_code=None,
        status_code=status,
        online=status == 1,
        occurred_at=occurred_at,
        observed_at=observed_at,
        ingested_at=ingested_at,
        quality_flags=(),
    )


def _media_file(source_id: str, device_id: str, created: dt.datetime, uploaded: dt.datetime):
    from app.data.normalization import MediaFile

    return MediaFile(
        source_system="aee",
        source_record_id=source_id,
        device_id=device_id,
        group_id=None,
        device_name_at_capture=None,
        title=None,
        file_type_code=3,
        media_kind="video",
        list_type_code=None,
        source_code=None,
        upload_status_code=None,
        file_size_bytes=100,
        duration_seconds=10,
        created_at_source=created,
        end_at_source=None,
        uploaded_at_source=uploaded,
        work_no=None,
        people_no=None,
        people_name=None,
        description=None,
        deleted_marker=None,
        observed_at=created,
        ingested_at=created,
        quality_flags=(),
    )


if __name__ == "__main__":
    unittest.main()
