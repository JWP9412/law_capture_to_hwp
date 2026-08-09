"""
화면 1 — 조건을 입력하고 작업 목록에 담는 화면.

이 파일은 '보여주기' 와 '입력받기' 만 한다.
법령을 실제로 찾는 일은 controller 에게 부탁한다.
"""
import tkinter as tk
import webbrowser
from datetime import date, datetime
import os
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from config import InsertionMode
from core.article_number import (
    ArticleNumber,
    append_article_to_entry_text,
    build_article_range_label,
    parse_article_numbers,
)
from core.errors import LawCaptureError
from core.favorites import FavoriteLaw
from core.models import ArticleCaptureJob, LawVersion
from ui.favorites_dialog import FavoritesSettingsDialog
from ui.preview_view import PreviewView
from ui.widgets import HintEntry, StepCard, VCheckbutton

PERIOD_MODE = "기간 안의 모든 개정본"
SINGLE_DATE_MODE = "특정 시점 하나"
ALL_TIME_MODE = "전체 기간"

# 개정본 목록이 창을 밀어내지 않도록 목록만 스크롤되게 한다.
# 「주택법」처럼 172개가 나와도 창 크기는 그대로다.
VERSION_LIST_VISIBLE_HEIGHT_IN_PIXELS = 140

# 이 개수 이상이면 '필요한 것만 체크하세요' 안내를 눈에 띄게 보여준다.
MANY_VERSIONS_WARNING_THRESHOLD = 20

MODE_FIND_BUTTON_LABELS = {
    SINGLE_DATE_MODE: "그 시점 판 찾기",
    PERIOD_MODE: "개정본 찾기",
    ALL_TIME_MODE: "전체 개정본 찾기",
}


class InputView(ttk.Frame):
    """조건 입력 화면."""

    def __init__(self, parent, controller, on_start_requested):
        super().__init__(parent, padding=12)
        self._controller = controller
        self._on_start_requested = on_start_requested

        self._found_law = None
        self._candidates: list = []  # 검색으로 찾은 법령 후보들
        self._version_checkboxes: list[tuple[tk.BooleanVar, LawVersion]] = []
        self._jobs: list[ArticleCaptureJob] = []
        self._underline_phrases: list[str] = []
        self._favorites: list[FavoriteLaw] = []

        # 하단 동작 바를 먼저 붙여 둔다.
        # 본문이 길어져도 [실행] 버튼이 항상 화면 아래에 남게 하려는 목적이다.
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

        self._build_law_search_row()
        self._build_period_row()
        self._build_version_list()
        self._build_article_rows()
        self._build_job_list()
        self._preview_view.pack(fill="both", expand=True, pady=(0, 8))
        self._build_document_rows()
        self._refresh_favorites_picker()

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
        self._are_all_versions_selected = tk.BooleanVar(value=True)
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

        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=4)

        # 목록만 고정 높이 + 스크롤. 172줄이 창을 밀어내지 않게 한다.
        list_container = ttk.Frame(frame)
        list_container.pack(fill="x")

        self._version_canvas = tk.Canvas(
            list_container,
            height=180,
            highlightthickness=0,
        )
        self._version_scrollbar = ttk.Scrollbar(
            list_container, orient="vertical", command=self._version_canvas.yview
        )
        self._version_canvas.configure(yscrollcommand=self._version_scrollbar.set)
        self._version_canvas.pack(side="left", fill="both", expand=True)
        self._version_scrollbar.pack(side="right", fill="y")

        self._version_list_frame = ttk.Frame(self._version_canvas)
        self._version_list_window = self._version_canvas.create_window(
            (0, 0), window=self._version_list_frame, anchor="nw"
        )
        self._version_list_frame.bind(
            "<Configure>",
            lambda _event: self._version_canvas.configure(
                scrollregion=self._version_canvas.bbox("all")
            ),
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
                 "빼고 싶은 개정본은 체크를 끄시면 됩니다.",
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

    def _build_article_rows(self) -> None:
        # 이 카드를 오른쪽 미리보기와 비슷한 높이에 두면,
        # 사용자가 드래그 후 시선을 크게 옮기지 않고 밑줄 칸을 확인할 수 있다.
        card = StepCard(self._left_column, 3, "조문과 빨간 밑줄")
        card.pack(fill="x", pady=(0, 8))
        self._article_card = card

        article_row = ttk.Frame(card)
        article_row.grid(row=0, column=0, sticky="ew")
        article_row.grid_columnconfigure(1, weight=1)
        ttk.Label(article_row, text="조문 번호").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Label(
            article_row,
            text="예: 1 또는 1, 2 또는 1-3 또는 32의2",
            style="Hint.TLabel",
        ).grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(4, 0))
        input_row = ttk.Frame(article_row)
        input_row.grid(row=0, column=1, sticky="ew")
        input_row.grid_columnconfigure(0, weight=1)
        # 여러 조문·가지번호를 받을 수 있어 칸을 넓혀 둔다.
        self._article_entry = ttk.Entry(input_row, width=18)
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
        ttk.Label(underline_row, text="빨간 밑줄").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self._underline_phrase_entry = ttk.Entry(underline_row)
        self._underline_phrase_entry.grid(row=0, column=1, sticky="ew")
        self._underline_phrase_entry.bind("<Return>", lambda _event: self._add_underline_phrase_from_entry())
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

        chips_frame = ttk.Frame(card)
        chips_frame.grid(row=2, column=0, sticky="ew", pady=(4, 2))
        self._underline_chips_canvas = tk.Canvas(chips_frame, height=82, highlightthickness=0)
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
        ).grid(row=3, column=0, sticky="w", pady=(2, 0))

        # 캡션·테두리는 기본으로 켠다. 서면에 넣을 때는 거의 항상 필요하지만,
        # 이미 캡션이 있는 문서에 그림만 끼울 때는 끌 수 있어야 한다.
        option_row = ttk.Frame(card)
        option_row.grid(row=4, column=0, sticky="w", pady=(6, 0))
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

        action_row = ttk.Frame(card)
        action_row.grid(row=5, column=0, sticky="ew", pady=(8, 0))
        action_row.grid_columnconfigure(0, weight=1)
        ttk.Label(
            action_row,
            text="↓ 아래 작업 대기 목록에 추가됩니다",
            style="Hint.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Button(
            action_row,
            text="＋ 이 조건을 목록에 담기",
            command=self._add_job,
        ).grid(row=0, column=1, sticky="e")
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

        self._job_listbox = tk.Listbox(frame, height=6)
        self._job_listbox.pack(side="left", fill="both", expand=True)
        control_column = ttk.Frame(frame)
        control_column.pack(side="left", padx=6, anchor="n")
        self._remove_selected_job_button = ttk.Button(
            control_column,
            text="선택 삭제",
            command=self._remove_selected_job,
        )
        self._remove_selected_job_button.pack(fill="x")
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
        ttk.Separator(self, orient="horizontal").pack(side="bottom", fill="x", pady=(10, 6))
        action_row = ttk.Frame(self)
        action_row.pack(side="bottom", fill="x")
        ttk.Button(action_row, text="입력 값 리셋", command=self._reset_input_values).pack(side="left")
        self._start_button = ttk.Button(
            action_row, text="실행", command=self._request_start, state="disabled", style="Primary.TButton"
        )
        self._start_button.pack(side="right")

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

        self._show_search_results(candidates)
        self._refresh_version_list()

    def _show_search_results(self, candidates: list) -> None:
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

    def _refresh_version_list(self) -> None:
        """고른 시점 방식에 맞춰 개정본 목록을 다시 그린다."""
        for widget in self._version_list_frame.winfo_children():
            widget.destroy()
        self._version_checkboxes.clear()
        self._many_versions_warning.config(text="")
        self._version_canvas.yview_moveto(0)

        if self._found_law is None:
            self._version_hint.config(text="먼저 법령을 검색해 주세요.", foreground="gray")
            self._refresh_selection_summary(update_select_all=False)
            return

        try:
            versions = self._collect_versions_for_current_mode()
        except (LawCaptureError, ValueError) as error:
            self._version_hint.config(text=str(error), foreground="red")
            self._refresh_selection_summary(update_select_all=False)
            return

        # 전체 기간은 개정본이 아주 많을 수 있다 (주택법 172개).
        # 실수로 172장을 만들지 않도록 처음부터 전부 꺼 둔다.
        # 기간·단일 모드는 몇 개 안 되므로 지금처럼 전부 켠다.
        should_select_by_default = self._mode.get() != ALL_TIME_MODE

        if len(versions) >= MANY_VERSIONS_WARNING_THRESHOLD:
            self._many_versions_warning.config(
                text=(
                    f"개정본이 {len(versions)}개입니다. "
                    "필요한 것만 남기고 체크를 꺼주세요."
                    if should_select_by_default
                    else (
                        f"개정본이 {len(versions)}개입니다. "
                        "필요한 것만 체크해 주세요. (처음엔 전부 꺼져 있습니다)"
                    )
                )
            )

        self._version_hint.config(
            text="빼고 싶은 개정본은 체크를 끄시면 됩니다.", foreground="gray"
        )
        for version in versions:
            self._add_version_checkbox(version, is_selected_by_default=should_select_by_default)

        self._are_all_versions_selected.set(
            bool(versions) and should_select_by_default
        )
        self._refresh_selection_summary(update_select_all=False)

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

    def _add_version_checkbox(
        self, version: LawVersion, is_selected_by_default: bool = True
    ) -> None:
        is_selected = tk.BooleanVar(value=is_selected_by_default)
        status = "현행" if version.is_currently_in_effect else "구"
        VCheckbutton(
            self._version_list_frame,
            label_text=f"{version.effective_date_label}   {version.promulgation_label[:40]}   ({status})",
            variable=is_selected,
            command=self._refresh_selection_summary,
        ).pack(anchor="w")
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
            messagebox.showinfo("미리보기", "먼저 법령을 검색하고 개정본을 골라주세요.")
            return

        self._preview_view.show_loading(build_article_range_label(article_numbers))
        self._controller.start_loading_article_text(version, article_numbers)

    def _load_full_preview(self) -> None:
        """[전체보기] 를 누르면 고른 판의 본문 전체를 불러온다. 조문 번호는 필요 없다."""
        version = self._preview_view.chosen_version
        if version is None:
            messagebox.showinfo("전체보기", "먼저 법령을 검색하고 개정본을 골라주세요.")
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
                "먼저 법령을 검색하고 개정본을 골라주세요.",
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
            messagebox.showinfo("빨간 밑줄", "밑줄 문구를 먼저 입력해 주세요.")
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
        import config

        typed_path = self._hwp_path_entry.get().strip()
        folder_path = Path(typed_path).parent if typed_path else config.OUTPUT_DIRECTORY
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

        self._jobs.append(job)
        self._job_listbox.insert(
            tk.END,
            (
                f"{job.law_name} {job.article_label} "
                f"(개정본 {job.expected_figure_count}개)  밑줄 {len(job.underline_phrases)}건"
            ),
        )
        self._update_figure_count()
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

        if not self._underline_phrases:
            raise ValueError("빨간 밑줄을 칠 문구를 넣어주세요.")
        phrases = list(self._underline_phrases)

        return ArticleCaptureJob(
            law_name=self._found_law.law_name,
            target_versions=chosen_versions,
            article_numbers=article_numbers,
            underline_phrases=phrases,
            target_hwp_path=self._read_target_document_path(),
            insertion_mode=_find_insertion_mode(self._insertion_mode.get()),
            should_add_caption=self._should_add_caption.get(),
            should_add_border=self._should_add_border.get(),
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
        if not self._jobs:
            return
        selected = self._job_listbox.curselection()
        if not selected:
            messagebox.showinfo("선택 삭제", "삭제할 항목을 먼저 골라 주세요.")
            return
        index = selected[0]
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
        self._refresh_action_button_states()

    def _refresh_action_button_states(self) -> None:
        """
        목록 상태에 맞춰 실행/삭제 버튼 활성 상태를 맞춘다.
        """
        has_any_job = bool(self._jobs)
        state = "normal" if has_any_job else "disabled"
        self._start_button.config(state=state)
        self._remove_selected_job_button.config(state=state)
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
                text="법령을 검색하고 시점을 정하면 여기에 개정본이 나열됩니다.\n빼고 싶은 개정본은 체크를 끄시면 됩니다.",
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
        self._on_start_requested(list(self._jobs))


def _parse_date(text: str, field_name: str) -> date:
    try:
        return datetime.strptime(text.strip(), "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"{field_name}은 2025-06-01 형식으로 넣어주세요.")


def _find_insertion_mode(label: str) -> InsertionMode:
    return next(mode for mode in InsertionMode if mode.value == label)
