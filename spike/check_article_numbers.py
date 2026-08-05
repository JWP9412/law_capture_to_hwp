"""
조문 번호 파싱이 맞는지 확인한다. (한글·브라우저를 켜지 않는다)

인수인계에 적어 둔 입력 표기를 그대로 넣는다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.article_number import (
    ArticleNumber,
    build_article_range_label,
    parse_article_numbers,
)


def report(label: str, is_ok: bool, detail: str = "") -> bool:
    print(f"  [{'OK  ' if is_ok else '실패'}] {label}" + (f"  -- {detail}" if detail else ""))
    return is_ok


all_passed = True

print("=== 1. 단일·가지번호 ===")
cases = [
    ("32", [ArticleNumber(32)]),
    ("32의2", [ArticleNumber(32, 2)]),
    ("제32조의2", [ArticleNumber(32, 2)]),
    ("제32조", [ArticleNumber(32)]),
]
for text, expected in cases:
    got = parse_article_numbers(text)
    all_passed &= report(f"'{text}'", got == expected, f"{got} / 기대 {expected}")

print("\n=== 2. 범위·나열 ===")
all_passed &= report(
    "'1-3'",
    parse_article_numbers("1-3") == [ArticleNumber(1), ArticleNumber(2), ArticleNumber(3)],
)
all_passed &= report(
    "'1~3'",
    parse_article_numbers("1~3") == [ArticleNumber(1), ArticleNumber(2), ArticleNumber(3)],
)
all_passed &= report(
    "'32, 32의2'",
    parse_article_numbers("32, 32의2") == [ArticleNumber(32), ArticleNumber(32, 2)],
)
all_passed &= report(
    "'1, 3, 5-7'",
    parse_article_numbers("1, 3, 5-7")
    == [
        ArticleNumber(1),
        ArticleNumber(3),
        ArticleNumber(5),
        ArticleNumber(6),
        ArticleNumber(7),
    ],
)

print("\n=== 3. 잘못된 범위 안내 ===")
try:
    parse_article_numbers("32-2")
    all_passed &= report("'32-2' 가 막히는가", False, "오류 없이 통과함")
except ValueError as error:
    message = str(error)
    all_passed &= report(
        "'32-2' 가 막히는가",
        "32의2" in message and "적어주세요" in message,
        message,
    )

print("\n=== 4. 캡션용 표기 ===")
label_cases = [
    ([ArticleNumber(1)], "제1조"),
    ([ArticleNumber(32, 2)], "제32조의2"),
    ([ArticleNumber(1), ArticleNumber(2)], "제1, 2조"),
    ([ArticleNumber(1), ArticleNumber(2), ArticleNumber(3)], "제1조 내지 제3조"),
    ([ArticleNumber(1), ArticleNumber(5), ArticleNumber(9)], "제1, 5, 9조"),
    ([ArticleNumber(32), ArticleNumber(32, 2)], "제32조, 제32조의2"),
]
for articles, expected in label_cases:
    got = build_article_range_label(articles)
    all_passed &= report(expected, got == expected, got)

print("\n" + "=" * 58)
print("통과" if all_passed else "실패 — 위 목록을 보세요")
print("=" * 58)
sys.exit(0 if all_passed else 1)
