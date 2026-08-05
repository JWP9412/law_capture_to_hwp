"""
입력 화면에서 반복되는 조각을 재사용하기 위한 위젯 모음.
"""
import tkinter as tk
from tkinter import ttk

from ui import theme


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
