"""사용자 지정 SET 저장·읽기·이름 갱신이 되는지 확인한다. (한글 안 켬)"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import LawSourceKind
from core.capture_set_memory import (
    CaptureMemoryItem,
    CaptureMemoryNameChange,
    add_capture_memory_item,
    add_capture_memory_set,
    build_name_change_notice,
    load_capture_memory_sets,
    remove_capture_memory_item,
    rename_capture_memory_set,
    replace_capture_memory_item_law_name,
)


def report(label: str, is_ok: bool, detail: str = "") -> bool:
    print(f"  [{'OK  ' if is_ok else '실패'}] {label}" + (f"  -- {detail}" if detail else ""))
    return is_ok


def _sample_item(law_name: str, article_text: str) -> CaptureMemoryItem:
    return CaptureMemoryItem(
        law_name=law_name,
        law_id="111",
        source_kind=LawSourceKind.ADMINISTRATIVE_RULE,
        kind_label="고시",
        article_text=article_text,
        underline_phrases=("하자담보책임",),
        underline_color_name="빨강",
    )


all_passed = True

with tempfile.TemporaryDirectory() as temporary_folder:
    file_path = Path(temporary_folder) / "user_capture_set_memory.json"

    print("=== 1. 없는 파일 ===")
    all_passed &= report("없는 파일은 빈 목록", load_capture_memory_sets(file_path) == [])

    print("\n=== 2. 세트 만들기·이름 바꾸기 ===")
    add_capture_memory_set("감정 기준에 관한 의견서", file_path)
    add_capture_memory_set("감정 기준에 관한 의견서", file_path)
    loaded = load_capture_memory_sets(file_path)
    all_passed &= report("같은 이름은 한 번만", len(loaded) == 1, str(len(loaded)))
    rename_capture_memory_set("감정 기준에 관한 의견서", "감정기준 의견서", file_path)
    loaded = load_capture_memory_sets(file_path)
    all_passed &= report(
        "세트 이름이 바뀌었는가",
        len(loaded) == 1 and loaded[0].name == "감정기준 의견서",
        loaded[0].name if loaded else "",
    )

    print("\n=== 3. 항목 추가·중복·삭제 ===")
    add_capture_memory_item("감정기준 의견서", _sample_item("하자판정기준", "1"), file_path)
    add_capture_memory_item("감정기준 의견서", _sample_item("하자판정기준", "1"), file_path)
    add_capture_memory_item("감정기준 의견서", _sample_item("주택법", "2"), file_path)
    loaded = load_capture_memory_sets(file_path)
    all_passed &= report(
        "같은 법령·같은 조문은 한 번만",
        len(loaded[0].items) == 2,
        str(len(loaded[0].items)),
    )
    remove_capture_memory_item("감정기준 의견서", 0, file_path)
    loaded = load_capture_memory_sets(file_path)
    all_passed &= report(
        "첫 항목을 지우면 주택법만 남는가",
        len(loaded[0].items) == 1 and loaded[0].items[0].law_name == "주택법",
        loaded[0].items[0].law_name if loaded[0].items else "",
    )

    print("\n=== 4. 법령 이름이 바뀌면 저장 이름을 고친다 ===")
    replace_capture_memory_item_law_name("감정기준 의견서", 0, "주택법(현행)", file_path)
    loaded = load_capture_memory_sets(file_path)
    all_passed &= report(
        "저장 이름이 지금 이름으로 바뀌었는가",
        loaded[0].items[0].law_name == "주택법(현행)",
        loaded[0].items[0].law_name,
    )
    # 띄어쓰기만 다른 이름은 안내하지 않는다.
    spacing_notice = build_name_change_notice(
        [
            CaptureMemoryNameChange(
                stored_law_name="주택 법",
                current_law_name="주택법",
            )
        ]
    )
    all_passed &= report("띄어쓰기만 다르면 안내가 없는가", spacing_notice == "")
    rename_notice = build_name_change_notice(
        [
            CaptureMemoryNameChange(
                stored_law_name="주택건설촉진법",
                current_law_name="주택법",
                historical_law_name="주택건설촉진법",
            )
        ]
    )
    all_passed &= report(
        "개명 안내가 지금 이름을 말하는가",
        "주택건설촉진법" in rename_notice and "주택법" in rename_notice,
        rename_notice,
    )
    all_passed &= report(
        "당시 이름 안내가 있는가",
        "당시 이름" in rename_notice,
    )

    print("\n=== 5. 조문·밑줄만 수정하고 법령 번호는 유지 ===")
    from core.capture_set_memory import update_capture_memory_item_details

    was_saved = update_capture_memory_item_details(
        "감정기준 의견서",
        0,
        "제3조",
        ("새 밑줄",),
        "파랑",
        file_path,
    )
    loaded = load_capture_memory_sets(file_path)
    updated_item = loaded[0].items[0]
    all_passed &= report("수정이 저장됐는가", was_saved and updated_item.article_text == "3")
    all_passed &= report(
        "밑줄과 색이 바뀌었는가",
        updated_item.underline_phrases == ("새 밑줄",) and updated_item.underline_color_name == "파랑",
    )
    all_passed &= report("법령 번호는 그대로인가", updated_item.law_id == "111")
    blocked = update_capture_memory_item_details(
        "감정기준 의견서",
        0,
        "3",
        ("다른 밑줄",),
        "빨강",
        file_path,
    )
    # 같은 줄만 있으면 조문이 같아도 저장된다. 다른 줄을 넣어 겹침을 만든다.
    add_capture_memory_item("감정기준 의견서", _sample_item("다른법", "9"), file_path)
    blocked = update_capture_memory_item_details(
        "감정기준 의견서",
        1,
        "3",
        ("겹침",),
        "빨강",
        file_path,
    )
    # 다른 법의 조문 3은 주택법(현행) 조문 3과 법령이 달라 겹치지 않는다.
    # 같은 법령으로 맞춰 겹치는지 보려면 항목을 직접 같은 law_id 로 넣어야 한다.
    add_capture_memory_item(
        "감정기준 의견서",
        _sample_item("주택법(현행)", "8"),
        file_path,
    )
    loaded = load_capture_memory_sets(file_path)
    duplicate_index = len(loaded[0].items) - 1
    blocked = update_capture_memory_item_details(
        "감정기준 의견서",
        duplicate_index,
        "3",
        ("겹침",),
        "빨강",
        file_path,
    )
    loaded_after = load_capture_memory_sets(file_path)
    all_passed &= report(
        "같은 조문으로 고치면 저장하지 않는가",
        blocked is False and loaded_after[0].items[duplicate_index].article_text == "8",
        loaded_after[0].items[duplicate_index].article_text,
    )

print()
print("모든 확인 통과" if all_passed else "실패한 확인이 있습니다")
raise SystemExit(0 if all_passed else 1)
