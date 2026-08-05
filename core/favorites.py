"""
자주 쓰는 법령·고시 즐겨찾기 저장.

왜 따로 두는가:
  하자소송에서 같은 법령(하자판정기준, 공동주택관리법 등)을 매번 검색하는 것은 번거롭다.
  이름만 기억해 두면 검색 없이 바로 고를 수 있다.

왜 JSON 파일인가:
  설치·데이터베이스 없이 프로젝트 폴더에 파일이 하나 생기면 된다.
  사용자가 파일을 열어 볼 수도 있고, 지워도 프로그램은 빈 목록으로 다시 시작한다.

왜 개정본 번호(version_id)를 안 넣는가:
  개정본 번호는 개정될 때마다 바뀐다. 즐겨찾기는 '어느 법' 이지 '어느 판' 이 아니다.
  판은 화면의 시점·개정본 체크로 고른다.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import config
from config import LawSourceKind


@dataclass(frozen=True)
class FavoriteLaw:
    """
    즐겨찾기에 넣은 법령·고시 하나.

    law_id 는 개정돼도 같은 법령을 가리키는 번호다.
    같은 이름이 여러 갈래에 있을 수 있어 source_kind 와 함께 중복을 가린다.
    """

    law_name: str
    law_id: str
    source_kind: LawSourceKind
    kind_label: str  # 화면 표시용. 예: "고시", "법률"

    def display_label(self) -> str:
        """즐겨찾기 목록에 보여줄 글자."""
        return f"{self.law_name} ({self.kind_label})"

    def is_same_law_as(self, other: FavoriteLaw) -> bool:
        """같은 법령인지. law_id 가 있으면 그것으로, 없으면 이름+갈래로 본다."""
        if self.law_id and other.law_id:
            return (
                self.law_id == other.law_id
                and self.source_kind is other.source_kind
            )
        return (
            self.law_name == other.law_name
            and self.source_kind is other.source_kind
        )


def load_favorites(file_path: Path | None = None) -> list[FavoriteLaw]:
    """
    즐겨찾기 목록을 읽는다.

    파일이 없거나 깨져 있으면 빈 목록을 돌려준다.
    (프로그램이 즐겨찾기 때문에 죽으면 안 된다)
    """
    path = file_path or config.FAVORITES_FILE_PATH
    if not path.is_file():
        return []

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    if not isinstance(raw, list):
        return []

    favorites: list[FavoriteLaw] = []
    for entry in raw:
        favorite = _favorite_from_json_entry(entry)
        if favorite is not None:
            favorites.append(favorite)
    return favorites


def add_favorite(
    favorite: FavoriteLaw, file_path: Path | None = None
) -> list[FavoriteLaw]:
    """
    즐겨찾기에 한 건을 넣고 저장한다.

    이미 같은 법령이 있으면 목록을 그대로 두고 다시 쓰지 않는다.
    """
    path = file_path or config.FAVORITES_FILE_PATH
    favorites = load_favorites(path)
    if any(existing.is_same_law_as(favorite) for existing in favorites):
        return favorites

    favorites.append(favorite)
    _save_favorites(favorites, path)
    return favorites


def remove_favorite(
    favorite: FavoriteLaw, file_path: Path | None = None
) -> list[FavoriteLaw]:
    """즐겨찾기에서 한 건을 빼고 저장한다."""
    path = file_path or config.FAVORITES_FILE_PATH
    favorites = [
        existing
        for existing in load_favorites(path)
        if not existing.is_same_law_as(favorite)
    ]
    _save_favorites(favorites, path)
    return favorites


def _save_favorites(favorites: list[FavoriteLaw], path: Path) -> None:
    """목록을 JSON 파일로 쓴다."""
    payload = [
        {
            "law_name": item.law_name,
            "law_id": item.law_id,
            "source_kind": item.source_kind.name,
            "kind_label": item.kind_label,
        }
        for item in favorites
    ]
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _favorite_from_json_entry(entry: object) -> FavoriteLaw | None:
    """JSON 한 줄을 FavoriteLaw 로 바꾼다. 형식이 이상하면 건너뛴다."""
    if not isinstance(entry, dict):
        return None

    law_name = entry.get("law_name")
    law_id = entry.get("law_id", "")
    source_kind_name = entry.get("source_kind")
    kind_label = entry.get("kind_label", "")
    if not isinstance(law_name, str) or not law_name.strip():
        return None
    if not isinstance(source_kind_name, str):
        return None

    try:
        source_kind = LawSourceKind[source_kind_name]
    except KeyError:
        return None

    return FavoriteLaw(
        law_name=law_name.strip(),
        law_id=law_id if isinstance(law_id, str) else "",
        source_kind=source_kind,
        kind_label=kind_label if isinstance(kind_label, str) else "",
    )
