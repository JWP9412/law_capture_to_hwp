"""
화면과 실제 기능 사이를 잇는 다리.

화면(ui 폴더의 나머지 파일들)은 법령을 어떻게 찾는지, 한글을 어떻게 다루는지 모른다.
반대로 기능(core 폴더)은 버튼이나 창의 존재를 모른다.
그 둘을 이어주는 것이 이 파일의 유일한 역할이다.

여기서 중요한 일이 하나 더 있다. 시간이 오래 걸리는 작업(법령 조회, PDF 내려받기,
한글 조작)을 화면과 같은 흐름에서 실행하면 그동안 창이 얼어붙어서
'프로그램이 죽었나' 싶게 된다. 그래서 그런 일은 별도의 흐름에서 돌리고,
진행 상황만 화면 쪽으로 넘겨준다.
"""
import queue
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from core import pipeline
from core.article_number import ArticleNumber, build_article_range_label
from core.article_text import fetch_article_text, fetch_full_law_text
from core.errors import LawCaptureError
from core.favorites import FavoriteLaw, add_favorite, load_favorites, remove_favorite
from core.law_source import (
    DatePeriod,
    LawSearchResult,
    find_version_effective_on,
    find_versions_effective_between,
    list_all_versions,
    search_laws,
    was_found_by_former_name,
)
from core.models import ArticleCaptureJob, CaptureRunResult, LawVersion
from core.pipeline import WorkStage


@dataclass
class ProgressUpdate:
    """작업 하나가 끝날 때마다 화면으로 보내는 소식."""

    finished_count: int
    total_count: int
    description: str
    stage: WorkStage
    detail: str

    @property
    def is_failure(self) -> bool:
        return self.stage is WorkStage.FAILED


@dataclass
class RunFinished:
    """전체 작업이 끝났음을 알리는 소식."""

    result: CaptureRunResult


@dataclass
class RunCrashed:
    """예상하지 못한 문제로 전체가 멈췄음을 알리는 소식."""

    error: Exception


@dataclass
class ArticleTextLoaded:
    """미리보기용 조문(또는 전체) 내용을 다 불러왔음을 알리는 소식."""

    version: LawVersion
    article_numbers: list[ArticleNumber]
    text: str
    # 전체보기면 True. 드래그 시 조문 번호 자동 채움에 쓴다.
    is_full_view: bool = False

    @property
    def article_label(self) -> str:
        if self.is_full_view or not self.article_numbers:
            return "전체"
        return build_article_range_label(self.article_numbers)


@dataclass
class ArticleTextFailed:
    """미리보기용 조문 내용을 불러오지 못했음을 알리는 소식."""

    article_numbers: list[ArticleNumber]
    error: Exception
    is_full_view: bool = False

    @property
    def article_label(self) -> str:
        if self.is_full_view or not self.article_numbers:
            return "전체"
        return build_article_range_label(self.article_numbers)


class LawCaptureController:
    """
    화면의 요청을 받아 기능을 실행하고, 결과를 화면으로 돌려준다.

    화면은 이 클래스의 메서드만 부르고, core 폴더의 파일들을 직접 부르지 않는다.
    """

    def __init__(self):
        self._message_queue: queue.Queue = queue.Queue()
        self._worker_thread: threading.Thread | None = None

    # -- 법령 찾기 (금방 끝나므로 화면 흐름에서 바로 실행한다) --

    def search_laws_by_name(self, query: str) -> list[LawSearchResult]:
        """이름 일부로 법령·고시를 찾는다."""
        return search_laws(query)

    def was_searched_by_former_name(self, query: str, found_law_name: str) -> bool:
        """
        찾아낸 법령이 '지금은 안 쓰는 옛 이름' 으로 걸린 것인지 알려준다.

        화면이 '그 이름은 옛 이름입니다' 안내를 띄울지 정하는 데 쓴다.
        """
        return was_found_by_former_name(query, found_law_name)

    def list_versions(self, law: LawSearchResult) -> list[LawVersion]:
        """개정 이력 전체를 시행일 오래된 순으로 가져온다."""
        return list_all_versions(law)

    def find_versions_in_period(
        self, law: LawSearchResult, period_start: date, period_end: date
    ) -> list[LawVersion]:
        """기간 안에 시행된 개정본을 가져온다."""
        return find_versions_effective_between(law, DatePeriod(period_start, period_end))

    def find_single_version(self, law: LawSearchResult, reference_date: date) -> LawVersion:
        """특정 시점에 시행 중이던 판 하나를 가져온다."""
        return find_version_effective_on(law, reference_date)

    # -- 즐겨찾기 (파일만 다루므로 화면 흐름에서 바로 실행한다) --

    def list_favorites(self) -> list[FavoriteLaw]:
        """저장된 즐겨찾기 목록을 읽는다."""
        return load_favorites()

    def add_favorite_law(self, favorite: FavoriteLaw) -> list[FavoriteLaw]:
        """즐겨찾기에 한 건을 넣고, 갱신된 목록을 돌려준다."""
        return add_favorite(favorite)

    def remove_favorite_law(self, favorite: FavoriteLaw) -> list[FavoriteLaw]:
        """즐겨찾기에서 한 건을 빼고, 갱신된 목록을 돌려준다."""
        return remove_favorite(favorite)

    def resolve_favorite_to_search_result(
        self, favorite: FavoriteLaw
    ) -> LawSearchResult:
        """
        즐겨찾기를 검색 결과로 바꾼다.

        즐겨찾기에는 개정본 번호가 없다. 이름으로 다시 찾아
        law_id(또는 이름+갈래)가 같은 것을 고른다.
        """
        candidates = search_laws(favorite.law_name, favorite.source_kind)
        for candidate in candidates:
            if favorite.law_id and candidate.law_id == favorite.law_id:
                return candidate
            if (
                not favorite.law_id
                and candidate.law_name == favorite.law_name
                and candidate.source_kind is favorite.source_kind
            ):
                return candidate

        # law_id 로 못 찾으면 이름 완전 일치하는 첫 결과를 쓴다.
        for candidate in candidates:
            if candidate.law_name == favorite.law_name:
                return candidate

        if candidates:
            return candidates[0]

        raise LawCaptureError(
            f"즐겨찾기 '{favorite.law_name}' 을(를) 다시 찾지 못했습니다. "
            "이름을 검색해 주세요."
        )

    # -- 미리보기용 조문 내용 (0.5초 남짓이지만 인터넷을 쓰므로 별도 흐름에서) --

    def start_loading_article_text(
        self, version: LawVersion, article_numbers: list[ArticleNumber]
    ) -> None:
        """
        미리보기에 보여줄 조문 내용을 불러온다.

        보통 1초 안에 끝나지만 인터넷이 느릴 수도 있어 별도 흐름에서 돌린다.
        그래야 불러오는 동안에도 창이 멈추지 않는다.
        """
        threading.Thread(
            target=self._load_article_text_in_background,
            args=(version, article_numbers),
            daemon=True,
        ).start()

    def start_loading_full_law_text(self, version: LawVersion) -> None:
        """미리보기에 보여줄 본문 전체를 불러온다. (전체보기)"""
        threading.Thread(
            target=self._load_full_law_text_in_background,
            args=(version,),
            daemon=True,
        ).start()

    def _load_article_text_in_background(
        self, version: LawVersion, article_numbers: list[ArticleNumber]
    ) -> None:
        try:
            text = fetch_article_text(version, article_numbers)
            self._message_queue.put(
                ArticleTextLoaded(version, article_numbers, text, is_full_view=False)
            )
        except Exception as error:
            # 미리보기가 안 되더라도 프로그램 전체가 멈추면 안 된다.
            # 사용자는 지금처럼 문구를 직접 적어 넣으면 된다.
            self._message_queue.put(
                ArticleTextFailed(article_numbers, error, is_full_view=False)
            )

    def _load_full_law_text_in_background(self, version: LawVersion) -> None:
        try:
            text = fetch_full_law_text(version)
            self._message_queue.put(
                ArticleTextLoaded(version, [], text, is_full_view=True)
            )
        except Exception as error:
            self._message_queue.put(
                ArticleTextFailed([], error, is_full_view=True)
            )

    # -- 실제 캡처 작업 (오래 걸리므로 별도 흐름에서 실행한다) --

    @property
    def is_running(self) -> bool:
        return self._worker_thread is not None and self._worker_thread.is_alive()

    def start_capture(self, jobs: list[ArticleCaptureJob], result_path: Path) -> None:
        """캡처 작업을 시작한다. 창이 얼지 않도록 별도 흐름에서 돌린다."""
        if self.is_running:
            return

        self._worker_thread = threading.Thread(
            target=self._run_capture_in_background,
            args=(jobs, result_path),
            daemon=True,  # 창을 닫으면 작업도 함께 정리되도록
        )
        self._worker_thread.start()

    def _run_capture_in_background(
        self, jobs: list[ArticleCaptureJob], result_path: Path
    ) -> None:
        try:
            result = pipeline.run_capture_jobs(jobs, result_path, self._report_progress)
            self._message_queue.put(RunFinished(result))
        except LawCaptureError as error:
            self._message_queue.put(RunCrashed(error))
        except Exception as error:
            # 예상하지 못한 문제도 화면에 알려야 한다. 조용히 사라지면 안 된다.
            self._message_queue.put(RunCrashed(error))

    def _report_progress(
        self, task_index: int, total_count: int, task, stage: WorkStage, detail: str
    ) -> None:
        self._message_queue.put(
            ProgressUpdate(
                finished_count=task_index,
                total_count=total_count,
                description=str(task),
                stage=stage,
                detail=detail,
            )
        )

    def drain_messages(self, handle_message: Callable[[object], None]) -> None:
        """
        쌓여 있는 소식을 화면에 전달한다.

        화면 쪽에서 짧은 간격으로 이 함수를 부른다.
        별도 흐름에서 창을 직접 건드리면 프로그램이 불안정해지므로,
        소식을 상자에 넣어두고 화면 흐름이 꺼내 가는 방식을 쓴다.
        """
        while True:
            try:
                handle_message(self._message_queue.get_nowait())
            except queue.Empty:
                return
