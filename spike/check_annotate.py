"""
annotate.py 가 밑줄을 제대로 긋고 본문만 잘라내는지 확인한다.

확인 항목:
  - 밑줄이 받침을 관통하지 않는가 (그림을 눈으로 확인)
  - 여러 줄에 걸친 문구도 줄마다 밑줄이 그어지는가
  - 없는 문구를 넣으면 알아듣기 쉬운 오류가 나는가
  - 조문 본문만 뽑아내는 기능이 제목·시행일을 걸러내는가
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
import fitz
from core.annotate import extract_article_body_text, underline_and_capture
from core.errors import UnderlinePhraseNotFoundError

PDF_DIRECTORY = config.OUTPUT_DIRECTORY / "check_pdf"
IMAGE_DIRECTORY = config.OUTPUT_DIRECTORY / "check_annotate"

CASES = [
    ("공동주택 하자의 조사, 보수비용 산정 및 하자판정기준_2025-02-03_제1조.pdf",
     ["제1조(목적) 이 기준은"]),
    ("공동주택 하자의 조사, 보수비용 산정 및 하자판정기준_2025-02-03_제7조.pdf",
     ["균열 폭이 0.3mm 이상인 경우 시공하자로 본다", "철근이 배근된 위치에"]),
]

for pdf_name, phrases in CASES:
    pdf_path = PDF_DIRECTORY / pdf_name
    if not pdf_path.exists():
        print(f"[건너뜀] 먼저 check_law_pdf.py 를 실행하세요: {pdf_name}")
        continue

    image_path = IMAGE_DIRECTORY / (pdf_path.stem + ".png")
    made_images = underline_and_capture(pdf_path, phrases, image_path)
    total_kilobytes = sum(p.stat().st_size for p in made_images) // 1024
    print(f"[완료] {pdf_path.stem[-14:]}  밑줄 {len(phrases)}건 -> "
          f"그림 {len(made_images)}장 ({total_kilobytes}KB)")

# 색을 바꿔 그을 수 있는지 (첫 케이스가 있을 때만)
first_case = CASES[0]
first_pdf = PDF_DIRECTORY / first_case[0]
if first_pdf.exists():
    blue_rgb = config.underline_color_for_name("파랑")
    blue_path = IMAGE_DIRECTORY / (first_pdf.stem + "_파랑.png")
    underline_and_capture(
        first_pdf, first_case[1], blue_path, underline_color=blue_rgb
    )
    print(f"[완료] 파랑 밑줄 시험 -> {blue_path.name}")
else:
    print("[건너뜀] 파랑 밑줄 시험 (PDF 없음)")

print("\n=== 없는 문구를 넣었을 때 ===")
first_pdf = PDF_DIRECTORY / CASES[0][0]
if first_pdf.exists():
    try:
        underline_and_capture(first_pdf, ["있을 리 없는 문구"], IMAGE_DIRECTORY / "버림.png")
        print("  문제: 오류가 나야 하는데 통과했습니다")
    except UnderlinePhraseNotFoundError as error:
        print(f"  정상: {error}")

print("\n=== 띄어쓰기가 다른 문구도 찾는지 ===")
if first_pdf.exists():
    try:
        underline_and_capture(first_pdf, ["제1조(목적)이기준은"], IMAGE_DIRECTORY / "띄어쓰기시험.png")
        print("  정상: 띄어쓰기를 무시하고 찾았습니다")
    except UnderlinePhraseNotFoundError:
        print("  문제: 띄어쓰기가 달라 못 찾았습니다")

print("\n=== 조문 본문만 뽑아내기 (개정본 비교용) ===")
for pdf_name, _ in CASES:
    pdf_path = PDF_DIRECTORY / pdf_name
    if pdf_path.exists():
        body = extract_article_body_text(pdf_path)
        print(f"  {pdf_path.stem[-8:]}: {len(body)}자 / {body[:66]}...")

print("\n=== 제목 위 안내문을 뺐는가 ===")
from core.annotate import find_content_area

def _top_lines_of_capture(pdf_path: Path) -> list[str]:
    """자른 영역 맨 위 글 몇 줄. 안내문이 남았는지 볼 때 쓴다."""
    document = fitz.open(pdf_path)
    try:
        clip = find_content_area(document[0])
        clipped_text = document[0].get_text("text", clip=clip)
    finally:
        document.close()
    return [line.strip() for line in clipped_text.splitlines() if line.strip()]


title_crop_targets = list(PDF_DIRECTORY.glob("*.pdf"))
if not title_crop_targets:
    print("  [건너뜀] PDF 가 없습니다")
else:
    for pdf_path in title_crop_targets:
        top_lines = _top_lines_of_capture(pdf_path)
        top_text = " ".join(top_lines[:4])
        has_notice = any(
            marker in top_text
            for marker in ("본 법령은", "본 행정규칙은", "아이콘을 통해 확인")
        )
        print(
            f"  [{'문제' if has_notice else '정상'}] {pdf_path.name[:40]} "
            f"맨 위: {top_text[:80]}"
        )

print("\n=== 순번 밑줄 (제7조의 '균열') ===")
article7 = PDF_DIRECTORY / CASES[1][0]
if article7.exists():
    # '균열' 은 제7조에 여러 번 나온다. 두 번째만 밑줄을 긋는다.
    second_only = IMAGE_DIRECTORY / "제7조_균열_2번째.png"
    underline_and_capture(article7, ["균열 [2번째]"], second_only)
    print(f"  정상: 두 번째 '균열' 만 밑줄 -> {second_only.name}")
else:
    print("  [건너뜀] 제7조 PDF 없음")
