"""
한글 작업이 어느 단계에서 멈추는지 하나씩 확인한다.

출력이 바로 보이도록 매번 흘려보내고(flush), 각 단계가 끝날 때마다
한글이 몇 개 떠 있는지 함께 찍는다. 멈추면 어디까지 갔는지 알 수 있다.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pythoncom

import config
from core.hwp_insert import _running_hwp_instance_names

SAMPLE_IMAGE = config.OUTPUT_DIRECTORY / "check_annotate" / (
    "공동주택 하자의 조사, 보수비용 산정 및 하자판정기준_2025-02-03_제1조.png"
)


def step(message: str) -> None:
    count = len(_running_hwp_instance_names())
    print(f"  [{time.strftime('%H:%M:%S')}] {message}  (한글 {count}개)", flush=True)


pythoncom.CoInitialize()
step("시작")

from pyhwpx import Hwp

step("pyhwpx 불러옴")

hwp = Hwp(new=True, visible=False, register_module=True)
step("한글 켬")

print(f"          문서 수: {hwp.XHwpDocuments.Count}", flush=True)

hwp.insert_text("시험")
step("글자 넣음")

if SAMPLE_IMAGE.exists():
    hwp.insert_picture(str(SAMPLE_IMAGE), embedded=True, sizeoption=1, width=155.0, height=59.0)
    step("그림 넣음")
else:
    print("          그림 파일이 없어 건너뜀", flush=True)

document = hwp.XHwpDocuments.Active_XHwpDocument
step("현재 문서 잡음")

document.Close(False)
step("문서 닫음")

hwp.quit()
step("한글 끔")

print("\n모든 단계 통과", flush=True)
