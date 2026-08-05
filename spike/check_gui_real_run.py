"""
화면에서 [실행] 을 눌러 한글 파일이 실제로 만들어지는지 확인한다.

**이 검증이 없어서 큰 문제를 놓쳤다.**
지금까지의 검증은 두 갈래였는데 둘 다 실제 실행을 지나지 않았다.
  - 명령줄 실행: 흐름이 하나뿐이라 윈도우 프로그램 조작 준비가 저절로 됨
  - 화면 검증:   버튼 연결과 화면 전환만 확인, 실제 실행은 안 함
그래서 '화면에서 [실행] 을 누르면 한글이 아예 안 열리는' 문제를 사용자가 먼저 겪었다.

이 스크립트는 사용자가 실제로 하는 것과 똑같이,
화면을 띄우고 조건을 채우고 [실행] 을 눌러 결과 파일이 나올 때까지 확인한다.
"""
import sys
import time
import tkinter as tk
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from ui.app_window import AppWindow
from ui.controller import RunCrashed, RunFinished

# 사용자가 실제로 실패를 겪은 조건 그대로
LAW_NAME = "주택법"
REFERENCE_DATE = "2011-01-28"
ARTICLE_NUMBER = "39"
UNDERLINE_PHRASE = "공급질서 교란 금지"

RESULT_PATH = config.OUTPUT_DIRECTORY / "화면실행시험.hwp"
MAXIMUM_WAIT_IN_SECONDS = 300


def report(label: str, is_ok: bool, detail: str = "") -> bool:
    print(f"  [{'OK  ' if is_ok else '실패'}] {label}" + (f"  -- {detail}" if detail else ""))
    return is_ok


def set_entry(entry: tk.Entry, text: str) -> None:
    entry.delete(0, tk.END)
    entry.insert(0, text)


def wait_for_result(window: AppWindow) -> object | None:
    """
    작업이 끝날 때까지 창을 돌리며 기다린다.

    창이 소식을 받아 화면을 갱신하는 구조를 그대로 쓴다.
    (사람이 창을 보고 있는 것과 같은 상태를 만든다)
    """
    finished_message: list[object] = []
    original_handler = window._handle_message

    def watch(message: object) -> None:
        original_handler(message)
        if isinstance(message, (RunFinished, RunCrashed)):
            finished_message.append(message)

    window._handle_message = watch

    deadline = time.time() + MAXIMUM_WAIT_IN_SECONDS
    while time.time() < deadline and not finished_message:
        window.update()
        time.sleep(0.1)

    return finished_message[0] if finished_message else None


print("=" * 62)
print("화면에서 [실행] 을 눌러 끝까지 가는지 확인")
print("=" * 62)
print(f"조건: {LAW_NAME} {REFERENCE_DATE} 제{ARTICLE_NUMBER}조")
print("브라우저와 한글이 저절로 열렸다 닫힙니다. 잠시 기다려 주세요.\n")

RESULT_PATH.unlink(missing_ok=True)

window = AppWindow()
window.update()
view = window._input_view
all_passed = True

# 1) 사람이 하듯 조건을 채운다
set_entry(view._law_name_entry, LAW_NAME)
view._search_law()
window.update()
all_passed &= report("법령을 찾았는가", view._found_law is not None, str(view._found_law))

view._mode.set("특정 시점 하나")
view._apply_timing_mode_layout()
set_entry(view._reference_date_entry, REFERENCE_DATE)
view._refresh_version_list()
window.update()
all_passed &= report("개정본을 찾았는가", len(view._version_checkboxes) >= 1,
                     str(view._version_checkboxes[0][1]) if view._version_checkboxes else "없음")

set_entry(view._article_entry, ARTICLE_NUMBER)
set_entry(view._underline_entry, UNDERLINE_PHRASE)
set_entry(view._hwp_path_entry, "")
view._add_job()
window.update()
all_passed &= report("조건을 목록에 담았는가", len(view._jobs) == 1)

# 2) [실행] 을 누른다
print("\n  실행 중… (브라우저와 한글이 뜹니다)")
window._start_capture(list(view._jobs))
outcome = wait_for_result(window)

# 3) 결과를 확인한다
print()
if outcome is None:
    all_passed &= report("작업이 끝났는가", False, f"{MAXIMUM_WAIT_IN_SECONDS}초 안에 안 끝남")
elif isinstance(outcome, RunCrashed):
    all_passed &= report("작업이 끝났는가", False, f"중간에 멈춤: {outcome.error}")
else:
    result = outcome.result
    all_passed &= report("작업이 끝났는가", True, result.summary_for_display)
    for failure in result.failed:
        print(f"          실패 내용: {failure.message_for_display}")
    all_passed &= report("실패 없이 끝났는가", not result.has_any_failure)

    made_path = result.result_hwp_path
    all_passed &= report(
        "한글 파일이 실제로 만들어졌는가",
        made_path is not None and made_path.exists(),
        f"{made_path.stat().st_size:,}바이트" if made_path and made_path.exists() else str(made_path),
    )

window.destroy()

print("\n" + "=" * 62)
print("통과 — 화면에서 실행이 끝까지 됩니다" if all_passed else "실패 — 위 목록을 보세요")
print("=" * 62)
sys.exit(0 if all_passed else 1)
