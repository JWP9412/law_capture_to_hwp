"""
hwp_insert.py 가 그림을 제대로 넣는지 확인한다.

확인 항목:
  - 그림 두 장을 한 문서에 연달아 넣을 수 있는가
  - 캡션이 그림 '위' 에 '왼쪽 정렬' 로 붙는가
  - 캡션 글씨가 휴먼명조 10pt 인가
  - 그림에 0.12mm 테두리가 들어가는가
  - 두 번째 그림을 넣을 때 첫 번째 캡션이 흐트러지지 않는가 (가장 중요)
  - 보안 프로그램에 막히지 않고 저장되는가
"""
import shutil
import sys
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image

import config
from config import InsertionMode
from core.hwp_insert import PictureInsertion, open_hwp_document

IMAGE_DIRECTORY = config.OUTPUT_DIRECTORY / "check_annotate"
RESULT_DIRECTORY = config.OUTPUT_DIRECTORY / "check_hwp"
RESULT_HWP_PATH = RESULT_DIRECTORY / "삽입시험.hwp"
PREVIEW_IMAGE_PATH = RESULT_DIRECTORY / "삽입시험_미리보기.png"

CASES = [
    # 설명만 넘긴다. '[그림 N]' 번호는 한글 자동번호 필드가 붙인다.
    ("공동주택 하자의 조사, 보수비용 산정 및 하자판정기준_2025-02-03_제1조.png",
     "공동주택 하자의 조사, 보수비용 산정 및 하자판정기준 제1조 발췌 (시행 2025. 2. 3.)",
     True, True),
    # 앞 개정안과 동일 문구 강조(빨강+굵게) 검증용
    ("공동주택 하자의 조사, 보수비용 산정 및 하자판정기준_2025-02-03_제1조.png",
     "공동주택 하자의 조사, 보수비용 산정 및 하자판정기준 제1조 발췌 (시행 2025. 2. 3.) (앞 개정안과 동일)",
     True, True),
    ("공동주택 하자의 조사, 보수비용 산정 및 하자판정기준_2025-02-03_제7조.png",
     "공동주택 하자의 조사, 보수비용 산정 및 하자판정기준 제7조 발췌 (시행 2025. 2. 3.)",
     True, True),
    # 다중 조문 캡션 표기
    ("공동주택 하자의 조사, 보수비용 산정 및 하자판정기준_2025-02-03_제1조.png",
     "공동주택 하자의 조사, 보수비용 산정 및 하자판정기준 제1, 2조 발췌 (시행 2025. 2. 3.)",
     True, True),
    # 캡션 끔
    ("공동주택 하자의 조사, 보수비용 산정 및 하자판정기준_2025-02-03_제1조.png",
     None, False, True),
    # 테두리 끔 (캡션은 켬)
    ("공동주택 하자의 조사, 보수비용 산정 및 하자판정기준_2025-02-03_제7조.png",
     "테두리 없이 넣은 그림", True, False),
]


def render_preview(hwp_path: Path) -> Path:
    """만들어진 한글 문서를 사진으로 찍어 눈으로 확인할 수 있게 한다."""
    from pyhwpx import Hwp

    temporary_bitmap = Path(tempfile.gettempdir()) / f"preview_{uuid.uuid4().hex}.bmp"
    hwp = Hwp(new=True, visible=False, register_module=True)
    try:
        hwp.open(str(hwp_path))
        hwp.create_page_image(str(temporary_bitmap), pgno=0, resolution=150, format="bmp")
    finally:
        hwp.quit()

    with Image.open(temporary_bitmap) as bitmap:
        PREVIEW_IMAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
        bitmap.convert("RGB").save(PREVIEW_IMAGE_PATH)
    temporary_bitmap.unlink(missing_ok=True)
    return PREVIEW_IMAGE_PATH


missing = [name for name, *_ in CASES if not (IMAGE_DIRECTORY / name).exists()]
if missing:
    print("먼저 check_annotate.py 를 실행하세요. 없는 그림:")
    for name in set(missing):
        print(f"  {name}")
    sys.exit(1)

print("한글 문서에 그림 넣기 (캡션·테두리 선택 포함)")
with open_hwp_document(None, RESULT_HWP_PATH) as editor:
    for image_name, caption, should_add_caption, should_add_border in CASES:
        editor.insert_picture_with_caption(
            PictureInsertion(
                image_path=IMAGE_DIRECTORY / image_name,
                caption=caption if should_add_caption else None,
                insertion_mode=InsertionMode.APPEND_TO_END,
                should_add_border=should_add_border,
            )
        )
        label = caption[:38] if caption else "(캡션 없음)"
        print(f"  넣음: {label}...  테두리={'O' if should_add_border else 'X'}")

print(f"\n저장 완료: {RESULT_HWP_PATH}")
print(f"  파일 크기: {RESULT_HWP_PATH.stat().st_size:,}바이트")

preview_path = render_preview(RESULT_HWP_PATH)
print(f"미리보기: {preview_path}")
