"""
분류 기준을 JSON 파일에서 읽는다.

왜 코드 안에 시공사 이름을 안 박는가:
  사건마다 시공사가 다르다. 프로그램을 고치지 않고 글 파일만 고쳐
  이름을 추가할 수 있어야 건축 전공 사용자가 직접 쓸 수 있다.
"""

import json
from pathlib import Path

from mail_sort.models import KeywordRule, SortRules


class MailSortError(Exception):
    """분류 기준이 깨졌거나, 돌릴 수 없는 경로일 때. 메시지는 한국어 문장이다."""


def load_sort_rules(rules_path: Path) -> SortRules:
    """JSON 파일을 SortRules로 바꾼다. 형식이 이상하면 MailSortError."""

    if not rules_path.is_file():
        raise MailSortError(
            f"분류 기준 파일을 찾지 못했습니다: {rules_path}"
        )

    try:
        raw_text = rules_path.read_text(encoding="utf-8")
        raw_rules = json.loads(raw_text)
    except json.JSONDecodeError as error:
        raise MailSortError(
            f"분류 기준 파일이 올바른 JSON이 아닙니다: {rules_path} ({error})"
        ) from error
    except OSError as error:
        raise MailSortError(
            f"분류 기준 파일을 읽지 못했습니다: {rules_path} ({error})"
        ) from error

    if not isinstance(raw_rules, dict):
        raise MailSortError("분류 기준 파일의 맨 위는 중괄호로 묶인 항목이어야 합니다.")

    return SortRules(
        contractors=_read_rule_list(raw_rules, "contractors", "시공사"),
        stages=_read_rule_list(raw_rules, "stages", "소송 단계"),
        document_kinds=_read_rule_list(raw_rules, "document_kinds", "서류 종류"),
        unknown_contractor_name=_read_optional_name(
            raw_rules, "unknown_contractor_name", "시공사_미확인"
        ),
        unknown_stage_name=_read_optional_name(
            raw_rules, "unknown_stage_name", "단계_미확인"
        ),
        unknown_document_kind_name=_read_optional_name(
            raw_rules, "unknown_document_kind_name", "기타"
        ),
    )


def _read_optional_name(raw_rules: dict, key: str, default_name: str) -> str:
    value = raw_rules.get(key, default_name)
    if not isinstance(value, str) or not value.strip():
        raise MailSortError(f"'{key}' 는 비어 있지 않은 글이어야 합니다.")
    return value.strip()


def _read_rule_list(raw_rules: dict, key: str, label: str) -> tuple[KeywordRule, ...]:
    raw_list = raw_rules.get(key, [])
    if not isinstance(raw_list, list):
        raise MailSortError(f"{label} 목록('{key}')은 대괄호로 묶인 목록이어야 합니다.")

    rules: list[KeywordRule] = []
    for index, item in enumerate(raw_list, start=1):
        rules.append(_read_one_rule(item, label, index))
    return tuple(rules)


def _read_one_rule(item: object, label: str, index: int) -> KeywordRule:
    if not isinstance(item, dict):
        raise MailSortError(f"{label} {index}번째 항목이 중괄호 형식이 아닙니다.")

    name = item.get("name")
    if not isinstance(name, str) or not name.strip():
        raise MailSortError(f"{label} {index}번째 항목에 이름(name)이 없습니다.")

    place = f"{label} {index}번째 항목"
    return KeywordRule(
        name=name.strip(),
        keywords=_read_string_tuple(item.get("keywords", []), f"{place}의 keywords"),
        extensions=_read_extension_tuple(item.get("extensions", []), place),
    )


def _read_string_tuple(value: object, place: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(one, str) for one in value):
        raise MailSortError(f"{place} 는 글 목록이어야 합니다.")
    return tuple(one.strip() for one in value if one.strip())


def _read_extension_tuple(value: object, place: str) -> tuple[str, ...]:
    extensions = _read_string_tuple(value, f"{place}의 extensions")
    normalized: list[str] = []
    for extension in extensions:
        # 사용자가 "xlsx" 라고만 적어도 ".xlsx" 와 같게 본다.
        # 점 유무가 다르면 같은 파일이 엑셀로 안 들어가기 때문이다.
        if not extension.startswith("."):
            extension = f".{extension}"
        normalized.append(extension.lower())
    return tuple(normalized)
