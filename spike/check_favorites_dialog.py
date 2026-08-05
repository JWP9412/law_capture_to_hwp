"""즐겨찾기 설정 창이 뜨고 추가·제거·적용이 되는지 확인한다. (한글 안 켬)"""
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from config import LawSourceKind
from core.favorites import FavoriteLaw, add_favorite, load_favorites
from core.law_source import LawSearchResult
from datetime import date
import tkinter as tk
from ui.app_window import AppWindow
from ui.favorites_dialog import FavoritesSettingsDialog


def report(label: str, is_ok: bool, detail: str = "") -> bool:
    print(f"  [{'OK  ' if is_ok else '실패'}] {label}" + (f"  -- {detail}" if detail else ""))
    return is_ok


all_passed = True

with tempfile.TemporaryDirectory() as temporary_folder:
    favorites_path = Path(temporary_folder) / "fav.json"

    print("=== 1. 설정 창 열기 ===")
    with patch.object(config, "FAVORITES_FILE_PATH", favorites_path):
        window = AppWindow()
        window.update()
        view = window._input_view

        applied: list[FavoriteLaw] = []

        sample_law = LawSearchResult(
            source_kind=LawSourceKind.ADMINISTRATIVE_RULE,
            version_id="2100000254050",
            law_id="111",
            law_name="하자판정기준",
            effective_date=date(2025, 2, 3),
            kind_label="고시",
            promulgation_label="시험",
        )

        dialog = FavoritesSettingsDialog(
            parent=window,
            controller=view._controller,
            on_applied=lambda favorite: applied.append(favorite),
        )
        dialog.update()
        all_passed &= report("설정 창이 떴는가", dialog.winfo_exists() == 1)

        print("\n=== 2. 검색 결과로 추가 ===")
        dialog._search_candidates = [sample_law]
        dialog._search_picker.configure(values=[str(sample_law)], state="readonly")
        dialog._search_picker.current(0)
        dialog._add_from_search()
        dialog.update()
        favorites = load_favorites(favorites_path)
        all_passed &= report("추가 후 1건", len(favorites) == 1, str(len(favorites)))
        all_passed &= report(
            "목록에 표시",
            dialog._listbox.size() == 1,
            str(dialog._listbox.size()),
        )

        print("\n=== 3. 중복 추가 ===")
        with patch("ui.favorites_dialog.messagebox.showinfo"):
            dialog._add_from_search()
        favorites = load_favorites(favorites_path)
        all_passed &= report("중복이면 그대로 1건", len(favorites) == 1)

        print("\n=== 4. 적용 ===")
        dialog._listbox.selection_set(0)
        dialog._apply_selected()
        window.update()
        all_passed &= report("적용 콜백이 불렸는가", len(applied) == 1)
        all_passed &= report(
            "적용 후 창이 닫혔는가",
            not dialog.winfo_exists(),
        )

        # 다시 열어 제거 확인
        add_favorite(
            FavoriteLaw(
                law_name="공동주택관리법",
                law_id="222",
                source_kind=LawSourceKind.STATUTE,
                kind_label="법률",
            ),
            favorites_path,
        )
        dialog2 = FavoritesSettingsDialog(
            parent=window,
            controller=view._controller,
            on_applied=lambda _favorite: None,
        )
        dialog2.update()
        all_passed &= report("다시 열면 2건", dialog2._listbox.size() == 2)

        print("\n=== 5. 제거 ===")
        dialog2._listbox.selection_set(0)
        with patch("ui.favorites_dialog.messagebox.askyesno", return_value=True):
            dialog2._remove_selected()
        all_passed &= report(
            "제거 후 1건",
            dialog2._listbox.size() == 1,
            str(dialog2._listbox.size()),
        )
        dialog2._close()

        print("\n=== 6. 메인 [설정] 버튼 ===")
        def iter_widgets(widget):
            yield widget
            for child in widget.winfo_children():
                yield from iter_widgets(child)

        has_settings_button = False
        for widget in iter_widgets(view):
            try:
                if str(widget.cget("text")) == "설정":
                    has_settings_button = True
                    break
            except tk.TclError:
                continue
        all_passed &= report("메인에 [설정] 버튼이 있는가", has_settings_button)

        window.destroy()

print("\n" + "=" * 58)
print("통과" if all_passed else "실패 — 위 목록을 보세요")
sys.exit(0 if all_passed else 1)
