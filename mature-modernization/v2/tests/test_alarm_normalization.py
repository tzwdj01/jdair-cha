from __future__ import annotations

import datetime as dt
import unittest

from app.data.normalization import normalize_alarm_events


UTC = dt.timezone.utc
BUSINESS_TZ = dt.timezone(dt.timedelta(hours=8), name="Asia/Shanghai")
OBSERVED = dt.datetime(2026, 8, 15, 9, tzinfo=BUSINESS_TZ)
INGESTED = dt.datetime(2026, 8, 15, 9, 0, 2, tzinfo=BUSINESS_TZ)


class AlarmNormalizationTests(unittest.TestCase):
    def test_raw_alarm_codes_and_times_are_preserved_without_labels(
        self,
    ) -> None:
        result = normalize_alarm_events(
            [
                {
                    "id": "alarm-1",
                    "devId": "WXB358",
                    "groupId": "group-1",
                    "alarmType": 205,
                    "alarmStatus": 1,
                    "dealStatus": 0,
                    "dealType": 2,
                    "alarmTime": "2026-08-15 08:30:00",
                }
            ],
            source_timezone=BUSINESS_TZ,
            observed_at=OBSERVED,
            ingested_at=INGESTED,
        )

        event = result.events[0]
        self.assertEqual(event.source_record_id, "alarm-1")
        self.assertEqual(event.device_id, "WXB358")
        self.assertEqual(event.alarm_type_code, 205)
        self.assertEqual(event.alarm_status_code, 1)
        self.assertEqual(event.deal_status_code, 0)
        self.assertEqual(event.deal_type_code, 2)
        self.assertIsNone(event.handled)
        self.assertEqual(
            event.occurred_at,
            dt.datetime(2026, 8, 15, 0, 30, tzinfo=UTC),
        )
        self.assertIn("alarm_code_map_partial", event.quality_flags)
        self.assertIn("handled_state_unknown", event.quality_flags)
        self.assertIn(
            "source_id_scope_unverified",
            event.quality_flags,
        )

    def test_restricted_handling_fields_are_omitted_by_default(self) -> None:
        row = {
            "id": "alarm-1",
            "devId": "WXB358",
            "alarmType": 205,
            "alarmTime": "2026-08-15 08:30:00",
            "dealUser": "operator",
            "dealTime": "2026-08-15 08:40:00",
            "dealDesc": "restricted handling detail",
        }

        default = normalize_alarm_events(
            [row],
            source_timezone=BUSINESS_TZ,
            observed_at=OBSERVED,
            ingested_at=INGESTED,
        )
        included = normalize_alarm_events(
            [row],
            source_timezone=BUSINESS_TZ,
            observed_at=OBSERVED,
            ingested_at=INGESTED,
            include_restricted=True,
        )

        self.assertIsNone(default.events[0].handled_at)
        self.assertIsNone(default.events[0].handler)
        self.assertIsNone(default.events[0].deal_description)
        self.assertIn(
            "restricted_fields_omitted",
            default.events[0].quality_flags,
        )
        self.assertEqual(default.restricted_field_row_count, 1)
        self.assertEqual(included.events[0].handler, "operator")
        self.assertEqual(
            included.events[0].deal_description,
            "restricted handling detail",
        )
        self.assertEqual(
            included.events[0].handled_at,
            dt.datetime(2026, 8, 15, 0, 40, tzinfo=UTC),
        )

    def test_missing_required_fields_are_counted_not_materialized(
        self,
    ) -> None:
        result = normalize_alarm_events(
            [
                {
                    "devId": "WX1",
                    "alarmType": 1,
                    "alarmTime": "2026-08-15 08:00:00",
                },
                {
                    "id": "alarm-2",
                    "alarmType": 1,
                    "alarmTime": "2026-08-15 08:00:00",
                },
                {
                    "id": "alarm-3",
                    "devId": "WX3",
                    "alarmTime": "2026-08-15 08:00:00",
                },
                {
                    "id": "alarm-4",
                    "devId": "WX4",
                    "alarmType": 1,
                    "alarmTime": "invalid",
                },
            ],
            source_timezone=BUSINESS_TZ,
            observed_at=OBSERVED,
            ingested_at=INGESTED,
        )

        self.assertEqual(result.events, ())
        self.assertEqual(result.source_row_count, 4)
        self.assertEqual(result.invalid_row_count, 4)
        self.assertIn("invalid_rows_ignored", result.quality_flags)

    def test_invalid_optional_codes_and_markers_are_flagged(self) -> None:
        result = normalize_alarm_events(
            [
                {
                    "id": 0,
                    "devId": "WX1",
                    "alarmType": 205,
                    "alarmStatus": "bad",
                    "dealStatus": "bad",
                    "dealType": 1.5,
                    "alarmTime": "2026-08-15 08:00:00",
                    "dealTime": "invalid",
                    "isDeleted": "maybe",
                }
            ],
            source_timezone=BUSINESS_TZ,
            observed_at=OBSERVED,
            ingested_at=INGESTED,
            include_restricted=True,
        )

        event = result.events[0]
        self.assertEqual(event.source_record_id, "0")
        self.assertIsNone(event.alarm_status_code)
        self.assertIsNone(event.deal_status_code)
        self.assertIsNone(event.deal_type_code)
        self.assertIsNone(event.handled_at)
        self.assertIsNone(event.deleted_marker)
        self.assertIn(
            "invalid_alarm_status_ignored",
            event.quality_flags,
        )
        self.assertIn(
            "invalid_deal_status_ignored",
            event.quality_flags,
        )
        self.assertIn(
            "invalid_deal_type_ignored",
            event.quality_flags,
        )
        self.assertIn("invalid_deal_time_ignored", event.quality_flags)
        self.assertIn("invalid_deleted_marker", event.quality_flags)

    def test_push_status_alias_is_explicit_not_silently_merged(self) -> None:
        result = normalize_alarm_events(
            [
                {
                    "id": "alarm-1",
                    "devId": "WX1",
                    "alarmType": 205,
                    "status": 2,
                    "alarmTime": "2026-08-15 08:00:00",
                }
            ],
            source_timezone=BUSINESS_TZ,
            observed_at=OBSERVED,
            ingested_at=INGESTED,
        )

        event = result.events[0]
        self.assertEqual(event.alarm_status_code, 2)
        self.assertIn("push_status_alias_used", event.quality_flags)
        self.assertIn("alarm_status_map_partial", event.quality_flags)

    def test_lifecycle_times_must_be_timezone_aware_and_ordered(self) -> None:
        with self.assertRaises(ValueError):
            normalize_alarm_events(
                [],
                source_timezone=BUSINESS_TZ,
                observed_at=dt.datetime(2026, 8, 15, 9),
                ingested_at=INGESTED,
            )
        with self.assertRaises(ValueError):
            normalize_alarm_events(
                [],
                source_timezone=BUSINESS_TZ,
                observed_at=INGESTED,
                ingested_at=OBSERVED,
            )


if __name__ == "__main__":
    unittest.main()
