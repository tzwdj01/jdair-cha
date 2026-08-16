from __future__ import annotations

import datetime as dt
import unittest

from app.data.metrics import (
    aggregate_device_uptime,
    aggregate_media_files,
)


UTC = dt.timezone.utc
BUSINESS_TZ = dt.timezone(dt.timedelta(hours=8), name="Asia/Shanghai")


class DeviceUptimeMetricTests(unittest.TestCase):
    def test_events_are_sorted_deduplicated_and_clipped_to_window(self) -> None:
        rows = [
            {
                "id": "3",
                "devId": "WX1",
                "groupId": "G1",
                "status": 0,
                "time": "2026-08-15 12:00:00",
            },
            {
                "id": "1",
                "devId": "WX1",
                "groupId": "G1",
                "status": 1,
                "time": "2026-08-15 08:00:00",
            },
            {
                "id": "duplicate",
                "devId": "WX1",
                "groupId": "G1",
                "status": 1,
                "time": "2026-08-15 08:00:00",
            },
            {
                "id": "4",
                "devId": "WX1",
                "groupId": "G1",
                "status": 1,
                "time": "2026-08-15 13:00:00",
            },
        ]

        result = aggregate_device_uptime(
            rows,
            window_start=dt.datetime(
                2026,
                8,
                15,
                0,
                tzinfo=BUSINESS_TZ,
            ),
            window_end=dt.datetime(
                2026,
                8,
                15,
                16,
                tzinfo=BUSINESS_TZ,
            ),
            source_timezone=BUSINESS_TZ,
        )

        self.assertEqual(len(result.devices), 1)
        self.assertEqual(result.duplicate_event_count, 1)
        self.assertIn("duplicate_events_removed", result.quality_flags)
        metric = result.devices[0]
        self.assertEqual(metric.online_seconds, 7 * 3600)
        self.assertEqual(metric.offline_transition_count, 1)
        self.assertEqual(
            metric.first_online_at,
            dt.datetime(2026, 8, 15, 0, tzinfo=UTC),
        )
        self.assertEqual(
            metric.last_offline_at,
            dt.datetime(2026, 8, 15, 4, tzinfo=UTC),
        )
        self.assertEqual(metric.event_count, 3)
        self.assertIn(
            "open_interval_clipped_to_window_end",
            metric.quality_flags,
        )

    def test_multi_source_same_time_status_dedup_is_explicit(self) -> None:
        rows = [
            {
                "id": "a",
                "devId": "WX1",
                "groupId": "G1",
                "status": 1,
                "time": "2026-08-15 08:00:00",
            },
            {
                # same device/time/status, different source id, identical
                # content -> source-level redundancy, explicitly flagged.
                "id": "b",
                "devId": "WX1",
                "groupId": "G1",
                "status": 1,
                "time": "2026-08-15 08:00:00",
            },
        ]
        result = aggregate_device_uptime(
            rows,
            window_start=dt.datetime(
                2026,
                8,
                15,
                0,
                tzinfo=BUSINESS_TZ,
            ),
            window_end=dt.datetime(
                2026,
                8,
                15,
                16,
                tzinfo=BUSINESS_TZ,
            ),
            source_timezone=BUSINESS_TZ,
        )
        self.assertEqual(result.duplicate_event_count, 1)
        metric = result.devices[0]
        self.assertIn(
            "same_time_status_multi_source_dedup",
            metric.quality_flags,
        )

    def test_pre_window_event_seeds_initial_online_state(self) -> None:
        rows = [
            {
                "id": "before",
                "devId": "WX2",
                "status": 1,
                "time": "2026-08-15 07:00:00",
            },
            {
                "id": "offline",
                "devId": "WX2",
                "status": 2,
                "time": "2026-08-15 10:00:00",
            },
        ]

        metric = aggregate_device_uptime(
            rows,
            window_start=dt.datetime(
                2026,
                8,
                15,
                8,
                tzinfo=BUSINESS_TZ,
            ),
            window_end=dt.datetime(
                2026,
                8,
                15,
                16,
                tzinfo=BUSINESS_TZ,
            ),
            source_timezone=BUSINESS_TZ,
        ).devices[0]

        self.assertEqual(metric.online_seconds, 2 * 3600)
        self.assertEqual(metric.offline_transition_count, 1)
        self.assertIn("online_at_window_start", metric.quality_flags)
        self.assertNotIn("missing_start_state", metric.quality_flags)

    def test_missing_start_state_is_explicit(self) -> None:
        metric = aggregate_device_uptime(
            [
                {
                    "id": "offline",
                    "devId": "WX3",
                    "status": 0,
                    "time": "2026-08-15 10:00:00",
                }
            ],
            window_start=dt.datetime(
                2026,
                8,
                15,
                8,
                tzinfo=BUSINESS_TZ,
            ),
            window_end=dt.datetime(
                2026,
                8,
                15,
                16,
                tzinfo=BUSINESS_TZ,
            ),
            source_timezone=BUSINESS_TZ,
        ).devices[0]

        self.assertEqual(metric.online_seconds, 0)
        self.assertIn("missing_start_state", metric.quality_flags)

    def test_naive_window_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            aggregate_device_uptime(
                [],
                window_start=dt.datetime(2026, 8, 15),
                window_end=dt.datetime(2026, 8, 15, 16, tzinfo=UTC),
                source_timezone=BUSINESS_TZ,
            )

    def test_invalid_and_conflicting_rows_are_visible(self) -> None:
        result = aggregate_device_uptime(
            [
                {"status": 1, "time": "2026-08-15 08:00:00"},
                {
                    "id": "bad-time",
                    "devId": "WX1",
                    "status": 1,
                    "time": "not-a-time",
                },
                {
                    "id": "online",
                    "devId": "WX1",
                    "status": 1,
                    "time": "2026-08-15 09:00:00",
                },
                {
                    "id": "offline",
                    "devId": "WX1",
                    "status": 0,
                    "time": "2026-08-15 09:00:00",
                },
            ],
            window_start=dt.datetime(
                2026,
                8,
                15,
                8,
                tzinfo=BUSINESS_TZ,
            ),
            window_end=dt.datetime(
                2026,
                8,
                15,
                16,
                tzinfo=BUSINESS_TZ,
            ),
            source_timezone=BUSINESS_TZ,
        )

        self.assertEqual(result.invalid_row_count, 2)
        self.assertIn("invalid_rows_ignored", result.quality_flags)
        self.assertIn(
            "conflicting_status_same_time",
            result.devices[0].quality_flags,
        )


class MediaMetricTests(unittest.TestCase):
    def test_media_rows_preserve_raw_units_and_types(self) -> None:
        result = aggregate_media_files(
            [
                {
                    "id": "1",
                    "devId": "WX1",
                    "groupId": "G1",
                    "fType": 1,
                    "fileLen": 1024,
                    "duration": 0,
                },
                {
                    "id": "2",
                    "devId": "WX1",
                    "groupId": "G1",
                    "fType": 2,
                    "fileLen": 2048,
                    "duration": 8,
                },
                {
                    "id": "3",
                    "devId": "WX1",
                    "groupId": "G1",
                    "fType": 3,
                    "fileLen": 4096,
                    "duration": 125,
                },
                {
                    "id": "4",
                    "devId": "WX1",
                    "groupId": "G1",
                    "fType": 4,
                    "fileLen": 512,
                    "duration": 999,
                },
            ],
            records_total=4,
            query_limit=10_000,
        )

        metric = result.devices[0]
        self.assertFalse(result.partial)
        self.assertEqual(metric.total_files, 4)
        self.assertEqual(metric.image_count, 1)
        self.assertEqual(metric.audio_count, 1)
        self.assertEqual(metric.video_count, 1)
        self.assertEqual(metric.device_file_count, 1)
        self.assertEqual(metric.video_duration_seconds, 125)
        self.assertEqual(metric.file_size_bytes, 7680)

    def test_partial_results_are_not_silently_treated_as_complete(self) -> None:
        rows = [
            {
                "id": str(index),
                "devId": "WX1",
                "fType": 3,
                "fileLen": 1,
                "duration": 1,
            }
            for index in range(10)
        ]

        result = aggregate_media_files(
            rows,
            records_total=12,
            query_limit=10,
        )

        self.assertTrue(result.partial)
        self.assertIn(
            "records_total_exceeds_fetched_count",
            result.quality_flags,
        )
        self.assertIn("query_limit_reached", result.quality_flags)

    def test_invalid_rows_and_values_are_flagged(self) -> None:
        result = aggregate_media_files(
            [
                {"fType": 3, "fileLen": 1, "duration": 1},
                {
                    "devId": "WX1",
                    "fType": "unexpected",
                    "fileLen": -1,
                    "duration": "bad",
                },
            ]
        )

        self.assertEqual(result.invalid_row_count, 1)
        self.assertIn("rows_without_device_ignored", result.quality_flags)
        metric = result.devices[0]
        self.assertEqual(metric.unknown_type_count, 1)
        self.assertIn("unknown_file_type", metric.quality_flags)
        self.assertIn("invalid_file_size_ignored", metric.quality_flags)


if __name__ == "__main__":
    unittest.main()
