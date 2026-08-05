"""
조문 번호 표기와 입력 해석을 담당한다.

조문 번호는 숫자 하나가 아니다. '제32조의2' 처럼 가지번호가 붙는 조문이
흔하고(「주택건설기준 등에 관한 규정」에만 26개), 서면에는 조문 여러 개를
한 장에 넣는 경우도 있다. 그래서 번호와 가지번호를 함께 다루고,
사람이 적는 여러 표기를 같은 자료로 해석한다.

입력 예:
  32          -> 제32조
  32의2       -> 제32조의2
  제32조의2   -> 제32조의2 (사이트에서 복사해 붙여넣기)
  1-3 / 1~3   -> 제1조부터 제3조까지
  32, 32의2   -> 제32조와 제32조의2
  32-2        -> 범위로 읽히지만 앞뒤가 뒤바뀜 → 안내 오류
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class ArticleNumber:
    """
    조문 번호. '제32조의2' 처럼 가지번호가 붙는 조문이 있어 두 값으로 다룬다.

    branch 가 0 이면 가지번호가 없는 보통 조문이다.
    """

    number: int
    branch: int = 0

    @property
    def label(self) -> str:
        if self.branch:
            return f"제{self.number}조의{self.branch}"
        return f"제{self.number}조"

    @property
    def has_branch(self) -> bool:
        return self.branch != 0


# 한 칸에 올 수 있는 표기. '제'·'조' 는 있어도 없어도 된다.
#   32 / 제32조 / 32의2 / 제32조의2
SINGLE_ARTICLE_PATTERN = re.compile(
    r"^제?\s*(\d+)\s*조?(?:의\s*(\d+))?$"
)

# 범위 표기. 가지번호 없는 조문만 범위로 받는다.
#   1-3 / 1~3
RANGE_PATTERN = re.compile(r"^제?\s*(\d+)\s*조?\s*[-~]\s*제?\s*(\d+)\s*조?$")


def parse_article_numbers(text: str) -> list[ArticleNumber]:
    """
    사람이 적은 조문 번호 칸을 ArticleNumber 목록으로 바꾼다.

    콤마로 나열하거나 범위·가지번호를 섞어 써도 된다.
    알아들을 수 없으면 ValueError 에 한국어 안내를 담아 올린다.
    """
    cleaned = text.strip()
    if not cleaned:
        raise ValueError(
            "조문 번호를 넣어주세요. (예: 1 또는 1, 2 또는 1-3 또는 32의2)"
        )

    parts = [part.strip() for part in cleaned.replace("，", ",").split(",") if part.strip()]
    if not parts:
        raise ValueError(
            "조문 번호를 넣어주세요. (예: 1 또는 1, 2 또는 1-3 또는 32의2)"
        )

    result: list[ArticleNumber] = []
    for part in parts:
        result.extend(_parse_one_part(part))

    # 같은 조문을 두 번 적으면 한 번만 남긴다. 순서는 유지한다.
    unique: list[ArticleNumber] = []
    for article in result:
        if article not in unique:
            unique.append(article)
    return unique


def _parse_one_part(part: str) -> list[ArticleNumber]:
    """콤마로 나뉜 한 조각을 해석한다. 범위면 여러 개, 아니면 하나."""
    range_match = RANGE_PATTERN.match(part)
    if range_match:
        start = int(range_match.group(1))
        end = int(range_match.group(2))
        if start > end:
            # 32-2 처럼 적으면 범위로 읽혀 앞뒤가 뒤바뀐다.
            # 조용히 엉뚱하게 처리하지 않고, 가지번호를 뜻했는지 안내한다.
            raise ValueError(
                f"'{part}' 는 범위로 읽히는데 시작({start})이 끝({end})보다 큽니다. "
                f"제{start}조의{end} 를 뜻한다면 '{start}의{end}' 로 적어주세요."
            )
        return [ArticleNumber(number=value) for value in range(start, end + 1)]

    single_match = SINGLE_ARTICLE_PATTERN.match(part)
    if single_match:
        number = int(single_match.group(1))
        branch = int(single_match.group(2) or 0)
        return [ArticleNumber(number=number, branch=branch)]

    raise ValueError(
        f"'{part}' 를 조문 번호로 알아듣지 못했습니다. "
        f"예: 1 또는 1, 2 또는 1-3 또는 32의2"
    )


def build_article_range_label(article_numbers: list[ArticleNumber]) -> str:
    """
    캡션·화면에 넣을 조문 표기를 만든다.

    규칙 (서면 인용이라 정확해야 한다):
      1개                         -> 제N조 / 제N조의M
      2개                         -> 제N, M조  (가지번호 섞이면 온전히 나열)
      3개 이상 + 가지번호 없이 연속 -> 제N조 내지 제M조
      그 밖                       -> 전부 나열 (제1, 5, 9조 또는 제32조, 제32조의2)

    떨어진 조문을 '내지' 로 묶으면 중간 조문까지 인용한 것처럼 읽혀
    서면에서 사실과 다른 표기가 되므로, 이어진 경우에만 '내지' 를 쓴다.
    가지번호가 하나라도 있으면 줄여 쓰지 않는다.
    """
    if not article_numbers:
        raise ValueError("조문 번호가 비어 있습니다.")

    if len(article_numbers) == 1:
        return article_numbers[0].label

    has_any_branch = any(article.has_branch for article in article_numbers)

    if has_any_branch:
        # 가지번호가 섞이면 온전히 나열한다. '제32, 32조' 처럼 줄이면 안 된다.
        return ", ".join(article.label for article in article_numbers)

    numbers = [article.number for article in article_numbers]
    if len(numbers) == 2:
        return f"제{numbers[0]}, {numbers[1]}조"

    if _is_consecutive(numbers):
        return f"제{numbers[0]}조 내지 제{numbers[-1]}조"

    joined = ", ".join(str(value) for value in numbers)
    return f"제{joined}조"


def _is_consecutive(numbers: list[int]) -> bool:
    """번호가 빠짐없이 이어지는지 본다. (1,2,3 → True / 1,3,5 → False)"""
    return all(
        numbers[index] + 1 == numbers[index + 1]
        for index in range(len(numbers) - 1)
    )


def article_numbers_as_key(
    article_numbers: list[ArticleNumber],
) -> tuple[ArticleNumber, ...]:
    """개정본 비교 등에서 조문 조합을 키로 쓸 때 쓰는 변하지 않는 묶음."""
    return tuple(article_numbers)


def format_article_for_entry(article: ArticleNumber) -> str:
    """
    조문 번호 입력칸에 넣을 짧은 표기.

    사람이 직접 적는 형식과 같게 맞춘다. (예: 39 / 32의2)
    """
    if article.branch:
        return f"{article.number}의{article.branch}"
    return str(article.number)


def append_article_to_entry_text(
    current_text: str, article: ArticleNumber
) -> str:
    """
    조문 번호 칸 글자에 조문 하나를 덧붙인다.

    이미 같은 조문이 있으면 그대로 둔다.
    칸이 비어 있으면 그 조문만 넣고, 있으면 콤마로 이어 붙인다.
    """
    cleaned = current_text.strip()
    if not cleaned:
        return format_article_for_entry(article)

    try:
        existing = parse_article_numbers(cleaned)
    except ValueError:
        # 칸에 이상한 값이 있으면 덮어쓰지 않고, 뒤에 콤마로만 덧붙인다.
        return f"{cleaned},{format_article_for_entry(article)}"

    if article in existing:
        return cleaned

    return f"{cleaned},{format_article_for_entry(article)}"


# 본문에서 조문 제목 줄을 찾을 때 쓴다.
# article_text 와 같은 규칙이어야 전체보기 드래그 추정이 맞는다.
ARTICLE_HEADING_PATTERN = re.compile(r"^제\s*(\d+)\s*조(?:의\s*(\d+))?")


def find_article_covering_character_offset(
    full_text: str, character_offset: int
) -> ArticleNumber | None:
    """
    본문에서 글자 위치가 속한 조문 번호를 찾는다.

    전체보기에서 드래그한 뒤 '어느 조인지' 를 자동으로 채울 때 쓴다.
    선택 시작 위치보다 앞쪽을 위로 훑어, 가장 가까운 조 제목 줄을 고른다.

    character_offset 은 줄바꿈을 포함한 글자 위치(0부터)다.
    """
    if character_offset < 0:
        character_offset = 0
    if character_offset > len(full_text):
        character_offset = len(full_text)

    prefix = full_text[:character_offset]
    lines = prefix.splitlines()
    # 선택 위치가 줄 한가운데여도, 그 줄 앞부분까지는 이미 prefix 에 들어 있다.
    # 줄 단위로 뒤에서부터 조 제목을 찾는다.
    for line in reversed(lines):
        heading = _read_heading_from_line(line.strip())
        if heading is not None:
            return heading
    return None


def _read_heading_from_line(line: str) -> ArticleNumber | None:
    """줄이 조문 제목이면 번호·가지번호를 돌려주고, 아니면 None."""
    matched = ARTICLE_HEADING_PATTERN.match(line)
    if not matched:
        return None
    return ArticleNumber(
        number=int(matched.group(1)),
        branch=int(matched.group(2) or 0),
    )
