"""
프로그램 창·작업표시줄에 쓸 아이콘(assets/icon.ico)을 만든다.

한 번 실행해서 파일을 만들어 두면 되는 스크립트다 (실행할 때마다 돌릴 필요 없음).
프로그램이 하는 일 — 조문에 빨간 밑줄을 긋는 것 — 을 그대로 아이콘에 담았다:
남색 문서 위에 흰 줄(글줄) 몇 개와 빨간 밑줄 하나.

여러 크기(16~256px)를 한 파일에 함께 담아야 작업표시줄·창 제목·Alt+Tab
어디서든 흐려지지 않는다.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = PROJECT_ROOT / "assets" / "icon.ico"

NAVY = (30, 39, 97, 255)
NAVY_DARK = (20, 27, 77, 255)
WHITE = (255, 255, 255, 255)
RED = (214, 69, 69, 255)
SIZES = (256, 128, 64, 48, 32, 16)


def draw_document_with_red_underline(size: int) -> Image.Image:
    """정사각형 캔버스에 '문서 + 빨간 밑줄' 그림을 그린다."""
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    margin = round(size * 0.12)
    corner_radius = round(size * 0.16)
    draw.rounded_rectangle(
        (margin, margin, size - margin, size - margin),
        radius=corner_radius,
        fill=NAVY,
        outline=NAVY_DARK,
        width=max(1, round(size * 0.02)),
    )

    line_left = margin + round(size * 0.18)
    line_right = size - margin - round(size * 0.18)
    line_height = max(1, round(size * 0.045))

    line_ys = [round(size * ratio) for ratio in (0.34, 0.46, 0.58)]
    for y in line_ys:
        draw.rounded_rectangle(
            (line_left, y, line_right, y + line_height),
            radius=line_height // 2,
            fill=WHITE,
        )

    # 마지막 줄 아래, 짧게 빨간 밑줄 — 이 프로그램의 상징
    underline_y = round(size * 0.72)
    underline_height = max(1, round(size * 0.06))
    underline_right = line_left + round((line_right - line_left) * 0.62)
    draw.rounded_rectangle(
        (line_left, underline_y, underline_right, underline_y + underline_height),
        radius=underline_height // 2,
        fill=RED,
    )

    return image


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    base = draw_document_with_red_underline(SIZES[0])
    frames = [base] + [
        base.resize((size, size), Image.LANCZOS) for size in SIZES[1:]
    ]
    base.save(
        OUTPUT_PATH,
        format="ICO",
        sizes=[(size, size) for size in SIZES],
    )
    print(f"저장됨: {OUTPUT_PATH} ({OUTPUT_PATH.stat().st_size:,} 바이트)")


if __name__ == "__main__":
    sys.exit(main())
