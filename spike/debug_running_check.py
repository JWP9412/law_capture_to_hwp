"""한글이 이미 떠 있는지 판단하는 부분이 제대로 도는지 진단한다."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pythoncom

from core.hwp_insert import _is_hwp_already_running


def list_running_program_names() -> list[str]:
    """윈도우가 들고 있는 '실행 중인 프로그램 이름표' 를 전부 본다."""
    context = pythoncom.CreateBindCtx(0)
    names = []
    for moniker in pythoncom.GetRunningObjectTable().EnumRunning():
        try:
            names.append(moniker.GetDisplayName(context, moniker))
        except Exception as error:
            names.append(f"(읽기실패 {type(error).__name__})")
    return names


pythoncom.CoInitialize()

print("=== 한글을 띄우기 전 ===")
before = list_running_program_names()
print(f"  이름표 {len(before)}개")
print(f"  한글로 보이는 것: {[n for n in before if 'wp' in n.lower()]}")
print(f"  판단 결과: {_is_hwp_already_running()}")

print("\n=== 한글을 띄운 뒤 ===")
from pyhwpx import Hwp

hwp = Hwp(new=True, visible=True, register_module=True)
hwp.XHwpDocuments.Add(0)
hwp.insert_text("진단용 문서")

after = list_running_program_names()
print(f"  이름표 {len(after)}개")
print(f"  한글로 보이는 것: {[n for n in after if 'wp' in n.lower()]}")
print(f"  새로 생긴 것: {[n for n in after if n not in before]}")
print(f"  판단 결과: {_is_hwp_already_running()}")
print(f"  열린 문서 수: {hwp.XHwpDocuments.Count}")

print("\n=== 정리 ===")
try:
    hwp.clear(option=1)
    hwp.quit()
    print("  정리 완료")
except Exception as error:
    print(f"  정리 중 문제: {type(error).__name__}")
