"""
화면 공통 테마.

색·글꼴·둥근 모서리 그림을 한 곳에서 관리한다.

왜 한 곳에서 관리하나:
  색/글꼴/여백을 파일마다 따로 넣으면 화면이 쉽게 들쑥날쑥해진다.
  특히 윈도우 기본 ttk 테마(vista)는 버튼 배경색 지정이 잘 먹지 않아
  실행 버튼 강조가 어렵다. 그래서 clam 테마를 기본으로 강제한다.

색 출처 (2026-11-20 실측):
  국가법령정보센터 리뉴얼 화면(main.html, lsInfoP.do)에서 계산된 스타일을
  읽어 왔다. 정부 상징(태극 로고)은 사용 규정이 있어 넣지 않았고,
  색·글꼴·모서리·배치만 따왔다.

둥근 모서리:
  ttk 에는 모서리를 둥글게 하는 설정이 없어서, Pillow 로 만든 작은
  둥근 사각형을 그림 요소로 등록해 아홉 조각으로 늘린다.
  자세한 원리는 ui/rounded_shapes.py 맨 위 설명 참고.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from ui.rounded_shapes import make_state_images, register_stretchable_element

# ---------------------------------------------------------------------------
# 색 상수 — 이름은 예전과 같게 두어 다른 파일이 깨지지 않게 한다.
# ---------------------------------------------------------------------------

# 배경과 선 색 (사이트 첫 화면 바탕·칸 구분선)
WINDOW_BACKGROUND = "#eef2f7"
CARD_BACKGROUND = "#ffffff"
CARD_BORDER = "#cbced6"

# 텍스트/강조 색 (사이트 본문·보조·흐린 글자)
TEXT_PRIMARY = "#1e2124"
TEXT_HINT = "#6e7377"
TEXT_DANGER = "#b42318"
TEXT_SECONDARY = "#464c53"

# 주 강조: 사이트 [화면내 검색] 버튼 진남색 / 로고·제목 남색
ACCENT_BLUE = "#063a74"
ACCENT_BLUE_ACTIVE = "#001e4e"
BRAND_NAVY = "#001e4e"
# 링크·개정 표시·선택 상자 테두리 (사이트 파랑)
LINK_BLUE = "#2b6ad1"

BUTTON_BORDER = "#b1b8be"
HOVER_BACKGROUND = "#f8f9fb"
SELECTED_BACKGROUND = "#e2eaf7"
BUTTON_DISABLED_BACKGROUND = "#d1d5db"
BUTTON_DISABLED_BORDER = "#c4cbd6"

# 모서리 반지름 (사이트: 버튼 8px, 카드 12px)
BUTTON_CORNER_RADIUS = 8
CARD_CORNER_RADIUS = 12

# 글꼴 후보. 사이트가 쓰는 Pretendard GOV 가 있으면 그걸,
# 없으면 가장 비슷한 Noto Sans KR, 그것도 없으면 맑은 고딕.
_FONT_CANDIDATES = ("Pretendard GOV", "Noto Sans KR", "맑은 고딕")

# apply_theme 이 고른 글꼴 이름. body_font / title_font 가 읽는다.
_chosen_font_family = "맑은 고딕"


def pick_font_family(root) -> str:
    """
    이 컴퓨터에 설치된 글꼴 중 가장 가까운 것을 고른다.

    tkinter 의 families() 는 창이 만들어진 뒤에야 믿을 수 있다.
    그래서 apply_theme(root) 안에서 부른다.
    """
    installed = {name.lower(): name for name in tkfont.families(root)}
    for candidate in _FONT_CANDIDATES:
        found = installed.get(candidate.lower())
        if found:
            return found
    return "맑은 고딕"


def body_font(size: int = 10, weight: str = "normal") -> tuple:
    """본문용 (글꼴이름, 크기) 또는 (글꼴이름, 크기, 굵기) 튜플."""
    if weight == "normal":
        return (_chosen_font_family, size)
    return (_chosen_font_family, size, weight)


def title_font(size: int = 11) -> tuple:
    """제목용 굵은 글꼴."""
    return (_chosen_font_family, size, "bold")


def apply_theme(root) -> None:
    """
    프로그램 전체의 ttk 스타일을 한 번에 적용한다.

    root 한 곳에서만 호출하면 모든 하위 화면이 같은 디자인을 쓰게 된다.
    둥근 그림은 여기서 만들어 등록하므로, 창이 뜨기 전에 반드시 부른다.
    """
    global _chosen_font_family

    style = ttk.Style(root)
    style.theme_use("clam")

    _chosen_font_family = pick_font_family(root)
    _apply_default_fonts(root)

    root.configure(bg=WINDOW_BACKGROUND)

    style.configure("TFrame", background=WINDOW_BACKGROUND)
    style.configure(
        "TLabel",
        background=WINDOW_BACKGROUND,
        foreground=TEXT_PRIMARY,
        font=body_font(10),
    )

    # 카드 안은 창 바탕(회색)이 아니라 흰 바탕이어야 한다.
    # 카드 안에 두는 Frame/Label 은 Card.* 스타일을 쓴다.
    # 주의: Card.TFrame 은 '안쪽 흰 틀' 전용(테두리 없음).
    # 바깥 둥근 카드는 RoundedCard.TFrame 을 쓴다.
    style.configure("Card.TFrame", background=CARD_BACKGROUND)
    style.configure(
        "Card.TLabel",
        background=CARD_BACKGROUND,
        foreground=TEXT_PRIMARY,
        font=body_font(10),
    )
    style.configure(
        "CardTitle.TLabel",
        background=CARD_BACKGROUND,
        foreground=BRAND_NAVY,
        font=title_font(12),
    )
    style.configure(
        "Hint.TLabel",
        background=WINDOW_BACKGROUND,
        foreground=TEXT_HINT,
        font=body_font(9),
    )
    style.configure(
        "Card.Hint.TLabel",
        background=CARD_BACKGROUND,
        foreground=TEXT_HINT,
        font=body_font(9),
    )
    style.configure(
        "Danger.TLabel",
        background=WINDOW_BACKGROUND,
        foreground=TEXT_DANGER,
        font=body_font(9),
    )
    style.configure(
        "Card.Danger.TLabel",
        background=CARD_BACKGROUND,
        foreground=TEXT_DANGER,
        font=body_font(9),
    )
    style.configure(
        "Header.TLabel",
        background=CARD_BACKGROUND,
        foreground=TEXT_HINT,
        font=body_font(9),
    )
    style.configure(
        "HeaderTitle.TLabel",
        background=CARD_BACKGROUND,
        foreground=BRAND_NAVY,
        font=title_font(16),
    )
    style.configure(
        "HeaderLink.TLabel",
        background=CARD_BACKGROUND,
        foreground=LINK_BLUE,
        font=body_font(9),
    )

    _register_rounded_buttons(style, root)
    _register_rounded_entries(style, root)
    _register_rounded_card(style, root)
    _register_rounded_toggle(style, root)
    _register_step_badge(style, root)

    style.configure(
        "TCheckbutton",
        background=CARD_BACKGROUND,
        foreground=TEXT_PRIMARY,
        font=body_font(10),
    )
    style.configure(
        "TRadiobutton",
        background=CARD_BACKGROUND,
        foreground=TEXT_PRIMARY,
        font=body_font(10),
    )
    style.map(
        "TRadiobutton",
        background=[("active", CARD_BACKGROUND)],
        indicatorcolor=[
            ("selected", LINK_BLUE),
            ("!selected", CARD_BACKGROUND),
        ],
    )


def _apply_default_fonts(root) -> None:
    """Tk 기본 글꼴을 고른 글꼴로 바꿔, 글꼴을 안 적은 위젯에도 적용한다."""
    for name, size, weight in (
        ("TkDefaultFont", 10, "normal"),
        ("TkTextFont", 10, "normal"),
        ("TkHeadingFont", 11, "bold"),
        ("TkMenuFont", 10, "normal"),
        ("TkCaptionFont", 10, "normal"),
        ("TkSmallCaptionFont", 9, "normal"),
        ("TkIconFont", 10, "normal"),
        ("TkTooltipFont", 9, "normal"),
    ):
        try:
            named = tkfont.nametofont(name)
            named.configure(family=_chosen_font_family, size=size, weight=weight)
        except Exception:
            # 없는 이름이면 조용히 넘어간다. (환경마다 기본 글꼴 목록이 다름)
            pass


def _register_rounded_buttons(style: ttk.Style, root) -> None:
    """
    기본 버튼·주 버튼을 둥근 그림으로 바꾼다.

    레이아웃에서 border/focus 요소를 우리 그림 요소로 갈아끼운다.
    글자(label)는 그대로 두어 버튼 글씨가 보이게 한다.
    """
    # --- 보조(흰) 버튼: 사이트 [파일저장]·[프린트] 버튼 ---
    secondary = make_state_images(
        root,
        fill_by_state={
            "normal": CARD_BACKGROUND,
            "active": HOVER_BACKGROUND,
            "pressed": WINDOW_BACKGROUND,
            "disabled": BUTTON_DISABLED_BACKGROUND,
        },
        border_by_state={
            "normal": BUTTON_BORDER,
            "active": BUTTON_BORDER,
            "pressed": BUTTON_BORDER,
            "disabled": BUTTON_DISABLED_BORDER,
        },
        corner_radius=BUTTON_CORNER_RADIUS,
    )
    register_stretchable_element(
        style, "Law.Button.border", secondary, BUTTON_CORNER_RADIUS, root
    )
    style.layout(
        "TButton",
        [
            (
                "Law.Button.border",
                {
                    "sticky": "nsew",
                    "children": [
                        (
                            "Button.padding",
                            {
                                "sticky": "nsew",
                                "children": [("Button.label", {"sticky": "nsew"})],
                            },
                        )
                    ],
                },
            )
        ],
    )
    style.configure(
        "TButton",
        background=CARD_BACKGROUND,
        foreground=TEXT_PRIMARY,
        borderwidth=0,
        focuscolor="",
        padding=(12, 6),
        font=body_font(10),
    )
    style.map(
        "TButton",
        foreground=[
            ("disabled", TEXT_HINT),
            ("!disabled", TEXT_PRIMARY),
        ],
        background=[("active", HOVER_BACKGROUND)],
    )

    # --- 주(진남) 버튼: 사이트 [화면내 검색] 버튼 ---
    primary = make_state_images(
        root,
        fill_by_state={
            "normal": ACCENT_BLUE,
            "active": ACCENT_BLUE_ACTIVE,
            "pressed": ACCENT_BLUE_ACTIVE,
            "disabled": BUTTON_DISABLED_BACKGROUND,
        },
        border_by_state={
            "normal": ACCENT_BLUE,
            "active": ACCENT_BLUE_ACTIVE,
            "pressed": ACCENT_BLUE_ACTIVE,
            "disabled": BUTTON_DISABLED_BORDER,
        },
        corner_radius=BUTTON_CORNER_RADIUS,
    )
    register_stretchable_element(
        style, "Law.Primary.border", primary, BUTTON_CORNER_RADIUS, root
    )
    style.layout(
        "Primary.TButton",
        [
            (
                "Law.Primary.border",
                {
                    "sticky": "nsew",
                    "children": [
                        (
                            "Button.padding",
                            {
                                "sticky": "nsew",
                                "children": [("Button.label", {"sticky": "nsew"})],
                            },
                        )
                    ],
                },
            )
        ],
    )
    style.configure(
        "Primary.TButton",
        background=ACCENT_BLUE,
        foreground="#ffffff",
        borderwidth=0,
        focuscolor="",
        padding=(16, 8),
        font=body_font(10, "bold"),
    )
    style.map(
        "Primary.TButton",
        foreground=[
            ("disabled", "#e5e7eb"),
            ("!disabled", "#ffffff"),
        ],
        background=[
            ("disabled", BUTTON_DISABLED_BACKGROUND),
            ("pressed", ACCENT_BLUE_ACTIVE),
            ("active", ACCENT_BLUE_ACTIVE),
        ],
    )


def _register_rounded_entries(style: ttk.Style, root) -> None:
    """입력칸·콤보 상자 바탕을 둥근 그림으로."""
    field = make_state_images(
        root,
        fill_by_state={
            "normal": CARD_BACKGROUND,
            "focus": CARD_BACKGROUND,
            "disabled": HOVER_BACKGROUND,
            "readonly": CARD_BACKGROUND,
        },
        border_by_state={
            "normal": BUTTON_BORDER,
            "focus": LINK_BLUE,
            "disabled": BUTTON_DISABLED_BORDER,
            "readonly": BUTTON_BORDER,
        },
        corner_radius=BUTTON_CORNER_RADIUS,
    )
    register_stretchable_element(
        style, "Law.Field.border", field, BUTTON_CORNER_RADIUS, root
    )

    style.layout(
        "TEntry",
        [
            (
                "Law.Field.border",
                {
                    "sticky": "nsew",
                    "children": [
                        (
                            "Entry.padding",
                            {
                                "sticky": "nsew",
                                "children": [("Entry.textarea", {"sticky": "nsew"})],
                            },
                        )
                    ],
                },
            )
        ],
    )
    style.configure(
        "TEntry",
        fieldbackground=CARD_BACKGROUND,
        foreground=TEXT_PRIMARY,
        borderwidth=0,
        padding=(8, 5),
        insertcolor=TEXT_PRIMARY,
        font=body_font(10),
    )

    # Combobox 는 화살표(downarrow)를 오른쪽에 남겨 두고
    # 나머지 칸을 둥근 그림으로 감싼다. 화살표가 빠지면 목록을 못 연다.
    style.layout(
        "TCombobox",
        [
            ("Combobox.downarrow", {"side": "right", "sticky": "ns"}),
            (
                "Law.Field.border",
                {
                    "sticky": "nsew",
                    "children": [
                        (
                            "Combobox.padding",
                            {
                                "sticky": "nsew",
                                "children": [
                                    ("Combobox.textarea", {"sticky": "nsew"}),
                                ],
                            },
                        )
                    ],
                },
            ),
        ],
    )
    style.configure(
        "TCombobox",
        fieldbackground=CARD_BACKGROUND,
        foreground=TEXT_PRIMARY,
        background=CARD_BACKGROUND,
        borderwidth=0,
        padding=(8, 5),
        arrowcolor=TEXT_SECONDARY,
        font=body_font(10),
    )
    style.map(
        "TCombobox",
        fieldbackground=[
            ("disabled", HOVER_BACKGROUND),
            ("readonly", CARD_BACKGROUND),
        ],
        foreground=[("disabled", TEXT_HINT)],
        arrowcolor=[("disabled", TEXT_HINT), ("!disabled", TEXT_SECONDARY)],
    )


def _register_rounded_card(style: ttk.Style, root) -> None:
    """
    카드(바깥 패널) 스타일.

    왜 카드에는 둥근 그림 요소를 안 쓰나:
      버튼·입력칸처럼 작은 위젯은 그림 테두리가 잘 동작한다.
      그런데 스크롤 칸 안에 큰 카드를 여러 개 두고 그림 테두리를 붙이면
      창을 그리는 동안 크기 계산이 끝나지 않는다. (update() 무한 대기)
      단순 재현도 환경에 따라 들쑥날쑥해, 카드는 색 테두리로 두고
      모서리는 버튼·입력칸·토글만 둥글게 한다.

    카드 골격은 Frame(RoundedCard.TFrame) 이다.
    LabelFrame 그림 테두리는 같은 이유로 쓰지 않는다.
    """
    style.configure(
        "RoundedCard.TFrame",
        background=CARD_BACKGROUND,
        borderwidth=1,
        relief="solid",
    )
    # clam 에서 Frame 테두리 색은 bordercolor / lightcolor / darkcolor 로 맞춘다.
    style.map(
        "RoundedCard.TFrame",
        background=[("!disabled", CARD_BACKGROUND)],
    )
    try:
        style.configure(
            "RoundedCard.TFrame",
            bordercolor=CARD_BORDER,
            lightcolor=CARD_BORDER,
            darkcolor=CARD_BORDER,
        )
    except tk.TclError:
        pass

    style.configure(
        "Card.TLabelframe",
        background=CARD_BACKGROUND,
        bordercolor=CARD_BORDER,
        lightcolor=CARD_BORDER,
        darkcolor=CARD_BORDER,
        relief="solid",
        borderwidth=1,
        padding=12,
    )
    style.configure(
        "Card.TLabelframe.Label",
        background=CARD_BACKGROUND,
        foreground=BRAND_NAVY,
        font=title_font(11),
    )


def _register_rounded_toggle(style: ttk.Style, root) -> None:
    """
    VCheckbutton 이 쓰는 둥근 토글 단추 스타일.

    꺼짐=흰 바탕+회색 테두리, 켜짐=연한 파랑+파란 테두리+진남 글자.
    indicatoron=False 처럼 글자만 보이는 단추로 쓰므로
    indicator 요소는 빼고 border+label 만 둔다.
    """
    toggle = make_state_images(
        root,
        fill_by_state={
            "normal": CARD_BACKGROUND,
            "active": HOVER_BACKGROUND,
            "selected": SELECTED_BACKGROUND,
            "pressed": WINDOW_BACKGROUND,
            "disabled": BUTTON_DISABLED_BACKGROUND,
        },
        border_by_state={
            "normal": BUTTON_BORDER,
            "active": BUTTON_BORDER,
            "selected": LINK_BLUE,
            "pressed": BUTTON_BORDER,
            "disabled": BUTTON_DISABLED_BORDER,
        },
        corner_radius=BUTTON_CORNER_RADIUS,
    )
    register_stretchable_element(
        style, "Law.Toggle.border", toggle, BUTTON_CORNER_RADIUS, root
    )
    style.layout(
        "Toggle.TCheckbutton",
        [
            (
                "Law.Toggle.border",
                {
                    "sticky": "nsew",
                    "children": [
                        (
                            "Checkbutton.padding",
                            {
                                "sticky": "nsew",
                                "children": [
                                    ("Checkbutton.label", {"sticky": "nsew"})
                                ],
                            },
                        )
                    ],
                },
            )
        ],
    )
    style.configure(
        "Toggle.TCheckbutton",
        background=CARD_BACKGROUND,
        foreground=TEXT_PRIMARY,
        borderwidth=0,
        focuscolor="",
        padding=(8, 3),
        font=body_font(10),
    )
    style.map(
        "Toggle.TCheckbutton",
        foreground=[
            ("disabled", TEXT_HINT),
            ("selected", BRAND_NAVY),
            ("!selected", TEXT_PRIMARY),
        ],
        background=[
            ("selected", SELECTED_BACKGROUND),
            ("active", HOVER_BACKGROUND),
        ],
    )


def _register_step_badge(style: ttk.Style, root) -> None:
    """
    StepCard 번호 배지용 작은 진남 둥근 칸.

    실제 배지는 widgets.StepCard 가 Canvas/Label 로 그리지만,
    같은 색을 쓰도록 상수만 여기서 쓴다. (스타일 자체는 예비용)
    """
    badge = make_state_images(
        root,
        fill_by_state={"normal": ACCENT_BLUE},
        border_by_state={"normal": ACCENT_BLUE},
        corner_radius=4,
        border_width=0,
    )
    register_stretchable_element(
        style, "Law.Badge.border", badge, 4, root
    )
    style.layout(
        "StepBadge.TLabel",
        [
            (
                "Law.Badge.border",
                {
                    "sticky": "nsew",
                    "children": [("Label.padding", {"sticky": "nsew",
                        "children": [("Label.label", {"sticky": "nsew"})]})],
                },
            )
        ],
    )
    style.configure(
        "StepBadge.TLabel",
        background=ACCENT_BLUE,
        foreground="#ffffff",
        borderwidth=0,
        padding=(5, 1),
        font=body_font(9, "bold"),
        anchor="center",
    )
