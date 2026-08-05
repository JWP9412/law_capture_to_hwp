"""
'어느 시점?' 세 가지 방식이 맞는지 확인한다. (한글을 켜지 않는다)

확인 항목:
  - 특정 시점 하나: 기준일 칸만 보이고, 경계일이 맞는 판을 고르는가
  - 기간: 칸 둘이 다시 나오고 구간 안 개정본만 나오는가
  - 전체 기간: 날짜 칸이 없고, 많으면 처음부터 전부 꺼져 있는가
"""
import sys
import tkinter as tk
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ui.app_window import AppWindow
from ui.input_view import ALL_TIME_MODE, PERIOD_MODE, SINGLE_DATE_MODE


def report(label: str, is_ok: bool, detail: str = "") -> bool:
    mark = "OK  " if is_ok else "실패"
    print(f"  [{mark}] {label}" + (f"  -- {detail}" if detail else ""))
    return is_ok


def set_entry(entry: tk.Entry, text: str) -> None:
    entry.delete(0, tk.END)
    entry.insert(0, text)


def is_packed(widget) -> bool:
    """위젯이 화면에 붙어 있는지 본다. pack_forget 한 것은 False."""
    try:
        return bool(widget.winfo_ismapped())
    except tk.TclError:
        return False


window = AppWindow()
window.update()
view = window._input_view
all_passed = True

print("=== 1. 특정 시점 하나 — 칸 레이아웃 ===")
view._mode.set(SINGLE_DATE_MODE)
view._apply_timing_mode_layout()
window.update()
all_passed &= report("기준일 칸이 보이는가", is_packed(view._reference_date_entry))
all_passed &= report("기간 시작 칸이 숨겨졌는가", not is_packed(view._period_start_entry))
all_passed &= report("기간 끝 칸이 숨겨졌는가", not is_packed(view._period_end_entry))
all_passed &= report(
    "버튼 글자",
    view._find_versions_button.cget("text") == "그 시점 판 찾기",
    view._find_versions_button.cget("text"),
)

print("\n=== 2. 지능형 홈네트워크 — 시점 경계 ===")
set_entry(view._law_name_entry, "지능형 홈네트워크")
view._search_law()
window.update()
all_passed &= report("법령을 찾았는가", view._found_law is not None, str(view._found_law))

set_entry(view._reference_date_entry, "2012-09-20")
view._refresh_version_list()
window.update()
versions = [version for _, version in view._version_checkboxes]
all_passed &= report("2012-09-20 → 판 1개", len(versions) == 1, f"{len(versions)}개")
if versions:
    label = versions[0].effective_date_label
    all_passed &= report(
        "시행 2011. 3. 4. 인가",
        "2011. 3. 4" in label or "2011.3.4" in label.replace(" ", ""),
        label,
    )
    print(f"          {versions[0]}")

set_entry(view._reference_date_entry, "2011-03-03")
view._refresh_version_list()
window.update()
versions = [version for _, version in view._version_checkboxes]
if versions:
    label = versions[0].effective_date_label
    all_passed &= report(
        "2011-03-03 → 시행 2009. 8. 24.",
        "2009. 8. 24" in label or "2009.8.24" in label.replace(" ", ""),
        label,
    )
    print(f"          {versions[0]}")
else:
    all_passed &= report("2011-03-03 → 시행 2009. 8. 24.", False, "판 없음")

print("\n=== 3. 기간 모드 — 칸이 둘 다시 나오는가 ===")
view._mode.set(PERIOD_MODE)
view._apply_timing_mode_layout()
window.update()
all_passed &= report("기간 시작 칸이 보이는가", is_packed(view._period_start_entry))
all_passed &= report("기간 끝 칸이 보이는가", is_packed(view._period_end_entry))
all_passed &= report("기준일 칸이 숨겨졌는가", not is_packed(view._reference_date_entry))
all_passed &= report(
    "버튼 글자",
    view._find_versions_button.cget("text") == "개정본 찾기",
    view._find_versions_button.cget("text"),
)

set_entry(view._law_name_entry, "하자판정기준")
view._search_law()
window.update()
set_entry(view._period_start_entry, "2024-01-01")
set_entry(view._period_end_entry, "2026-12-31")
view._refresh_version_list()
window.update()
period_count = len(view._version_checkboxes)
all_passed &= report("기간 안 개정본", period_count == 2, f"{period_count}개")
all_passed &= report(
    "기간 모드는 처음부터 전부 켜져 있는가",
    all(is_on.get() for is_on, _ in view._version_checkboxes),
)

print("\n=== 4. 전체 기간 — 주택법 ===")
view._mode.set(ALL_TIME_MODE)
view._apply_timing_mode_layout()
window.update()
all_passed &= report("날짜 칸이 모두 숨겨졌는가",
                     not is_packed(view._reference_date_entry)
                     and not is_packed(view._period_start_entry)
                     and not is_packed(view._period_end_entry))
all_passed &= report("안내 문구가 보이는가", is_packed(view._all_time_hint_label))
all_passed &= report(
    "버튼 글자",
    view._find_versions_button.cget("text") == "전체 개정본 찾기",
    view._find_versions_button.cget("text"),
)

set_entry(view._law_name_entry, "주택법")
view._search_law()
window.update()
# 검색이 부분 일치라 여러 건이 나올 수 있다. 이름이 정확히 '주택법' 인 것을 고른다.
exact = next(
    (item for item in view._candidates if item.law_name == "주택법"),
    view._found_law,
)
if exact is not None:
    view._found_law = exact
view._refresh_version_list()
window.update()
all_count = len(view._version_checkboxes)
all_passed &= report("전체 개정본이 많이 나오는가", all_count >= 100, f"{all_count}개")
all_passed &= report(
    "처음부터 전부 꺼져 있는가",
    all_count > 0 and not any(is_on.get() for is_on, _ in view._version_checkboxes),
)
warning = view._many_versions_warning.cget("text")
all_passed &= report("많은 개정본 안내가 뜨는가", "개정본이" in warning and "개" in warning, warning)

# 전체 선택으로 한 번에 켤 수 있는지
view._are_all_versions_selected.set(True)
view._apply_select_all()
window.update()
all_passed &= report(
    "전체 선택으로 모두 켜지는가",
    all(is_on.get() for is_on, _ in view._version_checkboxes),
)

window.destroy()

print("\n" + "=" * 58)
print("통과" if all_passed else "실패 — 위 목록을 보세요")
print("=" * 58)
sys.exit(0 if all_passed else 1)
