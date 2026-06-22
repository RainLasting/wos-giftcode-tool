import os
import sys
import time
import json
import threading

AUTO_REDEEM_ORDER = [
    "playerR4R5.csv",
    "playerR3.csv",
    "playerR2.csv",
    "playerR1.csv",
    "playerR0.csv",
    "playerFARM.csv",
    "playerALLY.csv",
]

CHECK_INTERVAL = 3600
STATE_FILE = "scheduler_state.json"


class GiftCodeScheduler:

    def __init__(self, app_path, scraper, redeemer, log_callback=None, status_callback=None):
        self.app_path = app_path
        self.scraper = scraper
        self.redeemer = redeemer
        self.log_callback = log_callback
        self.status_callback = status_callback

        self.enabled = False
        self.stop_flag = False
        self._busy = False
        self._thread = None
        self._lock = threading.Lock()

        self._known_codes = set()
        self._new_codes = set()
        self._check_count = 0
        self._last_check_time = None
        self._status = "idle"

        self._load_state()

    def _get_state_path(self):
        if getattr(sys, 'frozen', False):
            return os.path.join(os.path.dirname(sys.executable), STATE_FILE)
        return os.path.join(self.app_path, STATE_FILE)

    def _load_state(self):
        try:
            path = self._get_state_path()
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                self._known_codes = set(state.get('known_codes', []))
                self._check_count = state.get('check_count', 0)
        except Exception:
            pass

    def _save_state(self):
        try:
            path = self._get_state_path()
            state = {
                'known_codes': list(self._known_codes),
                'check_count': self._check_count,
                'last_check': self._last_check_time,
            }
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(state, f)
        except Exception:
            pass

    def _log(self, message, level='info'):
        if self.log_callback:
            self.log_callback(message, level)

    def _set_status(self, status):
        self._status = status
        if self.status_callback:
            self.status_callback(status)

    def start(self):
        with self._lock:
            if self.enabled:
                return
            self.enabled = True
            self.stop_flag = False
            self._set_status("monitoring")
            self._log("定时任务已启动，每60分钟检查一次礼包码变更", level='info')
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()

    def stop(self):
        with self._lock:
            self.enabled = False
            self.stop_flag = True
            self._busy = False
            if self.redeemer:
                self.redeemer.stop()
            self._set_status("idle")
            self._log("定时任务已停止", level='info')

    def check_now(self):
        if self._busy:
            self._log("已有检查任务正在执行，请等待完成", level='warn')
            return
        self._log("手动触发礼包码检查...", level='info')
        threading.Thread(target=self._do_check_and_redeem, daemon=True).start()

    def _run_loop(self):
        self._log("开始定时监控礼包码变更...", level='info')
        while not self.stop_flag:
            self._do_check_and_redeem()
            for _ in range(CHECK_INTERVAL):
                if self.stop_flag:
                    break
                time.sleep(1)

    def _do_check_and_redeem(self):
        if self.stop_flag:
            return

        with self._lock:
            if self._busy:
                self._log("已有检查任务正在执行，跳过本次检查", level='warn')
                return
            self._busy = True

        try:
            self._set_status("checking")
            self._check_count += 1
            self._last_check_time = time.strftime("%Y-%m-%d %H:%M:%S")
            self._log(f"[定时检查 #{self._check_count}] 开始检查礼包码变更...", level='info')

            try:
                result = self.scraper.scrape(source_type="rss")
                current_codes = set(result.get("codes", []))

                if self.stop_flag:
                    return

                if result.get("error"):
                    self._log(f"[定时检查 #{self._check_count}] 获取礼包码失败: {result['error']}", level='error')
                    self._set_status("error")
                    return

                self._log(f"[定时检查 #{self._check_count}] 当前有效礼包码: {len(current_codes)} 个", level='info')

                new_codes = current_codes - self._known_codes
                self._new_codes = new_codes

                if new_codes:
                    self._log(
                        f"[定时检查 #{self._check_count}] 检测到 {len(new_codes)} 个新礼包码: "
                        f"{', '.join(sorted(new_codes))}",
                        level='success'
                    )
                    self._set_status("redeeming")
                    self._auto_redeem(current_codes)
                else:
                    self._log(f"[定时检查 #{self._check_count}] 未检测到新礼包码", level='info')
                    if self.enabled:
                        self._set_status("monitoring")

                self._known_codes = current_codes
                self._save_state()

            except Exception as e:
                self._log(f"[定时检查 #{self._check_count}] 检查出错: {str(e)}", level='error')
                self._set_status("error")
        finally:
            with self._lock:
                self._busy = False

    def _auto_redeem(self, codes):
        if not codes:
            return

        codes_list = sorted(codes)
        self._log(f"开始自动兑换 {len(codes_list)} 个礼包码: {', '.join(codes_list)}", level='info')

        for csv_file in AUTO_REDEEM_ORDER:
            if self.stop_flag or (self.redeemer and self.redeemer.stop_flag):
                break

            csv_path = self._get_runtime_path(csv_file)
            if not os.path.exists(csv_path):
                self._log(f"  [{csv_file}] 文件不存在，跳过", level='warn')
                continue

            fids = self._read_player_ids(csv_path)
            if not fids:
                self._log(f"  [{csv_file}] 没有玩家，跳过", level='warn')
                continue

            self._log(f"  [{csv_file}] {len(fids)} 个玩家", level='info')

            for code in codes_list:
                if self.stop_flag or (self.redeemer and self.redeemer.stop_flag):
                    break

                self._log(f"  [{csv_file}] 兑换 {code} ({len(fids)} 人)...", level='info')

                retry_count = 0
                max_retries = 3
                redeemed = False
                while retry_count < max_retries and not self.stop_flag and not (self.redeemer and self.redeemer.stop_flag):
                    try:
                        summary = self.redeemer.redeem_all(
                            code, selected_fids=fids, csv_filename=csv_file
                        )
                        redeemed = True
                        if summary:
                            self._log(
                                f"  [{csv_file}] {code} 完成: "
                                f"成功 {summary.get('success', 0)}, "
                                f"已兑换 {summary.get('already_redeemed', 0)}, "
                                f"失败 {summary.get('errors', 0)}",
                                level='success'
                            )
                        break
                    except Exception as e:
                        retry_count += 1
                        if retry_count < max_retries:
                            wait = 2 ** retry_count * 10
                            self._log(
                                f"  [{csv_file}] {code} 出错: {str(e)[:80]}, "
                                f"{wait}秒后重试 ({retry_count}/{max_retries})",
                                level='warn'
                            )
                            for _ in range(wait):
                                if self.stop_flag:
                                    break
                                time.sleep(1)
                        else:
                            self._log(
                                f"  [{csv_file}] {code} 最终失败: {str(e)[:80]}",
                                level='error'
                            )

                if not redeemed:
                    self._log(f"  [{csv_file}] {code} 已取消（用户停止）", level='warn')
                    break

            if self.redeemer and self.redeemer.stop_flag:
                self._log("检测到用户停止信号，中断自动兑换", level='warn')
                self.stop_flag = True
                break

        self._log("自动兑换完成", level='success')
        if self.enabled:
            self._set_status("monitoring")

    def _get_runtime_path(self, filename):
        if getattr(sys, 'frozen', False):
            return os.path.join(os.path.dirname(sys.executable), filename)
        return os.path.join(self.app_path, filename)

    def _read_player_ids(self, csv_path):
        fids = []
        try:
            with open(csv_path, 'r', encoding='utf-8-sig') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split(',')
                    if parts[0].strip():
                        fids.append(parts[0].strip())
        except Exception as e:
            self._log(f"读取 {csv_path} 失败: {e}", level='error')
        return fids

    def get_status(self):
        return {
            'enabled': self.enabled,
            'status': self._status,
            'check_count': self._check_count,
            'last_check': self._last_check_time,
            'known_codes_count': len(self._known_codes),
            'new_codes': list(self._new_codes),
        }