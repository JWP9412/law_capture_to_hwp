"""
법령·고시를 찾고, 원하는 시점에 시행 중이던 판을 골라내는 일을 담당한다.

이 파일이 푸는 문제:
  같은 법이라도 개정될 때마다 별개의 문서로 존재한다.
  2025년에 벌어진 일을 다투는 서면에 2026년 개정본을 인용하면 안 되므로,
  "그때 살아있던 판이 무엇인가" 를 정확히 골라내야 한다.

주요 사용법:
  search_laws("하자판정기준")                       # 이름 일부로 찾기 (화면의 [검색])
  list_all_versions(찾은결과)                       # 개정 이력 전체
  find_version_effective_on(찾은결과, date(2025,6,1))  # 그 시점의 판 하나
  find_versions_effective_between(찾은결과, 기간)      # 기간 안의 개정본 전부
"""
import html
import re
import xml.etree.ElementTree as ElementTree
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime

import config
from config import LawSourceKind
from core import law_site
from core.errors import (
    LawNotFoundError,
    LawSiteStructureChangedError,
    LawVersionNotFoundError,
    NoVersionInPeriodError,
)
from core.models import LawVersion

DEFAULT_SEARCH_RESULT_LIMIT = 20

# 공개 API 가 갈래마다 다른 이름을 쓰기 때문에 짝을 지어둔다.
OPEN_API_TARGETS = {
    LawSourceKind.ADMINISTRATIVE_RULE: "admrul",
    LawSourceKind.STATUTE: "law",
}

# 공개 API 응답에서 항목 하나가 담기는 태그와, 그 안의 항목 이름들.
# 갈래마다 태그 이름이 달라 표로 만들어 두었다.
OPEN_API_FIELDS = {
    LawSourceKind.ADMINISTRATIVE_RULE: {
        "entry_tag": "admrul",
        "version_id": "행정규칙일련번호",
        "law_id": "행정규칙ID",
        "law_name": "행정규칙명",
        "effective_date": "시행일자",
        "kind_label": "행정규칙종류",
        "promulgation_number": "발령번호",
        "revision_label": "제개정구분명",
    },
    LawSourceKind.STATUTE: {
        "entry_tag": "law",
        "version_id": "법령일련번호",
        "law_id": "법령ID",
        "law_name": "법령명한글",
        "effective_date": "시행일자",
        "kind_label": "법령구분명",
        "promulgation_number": "공포번호",
        "revision_label": "제개정구분명",
    },
}

# 한글 주소로 연 화면에서 문서 번호를 뽑아내는 규칙 (공개 API 가 막혔을 때의 예비 수단)
KOREAN_URL_VERSION_ID_PATTERNS = {
    LawSourceKind.ADMINISTRATIVE_RULE: re.compile(r"admRulSeq[^0-9]{0,12}(\d{10,})"),
    LawSourceKind.STATUTE: re.compile(r"lsiSeq[^0-9]{0,12}(\d{5,})"),
}
KOREAN_URL_CATEGORIES = {
    LawSourceKind.ADMINISTRATIVE_RULE: "행정규칙",
    LawSourceKind.STATUTE: "법령",
}

# 개정 이력 한 줄에서 문서 번호를 뽑아내는 규칙.
# 갈래마다 사이트가 쓰는 함수 이름과 인자 순서가 다르다.
#   행정규칙: admRulViewHst('Y','2100000254050')
#   법령:     lsViewLsHst2('284009', '20260305', '21447', '20260701', 'Y', '0', '타법개정')
HISTORY_VERSION_ID_PATTERN = re.compile(
    r"admRulViewHst\('[YN]',\s*'(\d+)'\)|lsViewLsHst\d*\(\s*'(\d+)'"
)

# "[시행 2025. 2. 3.] [국토교통부고시 제2025-58호, 2025. 2. 3., 일부개정]" 에서
# 시행일과 발령 정보를 각각 뽑아내는 규칙.
EFFECTIVE_DATE_PATTERN = re.compile(r"\[시행\s*(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.?\s*\]")
PROMULGATION_PATTERN = re.compile(r"\[시행[^\]]*\]\s*\[([^\]]+)\]")

HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
WHITESPACE_IN_NAME_PATTERN = re.compile(r"\s+")


@dataclass(frozen=True)
class DatePeriod:
    """언제부터 언제까지인지. 기간으로 개정본을 찾을 때 쓴다."""

    start: date
    end: date

    def contains(self, moment: date) -> bool:
        return self.start <= moment <= self.end

    def __str__(self) -> str:
        return f"{self.start} ~ {self.end}"


@dataclass(frozen=True)
class LawSearchResult:
    """
    검색 결과 한 줄. 화면에서 사용자가 고를 후보다.

    여기 담긴 시행일은 '현재 판' 의 것이다.
    옛 판까지 보려면 이 결과를 가지고 개정 이력을 다시 물어봐야 한다.
    """

    source_kind: LawSourceKind
    version_id: str  # 이 판을 가리키는 번호 (개정될 때마다 바뀐다)
    law_id: str  # 법령 자체를 가리키는 번호 (개정돼도 그대로다)
    law_name: str
    effective_date: date
    kind_label: str  # 예: "고시", "법률", "대통령령"
    promulgation_label: str

    def __str__(self) -> str:
        return f"{self.law_name} ({self.kind_label}) [시행 {self.effective_date}]"


def _strip_html_tags(fragment: str) -> str:
    """화면 꾸미기용 표시를 걷어내고 사람이 읽는 글자만 남긴다."""
    return html.unescape(HTML_TAG_PATTERN.sub("", fragment)).replace("\xa0", " ").strip()


def _parse_compact_date(text: str) -> date | None:
    """'20250203' 형태의 날짜를 읽는다."""
    digits = text.strip()
    if len(digits) != 8 or not digits.isdigit():
        return None
    return datetime.strptime(digits, "%Y%m%d").date()


def _parse_bracketed_effective_date(text: str) -> date | None:
    """'[시행 2025. 2. 3.]' 형태의 날짜를 읽는다."""
    matched = EFFECTIVE_DATE_PATTERN.search(text)
    if not matched:
        return None
    year, month, day = (int(part) for part in matched.groups())
    return date(year, month, day)


def search_laws(
    query: str, source_kind: LawSourceKind | None = None
) -> list[LawSearchResult]:
    """
    이름의 일부만으로 법령·고시를 찾는다. 화면의 [검색] 버튼이 부르는 함수다.

    갈래를 지정하지 않으면 행정규칙과 법령을 모두 뒤진다.
    "하자판정기준" 처럼 줄여 부르는 이름으로도 찾아진다.
    """
    kinds_to_search = [source_kind] if source_kind else list(LawSourceKind)

    results: list[LawSearchResult] = []
    for kind in kinds_to_search:
        results.extend(_search_within_one_kind(query, kind))

    if not results:
        raise LawNotFoundError(query)

    return _put_closest_name_match_first(results, query)


def _put_closest_name_match_first(
    results: list[LawSearchResult], query: str
) -> list[LawSearchResult]:
    """
    검색어와 가장 가까운 이름을 맨 앞으로 옮긴다.

    법제처 검색은 이름 어디에든 검색어가 들어가면 결과로 준다.
    그래서 '주택법' 을 찾으면 '민간임대주택에 관한 특별법' 이 먼저 나오기도 한다.
    화면은 첫 번째 결과를 기본으로 고르므로, 이름이 정확히 같거나
    검색어로 시작하는 것을 앞쪽에 두어야 엉뚱한 법을 집지 않는다.
    """
    normalized_query = _normalize_law_name(query)

    def closeness(result: LawSearchResult) -> tuple[int, int]:
        name = _normalize_law_name(result.law_name)
        if name == normalized_query:
            rank = 0  # 이름이 정확히 같음
        elif name.startswith(normalized_query):
            rank = 1  # 검색어로 시작함 (예: '주택법 시행령')
        else:
            rank = 2  # 이름 중간에 들어있음
        return rank, len(name)  # 같은 등급이면 이름이 짧은 쪽을 앞으로

    return sorted(results, key=closeness)


def _normalize_law_name(name: str) -> str:
    return WHITESPACE_IN_NAME_PATTERN.sub("", name)


def _search_within_one_kind(query: str, kind: LawSourceKind) -> list[LawSearchResult]:
    """한 갈래(행정규칙 또는 법령) 안에서만 검색한다."""
    try:
        response_xml = law_site.request_open_api_search(
            OPEN_API_TARGETS[kind], query, DEFAULT_SEARCH_RESULT_LIMIT
        )
    except LawSiteStructureChangedError:
        # 검색 통로가 막혔을 때의 예비 수단.
        # 이름을 정확히 알고 있다면 한글 주소로 바로 찾아갈 수 있다.
        return _search_by_korean_url(query, kind)

    try:
        root = ElementTree.fromstring(response_xml)
    except ElementTree.ParseError:
        return []  # 검색이 실패하면 이 갈래는 결과가 없는 것으로 본다

    fields = OPEN_API_FIELDS[kind]
    results: list[LawSearchResult] = []

    for entry in root.findall(fields["entry_tag"]):
        effective_date = _parse_compact_date(_text_of(entry, fields["effective_date"]))
        law_name = _text_of(entry, fields["law_name"])
        version_id = _text_of(entry, fields["version_id"])
        if not (effective_date and law_name and version_id):
            continue

        results.append(
            LawSearchResult(
                source_kind=kind,
                version_id=version_id,
                law_id=_text_of(entry, fields["law_id"]),
                law_name=law_name,
                effective_date=effective_date,
                kind_label=_text_of(entry, fields["kind_label"]),
                promulgation_label=_build_promulgation_label(entry, fields),
            )
        )

    return results


def _text_of(entry: ElementTree.Element, tag_name: str) -> str:
    element = entry.find(tag_name)
    return (element.text or "").strip() if element is not None else ""


def _build_promulgation_label(entry: ElementTree.Element, fields: dict) -> str:
    """'국토교통부고시 제2026-360호, 타법개정' 같은 표기를 만든다."""
    number = _text_of(entry, fields["promulgation_number"])
    revision = _text_of(entry, fields["revision_label"])
    parts = [f"제{number}호" if number else "", revision]
    return ", ".join(part for part in parts if part)


def _search_by_korean_url(law_name: str, kind: LawSourceKind) -> list[LawSearchResult]:
    """
    한글 주소로 법령을 찾는다. 검색 통로가 막혔을 때만 쓰는 예비 수단.

    법령정보센터는 'law.go.kr/행정규칙/이름' 형태의 주소를 지원한다.
    이름이 한 글자라도 다르면 오류 화면이 오므로 정확한 이름을 알아야 한다.
    검색만큼 편하지는 않지만, 통로가 막혔을 때 아무것도 못 하는 것보다는 낫다.

    이 방법으로는 시행일·발령번호까지 알 수 없다.
    문서 번호만 얻어두면 개정 이력을 물어볼 때 나머지가 채워진다.
    """
    try:
        page_html = law_site.request_page_by_korean_url(
            KOREAN_URL_CATEGORIES[kind], law_name
        )
    except LawSiteStructureChangedError:
        return []

    matched = KOREAN_URL_VERSION_ID_PATTERNS[kind].search(page_html)
    if not matched:
        return []

    return [
        LawSearchResult(
            source_kind=kind,
            version_id=matched.group(1),
            law_id="",  # 한글 주소로는 알 수 없다
            law_name=law_name,
            effective_date=date.today(),  # 이력을 조회하면 정확한 값으로 채워진다
            kind_label="",
            promulgation_label="",
        )
    ]


def list_all_versions(law: LawSearchResult) -> list[LawVersion]:
    """
    한 법령·고시의 개정 이력 전체를 시행일 오래된 순으로 돌려준다.

    화면에서 '연혁' 을 눌렀을 때 뜨는 목록과 같은 내용이다.
    예를 들어 하자판정기준은 2014년부터 2026년까지 7개 판이 나온다.

    조문마다 시행일이 다른 개정본은 문서 하나당 '가장 이른 시행일' 을 대표로 둔다.
    (목록 정렬·전체 기간 나열용). 어느 줄에 '(현행)' 을 붙일지와
    특정 시점 고르기는 조문별 시행일 전체를 본다.
    """
    versions, dates_by_version_id = _load_history_with_all_dates(law)
    return _mark_which_version_is_currently_in_effect(versions, dates_by_version_id)


def _effective_date_on_or_before(
    dates: set[date], reference_date: date
) -> date | None:
    """
    기준일 이하인 시행일 중 가장 늦은 날을 고른다.

    조문마다 시행일이 다른 개정본에서
    '그 시점에 이미 시작된 시행일 중 가장 최근 것' 을 고를 때 쓴다.
    기준일보다 늦은 날만 있으면 None (그 시점에는 아직 이 문서가 안 살아 있음).
    """
    already_started = [moment for moment in dates if moment <= reference_date]
    if not already_started:
        return None
    return max(already_started)


def _pick_version_for_reference_date(
    versions: list[LawVersion],
    dates_by_version_id: dict[str, set[date]],
    reference_date: date,
) -> LawVersion | None:
    """
    기준일 시점에 시행 중이던 판 하나를 고른다.

    각 문서의 조문별 시행일 중 기준일 이하인 날들의 최댓값을 비교해
    그 값이 가장 큰 문서를 고른다. 이른 대표일만 보면
    (예: 236977→2022-12-01, 247269→2023-07-04) 검색의 2024-12-01 판을 놓친다.
    """
    best_version: LawVersion | None = None
    best_date: date | None = None

    for version in versions:
        candidate_date = _effective_date_on_or_before(
            dates_by_version_id.get(version.version_id, set()),
            reference_date,
        )
        if candidate_date is None:
            continue
        if best_date is None or candidate_date > best_date:
            best_date = candidate_date
            best_version = version

    if best_version is None or best_date is None:
        return None

    return _copy_version_with_effective_date(best_version, best_date)


def _load_history_with_all_dates(
    law: LawSearchResult,
) -> tuple[list[LawVersion], dict[str, set[date]]]:
    """
    연혁을 읽어 (대표 개정본 목록, 문서번호별 모든 시행일) 을 함께 돌려준다.

    대표 목록: 같은 문서번호는 가장 이른 시행일 하나만 (PDF·특정 시점용).
    시행일 집합: 조문별·검색 API 날짜까지 모은 것 (기간 필터용).
    """
    adapter = config.LAW_SITE_ADAPTERS[law.source_kind]

    form_values = {adapter["version_id_parameter"]: law.version_id}
    if adapter["law_id_parameter"]:
        # 법령은 문서 번호만으로는 이력을 알려주지 않고 법령 고유번호를 함께 요구한다.
        form_values[adapter["law_id_parameter"]] = law.law_id

    history_html = law_site.request_data(adapter["history_path"], form_values)

    raw_versions = _parse_history_entries(history_html, law)
    if not raw_versions:
        # 이력을 못 읽으면 최소한 검색으로 찾은 현재 판이라도 쓸 수 있게 한다.
        raw_versions = [_version_from_search_result(law)]

    dates_by_version_id = _collect_effective_dates_by_version_id(raw_versions, law)
    unique_versions = _remove_duplicate_versions(raw_versions)
    unique_versions.sort(key=lambda version: version.effective_date)
    return unique_versions, dates_by_version_id


def _collect_effective_dates_by_version_id(
    raw_versions: list[LawVersion],
    law: LawSearchResult,
) -> dict[str, set[date]]:
    """
    문서번호마다 연혁에 나온 시행일을 모두 모은다.

    검색 API 가 알려 준 '현재 판' 시행일도 같은 문서번호에 합친다.
    연혁에는 이른 날(예: 2022-12-01)만 있고 API 에는 늦은 날(2024-12-01)만
    보이는 경우가 있어서, 기간 찾기에서 늦은 날이 빠지지 않게 하기 위함이다.
    """
    dates_by_version_id: dict[str, set[date]] = defaultdict(set)
    for version in raw_versions:
        dates_by_version_id[version.version_id].add(version.effective_date)

    if law.version_id:
        dates_by_version_id[law.version_id].add(law.effective_date)

    return dates_by_version_id


def _remove_duplicate_versions(versions_oldest_first: list[LawVersion]) -> list[LawVersion]:
    """
    같은 문서가 여러 번 나오는 것을 하나로 합친다.

    법령은 한 번 개정할 때 조문마다 시행일을 다르게 두는 경우가 있다.
    (예: 대부분은 3월부터, 일부 조문은 6월부터 시행)
    그러면 사이트가 같은 개정본을 시행일만 바꿔 여러 줄로 보여준다.

    우리에게는 같은 문서이므로 그대로 두면 똑같은 PDF 를 여러 번 받아
    서면에 같은 그림이 중복으로 들어간다. 가장 이른 시행일 하나만 남긴다.

    주의: 이 '이른 날' 만으로 기간 필터를 걸면, 늦은 조문 시행일
    (예: 2024-12-01)이 기간 안에 있어도 개정본이 없다고 나온다.
    기간 찾기는 find_versions_effective_between 이 모든 시행일을 본다.
    """
    # 이른 날을 남기려면 시행일 오름차순으로 먼저 본 것을 채택해야 한다.
    ordered = sorted(versions_oldest_first, key=lambda version: version.effective_date)

    seen_version_ids: set[str] = set()
    unique_versions: list[LawVersion] = []

    for version in ordered:
        if version.version_id in seen_version_ids:
            continue
        seen_version_ids.add(version.version_id)
        unique_versions.append(version)

    return unique_versions


def _version_from_search_result(law: LawSearchResult) -> LawVersion:
    return LawVersion(
        source_kind=law.source_kind,
        version_id=law.version_id,
        law_name=law.law_name,
        effective_date=law.effective_date,
        promulgation_label=law.promulgation_label,
        is_currently_in_effect=True,
    )


def _copy_version_with_effective_date(
    version: LawVersion, effective_date: date
) -> LawVersion:
    """같은 문서인데 표시·다운로드용 시행일만 바꿔 새 상자를 만든다."""
    return LawVersion(
        source_kind=version.source_kind,
        version_id=version.version_id,
        law_name=version.law_name,
        effective_date=effective_date,
        promulgation_label=version.promulgation_label,
        is_currently_in_effect=version.is_currently_in_effect,
    )


def _read_version_id(history_entry: str) -> str | None:
    """
    개정 이력 한 줄에서 그 판의 문서 번호를 읽어낸다.

    갈래마다 사이트가 다른 함수 이름을 쓰기 때문에 두 가지 모양을 함께 찾는다.
    찾은 쪽에만 값이 담기므로, 값이 있는 쪽을 골라 돌려준다.
    """
    matched = HISTORY_VERSION_ID_PATTERN.search(history_entry)
    if not matched:
        return None
    return next((group for group in matched.groups() if group), None)


def _parse_history_entries(history_html: str, law: LawSearchResult) -> list[LawVersion]:
    """개정 이력 화면에서 판 하나하나를 읽어낸다."""
    versions: list[LawVersion] = []

    # 이력은 <li> 한 덩어리가 판 하나에 해당한다.
    for entry in re.split(r"<li[^>]*>", history_html)[1:]:
        version_id = _read_version_id(entry)
        if version_id is None:
            continue

        readable_text = _strip_html_tags(entry)
        effective_date = _parse_bracketed_effective_date(readable_text)
        if effective_date is None:
            continue

        promulgation = PROMULGATION_PATTERN.search(readable_text)
        versions.append(
            LawVersion(
                source_kind=law.source_kind,
                version_id=version_id,
                law_name=law.law_name,
                effective_date=effective_date,
                promulgation_label=promulgation.group(1).strip() if promulgation else "",
                is_currently_in_effect=False,  # 아래에서 다시 표시한다
            )
        )

    return versions


def _mark_which_version_is_currently_in_effect(
    versions_oldest_first: list[LawVersion],
    dates_by_version_id: dict[str, set[date]],
) -> list[LawVersion]:
    """
    지금 살아있는 판이 어느 것인지 표시한다.

    '가장 나중에 만들어진 판' 이 아니라
    '오늘 기준으로 이미 시작된 시행일 중 가장 최근인 문서' 이다.
    조문별 시행일이 있으면 이른 대표일만 보지 않고 전체 시행일을 본다.
    (안 그러면 소방시설법처럼 2024-12-01 판을 두고 2023-07-04 를 현행으로 찍는다)
    """
    today = date.today()
    current = _pick_version_for_reference_date(
        versions_oldest_first, dates_by_version_id, today
    )
    current_version_id = current.version_id if current is not None else None

    return [
        LawVersion(
            source_kind=version.source_kind,
            version_id=version.version_id,
            law_name=version.law_name,
            effective_date=version.effective_date,
            promulgation_label=version.promulgation_label,
            is_currently_in_effect=(
                current_version_id is not None
                and version.version_id == current_version_id
            ),
        )
        for version in versions_oldest_first
    ]


def find_version_effective_on(law: LawSearchResult, reference_date: date) -> LawVersion:
    """
    특정 시점에 시행 중이던 판 하나를 골라낸다.

    고르는 기준은 '그 날짜보다 늦지 않게 시작된 시행일들 중 가장 최근인 문서' 이다.
    조문마다 시행일이 다른 개정본은 모든 시행일을 본다.
    예를 들어 소방시설법은 같은 문서에 2022-12-01 과 2024-12-01 이 있는데,
    2026년 기준으로는 2024-12-01 쪽이 맞다 (이른 날만 보면 엉뚱한 판이 고른다).
    """
    versions, dates_by_version_id = _load_history_with_all_dates(law)
    picked = _pick_version_for_reference_date(
        versions, dates_by_version_id, reference_date
    )
    if picked is None:
        raise LawVersionNotFoundError(law.law_name, reference_date)

    # 현행 표시는 '오늘' 기준. 과거 시점을 골라도 목록·캡션에서 구분할 수 있게.
    current_today = _pick_version_for_reference_date(
        versions, dates_by_version_id, date.today()
    )
    is_current = (
        current_today is not None and picked.version_id == current_today.version_id
    )
    return LawVersion(
        source_kind=picked.source_kind,
        version_id=picked.version_id,
        law_name=picked.law_name,
        effective_date=picked.effective_date,
        promulgation_label=picked.promulgation_label,
        is_currently_in_effect=is_current,
    )


def find_versions_effective_between(
    law: LawSearchResult, period: DatePeriod
) -> list[LawVersion]:
    """
    기간 안에 시행된 개정본을 오래된 순으로 모두 돌려준다.

    "2024년부터 2026년 사이에 이 조문이 어떻게 바뀌었나" 를
    서면에 나란히 보여줄 때 쓴다.

    조문마다 시행일이 다른 개정본은, 그 문서의 시행일 중 하나라도
    기간 안에 들어가면 포함한다. (대표일로 쓴 '가장 이른 날'만 보면
    늦은 조문 시행일이 기간에 있어도 빠지는 버그가 난다)

    포함될 때 effective_date 는 기간 안에 드는 날 중 가장 늦은 날로 둔다.
    검색에 보이는 날짜·캡션·법령 PDF 의 efYd 와 맞추기 위해서다.
    """
    unique_versions, dates_by_version_id = _load_history_with_all_dates(law)
    marked_versions = _mark_which_version_is_currently_in_effect(
        unique_versions, dates_by_version_id
    )

    within_period: list[LawVersion] = []
    for version in marked_versions:
        dates_in_period = [
            moment
            for moment in dates_by_version_id.get(version.version_id, set())
            if period.contains(moment)
        ]
        if not dates_in_period:
            continue
        # 기간 안 늦은 날을 쓰면 검색 [시행 2024-12-01] 과 캡션이 맞는다.
        within_period.append(
            _copy_version_with_effective_date(version, max(dates_in_period))
        )

    within_period.sort(key=lambda item: item.effective_date)

    if not within_period:
        raise NoVersionInPeriodError(law.law_name, period.start, period.end)

    return within_period
