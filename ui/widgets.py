"""
입력 화면에서 반복되는 조각을 재사용하기 위한 위젯 모음.
"""
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageDraw, ImageTk

from ui import theme


AUTO_WRAP_LABEL_STYLES = (
    "Hint.TLabel",
    "Danger.TLabel",
    "Card.Hint.TLabel",
    "Card.Danger.TLabel",
)

# 카드 오른쪽 가장자리에서 글자를 띄워 둘 여유(테두리·안쪽 여백·스크롤바 몫)
AUTO_WRAP_RIGHT_MARGIN = 34
AUTO_WRAP_MINIMUM_WIDTH = 120

# 카드 배경 그림을 다시 그릴 때, 너무 자주 그리지 않기 위한 최소 변화(픽셀).
# 창 폭 10픽셀 간격 정책과 맞춰, 그보다 작은 흔들림에는 다시 그리지 않는다.
_CARD_REDRAW_SIZE_SLOP = 10

# 크기 조절 중에는 그리지 않고, 손이 멈춘 뒤에 한 번만 그리기 위한 대기(ms).
_CARD_REDRAW_DELAY_MS = 80


def _iter_descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from _iter_descendants(child)


def install_auto_wrap(card) -> None:
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


class RoundedCardShell(tk.Frame):
    """
    둥근 모서리 카드의 겉면.

    왜 ttk 그림 요소를 쓰지 않나:
      큰 카드에 ttk image border 를 붙이면 스크롤 화면에서
      창 그리기(update)가 끝나지 않는 경우가 있다.
      그래서 카드 크기만큼 둥근 사각형 그림을 직접 그려
      배경 라벨에 깔고, 그 위에 알맹이 틀을 올린다.

    구조:
      이 Frame(창 바탕색) → 배경 라벨(둥근 흰 카드 그림) → panel(알맹이)
    """

    def __init__(self, parent, padding: int = 12):
        super().__init__(parent, background=theme.WINDOW_BACKGROUND, highlightthickness=0)
        self._padding = padding
        self._photo = None
        self._drawn_size = (0, 0)
        self._redraw_after_id = None

        self._background_label = tk.Label(self, borderwidth=0, highlightthickness=0)
        self._background_label.place(x=0, y=0, relwidth=1, relheight=1)

        # 알맹이 패널. 배경 그림 위에 올린다.
        self.panel = ttk.Frame(self, style="Card.TFrame")
        self.panel.pack(
            fill="both",
            expand=True,
            padx=1,
            pady=1,
            ipadx=max(padding - 1, 0),
            ipady=max(padding - 1, 0),
        )

        self.bind("<Configure>", self._schedule_redraw, add="+")

    def _schedule_redraw(self, event=None) -> None:
        if event is not None and event.widget is not self:
            return
        if self._redraw_after_id is not None:
            self.after_cancel(self._redraw_after_id)
        # 크기 조절 중 매번 그리지 않고, 잠깐 기다렸다가 한 번만 그린다.
        self._redraw_after_id = self.after(_CARD_REDRAW_DELAY_MS, self._redraw_background)

    def _redraw_background(self) -> None:
        self._redraw_after_id = None
        width = max(self.winfo_width(), 1)
        height = max(self.winfo_height(), 1)
        old_width, old_height = self._drawn_size
        if (
            abs(width - old_width) < _CARD_REDRAW_SIZE_SLOP
            and abs(height - old_height) < _CARD_REDRAW_SIZE_SLOP
        ):
            return
        if width < 8 or height < 8:
            return

        radius = theme.CARD_CORNER_RADIUS
        scale = 2
        # tk.Label 은 투명(알파)을 제대로 못 보여 모서리가 검게 나온다.
        # 그래서 모서리 밖을 창 바탕색으로 칠한 RGB 그림으로 만든다.
        image = Image.new(
            "RGB",
            (width * scale, height * scale),
            theme.WINDOW_BACKGROUND,
        )
        drawer = ImageDraw.Draw(image)
        drawer.rounded_rectangle(
            (0, 0, width * scale - 1, height * scale - 1),
            radius=radius * scale,
            fill=theme.CARD_BORDER,
        )
        inset = scale
        drawer.rounded_rectangle(
            (inset, inset, width * scale - 1 - inset, height * scale - 1 - inset),
            radius=max(radius * scale - inset, 0),
            fill=theme.CARD_BACKGROUND,
        )
        small = image.resize((width, height), Image.Resampling.LANCZOS)
        self._photo = ImageTk.PhotoImage(small)
        self._background_label.configure(image=self._photo)
        self._drawn_size = (width, height)


class StepCard(RoundedCardShell):
    """
    번호가 붙은 둥근 카드 컨테이너.

    제목 줄은 pack, 내용은 grid — 혼용하면 안 되므로 내용용 body 를 둔다.
    """

    def __init__(self, parent, step_number: int, title: str):
        super().__init__(parent, padding=12)
        self._title_text = f"{step_number}. {title}"

        title_bar = ttk.Frame(self.panel, style="Card.TFrame")
        title_bar.pack(fill="x", pady=(0, 8))
        badge = ttk.Label(
            title_bar,
            text=str(step_number),
            style="StepBadge.TLabel",
            width=2,
            anchor="center",
        )
        badge.pack(side="left", padx=(0, 6))
        ttk.Label(
            title_bar,
            text=title,
            style="CardTitle.TLabel",
        ).pack(side="left")

        self.body = ttk.Frame(self.panel, style="Card.TFrame")
        self.body.pack(fill="both", expand=True)
        self.body.grid_columnconfigure(1, weight=1)

    def cget(self, key):
        """예전 LabelFrame 검증 코드가 text 를 읽어도 되게 한다."""
        if key == "text":
            return self._title_text
        return super().cget(key)

    def grid_columnconfigure(self, index, **kwargs):
        """내용 틀에 열 비율을 넘긴다. (예전 LabelFrame API 와 같게)"""
        return self.body.grid_columnconfigure(index, **kwargs)

    def grid_rowconfigure(self, index, **kwargs):
        return self.body.grid_rowconfigure(index, **kwargs)


class CardPanel(RoundedCardShell):
    """
    번호 없이 제목만 있는 둥근 카드.

    개정본 선택·담은 작업 목록·조문 미리보기처럼
    'N. 제목' 번호가 없는 칸에 쓴다.
    """

    def __init__(self, parent, title: str = "", padding: int = 10):
        super().__init__(parent, padding=padding)
        self._title_text = title
        if title:
            ttk.Label(self.panel, text=title, style="CardTitle.TLabel").pack(
                anchor="w", pady=(0, 6)
            )
        self.body = ttk.Frame(self.panel, style="Card.TFrame")
        self.body.pack(fill="both", expand=True)

    def cget(self, key):
        """
        예전 LabelFrame 검증 코드가 text 를 읽어도 되게 한다.
        (spike/check_gui.py 가 _job_list_frame.cget("text") 를 쓴다)
        """
        if key == "text":
            return self._title_text
        return super().cget(key)

    def grid_columnconfigure(self, index, **kwargs):
        return self.body.grid_columnconfigure(index, **kwargs)


def add_field(card: ttk.Frame, row_index: int, label_text: str, widget, hint_text: str = "") -> None:
    """
    카드 안에 '라벨 + 입력칸' 한 줄을 만든다.
    """
    label = ttk.Label(card, text=label_text, style="Card.TLabel")
    label.grid(row=row_index, column=0, sticky="w", padx=(0, 8), pady=(0, 6))
    widget.grid(row=row_index, column=1, sticky="ew", pady=(0, 6))
    if hint_text:
        hint = ttk.Label(card, text=hint_text, style="Card.Hint.TLabel")
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


class VCheckbutton(ttk.Checkbutton):
    """
    체크 상태를 'v'로 보여주는 공통 체크박스.

    예전에는 tk.Checkbutton(indicatoron=False) 을 썼는데,
    tk 위젯은 둥근 모서리 그림을 입힐 수 없다.
    그래서 ttk.Checkbutton + Toggle.TCheckbutton(둥근 그림) 으로 바꿨다.

    바깥에서 쓰는 방법(label_text, variable, command)은 그대로다.
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
        self._external_command = command
        # ttk.Checkbutton 은 anchor 를 생성 인자로 안 받는 환경이 있어 걸러 낸다.
        kwargs.pop("anchor", None)
        super().__init__(
            parent,
            textvariable=self._text_variable,
            variable=self._variable,
            command=self._on_click,
            style="Toggle.TCheckbutton",
            takefocus=False,
            **kwargs,
        )
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
