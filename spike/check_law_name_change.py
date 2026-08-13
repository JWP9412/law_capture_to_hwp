"""
법령·고시의 이름이 바뀐 것을 제대로 알아채는지 확인한다. (한글은 켜지 않는다)

**실제로 사용자가 겪은 문제다.**
「자동차압·과압조절형댐퍼의 성능시험기술기준」(시행 2009. 8. 24.)을 찾으려고
'과압조절' 로 검색했더니 「자동차압급기댐퍼의 성능인증 및 제품검사의 기술기준」
하나만 나와서 '검색이 안 된다' 고 여겼다.

실제로는 검색이 정상이었고 그 고시의 이름이 두 번 바뀌었을 뿐이다.
더 심각한 것은 캡션이었다. 옛 판 그림에 지금 이름이 찍혀서,
그림 속 문서 제목과 캡션이 서로 다른 이름이 되고 있었다.
서면에 그대로 들어가면 인용 오류가 된다.
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from core.article_number import ArticleNumber
from core.law_source import (
    detect_law_name_change,
    find_version_effective_on,
    list_all_versions,
    search_laws,
    was_found_by_former_name,
)
from core.models import ArticleCaptureTask, ArticleTextComparison
from core.version_series import build_caption, compare_article_text

all_passed = True


def report(label: str, is_ok: bool, detail: str = "") -> None:
    global all_passed
    all_passed &= is_ok
    print(f"  [{'OK  ' if is_ok else '실패'}] {label}" + (f"  -- {detail}" if detail else ""))


def find_law(query: str, exact_name: str | None = None):
    """검색 결과에서 원하는 것을 고른다. 이름을 주면 정확히 그것을 찾는다."""
    results = search_laws(query)
    if exact_name is None:
        return results[0]
    return next(item for item in results if item.law_name == exact_name)


print("=" * 66)
print("이름이 바뀐 법령·고시를 알아채는지 확인 (한글 안 켬)")
print("=" * 66)

# ---------------------------------------------------------------- 1
print("\n1. 고시 — 사용자가 실제로 겪은 경우 (이름이 두 번 바뀜)")
damper = find_law("과압조절")
damper_versions = list_all_versions(damper)
damper_change = detect_law_name_change(damper_versions)

report(
    "옛 이름으로 검색한 것을 알아채는가",
    was_found_by_former_name("과압조절", damper.law_name),
    f"'과압조절' -> '{damper.law_name[:28]}…'",
)
report("이름이 바뀐 것을 알아채는가", damper_change.has_changed)
report(
    "이름이 3가지였는가",
    damper_change.changed_count == 3,
    f"{damper_change.changed_count}가지",
)
report(
    "가장 오래된 판의 이름이 맞는가",
    damper_change.oldest_name == "자동차압·과압조절형댐퍼의 성능시험기술기준",
    damper_change.oldest_name,
)

# ---------------------------------------------------------------- 2
print("\n2. 사용자가 찾던 바로 그 판 (시행 2009. 8. 24.)")
wanted = find_version_effective_on(damper, date(2009, 8, 24))
report("문서 번호가 맞는가", wanted.version_id == "2000000009577", wanted.version_id)
report(
    "당시 이름을 읽어냈는가",
    wanted.historical_law_name == "자동차압·과압조절형댐퍼의 성능시험기술기준",
    wanted.historical_law_name,
)
report("지금 이름과 다르다고 표시되는가", wanted.has_different_name_now)
report(
    "캡션에 쓸 이름이 '당시 이름' 인가",
    wanted.display_law_name == wanted.historical_law_name,
    wanted.display_law_name,
)

# ---------------------------------------------------------------- 3
print("\n3. 캡션에 당시 이름이 들어가는가 (이것이 핵심)")
task = ArticleCaptureTask(
    version=wanted,
    article_numbers=[ArticleNumber(1)],
    underline_phrases=[],
    target_hwp_path=None,
    insertion_mode=config.InsertionMode.APPEND_TO_END,
    should_add_caption=True,
    should_add_border=True,
)
caption = build_caption(task, ArticleTextComparison(is_same=False, similarity_ratio=0.0))
report(
    "캡션이 당시 이름으로 시작하는가",
    caption.startswith("자동차압·과압조절형댐퍼의 성능시험기술기준"),
    caption,
)
report("캡션에 지금 이름이 섞이지 않았는가", "급기댐퍼" not in caption)

# ---------------------------------------------------------------- 4
print("\n4. 법령(법률)에서도 되는가 — 주택법은 옛날에 주택건설촉진법이었다")
housing = find_law("주택법", exact_name="주택법")
housing_versions = list_all_versions(housing)
housing_change = detect_law_name_change(housing_versions)
report("이름이 바뀐 것을 알아채는가", housing_change.has_changed)
report(
    "가장 오래된 판이 '주택건설촉진법' 인가",
    housing_change.oldest_name == "주택건설촉진법",
    f"{housing_change.oldest_name} (시행 {housing_versions[0].effective_date})",
)
report("지금 이름이 '주택법' 인가", housing_change.current_name == "주택법")
report(
    "개정본이 아주 많아도 이름을 다 읽었는가",
    all(version.historical_law_name for version in housing_versions),
    f"{len(housing_versions)}개 판 전부",
)

# ---------------------------------------------------------------- 5
print("\n5. 거짓 양성이 없는가 — 이름이 안 바뀐 법령에 알림이 뜨면 안 된다")
for name in ("공동주택관리법", "건축법"):
    law = find_law(name, exact_name=name)
    change = detect_law_name_change(list_all_versions(law))
    report(f"{name} — 알림이 안 뜨는가", not change.has_changed, f"{change.changed_count}가지")

report(
    "'주택법' 은 옛 이름 검색이 아니라고 보는가",
    not was_found_by_former_name("주택법", "주택법"),
)

# ---------------------------------------------------------------- 6
print("\n6. 띄어쓰기만 다른 것을 개명으로 착각하지 않는가")
# 옛 법령은 이름을 붙여 썼다: 「주택건설기준등에관한규정」 -> 「주택건설기준 등에 관한 규정」
standard = find_law("주택건설기준 등에 관한 규정", exact_name="주택건설기준 등에 관한 규정")
standard_versions = list_all_versions(standard)
standard_change = detect_law_name_change(standard_versions)
old_spelling = [
    version
    for version in standard_versions
    if version.historical_law_name == "주택건설기준등에관한규정"
]
report(
    "붙여 쓴 옛 표기가 실제로 있는가 (시험 전제)",
    bool(old_spelling),
    f"{len(old_spelling)}개 판",
)
report("띄어쓰기 차이는 알림을 띄우지 않는가", not standard_change.has_changed)
report(
    "그래도 캡션에는 당시 표기 그대로 들어가는가",
    bool(old_spelling) and old_spelling[0].display_law_name == "주택건설기준등에관한규정",
    old_spelling[0].display_law_name if old_spelling else "",
)

# ---------------------------------------------------------------- 7
print("\n7. 내용이 얼마나 닮았는지 재는가")
same_text = "제1조(목적) 이 기준은 공동주택의 하자를 판정함을 목적으로 한다."
tweaked_text = "제1조(목적) 이 기준은 공동주택의 하자를 판정함을 목적으로 함."
unrelated_text = "제99조(벌칙) 전혀 다른 내용이 여기에 들어간다. 아주 무관한 문장이다."

exactly_same = compare_article_text(same_text, same_text)
report("완전히 같으면 '동일'", exactly_same.is_same and exactly_same.similarity_ratio == 1.0)

spaced_out = compare_article_text(same_text, same_text.replace(" ", "  "))
report("띄어쓰기만 다르면 '동일'", spaced_out.is_same)

nearly_same = compare_article_text(same_text, tweaked_text)
report(
    "조금 다르면 '유사' 로 알리는가",
    nearly_same.is_similar_but_not_same,
    f"{nearly_same.similarity_percent}% 유사",
)

quite_different = compare_article_text(same_text, unrelated_text)
report(
    "많이 다르면 알리지 않는가",
    not quite_different.is_similar_but_not_same and not quite_different.is_same,
    f"{quite_different.similarity_percent}%",
)

first_version = compare_article_text(same_text, "")
report("앞 판이 없으면 견주지 않는가", not first_version.is_same)

print("\n8. 캡션 꼬리표가 제대로 붙는가")
report(
    "'앞 개정안과 동일'",
    build_caption(task, ArticleTextComparison(True, 1.0)).endswith("(앞 개정안과 동일)"),
)
report(
    "'앞 개정안과 97% 유사'",
    build_caption(task, ArticleTextComparison(False, 0.97)).endswith("(앞 개정안과 97% 유사)"),
)
report(
    "많이 다르면 꼬리표 없음",
    not build_caption(task, ArticleTextComparison(False, 0.30)).endswith(")")
    or "유사" not in build_caption(task, ArticleTextComparison(False, 0.30)),
)

print("\n" + "=" * 66)
print("통과 — 이름이 바뀐 것을 알아챕니다" if all_passed else "실패 — 위 목록을 보세요")
print("=" * 66)
sys.exit(0 if all_passed else 1)
