"""
우리 작업이 남의 한글 인스턴스를 건드리는지 정밀하게 추적한다.

사용자가 실제로 작업 중인 문서가 있을 수 있으므로,
이 진단은 아무것도 종료하지 않는다. 보기만 한다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pythoncom


def hwp_instance_names() -> list[str]:
    """지금 떠 있는 한글 인스턴스들의 이름표."""
    context = pythoncom.CreateBindCtx(0)
    found = []
    for moniker in pythoncom.GetRunningObjectTable().EnumRunning():
        try:
            name = moniker.GetDisplayName(context, moniker)
        except Exception:
            continue
        if name.startswith("!HwpObject."):
            found.append(name)
    return sorted(found)


def describe(label: str, hwp) -> None:
    """그 인스턴스가 아직 살아 있는지, 문서가 몇 개인지."""
    try:
        print(f"   {label}: 살아있음, 문서 {hwp.XHwpDocuments.Count}개")
    except Exception as error:
        print(f"   {label}: 접근 불가 ({type(error).__name__})")


pythoncom.CoInitialize()

print("=== 시작 시점 ===")
at_start = hwp_instance_names()
print(f"   한글 인스턴스: {at_start}")

print("\n=== '사용자 문서' 역할 한글을 띄운다 ===")
from pyhwpx import Hwp

user_hwp = Hwp(new=True, visible=True, register_module=True)
user_hwp.XHwpDocuments.Add(0)
user_hwp.insert_text("건드리면 안 되는 내용")

after_user = hwp_instance_names()
print(f"   한글 인스턴스: {after_user}")
print(f"   새로 생긴 것: {[n for n in after_user if n not in at_start]}")
describe("사용자 한글", user_hwp)

print("\n=== 우리 편집기를 연다 (그림은 안 넣고 열고 닫기만) ===")
from core.hwp_insert import HwpDocumentEditor

editor = HwpDocumentEditor(None, Path("out/무시.hwp"))
editor.__enter__()

after_open = hwp_instance_names()
print(f"   한글 인스턴스: {after_open}")
print(f"   새로 생긴 것: {[n for n in after_open if n not in after_user]}")
print(f"   우리가 판단한 '이미 떠 있었다': {editor._was_hwp_already_running}")
describe("사용자 한글", user_hwp)
describe("우리 한글", editor._hwp)

print("\n=== 우리 편집기를 닫는다 (오류인 척해서 저장은 건너뜀) ===")
editor.__exit__(RuntimeError, None, None)

after_close = hwp_instance_names()
print(f"   한글 인스턴스: {after_close}")
print(f"   사라진 것: {[n for n in after_open if n not in after_close]}")
describe("사용자 한글", user_hwp)

print("\n=== 사용자 문서 내용 확인 ===")
try:
    user_hwp.XHwpDocuments.Item(0).SetActive_XHwpDocument()
    user_hwp.MoveDocBegin()
    user_hwp.Run("MoveSelDocEnd")
    print(f"   읽은 내용: {(user_hwp.get_selected_text() or '').strip()[:40]!r}")
except Exception as error:
    print(f"   읽기 실패: {type(error).__name__}")

print("\n=== 시험용 한글만 정리 ===")
try:
    user_hwp.clear(option=1)
    user_hwp.quit()
    print("   정리 완료")
except Exception as error:
    print(f"   정리 중 문제: {type(error).__name__}")

print(f"\n최종 한글 인스턴스: {hwp_instance_names()}")
print(f"(시작 시점: {at_start})")
