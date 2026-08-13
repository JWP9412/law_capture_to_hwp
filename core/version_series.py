"""
같은 조문을 여러 개정본에 걸쳐 다룰 때 필요한 판단들을 담당한다.

하는 일 세 가지:
  1) 화면에서 담은 조건 한 줄을, 개정본 수만큼의 실제 작업으로 펼친다
  2) 개정본끼리 조문 내용이 실제로 달라졌는지 비교한다
  3) 그림 아래(위)에 붙일 캡션 문구를 만든다

왜 내용을 비교하는가:
  개정이 있었다고 해서 그 조문이 바뀐 것은 아니다.
  다른 조문만 고치고 해당 조문은 그대로 두는 개정이 흔하다.
  그런 경우를 표시해 주지 않으면, 서면을 읽는 사람이
  똑같아 보이는 그림 두 장을 놓고 무엇이 달라졌는지 한참 찾게 된다.
"""
import difflib
import re

import config
from core.models import ArticleCaptureJob, ArticleCaptureTask, ArticleTextComparison

WHITESPACE_PATTERN = re.compile(r"\s+")


def expand_into_tasks(job: ArticleCaptureJob) -> list[ArticleCaptureTask]:
    """
    화면에서 담은 조건 한 줄을 실제 작업들로 펼친다.

    조문 하나를 개정본 세 개에 걸쳐 보겠다고 하면 작업 세 개가 나온다.
    개정본은 시행일이 오래된 것부터 순서대로 처리된다.
    """
    return [
        ArticleCaptureTask(
            version=version,
            article_numbers=list(job.article_numbers),
            underline_phrases=list(job.underline_phrases),
            target_hwp_path=job.target_hwp_path,
            insertion_mode=job.insertion_mode,
            should_add_caption=job.should_add_caption,
            should_add_border=job.should_add_border,
        )
        for version in job.target_versions
    ]


def _normalize(text: str) -> str:
    """띄어쓰기와 줄바꿈을 지운다. 견주기 전에 반드시 거친다."""
    return WHITESPACE_PATTERN.sub("", text)


def compare_article_text(
    current_body_text: str, previous_body_text: str
) -> ArticleTextComparison:
    """
    앞 개정본과 조문 내용이 얼마나 같은지 견준다.

    '같다/다르다' 만으로는 부족하다. 이름만 바뀌고 내용은 그대로인 개정,
    문구만 조금 다듬은 개정이 흔한데, 글자 하나만 달라도 '다름' 으로 나오면
    서면을 쓰는 사람이 그 사실을 알아챌 수 없다.

    견주기 전에 띄어쓰기와 줄바꿈 차이를 지운다. 같은 문장이라도 개정본마다
    줄이 다르게 끊겨서, 그대로 견주면 다르다고 나오기 때문이다.

    (제목·시행일·소관부처 줄은 이미 걸러진 상태로 들어온다.
     그 부분은 개정할 때마다 반드시 바뀌므로 견주기에 넣으면 의미가 없다)

    앞 개정본이 없으면(첫 판이면) 견줄 것이 없으므로 '다름 · 0.0' 이다.
    """
    if not previous_body_text:
        return ArticleTextComparison(is_same=False, similarity_ratio=0.0)

    current = _normalize(current_body_text)
    previous = _normalize(previous_body_text)
    if current == previous:
        return ArticleTextComparison(is_same=True, similarity_ratio=1.0)

    # autojunk 를 끄는 이유:
    #   켜 두면 긴 글에서 자주 나오는 글자를 '의미 없는 것' 으로 멋대로 빼고 센다.
    #   조문은 '제', '조', '항' 같은 글자가 자주 나오므로 값이 실제와 어긋난다.
    matcher = difflib.SequenceMatcher(None, previous, current, autojunk=False)
    return ArticleTextComparison(
        is_same=False, similarity_ratio=matcher.ratio()
    )


def build_caption(
    task: ArticleCaptureTask,
    comparison: ArticleTextComparison,
    page_number: int = 1,
    total_pages: int = 1,
) -> str:
    """
    그림 캡션에 붙일 **설명 문구**를 만든다. (번호는 여기에 넣지 않는다)

    예) 공동주택 하자의 조사, 보수비용 산정 및 하자판정기준 제1조 발췌 (시행 2025. 2. 3.)

    '[그림 N]' 번호는 한글이 캡션에 넣는 자동번호 필드를 그대로 쓴다.
    파이썬이 숫자를 세어 적으면 이미 그림이 있는 문서에서 번호가 겹친다.
    한글 쪽에서는 이 설명 앞에 대괄호만 붙여 '[그림 N] 설명…' 형태를 만든다.

    시행일을 반드시 넣는다. 개정본 여러 장이 나란히 들어가면
    시행일 없이는 어느 것이 어느 판인지 구별할 수 없기 때문이다.
    거꾸로 시행일이 있으므로 '구' 같은 표시는 넣지 않는다.

    조문이 길어 그림이 여러 장이면 뒤에 '(1/3)' 을 붙인다.
    그래야 서면을 읽는 사람이 뒤에 더 있다는 것을 안다.
    한 장뿐이면 붙이지 않는다.

    법령 이름은 '지금 이름' 이 아니라 **그 판이 시행되던 당시의 이름**을 쓴다.
    그림에 찍힌 문서 제목과 캡션이 어긋나면 서면에 실제와 다른 이름을
    인용하는 셈이 되기 때문이다. (자세한 이유는 models.py 의 historical_law_name)
    """
    version = task.version

    return config.CAPTION_TEMPLATE.format(
        law_name=version.display_law_name,
        article_label=task.article_label,
        effective_date_label=version.effective_date_label,
        same_as_previous_suffix=_build_comparison_suffix(comparison),
    ) + _build_page_marker(page_number, total_pages)


def _build_comparison_suffix(comparison: ArticleTextComparison) -> str:
    """'(앞 개정안과 동일)' 또는 '(앞 개정안과 97% 유사)'. 해당 없으면 빈 글자."""
    if comparison.is_same:
        return config.SAME_AS_PREVIOUS_VERSION_SUFFIX
    if comparison.is_similar_but_not_same:
        return config.SIMILAR_TO_PREVIOUS_VERSION_SUFFIX.format(
            percent=comparison.similarity_percent
        )
    return ""


def _build_page_marker(page_number: int, total_pages: int) -> str:
    """'(1/3)' 처럼 몇 번째 쪽인지 나타내는 꼬리표. 한 장뿐이면 빈 글자."""
    if total_pages <= 1:
        return ""
    return config.CAPTION_PAGE_MARKER.format(
        page_number=page_number, total_pages=total_pages
    )
