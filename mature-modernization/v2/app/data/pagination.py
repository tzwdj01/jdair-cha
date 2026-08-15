from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .aee_adapter import AEEPageResult


PageFetcher = Callable[[int, int], AEEPageResult]


@dataclass(frozen=True, slots=True)
class AEEPageCollection:
    rows: tuple[dict[str, Any], ...]
    records_total: int | None
    pages_fetched: int
    fetched_source_count: int
    invalid_row_count: int
    duplicate_source_id_count: int
    complete: bool
    quality_flags: tuple[str, ...]


def collect_aee_pages(
    fetch_page: PageFetcher,
    *,
    page_size: int = 1_000,
    max_pages: int = 100,
    max_records: int = 100_000,
) -> AEEPageCollection:
    """Collect AEE pages without silently claiming truncated data is complete."""

    if page_size <= 0:
        raise ValueError("page_size must be positive")
    if max_pages <= 0:
        raise ValueError("max_pages must be positive")
    if max_records <= 0:
        raise ValueError("max_records must be positive")

    rows: list[dict[str, Any]] = []
    records_total: int | None = None
    pages_fetched = 0
    fetched_source_count = 0
    invalid_row_count = 0
    duplicate_source_id_count = 0
    seen_source_ids: set[str] = set()
    flags: set[str] = set()
    complete = False

    for page_number in range(1, max_pages + 1):
        page = fetch_page(page_number, page_size)
        pages_fetched += 1
        if page.page != page_number or page.page_size != page_size:
            raise ValueError("page fetcher returned mismatched pagination")

        source_count = len(page.rows) + page.invalid_row_count
        fetched_source_count += source_count
        invalid_row_count += page.invalid_row_count
        flags.update(page.quality_flags)

        if page.records_total is not None:
            if records_total is None:
                records_total = page.records_total
            elif page.records_total != records_total:
                records_total = max(records_total, page.records_total)
                flags.add("records_total_changed")

        remaining = max_records - len(rows)
        if len(page.rows) > remaining:
            rows.extend(page.rows[:remaining])
            flags.add("max_records_reached")
            break

        rows.extend(page.rows)
        for row in page.rows:
            source_id = _optional_source_id(row.get("id"))
            if source_id is None:
                continue
            if source_id in seen_source_ids:
                duplicate_source_id_count += 1
            else:
                seen_source_ids.add(source_id)

        if page.has_more is False:
            complete = True
            break
        if page.has_more is True and source_count == 0:
            flags.add("empty_page_before_total")
            break
        if page.has_more is None and source_count < page_size:
            complete = True
            flags.add("completion_inferred_from_short_page")
            break
        if len(rows) >= max_records:
            flags.add("max_records_reached")
            break
    else:
        flags.add("max_pages_reached")

    if records_total is not None:
        if fetched_source_count < records_total:
            flags.add("fetched_count_below_records_total")
            complete = False
        elif fetched_source_count > records_total:
            flags.add("fetched_count_exceeds_records_total")

    if "records_total_changed" in flags:
        complete = False
    if duplicate_source_id_count:
        flags.add("duplicate_source_ids_observed")
    if invalid_row_count:
        flags.add("invalid_rows_ignored")

    return AEEPageCollection(
        rows=tuple(rows),
        records_total=records_total,
        pages_fetched=pages_fetched,
        fetched_source_count=fetched_source_count,
        invalid_row_count=invalid_row_count,
        duplicate_source_id_count=duplicate_source_id_count,
        complete=complete,
        quality_flags=tuple(sorted(flags)),
    )


def _optional_source_id(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None
