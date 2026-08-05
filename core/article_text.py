"""
조문 내용을 글자로 빠르게 받아온다. 미리보기에 쓴다.

왜 따로 만드는가:
  그림을 만들 때는 PDF 가 필요하지만, 미리보기는 '무슨 내용인지' 만 보면 된다.
  PDF 를 받으려면 브라우저를 띄우고 저장 창을 조작해야 해서 10초 넘게 걸린다.
  글자만 받아오는 통로를 쓰면 1~2초면 끝난다.

갈래마다 받아오는 방식이 다르다.
  법령:     조문 하나만 콕 집어 받을 수 있다 (약 3KB). 여러 개면 조문마다 받아 이어붙인다.
  행정규칙: 조문만 골라 받는 방법이 없어 문서 전체를 받은 뒤 잘라낸다 (약 110KB)
"""
import xml.etree.ElementTree as ElementTree

from config import LawSourceKind
from core import law_site
from core.article_number import (
    ARTICLE_HEADING_PATTERN,
    ArticleNumber,
    build_article_range_label,
)
from core.errors import ArticleNotFoundOnPageError, LawSiteStructureChangedError
from core.models import LawVersion

# 조문 본문이 담기는 태그들. 문서에 나오는 순서 그대로 이어붙이면 된다.
#   조문내용 = "제39조(…)" 같은 조 제목 줄
#   항내용   = "① …"
#   호내용   = "1. …"
#   목내용   = "가. …"
ARTICLE_CONTENT_TAGS = ("조문내용", "항내용", "호내용", "목내용")


def fetch_article_text(
    version: LawVersion, article_numbers: list[ArticleNumber]
) -> str:
    """
    지정한 판의 조문(들)을 글자로 받아온다.

    받아온 글자는 미리보기 화면에 그대로 뿌리고, 사용자가 드래그해서
    밑줄 칠 문구를 고르는 데 쓴다. 조문이 여러 개면 순서대로 이어붙인다.
    """
    if not article_numbers:
        raise ArticleNotFoundOnPageError(
            "조문", version.law_name, version.effective_date
        )

    if version.source_kind is LawSourceKind.STATUTE:
        return _fetch_statute_articles(version, article_numbers)
    return _fetch_administrative_rule_articles(version, article_numbers)


def fetch_full_law_text(version: LawVersion) -> str:
    """
    지정한 판의 본문 전체를 글자로 받아온다. (미리보기 '전체보기' 용)

    왜 조문 자르기를 안 하는가:
      사용자가 어느 조인지 모르는 채로 전체를 훑고 쟁점 문구를 고르기 위해서다.
      표·별표는 공개 API 글자에 안 들어올 수 있어, 필요하면 [원문 보기]로
      국가법령정보센터 화면을 연다.

    갈래별 받는 방법:
      행정규칙 — 원래 문서 전체가 온다. 자르지 않고 그대로 쓴다.
      법령     — 조문 번호(JO)를 빼고 요청하면 전체가 온다.
    """
    if version.source_kind is LawSourceKind.STATUTE:
        response_xml = law_site.request_open_api_article(
            search_target="law",
            identifier_name="MST",
            identifier_value=version.version_id,
            article_code=None,
        )
    else:
        response_xml = law_site.request_open_api_article(
            search_target="admrul",
            identifier_name="ID",
            identifier_value=version.version_id,
            article_code=None,
        )

    lines = _read_content_lines(response_xml, version, "전체")
    if not lines:
        raise ArticleNotFoundOnPageError(
            "전체", version.law_name, version.effective_date
        )
    return "\n".join(lines)


def _fetch_statute_articles(
    version: LawVersion, article_numbers: list[ArticleNumber]
) -> str:
    """
    법령(법률·시행령)에서 조문들을 받아온다.

    조문 번호를 여섯 자리로 적어 보내면 그 조문만 돌려준다.
    (제39조 -> '003900'. 제32조의2 -> '003202')
    조문이 여러 개면 하나씩 받아 이어붙인다. (한 번에 여러 조를 받는 방법이 없다)
    """
    blocks: list[str] = []
    for article in article_numbers:
        response_xml = law_site.request_open_api_article(
            search_target="law",
            identifier_name="MST",
            identifier_value=version.version_id,
            article_code=f"{article.number:04d}{article.branch:02d}",
        )
        lines = _read_content_lines(response_xml, version, article.label)
        if not lines:
            raise ArticleNotFoundOnPageError(
                article.label, version.law_name, version.effective_date
            )
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _fetch_administrative_rule_articles(
    version: LawVersion, article_numbers: list[ArticleNumber]
) -> str:
    """
    행정규칙(고시·훈령)에서 조문들을 받아온다.

    조문만 골라 받는 방법이 없어서 문서 전체를 받은 뒤,
    목표 조문에 속하는 줄만 모은다. 떨어진 조문도 한 번에 처리한다.
    """
    article_label = build_article_range_label(article_numbers)
    response_xml = law_site.request_open_api_article(
        search_target="admrul",
        identifier_name="ID",
        identifier_value=version.version_id,
        article_code=None,
    )

    all_lines = _read_content_lines(response_xml, version, article_label)
    article_lines = _cut_out_articles(all_lines, article_numbers)
    if not article_lines:
        raise ArticleNotFoundOnPageError(
            article_label, version.law_name, version.effective_date
        )

    # 요청한 조문이 모두 들어왔는지 확인한다.
    # (일부만 빠지면 조용히 틀린 미리보기가 되므로 꼭 짚어낸다)
    found = {
        _read_heading(line)
        for line in article_lines
        if _read_heading(line) is not None
    }
    missing = [article for article in article_numbers if article not in found]
    if missing:
        raise ArticleNotFoundOnPageError(
            build_article_range_label(missing),
            version.law_name,
            version.effective_date,
        )
    return "\n".join(article_lines)


def _read_content_lines(
    response_xml: str, version: LawVersion, article_label: str
) -> list[str]:
    """응답에서 조문 본문 줄들을 문서 순서대로 뽑아낸다."""
    try:
        root = ElementTree.fromstring(response_xml)
    except ElementTree.ParseError as error:
        raise LawSiteStructureChangedError(f"{article_label} 내용") from error

    return [
        element.text.strip()
        for element in root.iter()
        if element.tag in ARTICLE_CONTENT_TAGS and element.text and element.text.strip()
    ]


def _cut_out_articles(
    lines: list[str], article_numbers: list[ArticleNumber]
) -> list[str]:
    """
    여러 조문이 이어진 줄들에서 목표 조문에 속하는 줄만 모은다.

    줄마다 '지금 어느 조문 소속인지' 를 헤딩이 나올 때마다 갱신한다.
    떨어진 조문(제1조와 제5조)도 한 번에 처리할 수 있다.

    왜 시작·끝 인덱스로 자르지 않는가:
      예전에는 조문 하나(시작~다음 조문 직전)만 잘랐다.
      여러 조문을 받으려면 그 방식을 여러 번 돌리거나, 줄 단위로
      '이 줄이 목표에 속하는지' 를 판별하는 편이 단순하다.
    """
    wanted = set(article_numbers)
    current: ArticleNumber | None = None
    kept: list[str] = []

    for line in lines:
        heading = _read_heading(line)
        if heading is not None:
            current = heading
        if current in wanted:
            kept.append(line)

    return kept


def _read_heading(line: str) -> ArticleNumber | None:
    """줄이 조문 제목이면 번호·가지번호를 돌려주고, 아니면 None."""
    matched = ARTICLE_HEADING_PATTERN.match(line)
    if not matched:
        return None
    return ArticleNumber(
        number=int(matched.group(1)),
        branch=int(matched.group(2) or 0),
    )
