"""
받아 둔 파일들을 분류 결과에 맞는 폴더로 복사하거나 옮긴다.

포털(https://ngwx.ktbizoffice.com)에서 바로 내려받지 않는 이유:
  그 주소는 KT 마이오피스 웹 화면이다. 메일 프로그램처럼 붙는 공개 통로가
  없고, 로그인 비밀번호를 이 프로그램에 적어 두면 회사 자료가 위험하다.
  회사 보안 프로그램이 자동 접속을 막을 수도 있다.
  그래서 이 단계는 '이미 한 폴더에 저장해 둔 파일'만 나눈다.
  포털에서 첨부를 그 폴더로 저장하는 일은 다음 단계로 남긴다.
"""

import shutil
from pathlib import Path

from mail_sort.classify import build_destination_directory, classify_saved_file
from mail_sort.models import ClassifiedFile, SortOptions, SortResult
from mail_sort.rules_file import MailSortError


def sort_saved_mail_files(options: SortOptions) -> list[SortResult]:
    """원본 폴더의 파일을 결과 폴더로 나눈다. 파일 하나가 실패해도 나머지는 계속한다."""

    source_directory = options.source_directory
    output_directory = options.output_directory

    if not source_directory.is_dir():
        raise MailSortError(
            f"받아 둔 파일 폴더를 찾지 못했습니다: {source_directory}"
        )
    if _is_same_or_inside(output_directory, source_directory) or _is_same_or_inside(
        source_directory, output_directory
    ):
        # 결과 폴더가 원본 안에 있으면, 다음 실행이 방금 나눈 파일을 다시 주워 담는다.
        raise MailSortError(
            "결과 폴더는 받아 둔 파일 폴더와 서로 포함되지 않는 다른 위치여야 합니다."
        )

    results: list[SortResult] = []
    for file_path in _list_files(source_directory):
        try:
            results.append(_place_one_file(file_path, options))
        except OSError as error:
            results.append(
                SortResult(
                    source_path=file_path,
                    destination_path=None,
                    message=f"파일을 처리하지 못했습니다: {file_path.name} ({error})",
                    is_skipped=True,
                )
            )
    return results


def _place_one_file(file_path: Path, options: SortOptions) -> SortResult:
    classified = classify_saved_file(file_path, options.rules)
    destination_directory = build_destination_directory(
        classified, options.output_directory
    )
    destination_path = _destination_without_duplicate(
        file_path, destination_directory
    )

    if destination_path is None:
        return SortResult(
            source_path=file_path,
            destination_path=destination_directory / file_path.name,
            message=f"이미 같은 파일이 있어 건너뜀: {file_path.name}",
            is_skipped=True,
            classified_file=classified,
        )

    notes = _notes_for(classified, options.rules.unknown_contractor_name)
    if options.is_dry_run:
        return SortResult(
            source_path=file_path,
            destination_path=destination_path,
            message=f"예정: {file_path.name} → {destination_path}",
            classified_file=classified,
            notes=notes,
        )

    destination_directory.mkdir(parents=True, exist_ok=True)
    if options.is_copy:
        shutil.copy2(file_path, destination_path)
        verb = "복사"
    else:
        shutil.move(str(file_path), str(destination_path))
        verb = "이동"

    return SortResult(
        source_path=file_path,
        destination_path=destination_path,
        message=f"{verb}: {file_path.name} → {destination_path}",
        classified_file=classified,
        notes=notes,
    )


def _list_files(source_directory: Path) -> list[Path]:
    """바로 아래 파일만 본다. 하위 폴더까지 들어가면 이미 나눈 결과를 다시 집는다."""

    files = [path for path in source_directory.iterdir() if path.is_file()]
    return sorted(files, key=lambda path: path.name)


def _destination_without_duplicate(
    source_path: Path, destination_directory: Path
) -> Path | None:
    """같은 이름·같은 크기가 있으면 None. 이름만 같으면 _2, _3 을 붙인다.

    크기까지 보는 이유:
      분류를 두 번 돌려도 같은 파일이 계속 쌓이면 안 된다.
      이름은 같은데 크기가 다르면 다른 버전일 수 있어 둘 다 남긴다.
    """

    plain = destination_directory / source_path.name
    if plain.exists() and plain.stat().st_size == source_path.stat().st_size:
        return None
    if not plain.exists():
        return plain

    stem = source_path.stem
    suffix = source_path.suffix
    number = 2
    while True:
        candidate = destination_directory / f"{stem}_{number}{suffix}"
        if not candidate.exists():
            return candidate
        if candidate.stat().st_size == source_path.stat().st_size:
            return None
        number += 1


def _notes_for(classified: ClassifiedFile, unknown_contractor_name: str) -> list[str]:
    notes: list[str] = []
    if classified.is_date_from_file_time:
        notes.append("파일 이름에 날짜가 없어 저장된 날짜를 폴더 이름으로 썼습니다.")
    if classified.contractor_name == unknown_contractor_name:
        notes.append("시공사를 파일 이름에서 찾지 못했습니다. 분류 기준에 회사 이름을 추가하세요.")
    return notes


def _is_same_or_inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False
