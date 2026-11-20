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
from ui.taskbar_identity import apply_taskbar_identity
from ui import theme
from ui.theme import apply_theme

WINDOW_TITLE = "법령 조문 캡처"
WINDOW_SIZE = "1180x820"
HEADER_HEIGHT = 64

# 작업 진행 소식을 확인하는 간격(밀리초). 너무 짧으면 창이 버벅이고,
# 너무 길면 진행 상황이 늦게 보인다.
MESSAGE_CHECK_INTERVAL = 200

# 창 폭이 이만큼(픽셀) 이상 벌어질 때만 안쪽 화면 폭을 다시 맞춘다.
# 1픽셀마다 맞추면 둥근 버튼·입력칸이 매번 다시 늘어나 버벅인다.
LAYOUT_WIDTH_STEP_PIXELS = 10

# 손을 떼면 최종 폭을 한 번 더 맞추기까지의 대기(밀리초).
LAYOUT_WIDTH_FINALIZE_DELAY_MS = 100

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
        # 캡처를 누를 때 창이 이미 최소화돼 있었는지.
        # 끝났을 때 창을 되돌릴지 말지 가리는 데만 쓴다. (아래 _restore_window_after_capture)
        self._was_minimized_when_capture_started = False

        # 머리 띠는 입력·진행·완료 세 화면 공통으로 맨 위에 둔다.
        # 화면을 바꿔 끼우는 스크롤 틀 '바깥' 이어야 스크롤해도 안 사라진다.
        self._build_header_band()

        # Canvas + Scrollbar 로 감싸 창이 작아도 내용을 모두 볼 수 있게 한다.
        # 개정본 목록(input_view)에 이미 써 본 패턴을 창 전체에 그대로 쓴다.
        # 화면 맨 아래에 항상 떠 있는 자리. 스크롤 영역 '바깥' 이다.
        # [담기]·[실행] 처럼 자주 누르는 버튼을 여기 두면, 창을 줄이거나
        # 스크롤을 어디에 두어도 늘 보인다.
        # pack 순서가 중요하다: 아래쪽 자리는 늘어나는 캔버스보다 먼저 붙여야
        # 창이 작아져도 밀려나지 않는다.
        self._footer = ttk.Frame(self)
        self._footer.pack(side="bottom", fill="x")

        self._scroll_canvas = tk.Canvas(
            self,
            highlightthickness=0,
            background=theme.WINDOW_BACKGROUND,
        )
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
        # 안쪽 화면 폭을 마지막으로 맞춰 둔 값. 10픽셀 간격 비교에 쓴다.
        self._applied_container_width = 0
        self._pending_container_width = 0
        self._pending_width_after_id = None
        # 휠은 창에서만 bind_all 한다. 하위 화면이 unbind_all 하면
        # 이 연결까지 지워져 휠이 먹통이 되므로, 하위는 절대 unbind_all 하지 않는다.
        self._scroll_canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        self._input_view = InputView(
            self._container, self._controller, self._start_capture, self._footer
        )
        self._progress_view = ProgressView(self._container, self._request_stop)
        self._result_view = ResultView(self._container, self._show_input_view)

        self._show_input_view()
        self._check_for_messages()

        # 창이 다 만들어진 뒤에 적어야 한다. (창 번호가 필요하므로)
        # 이것이 있어야 창을 우클릭해 고정해도 아이콘·실행이 제대로 된다.
        apply_taskbar_identity(self)

    def _build_header_band(self) -> None:
        """
        창 맨 위 흰 머리 띠.

        국가법령정보센터 머리 영역(흰 바탕 + 두 줄 제목)을 따왔다.
        정부 상징(태극 로고)은 사용 규정이 있어 넣지 않았다.
        왼쪽은 프로그램 이름, 오른쪽은 자료 출처와 버전을 보여
        '법령 관련 프로그램' 임을 한눈에 알리려는 것이다.
        """
        header = tk.Frame(
            self,
            background=theme.CARD_BACKGROUND,
            height=HEADER_HEIGHT,
            highlightthickness=0,
        )
        header.pack(side="top", fill="x")
        header.pack_propagate(False)

        inner = ttk.Frame(header, style="Card.TFrame", padding=(16, 0))
        inner.pack(fill="both", expand=True)

        # 진남 세로 막대 — 사이트 로고 자리 대신 쓰는 포인트 색.
        accent = tk.Frame(inner, background=theme.ACCENT_BLUE, width=4, height=34)
        accent.pack(side="left", padx=(0, 12))
        accent.pack_propagate(False)

        brand = ttk.Frame(inner, style="Card.TFrame")
        brand.pack(side="left")
        ttk.Label(
            brand,
            text="건설 하자소송 준비서면용",
            style="Header.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            brand,
            text=WINDOW_TITLE,
            style="HeaderTitle.TLabel",
        ).pack(anchor="w")

        meta = ttk.Frame(inner, style="Card.TFrame")
        meta.pack(side="right")
        source_row = ttk.Frame(meta, style="Card.TFrame")
        source_row.pack(anchor="e")
        ttk.Label(
            source_row,
            text="자료 출처: ",
            style="Header.TLabel",
        ).pack(side="left")
        ttk.Label(
            source_row,
            text="국가법령정보센터",
            style="HeaderLink.TLabel",
        ).pack(side="left")
        ttk.Label(
            meta,
            text=f"버전 {config.APP_VERSION}",
            style="Header.TLabel",
        ).pack(anchor="e")

        # 머리 띠와 본문을 가르는 가는 선 (사이트 머리 아래 구분선).
        tk.Frame(self, background=theme.CARD_BORDER, height=1).pack(
            side="top", fill="x"
        )

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
        """
        창 폭에 맞춰 안쪽 화면 폭을 맞춘다. (가로 스크롤은 만들지 않는다)

        10픽셀 이상 벌어질 때만 바로 맞추고, 손을 떼면 최종 폭을 한 번 더 맞춘다.
        매 픽셀마다 맞추면 둥근 버튼·입력칸이 전부 다시 늘어나 느리다.
        """
        new_width = int(event.width)
        self._pending_container_width = new_width
        if abs(new_width - self._applied_container_width) >= LAYOUT_WIDTH_STEP_PIXELS:
            self._apply_container_width(new_width)
        if self._pending_width_after_id is not None:
            self.after_cancel(self._pending_width_after_id)
        self._pending_width_after_id = self.after(
            LAYOUT_WIDTH_FINALIZE_DELAY_MS,
            self._finalize_container_width,
        )

    def _finalize_container_width(self) -> None:
        self._pending_width_after_id = None
        self._apply_container_width(self._pending_container_width)

    def _apply_container_width(self, width: int) -> None:
        if width == self._applied_container_width:
            return
        self._applied_container_width = width
        self._scroll_canvas.itemconfigure(self._container_window, width=width)

    def _on_mousewheel(self, event) -> None:
        """
        마우스 휠을 포인터 아래 칸에 맞게 굴린다.

        - 개정본 목록 위 + 목록이 김 → 목록만
        - 개정본 목록 위 + 목록이 짧음 → 창 전체
        - 미리보기 본문 위 + 본문이 김 → 본문만
        - 미리보기 본문 위 + 본문이 짧음 → 창 전체
        - 그 밖 → 창 전체

        포인터 위치를 먼저 보는 이유:
          휠은 포커스가 아닌 '마우스 아래' 기준이어야 한다.
          event.widget 만 보면 다른 칸에 포커스가 있을 때 엉뚱한 곳으로 간다.
        """
        under_pointer = self.winfo_containing(event.x_root, event.y_root)
        target_widget = under_pointer or getattr(event, "widget", None)
        if target_widget is None:
            self._scroll_canvas.yview_scroll(int(-event.delta / 120), "units")
            return

        if _is_under(target_widget, self._input_view.version_list_canvas):
            if self._input_view.can_scroll_version_list():
                self._input_view.scroll_version_list_by_wheel(event.delta)
                return
            # 목록이 짧으면 아래 창 전체 스크롤로 넘어간다.

        if _is_under(target_widget, self._input_view.preview_view.text_box):
            if self._input_view.preview_view.can_scroll_text():
                self._input_view.preview_view.scroll_text_by_wheel(event.delta)
                return
            # 본문이 짧으면 아래 창 전체 스크롤로 넘어간다.

        self._scroll_canvas.yview_scroll(int(-event.delta / 120), "units")

    # ------------------------------------------------------------------
    # 화면 전환
    # ------------------------------------------------------------------

    def _show_only(self, view_to_show: ttk.Frame) -> None:
        for view in (self._input_view, self._progress_view, self._result_view):
            view.pack_forget()
        view_to_show.pack(fill="both", expand=True)

        # 하단 고정 바(담기·실행)는 조건 입력 화면에서만 필요하다.
        # 진행·완료 화면에는 각자의 버튼이 있으므로 숨긴다.
        # 다시 붙일 때는 before= 로 '캔버스보다 앞' 순서를 지켜야 한다.
        self._footer.pack_forget()
        if view_to_show is self._input_view:
            self._footer.pack(side="bottom", fill="x", before=self._scrollbar)
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

    def _restore_window_after_capture(self) -> None:
        """
        캡처가 끝난 뒤, 우리 창이 작업표시줄로 내려갔다면 다시 펼친다.

        왜 이 함수가 필요한가:
          코드 어디에도 iconify(최소화) 를 부르지 않는다. 그런데도 한글을
          뒤에서 켜고 끄는 동안 윈도우가 포커스를 뺏기며, 우리 창이
          최소화되거나 다른 창 뒤로 숨을 수 있다. 완료 화면으로 바꿔 놓고도
          창이 안 보이면 사용자는 끝난 줄 모르고 기다리게 된다.

        왜 무조건 deiconify 하지 않는가:
          캡처를 시작하기 전에 사용자가 이미 창을 최소화해 둔 경우에는
          그 뜻을 존중한다. 시작 당시에는 펼쳐 있었는데 끝났을 때
          최소화돼 있다면, 그건 우리가 켠 한글·브라우저 쪽 부작용으로 보고
          되돌린다.

        focus_force 는 쓰지 않는다. 다른 창에서 작업 중일 때 입력 포커스까지
        뺏으면 방해가 된다. lift 와 아주 잠깐의 맨 앞 표시만으로 창을 보이게 한다.
        """
        if self._was_minimized_when_capture_started:
            return
        try:
            if self.state() == "iconic":
                self.deiconify()
            self.lift()
            # Windows 는 포커스를 뺏긴 뒤 lift 만으로는 창을 앞으로
            # 안 올리는 경우가 있다. 맨 앞 표시를 아주 짧게 켰다 끄면
            # 입력 포커스는 뺏지 않으면서 창만 보이게 할 수 있다.
            self.attributes("-topmost", True)
            self.after(50, lambda: self.attributes("-topmost", False))
        except tk.TclError:
            # 창이 이미 닫히는 중이면 상태 조회·변경이 실패할 수 있다.
            pass

    # ------------------------------------------------------------------
    # 작업 시작과 진행
    # ------------------------------------------------------------------

    def _start_capture(self, jobs: list[ArticleCaptureJob]) -> None:
        if not jobs:
            return

        result_path = _decide_result_path(jobs)
        total_count = sum(job.expected_figure_count for job in jobs)

        # 시작 전에 이미 최소화돼 있었는지만 기억한다.
        # 끝났을 때 '우리가 망가뜨린 최소화' 와 '사용자가 원한 최소화' 를 가르기 위함이다.
        try:
            self._was_minimized_when_capture_started = self.state() == "iconic"
        except tk.TclError:
            self._was_minimized_when_capture_started = False

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
            # stage.value 는 「조문 내려받는 중」처럼 한국어 단계 이름이다.
            # 화면은 법령·한글을 모르고, 컨트롤러가 넘긴 글자만 기록 칸에 붙인다.
            self._progress_view.show_progress(
                message.finished_count,
                message.total_count,
                message.description,
                message.is_failure,
                message.detail,
                stage_label=message.stage.value,
                is_item_done=message.is_item_done,
            )
        elif isinstance(message, RunFinished):
            self._result_view.show_result(message.result)
            self._show_result_view()
            self._restore_window_after_capture()
        elif isinstance(message, RunCrashed):
            self._result_view.show_crash(message.error)
            self._show_result_view()
            self._restore_window_after_capture()


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
