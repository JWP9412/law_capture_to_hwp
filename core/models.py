"""
프로그램 안에서 주고받는 '자료의 모양'을 정의한 파일.

여기 있는 것들은 값을 담아 나르는 상자일 뿐, 스스로 무슨 일을 하지는 않는다.
(단, 자기 자신에 대해 답할 수 있는 것 — 예를 들어 '나는 몇 장짜리 작업인가' — 은 여기 둔다)

화면에 보이는 항목과 이름을 최대한 맞춰 두었다.
예를 들어 화면에서 '담은 목록'의 한 줄이 곧 ArticleCaptureJob 하나다.
"""
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import config
from config import InsertionMode, LawSourceKind
from core.article_number import ArticleNumber, build_article_range_label

_WHITESPACE_PATTERN = re.compile(r"\s+")


def _without_spaces(text: str) -> str:
    """이름을 견줄 때 띄어쓰기 차이를 무시하려고 쓴다."""
    return _WHITESPACE_PATTERN.sub("", text)


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

    # 이 판이 시행되던 당시의 이름. 지금 이름과 다를 수 있다.
    #
    # 위의 law_name 은 '검색한 시점의 현행 이름' 이라 옛 판에도 현재 이름이 붙는다.
    # 그런데 법령·고시는 이름이 바뀌는 일이 드물지 않다.
    #   - 「주택법」은 1973년에 「주택건설촉진법」이었다
    #   - 「자동차압급기댐퍼의 성능인증 및 제품검사의 기술기준」은
    #     2009년에 「자동차압·과압조절형댐퍼의 성능시험기술기준」이었다
    # 그대로 캡션에 쓰면 그림 속 문서 제목과 캡션이 서로 다른 이름이 되어
    # 서면에 실제와 다른 이름을 인용하게 된다.
    #
    # 연혁을 읽을 때 함께 채워진다. 못 읽었으면 비어 있다.
    historical_law_name: str = ""

    @property
    def display_law_name(self) -> str:
        """
        캡션과 화면에 쓸 이름.

        당시 이름을 알면 그것을 쓰고, 모르면 지금 이름을 쓴다.
        (연혁을 못 읽었거나 검색 결과만 가지고 만든 판인 경우)
        """
        return self.historical_law_name or self.law_name

    @property
    def has_different_name_now(self) -> bool:
        """
        이 판이 시행되던 당시의 이름이 지금 이름과 '실제로' 다른가.

        띄어쓰기 차이는 다른 이름으로 치지 않는다. 옛 법령은 이름을 붙여 쓰는
        표기법을 썼기 때문이다. 예를 들어 「주택건설기준 등에 관한 규정」은
        옛 판에 「주택건설기준등에관한규정」으로 적혀 있는데, 이것은 개명이 아니라
        표기법이 바뀐 것뿐이라 알릴 일이 아니다.

        (캡션에는 여전히 당시 표기 그대로 들어간다. 그것이 그 문서에 적힌 이름이다)
        """
        if not self.historical_law_name:
            return False
        return _without_spaces(self.historical_law_name) != _without_spaces(
            self.law_name
        )

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
        return f"{self.display_law_name} [{self.effective_date_label}] ({status})"


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


@dataclass(frozen=True)
class ArticleTextComparison:
    """
    앞 개정본과 조문 내용을 견준 결과.

    '같다/다르다' 만 담지 않고 얼마나 닮았는지까지 담는 이유:
    이름만 바뀌고 내용은 그대로인 개정, 문구만 조금 다듬은 개정이 흔한데
    글자 하나만 달라도 '다름' 이 되므로 그 사실을 알아챌 수 없다.
    """

    is_same: bool
    similarity_ratio: float  # 0.0(전혀 다름) ~ 1.0(완전히 같음)

    @property
    def is_similar_but_not_same(self) -> bool:
        """완전히 같지는 않지만 알릴 만큼 닮았는가."""
        return (
            not self.is_same
            and self.similarity_ratio >= config.SIMILARITY_NOTICE_THRESHOLD
        )

    @property
    def similarity_percent(self) -> int:
        """캡션에 적을 백분율. 99.7% 를 100% 로 적으면 안 되므로 내림한다."""
        return int(self.similarity_ratio * 100)


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
    comparison: ArticleTextComparison = field(
        default_factory=lambda: ArticleTextComparison(
            is_same=False, similarity_ratio=0.0
        )
    )

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
