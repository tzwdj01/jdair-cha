from __future__ import annotations

import unittest

from app.data.aee_adapter import AEEPageResult
from app.data.pagination import collect_aee_pages


def _page(
    number: int,
    size: int,
    rows,
    *,
    total=None,
    has_more=None,
    invalid=0,
    flags=(),
):
    return AEEPageResult(
        rows=tuple(rows),
        records_total=total,
        page=number,
        page_size=size,
        has_more=has_more,
        invalid_row_count=invalid,
        quality_flags=tuple(flags),
    )


class AEEDataPaginationTests(unittest.TestCase):
    def test_known_total_collects_all_pages(self) -> None:
        calls = []

        def fetch(number, size):
            calls.append((number, size))
            if number == 1:
                return _page(
                    1,
                    size,
                    [{"id": "1"}, {"id": "2"}],
                    total=3,
                    has_more=True,
                )
            return _page(
                2,
                size,
                [{"id": "3"}],
                total=3,
                has_more=False,
            )

        result = collect_aee_pages(fetch, page_size=2)

        self.assertTrue(result.complete)
        self.assertEqual(calls, [(1, 2), (2, 2)])
        self.assertEqual(len(result.rows), 3)
        self.assertEqual(result.fetched_source_count, 3)
        self.assertEqual(result.records_total, 3)

    def test_unknown_total_uses_short_page_without_claiming_source_total(
        self,
    ) -> None:
        def fetch(number, size):
            del number
            return _page(
                1,
                size,
                [{"id": "1"}],
                total=None,
                has_more=None,
                flags=("records_total_unknown",),
            )

        result = collect_aee_pages(fetch, page_size=2)

        self.assertTrue(result.complete)
        self.assertIsNone(result.records_total)
        self.assertIn(
            "completion_inferred_from_short_page",
            result.quality_flags,
        )
        self.assertIn("records_total_unknown", result.quality_flags)

    def test_max_records_marks_collection_incomplete(self) -> None:
        def fetch(number, size):
            return _page(
                number,
                size,
                [{"id": str(index)} for index in range(4)],
                total=10,
                has_more=True,
            )

        result = collect_aee_pages(
            fetch,
            page_size=4,
            max_records=3,
        )

        self.assertFalse(result.complete)
        self.assertEqual(len(result.rows), 3)
        self.assertIn("max_records_reached", result.quality_flags)
        self.assertIn(
            "fetched_count_below_records_total",
            result.quality_flags,
        )

    def test_exact_max_records_stops_without_fetching_an_extra_page(
        self,
    ) -> None:
        calls = []

        def fetch(number, size):
            calls.append((number, size))
            return _page(
                number,
                size,
                [{"id": "1"}, {"id": "2"}],
                total=4,
                has_more=True,
            )

        result = collect_aee_pages(
            fetch,
            page_size=2,
            max_records=2,
        )

        self.assertFalse(result.complete)
        self.assertEqual(calls, [(1, 2)])
        self.assertIn("max_records_reached", result.quality_flags)

    def test_empty_page_before_total_is_explicit(self) -> None:
        result = collect_aee_pages(
            lambda number, size: _page(
                number,
                size,
                [],
                total=5,
                has_more=True,
            ),
            page_size=2,
        )

        self.assertFalse(result.complete)
        self.assertIn("empty_page_before_total", result.quality_flags)

    def test_max_pages_marks_unknown_full_pages_incomplete(self) -> None:
        result = collect_aee_pages(
            lambda number, size: _page(
                number,
                size,
                [{"id": f"{number}-1"}, {"id": f"{number}-2"}],
                total=None,
                has_more=None,
                flags=("records_total_unknown",),
            ),
            page_size=2,
            max_pages=2,
        )

        self.assertFalse(result.complete)
        self.assertEqual(result.pages_fetched, 2)
        self.assertIn("max_pages_reached", result.quality_flags)
        self.assertIn("records_total_unknown", result.quality_flags)

    def test_total_change_and_duplicate_ids_are_not_hidden(self) -> None:
        def fetch(number, size):
            if number == 1:
                return _page(
                    1,
                    size,
                    [{"id": "1"}, {"id": "2"}],
                    total=3,
                    has_more=True,
                )
            return _page(
                2,
                size,
                [{"id": "2"}, {"id": "3"}],
                total=4,
                has_more=False,
            )

        result = collect_aee_pages(fetch, page_size=2)

        self.assertFalse(result.complete)
        self.assertEqual(result.duplicate_source_id_count, 1)
        self.assertIn("records_total_changed", result.quality_flags)
        self.assertIn(
            "duplicate_source_ids_observed",
            result.quality_flags,
        )

    def test_invalid_rows_count_toward_source_page_progress(self) -> None:
        result = collect_aee_pages(
            lambda number, size: _page(
                number,
                size,
                [{"id": "1"}],
                total=2,
                has_more=False,
                invalid=1,
                flags=("invalid_rows_ignored",),
            ),
            page_size=2,
        )

        self.assertTrue(result.complete)
        self.assertEqual(result.fetched_source_count, 2)
        self.assertEqual(result.invalid_row_count, 1)
        self.assertIn("invalid_rows_ignored", result.quality_flags)

    def test_invalid_limits_and_mismatched_page_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            collect_aee_pages(lambda number, size: None, page_size=0)
        with self.assertRaises(ValueError):
            collect_aee_pages(lambda number, size: None, max_pages=0)
        with self.assertRaises(ValueError):
            collect_aee_pages(lambda number, size: None, max_records=0)

        with self.assertRaises(ValueError):
            collect_aee_pages(
                lambda number, size: _page(
                    number + 1,
                    size,
                    [],
                    total=0,
                    has_more=False,
                )
            )


if __name__ == "__main__":
    unittest.main()
