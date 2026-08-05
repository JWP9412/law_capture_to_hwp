"""
화면 3 — 작업이 끝난 뒤 결과를 보여주는 화면.

실패한 것이 있으면 '어느 조문이 왜 안 됐는지' 를 한국어 문장으로 보여준다.
오류 코드 같은 것은 보여주지 않는다. 자세한 내용은 기록 파일에만 남는다.
"""
import os
import subprocess
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from core.models import CaptureRunResult


class ResultView(ttk.Frame):
    """결과 화면."""

    def __init__(self, parent, on_restart_requested):
        super().__init__(parent, padding=12)
        self._result: CaptureRunResult | None = None

        self._summary_label = ttk.Label(self, text="", style="CardTitle.TLabel")
        self._summary_label.pack(anchor="w", pady=(0, 8))

        # 실패 목록은 실패가 있을 때만 보여준다.
        # 자리는 요약 바로 아래(파일 안내와 버튼보다 위)에 잡는다.
        self._failure_frame = ttk.LabelFrame(
            self, text="확인이 필요한 항목", padding=8, style="Card.TLabelframe"
        )
        self._failure_box = tk.Text(self._failure_frame, height=8, state="disabled", wrap="word")
        self._failure_box.pack(fill="both", expand=True)

        self._file_label = ttk.Label(self, text="", style="Hint.TLabel", wraplength=900)
        self._file_label.pack(anchor="w", pady=6)

        ttk.Separator(self, orient="horizontal").pack(fill="x", pady=(10, 6))
        button_row = ttk.Frame(self)
        button_row.pack(fill="x")
        self._open_document_button = ttk.Button(
            button_row, text="결과 한글 파일 열기", command=self._open_result_document
        )
        self._open_document_button.pack(side="right", padx=4)
        ttk.Button(
            button_row, text="출력 폴더 열기", command=self._open_output_folder
        ).pack(side="right", padx=4)
        ttk.Button(button_row, text="처음으로", command=on_restart_requested).pack(
            side="left", padx=4
        )

    def show_result(self, result: CaptureRunResult) -> None:
        self._result = result
        self._summary_label.config(text=result.summary_for_display)
        self._show_failures(result)
        self._show_result_file(result)

    def show_crash(self, error: Exception) -> None:
        """작업 전체가 멈췄을 때. 이때는 결과 파일이 없다."""
        self._result = None
        self._summary_label.config(text="작업을 끝내지 못했습니다")
        self._show_failure_frame()
        self._write_failure_lines([str(error)])
        self._file_label.config(text="")
        self._open_document_button.config(state="disabled")

    def _show_failures(self, result: CaptureRunResult) -> None:
        if not result.has_any_failure:
            self._failure_frame.pack_forget()
            return

        self._show_failure_frame()
        self._write_failure_lines(
            [failure.message_for_display for failure in result.failed]
        )

    def _show_failure_frame(self) -> None:
        """
        실패 목록을 요약 바로 아래에 끼워 넣는다.

        before 를 지정하지 않으면 화면 맨 아래(버튼 뒤)에 붙어버린다.
        읽는 순서가 '무엇이 잘못됐나 -> 어떻게 할까' 가 되도록 위쪽에 둔다.
        """
        self._failure_frame.pack(fill="both", expand=True, before=self._file_label)

    def _write_failure_lines(self, lines: list[str]) -> None:
        self._failure_box.configure(state="normal")
        self._failure_box.delete("1.0", tk.END)
        for line in lines:
            self._failure_box.insert(tk.END, f"× {line}\n\n")
        self._failure_box.configure(state="disabled")

    def _show_result_file(self, result: CaptureRunResult) -> None:
        has_document = bool(result.succeeded and result.result_hwp_path)
        self._open_document_button.config(state="normal" if has_document else "disabled")
        self._file_label.config(
            text=f"결과 파일: {result.result_hwp_path}" if has_document else ""
        )

    def _open_result_document(self) -> None:
        if self._result and self._result.result_hwp_path:
            _open_in_explorer(self._result.result_hwp_path)

    def _open_output_folder(self) -> None:
        import config

        _open_in_explorer(config.OUTPUT_DIRECTORY)


def _open_in_explorer(path: Path) -> None:
    """윈도우 탐색기나 기본 프로그램으로 파일·폴더를 연다."""
    try:
        os.startfile(str(path))
    except OSError:
        subprocess.run(["explorer", str(path)], check=False)
