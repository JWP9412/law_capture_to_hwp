"""
화면 1 — 조건을 입력하고 작업 목록에 담는 화면.

이 파일은 '보여주기' 와 '입력받기' 만 한다.
법령을 실제로 찾는 일은 controller 에게 부탁한다.
"""
import tkinter as tk
import webbrowser
from datetime import date
import os
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from config import (
    InsertionMode,
    OUTPUT_DIRECTORY,
    underline_color_for_name,
    preview_highlight_for_name,
    UNDERLINE_COLOR_CHOICES,
    DEFAULT_UNDERLINE_COLOR_NAME,
)
from core.article_number import (
    ArticleNumber,
    append_article_to_entry_text,
    build_article_range_label,
    format_article_numbers_for_entry,
    format_article_for_entry,
    parse_article_numbers,
    step_to_adjacent_article_number,
)
from core.capture_set_memory import (
    CaptureMemoryItem,
    CaptureMemoryNameChange,
    build_name_change_notice,
)
from core.errors import LawCaptureError
from core.favorites import FavoriteLaw
from core.law_source import law_names_differ_beyond_spacing
from core.models import ArticleCaptureJob, LawVersion
from ui.capture_set_memory_dialog import CaptureSetMemoryDialog
from ui.favorites_dialog import FavoritesSettingsDialog
from ui.preview_view import PreviewView
from ui import theme
from ui.widgets import HintEntry, StepCard, VCheckbutton, install_auto_wrap

PERIOD_MODE = "기간 안의 모든 개정본"
SINGLE_DATE_MODE = "특정 시점 하나"
ALL_TIME_MODE = "전체 기간"

# 개정본 목록이 창을 밀어내지 않도록 목록만 스크롤되게 한다.
# 「주택법」처럼 172개가 나와도 창 크기는 그대로다.
VERSION_LIST_VISIBLE_HEIGHT_IN_PIXELS = 140

# 이 개수 이상이면 '필요한 것만 체크하세요' 안내를 눈에 띄게 보여준다.
MANY_VERSIONS_WARNING_THRESHOLD = 20

# 개정본 목록 아래 안내. 처음엔 전부 해제돼 있으므로 '체크하라' 고 알린다.
VERSION_LIST_HINT = "그림으로 만들 개정본을 체크해 주세요. (처음엔 전부 꺼져 있습니다)"

# '조문 번호' · '빨간 밑줄' 처럼 입력칸 왼쪽 이름표의 폭(글자 수).
# 두 줄의 입력칸 왼쪽이 나란히 서도록 같은 값을 쓴다.
LABEL_COLUMN_WIDTH = 8

MODE_FIND_BUTTON_LABELS = {
    SINGLE_DATE_MODE: "그 시점 판 찾기",
    PERIOD_MODE: "개정본 찾기",
    ALL_TIME_MODE: "전체 개정본 찾기",
}


class InputView(ttk.Frame):
    """조건 입력 화면."""

    def __init__(self, parent, controller, on_start_requested, footer_parent):
        super().__init__(parent, padding=12)
        self._controller = controller
        self._on_start_requested = on_start_requested

        # 하단 고정 바를 담을 자리. 스크롤 영역 '밖' 이라야 창을 줄이거나
        # 스크롤을 올려도 버튼이 항상 보인다. (창이 만들어 넘겨준다)
        self._footer_parent = footer_parent

        self._found_law = None
        self._candidates: list = []  # 검색으로 찾은 법령 후보들
        self._version_checkboxes: list[tuple[tk.BooleanVar, LawVersion]] = []
        self._jobs: list[ArticleCaptureJob] = []
        self._underline_phrases: list[str] = []
        self._favorites: list[FavoriteLaw] = []
        self._capture_memory_sets = []

        # 하단 동작 바를 먼저 만들어 둔다. (다른 곳이 [실행] 버튼을 참조하므로)
        self._build_action_row()

        self._body = ttk.Frame(self)
        self._body.pack(fill="both", expand=True)
        self._body.grid_columnconfigure(0, weight=3, uniform="columns")
        self._body.grid_columnconfigure(1, weight=4, uniform="columns")
        self._body.grid_rowconfigure(0, weight=1)

        self._left_column = ttk.Frame(self._body)
        self._left_column.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self._right_column = ttk.Frame(self._body)
        self._right_column.grid(row=0, column=1, sticky="nsew")
        self._right_column.grid_rowconfigure(0, weight=1)

        self._preview_view = PreviewView(
            self._right_column,
            on_phrase_selected=self.add_underline_phrase,
            on_open_original=self._open_original_in_browser,
            on_phrase_removed=self._remove_underline_phrase_by_text,
        )
        self._preview_view.set_on_move_article(self._move_preview_article)

        self._build_law_search_row()
        self._build_period_row()
        self._build_version_list()
        self._build_article_rows()
        self._build_job_list()
        self._preview_view.pack(fill="both", expand=True, pady=(0, 8))
        self._build_document_rows()
        self._refresh_favorites_picker()
        self._refresh_capture_memory_picker()

        # 모든 카드(와 미리보기)의 안내문이 카드 폭에 맞춰 줄바꿈되게 한다.
        # 이게 없으면 긴 안내문이 카드를 창보다 넓게 만들어 버튼이 잘린다.
        for card in _iter_widgets(self):
            if isinstance(card, ttk.LabelFrame):
                install_auto_wrap(card)

    @property
    def preview_view(self) -> "PreviewView":
        """창 쪽에서 미리보기 결과를 전달할 때 쓴다."""
        return self._preview_view

    # ------------------------------------------------------------------
    # 화면 구성
    # ------------------------------------------------------------------

    def _build_law_search_row(self) -> None:
        card = StepCard(self._left_column, 1, "법령 찾기")
        card.pack(fill="x", pady=(0, 8))
        card.grid_columnconfigure(1, weight=1)

        ttk.Label(card, text="법령/고시명").grid(row=0, column=0, sticky="w", padx=(0, 8))
        row = ttk.Frame(card)
        row.grid(row=0, column=1, sticky="ew")
        row.grid_columnconfigure(0, weight=1)

        self._law_name_entry = HintEntry(row, "예: 공동주택관리법 또는 하자판정기준")
        self._law_name_entry.grid(row=0, column=0, sticky="ew")
        self._law_name_entry.bind("<Return>", lambda _: self._search_law())
        ttk.Button(row, text="검색", command=self._search_law).grid(row=0, column=1, padx=(6, 0))

        # 검색 결과를 고르는 칸.
        # 이름 일부로 찾으면 여러 건이 나오는 경우가 많아서
        # (예: '공동' 으로 찾으면 30건 넘게 나온다) 직접 고를 수 있어야 한다.
        picker_row = ttk.Frame(card)
        picker_row.grid(row=1, column=1, sticky="ew", pady=(6, 0))
        self._law_picker = ttk.Combobox(picker_row, state="disabled")
        self._law_picker.pack(fill="x")
        self._law_picker.bind("<<ComboboxSelected>>", self._on_law_chosen)

        self._search_status_label = ttk.Label(
            card, text="법령·고시 이름을 넣고 [검색]을 누르세요", style="Hint.TLabel"
        )
        self._search_status_label.grid(row=2, column=1, sticky="w", pady=(6, 0))

        # 자주 쓰는 법령은 Combobox 로 바로 고르거나, [설정] 창에서 관리한다.
        favorites_row = ttk.Frame(card)
        favorites_row.grid(row=3, column=1, sticky="ew", pady=(8, 0))
        favorites_row.grid_columnconfigure(0, weight=1)
        ttk.Label(card, text="즐겨찾기").grid(
            row=3, column=0, sticky="nw", padx=(0, 8), pady=(8, 0)
        )
        self._favorites_picker = ttk.Combobox(favorites_row, state="disabled")
        self._favorites_picker.grid(row=0, column=0, sticky="ew")
        self._favorites_picker.bind("<<ComboboxSelected>>", self._on_favorite_chosen)
        ttk.Button(
            favorites_row, text="설정", command=self._open_favorites_settings
        ).grid(row=0, column=1, padx=(6, 0))
        ttk.Label(
            favorites_row,
            text="목록에서 고르거나 [설정]에서 추가·제거·적용",
            style="Hint.TLabel",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))

        # 즐겨찾기는 법령 하나. 그 아래는 서면 단위로 묶은 캡처 세트다.
        # 세트에는 법령·조문·밑줄만 있고, 시점은 여기서 기준일로 넣는다.
        memory_row = ttk.Frame(card)
        memory_row.grid(row=4, column=1, sticky="ew", pady=(8, 0))
        memory_row.grid_columnconfigure(0, weight=1)
        ttk.Label(card, text="사용자 지정 SET").grid(
            row=4, column=0, sticky="nw", padx=(0, 8), pady=(8, 0)
        )
        self._capture_memory_picker = ttk.Combobox(memory_row, state="disabled")
        self._capture_memory_picker.grid(row=0, column=0, sticky="ew")
        ttk.Button(
            memory_row, text="설정", command=self._open_capture_memory_settings
        ).grid(row=0, column=1, padx=(6, 0))

        apply_row = ttk.Frame(memory_row)
        apply_row.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Label(apply_row, text="기준일").pack(side="left")
        self._capture_memory_date_entry = ttk.Entry(apply_row, width=12)
        self._capture_memory_date_entry.insert(0, date.today().isoformat())
        self._capture_memory_date_entry.pack(side="left", padx=(6, 0))
        ttk.Button(
            apply_row, text="이 시점으로 담기", command=self._add_jobs_from_capture_memory
        ).pack(side="left", padx=(6, 0))
        ttk.Label(
            memory_row,
            text="세트에 넣어 둔 법령·조문·밑줄을, 이 날짜의 판으로 담은 목록에 넣습니다.",
            style="Hint.TLabel",
            wraplength=360,
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))

    def _build_period_row(self) -> None:
        """
        '어느 시점?' 을 세 가지로 고르게 한다.

        예전에는 방식과 무관하게 날짜 칸이 둘 다 남아 있었고,
        '특정 시점' 인데도 뒤쪽 칸만 몰래 써서 앞 칸에 넣은 날짜가 무시됐다.
        고른 방식에 맞는 칸만 보이게 해서 헷갈리지 않게 한다.
        """
        card = StepCard(self._left_column, 2, "어느 시점의 판")
        card.pack(fill="x", pady=(0, 8))
        card.grid_columnconfigure(0, weight=1)

        row = ttk.Frame(card)
        row.grid(row=0, column=0, sticky="ew", pady=(0, 6))

        self._mode = tk.StringVar(value=PERIOD_MODE)
        for label in (SINGLE_DATE_MODE, PERIOD_MODE, ALL_TIME_MODE):
            ttk.Radiobutton(
                row,
                text=label,
                value=label,
                variable=self._mode,
                command=self._on_timing_mode_changed,
            ).pack(side="left", padx=(0, 10))

        # 날짜 칸과 찾기 버튼을 담는 줄. 방식에 따라 안쪽만 다시 그린다.
        self._date_row = ttk.Frame(card)
        self._date_row.grid(row=1, column=0, sticky="ew")

        this_year = date.today().year
        # 기본은 오늘. 사건 시점을 보려면 사용자가 날짜를 바꾸면 된다.
        # (예전 {올해}-06-01 기본값은 지금이 아닌 날짜로 헷갈리게 했다)
        self._reference_date_entry = ttk.Entry(self._date_row, width=12)
        self._reference_date_entry.insert(0, date.today().isoformat())

        self._period_start_entry = ttk.Entry(self._date_row, width=12)
        self._period_start_entry.insert(0, f"{this_year - 2}-01-01")
        self._period_tilde_label = ttk.Label(self._date_row, text=" ~ ")
        self._period_end_entry = ttk.Entry(self._date_row, width=12)
        self._period_end_entry.insert(0, f"{this_year}-12-31")

        self._reference_date_label = ttk.Label(self._date_row, text="기준일 ")
        self._all_time_hint_label = ttk.Label(
            self._date_row,
            text="제정부터 현행까지 모두 (날짜 칸 없음)",
            style="Hint.TLabel",
        )
        self._find_versions_button = ttk.Button(
            self._date_row, text="개정본 찾기", command=self._refresh_version_list
        )

        self._apply_timing_mode_layout()

    def _on_timing_mode_changed(self) -> None:
        """시점을 고르는 방식이 바뀌면 칸을 맞추고, 이미 법령이 있으면 목록도 갱신한다."""
        self._apply_timing_mode_layout()
        if self._found_law is not None:
            self._refresh_version_list()

    def _apply_timing_mode_layout(self) -> None:
        """
        고른 방식에 맞는 칸만 보이게 한다.

        pack_forget 으로 숨긴 뒤 필요한 것만 다시 붙인다.
        안 쓰는 칸이 남아 있으면 '왜 이 날짜가 안 먹지?' 하는 혼란이 난다.
        """
        for widget in (
            self._reference_date_label,
            self._reference_date_entry,
            self._period_start_entry,
            self._period_tilde_label,
            self._period_end_entry,
            self._all_time_hint_label,
            self._find_versions_button,
        ):
            widget.pack_forget()

        mode = self._mode.get()
        if mode == SINGLE_DATE_MODE:
            self._reference_date_label.pack(side="left")
            self._reference_date_entry.pack(side="left")
        elif mode == PERIOD_MODE:
            self._period_start_entry.pack(side="left")
            self._period_tilde_label.pack(side="left")
            self._period_end_entry.pack(side="left")
        else:
            # 전체 기간 — 날짜 칸 없이 안내만
            self._all_time_hint_label.pack(side="left")

        self._find_versions_button.config(text=MODE_FIND_BUTTON_LABELS[mode])
        self._find_versions_button.pack(side="left", padx=6)

    def _build_version_list(self) -> None:
        frame = ttk.LabelFrame(
            self._left_column,
            text="개정본 선택 (오래된 순)",
            padding=8,
            style="Card.TLabelframe",
        )
        frame.pack(fill="both", expand=True, pady=(0, 8))

        # 개정본이 여덟 개까지 나오는 법령도 있어서 하나씩 끄고 켜기가 번거롭다.
        self._are_all_versions_selected = tk.BooleanVar(value=False)
        self._select_all_checkbox = VCheckbutton(
            frame,
            label_text="전체 선택",
            variable=self._are_all_versions_selected,
            command=self._apply_select_all,
        )
        self._select_all_checkbox.pack(anchor="w")

        self._selected_count_label = ttk.Label(frame, text="", style="Hint.TLabel")
        self._selected_count_label.pack(anchor="w", padx=(20, 0))

        # 개정본이 아주 많을 때(주택법 172개 등) 눈에 띄게 알린다.
        self._many_versions_warning = ttk.Label(frame, text="", style="Danger.TLabel")
        self._many_versions_warning.pack(anchor="w", pady=(2, 0))

        # 이름이 바뀐 적이 있는 법령·고시라면 알린다.
        # (옛 이름으로 찾은 사용자가 엉뚱한 것을 찾았다고 오해하지 않도록)
        self._name_change_notice = ttk.Label(
            frame, text="", style="Danger.TLabel", justify="left"
        )
        self._name_change_notice.pack(anchor="w", pady=(2, 0))

        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=4)

        # 목록만 고정 높이 + 스크롤. 172줄이 창을 밀어내지 않게 한다.
        list_container = ttk.Frame(frame)
        list_container.pack(fill="x")

        # width=1: 폭은 정해 주지 않으면 기본 약 380px 를 요구해 카드를 밀어낸다.
        # 요구 폭은 최소로 두고, 실제 폭은 남는 자리(fill="both")에 맡긴다.
        self._version_canvas = tk.Canvas(
            list_container,
            width=1,
            height=VERSION_LIST_VISIBLE_HEIGHT_IN_PIXELS,
            highlightthickness=0,
            background=theme.CARD_BACKGROUND,
            borderwidth=0,
        )
        self._version_scrollbar = ttk.Scrollbar(
            list_container, orient="vertical", command=self._scroll_version_list_from_bar
        )
        self._version_canvas.configure(yscrollcommand=self._version_scrollbar.set)
        self._version_canvas.pack(side="left", fill="both", expand=True)
        self._version_scrollbar.pack(side="right", fill="y")

        self._version_list_frame = ttk.Frame(self._version_canvas)
        self._version_list_window = self._version_canvas.create_window(
            (0, 0), window=self._version_list_frame, anchor="nw"
        )
        # 목록을 다시 그릴 때 스크롤 범위 조정이 자기 자신을 또 부르면
        # 창이 멈추므로, 조정 중에는 다시 들어오지 않게 막는다.
        self._is_adjusting_version_scroll = False
        self._version_list_frame.bind(
            "<Configure>",
            lambda _event: self._sync_version_list_scrollregion(),
        )
        self._version_canvas.bind(
            "<Configure>",
            lambda event: self._version_canvas.itemconfigure(
                self._version_list_window, width=event.width
            ),
        )
        # 마우스 휠은 창(app_window) 한곳에서만 받는다.
        # 예전에는 여기 Enter/Leave 로 bind_all / unbind_all 을 썼는데,
        # Leave 때 unbind_all 하면 창 전체 휠 연결까지 사라져 스크롤바가
        # 있는데도 휠이 먹통이 되었다. 그래서 목록은 "굴려 주세요" 만 받고,
        # 언제 굴릴지는 창이 포인터 위치를 보고 정한다.

        self._version_hint = ttk.Label(
            frame,
            text="법령을 검색하고 시점을 정하면 여기에 개정본이 나열됩니다.\n"
                 "그림으로 만들 개정본을 체크해 주세요.",
            style="Hint.TLabel",
        )
        self._version_hint.pack(fill="x")

    @property
    def version_list_canvas(self) -> tk.Canvas:
        """창 휠 처리기가 '지금 포인터가 목록 위인가' 판별할 때 쓴다."""
        return self._version_canvas

    def scroll_version_list_by_wheel(self, delta: int) -> None:
        """개정본 목록만 스크롤한다. (창 휠 처리기가 포인터가 목록 위일 때 부름)"""
        self._version_canvas.yview_scroll(int(-delta / 120), "units")
        # 휠은 맨 위에 있어도 한 칸 더 올려 첫 항목 위에 빈칸을 만든다.
        # 올린 직후 맨 위로 되돌린다.
        self._clamp_version_list_to_top()

    def _scroll_version_list_from_bar(self, *args) -> None:
        """스크롤바로 굴릴 때도 첫 항목보다 위로 올라가지 않게 한다."""
        self._version_canvas.yview(*args)
        self._clamp_version_list_to_top()

    def _sync_version_list_scrollregion(self) -> None:
        """
        스크롤 범위를 첫 항목이 칸의 맨 위에 오도록 잡는다.

        내용이 칸보다 짧을 때 범위를 내용 높이로만 두면, 윈도우는 그 짧은
        내용을 칸 맨 아래에 붙인다. 그러면 첫 항목 위에 빈칸이 생긴다.
        그래서 내용이 짧으면 범위를 칸 높이와 같게 해 스크롤이 없게 하고,
        길면 내용 높이만큼만 잡아 첫 항목 위로는 올라가지 않게 한다.
        """
        if self._is_adjusting_version_scroll:
            return
        self._is_adjusting_version_scroll = True
        try:
            self._version_canvas.update_idletasks()
            content_height = max(self._version_list_frame.winfo_reqheight(), 1)
            content_width = max(
                self._version_list_frame.winfo_reqwidth(),
                self._version_canvas.winfo_width(),
                1,
            )
            # 창 높이를 내용만큼만 고정한다. 안 그러면 칸 전체로 늘어나
            # 체크 줄이 그 아래쪽에 붙는다.
            self._version_canvas.coords(self._version_list_window, 0, 0)
            self._version_canvas.itemconfigure(
                self._version_list_window,
                width=content_width,
                height=content_height,
            )
            canvas_height = max(self._version_canvas.winfo_height(), 1)
            region_height = max(content_height, canvas_height)
            self._version_canvas.configure(
                scrollregion=(0, 0, content_width, region_height)
            )
            self._version_canvas.yview_moveto(0)
        finally:
            self._is_adjusting_version_scroll = False

    def _clamp_version_list_to_top(self) -> None:
        """이미 첫 항목보다 위로 올라가 있으면 맨 위로 붙인다."""
        top_fraction, _bottom_fraction = self._version_canvas.yview()
        if top_fraction < 0:
            self._version_canvas.yview_moveto(0)

    def _build_article_rows(self) -> None:
        # 이 카드를 오른쪽 미리보기와 비슷한 높이에 두면,
        # 사용자가 드래그 후 시선을 크게 옮기지 않고 밑줄 칸을 확인할 수 있다.
        card = StepCard(self._left_column, 3, "조문과 밑줄")
        card.pack(fill="x", pady=(0, 8))
        self._article_card = card

        article_row = ttk.Frame(card)
        article_row.grid(row=0, column=0, sticky="ew")
        article_row.grid_columnconfigure(1, weight=1)
        # 두 줄의 이름표 폭을 같게 맞춰, 아래 [밑줄] 입력칸과 왼쪽이 나란히 서게 한다.
        ttk.Label(article_row, text="조문 번호", width=LABEL_COLUMN_WIDTH).grid(
            row=0, column=0, sticky="w", padx=(0, 8)
        )
        # 안내문은 이름표 칸(첫 열)이 아니라 두 열에 걸쳐 둔다.
        # 첫 열에 두면 이 글자 폭만큼 입력칸과 버튼이 오른쪽으로 밀려 잘렸다.
        ttk.Label(
            article_row,
            text="예: 1 또는 1, 2 또는 1-3 또는 32의2",
            style="Hint.TLabel",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))
        input_row = ttk.Frame(article_row)
        input_row.grid(row=0, column=1, sticky="ew")
        input_row.grid_columnconfigure(0, weight=1)
        # width=1 로 두는 이유: 입력칸이 '최소한 이만큼' 을 요구하지 않고
        # 남는 폭만큼 늘고 줄게 하려는 것이다. (창이 좁아도 버튼이 잘리지 않게)
        self._article_entry = ttk.Entry(input_row, width=1)
        self._article_entry.grid(row=0, column=0, sticky="ew")
        self._article_entry.bind("<Return>", lambda _: self._load_preview())
        ttk.Button(input_row, text="미리보기", command=self._load_preview).grid(
            row=0, column=1, padx=(6, 0)
        )
        ttk.Button(input_row, text="전체보기", command=self._load_full_preview).grid(
            row=0, column=2, padx=(6, 0)
        )

        underline_row = ttk.Frame(card)
        underline_row.grid(row=1, column=0, sticky="ew", pady=(6, 2))
        underline_row.grid_columnconfigure(1, weight=1)
        ttk.Label(underline_row, text="밑줄", width=LABEL_COLUMN_WIDTH).grid(
            row=0, column=0, sticky="w", padx=(0, 8)
        )
        self._underline_phrase_entry = ttk.Entry(underline_row, width=1)
        self._underline_phrase_entry.grid(row=0, column=1, sticky="ew")
        self._underline_phrase_entry.bind(
            "<Return>", lambda _event: self._add_underline_phrase_from_entry()
        )
        ttk.Button(
            underline_row,
            text="추가",
            command=self._add_underline_phrase_from_entry,
        ).grid(row=0, column=2, padx=(6, 0))
        ttk.Button(
            underline_row,
            text="밑줄 초기화",
            command=self._reset_underline_phrases,
        ).grid(row=0, column=3, padx=(6, 0))

        # 밑줄 색. 기본은 빨강. 작업(담은 목록)마다 이 값이 저장된다.
        color_row = ttk.Frame(card)
        color_row.grid(row=2, column=0, sticky="w", pady=(2, 2))
        ttk.Label(color_row, text="밑줄 색", width=LABEL_COLUMN_WIDTH).pack(
            side="left", padx=(0, 8)
        )
        color_names = [name for name, _rgb in UNDERLINE_COLOR_CHOICES]
        self._underline_color_picker = ttk.Combobox(
            color_row,
            values=color_names,
            state="readonly",
            width=8,
        )
        self._underline_color_picker.set(DEFAULT_UNDERLINE_COLOR_NAME)
        self._underline_color_picker.pack(side="left")
        self._underline_color_picker.bind(
            "<<ComboboxSelected>>", self._on_underline_color_changed
        )
        ttk.Label(
            color_row,
            text="(기본 빨강 · 미리보기 형광펜과 PDF 밑줄에 적용)",
            style="Hint.TLabel",
        ).pack(side="left", padx=(8, 0))
        # 시작할 때도 미리보기 형광펜을 기본 색에 맞춰 둔다.
        self._apply_preview_highlight_for_current_color()

        chips_frame = ttk.Frame(card)
        chips_frame.grid(row=3, column=0, sticky="ew", pady=(4, 2))
        # width=1 로 두는 이유: tk.Canvas 는 폭을 정해 주지 않으면 기본 약 380px 를
        # 요구해서 카드를 그만큼 넓히려 든다. 창이 좁으면 카드 오른쪽이 잘리므로,
        # 요구 폭을 최소로 두고 실제 폭은 남는 자리(fill="x")에 맡긴다.
        self._underline_chips_canvas = tk.Canvas(
            chips_frame, width=1, height=82, highlightthickness=0
        )
        self._underline_chips_scrollbar = ttk.Scrollbar(
            chips_frame, orient="vertical", command=self._underline_chips_canvas.yview
        )
        self._underline_chips_canvas.configure(yscrollcommand=self._underline_chips_scrollbar.set)
        self._underline_chips_canvas.pack(side="left", fill="x", expand=True)
        self._underline_chips_scrollbar.pack(side="right", fill="y")
        self._underline_chips_frame = ttk.Frame(self._underline_chips_canvas)
        self._underline_chips_window = self._underline_chips_canvas.create_window(
            (0, 0), window=self._underline_chips_frame, anchor="nw"
        )
        self._underline_chips_frame.bind(
            "<Configure>",
            lambda _event: self._underline_chips_canvas.configure(
                scrollregion=self._underline_chips_canvas.bbox("all")
            ),
        )
        self._underline_chips_canvas.bind(
            "<Configure>",
            lambda event: self._underline_chips_canvas.itemconfigure(
                self._underline_chips_window, width=event.width
            ),
        )

        ttk.Label(
            card,
            text=(
                "조문 [미리보기] 또는 [전체보기]에서 문구를 드래그하거나, "
                "그대로 적어주세요. 전체보기에서 드래그하면 조문 번호도 함께 채워집니다."
            ),
            style="Hint.TLabel",
        ).grid(row=4, column=0, sticky="w", pady=(2, 0))

        # 캡션·테두리는 기본으로 켠다. 서면에 넣을 때는 거의 항상 필요하지만,
        # 이미 캡션이 있는 문서에 그림만 끼울 때는 끌 수 있어야 한다.
        option_row = ttk.Frame(card)
        option_row.grid(row=5, column=0, sticky="ew", pady=(6, 0))
        self._should_add_caption = tk.BooleanVar(value=True)
        self._should_add_border = tk.BooleanVar(value=True)
        self._caption_option_button = VCheckbutton(
            option_row,
            label_text="캡션 넣기",
            variable=self._should_add_caption,
        )
        self._caption_option_button.pack(side="left")
        self._border_option_button = VCheckbutton(
            option_row,
            label_text="테두리 넣기",
            variable=self._should_add_border,
        )
        self._border_option_button.pack(side="left", padx=(12, 0))

        # [담기] 는 조건을 채우던 자리(이 카드 오른쪽 아래)에 둔다.
        # 화면 구석의 고정 바에 두었더니 눈에 잘 띄지 않았다.
        # 입력을 마친 시선이 마지막에 머무는 곳이 바로 여기이기 때문이다.
        ttk.Button(
            option_row, text="＋ 이 조건을 목록에 담기", command=self._add_job
        ).pack(side="right")
        self._render_underline_phrase_chips()

    def _build_document_rows(self) -> None:
        card = StepCard(
            self._right_column,
            5,
            "한글 파일 저장 위치 - 현재는 임시 폴더에 저장됩니다. (추후 업데이트 예정)",
        )
        card.pack(fill="x")
        self._document_card = card
        card.grid_columnconfigure(1, weight=1)

        self._should_use_existing_hwp = tk.BooleanVar(value=False)
        self._use_existing_hwp_checkbutton = ttk.Checkbutton(
            card,
            text="기존 한글 문서에 넣기(체크했을 때만 사용)",
            variable=self._should_use_existing_hwp,
            command=self._on_use_existing_hwp_toggled,
        )
        self._use_existing_hwp_checkbutton.grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 6)
        )

        file_row = ttk.Frame(card)
        file_row.grid(row=1, column=0, columnspan=2, sticky="ew")
        file_row.grid_columnconfigure(1, weight=1)
        ttk.Label(file_row, text="대상 한글 파일").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self._hwp_path_entry = HintEntry(file_row, "비워두면 새 문서를 만듭니다")
        self._hwp_path_entry.grid(row=0, column=1, sticky="ew")
        self._browse_hwp_button = ttk.Button(file_row, text="찾아보기", command=self._browse_hwp_file)
        self._browse_hwp_button.grid(
            row=0, column=2, padx=(6, 0)
        )
        self._open_hwp_folder_button = ttk.Button(
            file_row, text="폴더 열기", command=self._open_hwp_folder
        )
        self._open_hwp_folder_button.grid(row=0, column=3, padx=(6, 0))

        mode_row = ttk.Frame(card)
        mode_row.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 2))
        ttk.Label(mode_row, text="삽입 위치").pack(side="left", padx=(0, 8))
        self._insertion_mode = tk.StringVar(value=InsertionMode.APPEND_TO_END.value)
        for mode in InsertionMode:
            ttk.Radiobutton(
                mode_row, text=mode.value, value=mode.value, variable=self._insertion_mode
            ).pack(side="left", padx=(0, 12))

        ttk.Label(
            card,
            text="이 단계는 현재 사용하지 않습니다. 기본 저장 규칙으로 자동 저장됩니다.",
            style="Hint.TLabel",
        ).grid(row=3, column=0, columnspan=2, sticky="w")
        self._disable_hwp_save_section()

    def _build_job_list(self) -> None:
        frame = ttk.LabelFrame(
            self._left_column,
            text="4. 담은 작업 대기 목록",
            padding=8,
            style="Card.TLabelframe",
        )
        frame.pack(fill="both", expand=False)
        self._job_list_frame = frame

        self._job_listbox = tk.Listbox(frame, height=6, selectmode="extended")
        self._job_listbox.pack(side="left", fill="both", expand=True)
        control_column = ttk.Frame(frame)
        control_column.pack(side="left", padx=6, anchor="n")
        self._remove_selected_job_button = ttk.Button(
            control_column,
            text="선택 삭제",
            command=self._remove_selected_job,
        )
        self._remove_selected_job_button.pack(fill="x")
        self._add_jobs_to_capture_memory_button = ttk.Button(
            control_column,
            text="현재 SET에 추가",
            command=self._add_waiting_jobs_to_capture_memory,
        )
        self._add_jobs_to_capture_memory_button.pack(fill="x", pady=(6, 0))
        self._remove_all_jobs_button = ttk.Button(
            control_column,
            text="전체 삭제",
            command=self._remove_all_jobs,
        )
        self._remove_all_jobs_button.pack(
            fill="x", pady=(6, 0)
        )

        self._figure_count_label = ttk.Label(frame, text="", style="Hint.TLabel")
        self._figure_count_label.pack(fill="x")
        self._refresh_action_button_states()

    def _build_action_row(self) -> None:
        """
        화면 맨 아래에 항상 떠 있는 동작 바를 만든다.

        왜 스크롤 바깥에 두는가:
          입력 화면은 세로로 길어서(약 1200px) 창 전체를 스크롤 영역에 넣어 두었다.
          [실행] 을 본문 끝에 두면 창을 줄였을 때 스크롤을 한참 내려야
          찾을 수 있다. 자주 누르는 버튼이라 스크롤과 상관없이 늘 보여야 한다.

        [담기] 는 여기 두지 않는다. 조건을 채우던 카드 안에 있어야
        눈에 띄기 때문이다. (구석 바에 두었더니 잘 안 보인다는 지적이 있었다)
        """
        parent = self._footer_parent
        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=(0, 6))
        action_row = ttk.Frame(parent, padding=(12, 0, 12, 8))
        action_row.pack(fill="x")

        ttk.Button(action_row, text="입력 값 리셋", command=self._reset_input_values).pack(side="left")

        self._start_button = ttk.Button(
            action_row, text="실행", command=self._request_start, state="disabled", style="Primary.TButton"
        )
        self._start_button.pack(side="right")

        # 결과 한글 파일은 out 폴더에 쌓인다. 저장 위치 칸은 지금 꺼져 있어서
        # 그 안의 [폴더 열기] 는 누를 수 없다. 실행 바로 왼쪽에서 열 수 있게 둔다.
        # side="right" 는 나중에 담은 것이 더 왼쪽이므로, 실행 다음에 담아야
        # 실행의 바로 왼쪽에 붙는다.
        self._open_saved_folder_button = ttk.Button(
            action_row, text="저장된 폴더 열기", command=self._open_saved_output_folder
        )
        self._open_saved_folder_button.pack(side="right", padx=(0, 8))

        # 담아둔 현황. 스크롤을 내리지 않고도 몇 건이 담겼는지 알 수 있다.
        self._footer_summary_label = ttk.Label(
            action_row, text="담은 작업 없음", style="Hint.TLabel"
        )
        self._footer_summary_label.pack(side="right", padx=(0, 12))

    # ------------------------------------------------------------------
    # 사용자 조작에 대한 반응
    # ------------------------------------------------------------------

    def _search_law(self) -> None:
        query = self._law_name_entry.get().strip()
        if not query:
            messagebox.showinfo("법령 검색", "찾을 법령·고시 이름을 넣어주세요.")
            return

        try:
            candidates = self._controller.search_laws_by_name(query)
        except LawCaptureError as error:
            self._show_search_failure(str(error))
            return

        self._show_search_results(candidates, query)
        self._refresh_version_list()

    def _show_search_results(self, candidates: list, query: str = "") -> None:
        """찾은 법령들을 고를 수 있게 목록에 채운다. 첫 번째를 기본으로 고른다."""
        self._candidates = candidates
        self._found_law = candidates[0]

        self._law_picker.configure(values=[str(item) for item in candidates])
        self._law_picker.configure(state="readonly")
        self._law_picker.current(0)

        if len(candidates) == 1:
            message = "이 법령으로 진행합니다."
        else:
            message = (
                f"{len(candidates)}건을 찾았습니다. 원하는 것이 아니면 위 목록에서 고르세요."
            )

        # 검색어가 결과 이름에 없으면, 지금은 안 쓰는 옛 이름으로 찾아준 것이다.
        # 알려주지 않으면 엉뚱한 것이 나왔다고 여기고 검색을 포기하게 된다.
        if self._controller.was_searched_by_former_name(
            query, self._found_law.law_name
        ):
            message = (
                f"'{query}' 은(는) 옛 이름입니다. 이름이 바뀌어 지금은 아래 이름으로 나옵니다.\n"
                "찾으시던 그 문서가 맞으니, 시점만 그때로 맞춰 주세요."
            )
            self._search_status_label.config(text=message, foreground="red")
            return

        self._search_status_label.config(text=message, foreground="gray")

    def _show_search_failure(self, message: str) -> None:
        self._candidates = []
        self._found_law = None
        self._law_picker.configure(values=[], state="disabled")
        self._law_picker.set("")
        self._search_status_label.config(text=message, foreground="red")

    def _on_law_chosen(self, _event=None) -> None:
        """목록에서 다른 법령을 고르면 개정본 목록을 다시 불러온다."""
        chosen_index = self._law_picker.current()
        if not (0 <= chosen_index < len(self._candidates)):
            return

        self._found_law = self._candidates[chosen_index]
        self._refresh_version_list()

    def _refresh_favorites_picker(self) -> None:
        """저장된 즐겨찾기를 Combobox 에 채운다."""
        self._favorites = self._controller.list_favorites()
        if not self._favorites:
            self._favorites_picker.configure(values=[], state="disabled")
            self._favorites_picker.set("")
            return

        self._favorites_picker.configure(
            values=[item.display_label() for item in self._favorites],
            state="readonly",
        )
        # 고른 값이 목록에서 빠졌을 수 있어 비워 둔다.
        self._favorites_picker.set("")

    def _open_favorites_settings(self) -> None:
        """
        즐겨찾기 설정 창을 연다.

        추가·제거는 창 안에서 바로 파일에 반영되고,
        [적용]을 누르면 메인 화면의 법령 선택까지 맞춘다.
        창을 닫으면 Combobox 목록을 다시 읽어 맞춘다.
        """
        dialog = FavoritesSettingsDialog(
            parent=self.winfo_toplevel(),
            controller=self._controller,
            on_applied=self._apply_favorite,
        )
        self.wait_window(dialog)
        self._refresh_favorites_picker()

    def _apply_favorite(self, favorite: FavoriteLaw) -> None:
        """
        즐겨찾기 한 건을 메인 화면 법령으로 반영한다.

        Combobox 에서 고른 때와 설정 창 [적용] 이 같은 길을 탄다.
        """
        try:
            law = self._controller.resolve_favorite_to_search_result(favorite)
        except LawCaptureError as error:
            messagebox.showinfo("즐겨찾기", str(error))
            return

        self._refresh_favorites_picker()
        # Combobox 표시도 적용한 항목으로 맞춘다.
        for index, item in enumerate(self._favorites):
            if item.is_same_law_as(favorite):
                self._favorites_picker.current(index)
                break

        self._law_name_entry.set_text(law.law_name)
        self._show_search_results([law])
        self._refresh_version_list()
        self._search_status_label.config(
            text=f"즐겨찾기 '{law.law_name}' 을(를) 적용했습니다.",
            foreground="gray",
        )

    def _on_favorite_chosen(self, _event=None) -> None:
        """메인 Combobox 에서 즐겨찾기를 고르면 바로 적용한다."""
        index = self._favorites_picker.current()
        if not (0 <= index < len(self._favorites)):
            return
        self._apply_favorite(self._favorites[index])

    def _refresh_capture_memory_picker(self) -> None:
        """저장된 캡처 세트 이름을 Combobox 에 채운다."""
        self._capture_memory_sets = self._controller.list_capture_memory_sets()
        if not self._capture_memory_sets:
            self._capture_memory_picker.configure(values=[], state="disabled")
            self._capture_memory_picker.set("")
            return

        self._capture_memory_picker.configure(
            values=[memory_set.name for memory_set in self._capture_memory_sets],
            state="readonly",
        )
        current_name = self._capture_memory_picker.get()
        if current_name not in [memory_set.name for memory_set in self._capture_memory_sets]:
            self._capture_memory_picker.set("")

    def _open_capture_memory_settings(self) -> None:
        """
        사용자 지정 SET 설정 창을 연다.

        세트와 항목은 창 안에서 바로 파일에 저장된다.
        창을 닫으면 메인 Combobox 를 다시 읽어 맞춘다.
        """
        dialog = CaptureSetMemoryDialog(
            parent=self.winfo_toplevel(),
            controller=self._controller,
        )
        self.wait_window(dialog)
        self._refresh_capture_memory_picker()

    def _add_jobs_from_capture_memory(self) -> None:
        """
        고른 세트의 법령·조문·밑줄을, 기준일 당시의 판으로 담은 목록에 넣는다.

        한 항목이 실패해도 나머지는 담는다. 이름이 바뀐 항목은 담은 뒤 안내한다.
        캡션·테두리·한글 넣기 방식은 '목록에 담기'와 같이 지금 화면 값을 쓴다.
        밑줄 색만 세트에 저장해 둔 색을 쓴다.
        """
        set_name = self._capture_memory_picker.get().strip()
        memory_set = next(
            (item for item in self._capture_memory_sets if item.name == set_name),
            None,
        )
        if memory_set is None:
            messagebox.showinfo("사용자 지정 SET", "먼저 세트를 고르세요. 없으면 [설정]에서 만드세요.")
            return
        if not memory_set.items:
            messagebox.showinfo("사용자 지정 SET", "이 세트에는 아직 법령이 없습니다. [설정]에서 추가하세요.")
            return

        try:
            reference_date = _parse_date(self._capture_memory_date_entry.get(), "기준일")
            # 한글 경로 오류는 항목마다 반복하지 않고, 담기 전에 한 번만 확인한다.
            target_hwp_path = self._read_target_document_path()
        except ValueError as error:
            messagebox.showinfo("사용자 지정 SET", str(error))
            return

        failures: list[str] = []
        name_changes: list[CaptureMemoryNameChange] = []
        added_count = 0

        for item_index, item in enumerate(memory_set.items):
            try:
                law = self._controller.resolve_capture_memory_item(item)
                version = self._controller.find_single_version(law, reference_date)
                article_numbers = parse_article_numbers(item.article_text)
            except (LawCaptureError, ValueError) as error:
                failures.append(f"{item.law_name} {item.article_text}: {error}")
                continue

            stored_name_changed = law_names_differ_beyond_spacing(item.law_name, law.law_name)
            if stored_name_changed:
                self._controller.replace_capture_memory_item_law_name(
                    memory_set.name, item_index, law.law_name
                )
            if stored_name_changed or version.has_different_name_now:
                name_changes.append(
                    CaptureMemoryNameChange(
                        stored_law_name=item.law_name,
                        current_law_name=law.law_name,
                        historical_law_name=(
                            version.historical_law_name if version.has_different_name_now else ""
                        ),
                    )
                )

            job = ArticleCaptureJob(
                law_name=law.law_name,
                target_versions=[version],
                article_numbers=article_numbers,
                underline_phrases=list(item.underline_phrases),
                underline_color=underline_color_for_name(item.underline_color_name),
                target_hwp_path=target_hwp_path,
                insertion_mode=_find_insertion_mode(self._insertion_mode.get()),
                should_add_caption=self._should_add_caption.get(),
                should_add_border=self._should_add_border.get(),
                law_id=item.law_id,
                kind_label=item.kind_label,
            )
            self._append_job_to_list(job)
            added_count += 1

        self._refresh_capture_memory_picker()
        if set_name in [item.name for item in self._capture_memory_sets]:
            self._capture_memory_picker.set(set_name)

        notice = build_name_change_notice(name_changes)
        summary_lines = [f"{added_count}건을 담은 목록에 넣었습니다."]
        if failures:
            summary_lines.append("")
            summary_lines.append("아래 항목은 담지 못했습니다.")
            summary_lines.extend(failures)
        if notice:
            summary_lines.append("")
            summary_lines.append(notice)
        messagebox.showinfo("사용자 지정 SET", "\n".join(summary_lines))

    def _add_waiting_jobs_to_capture_memory(self) -> None:
        """
        담아 둔 작업 전체를 지금 고른 세트에 넣는다.

        미리보기로 밑줄까지 고른 뒤 한 번에 기억시키려고 둔다.
        개정본과 날짜는 넣지 않는다. 나중에 기준일만 바꿔 다시 담는다.
        대기 목록은 지우지 않는다. 바로 실행할 수도 있기 때문이다.
        """
        if not self._jobs:
            messagebox.showinfo("사용자 지정 SET", "담은 작업이 없습니다. 먼저 목록에 담아 주세요.")
            return

        set_name = self._capture_memory_picker.get().strip()
        memory_set = next(
            (item for item in self._capture_memory_sets if item.name == set_name),
            None,
        )
        if memory_set is None:
            messagebox.showinfo(
                "사용자 지정 SET",
                "세트를 고르거나 [설정]에서 만드세요.",
            )
            return

        current_items = list(memory_set.items)
        added_count = 0
        skipped_count = 0
        for job in self._jobs:
            if not job.target_versions:
                skipped_count += 1
                continue
            item = CaptureMemoryItem(
                law_name=job.law_name,
                law_id=job.law_id,
                source_kind=job.target_versions[0].source_kind,
                kind_label=job.kind_label,
                article_text=format_article_numbers_for_entry(job.article_numbers),
                underline_phrases=tuple(job.underline_phrases),
                underline_color_name=_underline_color_name_for_set(job.underline_color),
            )
            if any(existing.is_same_recipe_as(item) for existing in current_items):
                skipped_count += 1
                continue
            self._controller.add_capture_memory_item(set_name, item)
            current_items.append(item)
            added_count += 1

        self._refresh_capture_memory_picker()
        if set_name in [item.name for item in self._capture_memory_sets]:
            self._capture_memory_picker.set(set_name)

        messagebox.showinfo(
            "사용자 지정 SET",
            f"{added_count}건을 넣었습니다. 이미 있던 {skipped_count}건은 건너뛰었습니다.",
        )

    def _append_job_to_list(self, job: ArticleCaptureJob) -> None:
        """담은 목록에 작업 한 줄을 붙인다. '목록에 담기'와 세트가 같이 쓴다."""
        self._jobs.append(job)
        color_label = _underline_color_display_name(job.underline_color)
        self._job_listbox.insert(
            tk.END,
            (
                f"{job.law_name} {job.article_label} "
                f"(개정본 {job.expected_figure_count}개)  "
                f"밑줄 {len(job.underline_phrases)}건 · {color_label}"
            ),
        )
        self._update_figure_count()

    def _refresh_version_list(self) -> None:
        """고른 시점 방식에 맞춰 개정본 목록을 다시 그린다."""
        for widget in self._version_list_frame.winfo_children():
            widget.destroy()
        self._version_checkboxes.clear()
        self._many_versions_warning.config(text="")
        self._name_change_notice.config(text="")
        self._version_canvas.yview_moveto(0)

        if self._found_law is None:
            self._version_hint.config(text="먼저 법령을 검색해 주세요.", foreground="gray")
            self._refresh_selection_summary(update_select_all=False)
            self._sync_version_list_scrollregion()
            return

        try:
            versions = self._collect_versions_for_current_mode()
        except (LawCaptureError, ValueError) as error:
            self._version_hint.config(text=str(error), foreground="red")
            self._refresh_selection_summary(update_select_all=False)
            self._sync_version_list_scrollregion()
            return

        # 어느 모드에서든 개정본은 처음에 전부 해제된 상태로 시작한다.
        # 사용자가 필요한 것만 직접 체크한다. (사용자 결정)
        # 예전에는 기간·단일 모드만 전부 켜 두었는데, 원치 않는 판까지
        # 그림으로 만들어지기 쉬워 바꿨다.
        if len(versions) >= MANY_VERSIONS_WARNING_THRESHOLD:
            self._many_versions_warning.config(
                text=(
                    f"개정본이 {len(versions)}개입니다. "
                    "필요한 것만 체크해 주세요. (처음엔 전부 꺼져 있습니다)"
                )
            )

        self._name_change_notice.config(text=_build_name_change_notice(versions))

        self._version_hint.config(text=VERSION_LIST_HINT, foreground="gray")
        for version in versions:
            self._add_version_checkbox(version)

        self._are_all_versions_selected.set(False)
        self._refresh_selection_summary(update_select_all=False)
        self._sync_version_list_scrollregion()

    def _collect_versions_for_current_mode(self) -> list[LawVersion]:
        mode = self._mode.get()

        if mode == SINGLE_DATE_MODE:
            # 단일 모드는 '기준일' 칸(읽는 순서상 첫 칸)을 쓴다.
            # 예전에는 끝 날짜 칸을 몰래 써서 앞 칸 입력이 무시됐다.
            reference_date = _parse_date(self._reference_date_entry.get(), "기준일")
            return [self._controller.find_single_version(self._found_law, reference_date)]

        if mode == ALL_TIME_MODE:
            return self._controller.list_versions(self._found_law)

        return self._controller.find_versions_in_period(
            self._found_law,
            _parse_date(self._period_start_entry.get(), "기간 시작"),
            _parse_date(self._period_end_entry.get(), "기간 끝"),
        )

    def _add_version_checkbox(self, version: LawVersion) -> None:
        """개정본 한 줄을 목록에 더한다. 처음엔 체크가 꺼진 상태다."""
        is_selected = tk.BooleanVar(value=False)
        VCheckbutton(
            self._version_list_frame,
            label_text=_build_version_row_label(version),
            variable=is_selected,
            command=self._refresh_selection_summary,
            anchor="w",  # 버튼이 넓어져도 글자가 가운데로 몰리지 않게 왼쪽 정렬
        ).pack(fill="x", anchor="w")  # 목록 칸 너비에 맞춰 채움 (줄마다 들쭉날쭉하지 않게)
        self._version_checkboxes.append((is_selected, version))

    def _apply_select_all(self) -> None:
        """전체 선택을 켜거나 끄면 모든 개정본을 그에 맞춘다."""
        should_select = self._are_all_versions_selected.get()
        for is_selected, _ in self._version_checkboxes:
            is_selected.set(should_select)
        self._refresh_selection_summary(update_select_all=False)

    def _refresh_selection_summary(self, update_select_all: bool = True) -> None:
        """
        고른 개수를 다시 세어 보여준다.

        개별 항목을 하나라도 끄면 '전체 선택' 표시도 꺼져야 실제 상태와 맞는다.
        """
        chosen = [version for is_on, version in self._version_checkboxes if is_on.get()]
        total = len(self._version_checkboxes)

        if total:
            self._selected_count_label.config(text=f"{total}개 중 {len(chosen)}개 선택")
        else:
            self._selected_count_label.config(text="")

        if update_select_all:
            self._are_all_versions_selected.set(bool(total) and len(chosen) == total)

        self._preview_view.show_available_versions(chosen)

    def _load_preview(self) -> None:
        """[미리보기] 를 누르면 고른 판의 조문 내용을 불러온다."""
        article_text = self._article_entry.get().strip()
        try:
            article_numbers = parse_article_numbers(article_text)
        except ValueError as error:
            messagebox.showinfo("미리보기", str(error))
            return

        version = self._preview_view.chosen_version
        if version is None:
            messagebox.showinfo("미리보기", "먼저 법령을 검색하고, 개정본을 체크해 주세요.")
            return

        self._preview_view.show_loading(build_article_range_label(article_numbers))
        self._controller.start_loading_article_text(version, article_numbers)

    def _move_preview_article(self, step: int) -> None:
        """
        위/아래 버튼으로 옆 조문을 보여 준다.

        전체보기처럼 본문에 다음 조 제목이 있으면 그 줄로 스크롤만 한다.
        조문 하나만 불러 둔 경우에는 번호만 바꿔 그 조를 다시 받는다.
        제12조에서 아래를 누르면 제13조가 나오는 것이 이 경우다.
        """
        shown, did_move_inside_text = self._preview_view.reveal_adjacent_article(step)
        if did_move_inside_text and shown is not None:
            self._set_article_entry_text(format_article_for_entry(shown))
            return

        current = shown
        if current is None:
            try:
                articles = parse_article_numbers(self._article_entry.get().strip())
            except ValueError:
                messagebox.showinfo(
                    "조문 이동",
                    "먼저 조문 번호를 넣고 미리보기를 해 주세요.",
                )
                return
            current = articles[-1] if step > 0 else articles[0]

        target = step_to_adjacent_article_number(current, step)
        if target is None:
            messagebox.showinfo("조문 이동", "첫 조문보다 앞은 없습니다.")
            return
        if self._preview_view.chosen_version is None:
            messagebox.showinfo(
                "조문 이동",
                "먼저 법령을 검색하고, 개정본을 체크해 주세요.",
            )
            return

        self._set_article_entry_text(format_article_for_entry(target))
        self._load_preview()

    def _set_article_entry_text(self, article_text: str) -> None:
        """조문 번호 칸을 통째로 바꾼다. 위/아래 이동은 조문 하나만 남긴다."""
        self._article_entry.delete(0, tk.END)
        self._article_entry.insert(0, article_text)

    def _load_full_preview(self) -> None:
        """[전체보기] 를 누르면 고른 판의 본문 전체를 불러온다. 조문 번호는 필요 없다."""
        version = self._preview_view.chosen_version
        if version is None:
            messagebox.showinfo("전체보기", "먼저 법령을 검색하고, 개정본을 체크해 주세요.")
            return

        self._preview_view.show_loading("전체")
        self._controller.start_loading_full_law_text(version)

    def _open_original_in_browser(self) -> None:
        """
        국가법령정보센터에서 지금 고른 판의 원문을 연다.

        미리보기(글자만)에는 표·별표가 빠질 수 있어, 사이트로 바로 대조할 때 쓴다.
        """
        version = self._preview_view.chosen_version
        if version is None:
            checked = [item for is_on, item in self._version_checkboxes if is_on.get()]
            version = checked[0] if checked else None
        if version is None:
            messagebox.showinfo(
                "원문 보기",
                "먼저 법령을 검색하고, 개정본을 체크해 주세요.",
            )
            return

        webbrowser.open(version.detail_page_url)

    def add_underline_phrase(
        self, phrase: str, detected_article: ArticleNumber | None = None
    ) -> None:
        """
        미리보기에서 드래그한 문구를 밑줄 칸에 덧붙인다.

        전체보기에서 조문 번호가 함께 오면 조문 칸에도 자동으로 채운다.
        조문 단위 미리보기에서는 detected_article 이 None 이라 조문 칸을 건드리지 않는다.
        """
        self._append_underline_phrase(phrase)

        # 전체보기인데 조 제목을 못 찾은 경우(머리말·부칙 등)만 안내한다.
        if self._preview_view.is_full_view_mode and detected_article is None:
            messagebox.showinfo(
                "조문 번호",
                "어느 조인지 몰라 조문 번호는 직접 넣어 주세요.",
            )
            return

        if detected_article is None:
            return

        current = self._article_entry.get()
        updated = append_article_to_entry_text(current, detected_article)
        self._article_entry.delete(0, tk.END)
        self._article_entry.insert(0, updated)

    def _add_underline_phrase_from_entry(self) -> None:
        """
        밑줄 문구 입력칸의 값을 칩 목록에 추가한다.
        """
        typed_phrase = self._underline_phrase_entry.get().strip()
        if not typed_phrase:
            messagebox.showinfo("밑줄", "밑줄 문구를 먼저 입력해 주세요.")
            return
        self._append_underline_phrase(typed_phrase)
        self._underline_phrase_entry.delete(0, tk.END)

    def _append_underline_phrase(self, phrase: str) -> None:
        """
        중복을 피하면서 밑줄 문구 목록에 추가한다.
        """
        cleaned_phrase = phrase.strip()
        if not cleaned_phrase:
            return
        if cleaned_phrase in self._underline_phrases:
            return
        self._underline_phrases.append(cleaned_phrase)
        self._render_underline_phrase_chips()

    def _on_underline_color_changed(self, _event=None) -> None:
        """
        밑줄 색을 바꾸면 미리보기 형광펜도 같은 계열로 맞춘다.

        PDF에 그을 색과 미리보기 칠이 어긋나면 '고른 색이 안 바뀐 것 같다'고
        느끼기 쉽다. Combobox 선택 직후 바로 반영한다.
        """
        self._apply_preview_highlight_for_current_color()

    def _apply_preview_highlight_for_current_color(self) -> None:
        """지금 Combobox에 있는 색 이름으로 미리보기 형광펜을 설정한다."""
        color_name = self._underline_color_picker.get() or DEFAULT_UNDERLINE_COLOR_NAME
        self._preview_view.set_selected_highlight_color(
            preview_highlight_for_name(color_name)
        )

    def _reset_underline_phrases(self) -> None:
        """
        빨간 밑줄 입력값과 미리보기 선택 표시를 초기화한다.
        """
        self._underline_phrase_entry.delete(0, tk.END)
        self._underline_phrases.clear()
        self._render_underline_phrase_chips()
        self._preview_view.clear_selected_phrases()

    def _remove_underline_phrase_at(self, index: int) -> None:
        """
        지정한 위치의 밑줄 문구 칩을 삭제한다.

        미리보기 빨간 표시도 같은 문구만큼 지워 양쪽이 어긋나지 않게 한다.
        """
        if not (0 <= index < len(self._underline_phrases)):
            return
        phrase = self._underline_phrases[index]
        del self._underline_phrases[index]
        self._render_underline_phrase_chips()
        self._preview_view.remove_selected_phrase(phrase)

    def _remove_underline_phrase_by_text(self, phrase: str) -> None:
        """
        미리보기에서 빨간 표시를 클릭해 지웠을 때 칩 목록을 맞춘다.

        미리보기 쪽 표시는 이미 지워진 상태이므로 remove_selected_phrase 는 부르지 않는다.
        """
        cleaned = phrase.strip()
        if cleaned in self._underline_phrases:
            self._underline_phrases.remove(cleaned)
            self._render_underline_phrase_chips()

    def _render_underline_phrase_chips(self) -> None:
        """
        현재 밑줄 문구 리스트를 칩 UI로 다시 그린다.
        """
        for widget in self._underline_chips_frame.winfo_children():
            widget.destroy()

        if not self._underline_phrases:
            ttk.Label(
                self._underline_chips_frame,
                text="아직 추가된 문구가 없습니다.",
                style="Hint.TLabel",
            ).pack(anchor="w")
            return

        for index, phrase in enumerate(self._underline_phrases):
            chip_row = ttk.Frame(self._underline_chips_frame)
            chip_row.pack(fill="x", pady=(0, 4))
            ttk.Label(
                chip_row,
                text=f"• {phrase}",
                wraplength=420,
            ).pack(side="left", fill="x", expand=True)
            ttk.Button(
                chip_row,
                text="삭제",
                command=lambda item_index=index: self._remove_underline_phrase_at(item_index),
            ).pack(side="right")

    def _browse_hwp_file(self) -> None:
        chosen = filedialog.askopenfilename(
            title="그림을 넣을 한글 파일 고르기",
            filetypes=[("한글 문서", "*.hwp"), ("모든 파일", "*.*")],
        )
        if chosen:
            self._hwp_path_entry.set_text(chosen)

    def _open_hwp_folder(self) -> None:
        """
        대상 문서의 폴더를 연다.

        아직 문서를 고르지 않았으면 결과물 기본 폴더를 연다.
        """
        typed_path = self._hwp_path_entry.get().strip()
        folder_path = Path(typed_path).parent if typed_path else OUTPUT_DIRECTORY
        self._open_folder(folder_path)

    def _open_saved_output_folder(self) -> None:
        """
        결과 한글 파일이 쌓이는 폴더를 연다.

        아직 한 번도 실행하지 않아 폴더가 없으면 만들어 연다.
        만들어 두지 않으면 탐색기가 경로를 못 찾아 아무 일도 안 한다.
        """
        try:
            OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
        except OSError:
            messagebox.showinfo(
                "저장된 폴더 열기",
                "저장 폴더를 만들지 못했습니다. 경로를 확인해 주세요.",
            )
            return
        self._open_folder(OUTPUT_DIRECTORY)

    def _open_folder(self, folder_path: Path) -> None:
        """탐색기로 폴더를 연다. 실패하면 안내만 하고 화면은 그대로 둔다."""
        try:
            os.startfile(str(folder_path))
        except OSError:
            messagebox.showinfo("폴더 열기", "폴더를 열지 못했습니다. 경로를 확인해 주세요.")

    def _on_use_existing_hwp_toggled(self) -> None:
        """
        '기존 한글 문서 사용' 체크 상태에 따라 관련 입력칸을 켜고 끈다.
        """
        entry_state = "normal" if self._should_use_existing_hwp.get() else "disabled"
        button_state = "normal" if self._should_use_existing_hwp.get() else "disabled"
        self._hwp_path_entry.configure(state=entry_state)
        self._browse_hwp_button.configure(state=button_state)
        self._open_hwp_folder_button.configure(state=button_state)

    def _disable_hwp_save_section(self) -> None:
        """
        5번 섹션 전체를 비활성화한다.

        현재는 저장 위치를 사용자에게 받지 않고 내부 규칙으로 자동 저장한다.
        요청에 따라 화면은 보여주되 모든 조작은 막아 둔다.
        """
        self._should_use_existing_hwp.set(False)
        self._use_existing_hwp_checkbutton.configure(state="disabled")
        self._hwp_path_entry.configure(state="disabled")
        self._browse_hwp_button.configure(state="disabled")
        self._open_hwp_folder_button.configure(state="disabled")
        for child in self._document_card.winfo_children():
            if isinstance(child, ttk.Frame):
                for nested in child.winfo_children():
                    if isinstance(nested, ttk.Radiobutton):
                        nested.configure(state="disabled")

    def _add_job(self) -> None:
        try:
            job = self._build_job_from_inputs()
        except ValueError as error:
            messagebox.showinfo("입력 확인", str(error))
            return

        self._append_job_to_list(job)
        self._article_entry.delete(0, tk.END)
        self._underline_phrase_entry.delete(0, tk.END)
        self._underline_phrases.clear()
        self._render_underline_phrase_chips()

    def _build_job_from_inputs(self) -> ArticleCaptureJob:
        if self._found_law is None:
            raise ValueError("먼저 법령을 검색해 주세요.")

        chosen_versions = [version for is_on, version in self._version_checkboxes if is_on.get()]
        if not chosen_versions:
            raise ValueError("캡처할 개정본을 하나 이상 체크해 주세요.")

        article_text = self._article_entry.get().strip()
        # ValueError 의 안내 문구를 그대로 화면으로 올린다.
        article_numbers = parse_article_numbers(article_text)

        # 밑줄은 필수가 아니다. 비어 있으면 조문 그림만 만들고,
        # 실행 직전에 "그래도 진행할까요?" 로 한 번 더 확인한다.
        phrases = list(self._underline_phrases)
        color_name = self._underline_color_picker.get() or DEFAULT_UNDERLINE_COLOR_NAME

        return ArticleCaptureJob(
            law_name=self._found_law.law_name,
            target_versions=chosen_versions,
            article_numbers=article_numbers,
            underline_phrases=phrases,
            underline_color=underline_color_for_name(color_name),
            target_hwp_path=self._read_target_document_path(),
            insertion_mode=_find_insertion_mode(self._insertion_mode.get()),
            should_add_caption=self._should_add_caption.get(),
            should_add_border=self._should_add_border.get(),
            law_id=self._found_law.law_id,
            kind_label=self._found_law.kind_label,
        )

    def _read_target_document_path(self) -> Path | None:
        """
        그림을 넣을 기존 문서 경로를 읽는다. 비워두면 None (새 문서를 만든다).

        빈 칸을 빈 경로로 넘기면 한글이 그것을 현재 폴더로 알아듣고 열려다 실패한다.
        '고르지 않았다' 는 것을 None 으로 분명히 구분해서 넘긴다.
        """
        if not self._should_use_existing_hwp.get():
            return None

        typed_path = self._hwp_path_entry.get().strip()
        if not typed_path:
            raise ValueError(
                "'기존 한글 문서에 넣기'를 체크했다면 파일을 골라주세요.\n"
                "새 문서로 만들려면 체크를 끄면 됩니다."
            )

        document_path = Path(typed_path)
        if not document_path.is_file():
            raise ValueError(
                f"'{document_path.name}' 파일을 찾을 수 없습니다.\n"
                f"[찾아보기] 로 고르시거나, 새 문서로 만들려면 칸을 비워두세요."
            )
        return document_path

    def _remove_selected_job(self) -> None:
        """
        고른 대기 항목을 지운다. 여러 줄을 골랐으면 함께 지운다.

        앞에서부터 지우면 뒤 번호가 밀리므로, 아래쪽부터 지운다.
        """
        if not self._jobs:
            return
        selected = self._job_listbox.curselection()
        if not selected:
            messagebox.showinfo("선택 삭제", "삭제할 항목을 먼저 골라 주세요.")
            return
        for index in reversed(selected):
            self._job_listbox.delete(index)
            del self._jobs[index]
        self._update_figure_count()

    def _remove_all_jobs(self) -> None:
        """담은 작업 대기 목록을 전부 비운다."""
        if not self._jobs:
            return
        should_remove = messagebox.askyesno(
            "전체 삭제 확인",
            "담은 작업 대기 목록을 모두 지울까요?",
        )
        if not should_remove:
            return
        self._job_listbox.delete(0, tk.END)
        self._jobs.clear()
        self._update_figure_count()

    def _update_figure_count(self) -> None:
        total = sum(job.expected_figure_count for job in self._jobs)
        self._figure_count_label.config(
            text=f"→ 만들어질 그림 {total}장" if self._jobs else ""
        )
        self._footer_summary_label.config(
            text=(
                f"담은 작업 {len(self._jobs)}건 · 만들어질 그림 {total}장"
                if self._jobs
                else "담은 작업 없음"
            )
        )
        self._refresh_action_button_states()

    def _refresh_action_button_states(self) -> None:
        """
        목록 상태에 맞춰 실행/삭제 버튼 활성 상태를 맞춘다.
        """
        has_any_job = bool(self._jobs)
        state = "normal" if has_any_job else "disabled"
        self._start_button.config(state=state)
        self._remove_selected_job_button.config(state=state)
        self._add_jobs_to_capture_memory_button.config(state=state)
        self._remove_all_jobs_button.config(state=state)

    def _reset_input_values(self) -> None:
        """
        입력 화면에서 채운 값들을 한 번에 초기화한다.

        실수로 지워지는 일을 막기 위해 재확인을 받고,
        예외가 나면 조용히 실패하지 않고 안내한다.
        """
        if not self._has_any_entered_values():
            messagebox.showinfo("입력 값 리셋", "리셋할 입력 값이 없습니다.")
            return

        should_reset = messagebox.askyesno(
            "입력 값 리셋 확인",
            "선택한 법령/개정본/조문/밑줄/작업 대기 목록을 모두 초기화할까요?",
        )
        if not should_reset:
            return

        try:
            self._law_name_entry.set_text("")
            self._show_search_failure("법령·고시 이름을 넣고 [검색]을 누르세요")
            self._found_law = None
            self._candidates = []

            self._article_entry.delete(0, tk.END)
            self._underline_phrase_entry.delete(0, tk.END)
            self._underline_phrases.clear()
            self._render_underline_phrase_chips()

            for widget in self._version_list_frame.winfo_children():
                widget.destroy()
            self._version_checkboxes.clear()
            self._are_all_versions_selected.set(True)
            self._selected_count_label.config(text="")
            self._many_versions_warning.config(text="")
            self._version_hint.config(
                text="법령을 검색하고 시점을 정하면 여기에 개정본이 나열됩니다.\n그림으로 만들 개정본을 체크해 주세요.",
                foreground="gray",
            )
            self._preview_view.reset_view()

            self._job_listbox.delete(0, tk.END)
            self._jobs.clear()
            self._update_figure_count()

            messagebox.showinfo("입력 값 리셋", "입력 값이 초기화되었습니다.")
        except Exception as error:
            messagebox.showerror(
                "입력 값 리셋",
                f"리셋 중 문제가 발생했습니다.\n{error}",
            )

    def _has_any_entered_values(self) -> bool:
        """
        현재 화면에 사용자가 입력/선택해 둔 값이 있는지 본다.
        """
        has_law_text = bool(self._law_name_entry.get().strip())
        has_found_law = self._found_law is not None or bool(self._candidates)
        has_versions = bool(self._version_checkboxes)
        has_article = bool(self._article_entry.get().strip())
        has_underlines = bool(self._underline_phrase_entry.get().strip()) or bool(self._underline_phrases)
        has_jobs = bool(self._jobs)
        return any((has_law_text, has_found_law, has_versions, has_article, has_underlines, has_jobs))

    def _request_start(self) -> None:
        if not self._jobs:
            messagebox.showinfo("실행", "먼저 조건을 목록에 담아 주세요.")
            return

        # 밑줄이 하나도 없는 작업이 있으면 한 번 확인한다.
        # 그래도 진행하면 annotate 가 밑줄 없이 조문 그림만 만든다.
        has_job_without_underline = any(
            not job.underline_phrases for job in self._jobs
        )
        if has_job_without_underline:
            should_continue = messagebox.askyesno(
                "밑줄 없음",
                "밑줄을 선택 하지 않았습니다. 그래도 진행할까요?",
            )
            if not should_continue:
                return

        self._on_start_requested(list(self._jobs))


def _iter_widgets(widget):
    """위젯 아래의 모든 위젯을 차례로 돌려준다."""
    for child in widget.winfo_children():
        yield child
        yield from _iter_widgets(child)


def _build_version_row_label(version: LawVersion) -> str:
    """
    개정본 목록 한 줄에 쓸 문구를 만든다.

    그 판이 시행되던 당시의 이름이 지금 이름과 다르면 함께 보여준다.
    이름이 바뀐 법령·고시가 드물지 않은데(「주택법」은 1973년에
    「주택건설촉진법」이었다), 목록에 지금 이름만 나오면 옛 이름으로 찾던
    사용자가 엉뚱한 것을 찾았다고 여기게 된다.
    """
    status = "현행" if version.is_currently_in_effect else "구"
    row = (
        f"{version.effective_date_label}   "
        f"{version.promulgation_label[:40]}   ({status})"
    )
    if version.has_different_name_now:
        row = f"{row}\n        └ 당시 이름: {version.historical_law_name}"
    return row


def _build_name_change_notice(versions: list[LawVersion]) -> str:
    """
    '이름이 바뀌었습니다' 안내 문구를 만든다. 알릴 것이 없으면 빈 글자.

    목록에 보이는 판들만 본다. 그 판들이 곧 사용자가 그림으로 만들 것이고,
    캡션에 들어갈 이름이 지금 이름과 다르다는 사실을 미리 알려야 하기 때문이다.
    (연혁 전체를 다시 물어볼 필요가 없어 값도 싸다)
    """
    former_names = [
        version.historical_law_name
        for version in versions
        if version.has_different_name_now
    ]
    if not former_names:
        return ""

    # 같은 이름이 여러 판에 걸쳐 있으므로 중복을 없애되 순서는 지킨다.
    unique_former_names = list(dict.fromkeys(former_names))
    current_name = versions[0].law_name

    lines = ["ⓘ 이름이 바뀐 적이 있습니다. 캡션에는 각 판의 '당시 이름' 이 들어갑니다."]
    for former_name in unique_former_names:
        lines.append(f"     당시: {former_name}")
    lines.append(f"     지금: {current_name}")
    return "\n".join(lines)


def _underline_color_name_for_set(color_rgb: tuple[float, float, float]) -> str:
    """세트에 저장할 색 이름. 목록에 없는 색이면 기본 빨강."""
    color_name = _underline_color_display_name(color_rgb)
    if color_name == "색지정":
        return DEFAULT_UNDERLINE_COLOR_NAME
    return color_name


def _underline_color_display_name(
    color_rgb: tuple[float, float, float],
) -> str:
    """작업 목록에 보여줄 밑줄 색 이름. 목록에 없으면 RGB 그대로."""
    for name, rgb in UNDERLINE_COLOR_CHOICES:
        if rgb == color_rgb:
            return name
    return "색지정"


def _parse_date(text: str, field_name: str) -> date:
    """
    날짜 칸에 적은 글을 날짜로 읽는다.

    칸에 넣는 방식이 사람마다 다르다. 아래는 모두 2025년 6월 1일이다.
      2025-06-01 / 2025/6/1 / 2025.6.1. / 2025. 6. 1.
      25.06.01 / 25.6.1. / 20250601
    연도를 두 자리로 적으면 70 이상은 1900년대(73 → 1973), 그 미만은 2000년대(25 → 2025)다.
    옛 법령을 73년으로 적는 경우와, 요즘 사건을 25년으로 적는 경우를 같이 받기 위해서다.
    """
    pieces = _date_number_pieces(text)
    if pieces is None:
        raise ValueError(
            f"{field_name}을 알아듣지 못했습니다. "
            "예: 2025-06-01, 2025.6.1., 25/6/1"
        )

    year_text, month_text, day_text = pieces
    try:
        year = int(year_text)
        month = int(month_text)
        day = int(day_text)
    except ValueError:
        raise ValueError(
            f"{field_name}을 알아듣지 못했습니다. "
            "예: 2025-06-01, 2025.6.1., 25/6/1"
        )

    if len(year_text) == 2:
        year += 1900 if year >= 70 else 2000
    elif len(year_text) != 4:
        raise ValueError(
            f"{field_name}의 연도는 두 자리(25) 또는 네 자리(2025)로 적어 주세요."
        )

    try:
        return date(year, month, day)
    except ValueError:
        raise ValueError(
            f"{field_name}에 없는 날짜입니다. 월은 1~12, 일은 그 달에 있는 날로 적어 주세요."
        )


def _date_number_pieces(text: str) -> tuple[str, str, str] | None:
    """
    날짜 글에서 연·월·일 숫자만 뽑는다. 구분자는 빼 버린다.

    못 알아들으면 None. 호출하는 쪽에서 안내 문장을 만든다.
    """
    cleaned = text.strip()
    cleaned = cleaned.replace("년", ".").replace("월", ".").replace("일", "")
    cleaned = cleaned.replace("/", ".").replace("-", ".")
    cleaned = cleaned.replace(" ", "")
    cleaned = cleaned.strip(".")
    if not cleaned:
        return None

    if cleaned.isdigit() and len(cleaned) == 8:
        return cleaned[0:4], cleaned[4:6], cleaned[6:8]
    if cleaned.isdigit() and len(cleaned) == 6:
        return cleaned[0:2], cleaned[2:4], cleaned[4:6]

    parts = [part for part in cleaned.split(".") if part]
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        return None
    return parts[0], parts[1], parts[2]


def _find_insertion_mode(label: str) -> InsertionMode:
    return next(mode for mode in InsertionMode if mode.value == label)
