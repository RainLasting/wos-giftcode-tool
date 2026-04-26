import tkinter as tk
from tkinter import ttk


ITEMS_PER_PAGE = 50

PLAYER_FILES = ["playerR0.csv", "playerR1.csv", "playerR2.csv", "playerR3.csv", "playerR4R5.csv"]

RIGHT_SIDEBAR_WIDTH = 300
LEFT_SIDEBAR_WIDTH = 300

WIKI_GIFTCODES_URL = "https://www.whiteoutsurvival.wiki/giftcodes/"
WIKI_HOME_URL = "https://www.whiteoutsurvival.wiki/tw/"


class ScrollableListFrame(ttk.Frame):
    def __init__(self, parent, item_height=30, **kwargs):
        super().__init__(parent, **kwargs)
        self.item_height = item_height
        self.items = []
        self.checkbox_vars = {}
        self.select_all_var = tk.BooleanVar(value=True)

        self.canvas = tk.Canvas(self, highlightthickness=0, bg="#F5F5F5")
        self.scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.canvas.yview)
        self.inner_frame = tk.Frame(self.canvas, bg="#F5F5F5")

        self.canvas.create_window((0, 0), window=self.inner_frame, anchor=tk.NW, width=260)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._bind_mousewheel()

    def _bind_mousewheel(self):
        def _on_mousewheel(ev):
            self.canvas.yview_scroll(int(-1 * (ev.delta / 120)), "units")

        def _bound_to_mousewheel(ev):
            self.canvas.bind_all("<MouseWheel>", _on_mousewheel)
            self.canvas.bind_all("<Button-4>", lambda e: self.canvas.yview_scroll(-3, "units"))
            self.canvas.bind_all("<Button-5>", lambda e: self.canvas.yview_scroll(3, "units"))

        def _unbound_from_mousewheel(ev):
            self.canvas.unbind_all("<MouseWheel>")
            self.canvas.unbind_all("<Button-4>")
            self.canvas.unbind_all("<Button-5>")

        self.canvas.bind("<Enter>", _bound_to_mousewheel)
        self.canvas.bind("<Leave>", _unbound_from_mousewheel)

    def clear_items(self):
        for item in self.items:
            item.destroy()
        self.items.clear()

    def update_scrollregion(self):
        try:
            req_h = self.inner_frame.winfo_reqheight()
            self.canvas.configure(scrollregion=(0, 0, 260, req_h))
        except Exception:
            pass

    def save_scroll_position(self):
        return self.canvas.yview()

    def restore_scroll_position(self, scroll_pos):
        if scroll_pos:
            self.canvas.yview_moveto(scroll_pos[0])

    def clear_checkbox_vars(self):
        self.checkbox_vars = {}


class SelectableListFrame(ttk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.items = []
        self.checkbox_vars = {}
        self.select_all_var = tk.BooleanVar(value=True)
        self.current_page = 0
        self.total_pages = 0
        self.all_rows = []

        self.canvas = tk.Canvas(self, highlightthickness=0, bg="#F5F5F5")
        self.scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.canvas.yview)
        self.inner_frame = tk.Frame(self.canvas, bg="#F5F5F5")

        self.canvas.create_window((0, 0), window=self.inner_frame, anchor=tk.NW, width=260)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._bind_mousewheel()

    def _bind_mousewheel(self):
        def _on_mousewheel(ev):
            self.canvas.yview_scroll(int(-1 * (ev.delta / 120)), "units")

        def _bound_to_mousewheel(ev):
            self.canvas.bind_all("<MouseWheel>", _on_mousewheel)
            self.canvas.bind_all("<Button-4>", lambda e: self.canvas.yview_scroll(-3, "units"))
            self.canvas.bind_all("<Button-5>", lambda e: self.canvas.yview_scroll(3, "units"))

        def _unbound_from_mousewheel(ev):
            self.canvas.unbind_all("<MouseWheel>")
            self.canvas.unbind_all("<Button-4>")
            self.canvas.unbind_all("<Button-5>")

        self.canvas.bind("<Enter>", _bound_to_mousewheel)
        self.canvas.bind("<Leave>", _unbound_from_mousewheel)

    def clear_items(self):
        for item in self.items:
            item.destroy()
        self.items.clear()

    def update_scrollregion(self):
        try:
            req_h = self.inner_frame.winfo_reqheight()
            self.canvas.configure(scrollregion=(0, 0, 260, req_h))
        except Exception:
            pass

    def save_scroll_position(self):
        return self.canvas.yview()

    def restore_scroll_position(self, scroll_pos):
        if scroll_pos:
            self.canvas.yview_moveto(scroll_pos[0])

    def clear_checkbox_vars(self):
        self.checkbox_vars = {}


class PageControlFrame(ttk.Frame):
    def __init__(self, parent, prev_callback, next_callback, **kwargs):
        super().__init__(parent, **kwargs)
        self.prev_callback = prev_callback
        self.next_callback = next_callback

        self.prev_btn = ttk.Button(self, text="◀ 上一页", command=self._on_prev, width=9)
        self.prev_btn.pack(side=tk.LEFT)

        self.page_label = tk.Label(self, text="第 1/1 页", font=("Microsoft YaHei UI", 9))
        self.page_label.pack(side=tk.LEFT, padx=6)

        self.next_btn = ttk.Button(self, text="下一页 ▶", command=self._on_next, width=9)
        self.next_btn.pack(side=tk.RIGHT)

    def _on_prev(self):
        if self.prev_callback:
            self.prev_callback()

    def _on_next(self):
        if self.next_callback:
            self.next_callback()

    def update(self, current_page, total_pages):
        self.page_label.configure(text=f"第 {current_page + 1}/{max(1, total_pages)} 页")
        self.prev_btn.configure(state=tk.NORMAL if current_page > 0 else tk.DISABLED)
        self.next_btn.configure(state=tk.NORMAL if current_page < total_pages - 1 else tk.DISABLED)


class StatusBar(ttk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.success_label = ttk.Label(self, text="成功：0", foreground="green")
        self.success_label.pack(side=tk.LEFT, padx=(0, 16))
        self.already_label = ttk.Label(self, text="已兑换：0", foreground="gray")
        self.already_label.pack(side=tk.LEFT, padx=(0, 16))
        self.error_label = ttk.Label(self, text="失败：0", foreground="red")
        self.error_label.pack(side=tk.LEFT)

    def update(self, success, already, errors):
        self.success_label.configure(text=f"成功：{success}")
        self.already_label.configure(text=f"已兑换：{already}")
        self.error_label.configure(text=f"失败：{errors}")


class PlayerContextMenu:
    def __init__(self, parent, delete_callback, edit_callback, move_callbacks):
        self.parent = parent
        self.menu = tk.Menu(parent, tearoff=0)

    def show(self, event, fid, move_targets):
        self.menu = tk.Menu(self.parent, tearoff=0)
        self.menu.add_command(label=f"删除 {fid}", command=lambda: self._delete(fid))
        self.menu.add_command(label=f"编辑 {fid}", command=lambda: self._edit(fid))

        if move_targets:
            move_menu = tk.Menu(self.menu, tearoff=0)
            for target in move_targets:
                move_menu.add_command(label=f"移动至 {target}", command=lambda t=target: self._move(fid, t))
            self.menu.add_cascade(label="添加至其他分组", menu=move_menu)

        self.menu.tk_popup(event.x_root, event.y_root)

    def _delete(self, fid):
        pass

    def _edit(self, fid):
        pass

    def _move(self, fid, target):
        pass
