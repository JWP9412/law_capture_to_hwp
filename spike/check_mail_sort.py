"""
메일 자료 분류가 폴더를 제대로 만드는지 임시 폴더에서 확인한다.
한글·브라우저·실제 메일은 켜지 않는다.
"""

import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mail_sort.models import SortOptions
from mail_sort.rules_file import load_sort_rules
from mail_sort.sort_files import sort_saved_mail_files


def report(label: str, is_ok: bool, detail: str = "") -> bool:
    print(f"  [{'OK  ' if is_ok else '실패'}] {label}" + (f"  -- {detail}" if detail else ""))
    return is_ok


def write_sample(folder: Path, file_name: str, content: str = "sample") -> Path:
    path = folder / file_name
    path.write_text(content, encoding="utf-8")
    return path


def main() -> int:
    rules_path = Path(__file__).resolve().parent.parent / "mail_sort" / "default_rules.json"
    rules = load_sort_rules(rules_path)
    all_passed = True

    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        source = root / "받은파일"
        output = root / "분류결과"
        source.mkdir()

        write_sample(source, "예시건설_2025-06-01_감정서.pdf", "appraisal")
        write_sample(source, "예시건설_의견서_2024.03.02.hwp", "opinion")
        write_sample(source, "평면도.dwg", "drawing")
        write_sample(source, "공사비내역.xlsx", "sheet")
        write_sample(source, "예시건설_감정서.xlsx", "appraisal-sheet")

        results = sort_saved_mail_files(
            SortOptions(
                source_directory=source,
                output_directory=output,
                rules=rules,
            )
        )
        by_name = {result.source_path.name: result for result in results}

        appraisal = by_name["예시건설_2025-06-01_감정서.pdf"]
        expected_appraisal = (
            output / "예시건설" / "감정" / "2025-06-01" / "감정서" / appraisal.source_path.name
        )
        all_passed &= report(
            "감정서 PDF는 시공사/감정/날짜/감정서",
            appraisal.destination_path == expected_appraisal and expected_appraisal.is_file(),
            str(appraisal.destination_path),
        )

        opinion = by_name["예시건설_의견서_2024.03.02.hwp"]
        expected_opinion = (
            output / "예시건설" / "의견서" / "2024-03-02" / "의견서" / opinion.source_path.name
        )
        all_passed &= report(
            "의견서는 점 날짜를 폴더 날짜로 바꿈",
            opinion.destination_path == expected_opinion and expected_opinion.is_file(),
            str(opinion.destination_path),
        )

        drawing = by_name["평면도.dwg"]
        all_passed &= report(
            "시공사를 모르면 미확인, 도면 확장자는 도면",
            drawing.classified_file is not None
            and drawing.classified_file.contractor_name == "시공사_미확인"
            and drawing.classified_file.document_kind_name == "도면"
            and drawing.classified_file.stage_name == "단계_미확인"
            and drawing.destination_path is not None
            and drawing.destination_path.is_file(),
            str(drawing.destination_path),
        )

        sheet = by_name["공사비내역.xlsx"]
        all_passed &= report(
            "이름에 종류가 없는 엑셀은 엑셀 폴더",
            sheet.classified_file is not None
            and sheet.classified_file.document_kind_name == "엑셀",
            str(sheet.destination_path),
        )

        appraisal_sheet = by_name["예시건설_감정서.xlsx"]
        all_passed &= report(
            "감정서.xlsx 는 엑셀보다 감정서 폴더",
            appraisal_sheet.classified_file is not None
            and appraisal_sheet.classified_file.document_kind_name == "감정서"
            and appraisal_sheet.classified_file.contractor_name == "예시건설",
            str(appraisal_sheet.destination_path),
        )

        second = sort_saved_mail_files(
            SortOptions(
                source_directory=source,
                output_directory=output,
                rules=rules,
            )
        )
        all_passed &= report(
            "같은 파일을 다시 돌려도 건너뜀",
            all(result.is_skipped for result in second),
            f"{len(second)}개",
        )

        originals = list(source.iterdir())
        all_passed &= report(
            "기본은 복사라 원본이 남음",
            len(originals) == 5,
            f"{len(originals)}개",
        )

    print()
    print("통과" if all_passed else "실패")
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
