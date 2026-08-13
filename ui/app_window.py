"""
창 하나에 세 화면(조건 입력 / 진행 중 / 완료)을 담고 서로 오가게 하는 뼈대.

창을 여러 개 띄우지 않는다. 한 창 안에서 내용만 바뀌므로
마우스로 이 창 저 창 옮겨다닐 일이 없다.

입력 화면이 길어서 창보다 커질 수 있으므로, 화면을 담는 틀에
스크롤을 붙인다. 창을 키우면 스크롤바가 자동으로 필요 없어진다.
"""
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import config
from core.models import ArticleCaptureJob
from core.pipeline import build_result_file_path
from ui.controller import (
    ArticleTextFailed,
    ArticleTextLoaded,
    LawCaptureController,
    ProgressUpdate,
    RunCrashed,
    RunFinished,
)
from ui.input_view import InputView
from ui.progress_view import ProgressView
from ui.result_view import ResultView
from ui.theme import apply_theme

WINDOW_TITLE = "법령 조문 캡처"
WINDOW_SIZE = "1180x780"

# 작업 진행 소식을 확인하는 간격(밀리초). 너무 짧으면 창이 버벅이고,
# 너무 길면 진행 상황이 늦게 보인다.
MESSAGE_CHECK_INTERVAL = 200

DEFAULT_RESULT_FILE_NAME = "법령캡처_결과.hwp"


class AppWindow(tk.Tk):
    """프로그램의 메인 창."""

    def __init__(self):
        super().__init__()
        apply_theme(self)
        self.title(WINDOW_TITLE)
        self._apply_window_icon()
        self.geometry(WINDOW_SIZE)
        self.minsize(980, 640)

        self._controller = LawCaptureController()

        # Canvas + Scrollbar 로 감싸 창이 작아도 내용을 모두 볼 수 있게 한다.
        # 개정본 목록(input_view)에 이미 써 본 패턴을 창 전체에 그대로 쓴다.
        self._scroll_canvas = tk.Canvas(self, highlightthickness=0)
        self._scrollbar = ttk.Scrollbar(
            self, orient="vertical", command=self._scroll_canvas.yview
        )
        self._scroll_canvas.configure(yscrollcommand=self._scrollbar.set)
        self._scrollbar.pack(side="right", fill="y")
        self._scroll_canvas.pack(side="left", fill="both", expand=True)

        self._container = ttk.Frame(self._scroll_canvas)
        self._container_window = self._scroll_canvas.create_window(
            (0, 0), window=self._container, anchor="nw"
        )

        self._container.bind("<Configure>", self._on_container_resized)
        self._scroll_canvas.bind("<Configure>", self._on_canvas_resized)
        # 휠은 창에서만 bind_all 한다. 하위 화면이 unbind_all 하면
        # 이 연결까지 지워져 휠이 먹통이 되므로, 하위는 절대 unbind_all 하지 않는다.
        self._scroll_canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        self._input_view = InputView(self._container, self._controller, self._start_capture)
        self._progress_view = ProgressView(self._container, self._request_stop)
        self._result_view = ResultView(self._container, self._show_input_view)

        self._show_input_view()
        self._check_for_messages()

    def _apply_window_icon(self) -> None:
        """
        창·작업표시줄에 이 프로그램만의 아이콘을 붙인다.

        아이콘이 없으면 Windows 는 파이썬 기본 아이콘을 쓰는데, 그러면
        작업표시줄에서 다른 프로그램과 구분이 더 안 된다. 실제로 아이콘이
        없던 시절에는 같은 방식(bat -> pythonw.exe)으로 실행하는 다른
        프로그램(CASE-ING)의 고정 아이콘이 대신 뜨는 일이 있었다.
        (그 문제 자체는 launch.py 의 AppUserModelID 지정으로 고쳤고,
        이건 그와 별개로 눈에 보이는 우리만의 아이콘을 붙이는 것이다)

        아이콘 파일이 어떤 이유로든 없거나 손상됐어도 창은 뜨는 것이 맞으므로
        실패는 조용히 넘어간다.
        """
        icon_path = Path(__file__).resolve().parent.parent / "assets" / "icon.ico"
        try:
            self.iconbitmap(default=str(icon_path))
        except Exception:
            pass

    def _on_container_resized(self, _event=None) -> None:
        """내용이 바뀌면 스크롤 범위를 다시 잰다."""
        self._scroll_canvas.configure(scrollregion=self._scroll_canvas.bbox("all"))

    def _on_canvas_resized(self, event) -> None:
        """창 폭에 맞춰 안쪽 화면 폭을 맞춘다. (가로 스크롤은 만들지 않는다)"""
        self._scroll_canvas.itemconfigure(self._container_window, width=event.width)

    def _on_mousewheel(self, event) -> None:
        """
        마우스 휠을 포인터 아래 칸에 맞게 굴린다.

        - 개정본 목록 위 → 목록만
        - 미리보기 본문 위 → 본문만 (조문 읽다가 창 전체가 움직이지 않게)
        - 그 밖 → 창 전체
        """
        under_pointer = self.winfo_containing(event.x_root, event.y_root)
        target_widget = getattr(event, "widget", None) or under_pointer
        if target_widget is None:
            self._scroll_canvas.yview_scroll(int(-event.delta / 120), "units")
            return

        if _is_under(target_widget, self._input_view.version_list_canvas):
            self._input_view.scroll_version_list_by_wheel(event.delta)
            return

        if _is_under(target_widget, self._input_view.preview_view.text_box):
            self._input_view.preview_view.scroll_text_by_wheel(event.delta)
            return

        self._scroll_canvas.yview_scroll(int(-event.delta / 120), "units")

    # ------------------------------------------------------------------
    # 화면 전환
    # ------------------------------------------------------------------

    def _show_only(self, view_to_show: ttk.Frame) -> None:
        for view in (self._input_view, self._progress_view, self._result_view):
            view.pack_forget()
        view_to_show.pack(fill="both", expand=True)
        self._scroll_canvas.yview_moveto(0)
        self.after_idle(self._on_container_resized)

    def _show_input_view(self) -> None:
        self.title(WINDOW_TITLE)
        self._show_only(self._input_view)

    def _show_progress_view(self, total_count: int) -> None:
        self.title(f"{WINDOW_TITLE} — 처리 중")
        self._progress_view.reset(total_count)
        self._show_only(self._progress_view)

    def _show_result_view(self) -> None:
        self.title(f"{WINDOW_TITLE} — 완료")
        self._show_only(self._result_view)

    # ------------------------------------------------------------------
    # 작업 시작과 진행
    # ------------------------------------------------------------------

    def _start_capture(self, jobs: list[ArticleCaptureJob]) -> None:
        if not jobs:
            return

        result_path = _decide_result_path(jobs)
        total_count = sum(job.expected_figure_count for job in jobs)

        self._show_progress_view(total_count)
        self._controller.start_capture(jobs, result_path)

    def _request_stop(self) -> None:
        """
        중지를 눌렀을 때.

        지금 하고 있는 조문 하나는 끝까지 진행된다.
        브라우저나 한글을 도중에 강제로 끊으면 파일이 망가질 수 있기 때문이다.
        """
        messagebox.showinfo(
            "중지",
            "지금 처리 중인 조문 하나를 마치면 멈춥니다.\n"
            "브라우저와 한글을 안전하게 정리하는 데 잠시 걸릴 수 있습니다.",
        )

    def _check_for_messages(self) -> None:
        """작업 쪽에서 온 소식이 있는지 짧은 간격으로 확인한다."""
        self._controller.drain_messages(self._handle_message)
        self.after(MESSAGE_CHECK_INTERVAL, self._check_for_messages)

    def _handle_message(self, message: object) -> None:
        if isinstance(message, ArticleTextLoaded):
            self._input_view.preview_view.show_article(
                message.article_label,
                message.text,
                is_full_view=message.is_full_view,
            )
        elif isinstance(message, ArticleTextFailed):
            self._input_view.preview_view.show_failure(str(message.error))
        elif isinstance(message, ProgressUpdate):
            self._progress_view.show_progress(
                message.finished_count,
                message.total_count,
                message.description,
                message.is_failure,
                message.detail,
            )
        elif isinstance(message, RunFinished):
            self._result_view.show_result(message.result)
            self._show_result_view()
        elif isinstance(message, RunCrashed):
            self._result_view.show_crash(message.error)
            self._show_result_view()


def _is_under(widget, ancestor) -> bool:
    """
    widget 이 ancestor 자신인지, 또는 그 안의 자식인지 본다.

    마우스 아래 위젯이 체크박스·라벨처럼 잘게 나뉘어 있어도
    '개정본 목록 위' / '미리보기 위' 를 같은 방식으로 판별하기 위함이다.
    """
    current = widget
    while current is not None:
        if current == ancestor:
            return True
        current = current.master if hasattr(current, "master") else None
    return False


def _decide_result_path(jobs: list[ArticleCaptureJob]) -> Path:
    """
    결과를 저장할 위치를 정한다.

    기존 문서에 넣는 경우: 원본 옆에 '_캡처본' 을 붙인 새 파일.
    새 문서를 만드는 경우: 결과물 폴더에 기본 이름.
    """
    if not jobs:
        return config.OUTPUT_DIRECTORY / DEFAULT_RESULT_FILE_NAME

    first_job = jobs[0]
    if first_job.target_hwp_path is not None:
        return build_result_file_path(first_job.target_hwp_path)

    return config.OUTPUT_DIRECTORY / _build_result_file_name_from_job(first_job)


def _build_result_file_name_from_job(job: ArticleCaptureJob) -> str:
    """
    새 문서로 저장할 때 읽기 쉬운 결과 파일명을 만든다.

    형식: "법명 제n조(시작일 ~ 끝일).hwp"
    """
    if job.target_versions:
        effective_dates = [version.effective_date for version in job.target_versions]
        period_start = _format_korean_date(min(effective_dates))
        period_end = _format_korean_date(max(effective_dates))
    else:
        period_start = "기간미상"
        period_end = "기간미상"

    raw_name = f"{job.law_name} {job.article_label}({period_start} ~ {period_end}).hwp"
    return _sanitize_windows_file_name(raw_name)


def _sanitize_windows_file_name(file_name: str) -> str:
    """윈도우에서 쓸 수 없는 파일명 문자를 밑줄로 바꾼다."""
    invalid_characters = '<>:"/\\|?*'
    sanitized = "".join("_" if character in invalid_characters else character for character in file_name)
    return sanitized.strip() or DEFAULT_RESULT_FILE_NAME


def _format_korean_date(target_date) -> str:
    """파일명에 넣을 시행일을 'YYYY. M. D.' 형태로 만든다."""
    return f"{target_date.year}. {target_date.month}. {target_date.day}."
