"""law_source.py 가 검색·개정 이력·시점별 판 고르기를 제대로 하는지 확인한다."""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import LawSourceKind
from core.law_source import (
    DatePeriod,
    find_version_effective_on,
    find_versions_effective_between,
    list_all_versions,
    search_laws,
)


def show_search(query: str) -> None:
    print(f"\n[검색] '{query}'")
    for result in search_laws(query):
        print(f"    {result}")


def show_history_and_selection(query: str) -> None:
    print(f"\n{'=' * 66}")
    print(f"'{query}' 상세")
    print("=" * 66)

    law = search_laws(query)[0]
    print(f"고른 법령: {law}")

    print("\n  -- 개정 이력 (오래된 순) --")
    for version in list_all_versions(law):
        current_mark = "   <= 현행" if version.is_currently_in_effect else ""
        print(f"    {version.effective_date}  {version.version_id:>14}  "
              f"{version.promulgation_label[:36]}{current_mark}")

    print("\n  -- 시점별로 고른 판 --")
    for reference_date in [date(2025, 6, 1), date(2021, 1, 1), date(2016, 1, 1)]:
        print(f"    {reference_date} 기준 -> {find_version_effective_on(law, reference_date)}")

    print("\n  -- 기간 안의 개정본 --")
    period = DatePeriod(date(2024, 1, 1), date(2026, 12, 31))
    print(f"    {period}")
    for version in find_versions_effective_between(law, period):
        print(f"      {version}")


show_search("하자판정기준")
show_search("공동주택관리법")

show_history_and_selection("하자판정기준")
