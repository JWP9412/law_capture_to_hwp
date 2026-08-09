"""
실행.bat 이 호출하는 진입 파일.

파일 이름을 영문(run)으로 둔 이유:
Windows 배치 파일(.bat)은 한글 경로·한글 파일명을
깨뜨리는 경우가 많아서, bat → run.pyw 만 ASCII 로 맞춘다.
"""
from launch import launch

launch()
