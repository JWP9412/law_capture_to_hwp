"""
프로그램 안에서 주고받는 '자료의 모양'을 정의한 파일.

여기 있는 것들은 값을 담아 나르는 상자일 뿐, 스스로 무슨 일을 하지는 않는다.
(단, 자기 자신에 대해 답할 수 있는 것 — 예를 들어 '나는 몇 장짜리 작업인가' — 은 여기 둔다)

화면에 보이는 항목과 이름을 최대한 맞춰 두었다.
예를 들어 화면에서 '담은 목록'의 한 줄이 곧 ArticleCaptureJob 하나다.
"""
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import config
from config import InsertionMode, LawSourceKind
from core.article_number import ArticleNumber, build_article_range_label


@dataclass(frozen=True)
class LawVersion:
    """
    법령·고시의 '어느 시점 판' 하나를 가리킨다.

    같은 법이라도 개정될 때마다 별개의 문서로 존재한다.
    예를 들어 하자판정기준은 2025. 2. 3. 시행판과 2026. 7. 8. 시행판이 서로 다른 문서다.
    """

    source_kind: LawSourceKind
    version_id: str  # 사이트가 이 판을 가리키는 데 쓰는 번호
    law_name: str
    effective_date: date  # 시행일
    promulgation_label: str  # 예: "국토교통부고시 제2025-58호, 2025. 2. 3., 일부개정"
    is_currently_in_effect: bool  # 지금 살아있는 판인지

    @property
    def detail_page_url(self) -> str:
        """
        이 판의 본문 화면 주소.

        국가법령정보센터에서 표·별표까지 보고 싶을 때 브라우저로 연다.
        법령은 시행일(efYd)을 함께 붙여야 같은 개정본이 여러 시행일로
        나뉠 때도 원하는 판이 열린다. (행정규칙은 문서 번호만으로 충분하다)
        """
        adapter = config.LAW_SITE_ADAPTERS[self.source_kind]
        parameter = adapter["version_id_parameter"]
        url = (
            f"{config.LAW_SITE_BASE_URL}{adapter['detail_page_path']}"
            f"?{parameter}={self.version_id}"
        )
        if self.source_kind is LawSourceKind.STATUTE:
            compact_date = (
                f"{self.effective_date.year:04d}"
                f"{self.effective_date.month:02d}"
                f"{self.effective_date.day:02d}"
            )
            url = f"{url}&efYd={compact_date}"
        return url

    @property
    def effective_date_label(self) -> str:
        """캡션에 넣을 시행일 표기. 예: '시행 2025. 2. 3.'"""
        moment = self.effective_date
        return f"시행 {moment.year}. {moment.month}. {moment.day}."

    def __str__(self) -> str:
        status = "현행" if self.is_currently_in_effect else "구"
        return f"{self.law_name} [{self.effective_date_label}] ({status})"


@dataclass(frozen=True)
class ArticleCaptureJob:
    """
    화면의 '담은 목록' 한 줄에 해당한다.

    조문(들)을 여러 개정본에 걸쳐 캡처할 수 있으므로,
    이 한 줄이 실제로는 여러 장의 그림을 만들어낸다.
    (예: 제1, 2조 × 개정본 2개 = 그림 2장 — 조문을 한 PDF 에 담아 쪽마다 그림)
    """

    law_name: str
    target_versions: list[LawVersion]  # 시행일 오래된 순으로 정렬되어 들어온다
    article_numbers: list[ArticleNumber]
    underline_phrases: list[str]
    # 그림을 넣을 기존 한글 문서. 비워두면(None) 새 문서를 만든다.
    target_hwp_path: Path | None = None
    insertion_mode: InsertionMode = InsertionMode.APPEND_TO_END
    should_add_caption: bool = True
    should_add_border: bool = True

    @property
    def expected_figure_count(self) -> int:
        """이 줄이 만들어낼 그림 장수. 화면에서 '총 몇 장' 을 보여줄 때 쓴다."""
        # 쪽 수는 PDF 를 받기 전에는 모르므로, 개정본 수만큼으로 가늠한다.
        return len(self.target_versions)

    @property
    def article_label(self) -> str:
        return build_article_range_label(self.article_numbers)

    def __str__(self) -> str:
        return f"{self.article_label} (개정본 {self.expected_figure_count}개)"


@dataclass(frozen=True)
class ArticleCaptureTask:
    """
    실제로 그림(들)을 만드는 작업 단위. 개정본 하나에 해당한다.

    ArticleCaptureJob 이 개정본 수만큼 펼쳐지면 이것들이 나온다.
    조문이 길거나 여러 개면 PDF 가 여러 쪽이 되어 그림도 여러 장이다.
    """

    version: LawVersion
    article_numbers: list[ArticleNumber]
    underline_phrases: list[str]
    target_hwp_path: Path | None
    insertion_mode: InsertionMode
    should_add_caption: bool = True
    should_add_border: bool = True

    @property
    def article_label(self) -> str:
        return build_article_range_label(self.article_numbers)

    def __str__(self) -> str:
        return f"{self.article_label} [{self.version.effective_date_label}]"


@dataclass
class CapturedArticle:
    """
    조문(들)을 내려받아 그림으로 만든 결과.

    그림이 여러 장인 이유: 조문이 길거나 여러 개면 PDF 가 여러 쪽이 되고,
    쪽마다 그림 하나씩 만든다. 짧은 조문이면 한 장뿐이다.
    """

    task: ArticleCaptureTask
    pdf_path: Path
    image_paths: list[Path]  # 쪽 순서대로
    article_body_text: str  # 개정본끼리 내용이 같은지 비교할 때 쓴다
    is_same_as_previous_version: bool = False

    @property
    def page_count(self) -> int:
        return len(self.image_paths)


@dataclass
class CaptureFailure:
    """작업 하나가 실패했을 때 무엇이 왜 안 됐는지."""

    task: ArticleCaptureTask
    error: Exception

    @property
    def message_for_display(self) -> str:
        """화면에 그대로 띄울 한국어 한 줄."""
        return f"{self.task} — {self.error}"


@dataclass
class CaptureRunResult:
    """
    한 번 '실행' 했을 때의 전체 결과.

    성공한 것과 실패한 것을 함께 담는다.
    조문 하나가 실패해도 나머지는 계속 진행하기 때문에 둘 다 생긴다.
    """

    succeeded: list[CapturedArticle] = field(default_factory=list)
    failed: list[CaptureFailure] = field(default_factory=list)
    result_hwp_path: Path | None = None

    @property
    def total_count(self) -> int:
        return len(self.succeeded) + len(self.failed)

    @property
    def has_any_failure(self) -> bool:
        return len(self.failed) > 0

    @property
    def summary_for_display(self) -> str:
        """화면 맨 위에 띄울 한 줄 요약."""
        if not self.has_any_failure:
            return f"{self.total_count}건 모두 완료"
        return f"{self.total_count}건 중 {len(self.succeeded)}건 완료, {len(self.failed)}건 실패"
