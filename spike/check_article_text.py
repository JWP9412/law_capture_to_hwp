"""조문 내용을 글자로 제대로 가져오는지 확인한다. (미리보기의 재료)"""
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import LawSourceKind
from core.article_number import ArticleNumber, parse_article_numbers
from core.article_text import fetch_article_text
from core.errors import ArticleNotFoundOnPageError
from core.law_source import find_version_effective_on, search_laws


def report(label: str, is_ok: bool, detail: str = "") -> bool:
    print(f"  [{'OK  ' if is_ok else '실패'}] {label}" + (f"  -- {detail}" if detail else ""))
    return is_ok


all_passed = True

print("=== 1. 기본 사례 ===")
CASES = [
    ("하자판정기준", LawSourceKind.ADMINISTRATIVE_RULE, date(2025, 6, 1),
     [[ArticleNumber(1)], [ArticleNumber(7)], [ArticleNumber(10)]]),
    ("공동주택관리법", LawSourceKind.STATUTE, date(2025, 6, 1),
     [[ArticleNumber(39)]]),
]

for law_name, kind, reference_date, article_groups in CASES:
    law = search_laws(law_name, kind)[0]
    version = find_version_effective_on(law, reference_date)
    print(f"\n--- {version} ---")

    for articles in article_groups:
        started_at = time.time()
        try:
            text = fetch_article_text(version, articles)
        except Exception as error:
            print(f"  [실패] {articles}: {error}")
            all_passed = False
            continue

        elapsed = time.time() - started_at
        lines = text.splitlines()
        label = articles[0].label
        print(f"  [OK  ] {label}: {len(lines)}줄 {len(text)}자 ({elapsed:.1f}초)")
        for line in lines[:3]:
            print(f"          {line[:64]}")

print("\n=== 2. 다중 조문·가지번호 ===")
# 주택건설기준 등에 관한 규정 — 제32조의2 가 실제로 있는 법령
housing = search_laws("주택건설기준 등에 관한 규정", LawSourceKind.STATUTE)[0]
housing_version = find_version_effective_on(housing, date(2025, 6, 1))
print(f"--- {housing_version} ---")

branch_alone = fetch_article_text(housing_version, [ArticleNumber(32, 2)])
all_passed &= report(
    "제32조의2 단독",
    "제32조의2" in branch_alone and "제32조(" not in branch_alone.splitlines()[0],
    branch_alone.splitlines()[0][:50],
)

both = fetch_article_text(
    housing_version, [ArticleNumber(32), ArticleNumber(32, 2)]
)
all_passed &= report(
    "제32조 + 제32조의2",
    "제32조(" in both and "제32조의2" in both,
)

article_32_only = fetch_article_text(housing_version, [ArticleNumber(32)])
# 제32조만 요청했는데 제32조의2 가 본문에 섞이면 안 된다.
stray_branch = any(
    line.startswith("제32조의2") for line in article_32_only.splitlines()
)
all_passed &= report(
    "제32조 단독에 제32조의2 가 안 딸려오는가",
    not stray_branch,
    article_32_only.splitlines()[0][:50],
)

print("\n=== 3. 고시 다중·범위 ===")
defect = search_laws("하자판정기준", LawSourceKind.ADMINISTRATIVE_RULE)[0]
defect_version = find_version_effective_on(defect, date(2025, 6, 1))
comma_text = fetch_article_text(defect_version, parse_article_numbers("1, 2"))
range_text = fetch_article_text(defect_version, parse_article_numbers("1-2"))
# 1-3 은 제1~3조. 1,2 와는 다르므로 1-2 로 비교한다.
all_passed &= report(
    "'1, 2' 와 '1-2' 결과가 같은가",
    comma_text == range_text,
)
all_passed &= report(
    "제1조·제2조가 모두 들어갔는가",
    "제1조" in comma_text and "제2조" in comma_text,
)

range_3 = fetch_article_text(defect_version, parse_article_numbers("1-3"))
all_passed &= report(
    "'1-3' 에 제3조가 들어갔는가",
    "제3조" in range_3,
)

print("\n=== 4. 없는 조문 ===")
try:
    fetch_article_text(defect_version, [ArticleNumber(9999)])
    all_passed &= report("없는 조문이 막히는가", False)
except ArticleNotFoundOnPageError as error:
    all_passed &= report("없는 조문이 막히는가", True, str(error))

print("\n=== 5. 전체보기 ===")
from core.article_number import (
    append_article_to_entry_text,
    find_article_covering_character_offset,
)
from core.article_text import fetch_full_law_text

# 고시 전체
started_at = time.time()
defect_full = fetch_full_law_text(defect_version)
elapsed = time.time() - started_at
article_1 = fetch_article_text(defect_version, [ArticleNumber(1)])
all_passed &= report(
    "고시 전체보기가 조문 미리보기보다 긴가",
    len(defect_full) > len(article_1),
    f"전체 {len(defect_full)}자 / 제1조 {len(article_1)}자 ({elapsed:.1f}초)",
)
all_passed &= report("고시 전체에 제1조·제7조가 있는가", "제1조" in defect_full and "제7조" in defect_full)

# 법령 전체 (JO 생략)
management = search_laws("공동주택관리법", LawSourceKind.STATUTE)[0]
management_version = find_version_effective_on(management, date(2025, 6, 1))
started_at = time.time()
try:
    statute_full = fetch_full_law_text(management_version)
    elapsed = time.time() - started_at
    article_39 = fetch_article_text(management_version, [ArticleNumber(39)])
    all_passed &= report(
        "법령 전체보기가 조문 미리보기보다 긴가",
        len(statute_full) > len(article_39),
        f"전체 {len(statute_full)}자 / 제39조 {len(article_39)}자 ({elapsed:.1f}초)",
    )
    all_passed &= report(
        "법령 전체에 제39조가 있는가",
        "제39조" in statute_full,
    )
except Exception as error:
    all_passed &= report("법령 전체보기", False, str(error))
    statute_full = ""

print("\n=== 6. 전체보기 드래그용 조문 추정 ===")
sample = (
    "제1조(목적) 이 법은 목적을 정한다.\n"
    "① 첫째 항입니다.\n"
    "제32조의2(특례) 가지번호 조문입니다.\n"
    "본문 내용이 이어집니다.\n"
)
offset_in_article_1 = sample.index("첫째")
offset_in_branch = sample.index("본문 내용")
found_1 = find_article_covering_character_offset(sample, offset_in_article_1)
found_branch = find_article_covering_character_offset(sample, offset_in_branch)
all_passed &= report(
    "제1조 본문 위치 추정",
    found_1 == ArticleNumber(1),
    str(found_1),
)
all_passed &= report(
    "제32조의2 본문 위치 추정",
    found_branch == ArticleNumber(32, 2),
    str(found_branch),
)
all_passed &= report(
    "조문 칸에 추가",
    append_article_to_entry_text("39", ArticleNumber(40)) == "39,40",
)
all_passed &= report(
    "같은 조문은 중복 안 함",
    append_article_to_entry_text("39", ArticleNumber(39)) == "39",
)
all_passed &= report(
    "가지번호 표기",
    append_article_to_entry_text("", ArticleNumber(32, 2)) == "32의2",
)

print("\n=== 7. 원문 URL ===")
all_passed &= report(
    "고시 URL",
    "admRulLsInfoP.do" in defect_version.detail_page_url
    and f"admRulSeq={defect_version.version_id}" in defect_version.detail_page_url,
    defect_version.detail_page_url,
)
all_passed &= report(
    "법령 URL 에 시행일",
    "lsInfoP.do" in management_version.detail_page_url
    and "efYd=" in management_version.detail_page_url,
    management_version.detail_page_url,
)

print("\n" + "=" * 58)
print("통과" if all_passed else "실패 — 위 목록을 보세요")
sys.exit(0 if all_passed else 1)
