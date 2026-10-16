"""
프로그램 전체가 함께 쓰는 설정값을 한 곳에 모아둔 파일.

여기에는 '값'만 두고 '일하는 코드'는 두지 않는다.
그래야 나중에 다음과 같은 상황에서 이 파일 하나만 열어보면 된다.
  - 국가법령정보센터 화면이 바뀌어서 버튼 위치를 다시 잡아야 할 때
  - 밑줄을 더 굵게/얇게 하고 싶을 때
  - 캡션 글씨체나 그림 크기를 바꾸고 싶을 때
"""
from enum import Enum
from pathlib import Path

# ---------------------------------------------------------------------------
# 프로그램 버전
# ---------------------------------------------------------------------------

APP_VERSION = "2.0.0"

# ---------------------------------------------------------------------------
# 폴더 위치
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DIRECTORY = PROJECT_ROOT / "out"
LOG_DIRECTORY = PROJECT_ROOT / "logs"

# 자주 쓰는 법령·고시 즐겨찾기. 프로그램이 직접 읽고 쓰는 사용자 파일이다.
# (개정본 번호는 넣지 않는다 — 개정될 때마다 바뀌어 깨지기 때문이다)
FAVORITES_FILE_PATH = PROJECT_ROOT / "user_favorites.json"

# 자주 쓰는 캡처 묶음(사용자 지정 SET). 법령·조문·밑줄만 기억하고
# 시행 시점은 담을 때마다 고른다. 개정본 번호는 넣지 않는다.
CAPTURE_SET_MEMORY_FILE_PATH = PROJECT_ROOT / "user_capture_set_memory.json"


# ---------------------------------------------------------------------------
# 국가법령정보센터 (law.go.kr)
#
# 아래 주소와 화면 요소 이름들은 실제 사이트를 열어 하나씩 확인한 값이다.
# 사이트가 개편되면 이 부분이 가장 먼저 어긋난다.
# ---------------------------------------------------------------------------

LAW_SITE_BASE_URL = "https://www.law.go.kr"


class LawSourceKind(Enum):
    """국가법령정보센터에서 자료가 어느 갈래에 속하는지.

    갈래마다 화면 주소와 저장 창의 내부 이름이 달라서 구분이 필요하다.
    """

    ADMINISTRATIVE_RULE = "행정규칙"  # 고시·훈령·예규 (예: 하자판정기준)
    STATUTE = "법령"  # 법률·시행령·시행규칙 (예: 공동주택관리법)


# 갈래별로 다른 부분만 모아둔 표.
# 저장 버튼(#aBtnOutPutSave)처럼 양쪽이 똑같은 것은 아래 공통 항목에 둔다.
LAW_SITE_ADAPTERS = {
    LawSourceKind.ADMINISTRATIVE_RULE: {
        "detail_page_path": "/LSW/admRulLsInfoP.do",
        "version_id_parameter": "admRulSeq",
        "history_path": "/LSW/admRulHstListR.do",
        # 이력을 물어볼 때 문서 번호만 있으면 된다.
        "law_id_parameter": None,
        "save_dialog_selector": "#admRulOutPutLayer",
        "pdf_radio_selector": "#FileSavePdf",
        # 저장 창 목록에서 제1조를 가리키는 값: "0001-0000:00"
        "save_dialog_article_value_format": "{article_number:04d}-0000:{branch_number:02d}",
    },
    LawSourceKind.STATUTE: {
        "detail_page_path": "/LSW/lsInfoP.do",
        "version_id_parameter": "lsiSeq",
        "history_path": "/LSW/lsHstListR.do",
        # 법령은 문서 번호와 법령 고유번호를 함께 줘야 이력을 알려준다.
        "law_id_parameter": "lsId",
        "save_dialog_selector": "#lsOutPutLayer",
        "pdf_radio_selector": "#FileSavePdf1",
        # 저장 창 목록에서 제1조를 가리키는 값: "0001:00" (고시와 형식이 다르다)
        "save_dialog_article_value_format": "{article_number:04d}:{branch_number:02d}",
    },
}

# 양쪽 갈래가 공통으로 쓰는 화면 요소
ARTICLE_CHECKBOX_GROUP_SELECTOR = "input[name=joNoList]"  # 본문 옆의 조문 체크박스
OPEN_SAVE_DIALOG_SCRIPT = "bdyCheckOutPut('0')"
ARTICLE_RANGE_INPUT_SELECTOR = "#outputCustomJoNo"

# 저장 창 안의 '저장' 버튼.
#
# 반드시 저장 창 안쪽으로 범위를 좁혀서 찾아야 한다.
# 법령 화면에는 같은 이름의 버튼이 하나 더 있는데(숨어 있는 '3단비교' 창의 것),
# 범위를 좁히지 않으면 그 숨은 버튼을 누르려다 실패한다.
SAVE_BUTTON_SELECTOR = "#aBtnOutPutSave"
SAVE_DIALOG_ARTICLE_CHECKBOX_NAME = "joNo"

# 브라우저 자동화 시간 제한 (밀리초)
PAGE_LOAD_TIMEOUT_IN_MILLISECONDS = 60000
PDF_DOWNLOAD_TIMEOUT_IN_MILLISECONDS = 120000

# PDF 를 받을 때 크롬 창을 화면에 보일지.
# False 면 뒤에서 조용히 받는다. 문제 확인할 때만 True 로 바꾼다.
SHOW_BROWSER_WINDOW = False


# ---------------------------------------------------------------------------
# 밑줄·캡처 (PDF → 그림)
# ---------------------------------------------------------------------------

# 화면에서 고를 수 있는 밑줄 색. 이름은 그대로 Combobox 에 보인다.
# RGB 는 PyMuPDF draw_line 이 받는 0~1 값이다.
UNDERLINE_COLOR_CHOICES: list[tuple[str, tuple[float, float, float]]] = [
    ("빨강", (1.0, 0.0, 0.0)),
    ("파랑", (0.0, 0.2, 0.9)),
    ("초록", (0.0, 0.55, 0.0)),
    ("주황", (1.0, 0.45, 0.0)),
    ("검정", (0.0, 0.0, 0.0)),
]
DEFAULT_UNDERLINE_COLOR_NAME = "빨강"
UNDERLINE_COLOR = dict(UNDERLINE_COLOR_CHOICES)[DEFAULT_UNDERLINE_COLOR_NAME]
UNDERLINE_THICKNESS_IN_POINTS = 2.0
UNDERLINE_GAP_BELOW_TEXT_IN_POINTS = 1.2

# 미리보기에서 고른 문구를 칠하는 형광펜 색 (tk Text background용 #RRGGBB).
# PDF 밑줄 색과 짝을 맞춰, 사용자가 고른 색이 미리보기에서도 보이게 한다.
PREVIEW_HIGHLIGHT_BY_COLOR_NAME: dict[str, str] = {
    "빨강": "#ffe0e0",
    "파랑": "#d6e4ff",
    "초록": "#d4f0d4",
    "주황": "#ffe4c4",
    "검정": "#e0e0e0",
}


def underline_color_for_name(color_name: str) -> tuple[float, float, float]:
    """
    화면에서 고른 색 이름을 PyMuPDF RGB 로 바꾼다.

    모르는 이름이 들어오면 기본(빨강)을 쓴다.
    (설정 파일이 바뀌거나 옛 값이 남아 있어도 프로그램이 멈추지 않게)
    """
    for name, rgb in UNDERLINE_COLOR_CHOICES:
        if name == color_name:
            return rgb
    return UNDERLINE_COLOR


def preview_highlight_for_name(color_name: str) -> str:
    """
    미리보기 형광펜(#RRGGBB)을 밑줄 색 이름에 맞춰 돌려준다.

    모르는 이름이면 빨강용 형광펜을 쓴다.
    """
    return PREVIEW_HIGHLIGHT_BY_COLOR_NAME.get(
        color_name,
        PREVIEW_HIGHLIGHT_BY_COLOR_NAME[DEFAULT_UNDERLINE_COLOR_NAME],
    )


CAPTURE_RESOLUTION_IN_DPI = 300
CAPTURE_PADDING_IN_POINTS = 8
# 머리말·꼬리말을 가르는 가로선으로 볼 높이 상한
HORIZONTAL_RULE_MAX_HEIGHT_IN_POINTS = 1.0


# ---------------------------------------------------------------------------
# 한글 삽입 (그림·캡션·테두리)
# ---------------------------------------------------------------------------


class TextAlignment(Enum):
    """한글 문단 정렬."""

    LEFT = "왼쪽"
    CENTER = "가운데"


class InsertionMode(Enum):
    """그림을 문서 어디에 넣을지."""

    REPLACE_PLACEHOLDER = "플레이스홀더 자리"
    APPEND_TO_END = "문서 끝에 추가"


PICTURE_WIDTH_IN_MILLIMETERS = 155.0  # A4 본문 폭에 맞춤
PICTURE_ALIGNMENT = TextAlignment.CENTER
PICTURE_BORDER_WIDTH_IN_MILLIMETERS = 0.12
PICTURE_BORDER_COLOR = (0, 0, 0)  # 검정

CAPTION_SIDE = "Top"  # 그림 위
CAPTION_ALIGNMENT = TextAlignment.LEFT
CAPTION_FONT_NAME = "휴먼명조"
CAPTION_FONT_SIZE_IN_POINTS = 10

# 캡션 본문. 앞의 '[그림 N]' 번호는 한글 자동번호를 쓰고, 여기에는 설명만 둔다.
CAPTION_TEMPLATE = (
    "{law_name} {article_label} 발췌 ({effective_date_label}){same_as_previous_suffix}"
)
CAPTION_NUMBER_OPENING = "["
CAPTION_NUMBER_CLOSING = "] "
CAPTION_PAGE_MARKER = " ({page_number}/{total_pages})"
SAME_AS_PREVIOUS_VERSION_SUFFIX = " (앞 개정안과 동일)"

# 앞 개정안과 완전히 같지는 않지만 거의 같을 때 붙이는 말.
#
# 왜 '같다/다르다' 만으로 부족한가:
#   글자 하나만 달라도 '다름' 으로 나온다. 그런데 이름만 바뀌고 조문 내용은
#   그대로인 개정, 문구를 조금만 다듬은 개정이 흔하다. 그런 경우
#   아무 표시가 없으면 서면을 읽는 사람이 똑같아 보이는 그림 두 장을 놓고
#   무엇이 달라졌는지 한참 찾게 된다.
SIMILAR_TO_PREVIOUS_VERSION_SUFFIX = " (앞 개정안과 {percent}% 유사)"

# 이 값 이상으로 닮았을 때만 '유사' 라고 알린다.
# 절반쯤 닮은 것까지 알리면 오히려 방해가 되므로 꽤 높게 잡는다.
SIMILARITY_NOTICE_THRESHOLD = 0.90

# 기존 문서에 넣을 때 찾을 표시. 예: [[법령그림:하자판정기준@2025-02-03#제1조]]
PLACEHOLDER_PATTERN = "[[법령그림:{law_name}@{effective_date}#{article_label}]]"

# 기존 문서를 열었을 때 저장 이름 뒤에 붙는 말 (원본은 그대로 둔다)
RESULT_FILE_SUFFIX = "_캡처본"
