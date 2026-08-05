"""
긴 조문의 뒷부분이 잘리지 않는지 확인한다. (한글은 켜지 않는다)

**실제로 데이터가 사라지던 문제다.**
「주택법」 제2조(정의) 처럼 긴 조문은 PDF 가 3쪽까지 나오는데,
예전에는 첫 쪽만 그림으로 만들고 나머지를 조용히 버렸다.
아무 경고도 없어서 서면에 잘린 그림이 들어가도 알 수 없었다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fitz

import config
from core.annotate import extract_article_body_text, find_text_areas, underline_and_capture

PDF_DIRECTORY = config.OUTPUT_DIRECTORY / "작업중"
IMAGE_DIRECTORY = config.OUTPUT_DIRECTORY / "check_multipage"


def report(label: str, is_ok: bool, detail: str = "") -> bool:
    print(f"  [{'OK  ' if is_ok else '실패'}] {label}" + (f"  -- {detail}" if detail else ""))
    return is_ok


def find_multipage_pdf() -> Path | None:
    """여러 쪽짜리 조문 PDF 를 찾는다. (이미 받아둔 것 중에서)"""
    for path in sorted(PDF_DIRECTORY.glob("*.pdf")):
        document = fitz.open(path)
        page_count = document.page_count
        document.close()
        if page_count >= 2:
            return path
    return None


all_passed = True

print("=" * 62)
print("긴 조문이 잘리지 않는지 확인 (한글 안 켬)")
print("=" * 62)

multipage_pdf = find_multipage_pdf()
if multipage_pdf is None:
    print("\n여러 쪽짜리 PDF 가 없습니다. 먼저 긴 조문을 한 번 받아주세요.")
    print(f"  (예: python run_from_command_line.py --name 주택법 --date 2011-01-28 "
          f"--article 2 --underline \"이 법에서 사용하는\" --out out\\시험.hwp)")
    sys.exit(1)

document = fitz.open(multipage_pdf)
page_count = document.page_count
print(f"\n대상: {multipage_pdf.name}  ({page_count}쪽)")

def pick_body_phrase(page) -> str | None:
    """
    그 쪽의 '본문' 에서 문구를 하나 고른다.

    머리말('법제처', '국가법령정보센터')과 제목 줄은 모든 쪽에 똑같이 나오므로
    고르면 안 된다. 그것으로는 '이 쪽에서만 찾아지는가' 를 확인할 수 없다.
    """
    skip_words = ("법제처", "국가법령정보센터", "[시행")
    candidates = [
        text
        for text in (line.strip() for line in page.get_text().splitlines())
        if len(text) >= 8 and not any(word in text for word in skip_words)
    ]
    if not candidates:
        return None

    # 마지막 쪽은 줄이 몇 개 없을 수 있으므로 가장 긴 줄을 고른다.
    return max(candidates, key=len)[:30]


# 쪽마다 그 쪽에만 있는 문구를 골라 둔다 (뒷쪽 문구로도 밑줄이 되는지 보려고)
phrase_by_page = {}
for index, page in enumerate(document):
    phrase = pick_body_phrase(page)
    if phrase:
        phrase_by_page[index] = phrase
document.close()

print("\n1. 쪽마다 그림이 만들어지는가")
first_image = IMAGE_DIRECTORY / (multipage_pdf.stem + ".png")
made_images = underline_and_capture(multipage_pdf, [], first_image)
all_passed &= report("쪽 수만큼 그림이 나왔는가", len(made_images) == page_count,
                     f"{page_count}쪽 -> 그림 {len(made_images)}장")
for image_path in made_images:
    print(f"          {image_path.name}")

print("\n2. 뒷쪽에 있는 문구로도 밑줄이 되는가")
for page_index, phrase in phrase_by_page.items():
    document = fitz.open(multipage_pdf)
    found_on = [i for i, page in enumerate(document) if find_text_areas(page, phrase)]
    document.close()
    all_passed &= report(
        f"{page_index + 1}쪽 문구를 찾았는가",
        page_index in found_on,
        f"'{phrase[:24]}…' -> {[i + 1 for i in found_on]}쪽에서 발견",
    )

print("\n3. 본문 뽑아내기가 모든 쪽을 보는가 (개정본 비교에 쓰임)")
# 마지막 쪽에만 있는 문구가 뽑은 결과에 들어있는지 본다.
# 첫 쪽만 보던 예전 코드라면 이 문구가 빠진다.
body_text = extract_article_body_text(multipage_pdf).replace(" ", "")
last_page_phrase = phrase_by_page.get(page_count - 1, "")
all_passed &= report(
    "마지막 쪽 내용까지 뽑았는가",
    bool(last_page_phrase) and last_page_phrase.replace(" ", "") in body_text,
    f"뽑은 글자 {len(body_text):,}자, 마지막 쪽 문구 '{last_page_phrase[:24]}…'",
)

print("\n" + "=" * 62)
print("통과 — 긴 조문이 잘리지 않습니다" if all_passed else "실패 — 위 목록을 보세요")
print("=" * 62)
sys.exit(0 if all_passed else 1)
