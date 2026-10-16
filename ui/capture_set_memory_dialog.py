"""
사용자 지정 SET 설정 창.

세트 이름을 만들고 바꾸거나 지우고, 이미 넣은 항목의 조문·밑줄·색을 고친다.
항목을 새로 넣는 일은 하지 않는다. 미리보기가 없는 창에서 문장을 고르면
틀린 밑줄이 저장되기 쉽다. 새 항목은 메인 화면에서 미리보기로 담은 뒤
[현재 SET에 추가] 로 넣는다.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from config import DEFAULT_UNDERLINE_COLOR_NAME, UNDERLINE_COLOR_CHOICES
from core.article_number import parse_article_numbers
from core.capture_set_memory import CaptureMemorySet
from ui import theme


class CaptureSetMemoryDialog(tk.Toplevel):
    """
    저장된 세트를 고치고 지우는 창.

    세트 추가·이름 변경·삭제, 항목 수정·제거는 누르는 즉시 파일에 반영된다.
    """

    def __init__(self, parent, controller):
        super().__init__(parent)
        self.title("사용자 지정 SET 설정")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)
        self.configure(bg=theme.WINDOW_BACKGROUND)

        self._controller = controller
        self._sets: list[CaptureMemorySet] = []

        self._build_body()
        self._reload_sets()
        self.protocol("WM_DELETE_WINDOW", self._close)

        self.update_idletasks()
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        self.geometry(f"+{parent_x + 40}+{parent_y + 40}")

    def _build_body(self) -> None:
        padding = ttk.Frame(self, padding=12)
        padding.pack(fill="both", expand=True)

        ttk.Label(
            padding,
            text=(
                "세트를 만들고 이름을 바꾸거나 지웁니다. "
                "조문·밑줄·색은 오른쪽에서 고친 뒤 [수정 저장]을 누르세요. "
                "새 법령은 메인 화면 미리보기로 담은 뒤 [현재 SET에 추가]로 넣습니다."
            ),
            style="Hint.TLabel",
            wraplength=640,
        ).pack(anchor="w", pady=(0, 8))

        columns = ttk.Frame(padding)
        columns.pack(fill="both", expand=True)

        set_box = ttk.LabelFrame(columns, text="세트 이름", padding=8)
        set_box.grid(row=0, column=0, sticky="ns", padx=(0, 8))
        self._set_listbox = tk.Listbox(
            set_box,
            height=12,
            width=28,
            activestyle="dotbox",
            exportselection=False,
            font=("맑은 고딕", 10),
        )
        self._set_listbox.pack(fill="both", expand=True)
        self._set_listbox.bind("<<ListboxSelect>>", lambda _event: self._show_selected_set_items())

        set_buttons = ttk.Frame(set_box)
        set_buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(set_buttons, text="새 세트", command=self._create_set).pack(side="left")
        ttk.Button(set_buttons, text="이름 바꾸기", command=self._rename_set).pack(
            side="left", padx=(6, 0)
        )
        ttk.Button(set_buttons, text="세트 삭제", command=self._remove_set).pack(
            side="left", padx=(6, 0)
        )

        item_box = ttk.LabelFrame(columns, text="이 세트의 법령", padding=8)
        item_box.grid(row=0, column=1, sticky="nsew")
        columns.grid_columnconfigure(1, weight=1)
        item_box.grid_columnconfigure(1, weight=1)

        self._item_listbox = tk.Listbox(
            item_box,
            height=8,
            width=52,
            activestyle="dotbox",
            exportselection=False,
            font=("맑은 고딕", 10),
        )
        self._item_listbox.grid(row=0, column=0, columnspan=2, sticky="nsew")
        self._item_listbox.bind("<<ListboxSelect>>", lambda _event: self._fill_edit_fields())

        ttk.Label(item_box, text="법령").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self._law_name_label = ttk.Label(item_box, text="항목을 고르면 법령 이름이 나옵니다.")
        self._law_name_label.grid(row=1, column=1, sticky="w", pady=(8, 0))

        ttk.Label(item_box, text="조문").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=(6, 0))
        self._article_entry = ttk.Entry(item_box)
        self._article_entry.grid(row=2, column=1, sticky="ew", pady=(6, 0))

        ttk.Label(item_box, text="밑줄").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=(6, 0))
        self._underline_entry = ttk.Entry(item_box)
        self._underline_entry.grid(row=3, column=1, sticky="ew", pady=(6, 0))

        ttk.Label(item_box, text="밑줄 색").grid(
            row=4, column=0, sticky="w", padx=(0, 8), pady=(6, 0)
        )
        self._color_picker = ttk.Combobox(
            item_box,
            state="readonly",
            values=[name for name, _rgb in UNDERLINE_COLOR_CHOICES],
            width=8,
        )
        self._color_picker.set(DEFAULT_UNDERLINE_COLOR_NAME)
        self._color_picker.grid(row=4, column=1, sticky="w", pady=(6, 0))

        self._status_label = ttk.Label(
            item_box,
            text="밑줄이 여러 개면 ; 로 구분합니다. 법령 자체는 여기서 바꾸지 않습니다.",
            style="Hint.TLabel",
            wraplength=420,
        )
        self._status_label.grid(row=5, column=1, sticky="w", pady=(6, 0))

        item_buttons = ttk.Frame(item_box)
        item_buttons.grid(row=6, column=1, sticky="w", pady=(8, 0))
        ttk.Button(item_buttons, text="수정 저장", command=self._save_item_edit).pack(side="left")
        ttk.Button(item_buttons, text="항목 제거", command=self._remove_item).pack(
            side="left", padx=(6, 0)
        )

        button_row = ttk.Frame(padding)
        button_row.pack(fill="x", pady=(12, 0))
        ttk.Button(button_row, text="닫기", command=self._close).pack(side="right")

    def _reload_sets(self, select_name: str | None = None, select_item_index: int | None = None) -> None:
        """파일에서 세트 목록을 다시 읽어 왼쪽에 채운다."""
        self._sets = self._controller.list_capture_memory_sets()
        self._set_listbox.delete(0, tk.END)
        for memory_set in self._sets:
            self._set_listbox.insert(tk.END, memory_set.name)

        if not self._sets:
            self._item_listbox.delete(0, tk.END)
            self._clear_edit_fields()
            return

        selected_index = 0
        if select_name is not None:
            for index, memory_set in enumerate(self._sets):
                if memory_set.name == select_name:
                    selected_index = index
                    break
        self._set_listbox.selection_clear(0, tk.END)
        self._set_listbox.selection_set(selected_index)
        self._set_listbox.see(selected_index)
        self._show_selected_set_items(select_item_index)

    def _selected_set(self) -> CaptureMemorySet | None:
        selection = self._set_listbox.curselection()
        if not selection:
            return None
        index = selection[0]
        if not (0 <= index < len(self._sets)):
            return None
        return self._sets[index]

    def _show_selected_set_items(self, select_item_index: int | None = None) -> None:
        """왼쪽에서 고른 세트의 항목을 오른쪽에 보여 준다."""
        self._item_listbox.delete(0, tk.END)
        memory_set = self._selected_set()
        if memory_set is None:
            self._clear_edit_fields()
            return
        for item in memory_set.items:
            self._item_listbox.insert(tk.END, item.display_label())
        if memory_set.items and select_item_index is not None:
            if 0 <= select_item_index < len(memory_set.items):
                self._item_listbox.selection_set(select_item_index)
                self._item_listbox.see(select_item_index)
        self._fill_edit_fields()

    def _clear_edit_fields(self) -> None:
        self._law_name_label.config(text="항목을 고르면 법령 이름이 나옵니다.")
        self._article_entry.delete(0, tk.END)
        self._underline_entry.delete(0, tk.END)
        self._color_picker.set(DEFAULT_UNDERLINE_COLOR_NAME)

    def _fill_edit_fields(self) -> None:
        """고른 항목의 조문·밑줄·색을 수정 칸에 채운다. 법령 이름은 보여 주기만 한다."""
        memory_set = self._selected_set()
        selection = self._item_listbox.curselection()
        if memory_set is None or not selection:
            self._clear_edit_fields()
            return
        item = memory_set.items[selection[0]]
        self._law_name_label.config(text=f"{item.law_name} ({item.kind_label})")
        self._article_entry.delete(0, tk.END)
        self._article_entry.insert(0, item.article_text)
        self._underline_entry.delete(0, tk.END)
        self._underline_entry.insert(0, "; ".join(item.underline_phrases))
        color_name = item.underline_color_name or DEFAULT_UNDERLINE_COLOR_NAME
        known_names = [name for name, _rgb in UNDERLINE_COLOR_CHOICES]
        self._color_picker.set(
            color_name if color_name in known_names else DEFAULT_UNDERLINE_COLOR_NAME
        )

    def _create_set(self) -> None:
        name = simpledialog.askstring("새 세트", "세트 이름을 입력하세요.", parent=self)
        if name is None:
            return
        cleaned = name.strip()
        if not cleaned:
            messagebox.showinfo("사용자 지정 SET", "세트 이름을 넣어주세요.", parent=self)
            return
        before = {memory_set.name for memory_set in self._sets}
        self._controller.add_capture_memory_set(cleaned)
        self._reload_sets(select_name=cleaned)
        names_after = {memory_set.name for memory_set in self._sets}
        if cleaned in before:
            messagebox.showinfo("사용자 지정 SET", "같은 이름의 세트가 이미 있습니다.", parent=self)
        elif cleaned in names_after:
            self._status_label.config(
                text=f"'{cleaned}' 세트를 만들었습니다. 법령은 메인 화면에서 담아 추가하세요.",
                foreground=theme.TEXT_HINT,
            )

    def _rename_set(self) -> None:
        memory_set = self._selected_set()
        if memory_set is None:
            messagebox.showinfo("사용자 지정 SET", "이름을 바꿀 세트를 고르세요.", parent=self)
            return
        new_name = simpledialog.askstring(
            "이름 바꾸기",
            "새 세트 이름을 입력하세요.",
            initialvalue=memory_set.name,
            parent=self,
        )
        if new_name is None:
            return
        cleaned = new_name.strip()
        if not cleaned:
            messagebox.showinfo("사용자 지정 SET", "세트 이름을 넣어주세요.", parent=self)
            return
        self._controller.rename_capture_memory_set(memory_set.name, cleaned)
        self._reload_sets(select_name=cleaned)
        if not any(item.name == cleaned for item in self._sets):
            messagebox.showinfo(
                "사용자 지정 SET",
                "그 이름은 이미 다른 세트가 쓰고 있습니다.",
                parent=self,
            )

    def _remove_set(self) -> None:
        memory_set = self._selected_set()
        if memory_set is None:
            messagebox.showinfo("사용자 지정 SET", "지울 세트를 고르세요.", parent=self)
            return
        should_remove = messagebox.askyesno(
            "세트 삭제",
            f"'{memory_set.name}' 세트와 안의 법령을 모두 지울까요?",
            parent=self,
        )
        if not should_remove:
            return
        self._controller.remove_capture_memory_set(memory_set.name)
        self._reload_sets()

    def _save_item_edit(self) -> None:
        """고른 항목의 조문·밑줄·색만 저장한다. 법령 번호는 건드리지 않는다."""
        memory_set = self._selected_set()
        selection = self._item_listbox.curselection()
        if memory_set is None or not selection:
            messagebox.showinfo("사용자 지정 SET", "수정할 항목을 오른쪽 목록에서 고르세요.", parent=self)
            return

        article_text = self._article_entry.get().strip()
        try:
            parse_article_numbers(article_text)
        except ValueError as error:
            messagebox.showinfo("사용자 지정 SET", str(error), parent=self)
            return

        item_index = selection[0]
        saved_law_id = memory_set.items[item_index].law_id
        was_saved = self._controller.update_capture_memory_item_details(
            memory_set.name,
            item_index,
            article_text,
            tuple(_split_underline_phrases(self._underline_entry.get())),
            self._color_picker.get() or DEFAULT_UNDERLINE_COLOR_NAME,
        )
        if not was_saved:
            messagebox.showinfo(
                "사용자 지정 SET",
                "같은 법령·같은 조문이 이미 이 세트에 있어 저장하지 않았습니다.",
                parent=self,
            )
            return

        self._reload_sets(select_name=memory_set.name, select_item_index=item_index)
        updated = self._selected_set()
        if updated is not None and item_index < len(updated.items):
            if updated.items[item_index].law_id != saved_law_id:
                self._status_label.config(
                    text="법령 번호가 바뀌었습니다. 이 수정은 조문만 바꿔야 합니다.",
                    foreground=theme.TEXT_DANGER,
                )
                return
        self._status_label.config(text="조문·밑줄·색을 저장했습니다.", foreground=theme.TEXT_HINT)

    def _remove_item(self) -> None:
        memory_set = self._selected_set()
        selection = self._item_listbox.curselection()
        if memory_set is None or not selection:
            messagebox.showinfo("사용자 지정 SET", "지울 항목을 오른쪽 목록에서 고르세요.", parent=self)
            return
        item_index = selection[0]
        target = memory_set.items[item_index]
        should_remove = messagebox.askyesno(
            "항목 제거",
            f"'{target.law_name}' {target.article_text} 을(를) 세트에서 지울까요?",
            parent=self,
        )
        if not should_remove:
            return
        self._controller.remove_capture_memory_item(memory_set.name, item_index)
        self._reload_sets(select_name=memory_set.name)

    def _close(self) -> None:
        self.grab_release()
        self.destroy()


def _split_underline_phrases(text: str) -> list[str]:
    """밑줄 칸을 여러 문구로 나눈다. 세미콜론이 없으면 한 문구다."""
    phrases: list[str] = []
    for part in text.replace("；", ";").split(";"):
        cleaned = part.strip()
        if cleaned and cleaned not in phrases:
            phrases.append(cleaned)
    return phrases
