"""
전체 작업의 순서를 정하고 진행 상황을 알려주는 지휘자 역할.

이 파일은 '무엇을 어떤 순서로 할지' 만 안다.
법령을 어떻게 찾는지, PDF 를 어떻게 받는지, 한글을 어떻게 다루는지는 모른다.
그건 각각 law_source.py, law_pdf.py, hwp_insert.py 가 안다.

이렇게 나눠두면 "PDF 받는 게 이상해요" 같은 문제가 생겼을 때
law_pdf.py 한 파일만 보면 되고, 여기는 건드릴 필요가 없다.

오류 처리 방침:
  조문 하나가 실패해도 나머지는 계속 진행한다.
  급한 서면 마감에 하나 때문에 전부 멈추면 곤란하기 때문이다.
  실패한 것은 결과에 모아서 돌려주고, 화면이 "무엇이 왜 안 됐는지" 를 보여준다.
  예외를 잡는 곳은 이 파일 한 군데뿐이다.
"""
from collections.abc import Callable
from enum import Enum
from pathlib import Path

import config
from core import annotate, version_series
from core.article_number import article_numbers_as_key
from core.errors import LawCaptureError
from core.hwp_insert import PictureInsertion, open_hwp_document
from core.law_pdf import open_law_site_browser
from core.models import (
    ArticleCaptureJob,
    ArticleCaptureTask,
    CapturedArticle,
    CaptureFailure,
    CaptureRunResult,
)


class WorkStage(Enum):
    """한 조문을 처리하는 동안 거치는 단계들. 화면에 '지금 뭐 하는 중' 을 보여줄 때 쓴다."""

    DOWNLOADING_PDF = "조문 내려받는 중"
    DRAWING_UNDERLINE = "밑줄 긋고 그림 만드는 중"
    INSERTING_INTO_DOCUMENT = "한글 문서에 넣는 중"
    FINISHED = "완료"
    FAILED = "실패"


# 진행 상황을 바깥(화면)에 알려줄 때 부르는 함수의 모양.
# (몇 번째 작업인지, 전체 몇 개인지, 무슨 작업인지, 어느 단계인지, 덧붙일 말)
ProgressReporter = Callable[[int, int, ArticleCaptureTask, WorkStage, str], None]


def _report_nothing(*_) -> None:
    """진행 상황을 알려줄 곳이 없을 때 쓰는 빈 함수. (커맨드라인 실행 등)"""


def run_capture_jobs(
    jobs: list[ArticleCaptureJob],
    result_hwp_path: Path,
    report_progress: ProgressReporter = _report_nothing,
) -> CaptureRunResult:
    """
    담아둔 작업들을 순서대로 처리해 한글 문서 하나를 만든다.

    작업 하나가 실패해도 멈추지 않는다.
    끝까지 진행한 뒤 성공한 것과 실패한 것을 함께 돌려준다.
    """
    tasks = _expand_all_jobs_into_tasks(jobs)
    result = CaptureRunResult()

    source_document_path = jobs[0].target_hwp_path if jobs else None
    working_directory = config.OUTPUT_DIRECTORY / "작업중"

    with open_law_site_browser(working_directory) as browser, open_hwp_document(
        source_document_path, result_hwp_path
    ) as editor:
        # 조문마다 '바로 앞 개정본의 본문' 을 따로 기억한다.
        # 제1조와 제7조(또는 서로 다른 조문 조합)를 섞어서 비교하면 안 된다.
        previous_body_text_by_article: dict[tuple, str] = {}

        for task_index, task in enumerate(tasks, start=1):
            try:
                article_key = article_numbers_as_key(task.article_numbers)
                captured = _capture_one_article(
                    task,
                    browser,
                    working_directory,
                    previous_body_text_by_article.get(article_key, ""),
                )
                # 그림 번호는 파이썬이 세지 않는다. 한글 자동번호 필드가 맡는다.
                _insert_into_document(editor, captured)

                result.succeeded.append(captured)
                previous_body_text_by_article[article_key] = (
                    captured.article_body_text
                )
                report_progress(task_index, len(tasks), task, WorkStage.FINISHED, "")

            except LawCaptureError as error:
                # 우리가 예상한 종류의 문제. 이 작업만 건너뛰고 계속 간다.
                result.failed.append(CaptureFailure(task, error))
                report_progress(task_index, len(tasks), task, WorkStage.FAILED, str(error))

    result.result_hwp_path = result_hwp_path
    return result


def _expand_all_jobs_into_tasks(
    jobs: list[ArticleCaptureJob],
) -> list[ArticleCaptureTask]:
    """담아둔 조건들을 실제 작업 목록으로 펼친다. (조문 × 개정본)"""
    tasks: list[ArticleCaptureTask] = []
    for job in jobs:
        tasks.extend(version_series.expand_into_tasks(job))
    return tasks


def _capture_one_article(
    task: ArticleCaptureTask,
    browser,
    working_directory: Path,
    previous_body_text: str,
) -> CapturedArticle:
    """
    조문 하나를 내려받아 밑줄을 긋고 그림으로 만든다.

    조문이 길면 PDF 가 여러 쪽이 되고, 그림도 쪽 수만큼 나온다.
    (「주택법」 제2조처럼 3쪽까지 가는 조문이 드물지 않다)
    """
    pdf_path = browser.download_article_pdf(task.version, task.article_numbers)

    first_image_path = working_directory / f"{pdf_path.stem}.png"
    image_paths = annotate.underline_and_capture(
        pdf_path, task.underline_phrases, first_image_path
    )

    body_text = annotate.extract_article_body_text(pdf_path)

    return CapturedArticle(
        task=task,
        pdf_path=pdf_path,
        image_paths=image_paths,
        article_body_text=body_text,
        comparison=version_series.compare_article_text(body_text, previous_body_text),
    )


def _insert_into_document(editor, captured: CapturedArticle) -> None:
    """
    만들어진 그림들을 한글 문서에 캡션과 함께 차례로 넣는다.

    조문이 길면 그림이 여러 장이다. 이때 캡션에 '(1/3)' 처럼 몇 번째 쪽인지
    적어 두어야, 서면을 읽는 사람이 뒤에 더 있다는 것을 알 수 있다.

    '[그림 N]' 번호는 build_caption 이 만들지 않는다.
    한글이 캡션에 넣는 자동번호 필드를 그대로 쓰기 때문이다.
    """
    total_pages = len(captured.image_paths)

    for page_number, image_path in enumerate(captured.image_paths, start=1):
        caption = None
        if captured.task.should_add_caption:
            caption = version_series.build_caption(
                captured.task,
                captured.comparison,
                page_number=page_number,
                total_pages=total_pages,
            )
        editor.insert_picture_with_caption(
            PictureInsertion(
                image_path=image_path,
                caption=caption,
                insertion_mode=captured.task.insertion_mode,
                placeholder=_build_placeholder(captured.task),
                should_add_border=captured.task.should_add_border,
            )
        )


def _build_placeholder(task: ArticleCaptureTask) -> str:
    """문서에서 찾을 표시 문구를 만든다. (플레이스홀더 방식으로 넣을 때만 쓰인다)"""
    return config.PLACEHOLDER_PATTERN.format(
        law_name=task.version.law_name,
        effective_date=task.version.effective_date,
        article_label=task.article_label,
    )


def build_result_file_path(source_hwp_path: Path) -> Path:
    """
    결과를 저장할 파일 이름을 정한다.

    원본은 절대 덮어쓰지 않는다. 결과가 마음에 들지 않아도
    원래 문서는 그대로 남아 있어야 하기 때문이다.
    """
    return source_hwp_path.with_name(
        f"{source_hwp_path.stem}{config.RESULT_FILE_SUFFIX}{source_hwp_path.suffix}"
    )
