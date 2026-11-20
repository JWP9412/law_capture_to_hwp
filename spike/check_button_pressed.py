"""버튼 pressed 스타일이 등록됐는지·색이 구분되는지 확인. 한글은 안 켠다."""
from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ui import theme
from ui.rounded_shapes import kept_image_count

root = tk.Tk()
root.withdraw()
theme.apply_theme(root)
style = ttk.Style(root)

elements = set(style.element_names())
for name in ("Law.Button.border", "Law.Primary.border", "Law.Toggle.border"):
    status = "OK" if name in elements else "MISSING"
    print(f"element {name}: {status}")
    assert name in elements, name

for sty in ("TButton", "Primary.TButton", "Toggle.TCheckbutton"):
    bg_map = style.map(sty, "background")
    pressed_vals = [pair[-1] for pair in bg_map if "pressed" in str(pair[0])]
    print(f"map {sty} background: {bg_map}")
    print(f"  pressed colors: {pressed_vals}")
    assert pressed_vals, f"{sty} map 에 pressed 없음"

print("colors:")
print(
    f"  primary normal={theme.ACCENT_BLUE} "
    f"active={theme.ACCENT_BLUE_ACTIVE} "
    f"pressed={theme.ACCENT_BLUE_PRESSED}"
)
print(
    f"  secondary pressed bg={theme.BUTTON_PRESSED_BACKGROUND} "
    f"border={theme.BUTTON_PRESSED_BORDER}"
)
assert theme.ACCENT_BLUE != theme.ACCENT_BLUE_ACTIVE
assert theme.ACCENT_BLUE_ACTIVE != theme.ACCENT_BLUE_PRESSED
assert theme.ACCENT_BLUE != theme.ACCENT_BLUE_PRESSED
assert theme.BUTTON_PRESSED_BACKGROUND not in (
    theme.CARD_BACKGROUND,
    theme.HOVER_BACKGROUND,
    theme.WINDOW_BACKGROUND,
)
print(f"kept images: {kept_image_count()}")
print("PASS: pressed colors distinct + maps present")
root.destroy()
