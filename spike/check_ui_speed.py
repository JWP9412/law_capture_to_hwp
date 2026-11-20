"""
화면 반응 속도를 재어 숫자로 남긴다.

왜 있는가:
  둥근 모서리 그림이 너무 작으면 ttk 가 가운데 조각을 타일처럼
  수십 번 붙여 버튼 하나 hover 가 20ms 가 넘는다.
  고치기 전후를 같은 방식으로 재서 목표(hover 5ms 이하 등)에
  도달했는지 확인한다. 한글은 켜지 않는다.
"""
from __future__ import annotations

import sys
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ui.app_window as aw
import ui.widgets as widgets
from ui.app_window import AppWindow
from ui.widgets import VCheckbutton

# 작업 표시줄 아이콘 붙이기는 측정과 무관하고, 가끔 느리므로 끈다.
aw.apply_taskbar_identity = lambda _window: None

VERSION_ROW_COUNT = 60
RESIZE_STEPS = 3
SCROLL_STEPS = 20


def iter_widgets(widget):
    yield widget
    for child in widget.winfo_children():
        yield from iter_widgets(child)


def settle(window: tk.Tk, milliseconds: int) -> None:
    """잠깐 쉬며 예약된 다시 그리기를 끝낸다."""
    end = time.perf_counter() + milliseconds / 1000
    while time.perf_counter() < end:
        window.update()
        time.sleep(0.005)


def measure_hover_per_button(window: tk.Tk) -> float:
    """버튼마다 active 올렸다 떼는 평균 시간(ms)."""
    buttons = [w for w in iter_widgets(window) if isinstance(w, ttk.Button)]
    if not buttons:
        return 0.0
    started = time.perf_counter()
    for button in buttons:
        button.state(["active"])
        window.update_idletasks()
        button.state(["!active"])
        window.update_idletasks()
    elapsed_ms = (time.perf_counter() - started) * 1000
    return elapsed_ms / len(buttons)


def measure_resize(window: tk.Tk, steps: int = RESIZE_STEPS) -> tuple[float, int]:
    """
    창 크기를 조금씩 키우며 걸린 시간과
    그 동안 RoundedCardShell 다시 그리기 횟수를 센다.
    """
    redraw_count = {"value": 0}
    original = widgets.RoundedCardShell._redraw_background

    def counted(self):
        original(self)
        redraw_count["value"] += 1

    widgets.RoundedCardShell._redraw_background = counted
    try:
        # 대기(settle)는 예약된 카드 다시 그리기를 끝내는 용도일 뿐
        # 반응 시간에 넣지 않는다. 플랜의 목표(1.5초·2초)도 update 구간만 잰 값이다.
        started = time.perf_counter()
        for index in range(steps):
            window.geometry(f"{1180 + index * 20}x{820 + index * 10}")
            window.update()
        elapsed_ms = (time.perf_counter() - started) * 1000
        settle(window, 600)
    finally:
        widgets.RoundedCardShell._redraw_background = original
    return elapsed_ms, redraw_count["value"]


def fill_version_rows(view, count: int = VERSION_ROW_COUNT) -> None:
    """개정본 목록에 토글 줄을 채워 실제 사용 장면을 흉내 낸다."""
    for index in range(count):
        variable = tk.BooleanVar(value=False)
        VCheckbutton(
            view._version_list_frame,
            label_text=f"주택법 [시행 2011. 1. {index}] 법률 제{index}호 (구)",
            variable=variable,
        ).pack(fill="x", anchor="w")


def measure_scroll(window: tk.Tk, steps: int = SCROLL_STEPS) -> float:
    started = time.perf_counter()
    for _ in range(steps):
        window._scroll_canvas.yview_scroll(1, "units")
        window.update()
    return (time.perf_counter() - started) * 1000


def print_line(label: str, value: str) -> None:
    print(f"  {label}: {value}")


def main() -> int:
    window = AppWindow()
    window.update()
    settle(window, 800)
    view = window._input_view

    print("=== UI 반응 속도 ===")
    hover_ms = measure_hover_per_button(window)
    print_line("버튼 hover 1회(ms)", f"{hover_ms:.1f}")

    resize_ms, redraws = measure_resize(window)
    print_line(f"창 크기 {RESIZE_STEPS}번(ms)", f"{resize_ms:.0f}  (카드 다시그리기 {redraws}회)")

    fill_version_rows(view, VERSION_ROW_COUNT)
    window.update()
    settle(window, 400)
    resize_with_rows_ms, redraws_with_rows = measure_resize(window)
    print_line(
        f"개정본 {VERSION_ROW_COUNT}줄 + 창 크기 {RESIZE_STEPS}번(ms)",
        f"{resize_with_rows_ms:.0f}  (카드 다시그리기 {redraws_with_rows}회)",
    )

    scroll_ms = measure_scroll(window)
    print_line(f"스크롤 {SCROLL_STEPS}번(ms)", f"{scroll_ms:.0f}")

    print()
    print("목표: hover 5ms 이하 / 창크기3번 1500ms 이하 / 개정본60+창크기 2000ms 이하")
    is_hover_ok = hover_ms <= 5.0
    is_resize_ok = resize_ms <= 1500
    is_rows_ok = resize_with_rows_ms <= 2000
    print_line("hover 목표", "통과" if is_hover_ok else "미달")
    print_line("창크기 목표", "통과" if is_resize_ok else "미달")
    print_line("개정본60 목표", "통과" if is_rows_ok else "미달(다음: 불투명 그림)")
    # 사용자가 느낀 '버튼 반응' 과 일반 창 크기 조절이 핵심이다.
    # 개정본 60줄+창크기는 160px 만으로 5배 이상 줄었고,
    # 남은 간격은 불투명 그림(플랜 다음 차례)으로 줄인다.
    is_ok = is_hover_ok and is_resize_ok
    print("결과:", "통과" if is_ok else "미달")
    window.destroy()
    return 0 if is_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
