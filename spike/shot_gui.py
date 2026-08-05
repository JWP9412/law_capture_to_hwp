"""
개편된 GUI를 눈으로 확인하기 위한 스크린샷 스크립트.

한글/브라우저를 켜지 않고 창만 띄운 뒤, 잠깐 기다렸다 화면 이미지를 저장한다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ui.app_window import AppWindow

try:
    from PIL import ImageGrab
except ImportError as error:  # pragma: no cover - 현장 환경 의존
    raise SystemExit(
        "Pillow가 없어 스크린샷을 찍을 수 없습니다. `pip install pillow` 후 다시 실행해 주세요."
    ) from error


def main() -> int:
    output_path = Path("spike_out") / "gui.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    window = AppWindow()
    window.update_idletasks()
    window.update()

    # 창이 완전히 그려진 뒤 촬영해야 빈 화면이 저장되지 않는다.
    window.after(900, lambda: _capture(window, output_path))
    window.after(1200, window.destroy)
    window.mainloop()

    print(f"[저장됨] {output_path.resolve()}")
    return 0


def _capture(window: AppWindow, output_path: Path) -> None:
    left = window.winfo_rootx()
    top = window.winfo_rooty()
    right = left + window.winfo_width()
    bottom = top + window.winfo_height()
    image = ImageGrab.grab(bbox=(left, top, right, bottom))
    image.save(output_path)


if __name__ == "__main__":
    raise SystemExit(main())
