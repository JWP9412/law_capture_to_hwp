"""
화면 공통 테마.

왜 한 곳에서 관리하나:
  색/글꼴/여백을 파일마다 따로 넣으면 화면이 쉽게 들쑥날쑥해진다.
  특히 윈도우 기본 ttk 테마(vista)는 버튼 배경색 지정이 잘 먹지 않아
  실행 버튼 강조가 어렵다. 그래서 clam 테마를 기본으로 강제한다.
"""
from tkinter import ttk

# 배경과 선 색
WINDOW_BACKGROUND = "#f4f6fb"
CARD_BACKGROUND = "#ffffff"
CARD_BORDER = "#d6dbe6"

# 텍스트/강조 색
TEXT_PRIMARY = "#1f2937"
TEXT_HINT = "#6b7280"
TEXT_DANGER = "#b42318"
ACCENT_BLUE = "#2563eb"
ACCENT_BLUE_ACTIVE = "#1d4ed8"
BUTTON_DISABLED_BACKGROUND = "#d1d5db"
BUTTON_DISABLED_BORDER = "#c4cbd6"


def apply_theme(root) -> None:
    """
    프로그램 전체의 ttk 스타일을 한 번에 적용한다.

    root 한 곳에서만 호출하면 모든 하위 화면이 같은 디자인을 쓰게 된다.
    """
    style = ttk.Style(root)
    style.theme_use("clam")

    root.configure(bg=WINDOW_BACKGROUND)

    style.configure("TFrame", background=WINDOW_BACKGROUND)
    style.configure("TLabel", background=WINDOW_BACKGROUND, foreground=TEXT_PRIMARY)

    style.configure("Card.TLabelframe", background=CARD_BACKGROUND, bordercolor=CARD_BORDER)
    style.configure("Card.TLabelframe.Label", background=CARD_BACKGROUND, foreground=TEXT_PRIMARY)

    style.configure(
        "CardTitle.TLabel",
        background=CARD_BACKGROUND,
        foreground=TEXT_PRIMARY,
        font=("맑은 고딕", 11, "bold"),
    )
    style.configure("Hint.TLabel", foreground=TEXT_HINT)
    style.configure("Danger.TLabel", foreground=TEXT_DANGER)

    style.configure("TButton", padding=(10, 6))
    style.configure(
        "Primary.TButton",
        foreground="#ffffff",
        background=ACCENT_BLUE,
        bordercolor=ACCENT_BLUE,
        padding=(14, 8),
        font=("맑은 고딕", 10, "bold"),
    )
    style.map(
        "Primary.TButton",
        background=[
            ("disabled", BUTTON_DISABLED_BACKGROUND),
            ("active", ACCENT_BLUE_ACTIVE),
            ("pressed", ACCENT_BLUE_ACTIVE),
        ],
        bordercolor=[
            ("disabled", BUTTON_DISABLED_BORDER),
            ("active", ACCENT_BLUE_ACTIVE),
            ("pressed", ACCENT_BLUE_ACTIVE),
        ],
        foreground=[("disabled", "#e5e7eb"), ("!disabled", "#ffffff")],
    )

    style.configure("TEntry", padding=(6, 4))
    style.configure("TCombobox", padding=(6, 4))
    style.configure("TCheckbutton", background=CARD_BACKGROUND)
    style.configure("TRadiobutton", background=CARD_BACKGROUND)
