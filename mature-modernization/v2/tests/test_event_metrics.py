from __future__ import annotations

import datetime as dt
import unittest
from dataclasses import replace

from app.data.metrics import (
    aggregate_alarm_events,
    aggregate_device_locations,
    aggregate_realtime_views,
)
from app.data.normalization import (
    normalize_alarm_events,
    normalize_device_location_events,
)
from app.data.realtime_views import build_realtime_view_event


UTC = dt.timezone.utc
BUSINESS_TZ = dt.timezone(dt.timedelta(hours=8), name="Asia/Shanghai")


def location_events(
    rows,
    *,
    device_id: str,
    observed_at: dt.datetime | None = None,
):
    observed = observed_at or dt.datetime(
        2026,
        8,
        15,
        1,
        tzinfo=UTC,
    )
    return normalize_device_location_events(
        rows,
        device_id=device_id,
        source_timezone=UTC,
        observed_at=observed,
        ingested_at=observed + dt.timedelta(seconds=1),
    ).events


def view_event(
    *,
    stream_id: str,
    username: str,
    device_id: str,
    opened_second: int,
    first_frame_second: int | None,
    closed_second: int,
    result_reason: str,
    error_code: str | None = None,
):
    opened = dt.datetime(
        2026,
        8,
        15,
        0,
        0,
        opened_second,
        tzinfo=UTC,
    )
    first_frame = (
        opened
        + dt.timedelta(seconds=first_frame_second)
        if first_frame_second is not None
        else None
    )
    return build_realtime_view_event(
        username=username,
        user_id=None,
        device_id=device_id,
        session_id="session-1",
        stream_id=stream_id,
        opened_at=opened,
        first_frame_at=first_frame,
        closed_at=opened + dt.timedelta(seconds=closed_second),
        error_code=error_code,
        width=1920 if first_frame is not None else None,
        height=1080 if first_frame is not None else None,
        track_state="live" if first_frame is not None else None,
        close_reason=result_reason,
        release_mode="session_disconnect",
    )


class DeviceLocationMetricTests(unittest.TestCase):
    def test_coverage_and_age_are_raw_threshold_free_values(self) -> None:
        events = [
            *location_events(
                [
                    {
                        "lat": 39.9,
                        "lng": 116.4,
                        "gpsTime": "2026-08-15 00:10:00+00:00",
                        "speed": 10,
                        "accuracy": 5,
                    },
                    {
                        "lat": 39.91,
                        "lng": 116.41,
                        "gpsTime": "2026-08-15 00:30:00+00:00",
                        "direction": 90,
                        "battery": 80,
                        "gpsType": 2,
                        "netWorkType": "LTE",
                    },
                ],
                device_id="WX1",
            ),
            *location_events(
                [
                    {
                        "lat": 31.2,
                        "lng": 121.4,
                        "gpsTime": "2026-08-15 00:40:00+00:00",
                    }
                ],
                device_id="WX2",
            ),
        ]

        result = aggregate_device_locations(
            events,
            window_start=dt.datetime(
                2026,
                8,
                15,
                0,
                tzinfo=UTC,
            ),
            window_end=dt.datetime(
                2026,
                8,
                15,
                1,
                tzinfo=UTC,
            ),
        )

        self.assertEqual(result.source_event_count, 3)
        self.assertEqual(result.included_event_count, 3)
        metrics = {
            metric.device_id: metric
            for metric in result.devices
        }
        wx1 = metrics["WX1"]
        self.assertEqual(wx1.event_count, 2)
        self.assertEqual(wx1.distinct_coordinate_count, 2)
        self.assertEqual(wx1.source_span_seconds, 1200)
        self.assertEqual(wx1.latest_age_seconds, 1800)
        self.assertEqual(wx1.speed_value_count, 1)
        self.assertEqual(wx1.direction_value_count, 1)
        self.assertEqual(wx1.accuracy_value_count, 1)
        self.assertEqual(wx1.battery_value_count, 1)
        self.assertEqual(wx1.gps_type_count, 1)
        self.assertEqual(wx1.network_type_count, 1)
        self.assertNotIn("stale", " ".join(result.quality_flags))

    def test_duplicates_and_latest_same_position_update_are_collapsed(
        self,
    ) -> None:
        base = location_events(
            [
                {
                    "id": "gps-1",
                    "lat": 39.9,
                    "lng": 116.4,
                    "gpsTime": "2026-08-15 00:30:00+00:00",
                    "battery": 70,
                }
            ],
            device_id="WX1",
        )[0]
        updated = replace(
            base,
            battery_value=71,
            observed_at=base.observed_at + dt.timedelta(minutes=1),
            ingested_at=base.ingested_at + dt.timedelta(minutes=1),
        )

        result = aggregate_device_locations(
            [base, base, updated],
            window_start=dt.datetime(
                2026,
                8,
                15,
                0,
                tzinfo=UTC,
            ),
            window_end=dt.datetime(
                2026,
                8,
                15,
                2,
                tzinfo=UTC,
            ),
        )

        self.assertEqual(result.included_event_count, 1)
        self.assertEqual(result.duplicate_event_count, 1)
        self.assertEqual(result.updated_observation_count, 1)
        self.assertEqual(result.devices[0].battery_value_count, 1)
        self.assertIn(
            "location_updates_collapsed_to_latest_observation",
            result.quality_flags,
        )

    def test_same_timestamp_coordinate_conflict_is_excluded(self) -> None:
        base = location_events(
            [
                {
                    "lat": 39.9,
                    "lng": 116.4,
                    "gpsTime": "2026-08-15 00:30:00+00:00",
                }
            ],
            device_id="WX1",
        )[0]
        conflict = replace(base, longitude=116.5)

        result = aggregate_device_locations(
            [base, conflict],
            window_start=dt.datetime(
                2026,
                8,
                15,
                0,
                tzinfo=UTC,
            ),
            window_end=dt.datetime(
                2026,
                8,
                15,
                2,
                tzinfo=UTC,
            ),
        )

        self.assertEqual(result.included_event_count, 0)
        self.assertEqual(result.conflicting_timestamp_count, 1)
        self.assertTrue(result.partial)
        self.assertIn(
            "same_timestamp_location_conflicts_excluded",
            result.quality_flags,
        )

    def test_invalid_and_out_of_window_events_are_counted(self) -> None:
        before, inside = location_events(
            [
                {
                    "lat": 39.8,
                    "lng": 116.3,
                    "gpsTime": "2026-08-14 23:59:00+00:00",
                },
                {
                    "lat": 39.9,
                    "lng": 116.4,
                    "gpsTime": "2026-08-15 00:30:00+00:00",
                },
            ],
            device_id="WX1",
        )
        invalid = replace(inside, latitude=999)

        result = aggregate_device_locations(
            [before, inside, invalid],
            window_start=dt.datetime(
                2026,
                8,
                15,
                0,
                tzinfo=UTC,
            ),
            window_end=dt.datetime(
                2026,
                8,
                15,
                1,
                tzinfo=UTC,
            ),
            complete=False,
        )

        self.assertEqual(result.included_event_count, 1)
        self.assertEqual(result.out_of_window_count, 1)
        self.assertEqual(result.invalid_event_count, 1)
        self.assertTrue(result.partial)
        self.assertIn("invalid_events_excluded", result.quality_flags)
        self.assertIn(
            "events_outside_window_excluded",
            result.quality_flags,
        )
        self.assertIn("input_scope_incomplete", result.quality_flags)

    def test_window_must_be_aware_and_ordered(self) -> None:
        with self.assertRaises(ValueError):
            aggregate_device_locations(
                [],
                window_start=dt.datetime(2026, 8, 15, 0),
                window_end=dt.datetime(
                    2026,
                    8,
                    15,
                    1,
                    tzinfo=UTC,
                ),
            )
        with self.assertRaises(ValueError):
            aggregate_device_locations(
                [],
                window_start=dt.datetime(
                    2026,
                    8,
                    15,
                    1,
                    tzinfo=UTC,
                ),
                window_end=dt.datetime(
                    2026,
                    8,
                    15,
                    0,
                    tzinfo=UTC,
                ),
            )


class RealtimeViewMetricTests(unittest.TestCase):
    def test_totals_results_and_dimensions_are_reproducible(self) -> None:
        events = [
            view_event(
                stream_id="stream-1",
                username="alice",
                device_id="WX1",
                opened_second=0,
                first_frame_second=2,
                closed_second=12,
                result_reason="session_close",
            ),
            view_event(
                stream_id="stream-2",
                username="alice",
                device_id="WX2",
                opened_second=20,
                first_frame_second=None,
                closed_second=40,
                result_reason="first_frame_timeout",
                error_code="FIRST_FRAME_TIMEOUT",
            ),
            view_event(
                stream_id="stream-3",
                username="bob",
                device_id="WX1",
                opened_second=40,
                first_frame_second=1,
                closed_second=6,
                result_reason="abnormal_disconnect",
            ),
        ]

        result = aggregate_realtime_views(events)

        self.assertEqual(result.event_count, 3)
        self.assertEqual(result.played_count, 1)
        self.assertEqual(result.first_frame_count, 2)
        self.assertEqual(result.connection_duration_seconds, 58)
        self.assertEqual(result.view_duration_seconds, 15)
        self.assertEqual(result.first_frame_latency_seconds, 3)
        self.assertEqual(
            result.average_first_frame_latency_seconds,
            1.5,
        )
        self.assertEqual(
            dict(result.result_counts),
            {
                "abnormal_disconnect": 1,
                "played": 1,
                "timeout": 1,
            },
        )
        self.assertEqual(
            dict(result.error_counts),
            {"FIRST_FRAME_TIMEOUT": 1},
        )
        users = {
            item.dimension_id: item
            for item in result.users
        }
        self.assertEqual(users["alice"].view_count, 2)
        self.assertEqual(users["alice"].view_duration_seconds, 10)
        devices = {
            item.dimension_id: item
            for item in result.devices
        }
        self.assertEqual(devices["WX1"].view_count, 2)
        self.assertEqual(devices["WX1"].view_duration_seconds, 15)

    def test_duplicates_conflicts_and_incomplete_scope_are_explicit(
        self,
    ) -> None:
        event = view_event(
            stream_id="stream-1",
            username="alice",
            device_id="WX1",
            opened_second=0,
            first_frame_second=1,
            closed_second=5,
            result_reason="session_close",
        )
        conflict = replace(
            event,
            result="failed",
            error_code="CONFLICT",
        )

        result = aggregate_realtime_views(
            [event, event, conflict],
            complete=False,
        )

        self.assertEqual(result.event_count, 0)
        self.assertEqual(result.duplicate_event_count, 1)
        self.assertEqual(result.conflicting_stream_count, 1)
        self.assertTrue(result.partial)
        self.assertIn(
            "conflicting_streams_excluded",
            result.quality_flags,
        )
        self.assertIn("input_scope_incomplete", result.quality_flags)

    def test_stored_duration_mismatch_is_recalculated(self) -> None:
        event = view_event(
            stream_id="stream-1",
            username="alice",
            device_id="WX1",
            opened_second=0,
            first_frame_second=2,
            closed_second=12,
            result_reason="session_close",
        )
        event = replace(
            event,
            connection_duration_seconds=999,
            view_duration_seconds=999,
        )

        result = aggregate_realtime_views([event])

        self.assertEqual(result.connection_duration_seconds, 12)
        self.assertEqual(result.view_duration_seconds, 10)
        self.assertIn(
            "connection_duration_mismatch_recalculated",
            result.quality_flags,
        )
        self.assertIn(
            "view_duration_mismatch_recalculated",
            result.quality_flags,
        )

    def test_invalid_first_frame_interval_is_excluded(self) -> None:
        event = view_event(
            stream_id="stream-1",
            username="alice",
            device_id="WX1",
            opened_second=0,
            first_frame_second=1,
            closed_second=5,
            result_reason="session_close",
        )
        event = replace(
            event,
            first_frame_at=event.opened_at - dt.timedelta(seconds=1),
        )

        result = aggregate_realtime_views([event])

        self.assertEqual(result.event_count, 0)
        self.assertEqual(result.invalid_event_count, 1)
        self.assertTrue(result.partial)
        self.assertIn(
            "invalid_first_frame_event_excluded",
            result.quality_flags,
        )


class AlarmMetricTests(unittest.TestCase):
    def normalized(
        self,
        rows,
        *,
        observed_at: dt.datetime,
        ingested_at: dt.datetime,
    ):
        return normalize_alarm_events(
            rows,
            source_timezone=BUSINESS_TZ,
            observed_at=observed_at,
            ingested_at=ingested_at,
        ).events

    def test_latest_alarm_observation_is_used_for_raw_code_counts(
        self,
    ) -> None:
        first_observed = dt.datetime(
            2026,
            8,
            15,
            9,
            tzinfo=BUSINESS_TZ,
        )
        later_observed = first_observed + dt.timedelta(minutes=5)
        base_row = {
            "id": "alarm-1",
            "devId": "WX1",
            "alarmType": 205,
            "alarmStatus": 1,
            "dealStatus": 0,
            "alarmTime": "2026-08-15 08:30:00",
        }
        first = self.normalized(
            [base_row],
            observed_at=first_observed,
            ingested_at=first_observed,
        )[0]
        updated = self.normalized(
            [{**base_row, "dealStatus": 2}],
            observed_at=later_observed,
            ingested_at=later_observed,
        )[0]

        result = aggregate_alarm_events([first, first, updated])

        self.assertEqual(result.alarm_count, 1)
        self.assertEqual(result.duplicate_row_count, 1)
        self.assertEqual(result.updated_record_count, 1)
        self.assertEqual(dict(result.alarm_type_counts), {205: 1})
        self.assertEqual(dict(result.alarm_status_counts), {1: 1})
        self.assertEqual(dict(result.deal_status_counts), {2: 1})
        self.assertEqual(result.devices[0].device_id, "WX1")
        self.assertIn(
            "alarm_updates_collapsed_to_latest_observation",
            result.quality_flags,
        )

    def test_conflicting_latest_alarm_rows_are_excluded(self) -> None:
        observed = dt.datetime(
            2026,
            8,
            15,
            9,
            tzinfo=BUSINESS_TZ,
        )
        common = {
            "id": "alarm-1",
            "devId": "WX1",
            "alarmType": 205,
            "alarmTime": "2026-08-15 08:30:00",
        }
        events = self.normalized(
            [
                {**common, "alarmStatus": 1},
                {**common, "alarmStatus": 2},
            ],
            observed_at=observed,
            ingested_at=observed,
        )

        result = aggregate_alarm_events(events, complete=False)

        self.assertEqual(result.alarm_count, 0)
        self.assertEqual(result.conflicting_record_count, 1)
        self.assertTrue(result.partial)
        self.assertIn(
            "conflicting_alarm_records_excluded",
            result.quality_flags,
        )
        self.assertIn("input_scope_incomplete", result.quality_flags)

    def test_missing_alarm_statuses_remain_unknown_not_zero(self) -> None:
        observed = dt.datetime(
            2026,
            8,
            15,
            9,
            tzinfo=BUSINESS_TZ,
        )
        event = self.normalized(
            [
                {
                    "id": "alarm-1",
                    "devId": "WX1",
                    "alarmType": 205,
                    "alarmTime": "2026-08-15 08:30:00",
                }
            ],
            observed_at=observed,
            ingested_at=observed,
        )[0]

        result = aggregate_alarm_events([event])

        self.assertEqual(result.missing_alarm_status_count, 1)
        self.assertEqual(result.missing_deal_status_count, 1)
        self.assertEqual(result.alarm_status_counts, ())
        self.assertEqual(result.deal_status_counts, ())
        self.assertIn("alarm_status_missing", result.quality_flags)
        self.assertIn("deal_status_missing", result.quality_flags)


if __name__ == "__main__":
    unittest.main()
