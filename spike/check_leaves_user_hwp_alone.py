"""
사용자가 쓰던 한글을 건드리지 않으면서, 우리가 켠 한글은 남기지 않는지 확인한다.

**둘 다 실제로 문제가 났던 부분이다.**
  - 남의 한글을 끔      -> 사용자가 작업하던 문서가 통째로 닫혔다
  - 우리 한글을 안 끔   -> 창 없는 한글이 실행할 때마다 하나씩 쌓였다

이 검증은 그 상황을 만들어 양쪽을 모두 확인한다.
프로세스를 강제로 종료하지 않는다. 우리가 켠 것만 얌전히 닫는다.
"""
import sys
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pythoncom

import config
from config import InsertionMode
from core.hwp_insert import PictureInsertion, _running_hwp_instance_names, open_hwp_document

RESULT_DIRECTORY = config.OUTPUT_DIRECTORY / "check_user_hwp"
SAMPLE_IMAGE = config.OUTPUT_DIRECTORY / "check_annotate" / (
    "공동주택 하자의 조사, 보수비용 산정 및 하자판정기준_2025-02-03_제1조.png"
)
USER_DOCUMENT_MARK = "건드리면 안 되는 내용"


def report(label: str, is_ok: bool, detail: str = "") -> bool:
    print(f"  [{'OK  ' if is_ok else '실패'}] {label}" + (f"  -- {detail}" if detail else ""))
    return is_ok


def close_quietly(hwp) -> None:
    """
    시험용으로 켠 한글을 조용히 닫는다.

    문서를 먼저 닫으면 문서가 0개가 되어 quit() 이 안 먹는다.
    반대로 저장하지 않은 채로 quit() 하면 '저장할까요' 창이 뜰 수 있다.

    그래서 임시 폴더에 한 번 저장해 '깨끗함' 상태로 만든 뒤,
    문서는 그대로 두고 바로 종료한다. (본 프로그램 _quit_hwp 와 같은 요령)
    """
    try:
        temporary_path = Path(tempfile.gettempdir()) / f"lawcapture_discard_{uuid.uuid4().hex}.hwp"
        hwp.save_as(str(temporary_path), format="HWP")
    except Exception:
        temporary_path = None

    try:
        hwp.quit()
    except Exception:
        pass

    if temporary_path is not None:
        temporary_path.unlink(missing_ok=True)


if not SAMPLE_IMAGE.exists():
    print(f"먼저 check_annotate.py 를 실행하세요. 없는 그림: {SAMPLE_IMAGE.name}")
    sys.exit(1)

pythoncom.CoInitialize()
all_passed = True

print("=" * 62)
print("사용자 한글은 건드리지 않고, 우리 한글은 남기지 않는지 확인")
print("=" * 62)

names_at_start = _running_hwp_instance_names()
print(f"\n시작 시점 한글: {len(names_at_start)}개")

print("\n1. '사용자 문서' 역할을 할 한글을 띄웁니다")
from pyhwpx import Hwp

# 창을 보이지 않게 띄운다. 검증 때문에 화면에 한글 창이 튀어나오면
# 사용자가 하던 일을 가리기 때문이다. 격리 확인에는 창이 필요 없다.
user_hwp = Hwp(new=True, visible=False, register_module=True)
user_hwp.insert_text(USER_DOCUMENT_MARK)
names_with_user = _running_hwp_instance_names()
document_count_of_user = user_hwp.XHwpDocuments.Count
print(f"   한글 {len(names_with_user)}개 (사용자 것 1개 늘어남), 그 안의 문서 {document_count_of_user}개")

print("\n2. 그 상태에서 우리 프로그램을 돌립니다")
result_path = RESULT_DIRECTORY / "동시실행시험.hwp"
result_path.unlink(missing_ok=True)
our_document_count = None
try:
    with open_hwp_document(None, result_path) as editor:
        # 우리 창에 문서가 몇 개 떠 있는지 본다.
        # 예전에는 딸려 온 '빈 문서 1' 위에 하나를 더 만들어 2개가 됐다.
        our_document_count = editor._hwp.XHwpDocuments.Count
        editor.insert_picture_with_caption(
            PictureInsertion(
                SAMPLE_IMAGE, "동시 실행 시험", InsertionMode.APPEND_TO_END
            )
        )
    print("   그림 넣기 완료")
except Exception as error:
    all_passed &= report("우리 작업이 끝났는가", False, f"{type(error).__name__}: {error}")

all_passed &= report("빈 문서를 하나만 쓰는가", our_document_count == 1,
                     f"우리 창의 문서 {our_document_count}개")

print("\n3. 사용자 한글이 무사한지 확인합니다")
try:
    user_hwp.XHwpDocuments.Item(0).SetActive_XHwpDocument()
    user_hwp.MoveDocBegin()
    user_hwp.Run("MoveSelDocEnd")
    kept_text = (user_hwp.get_selected_text() or "").strip()
    all_passed &= report("사용자 문서가 살아 있는가", True)
    all_passed &= report("내용이 그대로인가", USER_DOCUMENT_MARK in kept_text,
                         f"읽은 내용: {kept_text[:32]!r}")
except Exception as error:
    all_passed &= report("사용자 문서가 살아 있는가", False,
                         f"접근 불가 ({type(error).__name__})")

print("\n4. 우리가 켠 한글이 남지 않았는지 확인합니다")
names_after_run = _running_hwp_instance_names()
leftover = names_after_run - names_with_user
all_passed &= report("우리 한글이 정리됐는가", not leftover,
                     f"남은 것: {sorted(leftover)}" if leftover else "남은 것 없음")

all_passed &= report("결과 파일이 만들어졌는가", result_path.exists(),
                     f"{result_path.stat().st_size:,}바이트" if result_path.exists() else "없음")

print("\n5. 시험용으로 켠 한글만 정리합니다")
names_before_close = _running_hwp_instance_names()
print(f"   정리 직전: {sorted(names_before_close)}")
close_quietly(user_hwp)
import time
time.sleep(1.0)
names_at_end = _running_hwp_instance_names()
print(f"   최종 한글 {len(names_at_end)}개 (시작 시점 {len(names_at_start)}개)")
print(f"   최종 목록: {sorted(names_at_end)}")
print(f"   시작 목록: {sorted(names_at_start)}")
all_passed &= report("시험 전 상태로 돌아왔는가", names_at_end <= names_at_start,
                     f"남은 것: {sorted(names_at_end - names_at_start)}"
                     if names_at_end - names_at_start else "시작과 같거나 더 적음")

print("\n" + "=" * 62)
print("통과" if all_passed else "실패 — 위 목록을 보세요")
print("=" * 62)
sys.exit(0 if all_passed else 1)
