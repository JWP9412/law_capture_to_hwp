"""검색 결과를 목록에서 고를 수 있는지 확인하고 화면 사진을 찍는다."""
import sys
import tkinter as tk
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import ImageGrab

import config
from ui.app_window import AppWindow

SCREENSHOT_PATH = config.OUTPUT_DIRECTORY / "화면" / "화면1_검색결과선택.png"


def take_screenshot(window: tk.Tk, path: Path) -> Path:
    window.update()
    window.lift()
    window.update_idletasks()
    left, top = window.winfo_rootx(), window.winfo_rooty()
    box = (left, top, left + window.winfo_width(), top + window.winfo_height())
    path.parent.mkdir(parents=True, exist_ok=True)
    ImageGrab.grab(bbox=box).save(path)
    return path


window = AppWindow()
window.update()
view = window._input_view

print("=== 여러 건이 나오는 검색어로 확인 ===")
view._law_name_entry.insert(0, "공동")
view._search_law()
window.update()

print(f"  찾은 건수: {len(view._candidates)}")
print(f"  목록에 채워진 개수: {len(view._law_picker.cget('values'))}")
print(f"  목록 상태: {view._law_picker.cget('state')}")
print(f"  기본 선택: {view._law_picker.get()[:46]}")
print(f"  안내 문구: {view._search_status_label.cget('text')}")

print("\n=== 다른 항목을 골랐을 때 ===")
before = str(view._found_law)
view._law_picker.current(3)
view._on_law_chosen()
window.update()
after = str(view._found_law)
print(f"  고르기 전: {before[:44]}")
print(f"  고른 뒤:   {after[:44]}")
print(f"  바뀌었는가: {'예' if before != after else '아니오'}")
print(f"  개정본 목록이 다시 채워졌는가: {len(view._version_checkboxes)}개")

print("\n=== 못 찾는 이름을 넣었을 때 ===")
view._law_name_entry.delete(0, tk.END)
view._law_name_entry.insert(0, "있을리없는법률")
view._search_law()
window.update()
print(f"  목록 상태: {view._law_picker.cget('state')}  (disabled 여야 정상)")
print(f"  안내 문구: {view._search_status_label.cget('text')[:60]}")

# 사진은 정상 검색 상태로 되돌린 뒤에 찍는다.
# 목록을 펼친 채로 찍으면 창 밖으로 떠서 뒤쪽 화면까지 같이 찍히므로 접어둔 상태로 찍는다.
view._law_name_entry.delete(0, tk.END)
view._law_name_entry.insert(0, "공동주택")
view._search_law()
print(f"\n사진: {take_screenshot(window, SCREENSHOT_PATH)}")

window.destroy()
