from __future__ import annotations

import datetime as dt
import unittest

from app.data.aee_http import AEEDataHTTPError
from app.data.mcs8_adapter import MCS8ReadOnlyDataAdapter


UTC = dt.timezone.utc
BUSINESS_TZ = dt.timezone(dt.timedelta(hours=8), name="Asia/Shanghai")


class _HTTPClient:
    def __init__(self, payload=None) -> None:
        self.payload = payload
        self.calls = []

    def get_json(self, path, *, query=None):
        self.calls.append((path, query))
        if callable(self.payload):
            return self.payload(path, query)
        return self.payload


class MCS8ReadOnlyDataAdapterTests(unittest.TestCase):
    def test_device_snapshot_from_list_payload(self) -> None:
        client = _HTTPClient(
            [
                {"szIDNO": "WXB310", "nOnline": 1, "groupId": 30000002},
                {"szIDNO": "WXB358", "nOnline": 0, "groupId": 30000002},
            ]
        )
        adapter = MCS8ReadOnlyDataAdapter(client)
        result = adapter.list_device_snapshot()
        self.assertEqual(len(result.rows), 2)
        self.assertEqual(result.records_total, 2)
        self.assertFalse(result.has_more)
        self.assertIn("mcs8_device_snapshot", result.quality_flags)

    def test_record_files_query_shape(self) -> None:
        client = _HTTPClient(
            {
                "error": 200,
                "data": [{"id": "rec-1", "devId": "WXB310"}],
                "recordsTotal": 1,
            }
        )
        adapter = MCS8ReadOnlyDataAdapter(client)
        result = adapter.list_record_files(
            start=dt.datetime(2026, 8, 16, 0, tzinfo=UTC),
            end=dt.datetime(2026, 8, 16, 8, tzinfo=UTC),
            source_timezone=BUSINESS_TZ,
            time_type=0,
            group_with_child=0,
            group_id=0,
        )
        path, query = client.calls[0]
        self.assertEqual(path, "/api/v1/RecordFileList")
        self.assertEqual(query["timeType"], "0")
        self.assertEqual(query["groupWithChild"], "0")
        self.assertEqual(query["groupId"], "0")
        self.assertIn("st", query)
        self.assertIn("et", query)
        self.assertEqual(len(result.rows), 1)

    def test_alarm_list_query_shape(self) -> None:
        client = _HTTPClient(
            {
                "error": 200,
                "data": [{"id": "alarm-1", "devId": "WXB358"}],
                "recordsTotal": 1,
            }
        )
        adapter = MCS8ReadOnlyDataAdapter(client)
        result = adapter.list_alarms(
            start=dt.datetime(2026, 8, 16, 0, tzinfo=UTC),
            end=dt.datetime(2026, 8, 16, 8, tzinfo=UTC),
            source_timezone=BUSINESS_TZ,
            time_type=0,
            group_with_child=0,
            group_id=0,
        )
        path, query = client.calls[0]
        self.assertEqual(path, "/api/v1/AlarmList")
        self.assertEqual(query["timeType"], "0")
        self.assertEqual(len(result.rows), 1)

    def test_upstream_rejected_raises_bounded_error(self) -> None:
        client = _HTTPClient({"error": 333, "data": None})
        adapter = MCS8ReadOnlyDataAdapter(client)
        with self.assertRaises(AEEDataHTTPError) as ctx:
            adapter.list_record_files(
                start=dt.datetime(2026, 8, 16, 0, tzinfo=UTC),
                end=dt.datetime(2026, 8, 16, 8, tzinfo=UTC),
                source_timezone=BUSINESS_TZ,
                time_type=0,
                group_with_child=0,
            )
        self.assertEqual(ctx.exception.code, "MCS8_DATA_UPSTREAM_REJECTED")


if __name__ == "__main__":
    unittest.main()
