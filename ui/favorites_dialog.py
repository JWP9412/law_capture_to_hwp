"""
즐겨찾기 설정 창.

자주 쓰는 법령·고시를 목록으로 보고, 추가·제거한 뒤 [적용]으로
메인 화면의 법령 선택에 바로 반영한다.

왜 별도 창인가:
  메인 화면의 Combobox 옆에 ★추가/삭제만 두면 목록이 길 때 관리가 불편하다.
  설정 창에서 검색→추가→제거→적용을 한곳에서 하게 한다.
"""
from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, ttk

from core.errors import LawCaptureError
from core.favorites import FavoriteLaw
from core.law_source import LawSearchResult
from ui import theme


class FavoritesSettingsDialog(tk.Toplevel):
    """
    즐겨찾기 목록을 다루는 작은 설정 창.

    버튼 역할:
      추가  — 아래 검색으로 고른 법령을 목록에 넣는다
      제거  — 목록에서 고른 항목을 지운다
      적용  — 목록에서 고른 항목을 메인 화면 법령으로 쓰고 창을 닫는다
      닫기  — 저장은 이미 되어 있으니 창만 닫는다 (추가·제거는 즉시 파일에 반영됨)
    """

    def __init__(
        self,
        parent,
        controller,
        on_applied: Callable[[FavoriteLaw], None],
    ):
        super().__init__(parent)
        self.title("즐겨찾기 설정")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)
        self.configure(bg=theme.WINDOW_BACKGROUND)

        self._controller = controller
        self._on_applied = on_applied
        self._favorites: list[FavoriteLaw] = []
        self._search_candidates: list[LawSearchResult] = []

        self._build_body()
        self._reload_list()
        self.protocol("WM_DELETE_WINDOW", self._close)

        # 부모 창 가운데쯤에 띄운다.
        self.update_idletasks()
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        self.geometry(f"+{parent_x + 80}+{parent_y + 80}")

    def _build_body(self) -> None:
        padding = ttk.Frame(self, padding=12)
        padding.pack(fill="both", expand=True)

        ttk.Label(
            padding,
            text="자주 쓰는 법령·고시 목록입니다. 고른 뒤 [적용]을 누르면 메인 화면에 반영됩니다.",
            style="Hint.TLabel",
            wraplength=420,
        ).pack(anchor="w", pady=(0, 8))

        list_frame = ttk.Frame(padding)
        list_frame.pack(fill="both", expand=True)
        list_frame.grid_columnconfigure(0, weight=1)

        self._listbox = tk.Listbox(
            list_frame,
            height=10,
            width=48,
            activestyle="dotbox",
            exportselection=False,
            font=("맑은 고딕", 10),
        )
        scrollbar = ttk.Scrollbar(list_frame, command=self._listbox.yview)
        self._listbox.configure(yscrollcommand=scrollbar.set)
        self._listbox.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self._listbox.bind("<Double-Button-1>", lambda _event: self._apply_selected())

        # --- 검색으로 추가 ---
        search_box = ttk.LabelFrame(padding, text="목록에 추가할 법령 찾기", padding=8)
        search_box.pack(fill="x", pady=(10, 0))
        search_box.grid_columnconfigure(0, weight=1)

        search_row = ttk.Frame(search_box)
        search_row.grid(row=0, column=0, sticky="ew")
        search_row.grid_columnconfigure(0, weight=1)
        self._search_entry = ttk.Entry(search_row)
        self._search_entry.grid(row=0, column=0, sticky="ew")
        self._search_entry.bind("<Return>", lambda _event: self._search_laws())
        ttk.Button(search_row, text="검색", command=self._search_laws).grid(
            row=0, column=1, padx=(6, 0)
        )

        self._search_picker = ttk.Combobox(search_box, state="disabled")
        self._search_picker.grid(row=1, column=0, sticky="ew", pady=(6, 0))

        self._search_status = ttk.Label(search_box, text="", style="Hint.TLabel")
        self._search_status.grid(row=2, column=0, sticky="w", pady=(4, 0))

        # --- 버튼 줄 ---
        button_row = ttk.Frame(padding)
        button_row.pack(fill="x", pady=(12, 0))

        ttk.Button(button_row, text="추가", command=self._add_from_search).pack(
            side="left"
        )
        ttk.Button(button_row, text="제거", command=self._remove_selected).pack(
            side="left", padx=(6, 0)
        )

        ttk.Button(button_row, text="닫기", command=self._close).pack(side="right")
        ttk.Button(
            button_row, text="적용", command=self._apply_selected, style="Primary.TButton"
        ).pack(side="right", padx=(0, 6))

    def _reload_list(self, select_favorite: FavoriteLaw | None = None) -> None:
        """파일에서 목록을 다시 읽어 Listbox 에 채운다."""
        self._favorites = self._controller.list_favorites()
        self._listbox.delete(0, tk.END)
        for item in self._favorites:
            self._listbox.insert(tk.END, item.display_label())

        if select_favorite is not None:
            for index, item in enumerate(self._favorites):
                if item.is_same_law_as(select_favorite):
                    self._listbox.selection_clear(0, tk.END)
                    self._listbox.selection_set(index)
                    self._listbox.see(index)
                    break

    def _search_laws(self) -> None:
        """설정 창 안에서 법령을 검색해 추가 후보를 채운다."""
        query = self._search_entry.get().strip()
        if not query:
            messagebox.showinfo("즐겨찾기", "찾을 법령·고시 이름을 넣어주세요.", parent=self)
            return

        try:
            candidates = self._controller.search_laws_by_name(query)
        except LawCaptureError as error:
            self._search_candidates = []
            self._search_picker.configure(values=[], state="disabled")
            self._search_picker.set("")
            self._search_status.config(text=str(error), foreground=theme.TEXT_DANGER)
            return

        self._search_candidates = candidates
        self._search_picker.configure(
            values=[str(item) for item in candidates],
            state="readonly",
        )
        self._search_picker.current(0)
        if len(candidates) == 1:
            self._search_status.config(
                text="이 법령을 [추가]로 넣을 수 있습니다.",
                foreground=theme.TEXT_HINT,
            )
        else:
            self._search_status.config(
                text=f"{len(candidates)}건을 찾았습니다. 목록에서 고른 뒤 [추가]를 누르세요.",
                foreground=theme.TEXT_HINT,
            )

    def _add_from_search(self) -> None:
        """검색 결과에서 고른 법령을 즐겨찾기에 넣는다."""
        index = self._search_picker.current()
        if not (0 <= index < len(self._search_candidates)):
            messagebox.showinfo(
                "즐겨찾기",
                "먼저 위에서 법령을 검색해 골라주세요.",
                parent=self,
            )
            return
        self._add_law_result(self._search_candidates[index])

    def _add_law_result(self, law: LawSearchResult) -> None:
        favorite = FavoriteLaw(
            law_name=law.law_name,
            law_id=law.law_id,
            source_kind=law.source_kind,
            kind_label=law.kind_label,
        )
        before_count = len(self._favorites)
        self._controller.add_favorite_law(favorite)
        self._reload_list(select_favorite=favorite)
        if len(self._favorites) == before_count:
            messagebox.showinfo("즐겨찾기", "이미 목록에 있는 법령입니다.", parent=self)
        else:
            self._search_status.config(
                text=f"'{favorite.law_name}' 을(를) 추가했습니다.",
                foreground=theme.TEXT_HINT,
            )

    def _remove_selected(self) -> None:
        """목록에서 고른 즐겨찾기를 지운다."""
        selection = self._listbox.curselection()
        if not selection:
            messagebox.showinfo("즐겨찾기", "지울 항목을 목록에서 고르세요.", parent=self)
            return

        index = selection[0]
        target = self._favorites[index]
        should_remove = messagebox.askyesno(
            "즐겨찾기 제거",
            f"'{target.law_name}' 을(를) 즐겨찾기에서 지울까요?",
            parent=self,
        )
        if not should_remove:
            return

        self._controller.remove_favorite_law(target)
        self._reload_list()
        self._search_status.config(
            text=f"'{target.law_name}' 을(를) 지웠습니다.",
            foreground=theme.TEXT_HINT,
        )

    def _apply_selected(self) -> None:
        """고른 즐겨찾기를 메인 화면에 반영하고 창을 닫는다."""
        selection = self._listbox.curselection()
        if not selection:
            messagebox.showinfo(
                "즐겨찾기",
                "적용할 항목을 목록에서 고르세요.\n(더블클릭으로도 적용됩니다)",
                parent=self,
            )
            return

        favorite = self._favorites[selection[0]]
        self._on_applied(favorite)
        self._close()

    def _close(self) -> None:
        self.grab_release()
        self.destroy()
