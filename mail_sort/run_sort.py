"""
받아 둔 메일 자료를 폴더로 나눈다.

쓰는 법 (명령 프롬프트에서 이 프로젝트 폴더로 이동한 뒤):

  python -X utf8 mail_sort/run_sort.py --source "받은파일" --output "분류결과"

미리 보기만 할 때 (파일을 복사하지 않음):

  python -X utf8 mail_sort/run_sort.py --source "받은파일" --output "분류결과" --dry-run

시공사 이름은 mail_sort/default_rules.json 의 contractors 에 추가한다.
예시건설 을 지우고, 실제 회사 이름과 파일 이름에 들어가는 말을 적으면 된다.

KT 마이오피스 웹 화면에서 자동으로 첨부를 받는 기능은 아직 없다.
비밀번호를 프로그램에 저장하지 않기 위해서다.
지금은 포털에서 파일을 한 폴더에 저장한 다음 이 프로그램을 실행한다.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mail_sort.models import SortOptions
from mail_sort.rules_file import MailSortError, load_sort_rules
from mail_sort.sort_files import sort_saved_mail_files


def main() -> int:
    parser = argparse.ArgumentParser(
        description="받아 둔 메일 자료를 시공사, 소송 단계, 날짜, 서류 종류 폴더로 나눈다."
    )
    parser.add_argument("--source", required=True, help="메일에서 받아 둔 파일이 있는 폴더")
    parser.add_argument("--output", required=True, help="나눈 결과를 넣을 폴더")
    parser.add_argument(
        "--rules",
        default=str(Path(__file__).resolve().parent / "default_rules.json"),
        help="분류 기준 JSON. 생략하면 mail_sort/default_rules.json",
    )
    parser.add_argument(
        "--move",
        action="store_true",
        help="복사 대신 원본을 결과 폴더로 옮긴다. 기본은 복사다.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실제로 복사하지 않고 어디로 갈지만 보여 준다.",
    )
    args = parser.parse_args()

    try:
        rules = load_sort_rules(Path(args.rules))
        options = SortOptions(
            source_directory=Path(args.source),
            output_directory=Path(args.output),
            rules=rules,
            is_copy=not args.move,
            is_dry_run=args.dry_run,
        )
        results = sort_saved_mail_files(options)
    except MailSortError as error:
        print(str(error))
        return 1

    if not results:
        print("나눌 파일이 없습니다. 받아 둔 폴더에 파일이 있는지 확인하세요.")
        return 0

    for result in results:
        print(result.message)
        for note in result.notes:
            print(f"  - {note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
