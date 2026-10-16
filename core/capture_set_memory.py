"""
자주 쓰는 캡처 묶음(사용자 지정 SET)을 파일에 기억한다.

왜 따로 두는가:
  '감정 기준에 관한 의견서'처럼 서면마다 들어가는 법령·조문·밑줄은 같고,
  사건마다 바뀌는 것은 시행 시점뿐이다. 그 레시피를 이름 붙여 저장해 두면
  날짜만 넣고 담은 목록에 한 번에 넣을 수 있다.

왜 JSON 파일인가:
  즐겨찾기와 같다. 설치·데이터베이스 없이 프로젝트 폴더에 파일 하나가 생긴다.
  지워도 프로그램은 빈 목록으로 다시 시작한다.

왜 개정본 번호(version_id)를 안 넣는가:
  개정본 번호는 개정될 때마다 바뀐다. 세트는 '어느 법의 어느 조문'이지
  '어느 판'이 아니다. 판은 담을 때 기준일로 다시 찾는다.

왜 law_id 를 넣는가:
  법령 이름이 바뀌어도 법령 번호는 그대로다. 저장해 둔 옛 이름으로 검색해
  번호가 같은 것을 고르면 개명 뒤에도 같은 법령으로 담을 수 있다.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path

import config
from config import DEFAULT_UNDERLINE_COLOR_NAME, LawSourceKind
from core.article_number import (
    format_article_numbers_for_entry,
    parse_article_numbers,
)
from core.law_source import law_names_differ_beyond_spacing


@dataclass(frozen=True)
class CaptureMemoryItem:
    """
    세트 안의 캡처 한 줄.

    조문 번호는 사람이 적은 글자 그대로 둔다. (예: '39, 32의2')
    담을 때 기존 조문 해석 함수로 다시 읽는다.
    """

    law_name: str
    law_id: str
    source_kind: LawSourceKind
    kind_label: str
    article_text: str
    underline_phrases: tuple[str, ...]
    underline_color_name: str = DEFAULT_UNDERLINE_COLOR_NAME

    def display_label(self) -> str:
        """설정 창 목록에 보여줄 한 줄."""
        if self.underline_phrases:
            phrase_label = " · ".join(self.underline_phrases)
            if len(phrase_label) > 28:
                phrase_label = phrase_label[:28] + "…"
        else:
            phrase_label = "밑줄 없음"
        return (
            f"{self.law_name} ({self.kind_label}) · {self.article_text} · {phrase_label}"
        )

    def is_same_recipe_as(self, other: CaptureMemoryItem) -> bool:
        """
        같은 법령의 같은 조문 칸인지.

        밑줄 문구가 달라도 조문이 같으면 중복으로 본다.
        한 세트에 같은 조문을 두 줄 넣으면 그림이 두 번 나오기 때문이다.
        """
        if _article_text_key(self.article_text) != _article_text_key(other.article_text):
            return False
        if self.law_id and other.law_id:
            return (
                self.law_id == other.law_id
                and self.source_kind is other.source_kind
            )
        return (
            self.law_name == other.law_name
            and self.source_kind is other.source_kind
        )


@dataclass(frozen=True)
class CaptureMemorySet:
    """이름이 붙은 캡처 묶음. 예: '감정 기준에 관한 의견서'."""

    name: str
    items: tuple[CaptureMemoryItem, ...]


@dataclass(frozen=True)
class CaptureMemoryNameChange:
    """
    담을 때 발견한 이름 차이.

    stored 와 current 가 다르면 법령 자체의 지금 이름이 바뀐 것이다.
    historical 이 있으면 그 시점 판의 당시 이름이 지금 이름과 다르다.
    (캡션에는 당시 이름이 들어간다)
    """

    stored_law_name: str
    current_law_name: str
    historical_law_name: str = ""


def load_capture_memory_sets(file_path: Path | None = None) -> list[CaptureMemorySet]:
    """
    세트 목록을 읽는다.

    파일이 없거나 깨져 있으면 빈 목록을 돌려준다.
    (기억 파일 때문에 프로그램이 죽으면 안 된다)
    """
    path = file_path or config.CAPTURE_SET_MEMORY_FILE_PATH
    if not path.is_file():
        return []

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    if not isinstance(raw, list):
        return []

    sets: list[CaptureMemorySet] = []
    for entry in raw:
        memory_set = _set_from_json_entry(entry)
        if memory_set is not None:
            sets.append(memory_set)
    return sets


def add_capture_memory_set(
    name: str, file_path: Path | None = None
) -> list[CaptureMemorySet]:
    """
    빈 세트를 하나 만든다.

    이름이 비었거나 이미 있으면 파일을 다시 쓰지 않고 지금 목록을 돌려준다.
    """
    path = file_path or config.CAPTURE_SET_MEMORY_FILE_PATH
    cleaned_name = name.strip()
    sets = load_capture_memory_sets(path)
    if not cleaned_name or _find_set_index(sets, cleaned_name) is not None:
        return sets

    sets.append(CaptureMemorySet(name=cleaned_name, items=()))
    _save_sets(sets, path)
    return sets


def rename_capture_memory_set(
    old_name: str, new_name: str, file_path: Path | None = None
) -> list[CaptureMemorySet]:
    """세트 이름만 바꾼다. 새 이름이 비었거나 다른 세트와 겹치면 그대로 둔다."""
    path = file_path or config.CAPTURE_SET_MEMORY_FILE_PATH
    cleaned_new_name = new_name.strip()
    sets = load_capture_memory_sets(path)
    old_index = _find_set_index(sets, old_name)
    if old_index is None or not cleaned_new_name:
        return sets
    if cleaned_new_name != old_name and _find_set_index(sets, cleaned_new_name) is not None:
        return sets

    sets[old_index] = replace(sets[old_index], name=cleaned_new_name)
    _save_sets(sets, path)
    return sets


def remove_capture_memory_set(
    name: str, file_path: Path | None = None
) -> list[CaptureMemorySet]:
    """세트 하나와 그 안의 항목을 모두 지운다."""
    path = file_path or config.CAPTURE_SET_MEMORY_FILE_PATH
    sets = [
        memory_set
        for memory_set in load_capture_memory_sets(path)
        if memory_set.name != name
    ]
    _save_sets(sets, path)
    return sets


def add_capture_memory_item(
    set_name: str, item: CaptureMemoryItem, file_path: Path | None = None
) -> list[CaptureMemorySet]:
    """
    세트에 캡처 한 줄을 넣는다.

    같은 법령·같은 조문 칸이 이미 있으면 넣지 않는다.
    """
    path = file_path or config.CAPTURE_SET_MEMORY_FILE_PATH
    sets = load_capture_memory_sets(path)
    index = _find_set_index(sets, set_name)
    if index is None:
        return sets

    memory_set = sets[index]
    if any(existing.is_same_recipe_as(item) for existing in memory_set.items):
        return sets

    sets[index] = replace(memory_set, items=memory_set.items + (item,))
    _save_sets(sets, path)
    return sets


def remove_capture_memory_item(
    set_name: str, item_index: int, file_path: Path | None = None
) -> list[CaptureMemorySet]:
    """세트 안에서 지정한 위치의 항목을 뺀다."""
    path = file_path or config.CAPTURE_SET_MEMORY_FILE_PATH
    sets = load_capture_memory_sets(path)
    index = _find_set_index(sets, set_name)
    if index is None:
        return sets

    items = list(sets[index].items)
    if not (0 <= item_index < len(items)):
        return sets

    del items[item_index]
    sets[index] = replace(sets[index], items=tuple(items))
    _save_sets(sets, path)
    return sets


def update_capture_memory_item_details(
    set_name: str,
    item_index: int,
    article_text: str,
    underline_phrases: tuple[str, ...],
    underline_color_name: str,
    file_path: Path | None = None,
) -> bool:
    """
    항목의 조문·밑줄·색만 바꾼다. 법령 이름과 법령 번호는 그대로 둔다.

    다른 줄과 같은 법령·같은 조문이 되면 저장하지 않고 False 를 돌려준다.
    설정 창은 미리보기가 없으므로 법령 자체를 여기서 바꾸지 않는다.
    """
    path = file_path or config.CAPTURE_SET_MEMORY_FILE_PATH
    sets = load_capture_memory_sets(path)
    index = _find_set_index(sets, set_name)
    if index is None:
        return False

    items = list(sets[index].items)
    if not (0 <= item_index < len(items)):
        return False

    cleaned_article = article_text.strip()
    try:
        cleaned_article = format_article_numbers_for_entry(
            parse_article_numbers(cleaned_article)
        )
    except ValueError:
        return False

    updated = replace(
        items[item_index],
        article_text=cleaned_article,
        underline_phrases=underline_phrases,
        underline_color_name=underline_color_name or DEFAULT_UNDERLINE_COLOR_NAME,
    )
    for other_index, existing in enumerate(items):
        if other_index != item_index and existing.is_same_recipe_as(updated):
            return False

    items[item_index] = updated
    sets[index] = replace(sets[index], items=tuple(items))
    _save_sets(sets, path)
    return True


def replace_capture_memory_item_law_name(
    set_name: str,
    item_index: int,
    new_law_name: str,
    file_path: Path | None = None,
) -> list[CaptureMemorySet]:
    """
    항목에 적어 둔 법령 이름을 지금 이름으로 고친다.

    담을 때 개명을 알아챘을 때만 부른다. 다음부터는 지금 이름으로 검색한다.
    """
    path = file_path or config.CAPTURE_SET_MEMORY_FILE_PATH
    cleaned_name = new_law_name.strip()
    sets = load_capture_memory_sets(path)
    index = _find_set_index(sets, set_name)
    if index is None or not cleaned_name:
        return sets

    items = list(sets[index].items)
    if not (0 <= item_index < len(items)):
        return sets

    items[item_index] = replace(items[item_index], law_name=cleaned_name)
    sets[index] = replace(sets[index], items=tuple(items))
    _save_sets(sets, path)
    return sets


def build_name_change_notice(changes: list[CaptureMemoryNameChange]) -> str:
    """
    이름 차이 안내 문장. 차이가 없으면 빈 글자.

    창을 띄우는 쪽은 이 글자가 비어 있지 않을 때만 messagebox 를 연다.
    검증에서는 창 없이 이 글자만 보면 된다.
    """
    lines: list[str] = []
    for change in changes:
        if law_names_differ_beyond_spacing(change.stored_law_name, change.current_law_name):
            lines.append(
                f"저장해 둔 이름 '{change.stored_law_name}'은 지금 "
                f"'{change.current_law_name}'입니다. "
                "같은 법령으로 담았고, 세트에 적힌 이름도 지금 이름으로 바꿔 두었습니다."
            )
        if change.historical_law_name and law_names_differ_beyond_spacing(
            change.historical_law_name, change.current_law_name
        ):
            lines.append(
                f"'{change.current_law_name}'의 이 시점 캡션에는 당시 이름 "
                f"'{change.historical_law_name}'이 들어갑니다."
            )
    return "\n\n".join(lines)


def _article_text_key(article_text: str) -> str:
    """
    조문 칸을 비교용 글자로 맞춘다.

    '제1조'와 '1'은 같은 조문이다. 해석이 안 되면 적은 글자 그대로 견준다.
    """
    try:
        return format_article_numbers_for_entry(parse_article_numbers(article_text))
    except ValueError:
        return article_text.strip()


def _find_set_index(sets: list[CaptureMemorySet], name: str) -> int | None:
    for index, memory_set in enumerate(sets):
        if memory_set.name == name:
            return index
    return None


def _save_sets(sets: list[CaptureMemorySet], path: Path) -> None:
    """목록을 JSON 파일로 쓴다. 사람이 열어 볼 수 있게 한글을 그대로 둔다."""
    payload = [
        {
            "name": memory_set.name,
            "items": [
                {
                    "law_name": item.law_name,
                    "law_id": item.law_id,
                    "source_kind": item.source_kind.name,
                    "kind_label": item.kind_label,
                    "article_text": item.article_text,
                    "underline_phrases": list(item.underline_phrases),
                    "underline_color_name": item.underline_color_name,
                }
                for item in memory_set.items
            ],
        }
        for memory_set in sets
    ]
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _set_from_json_entry(entry: object) -> CaptureMemorySet | None:
    """JSON 한 세트를 객체로 바꾼다. 이름이 없으면 건너뛴다."""
    if not isinstance(entry, dict):
        return None

    name = entry.get("name")
    if not isinstance(name, str) or not name.strip():
        return None

    raw_items = entry.get("items", [])
    if not isinstance(raw_items, list):
        raw_items = []

    items: list[CaptureMemoryItem] = []
    for raw_item in raw_items:
        item = _item_from_json_entry(raw_item)
        if item is not None:
            items.append(item)

    return CaptureMemorySet(name=name.strip(), items=tuple(items))


def _item_from_json_entry(entry: object) -> CaptureMemoryItem | None:
    """JSON 항목 하나를 객체로 바꾼다. 법령 이름이나 조문이 없으면 건너뛴다."""
    if not isinstance(entry, dict):
        return None

    law_name = entry.get("law_name")
    article_text = entry.get("article_text")
    source_kind_name = entry.get("source_kind")
    if not isinstance(law_name, str) or not law_name.strip():
        return None
    if not isinstance(article_text, str) or not article_text.strip():
        return None
    if not isinstance(source_kind_name, str):
        return None

    try:
        source_kind = LawSourceKind[source_kind_name]
    except KeyError:
        return None

    law_id = entry.get("law_id", "")
    kind_label = entry.get("kind_label", "")
    color_name = entry.get("underline_color_name", DEFAULT_UNDERLINE_COLOR_NAME)
    raw_phrases = entry.get("underline_phrases", [])
    phrases: list[str] = []
    if isinstance(raw_phrases, list):
        for phrase in raw_phrases:
            if isinstance(phrase, str) and phrase.strip():
                phrases.append(phrase.strip())

    return CaptureMemoryItem(
        law_name=law_name.strip(),
        law_id=law_id if isinstance(law_id, str) else "",
        source_kind=source_kind,
        kind_label=kind_label if isinstance(kind_label, str) else "",
        article_text=article_text.strip(),
        underline_phrases=tuple(phrases),
        underline_color_name=(
            color_name.strip()
            if isinstance(color_name, str) and color_name.strip()
            else DEFAULT_UNDERLINE_COLOR_NAME
        ),
    )
