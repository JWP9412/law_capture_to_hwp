"""
화면 없이 명령 한 줄로 전체 과정을 돌려보는 도구.

화면(창)을 만들기 전에 안쪽 기능이 제대로 도는지 확인하는 용도이고,
나중에도 여러 건을 자동으로 처리하고 싶을 때 쓸 수 있다.

사용 예:

  기간 안의 개정본 전부를 캡처
    python run_from_command_line.py --name 하자판정기준 --from 2024-01-01 --to 2026-12-31 ^
        --article 1 --underline "제1조(목적) 이 기준은" --out 결과.hwp

  특정 시점의 판 하나만 캡처
    python run_from_command_line.py --name 하자판정기준 --date 2025-06-01 ^
        --article 1 --underline "제1조(목적) 이 기준은" --out 결과.hwp

  조문마다 다른 문구에 밑줄 치기
    --underline 은 바로 앞의 --article 에 적용된다. 조문별로 이어서 쓰면 된다.
    python run_from_command_line.py --name 하자판정기준 --date 2025-06-01 ^
        --article 1 --underline "제1조(목적) 이 기준은" ^
        --article 7 --underline "균열 폭이 0.3mm 이상인 경우" --out 결과.hwp
"""
import argparse
import sys
from datetime import date, datetime
from pathlib import Path

import config
from core import pipeline
from core.article_number import parse_article_numbers
from core.errors import LawCaptureError
from core.law_source import (
    DatePeriod,
    find_version_effective_on,
    find_versions_effective_between,
    search_laws,
)
from core.models import ArticleCaptureJob
from core.pipeline import WorkStage


def parse_date(text: str) -> date:
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError(f"날짜는 2025-06-01 형식으로 넣어주세요: '{text}'")


class CollectArticleAction(argparse.Action):
    """--article 을 만나면 새 조문을 목록에 추가한다. (예: 1 / 1-3 / 32의2)"""

    def __call__(self, parser, namespace, value, option_string=None):
        try:
            article_numbers = parse_article_numbers(value)
        except ValueError as error:
            parser.error(str(error))
        namespace.articles.append(
            {"article_numbers": article_numbers, "underline_phrases": []}
        )


class CollectUnderlineAction(argparse.Action):
    """
    --underline 을 만나면 바로 앞의 --article 에 그 문구를 붙인다.

    조문마다 밑줄 칠 문구가 다르기 때문에 이렇게 짝을 지어 받는다.
    (제7조에 제1조용 문구를 적용하면 당연히 못 찾는다)
    """

    def __call__(self, parser, namespace, value, option_string=None):
        if not namespace.articles:
            parser.error("--underline 은 --article 다음에 써야 합니다")
        namespace.articles[-1]["underline_phrases"].append(value)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="법령 조문을 캡처해 한글 문서에 넣습니다",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.set_defaults(articles=[])
    parser.add_argument("--name", required=True, help="법령·고시 이름 (일부만 넣어도 됩니다)")
    parser.add_argument("--date", type=parse_date, help="이 시점에 시행 중이던 판 하나만")
    parser.add_argument("--from", dest="period_start", type=parse_date, help="기간 시작")
    parser.add_argument("--to", dest="period_end", type=parse_date, help="기간 끝")
    parser.add_argument("--article", action=CollectArticleAction,
                        help="조문 번호. 예: 1 / 1,2 / 1-3 / 32의2. 여러 번 쓸 수 있습니다")
    parser.add_argument("--underline", action=CollectUnderlineAction,
                        help="바로 앞 --article 에 밑줄 칠 문구")
    parser.add_argument("--out", required=True, help="결과 한글 파일을 저장할 경로")
    parser.add_argument("--into", help="그림을 넣을 기존 한글 문서 (없으면 새 문서를 만듭니다)")
    return parser


def choose_versions(law, arguments):
    """지정한 방식(시점 하나 또는 기간)에 따라 대상 개정본을 고른다."""
    if arguments.period_start and arguments.period_end:
        return find_versions_effective_between(
            law, DatePeriod(arguments.period_start, arguments.period_end)
        )

    reference_date = arguments.date or date.today()
    return [find_version_effective_on(law, reference_date)]


def show_progress(
    task_index: int, total_count: int, task, stage: WorkStage, detail: str
) -> None:
    mark = "완료" if stage is WorkStage.FINISHED else "실패"
    line = f"  [{task_index}/{total_count}] {task} .. {mark}"
    print(f"{line}\n        {detail}" if detail else line, flush=True)


def main() -> int:
    parser = build_argument_parser()
    arguments = parser.parse_args()

    if not arguments.articles:
        parser.error("--article 을 하나 이상 지정해 주세요")

    try:
        law = search_laws(arguments.name)[0]
        print(f"찾은 법령: {law}")

        versions = choose_versions(law, arguments)
        print(f"대상 개정본 {len(versions)}개 (오래된 순):")
        for version in versions:
            print(f"    {version}")
    except LawCaptureError as error:
        print(f"[중단] {error}")
        return 1

    output_path = Path(arguments.out).resolve()

    # target_hwp_path 는 '그림을 넣을 기존 문서' 를 뜻한다.
    # --into 를 주지 않으면 새 문서를 만들어 --out 위치에 저장한다.
    # (--out 을 여기에 넣으면 아직 만들어지지도 않은 파일을 열려고 해서 실패한다)
    source_path = Path(arguments.into).resolve() if arguments.into else None
    if source_path is not None and not source_path.is_file():
        print(f"[중단] --into 로 준 파일이 없습니다: {source_path}")
        return 1

    jobs = [
        ArticleCaptureJob(
            law_name=law.law_name,
            target_versions=versions,
            article_numbers=article["article_numbers"],
            underline_phrases=article["underline_phrases"],
            target_hwp_path=source_path,
        )
        for article in arguments.articles
    ]

    expected_figures = sum(job.expected_figure_count for job in jobs)
    print(f"\n만들 그림 {expected_figures}장 (조문 {len(jobs)}개 × 개정본 {len(versions)}개)\n")

    result = pipeline.run_capture_jobs(jobs, output_path, show_progress)

    print(f"\n{result.summary_for_display}")
    for failure in result.failed:
        print(f"  x {failure.message_for_display}")

    if result.succeeded:
        print(f"\n결과 파일: {result.result_hwp_path}")
    return 0 if not result.has_any_failure else 2


if __name__ == "__main__":
    config.OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    sys.exit(main())
