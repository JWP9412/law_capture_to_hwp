"""
법령정보센터에서 조문(들)을 골라 PDF 로 내려받는 일을 담당한다.

사람이 손으로 하던 과정을 그대로 흉내낸다.
  1) 법령 화면을 연다
  2) 원하는 조문 왼쪽의 체크박스를 켠다 (여러 개면 모두)
  3) 옆에 뜨는 작은 도구막대에서 '저장' 을 누른다
  4) 저장 창에서 파일 형식을 PDF 로 고른다
  5) '저장' 을 눌러 파일을 받는다

왜 브라우저를 쓰되 창을 안 보이게 하는가:
  저장 요청을 가로채 직접 받는 방식으로 바뀌어, 창이 화면에 그려질 필요가 없다.
  창이 튀어나오면 하던 일을 가리므로 기본은 숨긴다.
  디버깅할 때만 config.SHOW_BROWSER_WINDOW = True 로 되돌리면 된다.
"""
import os
import re
from contextlib import contextmanager
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

import config
from core.article_number import ArticleNumber, build_article_range_label
from core.errors import (
    ArticleNotFoundOnPageError,
    ArticlePdfDownloadError,
    LawSiteStructureChangedError,
)
from core.models import LawVersion

# 조문 체크박스가 달고 있는 값에서 조·가지번호를 읽어내는 규칙.
#
# 값의 생김새가 갈래마다 다르다.
#   행정규칙: "6-0:2::0006000002:18231671"   <- 제6조의2
#   법령:     "1:0:000100:96928583"          <- 제1조
#              "32:2:003202:…"               <- 제32조의2
# 맨 앞이 조 번호, 첫 번째 구분 다음이 가지 번호다.
# 예전에는 맨 앞 숫자만 읽어 제32조와 제32조의2를 구별하지 못했다.
ARTICLE_NUMBER_PATTERN = re.compile(r"^(\d+)[-:](\d+)")

# PDF 파일이 공통으로 갖는 앞부분 표식. 받은 것이 정말 PDF 인지 확인할 때 쓴다.
PDF_FILE_SIGNATURE = b"%PDF"

# 저장 버튼을 누른 뒤 사이트가 요청을 준비할 때까지 잠깐 기다리는 시간
SAVE_REQUEST_SETTLE_TIME_IN_MILLISECONDS = 800

# 저장 버튼이 폼을 보내려는 순간 가로채는 코드.
#
# 사이트는 '저장' 을 누르면 숨은 폼에 주소와 값을 채워 넣고 전송한다.
# 그대로 두면 화면이 PDF 로 넘어가 버려서 다음 조문을 이어서 처리할 수 없다.
# 그래서 보내는 동작만 바꿔치기해, 어디로 무엇을 보내려 했는지 기록만 남긴다.
#
# 보내는 방법이 갈래마다 다르다.
#   고시: 폼의 submit 을 부른다
#   법령: newLsSaveUpdate 라는 자기네 함수를 부른다
# 어느 쪽으로 오든 잡히도록 둘 다 바꿔둔다.
SAVE_REQUEST_INTERCEPTOR_SCRIPT = """
() => {
  window.__lawCaptureSubmission = null;

  const record = (action, form) => {
    window.__lawCaptureSubmission = {
      action: new URL(action, document.baseURI).href,
      body: new URLSearchParams(new FormData(form)).toString(),
    };
  };

  const form = document.getElementById('outPutFrm');
  if (form) {
    form.submit = function () { record(this.action, this); };
  }

  if (typeof window.newLsSaveUpdate === 'function') {
    window.newLsSaveUpdate = function (layerId, action, targetForm) {
      record(action, targetForm || form);
    };
  }
}
"""


class LawSiteBrowser:
    """
    법령정보센터를 다루는 브라우저 창 하나.

    여러 조문을 연달아 받을 때 창을 매번 새로 띄우면 느리므로,
    창 하나를 열어두고 계속 재사용한다.
    """

    def __init__(self, download_directory: Path):
        self._download_directory = download_directory
        self._playwright = None
        self._browser = None
        self._page = None

    def __enter__(self) -> "LawSiteBrowser":
        # headless=True 일 때 새 Playwright 는 'chromium_headless_shell' 을 찾는다.
        # 이 환경에는 일반 Chromium 만 깔려 있어, 창만 숨긴 일반 Chromium 을 쓴다.
        # sync_playwright() 보다 먼저 환경변수를 켜야 반영된다.
        if not config.SHOW_BROWSER_WINDOW:
            os.environ["PLAYWRIGHT_CHROMIUM_USE_HEADLESS_SHELL"] = "0"

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=not config.SHOW_BROWSER_WINDOW
        )
        context = self._browser.new_context(accept_downloads=True)
        self._page = context.new_page()

        # 이 사이트는 저장할 때 "최대 5분 걸릴 수 있습니다" 같은 알림창을 띄운다.
        # 사람이 없으면 그 창에서 멈춰버리므로 뜨는 즉시 자동으로 확인을 눌러준다.
        self._page.on("dialog", lambda dialog: dialog.accept())
        return self

    def __exit__(self, *exception_details) -> None:
        for closer in (
            lambda: self._browser and self._browser.close(),
            lambda: self._playwright and self._playwright.stop(),
        ):
            try:
                closer()
            except Exception:
                pass  # 정리 과정의 실패는 원래 작업의 결과를 가리면 안 된다

    def download_article_pdf(
        self, version: LawVersion, article_numbers: list[ArticleNumber]
    ) -> Path:
        """
        조문(들)을 PDF 로 받아 저장하고 그 파일 위치를 돌려준다.

        조문이 여러 개면 저장 창에서 그 조문들만 켠 채로 한 번에 받는다.
        가지번호가 있는 조문(제32조의2)도 같은 목록으로 처리한다.
        """
        if not article_numbers:
            raise ArticlePdfDownloadError("조문", "받을 조문 번호가 비어 있습니다")

        self._open_law_page(version)
        self._check_article_checkboxes(version, article_numbers)
        self._open_save_dialog(version)
        self._select_articles_in_save_dialog(version, article_numbers)
        self._choose_pdf_format(version)
        return self._click_save_and_wait_for_file(version, article_numbers)

    # -- 아래는 위 다섯 단계의 세부 내용 --

    def _open_law_page(self, version: LawVersion) -> None:
        self._page.goto(
            version.detail_page_url,
            wait_until="domcontentloaded",
            timeout=config.PAGE_LOAD_TIMEOUT_IN_MILLISECONDS,
        )
        try:
            self._page.wait_for_selector(
                config.ARTICLE_CHECKBOX_GROUP_SELECTOR,
                timeout=config.PAGE_LOAD_TIMEOUT_IN_MILLISECONDS,
            )
        except PlaywrightTimeoutError as error:
            raise LawSiteStructureChangedError("조문 체크박스") from error

    def _check_article_checkboxes(
        self, version: LawVersion, article_numbers: list[ArticleNumber]
    ) -> None:
        """
        원하는 조문들의 체크박스를 켠다.

        체크박스의 이름표(id)는 갈래마다 자릿수가 달라서 규칙만으로 만들면 어긋나기 쉽다.
        그래서 화면에 있는 체크박스를 전부 훑어 각자가 몇 조·몇 가지인지 읽어보고 고른다.
        """
        checkboxes = self._page.query_selector_all(config.ARTICLE_CHECKBOX_GROUP_SELECTOR)
        remaining = set(article_numbers)

        for checkbox in checkboxes:
            article = _read_article_number(checkbox.get_attribute("value") or "")
            if article is not None and article in remaining:
                checkbox.check()
                remaining.remove(article)

        if remaining:
            missing = build_article_range_label(sorted(remaining))
            raise ArticleNotFoundOnPageError(
                missing, version.law_name, version.effective_date
            )

    def _open_save_dialog(self, version: LawVersion) -> None:
        """
        조문을 체크하면 나타나는 도구막대의 '저장' 을 눌러 저장 창을 띄운다.

        저장 창은 두 부분이 따로 그려진다. 파일 형식 고르는 부분이 먼저 나오고,
        어느 조문을 저장할지 고르는 목록이 조금 늦게 채워진다.
        목록이 준비되기 전에 손대면 아무것도 못 찾으므로 둘 다 기다린다.
        """
        adapter = config.LAW_SITE_ADAPTERS[version.source_kind]
        self._page.evaluate(config.OPEN_SAVE_DIALOG_SCRIPT)

        article_list_selector = (
            f"{adapter['save_dialog_selector']} "
            f"input[name={config.SAVE_DIALOG_ARTICLE_CHECKBOX_NAME}]"
        )
        for selector, description in (
            (adapter["pdf_radio_selector"], "저장 창의 파일 형식 선택"),
            (article_list_selector, "저장 창의 조문 목록"),
        ):
            try:
                self._page.wait_for_selector(
                    selector,
                    state="attached",
                    timeout=config.PAGE_LOAD_TIMEOUT_IN_MILLISECONDS,
                )
            except PlaywrightTimeoutError as error:
                raise LawSiteStructureChangedError(description) from error

    def _select_articles_in_save_dialog(
        self, version: LawVersion, article_numbers: list[ArticleNumber]
    ) -> None:
        """
        저장 창의 조문 목록에서 원하는 조문들만 남기고 나머지를 모두 끈다.

        이 단계가 없으면 조문 하나가 아니라 문서 전체(수십 쪽)가 저장된다.
        본문에서 조문을 체크해도 저장 창의 목록은 전부 켜진 채로 열리기 때문이다.
        """
        adapter = config.LAW_SITE_ADAPTERS[version.source_kind]
        target_values = [
            adapter["save_dialog_article_value_format"].format(
                article_number=article.number, branch_number=article.branch
            )
            for article in article_numbers
        ]

        found_count = self._page.evaluate(
            """
            ({dialogSelector, checkboxName, targetValues}) => {
              const boxes = Array.from(
                document.querySelectorAll(
                  `${dialogSelector} input[name=${checkboxName}]`
                )
              );
              boxes.forEach(box => { box.checked = false; });
              let found = 0;
              const wanted = new Set(targetValues);
              boxes.forEach(box => {
                if (wanted.has(box.value)) {
                  box.checked = true;
                  found += 1;
                }
              });
              return found;
            }
            """,
            {
                "dialogSelector": adapter["save_dialog_selector"],
                "checkboxName": config.SAVE_DIALOG_ARTICLE_CHECKBOX_NAME,
                "targetValues": target_values,
            },
        )

        if found_count != len(article_numbers):
            raise ArticleNotFoundOnPageError(
                build_article_range_label(article_numbers),
                version.law_name,
                version.effective_date,
            )

    def _choose_pdf_format(self, version: LawVersion) -> None:
        adapter = config.LAW_SITE_ADAPTERS[version.source_kind]
        self._page.check(adapter["pdf_radio_selector"])

    def _click_save_and_wait_for_file(
        self, version: LawVersion, article_numbers: list[ArticleNumber]
    ) -> Path:
        """
        저장 버튼을 눌러 나온 PDF 를 파일로 저장한다.

        브라우저의 '다운로드' 기능에 기대지 않고, 사이트가 어디로 무엇을 보내려는지
        가로채서 우리가 직접 받아온다. 이유는 갈래마다 방식이 다르기 때문이다.
          - 고시: 파일을 내려받는 형태로 응답한다
          - 법령: 같은 창에서 PDF 를 열어버린다 (target="_self")
        뒤쪽은 브라우저가 화면에 띄우기만 해서 '다운로드' 가 일어나지 않는다.
        그래서 두 경우 모두에 통하는 방법으로 통일했다.
        """
        article_label = build_article_range_label(article_numbers)
        saved_path = self._download_directory / _build_pdf_file_name(
            version, article_numbers
        )
        saved_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            submission = self._capture_save_request(version)
        except PlaywrightError as error:
            raise ArticlePdfDownloadError(article_label, str(error)) from error

        if not submission:
            raise ArticlePdfDownloadError(
                article_label, "사이트가 저장 요청을 보내지 않았습니다"
            )

        pdf_bytes = self._fetch_pdf(submission, article_label)
        saved_path.write_bytes(pdf_bytes)
        return saved_path

    def _capture_save_request(self, version: LawVersion) -> dict | None:
        """
        저장 버튼을 누르되, 사이트가 보내려는 요청을 가로채 그 내용만 받아온다.

        폼이 실제로 전송되면 화면이 PDF 로 넘어가 버려서 다음 조문을 처리할 수 없다.
        그래서 전송 직전에 붙잡아 두고, 주소와 값만 꺼내 온다.
        """
        adapter = config.LAW_SITE_ADAPTERS[version.source_kind]
        save_button_selector = (
            f"{adapter['save_dialog_selector']} {config.SAVE_BUTTON_SELECTOR}"
        )

        self._page.evaluate(SAVE_REQUEST_INTERCEPTOR_SCRIPT)
        self._page.click(save_button_selector)
        self._page.wait_for_timeout(SAVE_REQUEST_SETTLE_TIME_IN_MILLISECONDS)
        return self._page.evaluate("window.__lawCaptureSubmission || null")

    def _fetch_pdf(self, submission: dict, article_label: str) -> bytes:
        """가로챈 주소로 직접 요청해 PDF 내용을 받아온다."""
        response = self._page.request.post(
            submission["action"],
            data=submission["body"],
            headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
            timeout=config.PDF_DOWNLOAD_TIMEOUT_IN_MILLISECONDS,
        )

        if not response.ok:
            raise ArticlePdfDownloadError(
                article_label, f"사이트가 오류로 답했습니다 ({response.status})"
            )

        content = response.body()
        if not content.startswith(PDF_FILE_SIGNATURE):
            raise ArticlePdfDownloadError(
                article_label, "받은 것이 PDF 가 아닙니다"
            )

        return content


def _read_article_number(checkbox_value: str) -> ArticleNumber | None:
    """
    체크박스가 달고 있는 값에서 조 번호와 가지번호를 함께 읽어낸다.

    맨 앞 숫자만 읽으면 제32조(32:0)와 제32조의2(32:2)를 구별하지 못한다.
    """
    matched = ARTICLE_NUMBER_PATTERN.match(checkbox_value)
    if not matched:
        return None
    return ArticleNumber(number=int(matched.group(1)), branch=int(matched.group(2)))


def _build_pdf_file_name(
    version: LawVersion, article_numbers: list[ArticleNumber]
) -> str:
    """겹치지 않고 나중에 알아보기 쉬운 파일 이름을 만든다."""
    safe_law_name = re.sub(r'[\\/:*?"<>|]', "", version.law_name)[:40]
    safe_articles = re.sub(
        r'[\\/:*?"<>|]', "", build_article_range_label(article_numbers)
    )
    return f"{safe_law_name}_{version.effective_date}_{safe_articles}.pdf"


@contextmanager
def open_law_site_browser(download_directory: Path):
    """
    브라우저 창을 열고, 일이 끝나면 반드시 닫는다.

    사용 예:
        with open_law_site_browser(폴더) as browser:
            browser.download_article_pdf(판, [ArticleNumber(1)])
            browser.download_article_pdf(판, [ArticleNumber(7)])
    """
    with LawSiteBrowser(download_directory) as browser:
        yield browser
