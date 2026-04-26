import os
import tkinter as tk
from tkinter import ttk, messagebox

from .widgets import ITEMS_PER_PAGE, PLAYER_FILES, LEFT_SIDEBAR_WIDTH


class PlayerListSidebar:
    def __init__(self, parent, redeemer, app_path, log_callback, on_switch_file=None):
        self.parent = parent
        self.redeemer = redeemer
        self.app_path = app_path
        self.log_callback = log_callback
        self.on_switch_file = on_switch_file

        self.frame = ttk.Frame(parent, width=LEFT_SIDEBAR_WIDTH)
        self.frame.pack_propagate(False)

        self.id_checkbox_vars = {}
        self.select_all_var = tk.BooleanVar(value=True)
        self.current_page = 0
        self.total_pages = 0
        self.all_csv_rows = []
        self.current_file_var = tk.StringVar(value=PLAYER_FILES[0])
        self.id_list_items = []

        self._file_checkbox_state = {}
        self._last_file = PLAYER_FILES[0]

        self._build_ui()

    def _build_ui(self):
        header_frame = ttk.Frame(self.frame)
        header_frame.pack(fill=tk.X, padx=8, pady=(8, 4))

        ttk.Label(header_frame, text="玩家列表",
                  font=("Microsoft YaHei UI", 11, "bold")).pack(side=tk.LEFT)

        self.left_close_btn = ttk.Button(header_frame, text="✕", width=3,
                                          command=self.on_close if hasattr(self, 'on_close') else lambda: None)
        self.left_close_btn.pack(side=tk.RIGHT)

        file_selector_frame = ttk.Frame(self.frame)
        file_selector_frame.pack(fill=tk.X, padx=8, pady=(0, 6))

        ttk.Label(file_selector_frame, text="数据文件：",
                  font=("Microsoft YaHei UI", 9)).pack(side=tk.LEFT)

        self.file_combo = ttk.Combobox(file_selector_frame, values=PLAYER_FILES,
                                        textvariable=self.current_file_var,
                                        state="readonly", width=16)
        self.file_combo.pack(side=tk.LEFT, padx=(4, 0))
        self.file_combo.bind("<<ComboboxSelected>>", lambda e: self._switch_file())

        self.file_count_label = tk.Label(file_selector_frame, text="(0 人)",
                                         font=("Microsoft YaHei UI", 8), fg="#888888")
        self.file_count_label.pack(side=tk.LEFT, padx=(4, 0))

        input_frame = ttk.Frame(self.frame)
        input_frame.pack(fill=tk.X, padx=8, pady=(0, 6))

        self.new_id_var = tk.StringVar()
        self.new_id_entry = ttk.Entry(input_frame, textvariable=self.new_id_var, width=15)
        self.new_id_entry.pack(side=tk.LEFT, padx=(0, 4), fill=tk.X, expand=True)
        self.new_id_entry.bind('<Return>', lambda e: self._add_new_id())

        add_btn = ttk.Button(input_frame, text="添加", command=self._add_new_id, width=5)
        add_btn.pack(side=tk.LEFT)

        select_all_frame = ttk.Frame(self.frame)
        select_all_frame.pack(fill=tk.X, padx=8, pady=(2, 0))

        select_all_check = tk.Checkbutton(select_all_frame, text="全选/取消全选",
                                             variable=self.select_all_var,
                                             command=self._on_select_all_changed,
                                             font=("Microsoft YaHei UI", 9))
        select_all_check.pack(side=tk.LEFT)

        self.selected_count_label = tk.Label(select_all_frame, text="已选: 0",
                                               font=("Microsoft YaHei UI", 9),
                                               fg="#1565C0")
        self.selected_count_label.pack(side=tk.RIGHT)

        ttk.Separator(self.frame, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=8, pady=(4, 4))

        list_container = ttk.Frame(self.frame)
        list_container.pack(fill=tk.BOTH, expand=True, padx=8)

        self.id_canvas = tk.Canvas(list_container, highlightthickness=0, bg="#F5F5F5")
        id_scrollbar = ttk.Scrollbar(list_container, orient=tk.VERTICAL,
                                      command=self.id_canvas.yview)
        self.id_inner_frame = tk.Frame(self.id_canvas, bg="#F5F5F5")

        self.id_canvas.create_window((0, 0), window=self.id_inner_frame, anchor=tk.NW, width=260)
        self.id_canvas.configure(yscrollcommand=id_scrollbar.set)

        self.id_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        id_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_mousewheel(ev):
            self.id_canvas.yview_scroll(int(-1 * (ev.delta / 120)), "units")

        def _bound_to_mousewheel(ev):
            self.id_canvas.bind_all("<MouseWheel>", _on_mousewheel)
            self.id_canvas.bind_all("<Button-4>", lambda e: self.id_canvas.yview_scroll(-3, "units"))
            self.id_canvas.bind_all("<Button-5>", lambda e: self.id_canvas.yview_scroll(3, "units"))

        def _unbound_from_mousewheel(ev):
            self.id_canvas.unbind_all("<MouseWheel>")
            self.id_canvas.unbind_all("<Button-4>")
            self.id_canvas.unbind_all("<Button-5>")

        self.id_canvas.bind("<Enter>", _bound_to_mousewheel)
        self.id_canvas.bind("<Leave>", _unbound_from_mousewheel)

        self.page_frame = ttk.Frame(self.frame)
        self.page_frame.pack(fill=tk.X, padx=8, pady=(4, 8))

        self.prev_page_btn = ttk.Button(self.page_frame, text="◀ 上一页",
                                         command=self._prev_page, width=9)
        self.prev_page_btn.pack(side=tk.LEFT)

        self.page_label = tk.Label(self.page_frame, text="第 1/1 页",
                                    font=("Microsoft YaHei UI", 9))
        self.page_label.pack(side=tk.LEFT, padx=6)

        self.next_page_btn = ttk.Button(self.page_frame, text="下一页 ▶",
                                         command=self._next_page, width=9)
        self.next_page_btn.pack(side=tk.RIGHT)

    def _refresh_id_list(self):
        saved_vars = dict(self.id_checkbox_vars)
        saved_page = self.current_page
        saved_scroll = self.id_canvas.yview()

        for item in self.id_list_items:
            item.destroy()
        self.id_list_items.clear()
        self.id_checkbox_vars = saved_vars
        self.current_page = saved_page

        csv_path = self._get_csv_path()
        current_file = self.current_file_var.get()
        if not os.path.exists(csv_path):
            try:
                with open(csv_path, "w", encoding="utf-8-sig", newline=""):
                    pass
                self._log(f"已自动创建数据文件：{current_file}", level='info')
            except Exception:
                pass
            self.all_csv_rows = []
            empty_label = ttk.Label(self.id_inner_frame, text=f"{current_file} 已创建（暂无数据）",
                                    foreground="gray")
            empty_label.pack(anchor=tk.W, pady=4)
            self.id_list_items.append(empty_label)
            self.total_pages = 0
            self.current_page = 0
            self._update_page_controls()
            self._restore_scroll(saved_scroll)
            self._update_file_count_label()
            return

        try:
            self.all_csv_rows = self.redeemer.read_csv_with_names(csv_path)
        except Exception:
            self.all_csv_rows = []

        if not self.all_csv_rows:
            empty_label = ttk.Label(self.id_inner_frame, text="暂无玩家 ID", foreground="gray")
            empty_label.pack(anchor=tk.W, pady=4)
            self.id_list_items.append(empty_label)
            self.total_pages = 0
            self.current_page = 0
            self._update_page_controls()
            self._restore_scroll(saved_scroll)
            self._update_file_count_label()
            return

        self.total_pages = max(1, (len(self.all_csv_rows) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
        if self.current_page >= self.total_pages:
            self.current_page = self.total_pages - 1
        if self.current_page < 0:
            self.current_page = 0

        all_fids = {row["fid"] for row in self.all_csv_rows}
        for fid in all_fids:
            if fid not in self.id_checkbox_vars:
                self.id_checkbox_vars[fid] = tk.BooleanVar(value=self.select_all_var.get())

        self._render_page(keep_state=True)
        self._update_page_controls()
        self._update_selected_count()
        self._restore_scroll(saved_scroll)
        self._update_file_count_label()

    def _render_page(self, keep_state=False):
        saved_scroll = self.id_canvas.yview() if keep_state else None

        for item in self.id_list_items:
            item.destroy()
        self.id_list_items.clear()

        start = self.current_page * ITEMS_PER_PAGE
        end = start + ITEMS_PER_PAGE
        page_rows = self.all_csv_rows[start:end]

        for row in page_rows:
            fid = row["fid"]
            name = row["name"]
            display_text = f"{fid}:{name}" if name else fid

            var = self.id_checkbox_vars.get(fid)
            if var is None:
                var = tk.BooleanVar(value=self.select_all_var.get() if not keep_state else False)
                self.id_checkbox_vars[fid] = var

            item_frame = tk.Frame(self.id_inner_frame, bg="#F5F5F5")
            item_frame.pack(fill=tk.X, pady=1)

            cb = tk.Checkbutton(item_frame, variable=var,
                                command=lambda f=fid: self._on_checkbox_changed(f),
                                bg="#F5F5F5", activebackground="#F5F5F5")
            cb.pack(side=tk.LEFT, padx=(4, 0))

            label = tk.Label(item_frame, text=display_text, anchor=tk.W,
                             font=("Consolas", 9), fg="#333333", bg="#F5F5F5",
                             padx=4, pady=3)
            label.pack(side=tk.LEFT, fill=tk.X, expand=True)

            label.bind("<Button-1>", lambda e, f=fid: self._on_id_left_click(e, f))
            item_frame.bind("<Button-1>", lambda e, f=fid: self._on_id_left_click(e, f))

            label.bind("<Button-3>", lambda e, f=fid: self._on_id_right_click(e, f))
            item_frame.bind("<Button-3>", lambda e, f=fid: self._on_id_right_click(e, f))

            self.id_list_items.append(item_frame)

        self.parent.after(10, self._update_scrollregion)
        if saved_scroll:
            self.parent.after(15, lambda: self._restore_scroll(saved_scroll))

        if keep_state:
            self._sync_select_all()

    def _on_checkbox_changed(self, fid):
        self._sync_select_all()
        self._update_selected_count()

    def _on_select_all_changed(self):
        val = self.select_all_var.get()
        for fid, var in self.id_checkbox_vars.items():
            var.set(val)
        self._update_selected_count()

    def _update_selected_count(self):
        selected = self._get_selected_fids()
        self.selected_count_label.configure(text=f"已选: {len(selected)}")

    def _sync_select_all(self):
        page_fids = {row["fid"] for row in self.all_csv_rows[
            self.current_page * ITEMS_PER_PAGE:(self.current_page + 1) * ITEMS_PER_PAGE
        ]}
        page_vars = {fid: var for fid, var in self.id_checkbox_vars.items() if fid in page_fids}
        if page_vars:
            all_checked = all(var.get() for var in page_vars.values())
            none_checked = not any(var.get() for var in page_vars.values())
            self.select_all_var.set(not none_checked)

    def _restore_scroll(self, scroll_pos):
        if scroll_pos:
            self.id_canvas.yview_moveto(scroll_pos[0])

    def _update_scrollregion(self):
        try:
            req_h = self.id_inner_frame.winfo_reqheight()
            self.id_canvas.configure(scrollregion=(0, 0, 260, req_h))
        except Exception:
            pass

    def _get_selected_fids(self):
        return [fid for fid, var in self.id_checkbox_vars.items() if var.get()]

    def _prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self._render_page(keep_state=True)
            self._update_page_controls()

    def _next_page(self):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self._render_page(keep_state=True)
            self._update_page_controls()

    def _update_page_controls(self):
        self.page_label.configure(text=f"第 {self.current_page + 1}/{max(1, self.total_pages)} 页")
        self.prev_page_btn.configure(state=tk.NORMAL if self.current_page > 0 else tk.DISABLED)
        self.next_page_btn.configure(state=tk.NORMAL if self.current_page < self.total_pages - 1 else tk.DISABLED)

    def _on_id_left_click(self, event, fid):
        self._edit_id_dialog(fid)

    def _on_id_right_click(self, event, fid):
        menu = tk.Menu(self.parent, tearoff=0)
        menu.add_command(label=f"删除 {fid}", command=lambda: self._delete_id(fid))
        menu.add_command(label=f"编辑 {fid}", command=lambda: self._edit_id_dialog(fid))

        current = self.current_file_var.get()
        target_files = [f for f in PLAYER_FILES if f != current]
        if target_files:
            move_menu = tk.Menu(menu, tearoff=0)
            for tf in target_files:
                move_menu.add_command(label=f"移动至 {tf}", command=lambda t=tf: self._move_player_to_file(fid, t))
            menu.add_cascade(label="添加至其他分组", menu=move_menu)

        menu.tk_popup(event.x_root, event.y_root)

    def _move_player_to_file(self, fid, target_file):
        import time
        from core import LOGIN_URL

        target_path = self._get_path_for_file(target_file)
        target_rows = self.redeemer.read_csv_with_names(target_path)
        existing = {r["fid"] for r in target_rows}
        if fid in existing:
            messagebox.showwarning("提示", f"玩家 {fid} 已存在于 {target_file} 中，无需重复添加。")
            return

        source_path = self._get_csv_path()
        source_rows = self.redeemer.read_csv_with_names(source_path)
        player_row = next((r for r in source_rows if r["fid"] == fid), None)
        if not player_row:
            messagebox.showwarning("提示", f"未在 {self.current_file_var.get()} 中找到玩家 {fid}")
            return

        nickname = player_row.get("name", "")
        self.redeemer.append_id_to_csv(target_path, fid, nickname)
        self.redeemer.delete_id_from_csv(source_path, fid)
        self._log(f"玩家 {fid} 已从 {self.current_file_var.get()} 移动至 {target_file}", level='success')
        messagebox.showinfo("操作成功", f"玩家 {fid}（{nickname or '无昵称'}）已从当前分组移动至 {target_file}")
        self._refresh_id_list()

    def _get_path_for_file(self, filename):
        if self.redeemer:
            return self.redeemer._get_runtime_path(filename)
        import sys
        if getattr(sys, 'frozen', False):
            return os.path.join(os.path.dirname(sys.executable), filename)
        return os.path.join(self.app_path, filename)

    def _add_new_id(self):
        import threading
        import time
        from core import LOGIN_URL

        new_id = self.new_id_var.get().strip()
        if not new_id:
            return
        if not new_id.isdigit():
            messagebox.showwarning("提示", "玩家 ID 必须为纯数字！")
            return

        self.new_id_entry.configure(state=tk.DISABLED)
        self._log("正在获取玩家昵称...", level='info')

        def fetch_and_add():
            nickname = None
            try:
                payload = self.redeemer.encode_data({"fid": new_id, "time": int(time.time() * 1000)})
                resp = self.redeemer.make_request(LOGIN_URL, payload)
                if resp and resp.status_code == 200:
                    data = resp.json()
                    if data.get("code") == 0:
                        nickname = data.get("data", {}).get("nickname", "")
            except Exception:
                pass

            def done():
                self.new_id_entry.configure(state=tk.NORMAL)
                if nickname:
                    self._log(f"获取到昵称: {nickname}", level='success')
                    messagebox.showinfo("添加成功", f"玩家 {new_id}（{nickname}）已添加至 {self.current_file_var.get()}！")
                else:
                    self._log(f"无法获取昵称，将留空", level='warn')
                    messagebox.showinfo("添加成功", f"玩家 {new_id} 已添加至 {self.current_file_var.get()}（昵称将在兑换时更新）")

                csv_path = self._get_csv_path()
                self.redeemer.append_id_to_csv(csv_path, new_id, nickname or "")
                self.new_id_var.set("")
                self._log(f"新增玩家 {new_id} -> {self.current_file_var.get()}", level='info')
                self._refresh_id_list()

            self.parent.after(0, done)

        threading.Thread(target=fetch_and_add, daemon=True).start()

    def _delete_id(self, fid):
        if messagebox.askyesno("确认删除", f"确定要删除玩家 {fid} 吗？"):
            csv_path = self._get_csv_path()
            self.redeemer.delete_id_from_csv(csv_path, fid)
            self._log(f"删除玩家 {fid} <- {self.current_file_var.get()}", level='info')
            self._refresh_id_list()

    def _edit_id_dialog(self, old_fid):
        dialog = tk.Toplevel(self.parent)
        dialog.title(f"编辑玩家 ID")
        dialog.resizable(False, False)
        dialog.transient(self.parent)
        dialog.grab_set()

        dialog.geometry("300x100")

        ttk.Label(dialog, text=f"原 ID: {old_fid}").pack(pady=(10, 4))

        entry_var = tk.StringVar(value=old_fid)
        entry = ttk.Entry(dialog, textvariable=entry_var, width=25)
        entry.pack(pady=(0, 8))
        entry.select_range(0, tk.END)
        entry.focus_set()

        def on_confirm():
            new_fid = entry_var.get().strip()
            if not new_fid.isdigit():
                messagebox.showwarning("提示", "玩家 ID 必须为纯数字！", parent=dialog)
                return
            if new_fid != old_fid:
                csv_path = self._get_csv_path()
                self.redeemer.update_id_in_csv(csv_path, old_fid, new_fid)
                self._log(f"编辑玩家 {old_fid} -> {new_fid} ({self.current_file_var.get()})", level='info')
            dialog.destroy()
            self._refresh_id_list()

        entry.bind('<Return>', lambda e: on_confirm())

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=(0, 8))
        ttk.Button(btn_frame, text="确定", command=on_confirm, width=8).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="取消", command=dialog.destroy, width=8).pack(side=tk.LEFT, padx=4)

    def _get_csv_path(self):
        filename = self.current_file_var.get()
        if self.redeemer:
            return self.redeemer._get_runtime_path(filename)
        import sys
        if getattr(sys, 'frozen', False):
            return os.path.join(os.path.dirname(sys.executable), filename)
        return os.path.join(self.app_path, filename)

    def _switch_file(self):
        old_file = self._last_file
        if old_file != self.current_file_var.get():
            self._file_checkbox_state[old_file] = dict(self.id_checkbox_vars)
            self._last_file = old_file

        self._log(f"切换数据文件：{self.current_file_var.get()}", level='info')
        self.id_checkbox_vars = self._file_checkbox_state.get(self.current_file_var.get(), {})
        self.current_page = 0
        self._refresh_id_list()
        self._log(f"已切换至 {self.current_file_var.get()}", level='info')

    def _update_file_count_label(self):
        count = len(self.all_csv_rows)
        self.file_count_label.configure(text=f"({count} 人)")

    def _log(self, message, level='info'):
        if self.log_callback:
            self.log_callback(message, level)

    def refresh(self):
        self._refresh_id_list()

    def pack_forget(self):
        self.frame.pack_forget()

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)
