"""즐겨찾기 저장·읽기·삭제가 제대로 되는지 확인한다. (한글 안 켬)"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import LawSourceKind
from core.favorites import FavoriteLaw, add_favorite, load_favorites, remove_favorite


def report(label: str, is_ok: bool, detail: str = "") -> bool:
    print(f"  [{'OK  ' if is_ok else '실패'}] {label}" + (f"  -- {detail}" if detail else ""))
    return is_ok


all_passed = True

with tempfile.TemporaryDirectory() as temporary_folder:
    file_path = Path(temporary_folder) / "favorites_test.json"

    print("=== 1. 빈 파일 / 없는 파일 ===")
    all_passed &= report("없는 파일은 빈 목록", load_favorites(file_path) == [])

    print("\n=== 2. 추가·다시 읽기 ===")
    first = FavoriteLaw(
        law_name="하자판정기준",
        law_id="111",
        source_kind=LawSourceKind.ADMINISTRATIVE_RULE,
        kind_label="고시",
    )
    second = FavoriteLaw(
        law_name="공동주택관리법",
        law_id="222",
        source_kind=LawSourceKind.STATUTE,
        kind_label="법률",
    )
    add_favorite(first, file_path)
    add_favorite(second, file_path)
    loaded = load_favorites(file_path)
    all_passed &= report("두 건이 저장됐는가", len(loaded) == 2, str(len(loaded)))
    all_passed &= report(
        "표시 글자",
        loaded[0].display_label() == "하자판정기준 (고시)",
        loaded[0].display_label(),
    )

    print("\n=== 3. 중복 추가 막기 ===")
    same_again = FavoriteLaw(
        law_name="하자판정기준(다른이름표기)",
        law_id="111",
        source_kind=LawSourceKind.ADMINISTRATIVE_RULE,
        kind_label="고시",
    )
    after_dup = add_favorite(same_again, file_path)
    all_passed &= report("같은 law_id 는 한 번만", len(after_dup) == 2, str(len(after_dup)))

    print("\n=== 4. 삭제 ===")
    after_remove = remove_favorite(first, file_path)
    all_passed &= report("한 건 삭제", len(after_remove) == 1, str(len(after_remove)))
    all_passed &= report(
        "남은 것이 공동주택관리법",
        after_remove[0].law_name == "공동주택관리법",
        after_remove[0].law_name,
    )

    print("\n=== 5. 깨진 JSON ===")
    broken = Path(temporary_folder) / "broken.json"
    broken.write_text("{이건 망가짐", encoding="utf-8")
    all_passed &= report("깨진 파일은 빈 목록", load_favorites(broken) == [])

print("\n" + "=" * 58)
print("통과" if all_passed else "실패 — 위 목록을 보세요")
sys.exit(0 if all_passed else 1)
