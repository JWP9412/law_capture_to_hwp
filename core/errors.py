"""
이 프로그램에서 발생할 수 있는 오류들을 종류별로 정의한 파일.

왜 오류마다 이름을 따로 붙이는가:
  "뭔가 잘못됐습니다" 하나로 뭉뚱그리면, 화면에 무슨 일이 났는지 설명할 수가 없다.
  오류에 이름과 한국어 설명을 붙여두면 화면에 그대로 띄울 수 있고,
  코드에서도 "이 오류는 건너뛰고 계속, 저 오류는 중단" 처럼 구분해 다룰 수 있다.

각 오류 클래스가 만들어질 때 한국어 문장을 함께 만들어 두는 이유도 같다.
화면에는 이 문장만 보여주고, 개발자용 상세 정보는 로그 파일에만 남긴다.
"""
from datetime import date
from pathlib import Path


class LawCaptureError(Exception):
    """이 프로그램에서 나는 모든 오류의 뿌리. 이걸 잡으면 우리 오류 전부를 잡는다."""


# ---------------------------------------------------------------------------
# 법령을 찾는 단계에서 나는 오류
# ---------------------------------------------------------------------------


class LawNotFoundError(LawCaptureError):
    """검색어에 해당하는 법령·고시를 아예 찾지 못한 경우."""

    def __init__(self, law_name: str):
        self.law_name = law_name
        super().__init__(
            f"'{law_name}' 이라는 법령·고시를 찾지 못했습니다. "
            f"이름의 일부만 넣어 다시 찾아보세요."
        )


class LawVersionNotFoundError(LawCaptureError):
    """법령은 찾았지만, 지정한 시점에 시행 중이던 판이 없는 경우."""

    def __init__(self, law_name: str, reference_date: date):
        self.law_name = law_name
        self.reference_date = reference_date
        super().__init__(
            f"'{law_name}' 은(는) {reference_date} 시점에 시행 중인 판이 없습니다. "
            f"제정일보다 이전 날짜를 넣지 않았는지 확인해 주세요."
        )


class NoVersionInPeriodError(LawCaptureError):
    """지정한 기간 안에 시행된 개정본이 하나도 없는 경우."""

    def __init__(self, law_name: str, period_start: date, period_end: date):
        self.law_name = law_name
        super().__init__(
            f"'{law_name}' 은(는) {period_start} ~ {period_end} 기간에 시행된 개정본이 없습니다."
        )


# ---------------------------------------------------------------------------
# PDF 를 내려받는 단계에서 나는 오류
# ---------------------------------------------------------------------------


class ArticleNotFoundOnPageError(LawCaptureError):
    """법령 화면에 해당 조문이 없는 경우. (조문 번호를 잘못 넣었거나, 그 판에는 없는 조문)"""

    def __init__(self, article_label: str, law_name: str, effective_date: date):
        self.article_label = article_label
        super().__init__(
            f"'{law_name}' {effective_date} 시행판에는 {article_label}가 없습니다."
        )


class ArticlePdfDownloadError(LawCaptureError):
    """저장 버튼을 눌렀지만 파일을 받지 못한 경우."""

    def __init__(self, article_label: str, reason: str):
        self.article_label = article_label
        super().__init__(f"{article_label} PDF를 내려받지 못했습니다. ({reason})")


class LawSiteStructureChangedError(LawCaptureError):
    """화면에서 찾아야 할 버튼·입력칸이 없는 경우. 사이트 개편을 의심해야 한다."""

    def __init__(self, missing_element: str):
        self.missing_element = missing_element
        super().__init__(
            f"국가법령정보센터 화면에서 '{missing_element}' 을(를) 찾지 못했습니다. "
            f"사이트 구조가 바뀌었을 수 있습니다."
        )


# ---------------------------------------------------------------------------
# 밑줄을 긋는 단계에서 나는 오류
# ---------------------------------------------------------------------------


class UnderlinePhraseNotFoundError(LawCaptureError):
    """밑줄을 그으려는 문구를 PDF 안에서 찾지 못한 경우."""

    def __init__(self, phrase: str, pdf_path: Path):
        # 화면에서 "어느 문구가 문제였는지" 짚어주기 위해 따로 보관한다.
        self.phrase = phrase
        self.pdf_path = pdf_path
        super().__init__(
            f"'{phrase}' 문구를 조문에서 찾지 못했습니다. "
            f"개정으로 문구가 바뀌었거나 띄어쓰기가 다를 수 있습니다."
        )


class EmptyCaptureAreaError(LawCaptureError):
    """잘라낼 내용 영역을 계산했는데 비어 있는 경우."""

    def __init__(self, pdf_path: Path):
        super().__init__(f"'{pdf_path.name}' 에서 잘라낼 내용을 찾지 못했습니다.")


# ---------------------------------------------------------------------------
# 한글 문서를 다루는 단계에서 나는 오류
# ---------------------------------------------------------------------------


class HwpAutomationError(LawCaptureError):
    """한글 프로그램 조작이 실패한 경우의 일반적인 오류."""

    def __init__(self, what_failed: str, reason: str = ""):
        detail = f" ({reason})" if reason else ""
        super().__init__(f"한글 문서 작업 중 '{what_failed}' 에 실패했습니다.{detail}")


class HwpSaveBlockedError(LawCaptureError):
    """
    보안 프로그램 때문에 한글이 파일을 저장하지 못한 경우.

    이 컴퓨터는 회사 PC라 문서보안 프로그램이 한글의 저장을 막는다.
    그래서 평소에는 임시 폴더를 거쳐 저장하는데, 그 임시 폴더마저 막히면 이 오류가 난다.
    """

    def __init__(self, attempted_path: Path):
        self.attempted_path = attempted_path
        super().__init__(
            f"한글이 파일을 저장하지 못했습니다: {attempted_path}\n"
            f"회사 보안 프로그램이 저장을 막고 있을 수 있습니다."
        )


class PlaceholderNotFoundError(LawCaptureError):
    """문서에서 그림을 넣을 표시 문구를 찾지 못한 경우."""

    def __init__(self, placeholder: str, hwp_path: Path):
        self.placeholder = placeholder
        super().__init__(
            f"'{hwp_path.name}' 문서에서 '{placeholder}' 표시를 찾지 못했습니다."
        )
