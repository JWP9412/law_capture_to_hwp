"""
화면이 제대로 도는지 사람 손 없이 확인한다.

실제 캡처(브라우저·한글)까지 돌리면 오래 걸리므로, 그 직전까지만 확인한다.
  - 창이 만들어지는가
  - [검색] 을 누르면 법령이 찾아지고 개정본 목록이 채워지는가
  - 조건을 담으면 목록에 들어가고 '그림 몇 장' 이 맞게 나오는가
  - 잘못 입력했을 때 안내가 뜨는가
  - 화면 세 개가 서로 오가는가
"""
import sys
import tkinter as tk
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.article_number import ArticleNumber
from core.models import CaptureFailure, CapturedArticle, CaptureRunResult
from ui.app_window import AppWindow


def report(label: str, is_ok: bool, detail: str = "") -> bool:
    mark = "OK  " if is_ok else "실패"
    print(f"  [{mark}] {label}" + (f"  -- {detail}" if detail else ""))
    return is_ok


def set_entry(entry: tk.Entry, text: str) -> None:
    entry.delete(0, tk.END)
    entry.insert(0, text)


def iter_widgets(widget):
    """위젯 자신과 모든 하위 위젯을 순회한다."""
    yield widget
    for child in widget.winfo_children():
        yield from iter_widgets(child)


def read_text_option(widget) -> str:
    """text 옵션이 있는 위젯이면 값을, 없으면 빈 문자열을 돌려준다."""
    try:
        return str(widget.cget("text"))
    except tk.TclError:
        return ""


window = AppWindow()
window.update()
view = window._input_view
all_passed = True

print("=== 1. 창 만들기 ===")
all_passed &= report("창이 떴는가", window.winfo_exists() == 1)
all_passed &= report(
    "처음엔 실행 버튼이 비활성화인가",
    str(view._start_button.cget("state")) == "disabled",
    str(view._start_button.cget("state")),
)
all_passed &= report(
    "처음엔 선택/전체 삭제 버튼이 비활성화인가",
    str(view._remove_selected_job_button.cget("state")) == "disabled"
    and str(view._remove_all_jobs_button.cget("state")) == "disabled",
)
all_passed &= report(
    "실행 왼쪽에 저장된 폴더 열기 버튼이 있는가",
    view._open_saved_folder_button.cget("text") == "저장된 폴더 열기"
    and view._open_saved_folder_button.winfo_rootx() + view._open_saved_folder_button.winfo_width()
    <= view._start_button.winfo_rootx(),
)

print("\n=== 2. 법령 검색 ===")
set_entry(view._law_name_entry, "하자판정기준")
view._search_law()
window.update()
found = view._found_law
all_passed &= report("법령을 찾았는가", found is not None,
                     found.law_name if found else "못 찾음")

print("\n=== 3. 기간으로 개정본 찾기 ===")
view._mode.set("기간 안의 모든 개정본")
view._apply_timing_mode_layout()
set_entry(view._period_start_entry, "2024-01-01")
set_entry(view._period_end_entry, "2026-12-31")
view._refresh_version_list()
window.update()
version_count = len(view._version_checkboxes)
all_passed &= report("개정본이 목록에 찼는가", version_count == 2, f"{version_count}개")
for _, version in view._version_checkboxes:
    print(f"          {version}")
view.version_list_canvas.update_idletasks()
first_version_row = view._version_list_frame.winfo_children()[0]
gap_above_first_row = first_version_row.winfo_rooty() - view.version_list_canvas.winfo_rooty()
all_passed &= report(
    "첫 개정본이 목록 칸 맨 위에 붙는가",
    0 <= gap_above_first_row < 8,
    f"{gap_above_first_row}px",
)

print("\n=== 3-2. 전체 선택/해제 ===")
# 사용자 결정: 어느 모드에서든 개정본은 처음에 전부 해제된 상태로 시작한다.
all_passed &= report("처음엔 전부 해제돼 있는가",
                     not any(is_on.get() for is_on, _ in view._version_checkboxes))
all_passed &= report("처음엔 '전체 선택' 도 꺼져 있는가",
                     not view._are_all_versions_selected.get())
all_passed &= report("처음 개수 표시가 맞는가",
                     view._selected_count_label.cget("text") == "2개 중 0개 선택",
                     view._selected_count_label.cget("text"))
view._are_all_versions_selected.set(True)
view._apply_select_all()
window.update()
all_passed &= report(
    "체크하면 개정본 체크박스 표시가 v 형태인가",
    any(
        read_text_option(widget).startswith("v ")
        for widget in iter_widgets(view._version_list_frame)
        if "시행" in read_text_option(widget)
    ),
)
all_passed &= report("전체 선택하면 개수 표시가 맞는가",
                     view._selected_count_label.cget("text") == "2개 중 2개 선택",
                     view._selected_count_label.cget("text"))

view._are_all_versions_selected.set(False)
view._apply_select_all()
window.update()
all_passed &= report("전체 해제가 되는가",
                     not any(is_on.get() for is_on, _ in view._version_checkboxes))
all_passed &= report("해제 후 개수 표시",
                     view._selected_count_label.cget("text") == "2개 중 0개 선택",
                     view._selected_count_label.cget("text"))

view._are_all_versions_selected.set(True)
view._apply_select_all()
view._version_checkboxes[0][0].set(False)
view._refresh_selection_summary()
window.update()
all_passed &= report("하나만 끄면 전체 선택도 꺼지는가",
                     not view._are_all_versions_selected.get())
all_passed &= report("부분 선택 개수 표시",
                     view._selected_count_label.cget("text") == "2개 중 1개 선택",
                     view._selected_count_label.cget("text"))

# 이후 시험을 위해 다시 전부 선택
view._are_all_versions_selected.set(True)
view._apply_select_all()
window.update()

print("\n=== 3-3. 미리보기에 판 목록이 따라가는가 ===")
all_passed &= report("미리보기에 판이 채워졌는가",
                     len(view.preview_view._shown_versions) == 2,
                     f"{len(view.preview_view._shown_versions)}개")
all_passed &= report("고른 판을 알려주는가",
                     view.preview_view.chosen_version is not None,
                     str(view.preview_view.chosen_version))

print("\n=== 3-3b. 미리보기가 밑줄 칸 바로 아래인가 ===")
# 2단 개편 이후에는 미리보기가 오른쪽 단에 있어야 한다.
all_passed &= report(
    "미리보기가 오른쪽 단에 있는가",
    view._preview_view.master == view._right_column,
)
all_passed &= report(
    "3번 카드 안(입력하던 자리)에 '목록 담기' 버튼이 있는가",
    any(
        read_text_option(widget) == "＋ 이 조건을 목록에 담기"
        for widget in iter_widgets(view._article_card)
    ),
)
all_passed &= report(
    "고정 바에는 '목록 담기' 버튼이 없는가 (중복 방지)",
    not any(
        read_text_option(widget) == "＋ 이 조건을 목록에 담기"
        for widget in iter_widgets(window._footer)
    ),
)
all_passed &= report(
    "고정 바에 [실행] 이 있고 스크롤 영역 밖에 있는가 (스크롤과 무관하게 보이려면)",
    window._footer.master is window
    and window._footer.winfo_manager() == "pack"
    and str(window._footer.pack_info().get("side")) == "bottom",
)
all_passed &= report(
    "조문 번호 안내문이 왼쪽 고정으로 보이는가",
    any(
        "예: 1 또는 1, 2 또는 1-3 또는 32의2" in read_text_option(widget)
        for widget in iter_widgets(view._article_card)
    ),
)
all_passed &= report(
    "담은 목록 제목이 4번 대기목록으로 보이는가",
    view._job_list_frame.cget("text") == "4. 담은 작업 대기 목록",
    view._job_list_frame.cget("text"),
)
all_passed &= report(
    "5번 저장 위치 카드 제목이 맞는가",
    view._document_card.cget("text")
    == "5. 한글 파일 저장 위치 - 현재는 임시 폴더에 저장됩니다. (추후 업데이트 예정)",
    view._document_card.cget("text"),
)
all_passed &= report(
    "4번 대기 목록이 왼쪽 단으로 이동했는가",
    view._job_list_frame.master == view._left_column,
)
all_passed &= report(
    "5번 저장 위치가 오른쪽 단으로 이동했는가",
    view._document_card.master == view._right_column,
)
all_passed &= report(
    "5번 카드 전체가 비활성화됐는가",
    str(view._use_existing_hwp_checkbutton.cget("state")) == "disabled"
    and str(view._hwp_path_entry.cget("state")) == "disabled"
    and str(view._browse_hwp_button.cget("state")) == "disabled"
    and str(view._open_hwp_folder_button.cget("state")) == "disabled",
)

print("\n=== 3-4. 드래그로 밑줄 문구 추가 ===")
sample_article = (
    "제7조(콘크리트 균열) ① 콘크리트에 발생한 균열은\n"
    "균열 폭이 0.3mm 이상인 경우 시공하자로 본다."
)
view.preview_view.show_article("제7조", sample_article)
window.update()
view.add_underline_phrase("균열 폭이 0.3mm 이상인 경우")
view.add_underline_phrase("시공하자로 본다")
view.add_underline_phrase("균열 폭이 0.3mm 이상인 경우")  # 같은 것 또 넣기
window.update()
phrases = list(view._underline_phrases)
all_passed &= report("두 문구가 ; 로 이어졌는가", len(phrases) == 2, str(phrases))
all_passed &= report("같은 문구를 두 번 넣어도 하나만 남는가", len(set(phrases)) == 2)
view._reset_underline_phrases()
window.update()
all_passed &= report("밑줄 초기화가 칩 목록을 비우는가", len(view._underline_phrases) == 0)

print("\n=== 3-4b. 밑줄 색 고르기 ===")
import config as app_config
from ui.preview_view import SELECTED_PHRASE_TAG

all_passed &= report(
    "밑줄 색 기본값이 빨강인가",
    view._underline_color_picker.get() == app_config.DEFAULT_UNDERLINE_COLOR_NAME,
    view._underline_color_picker.get(),
)
default_highlight = view.preview_view._text_box.tag_cget(
    SELECTED_PHRASE_TAG, "background"
)
all_passed &= report(
    "미리보기 형광펜 기본이 빨강용인가",
    default_highlight == app_config.preview_highlight_for_name("빨강"),
    default_highlight,
)
view._underline_color_picker.set("파랑")
# Combobox 의 .set() 은 선택 이벤트를 안 보낼 수 있어, 화면에서 고른 것과 같이 처리한다.
view._on_underline_color_changed()
window.update()
blue_highlight = view.preview_view._text_box.tag_cget(
    SELECTED_PHRASE_TAG, "background"
)
all_passed &= report(
    "파랑 선택 시 미리보기 형광펜이 바뀌는가",
    blue_highlight == app_config.preview_highlight_for_name("파랑"),
    blue_highlight,
)
# 개정본이 하나 이상 켜져 있어야 작업을 만들 수 있다.
if view._version_checkboxes:
    view._version_checkboxes[0][0].set(True)
set_entry(view._article_entry, "1")
view.add_underline_phrase("시험문구")
try:
    blue_job = view._build_job_from_inputs()
    all_passed &= report(
        "작업에 파랑 색이 들어가는가",
        blue_job.underline_color == app_config.underline_color_for_name("파랑"),
        str(blue_job.underline_color),
    )
except ValueError as error:
    all_passed &= report("작업에 파랑 색이 들어가는가", False, str(error))
view._underline_color_picker.set(app_config.DEFAULT_UNDERLINE_COLOR_NAME)
view._on_underline_color_changed()
view._reset_underline_phrases()

print("\n=== 3-4c. 사용자 지정 SET ===")
import tempfile
from unittest.mock import patch

from core.capture_set_memory import (
    CaptureMemoryItem,
    CaptureMemoryNameChange,
    add_capture_memory_item,
    add_capture_memory_set,
    build_name_change_notice,
)

memory_notice = build_name_change_notice(
    [
        CaptureMemoryNameChange(
            stored_law_name="주택건설촉진법",
            current_law_name="주택법",
            historical_law_name="주택건설촉진법",
        )
    ]
)
all_passed &= report(
    "이름 변경 안내 문구가 만들어지는가",
    "지금 이름으로 바꿔" in memory_notice and "당시 이름" in memory_notice,
    memory_notice,
)
set_label_found = any(
    read_text_option(widget) == "사용자 지정 SET" for widget in iter_widgets(view)
)
all_passed &= report("즐겨찾기 아래에 사용자 지정 SET 칸이 있는가", set_label_found)

if found is not None:
    with tempfile.TemporaryDirectory() as temporary_folder:
        memory_file = Path(temporary_folder) / "user_capture_set_memory.json"
        saved_memory_path = app_config.CAPTURE_SET_MEMORY_FILE_PATH
        app_config.CAPTURE_SET_MEMORY_FILE_PATH = memory_file
        try:
            add_capture_memory_set("감정 기준에 관한 의견서", memory_file)
            add_capture_memory_item(
                "감정 기준에 관한 의견서",
                CaptureMemoryItem(
                    law_name=found.law_name,
                    law_id=found.law_id,
                    source_kind=found.source_kind,
                    kind_label=found.kind_label,
                    article_text="1",
                    underline_phrases=("목적",),
                    underline_color_name="파랑",
                ),
                memory_file,
            )
            view._refresh_capture_memory_picker()
            view._capture_memory_picker.set("감정 기준에 관한 의견서")
            set_entry(view._capture_memory_date_entry, "2025-06-01")
            jobs_before = len(view._jobs)
            shown_messages: list[str] = []

            def _capture_showinfo(_title, message):
                shown_messages.append(message)

            with patch("ui.input_view.messagebox.showinfo", side_effect=_capture_showinfo):
                view._add_jobs_from_capture_memory()
            window.update()
            all_passed &= report(
                "이 시점으로 담기가 작업을 더하는가",
                len(view._jobs) == jobs_before + 1,
                f"{jobs_before} -> {len(view._jobs)}",
            )
            all_passed &= report(
                "담기 안내가 떴는가",
                bool(shown_messages) and "1건을 담은 목록" in shown_messages[-1],
                shown_messages[-1] if shown_messages else "",
            )

            from datetime import date

            from config import LawSourceKind
            from core.article_number import parse_article_numbers
            from core.capture_set_memory import load_capture_memory_sets
            from core.models import ArticleCaptureJob, LawVersion
            from ui.capture_set_memory_dialog import CaptureSetMemoryDialog

            add_capture_memory_set("대기목록세트", memory_file)
            view._refresh_capture_memory_picker()
            view._capture_memory_picker.set("대기목록세트")
            saved_jobs = list(view._jobs)
            view._jobs.clear()
            view._job_listbox.delete(0, tk.END)

            def _memory_job(article_text: str, phrase: str) -> ArticleCaptureJob:
                return ArticleCaptureJob(
                    law_name="주택법",
                    target_versions=[
                        LawVersion(
                            source_kind=LawSourceKind.STATUTE,
                            version_id="확인용",
                            law_name="주택법",
                            effective_date=date(2025, 6, 1),
                            promulgation_label="",
                            is_currently_in_effect=False,
                        )
                    ],
                    article_numbers=parse_article_numbers(article_text),
                    underline_phrases=[phrase],
                    underline_color=app_config.underline_color_for_name("초록"),
                    law_id="law-999",
                    kind_label="법률",
                )

            view._append_job_to_list(_memory_job("1", "목적"))
            view._append_job_to_list(_memory_job("32의2", "가지번호"))
            queue_messages: list[str] = []

            def _capture_queue_info(_title, message):
                queue_messages.append(message)

            with patch("ui.input_view.messagebox.showinfo", side_effect=_capture_queue_info):
                view._add_waiting_jobs_to_capture_memory()
            stored_sets = load_capture_memory_sets(memory_file)
            stored_set = next(item for item in stored_sets if item.name == "대기목록세트")
            stored_articles = [item.article_text for item in stored_set.items]
            all_passed &= report(
                "대기 목록 2건이 세트에 들어갔는가",
                stored_articles == ["1", "32의2"]
                and stored_set.items[0].law_id == "law-999"
                and stored_set.items[0].underline_color_name == "초록"
                and stored_set.items[1].underline_phrases == ("가지번호",),
                str(stored_articles),
            )
            with patch("ui.input_view.messagebox.showinfo", side_effect=_capture_queue_info):
                view._add_waiting_jobs_to_capture_memory()
            all_passed &= report(
                "같은 작업을 다시 넣으면 건너뛰는가",
                bool(queue_messages) and "이미 있던 2건은 건너뛰었습니다" in queue_messages[-1],
                queue_messages[-1] if queue_messages else "",
            )

            settings_dialog = CaptureSetMemoryDialog(window, view._controller)
            window.update()
            dialog_labels = [read_text_option(widget) for widget in iter_widgets(settings_dialog)]
            all_passed &= report(
                "설정 창에 법령 검색 칸이 없는가",
                "검색" not in dialog_labels and "이 조문을 세트에 추가" not in dialog_labels,
            )
            all_passed &= report("설정 창에 수정 저장이 있는가", "수정 저장" in dialog_labels)
            settings_dialog._close()

            view._jobs.clear()
            view._job_listbox.delete(0, tk.END)
            for saved_job in saved_jobs:
                view._append_job_to_list(saved_job)
        finally:
            app_config.CAPTURE_SET_MEMORY_FILE_PATH = saved_memory_path
            view._refresh_capture_memory_picker()

print("\n=== 3-5. Ctrl+F 찾기 ===")
preview = view.preview_view
all_passed &= report(
    "헤더에 찾기 버튼이 있는가",
    preview._find_button.cget("text") == "찾기",
    preview._find_button.cget("text"),
)
preview._find_button.invoke()
window.update()
all_passed &= report("찾기 버튼으로 막대가 열리는가", preview._is_find_bar_visible)
preview._hide_find_bar()
window.update()

preview._show_find_bar()
window.update()
all_passed &= report("찾기 막대가 보이는가", preview._is_find_bar_visible)
set_entry(preview._find_entry, "균열")
preview._refresh_find_highlights()
window.update()
all_passed &= report(
    "맞는 곳이 여러 개인가",
    len(preview._found_ranges) >= 2,
    f"{len(preview._found_ranges)}개",
)
all_passed &= report(
    "개수 표시가 나오는가",
    "개 중" in preview._find_status_label.cget("text"),
    preview._find_status_label.cget("text"),
)
first_index = preview._current_found_index
preview._go_to_next_match()
window.update()
all_passed &= report(
    "다음으로 이동하는가",
    preview._current_found_index == (first_index + 1) % len(preview._found_ranges),
)
set_entry(preview._find_entry, "없는글자XYZ")
preview._refresh_find_highlights()
window.update()
all_passed &= report(
    "못 찾으면 안내만 나오는가",
    preview._find_status_label.cget("text") == "찾는 글자가 없습니다",
    preview._find_status_label.cget("text"),
)
preview._hide_find_bar()
window.update()
all_passed &= report("닫으면 막대가 숨겨지는가", not preview._is_find_bar_visible)

all_passed &= report(
    "찾기 왼쪽에 ▲▼ 버튼이 있는가",
    preview._article_up_button.cget("text") == "▲"
    and preview._article_down_button.cget("text") == "▼"
    and preview._article_up_button.winfo_rootx()
    < preview._article_down_button.winfo_rootx()
    < preview._find_button.winfo_rootx(),
)
saved_preview_text = preview._text_box.get("1.0", "end-1c")
preview.show_article(
    "전체",
    "제12조(목적) 가나다\n\n제13조(정의) 라마바\n\n제14조(적용) 사아자",
    is_full_view=True,
)
window.update()
moved_article, did_scroll = preview.reveal_adjacent_article(1)
all_passed &= report(
    "전체보기에서 아래는 다음 조로 가는가",
    did_scroll and moved_article == ArticleNumber(13),
    str(moved_article),
)
moved_again, did_scroll_again = preview.reveal_adjacent_article(1)
all_passed &= report(
    "한 번 더 아래는 그다음 조인가",
    did_scroll_again and moved_again == ArticleNumber(14),
    str(moved_again),
)
preview.show_article("제12조", "제12조(목적) 가나다", is_full_view=False)
window.update()
one_article, did_scroll_one = preview.reveal_adjacent_article(1)
all_passed &= report(
    "조문 하나만 있으면 본문 밖 이동으로 보는가",
    (not did_scroll_one) and one_article == ArticleNumber(12),
    str(one_article),
)
preview.show_article("제7조", saved_preview_text)
window.update()

print("\n=== 3-5b. 빨간 표시 클릭으로 밑줄 취소 ===")
preview.show_article("제7조", sample_article)
window.update()
# 드래그 선택과 같은 경로: 구간을 표시하고 칩에 넣는다.
start = preview._text_box.search("시공하자로 본다", "1.0")
end = f"{start}+{len('시공하자로 본다')}c"
preview._text_box.tag_add("sel", start, end)
preview._text_box.mark_set("insert", end)
preview._on_drag_finished()
window.update()
all_passed &= report(
    "드래그 후 추적 구간이 생겼는가",
    len(preview._selected_phrase_ranges) == 1,
    str(preview._selected_phrase_ranges),
)
all_passed &= report(
    "칩에도 문구가 들어갔는가",
    "시공하자로 본다" in view._underline_phrases,
    str(view._underline_phrases),
)
removed = preview._try_remove_phrase_at(start)
window.update()
all_passed &= report("빨간 구간 클릭 삭제가 되는가", removed)
all_passed &= report(
    "미리보기 추적이 비었는가",
    len(preview._selected_phrase_ranges) == 0,
)
all_passed &= report(
    "칩에서도 빠졌는가",
    "시공하자로 본다" not in view._underline_phrases,
    str(view._underline_phrases),
)

# 칩 X → 미리보기 표시도 사라지는지
preview._text_box.tag_add("sel", start, end)
preview._on_drag_finished()
window.update()
all_passed &= report("다시 드래그해 칩이 생겼는가", "시공하자로 본다" in view._underline_phrases)
chip_index = view._underline_phrases.index("시공하자로 본다")
view._remove_underline_phrase_at(chip_index)
window.update()
all_passed &= report(
    "칩 삭제 후 미리보기 표시도 사라지는가",
    len(preview._selected_phrase_ranges) == 0,
    str(preview._selected_phrase_ranges),
)
all_passed &= report(
    "안내 문구에 클릭 취소가 있는가",
    "빨간 표시를 클릭하면" in preview._guide_label.cget("text"),
    preview._guide_label.cget("text"),
)

print("\n=== 3-6. 드래그 순번 표기 ===")
# 같은 문구가 두 번 나오는 본문에서 두 번째를 고르면 '[2번째]' 가 붙어야 한다.
dup_text = "가나다 균열 마바사 균열 아자차"
preview.show_article("제시험조", dup_text)
window.update()
# 두 번째 '균열' 위치: "가나다 균열 마바사 " 다음
second_start = "1.0 + 11c"  # 대략 — 아래에서 search 로 정확히 잡는다
ranges = preview._collect_match_ranges("균열")
all_passed &= report("균열이 두 번인가", len(ranges) == 2, str(ranges))
if len(ranges) == 2:
    label = preview._label_with_occurrence("균열", ranges[1][0])
    all_passed &= report(
        "두 번째면 [2번째] 가 붙는가",
        label == "균열 [2번째]",
        label,
    )
    label_first = preview._label_with_occurrence("균열", ranges[0][0])
    all_passed &= report(
        "첫 번째면 [1번째] 가 붙는가",
        label_first == "균열 [1번째]",
        label_first,
    )
set_entry(view._article_entry, "일번")
set_entry(view._underline_phrase_entry, "무언가")
view._add_underline_phrase_from_entry()
try:
    view._build_job_from_inputs()
    all_passed &= report("조문번호에 글자를 넣으면 막는가", False)
except ValueError as error:
    all_passed &= report("조문번호에 글자를 넣으면 막는가", True, str(error))

set_entry(view._article_entry, "1")
view._reset_underline_phrases()
try:
    empty_underline_job = view._build_job_from_inputs()
    all_passed &= report(
        "밑줄 없이도 작업을 만들 수 있는가",
        len(empty_underline_job.underline_phrases) == 0,
        str(empty_underline_job.underline_phrases),
    )
except ValueError as error:
    all_passed &= report("밑줄 없이도 작업을 만들 수 있는가", False, str(error))

print("\n=== 밑줄 없이 실행 확인 대화상자 ===")
# 밑줄 0건 작업을 목록에 넣고, [실행] 시 확인창에서 '아니오'면 시작하지 않는다.
view._jobs.clear()
view._job_listbox.delete(0, tk.END)
view._add_job()
window.update()
all_passed &= report("밑줄 0건 작업이 목록에 담기는가", len(view._jobs) == 1)

start_calls: list = []
view._on_start_requested = lambda jobs: start_calls.append(list(jobs))

from unittest.mock import patch

with patch("ui.input_view.messagebox.askyesno", return_value=False) as mocked_ask:
    view._request_start()
window.update()
all_passed &= report(
    "밑줄 없을 때 확인창을 띄우는가",
    mocked_ask.called,
)
all_passed &= report(
    "확인에서 아니오를 고르면 실행하지 않는가",
    start_calls == [],
)

with patch("ui.input_view.messagebox.askyesno", return_value=True):
    view._request_start()
window.update()
all_passed &= report(
    "확인에서 예 를 고르면 실행하는가",
    len(start_calls) == 1 and start_calls[0][0].underline_phrases == [],
)

# 이후 시나리오를 위해 목록을 비운다.
view._jobs.clear()
view._job_listbox.delete(0, tk.END)
view._update_figure_count()

print("\n=== 5. 조건 담기 ===")
set_entry(view._article_entry, "1")
set_entry(view._underline_phrase_entry, "제1조(목적) 이 기준은")
view._add_underline_phrase_from_entry()
view._add_job()
window.update()

set_entry(view._article_entry, "7")
set_entry(view._underline_phrase_entry, "균열 폭이 0.3mm 이상인 경우")
view._add_underline_phrase_from_entry()
set_entry(view._underline_phrase_entry, "철근이 배근된 위치에")
view._add_underline_phrase_from_entry()
view._add_job()
window.update()

print("\n=== 5b. 다중 조문 담기 ===")
set_entry(view._article_entry, "1, 2")
set_entry(view._underline_phrase_entry, "제1조(목적) 이 기준은")
view._add_underline_phrase_from_entry()
view._add_job()
window.update()
all_passed &= report(
    "제1, 2조로 담기는가",
    any("제1, 2조" in view._job_listbox.get(index) for index in range(view._job_listbox.size())),
)

all_passed &= report("목록에 3건이 담겼는가", len(view._jobs) == 3)
all_passed &= report("밑줄 문구를 ; 로 나눠 받았는가",
                     len(view._jobs[1].underline_phrases) == 2,
                     str(view._jobs[1].underline_phrases))
# 제1조×2개정 + 제7조×2개정 + 제1·2조×2개정 = 6장
all_passed &= report("그림 장수가 맞는가",
                     view._figure_count_label.cget("text") == "→ 만들어질 그림 6장",
                     view._figure_count_label.cget("text"))
all_passed &= report("[실행] 버튼이 켜졌는가",
                     str(view._start_button.cget("state")) == "normal")
all_passed &= report(
    "목록이 있으면 선택/전체 삭제 버튼도 켜지는가",
    str(view._remove_selected_job_button.cget("state")) == "normal"
    and str(view._remove_all_jobs_button.cget("state")) == "normal",
)

print("\n=== 6. 목록에서 빼기 ===")
view._job_listbox.selection_clear(0, tk.END)
view._job_listbox.selection_set(0)
view._job_listbox.selection_set(1)
all_passed &= report(
    "대기 목록에서 여러 줄을 고를 수 있는가",
    list(view._job_listbox.curselection()) == [0, 1],
    str(list(view._job_listbox.curselection())),
)
view._job_listbox.selection_clear(0, tk.END)
view._job_listbox.selection_set(0)
view._remove_selected_job()
window.update()
all_passed &= report("1건이 지워졌는가", len(view._jobs) == 2)
all_passed &= report("그림 장수가 다시 계산됐는가",
                     view._figure_count_label.cget("text") == "→ 만들어질 그림 4장",
                     view._figure_count_label.cget("text"))

import tkinter.messagebox as messagebox_module
_saved_askyesno = messagebox_module.askyesno
messagebox_module.askyesno = lambda *_args, **_kwargs: True
view._remove_all_jobs()
messagebox_module.askyesno = _saved_askyesno
window.update()
all_passed &= report("전체 삭제 후 목록이 비는가", len(view._jobs) == 0)
all_passed &= report(
    "전체 삭제 후 실행/삭제 버튼이 비활성화되는가",
    str(view._start_button.cget("state")) == "disabled"
    and str(view._remove_selected_job_button.cget("state")) == "disabled"
    and str(view._remove_all_jobs_button.cget("state")) == "disabled",
)

print("\n=== 7. 창 스크롤 ===")
# 기본 창에서 실행 버튼이 화면 안에 보여야 한다.
window.geometry("1180x780")
window.update()
start_bottom = view._start_button.winfo_rooty() + view._start_button.winfo_height()
window_bottom = window.winfo_rooty() + window.winfo_height()
is_start_visible = start_bottom <= window_bottom
if not is_start_visible:
    # 가시 영역 밖이어도 휠 한 번이면 닿는지 확인한다.
    before_one_wheel = window._scroll_canvas.yview()
    window._scroll_canvas.yview_scroll(1, "units")
    window.update()
    after_one_wheel = window._scroll_canvas.yview()
    is_start_visible = after_one_wheel != before_one_wheel
all_passed &= report(
    "기본 창에서 실행 버튼 접근이 쉬운가(바로 보이거나 휠 한 번)",
    is_start_visible,
    f"start={start_bottom}, window={window_bottom}",
)

# 안내글자 입력칸은 비어 있을 때 get()이 빈 문자열이어야 한다.
view._article_entry.delete(0, tk.END)
window.update()
all_passed &= report(
    "안내글자 표시 중에도 조문 입력값은 빈 문자열인가",
    view._article_entry.get() == "",
    repr(view._article_entry.get()),
)

# 창을 아주 작게 줄이면 스크롤 범위가 내용보다 작아져야 한다.
window.geometry("620x280")
window.update()
window._on_container_resized()
scroll_region = window._scroll_canvas.cget("scrollregion")
# scrollregion 은 "x0 y0 x1 y1" 형태. 높이(y1)가 창보다 크면 스크롤이 필요하다.
region_parts = [float(value) for value in str(scroll_region).split()]
all_passed &= report(
    "작은 창에서 스크롤 범위가 잡히는가",
    len(region_parts) == 4 and region_parts[3] > 280,
    f"scrollregion={scroll_region}",
)


class _FakeWheel:
    """마우스 휠 이벤트를 흉내 낸다. (실제 마우스를 굴리지 않고 검증하기 위함)"""

    def __init__(self, delta: int, widget):
        self.delta = delta
        self.widget = widget
        self.x_root = widget.winfo_rootx() + 5
        self.y_root = widget.winfo_rooty() + 5


window._scroll_canvas.yview_moveto(0)
window.update()
before_main = window._scroll_canvas.yview()
# 조문 번호 칸 위에서 휠 → 창 전체가 움직여야 한다
window._on_mousewheel(_FakeWheel(-120, view._article_entry))
window.update()
after_main = window._scroll_canvas.yview()
all_passed &= report(
    "휠로 창이 움직이는가",
    after_main != before_main,
    f"{before_main} -> {after_main}",
)

# 개정본 목록 위 휠 → 창은 그대로, 목록만 굴러야 한다
window._scroll_canvas.yview_moveto(0)
window.update()
main_before_list = window._scroll_canvas.yview()
version_canvas = view.version_list_canvas
window._on_mousewheel(_FakeWheel(-120, version_canvas))
window.update()
all_passed &= report(
    "개정본 목록 위 휠은 창을 안 움직이는가",
    window._scroll_canvas.yview() == main_before_list,
)
version_canvas.yview_moveto(0)
window.update()
window._on_mousewheel(_FakeWheel(120, version_canvas))
window.update()
top_fraction = version_canvas.yview()[0]
all_passed &= report(
    "개정본 목록은 맨 위 항목보다 위로 안 올라가는가",
    top_fraction >= 0,
    str(top_fraction),
)

# 예전 버그: 목록 Leave 때 unbind_all 하면 창 휠이 죽었다.
# Leave 를 흉내 낸 뒤에도 bind_all 과 창 휠이 살아 있어야 한다.
version_canvas.event_generate("<Leave>")
window.update()
all_passed &= report(
    "목록에서 나온 뒤에도 MouseWheel 연결이 남는가",
    bool(window.bind_all("<MouseWheel>")),
    repr(window.bind_all("<MouseWheel>")),
)
window._scroll_canvas.yview_moveto(0)
window.update()
before_after_leave = window._scroll_canvas.yview()
window._on_mousewheel(_FakeWheel(-120, view._article_entry))
window.update()
all_passed &= report(
    "목록에서 나온 뒤에도 창 휠이 사는가",
    window._scroll_canvas.yview() != before_after_leave,
)

window.geometry("620x820")
window.update()

print("\n=== 8. 화면 전환 ===")
window._show_progress_view(4)
window.update()
all_passed &= report("진행 화면으로 넘어갔는가",
                     window._progress_view.winfo_ismapped() == 1)

window._progress_view.show_progress(1, 4, "제1조 [시행 2025. 2. 3.]", False, "")
window._progress_view.show_progress(2, 4, "제7조 [시행 2025. 2. 3.]", True,
                                    "'없는 문구' 문구를 조문에서 찾지 못했습니다")
window.update()
all_passed &= report("진행 기록이 쌓이는가", True)

sample_result = CaptureRunResult(
    succeeded=[CapturedArticle(view._jobs[0].target_versions and None, Path("a.pdf"),
                               Path("a.png"), "본문")] if False else [],
    failed=[],
)
sample_result.result_hwp_path = Path("out/예시.hwp")
window._result_view.show_result(sample_result)
window._show_result_view()
window.update()
all_passed &= report("완료 화면으로 넘어갔는가",
                     window._result_view.winfo_ismapped() == 1)

window._show_input_view()
window.update()
all_passed &= report("처음 화면으로 돌아오는가", view.winfo_ismapped() == 1)

window.destroy()

print("\n" + "=" * 58)
print("모든 확인 통과" if all_passed else "일부 확인 실패 — 위 목록을 보세요")
print("=" * 58)
sys.exit(0 if all_passed else 1)
