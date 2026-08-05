"""
더블클릭으로 프로그램을 켜는 파일.

확장자가 .pyw 인 이유: 검은 명령창 없이 프로그램 창만 뜨게 하기 위해서다.
(.py 로 두면 뒤에 검은 창이 하나 같이 뜬다)
"""
import sys
from pathlib import Path

# 이 파일이 있는 폴더를 기준으로 나머지 코드를 찾도록 한다.
# 바탕화면 어디에 두고 더블클릭해도 동작하게 하기 위한 것이다.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from main import main

main()
