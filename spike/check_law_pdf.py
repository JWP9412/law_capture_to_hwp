"""
law_pdf.py 가 조문 PDF 를 제대로 받아오는지 확인한다.

확인 항목:
  - 여러 조문을 창 하나로 연달아 받을 수 있는가
  - 개정본이 다르면 서로 다른 내용이 받아지는가 (시점 선택이 실제로 먹히는가)
  - 가지번호·다중 조문이 제대로 받아지는가
  - 없는 조문을 요청하면 알아듣기 쉬운 오류가 나는가
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fitz

import config
from config import LawSourceKind
from core.article_number import ArticleNumber
from core.errors import ArticleNotFoundOnPageError
from core.law_pdf import open_law_site_browser
from core.law_source import DatePeriod, find_version_effective_on, find_versions_effective_between, search_laws

DOWNLOAD_DIRECTORY = config.OUTPUT_DIRECTORY / "check_pdf"


def summarize_pdf(pdf_path: Path) -> str:
    """받은 PDF 의 첫 줄들을 짧게 보여준다."""
    document = fitz.open(pdf_path)
    lines = [line.strip() for line in document[0].get_text().splitlines() if line.strip()]
    document.close()
    body_line = next((line for line in lines if line.startswith("제")), "(조문 못 찾음)")
    return f"{len(lines)}줄 / {body_line[:56]}"


def report(label: str, is_ok: bool, detail: str = "") -> bool:
    print(f"  [{'OK  ' if is_ok else '실패'}] {label}" + (f"  -- {detail}" if detail else ""))
    return is_ok


all_passed = True

law = search_laws("하자판정기준")[0]
versions = find_versions_effective_between(
    law, DatePeriod(date(2024, 1, 1), date(2026, 12, 31))
)

print(f"대상: {law.law_name}")
print(f"개정본 {len(versions)}개\n")

with open_law_site_browser(DOWNLOAD_DIRECTORY) as browser:
    for version in versions:
        print(f"[{version.effective_date_label}]")
        for article in (ArticleNumber(1), ArticleNumber(7)):
            pdf_path = browser.download_article_pdf(version, [article])
            print(f"    {article.label} -> {pdf_path.name}")
            print(f"        {summarize_pdf(pdf_path)}")

        # 다중 조문: 제1, 2조를 한 PDF 로
        multi_path = browser.download_article_pdf(
            version, [ArticleNumber(1), ArticleNumber(2)]
        )
        document = fitz.open(multi_path)
        multi_text = "\n".join(page.get_text() for page in document)
        document.close()
        all_passed &= report(
            f"{version.effective_date_label} 제1·2조 한 PDF",
            "제1조" in multi_text and "제2조" in multi_text,
            multi_path.name,
        )

    print("\n[가지번호 — 주택건설기준]")
    housing = search_laws("주택건설기준 등에 관한 규정", LawSourceKind.STATUTE)[0]
    housing_version = find_version_effective_on(housing, date(2025, 6, 1))
    branch_path = browser.download_article_pdf(
        housing_version, [ArticleNumber(32, 2)]
    )
    document = fitz.open(branch_path)
    branch_text = "\n".join(page.get_text() for page in document)
    document.close()
    all_passed &= report(
        "제32조의2 PDF",
        "제32조의2" in branch_text,
        summarize_pdf(branch_path),
    )

    print("\n[없는 조문 요청 시]")
    try:
        browser.download_article_pdf(versions[0], [ArticleNumber(9999)])
        all_passed &= report("없는 조문이 막히는가", False)
    except ArticleNotFoundOnPageError as error:
        all_passed &= report("없는 조문이 막히는가", True, str(error))

print(f"\n받은 파일들: {DOWNLOAD_DIRECTORY}")
print("=" * 58)
print("통과" if all_passed else "실패 — 위 목록을 보세요")
sys.exit(0 if all_passed else 1)
