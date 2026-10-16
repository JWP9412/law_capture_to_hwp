"""
작업표시줄에 '이 창은 이런 프로그램이다' 를 알려주는 일을 한다.

왜 필요한가:
  실행 중인 창을 우클릭해 [작업 표시줄에 고정] 하면, Windows 는 그 창을
  '다시 켜는 방법' 을 창에서 읽어 바로가기를 만든다. 우리 창은 그 정보를
  알려주지 않으므로 Windows 가 창을 띄운 프로그램(pythonw.exe)을 그대로 쓴다.
  그러면 두 가지가 어긋난다.
    - 아이콘이 파이썬 기본 아이콘이 된다
    - 눌러도 pythonw.exe 만 실행되고 run.pyw 는 실행되지 않아 아무 일도 안 일어난다

  그래서 창에 세 가지를 적어 둔다.
    1) 다시 켜는 명령   (pythonw.exe "…\\run.pyw")
    2) 아이콘           (assets\\icon.ico)
    3) 표시 이름        (법령 조문 캡처)
  Windows 규칙상 이 값들은 앱 이름표(AppUserModelID)와 함께 있어야 인정된다.

실패해도 프로그램 실행에는 지장이 없다. (고정했을 때 아이콘이 어긋날 뿐이다)
"""
import ctypes
import sys
from pathlib import Path

APP_USER_MODEL_ID = "LawCaptureToHwp.App"
DISPLAY_NAME = "법령 조문 캡처"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ICON_PATH = PROJECT_ROOT / "assets" / "icon.ico"
LAUNCH_SCRIPT_PATH = PROJECT_ROOT / "run.pyw"


def _find_pythonw_path() -> Path:
    """
    창 없이 파이썬을 여는 실행 파일(pythonw.exe)의 위치를 찾는다.

    지금 프로그램을 연 파이썬 바로 옆의 pythonw.exe 를 쓴다.
    python.exe 로 켰더라도 다시 켤 때는 검은 창이 뜨지 않게 pythonw 를 가리킨다.
    """
    current = Path(sys.executable)
    candidate = current.with_name("pythonw.exe")
    return candidate if candidate.exists() else current


def _build_relaunch_command() -> str:
    return f'"{_find_pythonw_path()}" "{LAUNCH_SCRIPT_PATH}"'


def apply_taskbar_identity(window) -> None:
    """
    tkinter 창에 '다시 켜는 방법·아이콘·이름' 을 적어 둔다.

    창이 실제로 만들어진 뒤에 불러야 한다. (창 번호가 있어야 하므로)
    """
    try:
        from win32com.propsys import propsys, pscon

        window.update_idletasks()

        # tkinter 의 winfo_id() 는 안쪽 그림판 창이다.
        # 작업표시줄이 보는 것은 그것을 감싸는 바깥 창이므로 한 단계 올라간다.
        outer_window_handle = ctypes.windll.user32.GetParent(window.winfo_id())
        if not outer_window_handle:
            outer_window_handle = window.winfo_id()

        store = propsys.SHGetPropertyStoreForWindow(
            outer_window_handle, propsys.IID_IPropertyStore
        )
        for key, value in (
            (pscon.PKEY_AppUserModel_ID, APP_USER_MODEL_ID),
            (pscon.PKEY_AppUserModel_RelaunchCommand, _build_relaunch_command()),
            (pscon.PKEY_AppUserModel_RelaunchIconResource, f"{ICON_PATH},0"),
            (pscon.PKEY_AppUserModel_RelaunchDisplayNameResource, DISPLAY_NAME),
        ):
            store.SetValue(key, propsys.PROPVARIANTType(value))
        store.Commit()
    except Exception:
        pass
