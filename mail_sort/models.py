"""
메일에서 받아 둔 파일을 나눌 때 쓰는 값 묶음.

왜 함수 인자로 하나씩 넘기지 않는가:
  시공사 규칙, 소송 단계, 저장 위치, 복사할지 말지를 인자로 늘리면
  나중에 순서가 바뀌어도 오류가 안 나고, 호출하는 쪽이 무엇을 넣는지 알기 어렵다.
  관련 값은 이 파일의 데이터 묶음으로 같이 다닌다.
"""

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class KeywordRule:
    """이름과, 그 이름으로 보낼지 판단할 때 파일 이름에서 찾을 말."""

    name: str
    keywords: tuple[str, ...] = ()
    # 도면의 dwg, 엑셀의 xlsx처럼 확장자로만 종류가 갈리는 경우에 쓴다.
    # 비어 있으면 파일 이름 안의 말만 본다.
    extensions: tuple[str, ...] = ()


@dataclass(frozen=True)
class SortRules:
    """사용자가 고칠 수 있는 분류 기준 전체."""

    contractors: tuple[KeywordRule, ...]
    stages: tuple[KeywordRule, ...]
    document_kinds: tuple[KeywordRule, ...]
    unknown_contractor_name: str = "시공사_미확인"
    unknown_stage_name: str = "단계_미확인"
    unknown_document_kind_name: str = "기타"


@dataclass(frozen=True)
class ClassifiedFile:
    """파일 하나를 보고 정한 폴더 재료. 아직 파일을 옮기지 않은 상태다."""

    source_path: Path
    contractor_name: str
    stage_name: str
    document_date: date
    document_kind_name: str
    # 파일 이름에 날짜가 없어서 받은 시각(수정 시각)을 썼으면 True.
    # 나중에 결과 문구에서 "이름에 날짜가 없어 저장 시각을 썼다"고 구분하려고 둔다.
    is_date_from_file_time: bool


@dataclass
class SortOptions:
    """한 번 분류를 돌릴 때 필요한 위치와 방식."""

    source_directory: Path
    output_directory: Path
    rules: SortRules
    # 기본은 복사다. 원본을 바로 옮기면 잘못 분류했을 때 메일에서 다시 받기 어렵다.
    is_copy: bool = True
    # True면 폴더를 만들지 않고, 어디로 갈지만 알려 준다.
    is_dry_run: bool = False


@dataclass
class SortResult:
    """파일 하나의 처리 결과. 화면·검증에서 이 목록을 그대로 읽는다."""

    source_path: Path
    destination_path: Path | None
    message: str
    is_skipped: bool = False
    classified_file: ClassifiedFile | None = None
    notes: list[str] = field(default_factory=list)
