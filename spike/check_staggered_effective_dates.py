"""
조문별 시행일이 다른 법령에서
기간 찾기·특정 시점 고르기가 검색 시행일과 맞는지 확인한다.

재현 사례:
  소방시설 설치 및 관리에 관한 법률
  - 검색 API 시행일: 2024-12-01 / 문서번호 236977
  - 연혁에는 같은 문서에 2022-12-01 과 2024-12-01 이 함께 있음
  - 이른 날만 보면 기간 찾기 0건, 특정 시점은 엉뚱한 2023-07-04 판을 고름
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.law_source import (
    DatePeriod,
    find_version_effective_on,
    find_versions_effective_between,
    list_all_versions,
    search_laws,
)

LAW_NAME = "소방시설 설치 및 관리에 관한 법률"
PERIOD = DatePeriod(date(2024, 1, 1), date(2026, 12, 31))
EXPECTED_SEARCH_DATE = date(2024, 12, 1)
EXPECTED_VERSION_ID = "236977"


def report(label: str, is_ok: bool, detail: str = "") -> bool:
    mark = "OK  " if is_ok else "실패"
    print(f"  [{mark}] {label}" + (f"  -- {detail}" if detail else ""))
    return is_ok


def main() -> int:
    all_passed = True

    print("=== 1. 검색 ===")
    matches = [item for item in search_laws(LAW_NAME) if item.law_name == LAW_NAME]
    all_passed &= report("검색 결과 있음", bool(matches))
    if not matches:
        return 1

    law = matches[0]
    all_passed &= report(
        "검색 시행일",
        law.effective_date == EXPECTED_SEARCH_DATE,
        str(law.effective_date),
    )
    all_passed &= report(
        "검색 문서번호",
        law.version_id == EXPECTED_VERSION_ID,
        law.version_id,
    )

    print("\n=== 2. 연혁(목록용 대표일 = 이른 날, 현행 표시는 전체 시행일) ===")
    history = list_all_versions(law)
    target = next((item for item in history if item.version_id == EXPECTED_VERSION_ID), None)
    all_passed &= report("연혁에 해당 문서 있음", target is not None)
    if target is not None:
        all_passed &= report(
            "목록 대표 시행일은 이른 날(2022-12-01)",
            target.effective_date == date(2022, 12, 1),
            str(target.effective_date),
        )
        all_passed &= report(
            "현행 표시가 검색 문서에 붙는가",
            target.is_currently_in_effect,
            f"현행={target.is_currently_in_effect}",
        )

    wrong_current = next(
        (
            item
            for item in history
            if item.is_currently_in_effect and item.version_id != EXPECTED_VERSION_ID
        ),
        None,
    )
    all_passed &= report(
        "다른 문서에 현행이 붙지 않는가",
        wrong_current is None,
        str(wrong_current) if wrong_current else "",
    )

    print("\n=== 3. 기간 안의 개정본 ===")
    try:
        within = find_versions_effective_between(law, PERIOD)
        error_message = ""
    except Exception as error:  # noqa: BLE001 — 검증 스크립트에서 문구까지 보여 준다
        within = []
        error_message = str(error)

    all_passed &= report(
        "기간 안에 1건 이상",
        len(within) >= 1,
        error_message or f"{len(within)}건",
    )
    if within:
        matched = next(
            (item for item in within if item.version_id == EXPECTED_VERSION_ID),
            None,
        )
        all_passed &= report("기간 목록에 검색 문서 포함", matched is not None)
        if matched is not None:
            all_passed &= report(
                "표시 시행일은 기간 안 늦은 날(2024-12-01)",
                matched.effective_date == EXPECTED_SEARCH_DATE,
                str(matched.effective_date),
            )

    print("\n=== 4. 특정 시점 ===")
    try:
        picked_today = find_version_effective_on(law, date.today())
        all_passed &= report(
            "오늘 기준 문서번호",
            picked_today.version_id == EXPECTED_VERSION_ID,
            picked_today.version_id,
        )
        all_passed &= report(
            "오늘 기준 시행일 2024-12-01",
            picked_today.effective_date == EXPECTED_SEARCH_DATE,
            str(picked_today.effective_date),
        )
        all_passed &= report(
            "오늘 기준 현행 표시",
            picked_today.is_currently_in_effect,
        )
    except Exception as error:  # noqa: BLE001
        all_passed &= report("오늘 기준 판 고르기", False, str(error))

    try:
        # 2024-12-01 당일에도 검색과 같은 판이 잡혀야 한다.
        picked_on_day = find_version_effective_on(law, EXPECTED_SEARCH_DATE)
        all_passed &= report(
            "2024-12-01 기준 문서번호",
            picked_on_day.version_id == EXPECTED_VERSION_ID,
            picked_on_day.version_id,
        )
        all_passed &= report(
            "2024-12-01 기준 시행일",
            picked_on_day.effective_date == EXPECTED_SEARCH_DATE,
            str(picked_on_day.effective_date),
        )
    except Exception as error:  # noqa: BLE001
        all_passed &= report("2024-12-01 기준 판 고르기", False, str(error))

    try:
        # 2024 조문 시행 전: 기준일 이하인 날만 쓰고, 오류 없이 한 판을 고른다.
        picked_early = find_version_effective_on(law, date(2023, 1, 1))
        all_passed &= report(
            "2023-01-01 기준 시행일이 기준일 이하",
            picked_early.effective_date <= date(2023, 1, 1),
            str(picked_early.effective_date),
        )
    except Exception as error:  # noqa: BLE001
        all_passed &= report("2023-01-01 기준 판 고르기", False, str(error))

    print()
    print("모두 통과" if all_passed else "실패 있음")
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
