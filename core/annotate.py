"""
받아온 조문 PDF 에 빨간 밑줄을 긋고, 필요한 부분만 잘라 그림으로 만든다.

두 가지 일을 한다.
  1) 지정한 문구에 빨간 밑줄 긋기
  2) 머리말·꼬리말을 뺀 본문만 잘라내어 그림 파일로 저장하기
"""
import re
from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF - PDF 를 읽고 그리는 도구

import config
from core.errors import EmptyCaptureAreaError, UnderlinePhraseNotFoundError

# 띄어쓰기만 다른 문구도 찾아주기 위해, 비교 전에 공백을 모두 지울 때 쓴다.
WHITESPACE_PATTERN = re.compile(r"\s+")

# 조문이 시작되는 줄인지 알아보는 규칙. 예: "제39조(하자심사…)", "제32조의2(…)"
# 이 앞의 줄들(법령 제목·시행일·소관부처)은 개정본 비교에서 빼야 한다.
ARTICLE_START_PATTERN = re.compile(r"^제\s*\d+\s*조")

# 모양만 다르고 사실상 같은 글자들을 하나로 통일하는 표.
#
# 왜 필요한가: 같은 조문인데도 어디서 가져오느냐에 따라 따옴표 모양이 다르다.
# PDF 에는 둥근따옴표(“ ”)가, 법제처 자료에는 곧은따옴표(" ")가 들어있다.
# 미리보기에서 문구를 골라 밑줄을 치려 할 때 이것 때문에 못 찾는 일이 생긴다.
# 눈으로는 같은 글자이므로 같은 것으로 취급한다.
#
# 한 글자를 한 글자로만 바꾼다. 길이가 달라지면 글자 위치 계산이 어긋나기 때문이다.
SIMILAR_CHARACTERS = str.maketrans(
    {
        "“": '"',  # 왼쪽 둥근 큰따옴표
        "”": '"',  # 오른쪽 둥근 큰따옴표
        "„": '"',
        "‟": '"',
        "‘": "'",  # 왼쪽 둥근 작은따옴표
        "’": "'",  # 오른쪽 둥근 작은따옴표
        "‚": "'",
        "‛": "'",
        "‐": "-",  # 여러 가지 붙임표·줄표
        "‑": "-",
        "‒": "-",
        "–": "-",
        "—": "-",
        "·": "ㆍ",  # 가운뎃점을 법령에서 쓰는 'ㆍ' 로 통일
        "•": "ㆍ",
    }
)


# 미리보기에서 드래그할 때 붙는 꼬리표. 예: "균열 [2번째]"
# 같은 문구가 여러 번 나올 때 어느 자리에만 밑줄을 그을지 가리킨다.
OCCURRENCE_MARKER_PATTERN = re.compile(r"^(.*?)\s*\[(\d+)번째\]\s*$")


def underline_and_capture(
    pdf_path: Path, underline_phrases: list[str], first_image_path: Path
) -> list[Path]:
    """
    PDF 에 밑줄을 긋고 본문 부분만 그림으로 잘라낸다. 쪽마다 그림 하나씩 만든다.

    **쪽이 여러 개인 경우가 흔하다.** 「주택법」 제2조(정의)처럼 긴 조문은
    PDF 가 3쪽까지 나온다. 예전에는 첫 쪽만 그림으로 만들고 나머지를 조용히
    버렸는데, 조문 뒷부분이 서면에서 통째로 빠지는데도 아무 표시가 없어
    잘린 줄 모르고 쓰게 되는 문제가 있었다.

    밑줄 칠 문구는 **모든 쪽에서** 찾는다. 어느 쪽에도 없을 때만 오류를 낸다.
    (문구가 둘째 쪽에 있다고 실패하면 안 된다)

    문구 끝에 " [N번째]" 가 붙어 있으면 그 순번의 자리에만 밑줄을 긋는다.
    없으면 지금처럼 나오는 자리마다 모두 긋는다.

    돌려주는 것은 만들어진 그림들의 목록이다. 한 쪽이면 하나만 들어있다.
    """
    document = fitz.open(pdf_path)
    try:
        _draw_underlines_on_all_pages(document, underline_phrases, pdf_path)
        return _capture_all_pages(document, first_image_path, pdf_path)
    finally:
        document.close()


def _draw_underlines_on_all_pages(
    document: fitz.Document, underline_phrases: list[str], pdf_path: Path
) -> None:
    """문구마다 모든 쪽을 뒤져 밑줄을 긋는다. 어느 쪽에도 없으면 오류를 낸다."""
    for phrase in underline_phrases:
        phrase_text, occurrence_index = _parse_occurrence_marker(phrase)
        was_found_somewhere = False
        seen_count = 0

        for page in document:
            for areas in _find_all_occurrences(page, phrase_text):
                seen_count += 1
                # 순번이 없으면 전부 긋고, 있으면 그 순번만 긋는다.
                if occurrence_index is None or seen_count == occurrence_index:
                    for text_area in areas:
                        _draw_underline_below_text(page, text_area)
                    was_found_somewhere = True

        if not was_found_somewhere:
            raise UnderlinePhraseNotFoundError(phrase, pdf_path)


def _parse_occurrence_marker(phrase: str) -> tuple[str, int | None]:
    """
    "균열 [2번째]" → ("균열", 2). 꼬리표가 없으면 순번은 None.

    사용자가 밑줄 칸에 직접 고쳐 쓸 수 있도록, 이 형태 자체가 저장 형식이다.
    """
    matched = OCCURRENCE_MARKER_PATTERN.match(phrase.strip())
    if not matched:
        return phrase, None
    return matched.group(1).strip(), int(matched.group(2))


def _capture_all_pages(
    document: fitz.Document, first_image_path: Path, pdf_path: Path
) -> list[Path]:
    """쪽마다 본문 부분을 잘라 그림으로 저장한다."""
    first_image_path.parent.mkdir(parents=True, exist_ok=True)
    saved_paths: list[Path] = []

    for page_index, page in enumerate(document):
        capture_area = find_content_area(page)
        if capture_area.is_empty:
            continue  # 빈 쪽은 건너뛴다 (마지막에 여백만 남는 경우가 있다)

        image_path = _build_page_image_path(first_image_path, page_index)
        page.get_pixmap(dpi=config.CAPTURE_RESOLUTION_IN_DPI, clip=capture_area).save(
            image_path
        )
        saved_paths.append(image_path)

    if not saved_paths:
        raise EmptyCaptureAreaError(pdf_path)

    return saved_paths


def _build_page_image_path(first_image_path: Path, page_index: int) -> Path:
    """
    쪽마다 다른 파일 이름을 만든다.

    첫 쪽은 원래 이름을 그대로 쓴다. 한 쪽짜리 조문이 대부분이므로
    쓸데없이 '_1쪽' 이 붙지 않게 하기 위해서다.
    """
    if page_index == 0:
        return first_image_path
    return first_image_path.with_name(
        f"{first_image_path.stem}_{page_index + 1}쪽{first_image_path.suffix}"
    )


def find_text_areas(
    page: fitz.Page, phrase: str, occurrence_index: int | None = None
) -> list[fitz.Rect]:
    """
    페이지에서 문구가 놓인 자리들을 찾는다.

    한 문구가 여러 자리로 나오는 경우가 있다.
    긴 문구는 종이 폭에 맞춰 줄바꿈되면서 두세 줄에 걸치는데,
    그러면 줄마다 자리가 하나씩 생긴다. (그래서 밑줄도 줄마다 따로 그어야 한다)

    occurrence_index 를 주면 (1부터) 그 순번의 자리만 돌려준다.
    한 자리에 여러 줄이 걸치면 그 줄들의 사각형이 함께 나온다.
    None 이면 모든 자리의 사각형을 평평하게 이어 붙인다.
    """
    occurrences = _find_all_occurrences(page, phrase)
    if occurrence_index is not None:
        if occurrence_index < 1 or occurrence_index > len(occurrences):
            return []
        return list(occurrences[occurrence_index - 1])

    flat: list[fitz.Rect] = []
    for areas in occurrences:
        flat.extend(areas)
    return flat


def _find_all_occurrences(page: fitz.Page, phrase: str) -> list[list[fitz.Rect]]:
    """
    문구가 나오는 자리들을 'occurrence' 단위로 모은다.

    한 occurrence 는 한 줄이면 사각형 하나, 여러 줄에 걸치면 줄마다 하나씩이다.
    """
    exact_matches = page.search_for(phrase)
    if exact_matches:
        # 한 줄 안에 들어있는 문구. 리스트의 각 항목이 한 번 나온 것이다.
        return [[area] for area in exact_matches]

    return _find_all_across_lines(page, phrase)


@dataclass(frozen=True)
class _PlacedCharacter:
    """페이지에 놓인 글자 하나와 그 자리."""

    letter: str
    line_index: int
    area: fitz.Rect


def _find_across_lines(page: fitz.Page, phrase: str) -> list[fitz.Rect]:
    """호환용. 첫 번째 occurrence 의 줄별 사각형만 돌려준다."""
    occurrences = _find_all_across_lines(page, phrase)
    return list(occurrences[0]) if occurrences else []


def _find_all_across_lines(page: fitz.Page, phrase: str) -> list[list[fitz.Rect]]:
    """
    여러 줄에 걸친 문구를 모두 찾아, occurrence 마다 줄별 사각형 목록을 만든다.

    PDF 는 종이 폭에 맞춰 줄을 바꾸기 때문에, 원문에서 한 문장이던 것이
    PDF 에서는 두세 줄로 나뉘어 있다. 그래서 문장을 통째로 찾으면 실패한다.

    그래서 글자 단위로 접근한다.
      1) 페이지의 모든 글자를 순서대로 모으고, 각 글자가 몇 번째 줄인지 기억한다
      2) 띄어쓰기를 없앤 글자들을 이어 하나의 긴 문자열로 만든다
      3) 찾을 문구도 띄어쓰기를 없애고, 그 문자열 안에서 위치를 모두 찾는다
      4) 걸리는 글자들을 줄별로 나눠, 줄마다 왼쪽끝~오른쪽끝 사각형을 만든다
    """
    phrase_to_find = _normalize(phrase)
    if not phrase_to_find:
        return []

    characters = _collect_characters_without_spaces(page)
    page_text = "".join(character.letter for character in characters)

    occurrences: list[list[fitz.Rect]] = []
    search_from = 0
    while True:
        found_at = page_text.find(phrase_to_find, search_from)
        if found_at < 0:
            break
        matched = characters[found_at : found_at + len(phrase_to_find)]
        occurrences.append(_group_into_line_areas(matched))
        search_from = found_at + 1

    return occurrences


def _normalize(text: str) -> str:
    """비교하기 좋게 다듬는다. 띄어쓰기를 없애고, 모양만 다른 글자를 통일한다."""
    return WHITESPACE_PATTERN.sub("", text).translate(SIMILAR_CHARACTERS)


def _collect_characters_without_spaces(page: fitz.Page) -> list[_PlacedCharacter]:
    """
    페이지의 글자를 순서대로 모은다. 띄어쓰기는 뺀다.

    'rawdict' 로 읽으면 글자 하나하나의 자리까지 알려준다.
    줄 번호를 함께 기억해 두어야 나중에 줄별로 나눌 수 있다.
    """
    characters: list[_PlacedCharacter] = []
    line_index = 0

    for block in page.get_text("rawdict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                for character in span["chars"]:
                    if character["c"].isspace():
                        continue
                    characters.append(
                        _PlacedCharacter(
                            letter=character["c"].translate(SIMILAR_CHARACTERS),
                            line_index=line_index,
                            area=fitz.Rect(character["bbox"]),
                        )
                    )
            line_index += 1

    return characters


def _group_into_line_areas(characters: list[_PlacedCharacter]) -> list[fitz.Rect]:
    """찾아낸 글자들을 줄별로 묶어, 줄마다 하나의 사각형으로 만든다."""
    areas: list[fitz.Rect] = []
    current_line_index: int | None = None
    current_area = fitz.Rect()

    for character in characters:
        if character.line_index != current_line_index:
            if current_line_index is not None:
                areas.append(current_area)
            current_line_index = character.line_index
            current_area = fitz.Rect(character.area)
        else:
            current_area |= character.area

    if current_line_index is not None:
        areas.append(current_area)

    return areas


def _draw_underline_below_text(page: fitz.Page, text_area: fitz.Rect) -> None:
    """
    글자 아래에 빨간 선을 긋는다.

    PyMuPDF 에 밑줄 기능이 따로 있지만 쓰지 않는다. 두 가지 문제 때문이다.
      - 그 기능은 글자 영역의 90% 지점에 선을 긋는데, 한글은 받침(ㄱ, ㅈ 등)이
        그보다 아래로 내려와서 선이 글자를 관통해 버린다.
        (알파벳은 받침이 없어 문제가 안 되므로 그렇게 만들어진 것이다)
      - 그 기능은 선 두께를 지정할 수 없다.

    그래서 직접 선을 긋는다. 그러면 위치와 두께를 원하는 대로 정할 수 있다.
    """
    underline_height = text_area.y1 + config.UNDERLINE_GAP_BELOW_TEXT_IN_POINTS
    page.draw_line(
        fitz.Point(text_area.x0, underline_height),
        fitz.Point(text_area.x1, underline_height),
        color=config.UNDERLINE_COLOR,
        width=config.UNDERLINE_THICKNESS_IN_POINTS,
    )


def find_content_area(page: fitz.Page) -> fitz.Rect:
    """
    그림으로 잘라낼 영역을 정한다. 머리말과 꼬리말은 빼고 본문만 남긴다.

    법령정보센터가 만드는 PDF 는 맨 위에 문서 이름, 맨 아래에
    '법제처 / 국가법령정보센터 / 쪽번호' 가 인쇄되어 있고,
    본문과의 사이에 가로 선이 하나씩 그어져 있다.
    그 두 선 사이가 우리가 원하는 부분이다.

    제목·시행일·소관부처와 우측 상단 QR 코드는 이 안에 들어있어 함께 담긴다.
    """
    header_line_height, footer_line_height = _find_horizontal_rule_heights(page)

    def lies_between_the_rules(area: fitz.Rect) -> bool:
        return area.y0 > header_line_height and area.y1 < footer_line_height

    content_area = fitz.Rect()
    for block in page.get_text("blocks"):
        block_area = fitz.Rect(block[:4])
        if lies_between_the_rules(block_area):
            content_area |= block_area

    for image_info in page.get_image_info():
        image_area = fitz.Rect(image_info["bbox"])
        if lies_between_the_rules(image_area):
            content_area |= image_area

    if content_area.is_empty:
        return content_area

    return _add_padding_without_crossing_the_rules(
        content_area, header_line_height, footer_line_height, page
    )


def _add_padding_without_crossing_the_rules(
    content_area: fitz.Rect,
    header_line_height: float,
    footer_line_height: float,
    page: fitz.Page,
) -> fitz.Rect:
    """
    잘라낼 영역 둘레에 여백을 주되, 위아래 구분선을 넘지 않게 막는다.

    여백을 그냥 더하면 구분선 너머의 머리말·꼬리말이 조금씩 딸려 들어온다.
    법령은 구분선과 본문 사이가 좁아서 실제로 머리말 글자가 잘린 채
    그림 위쪽에 걸쳐 들어오는 일이 있었다.
    """
    padding = config.CAPTURE_PADDING_IN_POINTS

    return fitz.Rect(
        max(content_area.x0 - padding, 0.0),
        max(content_area.y0 - padding, header_line_height),
        min(content_area.x1 + padding, page.rect.width),
        min(content_area.y1 + padding, footer_line_height),
    )


def _find_horizontal_rule_heights(page: fitz.Page) -> tuple[float, float]:
    """페이지 위아래를 가로지르는 구분선 두 개의 높이를 찾는다."""
    rule_heights = [
        drawing["rect"].y0
        for drawing in page.get_drawings()
        if drawing["rect"].height < config.HORIZONTAL_RULE_MAX_HEIGHT_IN_POINTS
    ]

    if len(rule_heights) < 2:
        # 구분선을 못 찾으면 페이지 전체를 대상으로 삼는다.
        return 0.0, page.rect.height

    return min(rule_heights), max(rule_heights)


def extract_article_body_text(pdf_path: Path) -> str:
    """
    조문 본문만 글자로 뽑아낸다. 개정본끼리 내용이 같은지 비교할 때 쓴다.

    제목·시행일·소관부처 줄은 제외한다.
    이 부분은 개정할 때마다 반드시 바뀌므로(고시 번호와 날짜가 달라진다),
    그대로 두고 비교하면 언제나 '다르다' 가 나와 비교가 무의미해진다.
    """
    document = fitz.open(pdf_path)
    try:
        all_lines: list[str] = []
        for page in document:
            all_lines.extend(_read_printed_lines_of_page(page))
    finally:
        document.close()

    body_lines = _drop_lines_before_first_article(all_lines)
    return WHITESPACE_PATTERN.sub(" ", " ".join(body_lines)).strip()


def _read_printed_lines_of_page(page: fitz.Page) -> list[str]:
    """
    한 쪽에서 머리말·꼬리말을 뺀 줄들을 순서대로 읽는다.

    쪽마다 따로 처리하는 이유: 긴 조문은 여러 쪽에 걸치는데,
    첫 쪽만 보면 뒷부분이 바뀐 개정을 '앞 버전과 동일' 로 잘못 판단한다.
    """
    header_line_height, footer_line_height = _find_horizontal_rule_heights(page)

    lines: list[str] = []
    for block in page.get_text("blocks"):
        block_area = fitz.Rect(block[:4])
        if not (block_area.y0 > header_line_height and block_area.y1 < footer_line_height):
            continue

        block_text = block[4].strip()
        if block_text:
            lines.append(block_text)

    return lines


def _drop_lines_before_first_article(lines: list[str]) -> list[str]:
    """
    조문이 시작되기 전의 줄들(법령 제목·시행일·소관부처·안내문)을 버린다.

    왜 이렇게 하는가: 이 앞부분은 개정할 때마다 반드시 바뀐다(고시 번호와 날짜).
    그대로 두고 개정본끼리 비교하면 언제나 '다르다' 가 나와 비교가 무의미해진다.

    '짧은 줄은 제목' 같은 식으로 가려내면 안 된다. 실제로 그렇게 했더니
    `27. 관광 휴게시설` 처럼 짧은 호(號)까지 본문에서 빠져,
    마지막 쪽 내용이 통째로 사라지는 일이 있었다.
    조문이 시작되는 자리를 찾아 그 앞을 버리는 편이 확실하다.
    """
    for index, line in enumerate(lines):
        if ARTICLE_START_PATTERN.match(line):
            return lines[index:]
    return lines  # 조문 시작을 못 찾으면 그대로 둔다


