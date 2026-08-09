"""
프로그램을 켤 때 공통으로 거치는 코드.

.pyw / 실행.bat 둘 다 여기를 호출한다.
pythonw 는 검은 창이 없어서 오류 메시지도 안 보이므로,
실패하면 작은 안내 창과 로그 파일을 남긴다.
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path


def _show_startup_error(error_message: str, log_path: Path) -> None:
    """pythonw 로 실행될 때 사용자에게 오류를 알린다."""
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "법령 캡처 — 실행 오류",
            "프로그램을 시작하지 못했습니다.\n\n"
            f"{error_message}\n\n"
            f"자세한 내용: {log_path}",
        )
        root.destroy()
    except Exception:
        # tkinter 마저 실패하면 로그 파일만 남긴다.
        pass


def launch() -> None:
    """메인 창을 띄운다. 실패하면 예외를 잡아 로그·안내 창을 남긴다."""
    project_root = Path(__file__).resolve().parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    try:
        from main import main

        main()
    except Exception as error:
        log_path = project_root / "실행_오류.log"
        log_path.write_text(traceback.format_exc(), encoding="utf-8")
        _show_startup_error(str(error), log_path)
        raise SystemExit(1) from error
