import os
import sys
import webbrowser
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

from core import GiftCodeRedeemer, ONNX_AVAILABLE, LOGIN_URL
from scraper import GiftCodeScraper, BS4_AVAILABLE
from .idlist import PlayerListSidebar
from .widgets import PLAYER_FILES, RIGHT_SIDEBAR_WIDTH, WIKI_GIFTCODES_URL, WIKI_HOME_URL


class GiftCodeApp:
    def __init__(self, root, app_path):
        self.root = root
        self.app_path = app_path
        self.redeemer = None
        self.redeem_thread = None
        self.scraper = None
        self.scrape_thread = None
        self.right_sidebar_visible = False
        self.left_sidebar_visible = False
        self.scrape_result = None
        self.code_buttons = []

        self.root.title("Whiteout Survival 礼包码兑换工具 v4.0")
        self.root.resizable(True, True)
        self.root.minsize(900, 600)

        self._build_ui()
        self._init_redeemer()
        self._init_scraper()
        self.root.after(300, self._auto_expand_sidebars)

    def _build_ui(self):
        self.outer_frame = ttk.Frame(self.root)
        self.outer_frame.pack(fill=tk.BOTH, expand=True)

        self.main_frame = ttk.Frame(self.outer_frame, padding=10)
        self.main_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.left_sidebar = PlayerListSidebar(
            self.outer_frame,
            redeemer=None,
            app_path=self.app_path,
            log_callback=self._on_log,
            on_switch_file=self._toggle_left_sidebar
        )

        self.right_sidebar_frame = ttk.Frame(self.outer_frame, width=RIGHT_SIDEBAR_WIDTH)
        self.right_sidebar_frame.pack_propagate(False)
        self.right_sidebar_frame.pack_forget()

        self._build_main_panel()
        self._build_right_sidebar()

    def _build_main_panel(self):
        top_bar = ttk.Frame(self.main_frame)
        top_bar.pack(fill=tk.X, pady=(0, 6))

        title_label = ttk.Label(top_bar, text="Whiteout Survival 礼包码兑换工具",
                                font=("Microsoft YaHei UI", 14, "bold"))
        title_label.pack(side=tk.LEFT)

        btn_bar = ttk.Frame(top_bar)
        btn_bar.pack(side=tk.RIGHT)

        wiki_btn = ttk.Button(btn_bar, text="🌐 进入Wiki", command=self._open_wiki_home, width=10)
        wiki_btn.pack(side=tk.LEFT, padx=(0, 4))

        self.left_sidebar_btn = ttk.Button(btn_bar, text="👥 玩家列表", command=self._toggle_left_sidebar, width=10)
        self.left_sidebar_btn.pack(side=tk.LEFT, padx=(0, 4))

        self.right_sidebar_btn = ttk.Button(btn_bar, text="📋 礼包码列表", command=self._toggle_right_sidebar, width=12)
        self.right_sidebar_btn.pack(side=tk.LEFT)

        input_frame = ttk.LabelFrame(self.main_frame, text="兑换设置", padding=8)
        input_frame.pack(fill=tk.X, pady=(0, 8))

        code_row = ttk.Frame(input_frame)
        code_row.pack(fill=tk.X, pady=2)
        ttk.Label(code_row, text="礼包码：").pack(side=tk.LEFT)
        self.code_var = tk.StringVar()
        self.code_entry = ttk.Entry(code_row, textvariable=self.code_var, width=25)
        self.code_entry.pack(side=tk.LEFT, padx=(4, 8), fill=tk.X, expand=True)
        self.code_entry.bind('<Return>', lambda e: self.start_redeem())

        self.start_btn = ttk.Button(code_row, text="开始兑换", command=self.start_redeem)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 4))
        self.stop_btn = ttk.Button(code_row, text="停止", command=self.stop_redeem, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT)

        options_row = ttk.Frame(input_frame)
        options_row.pack(fill=tk.X, pady=4)

        self.gpu_var = tk.BooleanVar(value=True)
        gpu_check = ttk.Checkbutton(options_row, text="启用 GPU 加速", variable=self.gpu_var)
        gpu_check.pack(side=tk.LEFT)

        ocr_text = "OCR 引擎："
        if ONNX_AVAILABLE:
            ocr_text += "ONNX（自动重试）"
        else:
            ocr_text += "无可用引擎！"
        ttk.Label(options_row, text=ocr_text).pack(side=tk.LEFT, padx=(16, 0))

        csv_frame = ttk.Frame(input_frame)
        csv_frame.pack(fill=tk.X, pady=2)
        csv_path = self._get_csv_path()
        ttk.Label(csv_frame, text=f"CSV 文件：{csv_path}（自动读取）").pack(side=tk.LEFT)

        progress_frame = ttk.LabelFrame(self.main_frame, text="兑换进度", padding=8)
        progress_frame.pack(fill=tk.X, pady=(0, 8))

        self.progress_bar = ttk.Progressbar(progress_frame, mode='determinate', length=400)
        self.progress_bar.pack(fill=tk.X, pady=(0, 4))

        self.progress_label = ttk.Label(progress_frame, text="等待开始...")
        self.progress_label.pack(anchor=tk.W)

        stats_frame = ttk.Frame(progress_frame)
        stats_frame.pack(fill=tk.X, pady=(4, 0))
        self.success_label = ttk.Label(stats_frame, text="成功：0", foreground="green")
        self.success_label.pack(side=tk.LEFT, padx=(0, 16))
        self.already_label = ttk.Label(stats_frame, text="已兑换：0", foreground="gray")
        self.already_label.pack(side=tk.LEFT, padx=(0, 16))
        self.error_label = ttk.Label(stats_frame, text="失败：0", foreground="red")
        self.error_label.pack(side=tk.LEFT)

        log_frame = ttk.LabelFrame(self.main_frame, text="日志输出", padding=4)
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=12, state=tk.DISABLED,
                                                   font=("Consolas", 9), wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        self.log_text.tag_configure('info', foreground='#2196F3')
        self.log_text.tag_configure('success', foreground='#4CAF50')
        self.log_text.tag_configure('warn', foreground='#FF9800')
        self.log_text.tag_configure('error', foreground='#F44336')
        self.log_text.tag_configure('process', foreground='#9C27B0')

    def _build_right_sidebar(self):
        header_frame = ttk.Frame(self.right_sidebar_frame)
        header_frame.pack(fill=tk.X, padx=8, pady=(8, 4))

        ttk.Label(header_frame, text="礼包码列表",
                  font=("Microsoft YaHei UI", 11, "bold")).pack(side=tk.LEFT)

        self.right_close_btn = ttk.Button(header_frame, text="✕", width=3,
                                           command=self._toggle_right_sidebar)
        self.right_close_btn.pack(side=tk.RIGHT)

        self.refresh_btn = ttk.Button(self.right_sidebar_frame, text="🔄 刷新礼包码",
                                       command=self._start_scrape)
        self.refresh_btn.pack(fill=tk.X, padx=8, pady=(0, 4))

        wiki_codes_btn = ttk.Button(self.right_sidebar_frame, text="🌐 Wiki礼包码界面",
                                     command=self._open_wiki_giftcodes)
        wiki_codes_btn.pack(fill=tk.X, padx=8, pady=(0, 6))

        self.scrape_status_label = ttk.Label(self.right_sidebar_frame, text="", foreground="gray")
        self.scrape_status_label.pack(fill=tk.X, padx=8, pady=(0, 4))

        ttk.Separator(self.right_sidebar_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=8, pady=(0, 4))

        ttk.Label(self.right_sidebar_frame, text="来源：Official Wiki",
                  font=("Microsoft YaHei UI", 9)).pack(anchor=tk.W, padx=8, pady=(0, 4))

        ttk.Label(self.right_sidebar_frame, text="✅ 有效礼包码",
                  font=("Microsoft YaHei UI", 10, "bold")).pack(anchor=tk.W, padx=8, pady=(0, 4))

        codes_container = ttk.Frame(self.right_sidebar_frame)
        codes_container.pack(fill=tk.BOTH, expand=True, padx=8)

        self.codes_canvas = tk.Canvas(codes_container, highlightthickness=0)
        codes_scrollbar = ttk.Scrollbar(codes_container, orient=tk.VERTICAL,
                                         command=self.codes_canvas.yview)
        self.codes_inner_frame = ttk.Frame(self.codes_canvas)

        self.codes_inner_frame.bind("<Configure>",
            lambda e: self.codes_canvas.configure(scrollregion=self.codes_canvas.bbox("all")))

        self.codes_canvas.create_window((0, 0), window=self.codes_inner_frame, anchor=tk.NW)
        self.codes_canvas.configure(yscrollcommand=codes_scrollbar.set)

        self.codes_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        codes_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.codes_canvas.bind("<Enter>",
            lambda e: self.codes_canvas.bind_all("<MouseWheel>",
                lambda ev: self.codes_canvas.yview_scroll(int(-1 * (ev.delta / 120)), "units")))
        self.codes_canvas.bind("<Leave>",
            lambda e: self.codes_canvas.unbind_all("<MouseWheel>"))

    def _open_wiki_home(self):
        webbrowser.open(WIKI_HOME_URL)

    def _open_wiki_giftcodes(self):
        webbrowser.open(WIKI_GIFTCODES_URL)

    def _toggle_left_sidebar(self):
        if self.left_sidebar_visible:
            self.left_sidebar.pack_forget()
            self.left_sidebar_visible = False
            self.left_sidebar_btn.configure(text="👥 玩家列表")
        else:
            self.left_sidebar.pack(side=tk.LEFT, fill=tk.Y, before=self.main_frame)
            self.left_sidebar_visible = True
            self.left_sidebar_btn.configure(text="隐藏玩家")
            self.left_sidebar.refresh()

    def _toggle_right_sidebar(self):
        if self.right_sidebar_visible:
            self.right_sidebar_frame.pack_forget()
            self.right_sidebar_visible = False
            self.right_sidebar_btn.configure(text="📋 礼包码列表")
        else:
            self.right_sidebar_frame.pack(side=tk.RIGHT, fill=tk.Y, before=self.main_frame)
            self.right_sidebar_visible = True
            self.right_sidebar_btn.configure(text="隐藏列表")
            if self.scrape_result is None:
                self._start_scrape()

    def _auto_expand_sidebars(self):
        if not self.left_sidebar_visible:
            self.left_sidebar.pack(side=tk.LEFT, fill=tk.Y, before=self.main_frame)
            self.left_sidebar_visible = True
            self.left_sidebar_btn.configure(text="隐藏玩家")
            self.left_sidebar.refresh()

        if not self.right_sidebar_visible:
            self.right_sidebar_frame.pack(side=tk.RIGHT, fill=tk.Y, before=self.main_frame)
            self.right_sidebar_visible = True
            self.right_sidebar_btn.configure(text="隐藏列表")
            self._start_scrape()

    def _get_csv_path(self):
        filename = self.left_sidebar.current_file_var.get() if self.left_sidebar else PLAYER_FILES[0]
        if self.redeemer:
            return self.redeemer._get_runtime_path(filename)
        if getattr(sys, 'frozen', False):
            return os.path.join(os.path.dirname(sys.executable), filename)
        return os.path.join(self.app_path, filename)

    def _init_redeemer(self):
        self.redeemer = GiftCodeRedeemer(
            app_path=self.app_path,
            log_callback=self._on_log,
            progress_callback=self._on_progress,
            name_update_callback=self._on_name_updated,
        )
        self.left_sidebar.redeemer = self.redeemer

    def _init_scraper(self):
        self.scraper = GiftCodeScraper(status_callback=self._on_scrape_status)

    def _on_name_updated(self, fid, name):
        self.root.after(0, lambda: self.left_sidebar.refresh())

    def _on_scrape_status(self, message, level='info'):
        def _update():
            color_map = {'info': '#2196F3', 'success': '#4CAF50', 'warn': '#FF9800', 'error': '#F44336'}
            self.scrape_status_label.configure(text=message, foreground=color_map.get(level, 'gray'))
        self.root.after(0, _update)

    def _start_scrape(self):
        if not BS4_AVAILABLE:
            self.scrape_status_label.configure(text="错误：beautifulsoup4 未安装", foreground="#F44336")
            return

        if self.scraper and self.scraper.running:
            return

        self.refresh_btn.configure(state=tk.DISABLED)
        self.scrape_status_label.configure(text="正在获取礼包码...", foreground="#2196F3")

        def run_scrape():
            result = self.scraper.scrape()
            self.root.after(0, lambda: self._on_scrape_complete(result))

        self.scrape_thread = threading.Thread(target=run_scrape, daemon=True)
        self.scrape_thread.start()

    def _render_codes(self):
        for btn in self.code_buttons:
            btn.destroy()
        self.code_buttons.clear()

        if not self.scrape_result:
            no_codes_label = ttk.Label(self.codes_inner_frame, text="请点击「刷新礼包码」获取数据",
                                        foreground="gray")
            no_codes_label.pack(anchor=tk.W, pady=4)
            self.code_buttons.append(no_codes_label)
            return

        codes = self.scrape_result.get("codes", [])

        if codes:
            for code in codes:
                btn = tk.Button(self.codes_inner_frame, text=code, anchor=tk.W,
                                font=("Consolas", 10, "bold"), fg="#1565C0", bg="#E3F2FD",
                                activebackground="#BBDEFB", activeforeground="#0D47A1",
                                relief=tk.FLAT, cursor="hand2", padx=8, pady=3,
                                command=lambda c=code: self._fill_code(c))
                btn.pack(fill=tk.X, pady=1)
                self.code_buttons.append(btn)
        else:
            no_codes_label = ttk.Label(self.codes_inner_frame, text="暂无有效礼包码",
                                        foreground="gray")
            no_codes_label.pack(anchor=tk.W, pady=4)
            self.code_buttons.append(no_codes_label)

    def _on_scrape_complete(self, result):
        self.scrape_result = result
        self.refresh_btn.configure(state=tk.NORMAL)

        if result.get("error"):
            self.scrape_status_label.configure(
                text=f"获取失败: {result['error']}", foreground="#F44336")
        else:
            count = len(result.get("codes", []))
            self.scrape_status_label.configure(
                text=f"已获取 {count} 个有效礼包码", foreground="#4CAF50")

        self._render_codes()

    def _fill_code(self, code):
        self.code_var.set(code)
        self.code_entry.focus_set()

    def _on_log(self, message, level='info'):
        def _update():
            self.log_text.configure(state=tk.NORMAL)
            tag = level if level in ('success', 'warn', 'error', 'process') else 'info'
            self.log_text.insert(tk.END, message + "\n", tag)
            self.log_text.see(tk.END)
            self.log_text.configure(state=tk.DISABLED)
        self.root.after(0, _update)

    def _on_progress(self, current, total, success, already, errors):
        def _update():
            if total > 0:
                self.progress_bar['value'] = (current / total) * 100
                self.progress_label.configure(text=f"进度：{current}/{total} ({current/total*100:.1f}%)")
            self.success_label.configure(text=f"成功：{success}")
            self.already_label.configure(text=f"已兑换：{already}")
            self.error_label.configure(text=f"失败：{errors}")
        self.root.after(0, _update)

    def start_redeem(self):
        gift_code = self.code_var.get().strip()
        if not gift_code:
            messagebox.showwarning("提示", "请输入礼包码！")
            return

        if not self.redeemer.onnx_session:
            messagebox.showerror("错误", "ONNX 模型未加载！请确认 onnxruntime 已安装且模型文件存在。")
            return

        selected = self.left_sidebar._get_selected_fids()
        if not selected:
            messagebox.showwarning("提示", "请至少选择一个玩家 ID！\n（勾选左侧列表中的玩家）")
            return

        confirm_msg = (
            f"【兑换确认】\n\n"
            f"数据文件：{self.left_sidebar.current_file_var.get()}\n"
            f"礼包码：{gift_code}\n"
            f"选中玩家数：{len(selected)} 人\n\n"
            f"是否确认开始兑换？"
        )

        if not messagebox.askyesno("确认兑换", confirm_msg):
            return

        self.redeemer.set_gpu_enabled(self.gpu_var.get())

        self.start_btn.configure(state=tk.DISABLED)
        self.stop_btn.configure(state=tk.NORMAL)
        self.code_entry.configure(state=tk.DISABLED)
        self.left_sidebar.new_id_entry.configure(state=tk.DISABLED)

        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

        self.progress_bar['value'] = 0
        self.progress_label.configure(text="正在兑换...")
        self.success_label.configure(text="成功：0")
        self.already_label.configure(text="已兑换：0")
        self.error_label.configure(text="失败：0")

        def run_redeem():
            summary = self.redeemer.redeem_all(gift_code, selected_fids=selected,
                                               csv_filename=self.left_sidebar.current_file_var.get())
            self.root.after(0, lambda: self._on_redeem_complete(summary))

        self.redeem_thread = threading.Thread(target=run_redeem, daemon=True)
        self.redeem_thread.start()

    def stop_redeem(self):
        if self.redeemer and self.redeemer.running:
            self.redeemer.stop()
            self._on_log("正在停止兑换...", level='warn')

    def _on_redeem_complete(self, summary):
        self.start_btn.configure(state=tk.NORMAL)
        self.stop_btn.configure(state=tk.DISABLED)
        self.code_entry.configure(state=tk.NORMAL)
        self.left_sidebar.new_id_entry.configure(state=tk.NORMAL)

        self.left_sidebar.refresh()

        if summary:
            msg = (
                f"礼包码：{summary['gift_code']}\n\n"
                f"成功兑换：{summary['success']}\n"
                f"已兑换过：{summary['already_redeemed']}\n"
                f"失败：{summary['errors']}\n\n"
                f"ONNX 识别成功：{summary['onnx_successes']}/{summary['ocr_attempts']}\n"
                f"OCR 成功率：{summary['ocr_success_rate']:.1f}%\n"
                f"OCR 重试次数：{summary['ocr_retry_triggered']}\n"
                f"平均识别耗时：{summary['avg_ocr_time']:.0f}ms\n"
                f"服务器通过率：{summary['server_pass_rate']:.1f}%\n"
                f"限流次数：{summary['rate_limited']}\n\n"
                f"总耗时：{summary['execution_time']}"
            )
            messagebox.showinfo("兑换完成 - 汇总报告", msg)
