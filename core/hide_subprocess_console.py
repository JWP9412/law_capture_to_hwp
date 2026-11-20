"""
Windows 에서 자식 프로그램이 검은 명령창(CMD)을 띄우지 않게 한다.

왜 필요한가
-----------
프로그램은 pythonw(.pyw)로 켜서 검은 창이 없어야 한다.
그런데 조문 PDF 를 받을 때 Playwright 가 뒤에서 node.exe 와 Chromium 을 켠다.
이 둘은 '콘솔 프로그램'이라, 부모(pythonw)에 콘솔이 없으면 Windows 가
자식용 검은 명령창을 새로 만들어 버린다.
→ 캡처를 누를 때마다 CMD 창이 깜빡이거나 남는 직접 원인이다.

Playwright 쪽에 "창 숨김" 전용 옵션이 없어서,
자식 프로세스를 만드는 subprocess.Popen 기본값에
CREATE_NO_WINDOW 플래그만 조심히 덧붙인다.

왜 전역으로 한 번만 덧씌우는가
------------------------------
Playwright 는 우리가 직접 Popen 을 부르지 않고 라이브러리 안에서 부른다.
그래서 그 경로만 골라 고칠 수 없고, Popen 기본 동작에 플래그를 더하는
방식이 가장 안전하다. 같은 프로세스에서 두 번 적용하지 않도록 가드를 둔다.
Windows 가 아니면 아무 것도 하지 않는다.
"""
from __future__ import annotations

import subprocess
import sys

_is_patch_applied = False


def apply_no_console_window_for_subprocesses() -> None:
    """
    이후 이 프로세스에서 뜨는 자식 콘솔 창을 숨긴다.

    이미 적용했으면 다시 덮지 않는다.
    호출부가 creationflags 를 이미 준 경우에는 그 값을 유지한 채
    CREATE_NO_WINDOW 비트만 추가로 켠다.
    """
    global _is_patch_applied
    if _is_patch_applied or sys.platform != "win32":
        return

    original_popen = subprocess.Popen
    no_window_flag = subprocess.CREATE_NO_WINDOW

    class NoConsolePopen(original_popen):
        """CREATE_NO_WINDOW 를 기본으로 켜는 Popen 대체품."""

        def __init__(self, *args, **kwargs):
            # 이미 플래그가 있어도 OR 로 합친다.
            # (다른 라이브러리가 CREATE_NEW_CONSOLE 등을 켠 경우도 창만 숨김)
            existing_flags = kwargs.get("creationflags", 0)
            kwargs["creationflags"] = existing_flags | no_window_flag

            # STARTF_USESHOWWINDOW 는 CREATE_NO_WINDOW 와 겹쳐도 해가 없고,
            # 일부 구형 Windows 에서 콘솔 깜빡임을 더 줄여 준다.
            startup_info = kwargs.get("startupinfo")
            if startup_info is None:
                startup_info = subprocess.STARTUPINFO()
                kwargs["startupinfo"] = startup_info
            startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            super().__init__(*args, **kwargs)

    subprocess.Popen = NoConsolePopen
    _is_patch_applied = True
