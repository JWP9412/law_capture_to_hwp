"""
조문 미리보기 패널 — 조문 내용을 보여주고, 드래그로 밑줄 칠 부분을 고르게 한다.

왜 필요한가:
  이것이 없으면 조문에 정확히 뭐라고 쓰여 있는지 모르는 채로
  밑줄 칠 문구를 외워서 타이핑해야 한다. 법령정보센터를 따로 열어
  확인하고 옮겨 적는 일이 매번 반복되고, 오타가 나면 실행이 실패한다.

이 파일은 '보여주기' 와 '고른 것을 알려주기' 만 한다.
조문을 실제로 불러오는 일은 controller 에게 부탁한다.
"""
import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from core.article_number import (
    ArticleNumber,
    find_article_covering_character_offset,
)
from core.models import LawVersion

SELECTED_PHRASE_TAG = "고른부분"
SELECTED_PHRASE_BACKGROUND = "#ffe0e0"  # 옅은 빨강 — 밑줄로 고른 부분

# 찾기(Ctrl+F)로 맞춘 곳. 고른 부분(옅은 빨강)과 색을 다르게 해 헷갈리지 않게 한다.
FOUND_TAG = "찾은곳"
FOUND_BACKGROUND = "#fff59d"  # 옅은 노랑
CURRENT_FOUND_TAG = "지금찾은곳"
CURRENT_FOUND_BACKGROUND = "#ffd54f"  # 진한 노랑 — 지금 보고 있는 곳

GUIDE_BEFORE_LOADING = (
    "조문 번호를 넣고 [미리보기] 를 누르거나, [전체보기] 로 본문 전체를 볼 수 있습니다. "
    "표·별표는 [원문 보기] 로 사이트에서 확인하세요."
)
GUIDE_WHILE_LOADING = "조문을 불러오는 중입니다…"
GUIDE_AFTER_LOADING = (
    "밑줄 칠 부분을 마우스로 드래그하세요. 여러 번 고를 수 있습니다. "
    "(Ctrl+F 로 찾기)"
)
GUIDE_AFTER_FULL_LOADING = (
    "전체보기입니다. 드래그하면 밑줄 문구와 조문 번호가 함께 채워집니다. "
    "(본문 글자만 표시 · Ctrl+F 로 찾기 · 표·별표는 [원문 보기])"
)


class PreviewView(ttk.LabelFrame):
    """조문 미리보기 패널."""

    def __init__(
        self,
        parent,
        on_phrase_selected: Callable[[str, ArticleNumber | None], None],
        on_open_original: Callable[[], None],
    ):
        super().__init__(parent, text="조문 미리보기", padding=6)
        self._on_phrase_selected = on_phrase_selected
        self._on_open_original = on_open_original
        self._shown_versions: list[LawVersion] = []
        # 전체보기일 때만 드래그로 조문 번호를 자동 채운다.
        self._is_full_view_mode = False

        # 찾기 결과. 각 항목은 (시작 인덱스, 끝 인덱스) 문자열이다.
        self._found_ranges: list[tuple[str, str]] = []
        self._current_found_index = -1
        self._is_find_bar_visible = False

        self._build_header_row()
        self._build_find_bar()
        self._build_text_area()
        self._build_guide_label()

    # ------------------------------------------------------------------
    # 화면 구성
    # ------------------------------------------------------------------

    def _build_header_row(self) -> None:
        row = ttk.Frame(self)
        row.pack(fill="x", pady=(0, 4))

        ttk.Label(row, text="어느 판:").pack(side="left")
        self._version_picker = ttk.Combobox(row, state="disabled", width=28)
        self._version_picker.pack(side="left", padx=4)
        self._version_picker.bind("<<ComboboxSelected>>", self._on_version_changed)

        self._article_label = ttk.Label(row, text="", foreground="gray")
        self._article_label.pack(side="left", padx=6)

        ttk.Button(
            row, text="원문 보기", command=self._on_open_original
        ).pack(side="right")

    def _build_find_bar(self) -> None:
        """
        Ctrl+F 로 나타나는 찾기 막대.

        평소에는 숨겨 두고, 필요할 때만 헤더와 본문 사이에 끼워 넣는다.
        웹브라우저나 한글의 찾기와 같은 흐름을 맞추기 위해서다.
        """
        self._find_bar = ttk.Frame(self)

        ttk.Label(self._find_bar, text="찾기").pack(side="left")
        self._find_entry = ttk.Entry(self._find_bar, width=20)
        self._find_entry.pack(side="left", padx=4)
        self._find_entry.bind("<KeyRelease>", self._on_find_query_changed)
        self._find_entry.bind("<Return>", lambda _event: self._go_to_next_match())
        self._find_entry.bind(
            "<Shift-Return>", lambda _event: self._go_to_previous_match()
        )
        self._find_entry.bind("<Escape>", lambda _event: self._hide_find_bar())

        ttk.Button(
            self._find_bar, text="◀", width=3, command=self._go_to_previous_match
        ).pack(side="left")
        ttk.Button(
            self._find_bar, text="▶", width=3, command=self._go_to_next_match
        ).pack(side="left", padx=(2, 0))
        ttk.Button(
            self._find_bar, text="X", width=3, command=self._hide_find_bar
        ).pack(side="left", padx=(4, 0))

        self._find_status_label = ttk.Label(
            self._find_bar, text="", foreground="gray"
        )
        self._find_status_label.pack(side="left", padx=8)

    def _build_text_area(self) -> None:
        text_frame = ttk.Frame(self)
        text_frame.pack(fill="both", expand=True)

        # state 를 normal 로 두는 이유: disabled 로 하면 드래그 선택이 안 된다.
        # 대신 키 입력을 막아 사용자가 내용을 고치지 못하게 한다.
        self._text_box = tk.Text(
            text_frame,
            height=16,
            wrap="word",
            font=("맑은 고딕", 10),
            relief="flat",
            borderwidth=1,
            padx=8,
            pady=6,
        )
        scrollbar = ttk.Scrollbar(text_frame, command=self._text_box.yview)
        self._text_box.configure(yscrollcommand=scrollbar.set)
        self._text_box.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._text_box.tag_configure(
            SELECTED_PHRASE_TAG, background=SELECTED_PHRASE_BACKGROUND
        )
        self._text_box.tag_configure(FOUND_TAG, background=FOUND_BACKGROUND)
        self._text_box.tag_configure(
            CURRENT_FOUND_TAG, background=CURRENT_FOUND_BACKGROUND
        )
        self._text_box.bind("<ButtonRelease-1>", self._on_drag_finished)
        self._text_box.bind("<Key>", self._block_typing)
        # 미리보기 안에서도, 창 전체에서도 Ctrl+F 가 통하게 한다.
        self._text_box.bind("<Control-f>", self._show_find_bar)
        self._text_box.bind("<Control-F>", self._show_find_bar)
        self.bind_all("<Control-f>", self._show_find_bar_if_focused)
        self.bind_all("<Control-F>", self._show_find_bar_if_focused)

    def _build_guide_label(self) -> None:
        self._guide_label = ttk.Label(self, text=GUIDE_BEFORE_LOADING, style="Hint.TLabel")
        self._guide_label.pack(fill="x", pady=(4, 0))

    def scroll_text_by_wheel(self, delta: int) -> None:
        """미리보기 본문만 스크롤한다. (창 휠 처리기가 포인터가 본문 위일 때 부름)"""
        self._text_box.yview_scroll(int(-delta / 120), "units")

    @property
    def text_box(self) -> tk.Text:
        """창 휠 처리기가 '지금 포인터가 미리보기 위인가' 판별할 때 쓴다."""
        return self._text_box

    @property
    def is_full_view_mode(self) -> bool:
        """지금 본문이 전체보기인지."""
        return self._is_full_view_mode

    # ------------------------------------------------------------------
    # 바깥(입력 화면)에서 부르는 것들
    # ------------------------------------------------------------------

    def show_available_versions(self, versions: list[LawVersion]) -> None:
        """미리볼 수 있는 판들을 목록에 채운다. 기본은 가장 오래된 판이다."""
        self._shown_versions = versions

        if not versions:
            self._version_picker.configure(values=[], state="disabled")
            self._version_picker.set("")
            return

        self._version_picker.configure(
            values=[version.effective_date_label for version in versions],
            state="readonly",
        )
        self._version_picker.current(0)

    @property
    def chosen_version(self) -> LawVersion | None:
        """지금 미리보기로 고른 판."""
        index = self._version_picker.current()
        if 0 <= index < len(self._shown_versions):
            return self._shown_versions[index]
        return None

    def show_loading(self, article_label: str) -> None:
        self._is_full_view_mode = False
        self._article_label.config(text=article_label)
        self._replace_text("")
        self._guide_label.config(text=GUIDE_WHILE_LOADING, foreground="gray")

    def show_article(
        self, article_label: str, text: str, is_full_view: bool = False
    ) -> None:
        self._is_full_view_mode = is_full_view
        self._article_label.config(text=article_label)
        self._replace_text(text)
        guide = GUIDE_AFTER_FULL_LOADING if is_full_view else GUIDE_AFTER_LOADING
        self._guide_label.config(text=guide, foreground="gray")

    def show_failure(self, message: str) -> None:
        self._is_full_view_mode = False
        self._replace_text("")
        self._guide_label.config(
            text=f"{message}\n밑줄 문구는 직접 적어 넣으셔도 됩니다.", foreground="red"
        )

    def clear_selected_phrases(self) -> None:
        """
        드래그로 고른 밑줄 표시만 지운다.

        본문 텍스트 자체는 유지하고, 선택 하이라이트 태그만 제거한다.
        """
        self._text_box.tag_remove(SELECTED_PHRASE_TAG, "1.0", tk.END)

    def reset_view(self) -> None:
        """
        입력 화면의 리셋 버튼에서 미리보기 상태를 초기화할 때 쓴다.
        """
        self._shown_versions = []
        self._is_full_view_mode = False
        self._version_picker.configure(values=[], state="disabled")
        self._version_picker.set("")
        self._article_label.config(text="")
        self._replace_text("")
        self._guide_label.config(text=GUIDE_BEFORE_LOADING, foreground="gray")

    # ------------------------------------------------------------------
    # 찾기 (Ctrl+F)
    # ------------------------------------------------------------------

    def _show_find_bar_if_focused(self, event=None):
        """
        창 전체의 Ctrl+F 를 받되, 미리보기가 보이는 동안에만 반응한다.

        입력 칸에 글을 쓰고 있을 때도 Ctrl+F 가 먹히면 불편하므로,
        미리보기 패널이 화면에 붙어 있을 때만 연다.
        """
        try:
            if not self.winfo_ismapped():
                return
        except tk.TclError:
            return
        return self._show_find_bar(event)

    def _show_find_bar(self, _event=None):
        """찾기 막대를 헤더와 본문 사이에 끼워 넣고 입력칸으로 커서를 보낸다."""
        if not self._is_find_bar_visible:
            # pack 순서를 헤더 바로 다음으로 고정한다.
            self._find_bar.pack(fill="x", pady=(0, 4), after=self.winfo_children()[0])
            self._is_find_bar_visible = True
        self._find_entry.focus_set()
        self._find_entry.selection_range(0, tk.END)
        self._refresh_find_highlights()
        return "break"

    def _hide_find_bar(self) -> None:
        """찾기 막대를 닫고 노란 표시만 지운다. 드래그로 고른 표시는 남긴다."""
        self._clear_find_highlights()
        self._find_entry.delete(0, tk.END)
        self._find_status_label.config(text="")
        if self._is_find_bar_visible:
            self._find_bar.pack_forget()
            self._is_find_bar_visible = False
        self._text_box.focus_set()

    def _on_find_query_changed(self, _event=None) -> None:
        self._refresh_find_highlights()

    def _refresh_find_highlights(self) -> None:
        """입력한 글자에 맞는 곳을 전부 노란으로 칠하고 개수를 보여준다."""
        self._clear_find_highlights()
        query = self._find_entry.get()
        if not query:
            self._find_status_label.config(text="")
            return

        self._found_ranges = self._collect_match_ranges(query)
        if not self._found_ranges:
            self._find_status_label.config(text="찾는 글자가 없습니다")
            return

        for start, end in self._found_ranges:
            self._text_box.tag_add(FOUND_TAG, start, end)

        self._current_found_index = 0
        self._highlight_current_match()

    def _collect_match_ranges(self, query: str) -> list[tuple[str, str]]:
        """본문에서 찾는 글자가 나오는 자리들을 모두 모은다."""
        ranges: list[tuple[str, str]] = []
        start = "1.0"
        while True:
            found = self._text_box.search(query, start, stopindex=tk.END, nocase=True)
            if not found:
                break
            end = f"{found}+{len(query)}c"
            ranges.append((found, end))
            start = end
        return ranges

    def _go_to_next_match(self) -> None:
        if not self._found_ranges:
            return
        self._current_found_index = (
            self._current_found_index + 1
        ) % len(self._found_ranges)
        self._highlight_current_match()

    def _go_to_previous_match(self) -> None:
        if not self._found_ranges:
            return
        self._current_found_index = (
            self._current_found_index - 1
        ) % len(self._found_ranges)
        self._highlight_current_match()

    def _highlight_current_match(self) -> None:
        """지금 보고 있는 곳만 진한 노랑으로 바꾸고 화면을 그쪽으로 옮긴다."""
        self._text_box.tag_remove(CURRENT_FOUND_TAG, "1.0", tk.END)
        start, end = self._found_ranges[self._current_found_index]
        self._text_box.tag_add(CURRENT_FOUND_TAG, start, end)
        self._text_box.see(start)
        self._find_status_label.config(
            text=f"{len(self._found_ranges)}개 중 {self._current_found_index + 1}번째"
        )

    def _clear_find_highlights(self) -> None:
        self._text_box.tag_remove(FOUND_TAG, "1.0", tk.END)
        self._text_box.tag_remove(CURRENT_FOUND_TAG, "1.0", tk.END)
        self._found_ranges = []
        self._current_found_index = -1

    # ------------------------------------------------------------------
    # 사용자 조작에 대한 반응
    # ------------------------------------------------------------------

    def _on_drag_finished(self, _event=None) -> None:
        """
        드래그를 뗀 순간 고른 글자를 밑줄 목록에 넘긴다.

        같은 문구가 미리보기에 두 번 이상 나오면 "문구 [N번째]" 형태로 넘긴다.
        전체보기면 선택 시작 위치가 속한 조문 번호도 함께 넘긴다.
        """
        selected = self._read_selected_text()
        if not selected:
            return

        try:
            selection_start = self._text_box.index("sel.first")
        except tk.TclError:
            return

        self._text_box.tag_add(SELECTED_PHRASE_TAG, "sel.first", "sel.last")
        phrase = self._label_with_occurrence(selected, selection_start)

        detected_article: ArticleNumber | None = None
        if self._is_full_view_mode:
            # tk 인덱스 "줄.칸" 을 글자 위치로 바꿔 조문 제목을 찾는다.
            character_offset = self._character_offset_of(selection_start)
            full_text = self._text_box.get("1.0", "end-1c")
            detected_article = find_article_covering_character_offset(
                full_text, character_offset
            )

        self._on_phrase_selected(phrase, detected_article)

    def _character_offset_of(self, text_index: str) -> int:
        """
        tk Text 인덱스(예: '12.5')를 본문 맨 앞부터의 글자 위치로 바꾼다.

        find_article_covering_character_offset 가 줄바꿈 포함 글자 위치를 받기 때문이다.
        """
        return len(self._text_box.get("1.0", text_index))

    def _label_with_occurrence(self, selected: str, selection_start: str) -> str:
        """고른 자리가 전체에서 몇 번째인지 세어 꼬리표를 붙인다."""
        ranges = self._collect_match_ranges(selected)
        if len(ranges) <= 1:
            return selected

        for index, (start, _end) in enumerate(ranges, start=1):
            if self._text_box.compare(start, "==", selection_start):
                return f"{selected} [{index}번째]"
        return selected

    def _read_selected_text(self) -> str:
        try:
            return self._text_box.get("sel.first", "sel.last").strip()
        except tk.TclError:
            return ""  # 선택된 것이 없으면 tkinter 가 오류를 낸다

    def _block_typing(self, event) -> str | None:
        """
        내용을 고치지 못하게 막는다.

        복사(Ctrl+C)·찾기(Ctrl+F)·화살표 이동은 허용한다.
        조문을 눈으로 훑거나 일부를 복사·찾는 것은 자연스러운 일이기 때문이다.
        """
        is_copy = event.state & 0x0004 and event.keysym.lower() == "c"
        is_find = event.state & 0x0004 and event.keysym.lower() == "f"
        is_navigation = event.keysym in (
            "Left", "Right", "Up", "Down", "Home", "End", "Prior", "Next",
        )
        return None if (is_copy or is_find or is_navigation) else "break"

    def _on_version_changed(self, _event=None) -> None:
        """다른 판을 고르면 내용을 비운다. 다시 [미리보기]/[전체보기] 를 눌러야 한다."""
        self._is_full_view_mode = False
        self._replace_text("")
        self._guide_label.config(
            text="다른 판을 골랐습니다. [미리보기] 또는 [전체보기] 를 다시 눌러주세요.",
            foreground="gray",
        )

    def _replace_text(self, text: str) -> None:
        self._clear_find_highlights()
        self._text_box.delete("1.0", tk.END)
        if text:
            self._text_box.insert("1.0", text)
