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

print("\n=== 순번 밑줄 (제7조의 '균열') ===")
article7 = PDF_DIRECTORY / CASES[1][0]
if article7.exists():
    # '균열' 은 제7조에 여러 번 나온다. 두 번째만 밑줄을 긋는다.
    second_only = IMAGE_DIRECTORY / "제7조_균열_2번째.png"
    underline_and_capture(article7, ["균열 [2번째]"], second_only)
    print(f"  정상: 두 번째 '균열' 만 밑줄 -> {second_only.name}")
else:
    print("  [건너뜀] 제7조 PDF 없음")
