"""
화면 2 — 작업이 도는 동안 진행 상황을 보여주는 화면.

화면이 멈춘 것처럼 보이지 않게 하는 것이 이 화면의 목적이다.
지금 몇 번째 작업의 어느 단계인지를 항상 한 줄로 보여준다.
"""
import tkinter as tk
from tkinter import ttk

SUCCESS_MARK = "○"
FAILURE_MARK = "×"


class ProgressView(ttk.Frame):
    """진행 상황 화면."""

    def __init__(self, parent, on_stop_requested):
        super().__init__(parent, padding=12)

        ttk.Label(self, text="처리 중입니다", style="CardTitle.TLabel").pack(
            anchor="w", pady=(0, 8)
        )

        self._progress_bar = ttk.Progressbar(self, mode="determinate", length=520)
        self._progress_bar.pack(fill="x")

        self._counter_label = ttk.Label(self, text="")
        self._counter_label.pack(anchor="w", pady=4)

        ttk.Label(
            self,
            text="브라우저 창과 한글이 저절로 열렸다 닫힙니다. 정상 동작이니 그동안 컴퓨터를 건드리지 마세요.",
            style="Hint.TLabel",
            wraplength=900,
        ).pack(anchor="w", pady=(0, 8))

        log_frame = ttk.LabelFrame(self, text="진행 기록", padding=8, style="Card.TLabelframe")
        log_frame.pack(fill="both", expand=True)

        self._log_box = tk.Text(log_frame, height=18, state="disabled", wrap="word")
        scrollbar = ttk.Scrollbar(log_frame, command=self._log_box.yview)
        self._log_box.configure(yscrollcommand=scrollbar.set)
        self._log_box.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._log_box.tag_configure("failure", foreground="red")

        ttk.Separator(self, orient="horizontal").pack(fill="x", pady=(10, 6))
        action_row = ttk.Frame(self)
        action_row.pack(fill="x")
        ttk.Button(action_row, text="중지", command=on_stop_requested).pack(side="right")

    def reset(self, total_count: int) -> None:
        """새 작업을 시작할 때 화면을 처음 상태로 되돌린다."""
        self._progress_bar.configure(maximum=total_count, value=0)
        self._counter_label.config(text=f"0 / {total_count} 건")
        self._log_box.configure(state="normal")
        self._log_box.delete("1.0", tk.END)
        self._log_box.configure(state="disabled")

    def show_progress(
        self, finished_count: int, total_count: int, description: str,
        is_failure: bool, detail: str,
    ) -> None:
        """작업 하나가 끝날 때마다 진행바와 기록을 갱신한다."""
        self._progress_bar.configure(value=finished_count)
        self._counter_label.config(text=f"{finished_count} / {total_count} 건")

        mark = FAILURE_MARK if is_failure else SUCCESS_MARK
        line = f"{mark} {description}"
        if detail:
            line += f"\n     {detail}"

        self._append_log_line(line, "failure" if is_failure else "")

    def _append_log_line(self, line: str, tag: str) -> None:
        self._log_box.configure(state="normal")
        self._log_box.insert(tk.END, line + "\n", tag)
        self._log_box.see(tk.END)
        self._log_box.configure(state="disabled")
