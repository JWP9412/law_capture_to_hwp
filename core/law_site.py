"""
국가법령정보센터(law.go.kr)에 자료를 요청하고 답을 받아오는 일만 담당하는 파일.

이 파일은 '어떻게 물어보고 무엇을 받았는지' 까지만 안다.
받아온 내용에서 법령 정보를 골라내는 일은 law_source.py 가 한다.
이렇게 나눠두면 사이트 주소가 바뀌었을 때 이 파일만 손보면 된다.

법령정보센터에 물어보는 통로가 세 가지인데, 각각 쓰임이 다르다.

  1) 공개 API (lawSearch.do)
     이름의 일부만 알아도 찾아준다. 답이 정돈된 형식(XML)으로 와서 읽기 쉽다.
     화면의 [검색] 버튼이 이걸 쓴다.

  2) 한글 주소 (law.go.kr/행정규칙/이름)
     이름을 정확히 알 때 문서 번호를 바로 얻는다. 공개 API 가 막혔을 때의 예비 수단.

  3) 일반 화면 요청 (admRulHstListR.do 등)
     개정 이력처럼 공개 API 에 없는 자료를 가져온다.
"""
import gzip
import time
import urllib.error
import urllib.parse
import urllib.request

import config
from core.errors import LawSiteStructureChangedError

# 사이트가 일반 브라우저의 요청으로 인식하도록 하는 표식.
# 이것이 없으면 응답을 주지 않거나 다른 화면을 주는 경우가 있다.
BROWSER_LIKE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
}

REQUEST_TIMEOUT_IN_SECONDS = 30

# 사이트가 잠깐 응답하지 않을 때 몇 번까지 다시 시도할지.
#
# 공개 API 는 여러 사람이 함께 쓰는 통로라, 짧은 시간에 여러 번 부르면
# 잠시 막혔다가 곧 다시 열린다. 실제로 개정본을 여러 개 훑는 도중에
# 한 번 막히는 것을 겪었다. 사람이 다시 누르게 하지 말고 프로그램이 기다렸다 재시도한다.
MAX_ATTEMPTS = 3
WAIT_BETWEEN_ATTEMPTS_IN_SECONDS = 1.5

OPEN_API_SEARCH_PATH = "/DRF/lawSearch.do"
OPEN_API_ARTICLE_PATH = "/DRF/lawService.do"

# 공개 API 를 쓸 때 자신을 밝히는 값. 법제처가 공개용으로 열어둔 것을 쓴다.
OPEN_API_CALLER_ID = "test"


def _read_response_text(response) -> str:
    """응답 본문을 글자로 바꾼다. 사이트가 압축해 보내는 경우도 처리한다."""
    raw_bytes = response.read()
    if response.headers.get("Content-Encoding") == "gzip":
        raw_bytes = gzip.decompress(raw_bytes)
    return raw_bytes.decode("utf-8", errors="replace")


def _open(request, purpose: str) -> str:
    """요청을 보내고 답을 받는다. 잠깐 실패하면 조금 기다렸다 다시 시도한다."""
    last_error: Exception | None = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(
                request, timeout=REQUEST_TIMEOUT_IN_SECONDS
            ) as response:
                return _read_response_text(response)
        except urllib.error.URLError as error:
            last_error = error
            if attempt < MAX_ATTEMPTS:
                time.sleep(WAIT_BETWEEN_ATTEMPTS_IN_SECONDS * attempt)

    raise LawSiteStructureChangedError(purpose) from last_error


def request_open_api_search(search_target: str, query: str, max_results: int) -> str:
    """
    공개 API 로 법령·고시를 검색한다.

    search_target 은 무엇을 찾을지 정한다.
      "admrul" = 고시·훈령 같은 행정규칙
      "law"    = 법률·시행령·시행규칙
    """
    parameters = {
        "OC": OPEN_API_CALLER_ID,
        "target": search_target,
        "type": "XML",
        "query": query,
        "display": str(max_results),
    }
    url = f"{config.LAW_SITE_BASE_URL}{OPEN_API_SEARCH_PATH}?{urllib.parse.urlencode(parameters)}"
    request = urllib.request.Request(url, headers=BROWSER_LIKE_HEADERS)
    return _open(request, f"'{query}' 검색")


def request_open_api_article(
    search_target: str,
    identifier_name: str,
    identifier_value: str,
    article_code: str | None,
) -> str:
    """
    공개 API 로 조문 내용을 받아온다. 미리보기에 쓴다.

    갈래마다 문서를 가리키는 이름이 다르다.
      법령:     MST (그 판의 번호), 조문 번호를 함께 주면 그 조문만 온다
      행정규칙: ID  (그 판의 번호), 조문만 골라 받는 방법이 없어 전체가 온다
    """
    parameters = {
        "OC": OPEN_API_CALLER_ID,
        "target": search_target,
        "type": "XML",
        identifier_name: identifier_value,
    }
    if article_code:
        parameters["JO"] = article_code

    url = f"{config.LAW_SITE_BASE_URL}{OPEN_API_ARTICLE_PATH}?{urllib.parse.urlencode(parameters)}"
    request = urllib.request.Request(url, headers=BROWSER_LIKE_HEADERS)
    return _open(request, "조문 내용 조회")


def request_page_by_korean_url(category: str, law_name: str) -> str:
    """
    한글 주소로 법령 화면을 직접 연다. (예: law.go.kr/행정규칙/공동주택 하자의 조사…)

    이름을 정확히 알아야만 동작한다. 대신 검색 과정을 건너뛸 수 있어
    공개 API 가 응답하지 않을 때의 예비 수단으로 쓴다.
    """
    url = (
        f"{config.LAW_SITE_BASE_URL}/{urllib.parse.quote(category)}"
        f"/{urllib.parse.quote(law_name)}"
    )
    request = urllib.request.Request(url, headers=BROWSER_LIKE_HEADERS)
    return _open(request, f"'{law_name}' 화면")


def request_data(path: str, form_values: dict) -> str:
    """
    법령정보센터에 값을 담아 물어보고 답을 받아온다.

    개정 이력처럼 화면에 처음부터 들어있지 않고
    사용자가 무언가를 눌렀을 때 따로 불러오는 자료들이 이 방식을 쓴다.
    """
    url = f"{config.LAW_SITE_BASE_URL}{path}"
    request = urllib.request.Request(
        url,
        data=urllib.parse.urlencode(form_values).encode("utf-8"),
        headers={
            **BROWSER_LIKE_HEADERS,
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": config.LAW_SITE_BASE_URL,
        },
    )
    return _open(request, f"{path} 자료 요청")
