"""한글 문서를 사진으로 찍어 눈으로 확인할 수 있게 한다. (검증용 도구)"""
import sys
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image
from pyhwpx import Hwp

PREVIEW_RESOLUTION_IN_DPI = 150


def render_all_pages(hwp_path: Path) -> list[Path]:
    """문서의 모든 쪽을 그림으로 만든다. (보안 프로그램 때문에 임시 폴더를 거친다)"""
    temporary_paths: list[tuple[Path, int]] = []

    hwp = Hwp(new=True, visible=False, register_module=True)
    try:
        hwp.open(str(hwp_path))
        page_count = hwp.PageCount
        for page_index in range(page_count):
            bitmap_path = Path(tempfile.gettempdir()) / f"pv_{uuid.uuid4().hex}.bmp"
            hwp.create_page_image(
                str(bitmap_path), pgno=page_index,
                resolution=PREVIEW_RESOLUTION_IN_DPI, format="bmp",
            )
            temporary_paths.append((bitmap_path, page_index))
    finally:
        hwp.quit()

    saved: list[Path] = []
    for bitmap_path, page_index in temporary_paths:
        if not bitmap_path.exists():
            continue
        output_path = hwp_path.with_name(f"{hwp_path.stem}_미리보기_{page_index + 1}쪽.png")
        with Image.open(bitmap_path) as bitmap:
            bitmap.convert("RGB").save(output_path)
        bitmap_path.unlink(missing_ok=True)
        saved.append(output_path)

    return saved


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python spike/render_hwp.py <한글파일경로>")
        sys.exit(1)

    target = Path(sys.argv[1]).resolve()
    if not target.exists():
        print(f"파일이 없습니다: {target}")
        sys.exit(1)

    for image_path in render_all_pages(target):
        print(f"  {image_path}")
