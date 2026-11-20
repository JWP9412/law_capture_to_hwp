import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ctypes
from ctypes import wintypes
from PIL import Image
from ui.app_window import AppWindow

PW_RENDERFULLCONTENT = 2
user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

SAMPLE = open("spike/_shot_design.py", encoding="utf-8").read()  # noop

text = """공동주택관리법
[시행 2026. 7. 1.] [법률 제21447호, 2026. 3. 5., 타법개정]

제3조(국가 등의 의무) ① 국가 및 지방자치단체는 공동주택의 관리에 관한 정책을 수립ㆍ시행할 때에는 다음 각 호의 사항을 위하여 노력하여야 한다. <개정 2025. 12. 2.>
1. 공동주택에 거주하는 입주자등이 쾌적하고 살기 좋은 주거생활을 할 수 있도록 할 것
2. 공동주택이 투명하고 체계적이며 평온하게 관리될 수 있도록 할 것
3. 안전사고를 예방하고 재해 및 재난 등으로부터 입주자등을 보호하기 위하여 공동주택이 안전하고 효율적으로 관리될 수 있도록 할 것
4. 공동주택의 관리와 관련한 산업이 건전한 발전을 꾀할 수 있도록 할 것
② 관리주체는 공동주택을 효율적이고 안전하게 관리하여야 한다.
③ 입주자등은 공동체 생활의 질서가 유지될 수 있도록 이웃을 배려하고 관리주체의 업무에 협조하여야 한다.
"""

out = Path("docs/mockup/프로그램_적용후.png")

def grab_window(hwnd, width, height):
    hwndDC = user32.GetWindowDC(hwnd)
    mfcDC = gdi32.CreateCompatibleDC(hwndDC)
    saveBitMap = gdi32.CreateCompatibleBitmap(hwndDC, width, height)
    gdi32.SelectObject(mfcDC, saveBitMap)
    result = user32.PrintWindow(hwnd, mfcDC, PW_RENDERFULLCONTENT)
    bmpinfo = {
        "bmWidth": width,
        "bmHeight": height,
    }
    # BITMAPINFOHEADER
    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", wintypes.DWORD),
            ("biWidth", wintypes.LONG),
            ("biHeight", wintypes.LONG),
            ("biPlanes", wintypes.WORD),
            ("biBitCount", wintypes.WORD),
            ("biCompression", wintypes.DWORD),
            ("biSizeImage", wintypes.DWORD),
            ("biXPelsPerMeter", wintypes.LONG),
            ("biYPelsPerMeter", wintypes.LONG),
            ("biClrUsed", wintypes.DWORD),
            ("biClrImportant", wintypes.DWORD),
        ]
    class BITMAPINFO(ctypes.Structure):
        _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]
    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = width
    bmi.bmiHeader.biHeight = -height
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = 0
    buffer_len = width * height * 4
    buffer = ctypes.create_string_buffer(buffer_len)
    gdi32.GetDIBits(mfcDC, saveBitMap, 0, height, buffer, ctypes.byref(bmi), 0)
    gdi32.DeleteObject(saveBitMap)
    gdi32.DeleteDC(mfcDC)
    user32.ReleaseDC(hwnd, hwndDC)
    image = Image.frombuffer("RGB", (width, height), buffer, "raw", "BGRX", 0, 1)
    print("PrintWindow", result, image.getextrema(), flush=True)
    return image

w = AppWindow()
w.deiconify(); w.lift(); w.geometry("+80+40")
view = w._input_view
view._law_name_entry.set_text("공동주택관리법")
view._article_entry.insert(0, "3")
view.preview_view.show_article("제3조", text)
view.add_underline_phrase("안전하고 효율적으로 관리")

def take():
    from ui.widgets import RoundedCardShell

    def walk(widget):
        yield widget
        for child in widget.winfo_children():
            yield from walk(child)

    for widget in walk(w):
        if isinstance(widget, RoundedCardShell):
            widget._drawn_size = (0, 0)
            widget._redraw_background()
    w.update_idletasks()
    w.update()
    hwnd = ctypes.windll.user32.GetParent(w.winfo_id()) or w.winfo_id()
    width, height = w.winfo_width(), w.winfo_height()
    img = grab_window(hwnd, width, height)
    img.save(out)
    print("saved", out, flush=True)
    w.destroy()

w.after(1500, take)
w.mainloop()
