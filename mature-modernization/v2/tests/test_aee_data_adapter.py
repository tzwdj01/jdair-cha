from __future__ import annotations

import datetime as dt
import unittest

from app.data.aee_adapter import AEEReadOnlyDataAdapter
from app.data.aee_http import AEEDataHTTPError


UTC = dt.timezone.utc
BUSINESS_TZ = dt.timezone(dt.timedelta(hours=8), name="Asia/Shanghai")


class _HTTPClient:
    def __init__(self, payload) -> None:
        self.payload = payload
        self.calls = []

    def get_json(self, path, *, query=None):
        self.calls.append((path, query))
        return self.payload


class AEEReadOnlyDataAdapterTests(unittest.TestCase):
    def test_device_online_query_uses_explicit_source_timezone(self) -> None:
        client = _HTTPClient(
            {
                "result": 200,
                "data": [{"id": "1", "devId": "WX1"}],
                "recordsTotal": 2,
            }
        )
        adapter = AEEReadOnlyDataAdapter(client)

        result = adapter.list_device_online(
            start=dt.datetime(2026, 8, 15, 0, tzinfo=UTC),
            end=dt.datetime(2026, 8, 15, 8, tzinfo=UTC),
            source_timezone=BUSINESS_TZ,
            enterprise_id=20_000_000,
            group_id=0,
            device_id=" WX1 ",
            keywords=" test value ",
            page=1,
            page_size=1,
        )

        path, query = client.calls[0]
        self.assertEqual(path, "/api/v1/DevOnlineList")
        self.assertEqual(query["st"], "2026-08-15 08:00:00")
        self.assertEqual(query["et"], "2026-08-15 16:00:00")
        self.assertEqual(query["enterId"], "20000000")
        self.assertEqual(query["devId"], "WX1")
        self.assertEqual(query["keywords"], "test value")
        self.assertEqual(result.records_total, 2)
        self.assertTrue(result.has_more)
        self.assertEqual(result.rows[0]["devId"], "WX1")

    def test_record_file_page_reports_invalid_rows_and_unknown_total(
        self,
    ) -> None:
        client = _HTTPClient(
            {
                "result": "200",
                "data": [
                    {"id": "1", "devId": "WX1"},
                    "invalid-row",
                ],
                "recordsTotal": "unknown",
            }
        )
        adapter = AEEReadOnlyDataAdapter(client)

        result = adapter.list_record_files(
            start=dt.datetime(
                2026,
                8,
                15,
                8,
                tzinfo=BUSINESS_TZ,
            ),
            end=dt.datetime(
                2026,
                8,
                15,
                16,
                tzinfo=BUSINESS_TZ,
            ),
            source_timezone=BUSINESS_TZ,
            enterprise_id="20000000",
        )

        self.assertEqual(len(result.rows), 1)
        self.assertEqual(result.invalid_row_count, 1)
        self.assertIsNone(result.records_total)
        self.assertIsNone(result.has_more)
        self.assertIn("invalid_rows_ignored", result.quality_flags)
        self.assertIn("records_total_unknown", result.quality_flags)

    def test_second_page_has_more_uses_upstream_total(self) -> None:
        client = _HTTPClient(
            {
                "result": 200,
                "data": [{"id": str(index)} for index in range(3)],
                "recordsTotal": 8,
            }
        )
        adapter = AEEReadOnlyDataAdapter(client)

        result = adapter.list_record_files(
            start=dt.datetime(
                2026,
                8,
                15,
                8,
                tzinfo=BUSINESS_TZ,
            ),
            end=dt.datetime(
                2026,
                8,
                15,
                16,
                tzinfo=BUSINESS_TZ,
            ),
            source_timezone=BUSINESS_TZ,
            enterprise_id="20000000",
            page=2,
            page_size=3,
        )

        self.assertTrue(result.has_more)

    def test_device_tree_uses_only_the_verified_path(self) -> None:
        payload = {"result": 200, "content": []}
        client = _HTTPClient(payload)
        adapter = AEEReadOnlyDataAdapter(client)

        self.assertIs(adapter.get_device_tree(), payload)
        self.assertEqual(
            client.calls,
            [("/api/v1/ext/DevTree", None)],
        )

    def test_invalid_ranges_pagination_and_enterprise_are_rejected(
        self,
    ) -> None:
        adapter = AEEReadOnlyDataAdapter(
            _HTTPClient({"result": 200, "data": []})
        )
        valid_start = dt.datetime(
            2026,
            8,
            15,
            8,
            tzinfo=BUSINESS_TZ,
        )
        valid_end = dt.datetime(
            2026,
            8,
            15,
            16,
            tzinfo=BUSINESS_TZ,
        )

        invalid_cases = (
            {
                "start": dt.datetime(2026, 8, 15, 8),
                "end": valid_end,
            },
            {
                "start": valid_end,
                "end": valid_start,
            },
            {
                "start": valid_start,
                "end": valid_end,
                "page": 0,
            },
            {
                "start": valid_start,
                "end": valid_end,
                "page_size": 10_001,
            },
            {
                "start": valid_start,
                "end": valid_end,
                "enterprise_id": "",
            },
        )
        for overrides in invalid_cases:
            values = {
                "start": valid_start,
                "end": valid_end,
                "source_timezone": BUSINESS_TZ,
                "enterprise_id": "20000000",
            }
            values.update(overrides)
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    adapter.list_device_online(**values)

    def test_upstream_rejection_and_invalid_page_are_bounded(self) -> None:
        common = {
            "start": dt.datetime(
                2026,
                8,
                15,
                8,
                tzinfo=BUSINESS_TZ,
            ),
            "end": dt.datetime(
                2026,
                8,
                15,
                16,
                tzinfo=BUSINESS_TZ,
            ),
            "source_timezone": BUSINESS_TZ,
            "enterprise_id": "20000000",
        }
        rejected = AEEReadOnlyDataAdapter(
            _HTTPClient({"result": 403, "data": []})
        )
        with self.assertRaises(AEEDataHTTPError) as rejection:
            rejected.list_device_online(**common)
        self.assertEqual(
            rejection.exception.code,
            "AEE_DATA_UPSTREAM_REJECTED",
        )

        malformed = AEEReadOnlyDataAdapter(
            _HTTPClient({"result": 200, "data": {}})
        )
        with self.assertRaises(AEEDataHTTPError) as invalid:
            malformed.list_record_files(**common)
        self.assertEqual(
            invalid.exception.code,
            "AEE_DATA_INVALID_RESPONSE",
        )


if __name__ == "__main__":
    unittest.main()
