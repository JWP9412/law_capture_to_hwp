"""
프로그램 시작점.

이 파일이 하는 일은 창을 띄우는 것뿐이다.
법령을 찾거나, PDF 를 내려받거나, 한글을 다루는 코드는 여기 한 줄도 없다.
그 일들은 core 폴더가, 화면은 ui 폴더가 맡는다.
"""
from ui.app_window import AppWindow


def main() -> None:
    AppWindow().mainloop()


if __name__ == "__main__":
    main()
