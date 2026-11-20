"""
캡처 실패를 파일에 남겨, 나중에 AI·직접 확인으로 피드백할 수 있게 한다.

왜 화면 메시지만으로 부족한가:
  밑줄 문구를 못 찾으면 그때는 고치고 넘어가기 바쁘다.
  며칠 뒤 '어떤 문구가 어느 판에서 실패했는지' 를 다시 모으려면
  기록이 있어야 한다. 그래서 out/실패기록/ 에 쌓아 둔다.

파일 두 가지:
  - 실패기록.jsonl  … 프로그램·AI가 다루기 쉬운 한 줄 한 건
  - 실패기록.md    … 사람이 읽고 '피드백' 칸에 메모하기 쉬운 글
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import config
from core.errors import UnderlinePhraseNotFoundError
from core.models import CaptureFailure

JSONL_FILE_NAME = "실패기록.jsonl"
MARKDOWN_FILE_NAME = "실패기록.md"
README_FILE_NAME = "읽는방법.txt"


def record_capture_failure(failure: CaptureFailure) -> Path:
    """
    실패한 작업 한 건을 실패기록 폴더에 덧붙인다.

    돌려주는 값은 기록이 쌓인 폴더 경로다. 화면에서 '기록 열기' 에 쓴다.
    """
    folder = config.FAILURE_FEEDBACK_DIRECTORY
    folder.mkdir(parents=True, exist_ok=True)
    _ensure_readme(folder)

    record = _build_record(failure)
    _append_jsonl(folder / JSONL_FILE_NAME, record)
    _append_markdown(folder / MARKDOWN_FILE_NAME, record)
    return folder


def record_capture_failures(failures: list[CaptureFailure]) -> Path | None:
    """
    한 번 실행에서 난 실패들을 모두 남긴다.

    실패가 없으면 None. 있으면 폴더 경로.
    """
    if not failures:
        return None
    folder = None
    for failure in failures:
        folder = record_capture_failure(failure)
    return folder


def _build_record(failure: CaptureFailure) -> dict:
    """화면에 보이는 내용 + 나중에 고칠 때 필요한 칸을 묶는다."""
    task = failure.task
    error = failure.error
    phrase = ""
    pdf_path = ""
    error_kind = type(error).__name__
    if isinstance(error, UnderlinePhraseNotFoundError):
        phrase = error.phrase
        pdf_path = str(error.pdf_path)
        error_kind = "underline_phrase_not_found"

    return {
        "recorded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "law_name": task.version.law_name,
        "article_label": task.article_label,
        "effective_date": task.version.effective_date.isoformat(),
        "effective_date_label": task.version.effective_date_label,
        "phrase": phrase,
        "error_kind": error_kind,
        "error_message": str(error),
        "pdf_path": pdf_path,
        "detail_page_url": task.version.detail_page_url,
        # 사람이 나중에 채우는 칸. AI·직접 확인 결과를 여기 적어도 된다.
        "feedback": "",
        "status": "open",
    }


def _append_jsonl(path: Path, record: dict) -> None:
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")


def _append_markdown(path: Path, record: dict) -> None:
    """
    사람이 읽기 쉬운 형태로 덧붙인다.

    '피드백' 줄을 비워 두어, 메모장에서 바로 적어 넣을 수 있게 한다.
    """
    is_new_file = not path.exists()
    lines: list[str] = []
    if is_new_file:
        lines.extend(
            [
                "# 캡처 실패 기록",
                "",
                "밑줄 문구를 못 찾았거나 캡처가 실패한 건을 모아 둔다.",
                "아래 **피드백** 칸에 고친 문구·원인·메모를 적으면 된다.",
                "",
            ]
        )

    phrase_line = record["phrase"] or "(해당 없음)"
    lines.extend(
        [
            # effective_date_label 에 이미 '시행 …' 이 들어 있다.
            f"## {record['recorded_at']} — {record['article_label']} "
            f"[{record['effective_date_label']}]",
            "",
            f"- 법령: {record['law_name']}",
            f"- 못 찾은 문구: `{phrase_line}`",
            f"- 안내: {record['error_message']}",
            f"- 원문: {record['detail_page_url']}",
            f"- PDF: {record['pdf_path'] or '(없음)'}",
            f"- 종류: {record['error_kind']}",
            "- 피드백: ",
            "- 상태: open",
            "",
        ]
    )
    with path.open("a", encoding="utf-8") as file:
        file.write("\n".join(lines) + "\n")


def _ensure_readme(folder: Path) -> None:
    """폴더를 처음 만들 때만 안내 글을 둔다."""
    readme_path = folder / README_FILE_NAME
    if readme_path.exists():
        return
    readme_path.write_text(
        "이 폴더는 조문 캡처가 실패했을 때 자동으로 쌓입니다.\n"
        "\n"
        "- 실패기록.md … 사람이 읽고 피드백을 적기 좋은 글\n"
        "- 실패기록.jsonl … 프로그램·AI가 다루기 좋은 한 줄 한 건\n"
        "\n"
        "쓰는 방법:\n"
        "1. 실패기록.md 를 연다.\n"
        "2. 해당 건의 '피드백' 줄에 바른 문구·원인·메모를 적는다.\n"
        "3. AI에게 맡길 때는 md 나 jsonl 내용을 그대로 붙여 넣으면 된다.\n",
        encoding="utf-8",
    )
