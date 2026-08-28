from __future__ import annotations

import datetime as dt
import unittest

from app.data.normalization import (
    normalize_device_location_events,
    normalize_device_status_events,
    normalize_media_files,
)


UTC = dt.timezone.utc
BUSINESS_TZ = dt.timezone(dt.timedelta(hours=8), name="Asia/Shanghai")
OBSERVED = dt.datetime(2026, 8, 15, 9, tzinfo=BUSINESS_TZ)
INGESTED = dt.datetime(2026, 8, 15, 9, 0, 2, tzinfo=BUSINESS_TZ)


class DeviceStatusNormalizationTests(unittest.TestCase):
    def test_online_event_preserves_source_and_lifecycle_times(self) -> None:
        result = normalize_device_status_events(
            [
                {
                    "id": "evt-1",
                    "devId": "WX1",
                    "groupId": "G1",
                    "devType": 1,
                    "status": 1,
                    "time": "2026-08-15 08:30:00",
                }
            ],
            source_timezone=BUSINESS_TZ,
            observed_at=OBSERVED,
            ingested_at=INGESTED,
        )

        event = result.events[0]
        self.assertEqual(event.source_system, "aee")
        self.assertEqual(event.source_record_id, "evt-1")
        self.assertEqual(event.device_id, "WX1")
        self.assertEqual(event.device_type_code, 1)
        self.assertEqual(event.status_code, 1)
        self.assertTrue(event.online)
        self.assertEqual(
            event.occurred_at,
            dt.datetime(2026, 8, 15, 0, 30, tzinfo=UTC),
        )
        self.assertEqual(
            event.observed_at,
            dt.datetime(2026, 8, 15, 1, tzinfo=UTC),
        )

    def test_non_online_status_is_not_guessed_as_offline(self) -> None:
        result = normalize_device_status_events(
            [
                {
                    "devId": "WX1",
                    "status": 2,
                    "time": "2026-08-15 08:30:00",
                }
            ],
            source_timezone=BUSINESS_TZ,
            observed_at=OBSERVED,
            ingested_at=INGESTED,
        )

        event = result.events[0]
        self.assertIsNone(event.online)
        self.assertIn(
            "non_online_status_map_partial",
            event.quality_flags,
        )
        self.assertIn("online_state_unknown", event.quality_flags)
        self.assertIn("source_record_id_missing", event.quality_flags)

    def test_invalid_required_rows_are_counted_not_materialized(self) -> None:
        result = normalize_device_status_events(
            [
                {"status": 1, "time": "2026-08-15 08:00:00"},
                {
                    "devId": "WX1",
                    "status": "invalid",
                    "time": "2026-08-15 08:00:00",
                },
                {
                    "devId": "WX2",
                    "status": 1,
                    "time": "invalid",
                },
            ],
            source_timezone=BUSINESS_TZ,
            observed_at=OBSERVED,
            ingested_at=INGESTED,
        )

        self.assertEqual(result.events, ())
        self.assertEqual(result.source_row_count, 3)
        self.assertEqual(result.invalid_row_count, 3)
        self.assertIn("invalid_rows_ignored", result.quality_flags)

    def test_lifecycle_times_must_be_ordered_and_timezone_aware(self) -> None:
        with self.assertRaises(ValueError):
            normalize_device_status_events(
                [],
                source_timezone=BUSINESS_TZ,
                observed_at=dt.datetime(2026, 8, 15, 9),
                ingested_at=INGESTED,
            )
        with self.assertRaises(ValueError):
            normalize_device_status_events(
                [],
                source_timezone=BUSINESS_TZ,
                observed_at=INGESTED,
                ingested_at=OBSERVED,
            )


class DeviceLocationNormalizationTests(unittest.TestCase):
    def test_legacy_gps_aliases_and_source_times_are_normalized(
        self,
    ) -> None:
        result = normalize_device_location_events(
            [
                {
                    "id": "gps-1",
                    "devId": "WX1",
                    "latitude": "39.9001",
                    "longitude": "116.4002",
                    "dateTime": "2026-08-15 08:30:00",
                    "speed": "12.5",
                    "direction": 180,
                    "accuracy": "8",
                    "battery": 76,
                    "gpsType": 2,
                    "netWorkType": "LTE",
                }
            ],
            device_id="WX1",
            source_timezone=BUSINESS_TZ,
            observed_at=OBSERVED,
            ingested_at=INGESTED,
        )

        event = result.events[0]
        self.assertEqual(event.source_system, "mcs8")
        self.assertEqual(event.location_source, "legacy_gps_history")
        self.assertEqual(event.source_record_id, "gps-1")
        self.assertEqual(event.device_id, "WX1")
        self.assertEqual(event.latitude, 39.9001)
        self.assertEqual(event.longitude, 116.4002)
        self.assertEqual(
            event.gps_occurred_at,
            dt.datetime(2026, 8, 15, 0, 30, tzinfo=UTC),
        )
        self.assertEqual(event.speed_value, 12.5)
        self.assertEqual(event.direction_value, 180.0)
        self.assertEqual(event.accuracy_value, 8.0)
        self.assertEqual(event.battery_value, 76.0)
        self.assertEqual(event.gps_type_code, 2)
        self.assertEqual(event.network_type_code, "LTE")
        self.assertIn(
            "coordinate_system_unverified",
            event.quality_flags,
        )
        self.assertIn("location_data_restricted", event.quality_flags)
        self.assertIn("speed_unit_unverified", event.quality_flags)
        self.assertIn(
            "network_type_code_map_unknown",
            event.quality_flags,
        )

    def test_missing_optional_measurements_do_not_become_zero(self) -> None:
        result = normalize_device_location_events(
            [
                {
                    "lat": 31.2,
                    "lng": 121.4,
                    "gpsTime": "2026-08-15 08:30:00",
                }
            ],
            device_id="WX1",
            source_timezone=BUSINESS_TZ,
            observed_at=OBSERVED,
            ingested_at=INGESTED,
        )

        event = result.events[0]
        self.assertIsNone(event.speed_value)
        self.assertIsNone(event.direction_value)
        self.assertIsNone(event.accuracy_value)
        self.assertIsNone(event.battery_value)
        self.assertIsNone(event.gps_type_code)
        self.assertIsNone(event.network_type_code)
        self.assertIn("source_record_id_missing", event.quality_flags)

    def test_invalid_coordinates_time_and_device_scope_are_rejected(
        self,
    ) -> None:
        result = normalize_device_location_events(
            [
                {
                    "lat": 0,
                    "lng": 0,
                    "gpsTime": "2026-08-15 08:30:00",
                },
                {
                    "lat": 91,
                    "lng": 116,
                    "gpsTime": "2026-08-15 08:30:00",
                },
                {
                    "lat": "nan",
                    "lng": 116,
                    "gpsTime": "2026-08-15 08:30:00",
                },
                {
                    "lat": 39,
                    "lng": 116,
                    "gpsTime": "not-a-time",
                },
                {
                    "devId": "WX2",
                    "lat": 39,
                    "lng": 116,
                    "gpsTime": "2026-08-15 08:30:00",
                },
            ],
            device_id="WX1",
            source_timezone=BUSINESS_TZ,
            observed_at=OBSERVED,
            ingested_at=INGESTED,
        )

        self.assertEqual(result.events, ())
        self.assertEqual(result.source_row_count, 5)
        self.assertEqual(result.invalid_row_count, 5)
        self.assertIn("invalid_rows_ignored", result.quality_flags)
        self.assertIn("row_device_scope_mismatch", result.quality_flags)

    def test_invalid_optional_values_are_omitted_and_flagged(self) -> None:
        result = normalize_device_location_events(
            [
                {
                    "lat": 39.9,
                    "lng": 116.4,
                    "gpsTime": "2026-08-15 08:30:00",
                    "speed": "fast",
                    "direct": float("inf"),
                    "accuracy": "unknown",
                    "battery": False,
                    "gpsType": False,
                    "networkType": True,
                }
            ],
            device_id="WX1",
            source_timezone=BUSINESS_TZ,
            observed_at=OBSERVED,
            ingested_at=INGESTED,
        )

        event = result.events[0]
        self.assertIsNone(event.speed_value)
        self.assertIsNone(event.direction_value)
        self.assertIsNone(event.accuracy_value)
        self.assertIsNone(event.battery_value)
        self.assertIsNone(event.gps_type_code)
        self.assertIsNone(event.network_type_code)
        self.assertIn("invalid_speed_ignored", event.quality_flags)
        self.assertIn("invalid_direction_ignored", event.quality_flags)
        self.assertIn("invalid_accuracy_ignored", event.quality_flags)
        self.assertIn("invalid_battery_ignored", event.quality_flags)
        self.assertIn("invalid_gps_type_ignored", event.quality_flags)
        self.assertIn(
            "invalid_network_type_ignored",
            event.quality_flags,
        )

    def test_future_source_time_is_preserved_but_marked(self) -> None:
        result = normalize_device_location_events(
            [
                {
                    "lat": 39.9,
                    "lng": 116.4,
                    "gpsTime": "2026-08-15 09:01:00",
                }
            ],
            device_id="WX1",
            source_timezone=BUSINESS_TZ,
            observed_at=OBSERVED,
            ingested_at=INGESTED,
        )

        event = result.events[0]
        self.assertIn(
            "source_time_after_observation",
            event.quality_flags,
        )
        self.assertIn(
            "source_time_after_observation",
            result.quality_flags,
        )

    def test_scope_and_lifecycle_arguments_are_validated(self) -> None:
        with self.assertRaises(ValueError):
            normalize_device_location_events(
                [],
                device_id=" ",
                source_timezone=BUSINESS_TZ,
                observed_at=OBSERVED,
                ingested_at=INGESTED,
            )
        with self.assertRaises(ValueError):
            normalize_device_location_events(
                [],
                device_id="WX1",
                source_timezone=BUSINESS_TZ,
                observed_at=INGESTED,
                ingested_at=OBSERVED,
            )


class MediaFileNormalizationTests(unittest.TestCase):
    def test_verified_aliases_units_and_media_kind_are_normalized(self) -> None:
        result = normalize_media_files(
            [
                {
                    "id": "file-1",
                    "DevId": "WX1",
                    "devName": "Device 1",
                    "groupId": "G1",
                    "fileName": "video.mp4",
                    "fType": 3,
                    "lType": 0,
                    "fileSize": 4096,
                    "videoTime": 125,
                    "startTime": "2026-08-15 08:00:00",
                    "endTime": "2026-08-15 08:02:05",
                    "uploadTime": "2026-08-15 08:05:00",
                    "workNo": "WORK-1",
                }
            ],
            source_timezone=BUSINESS_TZ,
            observed_at=OBSERVED,
            ingested_at=INGESTED,
        )

        item = result.files[0]
        self.assertEqual(item.source_record_id, "file-1")
        self.assertEqual(item.device_id, "WX1")
        self.assertEqual(item.device_name_at_capture, "Device 1")
        self.assertEqual(item.title, "video.mp4")
        self.assertEqual(item.media_kind, "video")
        self.assertEqual(item.file_size_bytes, 4096)
        self.assertEqual(item.duration_seconds, 125)
        self.assertEqual(
            item.created_at_source,
            dt.datetime(2026, 8, 15, 0, tzinfo=UTC),
        )
        self.assertEqual(
            item.end_at_source,
            dt.datetime(2026, 8, 15, 0, 2, 5, tzinfo=UTC),
        )
        self.assertIn(
            "source_id_scope_unverified",
            item.quality_flags,
        )

    def test_restricted_fields_are_omitted_by_default(self) -> None:
        row = {
            "id": "file-1",
            "devId": "WX1",
            "fType": 1,
            "peopleNo": "person-1",
            "peopleName": "Person",
            "des": "restricted text",
        }

        default = normalize_media_files(
            [row],
            source_timezone=BUSINESS_TZ,
            observed_at=OBSERVED,
            ingested_at=INGESTED,
        )
        included = normalize_media_files(
            [row],
            source_timezone=BUSINESS_TZ,
            observed_at=OBSERVED,
            ingested_at=INGESTED,
            include_restricted=True,
        )

        self.assertIsNone(default.files[0].people_no)
        self.assertIsNone(default.files[0].people_name)
        self.assertIsNone(default.files[0].description)
        self.assertIn(
            "restricted_fields_omitted",
            default.files[0].quality_flags,
        )
        self.assertEqual(default.restricted_field_row_count, 1)
        self.assertEqual(included.files[0].people_no, "person-1")
        self.assertEqual(included.files[0].people_name, "Person")
        self.assertEqual(
            included.files[0].description,
            "restricted text",
        )

    def test_invalid_values_remain_visible_as_quality_flags(self) -> None:
        result = normalize_media_files(
            [
                {"fType": 3, "fileLen": 1},
                {
                    "devId": "WX1",
                    "fType": "unknown",
                    "lType": 9,
                    "fileLen": -1,
                    "duration": "bad",
                    "fileTime": "not-a-time",
                    "endTime": "also-not-a-time",
                    "upLoadTime": "also-not-a-time",
                    "isDeleted": "maybe",
                },
            ],
            source_timezone=BUSINESS_TZ,
            observed_at=OBSERVED,
            ingested_at=INGESTED,
        )

        self.assertEqual(result.invalid_row_count, 1)
        item = result.files[0]
        self.assertEqual(item.media_kind, "unknown")
        self.assertIsNone(item.file_size_bytes)
        self.assertIsNone(item.duration_seconds)
        self.assertIn("unknown_file_type", item.quality_flags)
        self.assertIn("unknown_list_type", item.quality_flags)
        self.assertIn(
            "invalid_file_size_ignored",
            item.quality_flags,
        )
        self.assertIn(
            "invalid_created_time_ignored",
            item.quality_flags,
        )
        self.assertIn(
            "invalid_end_time_ignored",
            item.quality_flags,
        )
        self.assertIn(
            "invalid_uploaded_time_ignored",
            item.quality_flags,
        )
        self.assertIn("invalid_deleted_marker", item.quality_flags)

    def test_non_video_duration_is_not_used_as_video_duration(self) -> None:
        result = normalize_media_files(
            [
                {
                    "id": "file-1",
                    "devId": "WX1",
                    "fType": 4,
                    "duration": 999,
                }
            ],
            source_timezone=BUSINESS_TZ,
            observed_at=OBSERVED,
            ingested_at=INGESTED,
        )

        item = result.files[0]
        self.assertEqual(item.media_kind, "device_file")
        self.assertIsNone(item.duration_seconds)
        self.assertIn(
            "non_video_duration_ignored",
            item.quality_flags,
        )

    def test_partial_source_status_and_delete_codes_are_preserved_raw(
        self,
    ) -> None:
        result = normalize_media_files(
            [
                {
                    "id": "file-1",
                    "devId": "WX1",
                    "fType": 3,
                    "source": 2,
                    "upLoadStatus": 3,
                    "isDeleted": 1,
                }
            ],
            source_timezone=BUSINESS_TZ,
            observed_at=OBSERVED,
            ingested_at=INGESTED,
        )

        item = result.files[0]
        self.assertEqual(item.source_code, 2)
        self.assertEqual(item.upload_status_code, 3)
        self.assertTrue(item.deleted_marker)
        self.assertIn("source_code_map_partial", item.quality_flags)
        self.assertIn(
            "upload_status_code_map_partial",
            item.quality_flags,
        )
        self.assertIn(
            "deletion_semantics_unverified",
            item.quality_flags,
        )

    def test_media_lifecycle_times_use_same_validation(self) -> None:
        with self.assertRaises(ValueError):
            normalize_media_files(
                [],
                source_timezone=BUSINESS_TZ,
                observed_at=OBSERVED,
                ingested_at=dt.datetime(2026, 8, 15, 8),
            )

    def test_epoch_zero_capture_time_sentinel_is_treated_as_missing(
        self,
    ) -> None:
        # LIVE VERIFIED 2026-08-16: RecordFileList startTime may be the
        # "1970-01-01 08:00:00" sentinel (epoch-zero UTC). It must not pollute
        # capture-time range queries; the row stays queryable by upload time.
        result = normalize_media_files(
            [
                {
                    "id": "file-epoch",
                    "devId": "WX1",
                    "fType": 3,
                    "startTime": "1970-01-01 08:00:00",
                    "endTime": "2026-08-15 08:02:05",
                    "upLoadTime": "2026-08-15 08:05:00",
                }
            ],
            source_timezone=BUSINESS_TZ,
            observed_at=OBSERVED,
            ingested_at=INGESTED,
        )

        item = result.files[0]
        self.assertIsNone(item.created_at_source)
        self.assertIsNotNone(item.end_at_source)
        self.assertIsNotNone(item.uploaded_at_source)
        self.assertIn(
            "epoch_zero_source_time_ignored",
            item.quality_flags,
        )
        self.assertNotIn(
            "invalid_created_time_ignored",
            item.quality_flags,
        )
        self.assertNotIn("media_time_missing", item.quality_flags)


if __name__ == "__main__":
    unittest.main()
