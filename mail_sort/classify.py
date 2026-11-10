"""
파일 이름과 확장자만 보고 시공사, 소송 단계, 날짜, 서류 종류를 정한다.

왜 파일 내용을 열어 보지 않는가:
  감정서 PDF, 도면, 한글, 엑셀이 섞여 있고, 회사 PC에서 파일을 열어
  본문을 읽는 방식은 느리고 깨지기 쉽다. 메일로 받은 자료는 대개
  파일 이름에 시공사·날짜·서류 이름이 들어 있으므로 이름 규칙이 먼저다.
  이름이 부족하면 '미확인' 폴더로 보내고, 사용자가 규칙을 보강한다.
"""

import re
from datetime import date, datetime
from pathlib import Path

from mail_sort.models import ClassifiedFile, KeywordRule, SortRules


_DATE_WITH_SEPARATOR = re.compile(
    r"(20\d{2})\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})"
)
# 구분자 없는 20250601 형식. 앞뒤에 숫자가 더 있으면 사건번호 같은 긴 숫자이므로 버린다.
_DATE_COMPACT = re.compile(r"(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)")


def classify_saved_file(file_path: Path, rules: SortRules) -> ClassifiedFile:
    """파일 하나의 분류 결과를 만든다. 파일을 옮기지는 않는다."""

    file_name = file_path.name
    found_date = find_date_in_file_name(file_name)
    if found_date is None:
        document_date = _date_from_file_time(file_path)
        is_date_from_file_time = True
    else:
        document_date = found_date
        is_date_from_file_time = False

    contractor = find_best_keyword_rule(file_name, rules.contractors)
    stage = find_best_keyword_rule(file_name, rules.stages)
    document_kind = find_document_kind(file_path, rules)

    return ClassifiedFile(
        source_path=file_path,
        contractor_name=(
            contractor.name if contractor else rules.unknown_contractor_name
        ),
        stage_name=stage.name if stage else rules.unknown_stage_name,
        document_date=document_date,
        document_kind_name=(
            document_kind.name if document_kind else rules.unknown_document_kind_name
        ),
        is_date_from_file_time=is_date_from_file_time,
    )


def find_date_in_file_name(file_name: str) -> date | None:
    """파일 이름에서 처음 나오는 그럴듯한 날짜를 고른다.

    앞에 있는 날짜를 쓰는 이유:
      '2024-03-02_제출_2024-03-05.pdf' 처럼 두 날짜가 있으면,
      사람들이 문서 날짜를 앞에 적는 경우가 많아서 첫 날짜를 문서 날짜로 본다.
    """

    separated = _DATE_WITH_SEPARATOR.search(file_name)
    if separated:
        parsed = _try_make_date(separated.group(1), separated.group(2), separated.group(3))
        if parsed is not None:
            return parsed

    compact = _DATE_COMPACT.search(file_name)
    if compact:
        return _try_make_date(compact.group(1), compact.group(2), compact.group(3))
    return None


def find_best_keyword_rule(
    file_name: str, rules: tuple[KeywordRule, ...]
) -> KeywordRule | None:
    """파일 이름에 들어 있는 말 중 가장 긴 말에 해당하는 규칙을 고른다.

    긴 말을 우선하는 이유:
      '한라'와 '한라건설'이 둘 다 있으면 짧은 말이 먼저 걸려
      다른 회사 파일을 가져갈 수 있다. 더 긴 말이 더 구체적이다.
      길이가 같으면 기준 파일에 먼저 적힌 규칙을 쓴다.
    """

    folded_name = fold_for_match(file_name)
    best_rule: KeywordRule | None = None
    best_length = 0

    for rule in rules:
        for keyword in rule.keywords:
            folded_keyword = fold_for_match(keyword)
            if not folded_keyword:
                continue
            if folded_keyword not in folded_name:
                continue
            if len(folded_keyword) > best_length:
                best_rule = rule
                best_length = len(folded_keyword)
    return best_rule


def find_document_kind(file_path: Path, rules: SortRules) -> KeywordRule | None:
    """서류 종류는 파일 이름 문구를 먼저 보고, 없을 때만 확장자를 본다.

    문구를 우선하는 이유:
      '감정서.xlsx' 는 엑셀이기도 하고 감정서이기도 하다.
      확장자를 먼저 보면 전부 엑셀 폴더로 들어가 감정서가 묻힌다.
    """

    by_keyword = find_best_keyword_rule(file_path.name, rules.document_kinds)
    if by_keyword is not None:
        return by_keyword

    extension = file_path.suffix.lower()
    if not extension:
        return None

    for rule in rules.document_kinds:
        if extension in rule.extensions:
            return rule
    return None


def fold_for_match(text: str) -> str:
    """비교용으로 공백을 없애고 영문은 소문자로 만든다.

    공백을 빼는 이유:
      '감정 서'와 '감정서'를 다른 문서로 보면, 같은 자료가 다른 폴더로 갈라진다.
    """

    return "".join(text.split()).casefold()


def build_destination_directory(classified: ClassifiedFile, output_root: Path) -> Path:
    """시공사 / 소송 단계 / 날짜 / 서류 종류 순서로 폴더 경로를 만든다.

    이 순서인 이유:
      사용자가 원한 나눔이 시공사별, 날짜별, 소송 단계별이다.
      시공사가 맨 위여야 사건 더미가 회사별로 모이고,
      그 안에서 소송 단계로 들어간 뒤 날짜 폴더를 본다.
      서류 종류는 같은 날 감정서·도면·엑셀이 섞이지 않게 마지막에 둔다.
    """

    date_folder = classified.document_date.isoformat()
    return (
        output_root
        / _safe_folder_name(classified.contractor_name)
        / _safe_folder_name(classified.stage_name)
        / date_folder
        / _safe_folder_name(classified.document_kind_name)
    )


def _safe_folder_name(name: str) -> str:
    """윈도우 폴더 이름에 넣을 수 없는 문자를 밑줄로 바꾼다."""

    blocked = '\\/:*?"<>|'
    cleaned = "".join("_" if char in blocked else char for char in name).strip()
    return cleaned or "이름없음"


def _date_from_file_time(file_path: Path) -> date:
    modified = datetime.fromtimestamp(file_path.stat().st_mtime)
    return modified.date()


def _try_make_date(year_text: str, month_text: str, day_text: str) -> date | None:
    try:
        return date(int(year_text), int(month_text), int(day_text))
    except ValueError:
        return None
