from __future__ import annotations

import datetime as dt
import unittest

from app.data.normalization import (
    normalize_alarm_events,
    normalize_mcs8_device_snapshot,
    normalize_mcs8_device_snapshot_locations,
    normalize_media_files,
)


SHANGHAI = dt.timezone(dt.timedelta(hours=8), name="Asia/Shanghai")
UTC = dt.timezone.utc
OBSERVED = dt.datetime(2026, 8, 16, 4, 30, tzinfo=SHANGHAI)
INGESTED = OBSERVED + dt.timedelta(seconds=1)


class MCS8NormalizationTests(unittest.TestCase):
    def test_media_files_accept_source_system(self) -> None:
        result = normalize_media_files(
            [
                {
                    "id": "rec-1",
                    "devId": "WXB310",
                    "fType": 3,
                    "startTime": "2026-08-16 02:01:24",
                }
            ],
            source_timezone=SHANGHAI,
            observed_at=OBSERVED,
            ingested_at=INGESTED,
            source_system="mcs8",
        )
        self.assertEqual(result.files[0].source_system, "mcs8")

    def test_alarms_accept_source_system(self) -> None:
        result = normalize_alarm_events(
            [
                {
                    "id": "alarm-1",
                    "devId": "WXB358",
                    "alarmType": 205,
                    "alarmTime": "2026-08-16 01:42:00",
                }
            ],
            source_timezone=SHANGHAI,
            observed_at=OBSERVED,
            ingested_at=INGESTED,
            source_system="mcs8",
        )
        self.assertEqual(result.events[0].source_system, "mcs8")

    def test_media_files_default_source_system_is_aee(self) -> None:
        result = normalize_media_files(
            [
                {
                    "id": "rec-1",
                    "devId": "WXB310",
                    "fType": 3,
                    "startTime": "2026-08-16 02:01:24",
                }
            ],
            source_timezone=SHANGHAI,
            observed_at=OBSERVED,
            ingested_at=INGESTED,
        )
        self.assertEqual(result.files[0].source_system, "aee")

    def test_device_snapshot_normalizes_nonline(self) -> None:
        result = normalize_mcs8_device_snapshot(
            [
                {"szIDNO": "WXB310", "nOnline": 1, "groupId": 30000002},
                {"szIDNO": "WXB358", "nOnline": 0, "groupId": 30000002},
            ],
            observed_at=OBSERVED,
            ingested_at=INGESTED,
        )
        by_id = {event.device_id: event for event in result.events}
        self.assertTrue(by_id["WXB310"].online)
        self.assertFalse(by_id["WXB358"].online)
        self.assertEqual(by_id["WXB310"].source_system, "mcs8")
        self.assertEqual(
            by_id["WXB310"].occurred_at,
            OBSERVED.astimezone(UTC),
        )
        self.assertIn(
            "mcs8_device_snapshot",
            by_id["WXB310"].quality_flags,
        )
        self.assertIn(
            "snapshot_no_upstream_event_time",
            by_id["WXB310"].quality_flags,
        )

    def test_device_snapshot_invalid_rows_flagged(self) -> None:
        result = normalize_mcs8_device_snapshot(
            [
                {"szIDNO": "WXB310", "nOnline": 1},
                {"szIDNO": "", "nOnline": 1},
                {"szIDNO": "WXB358", "nOnline": "bad"},
            ],
            observed_at=OBSERVED,
            ingested_at=INGESTED,
        )
        self.assertEqual(result.invalid_row_count, 2)
        self.assertIn("invalid_rows_ignored", result.quality_flags)
        self.assertEqual(len(result.events), 1)

    def test_device_snapshot_locations_from_gps_fields(self) -> None:
        result = normalize_mcs8_device_snapshot_locations(
            [
                {
                    "szIDNO": "WXB310",
                    "nJingDu": "121.4737",
                    "nWeiDu": "31.2304",
                    "gpsTime": "2026-08-16 03:20:10",
                    "ucMapType": 1,
                }
            ],
            source_timezone=SHANGHAI,
            observed_at=OBSERVED,
            ingested_at=INGESTED,
        )
        self.assertEqual(len(result.events), 1)
        event = result.events[0]
        self.assertEqual(event.device_id, "WXB310")
        self.assertAlmostEqual(event.longitude, 121.4737)
        self.assertAlmostEqual(event.latitude, 31.2304)
        self.assertEqual(event.location_source, "mcs8_device_snapshot")
        self.assertEqual(event.source_system, "mcs8")
        self.assertEqual(
            event.gps_occurred_at,
            dt.datetime(2026, 8, 15, 19, 20, 10, tzinfo=UTC),
        )
        self.assertEqual(event.gps_type_code, 1)
        self.assertIn("coordinate_system_unverified", event.quality_flags)
        self.assertIn("location_data_restricted", event.quality_flags)
        self.assertIn("source_record_id_missing", event.quality_flags)
        self.assertIn("gps_type_code_map_unknown", event.quality_flags)

    def test_device_snapshot_locations_skip_invalid_rows(self) -> None:
        result = normalize_mcs8_device_snapshot_locations(
            [
                # zero sentinel coordinates
                {
                    "szIDNO": "WXB310",
                    "nJingDu": "0",
                    "nWeiDu": "0",
                    "gpsTime": "2026-08-16 03:20:10",
                },
                # no source GPS time
                {
                    "szIDNO": "WXB311",
                    "nJingDu": "116.39",
                    "nWeiDu": "39.90",
                },
                # missing device id
                {
                    "szIDNO": "",
                    "nJingDu": "116.39",
                    "nWeiDu": "39.90",
                    "gpsTime": "2026-08-16 03:20:10",
                },
            ],
            source_timezone=SHANGHAI,
            observed_at=OBSERVED,
            ingested_at=INGESTED,
        )
        self.assertEqual(result.invalid_row_count, 3)
        self.assertEqual(len(result.events), 0)
        self.assertIn("invalid_rows_ignored", result.quality_flags)

    def test_device_snapshot_locations_future_gps_time_flagged(self) -> None:
        result = normalize_mcs8_device_snapshot_locations(
            [
                {
                    "szIDNO": "WXB310",
                    "nJingDu": "121.4737",
                    "nWeiDu": "31.2304",
                    "gpsTime": "2026-08-16 06:00:00",
                }
            ],
            source_timezone=SHANGHAI,
            observed_at=OBSERVED,
            ingested_at=INGESTED,
        )
        self.assertEqual(len(result.events), 1)
        self.assertIn(
            "source_time_after_observation",
            result.events[0].quality_flags,
        )

    def test_device_snapshot_locations_ignore_sentinel_gps_time(self) -> None:
        # MCS8 uses ``0001-01-01 00:00:00`` as a "no GPS time" sentinel;
        # it must be treated as absent instead of crashing the cycle.
        result = normalize_mcs8_device_snapshot_locations(
            [
                {
                    "szIDNO": "WXB310",
                    "nJingDu": "121.4737",
                    "nWeiDu": "31.2304",
                    "gpsTime": "0001-01-01 00:00:00",
                },
                {
                    "szIDNO": "WXB311",
                    "nJingDu": "116.39",
                    "nWeiDu": "39.90",
                    "gpsTime": "2026-08-16 03:20:10",
                },
            ],
            source_timezone=SHANGHAI,
            observed_at=OBSERVED,
            ingested_at=INGESTED,
        )
        self.assertEqual(len(result.events), 1)
        self.assertEqual(result.events[0].device_id, "WXB311")
        self.assertEqual(result.invalid_row_count, 1)
        self.assertIn("invalid_rows_ignored", result.quality_flags)


if __name__ == "__main__":
    unittest.main()
