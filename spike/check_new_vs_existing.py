"""
'대상 한글 파일' 을 비웠을 때와 골랐을 때가 모두 제대로 되는지 확인한다.

실제로 문제가 있던 부분이다.
칸을 비우면 새 문서를 만들어야 하는데, 빈 경로를 한글에게 넘겨
'string index out of range' 오류가 났었다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from core.hwp_insert import PictureInsertion, open_hwp_document
from core.errors import HwpAutomationError
from ui.app_window import _decide_result_path

RESULT_DIRECTORY = config.OUTPUT_DIRECTORY / "check_new_doc"
SAMPLE_IMAGE = config.OUTPUT_DIRECTORY / "check_annotate" / (
    "공동주택 하자의 조사, 보수비용 산정 및 하자판정기준_2025-02-03_제1조.png"
)


def report(label: str, is_ok: bool, detail: str = "") -> bool:
    print(f"  [{'OK  ' if is_ok else '실패'}] {label}" + (f"  -- {detail}" if detail else ""))
    return is_ok


all_passed = True

print("=== 1. 저장 위치 정하기 ===")
new_document_path = _decide_result_path(None)
all_passed &= report("파일을 안 골랐을 때", new_document_path.name.endswith(".hwp"),
                     str(new_document_path))

existing = Path(r"C:\어딘가\준비서면.hwp")
result_for_existing = _decide_result_path(existing)
all_passed &= report("파일을 골랐을 때 원본을 안 덮어쓰는가",
                     result_for_existing != existing, result_for_existing.name)

print("\n=== 2. 새 문서 만들기 (칸을 비운 경우) ===")
if not SAMPLE_IMAGE.exists():
    print("  건너뜀: 먼저 check_annotate.py 를 실행하세요")
else:
    from config import InsertionMode

    made_path = RESULT_DIRECTORY / "새문서.hwp"
    made_path.unlink(missing_ok=True)
    with open_hwp_document(None, made_path) as editor:
        editor.insert_picture_with_caption(
            PictureInsertion(
                SAMPLE_IMAGE, "새 문서 만들기 시험", InsertionMode.APPEND_TO_END
            )
        )
    all_passed &= report("새 문서가 만들어졌는가", made_path.exists(),
                         f"{made_path.stat().st_size:,}바이트" if made_path.exists() else "없음")

    print("\n=== 3. 기존 문서에 넣기 ===")
    added_path = RESULT_DIRECTORY / "기존문서_캡처본.hwp"
    added_path.unlink(missing_ok=True)
    with open_hwp_document(made_path, added_path) as editor:
        editor.insert_picture_with_caption(
            PictureInsertion(
                SAMPLE_IMAGE, "기존 문서에 덧붙이기 시험", InsertionMode.APPEND_TO_END
            )
        )
    all_passed &= report("기존 문서를 읽어 새 파일로 저장했는가", added_path.exists())
    all_passed &= report("원본이 그대로 남아 있는가", made_path.exists())
    all_passed &= report("내용이 늘어났는가",
                         added_path.exists() and added_path.stat().st_size > made_path.stat().st_size,
                         f"{made_path.stat().st_size:,} -> {added_path.stat().st_size:,}바이트")

print("\n=== 4. 없는 파일을 지정했을 때 ===")
try:
    with open_hwp_document(Path(r"C:\없는폴더\없는파일.hwp"), RESULT_DIRECTORY / "버림.hwp"):
        pass
    all_passed &= report("알아듣기 쉬운 오류가 나는가", False, "오류 없이 통과함")
except HwpAutomationError as error:
    all_passed &= report("알아듣기 쉬운 오류가 나는가", True, str(error))

print("\n" + "=" * 58)
print("모든 확인 통과" if all_passed else "일부 확인 실패")
sys.exit(0 if all_passed else 1)
