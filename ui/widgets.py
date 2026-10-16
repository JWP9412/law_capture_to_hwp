"""
입력 화면에서 반복되는 조각을 재사용하기 위한 위젯 모음.
"""
import tkinter as tk
from tkinter import ttk

from ui import theme


AUTO_WRAP_LABEL_STYLES = ("Hint.TLabel", "Danger.TLabel")

# 카드 오른쪽 가장자리에서 글자를 띄워 둘 여유(테두리·안쪽 여백·스크롤바 몫)
AUTO_WRAP_RIGHT_MARGIN = 34
AUTO_WRAP_MINIMUM_WIDTH = 120


def _iter_descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from _iter_descendants(child)


def install_auto_wrap(card: ttk.LabelFrame) -> None:
    """
    카드 안의 안내문이 카드 폭을 넘지 않고 알아서 줄바꿈되게 한다.

    왜 필요한가:
      글자 라벨은 줄바꿈 기준(wraplength)을 정해 주지 않으면 글자 전체를
      한 줄로 펴서 '이만큼의 폭이 필요하다' 고 요구한다. 긴 안내문 하나가
      700px 를 요구하면 그 카드 전체가 그만큼 넓어져야 하는데, 창이 작으면
      왼쪽 열은 그보다 좁게 배정되므로 오른쪽이 잘려 나간다.
      (실제로 [미리보기]·[전체보기]·[밑줄 초기화] 버튼이 잘렸다)

    어떻게 하는가:
      카드 폭이 바뀔 때마다, 카드 안 안내문마다 '카드 오른쪽 끝까지 남은 폭'
      만큼으로 줄바꿈 기준을 다시 정한다. 안내문이 놓인 왼쪽 위치를 빼서 계산하므로
      들여쓴 자리에 있는 안내문도 맞는다. 카드 안에 나중에 생기는 안내문도
      다음 폭 변화 때 함께 처리된다.
    """

    def rewrap(_event=None) -> None:
        card_right_edge = card.winfo_rootx() + card.winfo_width()
        for widget in _iter_descendants(card):
            if not isinstance(widget, ttk.Label):
                continue
            if str(widget.cget("style")) not in AUTO_WRAP_LABEL_STYLES:
                continue
            available = card_right_edge - widget.winfo_rootx() - AUTO_WRAP_RIGHT_MARGIN
            widget.configure(wraplength=max(AUTO_WRAP_MINIMUM_WIDTH, available))

    card.bind("<Configure>", rewrap, add="+")
    card.after_idle(rewrap)


class StepCard(ttk.LabelFrame):
    """
    번호가 붙은 카드 컨테이너.

    입력칸 배치를 grid 기반으로 통일해, 라벨 폭을 숫자로 맞추지 않아도
    줄 정렬이 안정적으로 유지되게 한다.
    """

    def __init__(self, parent, step_number: int, title: str):
        super().__init__(
            parent,
            text=f"{step_number}. {title}",
            padding=10,
            style="Card.TLabelframe",
        )
        self.grid_columnconfigure(1, weight=1)


def add_field(card: ttk.Frame, row_index: int, label_text: str, widget, hint_text: str = "") -> None:
    """
    카드 안에 '라벨 + 입력칸' 한 줄을 만든다.
    """
    label = ttk.Label(card, text=label_text)
    label.grid(row=row_index, column=0, sticky="w", padx=(0, 8), pady=(0, 6))
    widget.grid(row=row_index, column=1, sticky="ew", pady=(0, 6))
    if hint_text:
        hint = ttk.Label(card, text=hint_text, style="Hint.TLabel")
        hint.grid(row=row_index + 1, column=1, sticky="w", pady=(0, 6))


class HintEntry(ttk.Entry):
    """
    안내 글자(placeholder)를 갖는 입력칸.

    핵심:
      화면에는 안내 글자를 보여도, 실제 값으로는 절대 넘어가면 안 된다.
      그래서 get()을 재정의해 안내 글자가 보일 때는 빈 문자열을 돌려준다.
    """

    def __init__(self, parent, hint_text: str, **kwargs):
        super().__init__(parent, **kwargs)
        self._hint_text = hint_text
        self._is_showing_hint = False

        self.bind("<FocusIn>", self._hide_hint)
        self.bind("<FocusOut>", self._show_hint_if_needed)
        self._show_hint_if_needed()

    def get(self) -> str:  # type: ignore[override]
        value = super().get()
        return "" if self._is_showing_hint else value

    def insert(self, index, string):  # type: ignore[override]
        """
        코드에서 직접 insert 를 불러도 안내글자 상태가 꼬이지 않게 맞춘다.
        """
        if self._is_showing_hint:
            super().delete(0, tk.END)
            self._is_showing_hint = False
        self.configure(foreground=theme.TEXT_PRIMARY)
        return super().insert(index, string)

    def delete(self, first, last=None):  # type: ignore[override]
        result = super().delete(first, last)
        if not super().get() and self.focus_get() != self:
            self._show_hint_if_needed()
        return result

    def set_text(self, value: str) -> None:
        """기존 입력을 지우고 값을 넣는다. 안내글자 상태도 같이 맞춘다."""
        self._hide_hint()
        super().delete(0, tk.END)
        if value:
            super().insert(0, value)
            self.configure(foreground=theme.TEXT_PRIMARY)
            self._is_showing_hint = False
        else:
            self._show_hint_if_needed()

    def _show_hint_if_needed(self, _event=None) -> None:
        if super().get():
            return
        super().delete(0, tk.END)
        super().insert(0, self._hint_text)
        self.configure(foreground=theme.TEXT_HINT)
        self._is_showing_hint = True

    def _hide_hint(self, _event=None) -> None:
        if not self._is_showing_hint:
            self.configure(foreground=theme.TEXT_PRIMARY)
            return
        super().delete(0, tk.END)
        self.configure(foreground=theme.TEXT_PRIMARY)
        self._is_showing_hint = False


class VCheckbutton(tk.Checkbutton):
    """
    체크 상태를 'v'로 보여주는 공통 체크박스.

    기본 ttk 체크박스는 환경에 따라 x처럼 보여 혼동을 줄 수 있어,
    선택됨/해제됨을 텍스트로 분명히 표시한다.
    """

    def __init__(
        self,
        parent,
        label_text: str,
        variable: tk.BooleanVar,
        command=None,
        **kwargs,
    ):
        self._label_text = label_text
        self._variable = variable
        self._text_variable = tk.StringVar()
        super().__init__(
            parent,
            textvariable=self._text_variable,
            variable=self._variable,
            command=self._on_click,
            indicatoron=False,
            relief="groove",
            padx=8,
            pady=2,
            bg=theme.CARD_BACKGROUND,
            activebackground=theme.CARD_BACKGROUND,
            fg=theme.TEXT_PRIMARY,
            activeforeground=theme.TEXT_PRIMARY,
            bd=1,
            **kwargs,
        )
        self._external_command = command
        self._variable.trace_add("write", self._on_variable_changed)
        self._refresh_label()

    def _on_click(self) -> None:
        self._refresh_label()
        if self._external_command is not None:
            self._external_command()

    def _on_variable_changed(self, *_args) -> None:
        self._refresh_label()

    def _refresh_label(self) -> None:
        prefix = "v" if self._variable.get() else " "
        self._text_variable.set(f"{prefix} {self._label_text}")
