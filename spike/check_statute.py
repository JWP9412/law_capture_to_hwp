"""법령(법률·시행령)도 고시와 똑같이 동작하는지 확인한다."""
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

for query in ["공동주택관리법", "주택법"]:
    print("=" * 66)
    print(f"'{query}'")
    print("=" * 66)

    law = search_laws(query, LawSourceKind.STATUTE)[0]
    print(f"찾은 법령: {law}  (법령ID={law.law_id}, 문서번호={law.version_id})")

    versions = list_all_versions(law)
    print(f"\n  개정 이력 {len(versions)}개 (오래된 순, 최근 6개만 표시)")
    for version in versions[-6:]:
        mark = "   <= 현행" if version.is_currently_in_effect else ""
        print(f"    {version.effective_date}  {version.version_id:>8}  "
              f"{version.promulgation_label[:36]}{mark}")

    print("\n  시점별로 고른 판")
    for reference_date in [date(2025, 6, 1), date(2020, 1, 1)]:
        print(f"    {reference_date} -> {find_version_effective_on(law, reference_date)}")

    period = DatePeriod(date(2024, 1, 1), date(2026, 12, 31))
    in_period = find_versions_effective_between(law, period)
    print(f"\n  {period} 기간의 개정본 {len(in_period)}개")
    for version in in_period:
        print(f"    {version}")
    print()
