"""
둥근 모서리 사각형 그림을 만들어 ttk 에 넘긴다.

왜 그림으로 그리는가:
  tkinter(ttk) 에는 '모서리를 둥글게' 하는 설정이 없다.
  대신 작은 둥근 사각형 그림을 등록하면, ttk 가 그 그림을
  아홉 조각(네 모서리 + 네 변 + 가운데)으로 나눠 늘린다.
  모서리는 그대로 두고 가운데·변만 늘리므로, 버튼 폭이 달라도
  곡선이 찌그러지지 않는다.

왜 그림을 모듈 수준 리스트에 보관하는가:
  tkinter 는 파이썬 쪽 PhotoImage 참조가 사라지면 그림을 지워 버린다.
  지역 변수로만 만들어 두면 함수가 끝난 뒤 버튼이 빈 칸이 된다.
  그래서 아래에 _KEPT_PHOTO_IMAGES 리스트에 꼭 넣어 둔다.
  나중에 '안 쓰는 변수' 로 보이더라도 절대 지우면 안 된다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from PIL import Image, ImageDraw, ImageTk

# PhotoImage 가 가비지 컬렉션으로 사라지지 않게 붙잡아 두는 보관소.
# apply_theme 이 만든 모든 그림이 여기 쌓인다.
_KEPT_PHOTO_IMAGES: list[ImageTk.PhotoImage] = []

# 곡선이 계단처럼 보이지 않게, 이 배율로 크게 그린 뒤 줄인다.
_DRAW_SCALE = 4

# ttk 아홉 조각 늘리기용 그림의 최소 한 변(픽셀).
#
# 왜 160 인가 / 작게 줄이면 안 되는 이유:
#   ttk 는 버튼 폭을 맞출 때 가운데 조각을 '늘리지' 않고
#   타일처럼 반복해서 붙인다. 그림이 24px 이면 모서리를 뺀
#   가운데가 4px 뿐이라, 폭 120 버튼 하나를 그릴 때마다
#   조각을 수십 번 붙이고 투명도까지 섞는다.
#   실제로 hover 한 번이 22ms(평면 버튼 1ms 대비 20배)였고
#   개정본 60줄을 띄운 뒤 창 크기 3번 바꾸면 11초가 걸렸다.
#   160px 로 키우면 붙이는 횟수가 확 줄어 hover 가 4ms 근처로 떨어진다.
#   메모리를 아끼겠다고 이 숫자를 줄이지 말 것.
_MINIMUM_IMAGE_SIZE = 160


@dataclass(frozen=True)
class RoundedShapeSpec:
    """
    둥근 사각형 한 장의 색·크기 묶음.

    매개변수 셋 이하 규칙 때문에 관련 값을 한데 묶는다.
    fill_color / border_color 는 '#rrggbb' 형식. 투명은 쓰지 않는다
    (모서리 '밖' 만 투명으로 두고, 안쪽 바탕은 항상 칠한다).
    """

    fill_color: str
    border_color: str
    border_width: int
    corner_radius: int
    # 그림 한 변 길이(픽셀). 0 이면 _MINIMUM_IMAGE_SIZE 이상을 쓴다.
    # 배지처럼 작은 요소만 직접 size 를 지정해도 된다.
    size: int = 0


def _resolve_size(spec: RoundedShapeSpec) -> int:
    """모서리·테두리가 다 들어가도록 최소 한 변 길이를 정한다."""
    if spec.size > 0:
        return spec.size
    # 네 모서리 + 가운데가 넉넉히 남도록 반지름*2 + 여유와
    # _MINIMUM_IMAGE_SIZE 중 큰 쪽을 쓴다(타일 붙이기 폭주 방지).
    return max(spec.corner_radius * 2 + 4, _MINIMUM_IMAGE_SIZE)


def make_rounded_image(spec: RoundedShapeSpec) -> ImageTk.PhotoImage:
    """
    RoundedShapeSpec 대로 둥근 사각형 PhotoImage 를 만든다.

    크게 그린 뒤 줄이는 이유:
      Pillow 의 rounded_rectangle 도 작은 그림에서는 곡선이 거칠다.
      4배 크기로 그리고 LANCZOS 로 줄이면 모서리가 매끄럽다.
    """
    size = _resolve_size(spec)
    scale = _DRAW_SCALE
    big = size * scale
    radius = spec.corner_radius * scale
    border = max(spec.border_width, 0) * scale

    image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    drawer = ImageDraw.Draw(image)

    # 바깥 테두리 색으로 먼저 채운 뒤, 안쪽을 바탕색으로 덮어
    # '테두리 두께' 를 만든다. 두께가 0 이면 바탕색만 그린다.
    outer_box = (0, 0, big - 1, big - 1)
    drawer.rounded_rectangle(outer_box, radius=radius, fill=spec.border_color)
    if border > 0:
        inset = border
        inner_box = (inset, inset, big - 1 - inset, big - 1 - inset)
        inner_radius = max(radius - inset, 0)
        drawer.rounded_rectangle(inner_box, radius=inner_radius, fill=spec.fill_color)
    elif spec.fill_color != spec.border_color:
        drawer.rounded_rectangle(outer_box, radius=radius, fill=spec.fill_color)

    small = image.resize((size, size), Image.Resampling.LANCZOS)
    photo = ImageTk.PhotoImage(small)
    _KEPT_PHOTO_IMAGES.append(photo)
    return photo


def scale_length(root, length: int) -> int:
    """
    화면 배율(125%·150%)에 맞춰 길이를 키운다.

    왜 필요한가:
      ttk 그림 요소의 border(아홉 조각 경계)는 '그림 픽셀' 기준이다.
      Windows 배율이 150% 인데도 72dpi 기준 숫자만 쓰면 모서리가
      실제보다 작게 보인다. tk scaling 값으로 맞춰 준다.
    """
    try:
        scaling = float(root.tk.call("tk", "scaling"))
    except Exception:
        scaling = 1.0
    # tk scaling 의 기본(96dpi)은 1.333… 근처. 1.0 을 기준으로 맞춘다.
    factor = scaling / (96 / 72)
    return max(1, int(round(length * factor)))


def make_state_images(
    root,
    *,
    fill_by_state: dict[str, str],
    border_by_state: dict[str, str],
    corner_radius: int,
    border_width: int = 1,
) -> dict[str, ImageTk.PhotoImage]:
    """
    상태 이름 -> 그림 사전을 만든다.

    fill_by_state / border_by_state 키 예: 'normal', 'active', 'pressed',
    'disabled', 'focus'. 같은 색 조합이면 그림을 다시 쓰지 않고
    같은 PhotoImage 를 돌려줘 메모리를 아낀다.
    """
    radius = scale_length(root, corner_radius)
    width = scale_length(root, border_width)
    cache: dict[tuple[str, str], ImageTk.PhotoImage] = {}
    result: dict[str, ImageTk.PhotoImage] = {}
    for state_name, fill in fill_by_state.items():
        border = border_by_state.get(state_name, fill)
        key = (fill, border)
        if key not in cache:
            cache[key] = make_rounded_image(
                RoundedShapeSpec(
                    fill_color=fill,
                    border_color=border,
                    border_width=width,
                    corner_radius=radius,
                )
            )
        result[state_name] = cache[key]
    return result


def register_stretchable_element(
    style,
    element_name: str,
    images_by_state: dict[str, ImageTk.PhotoImage],
    corner_radius: int,
    root,
) -> None:
    """
    ttk 그림 요소를 등록한다. 이미 있으면 덮어쓰지 않고 건너뛴다.

    border=모서리픽셀 로 아홉 조각 경계를 알려 준다.
    sticky='nsew' 는 늘릴 때 사방으로 붙으라는 뜻이다.

    상태 튜플 순서:
      ttk 는 앞에서부터 맞아떨어지는 첫 상태를 쓴다.
      pressed / disabled 처럼 드문 상태를 먼저, normal 은 기본값으로 둔다.
    """
    # element_create 는 같은 이름으로 두 번 부르면 오류가 난다.
    # 테마를 다시 적용하는 경우를 대비해 이미 있으면 넘어간다.
    try:
        existing = style.element_names()
    except Exception:
        existing = ()
    if element_name in existing:
        return

    normal = images_by_state["normal"]
    # 아홉 조각 경계. 그림 한 변의 절반 이상이면 가운데가 사라져
    # 늘리기가 잘못되거나 화면이 멈출 수 있다. 그래서 절반보다 작게 둔다.
    image_size = normal.width()
    border = min(scale_length(root, corner_radius), max(image_size // 2 - 1, 1))
    # (상태튜플, 그림) 쌍. 기본 그림은 맨 앞 인자로 넘긴다.
    #
    # 왜 순서를 강제하나:
    #   ttk 는 앞에서부터 첫 번째로 맞는 상태를 고른다.
    #   마우스로 누르는 순간에는 pressed 와 active 가 동시에 켜진다.
    #   dict 삽입 순서(보통 active → pressed) 그대로 넘기면 active 가
    #   먼저 맞아, pressed 그림이 영원히 안 보인다.
    #   드문 상태(disabled/pressed)를 앞에 둬야 눌림이 눈에 보인다.
    _STATE_PRIORITY = (
        "disabled",
        "pressed",
        "selected",
        "focus",
        "active",
    )
    priority_rank = {name: index for index, name in enumerate(_STATE_PRIORITY)}

    def _state_sort_key(state_name: str) -> tuple:
        # 우선순위에 없는 이름은 뒤로, 같은 순위면 이름순.
        return (priority_rank.get(state_name, len(_STATE_PRIORITY)), state_name)

    state_pairs: list = []
    ordered_states = sorted(
        (name for name in images_by_state if name != "normal"),
        key=_state_sort_key,
    )
    for state_name in ordered_states:
        # ttk 상태 이름은 그대로: active, pressed, disabled, focus, selected …
        state_pairs.append((state_name, images_by_state[state_name]))

    # 그림은 타일 붙이기를 줄이려고 크게(160+) 두되,
    # 요소가 '원하는 크기' 는 작게 알려 줘야 한다.
    # width/height 를 안 주면 ttk 가 그림 한 변(160)을 최소 크기로 잡아
    # ▲▼ 같은 작은 버튼이 160×160 으로 커지고 서로 겹친다.
    # 모서리 두 개 + 가운데 한 칸 정도면 글자·여백이 최소 크기를 정한다.
    preferred_size = max(border * 2 + 4, 20)

    style.element_create(
        element_name,
        "image",
        normal,
        *state_pairs,
        border=border,
        sticky="nsew",
        width=preferred_size,
        height=preferred_size,
    )


def kept_image_count() -> int:
    """검증용: 보관 중인 그림 장수."""
    return len(_KEPT_PHOTO_IMAGES)
