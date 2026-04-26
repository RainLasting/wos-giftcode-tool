import os
import sys
import time
import random
import csv
import io
import json
import base64
import warnings
from datetime import datetime, timedelta

from .api import (
    encode_data, make_request, DELAY, RETRY_DELAY, MAX_RETRIES,
    LOGIN_URL, CAPTCHA_URL, REDEEM_URL
)
from .ocr import CaptchaSolver, ONNX_AVAILABLE, OCR_MAX_RETRIES, OCR_RETRY_DELAY_MIN, OCR_RETRY_DELAY_MAX

warnings.filterwarnings("ignore", message=".*pin_memory.*", category=UserWarning)

CAPTCHA_RETRIES = 4
CAPTCHA_SLEEP = 60
MAX_CAPTCHA_FETCH_ATTEMPTS = 4

RESULT_MESSAGES = {
    "SUCCESS": "成功兑换",
    "RECEIVED": "已兑换过",
    "SAME TYPE EXCHANGE": "成功兑换（同类型）",
    "TIME ERROR": "礼包码已过期",
    "TIMEOUT RETRY": "服务器请求重试",
    "USED": "领取次数已达上限",
    "Server requested retry": "服务器请求重试",
    "CAPTCHA CHECK ERROR": "验证码校验错误",
    "CAPTCHA CHECK TOO FREQUENT": "验证码请求过于频繁",
    "Sign Error": "签名错误",
    "NOT LOGIN": "未登录/会话过期",
}


class GiftCodeRedeemer:
    def __init__(self, app_path, log_callback=None, progress_callback=None,
                 name_update_callback=None):
        self.app_path = app_path
        self.log_callback = log_callback
        self.progress_callback = progress_callback
        self.name_update_callback = name_update_callback
        self.stop_flag = False
        self.running = False

        self._ocr = None
        self._init_ocr()

        self.counters = {}
        self.error_details = {}
        self.script_start_time = None

    def _get_runtime_path(self, filename):
        if getattr(sys, 'frozen', False):
            return os.path.join(os.path.dirname(sys.executable), filename)
        return os.path.join(self.app_path, filename)

    def _init_ocr(self):
        self._ocr = CaptchaSolver(
            model_path='captcha_model.onnx',
            metadata_path='captcha_model_metadata.json',
            app_path=self.app_path,
            log_callback=self._make_log_callback()
        )
        self._ocr._log = lambda msg, level='info': self.log(msg, level) if self.log else None

    def set_gpu_enabled(self, enabled):
        self._ocr.set_gpu_enabled(enabled)

    @property
    def onnx_session(self):
        return self._ocr.session if self._ocr else None

    def _make_log_callback(self):
        return None

    def log(self, message, level='info', to_file=True):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        full_message = f"{timestamp} - {message}"

        if self.log_callback:
            self.log_callback(full_message, level)

        if to_file:
            try:
                log_file = self._get_runtime_path("redeemed_codes.txt")
                log_dir = os.path.dirname(log_file)
                if log_dir and not os.path.exists(log_dir):
                    os.makedirs(log_dir)
                with open(log_file, "a", encoding="utf-8-sig", newline='') as f:
                    f.write(full_message + "\n")
            except Exception:
                pass

    def _update_progress(self, current, total, success, already, errors):
        if self.progress_callback:
            self.progress_callback(current, total, success, already, errors)

    def stop(self):
        self.stop_flag = True

    def _reset_counters(self):
        self.counters = {
            "success": 0,
            "already_redeemed": 0,
            "errors": 0,
            "captcha_fetch_attempts": 0,
            "captcha_ocr_attempts": 0,
            "captcha_ocr_success": 0,
            "captcha_ocr_success_onnx": 0,
            "captcha_ocr_retry_triggered": 0,
            "captcha_ocr_total_time": 0.0,
            "captcha_redeem_success": 0,
            "captcha_redeem_failure": 0,
            "captcha_rate_limited": 0,
        }
        self.error_details = {}

    def fetch_and_solve_captcha(self, fid, nickname, retry_queue):
        attempts = 0
        current_time = time.time()

        while attempts < MAX_CAPTCHA_FETCH_ATTEMPTS:
            if self.stop_flag:
                return None, None, retry_queue, "Stopped"

            self.counters["captcha_fetch_attempts"] += 1

            payload = encode_data({"fid": fid, "time": int(time.time() * 1000), "init": "0"})
            response = make_request(CAPTCHA_URL, payload)

            if response and response.status_code == 200:
                try:
                    captcha_data = response.json()
                    if captcha_data.get("code") == 1 and "TOO FREQUENT" in captcha_data.get("msg", "").upper():
                        self.log(f"{nickname}({fid}) - 验证码请求被限流，加入重试队列", level='warn')
                        retry_queue[fid] = current_time + CAPTCHA_SLEEP
                        self.counters["captcha_rate_limited"] += 1
                        return None, None, retry_queue, "RateLimited"

                    if "data" in captcha_data and "img" in captcha_data["data"]:
                        img_base64 = self._ocr._parse_captcha_base64(captcha_data["data"]["img"])

                        if not img_base64:
                            attempts += 1
                            time.sleep(random.uniform(1.0, 2.0))
                            continue

                        try:
                            img_bytes = base64.b64decode(img_base64)
                        except base64.binascii.Error:
                            attempts += 1
                            time.sleep(random.uniform(1.0, 2.0))
                            continue

                        solved_code = None
                        ocr_retry = 0

                        while ocr_retry <= OCR_MAX_RETRIES:
                            if self.stop_flag:
                                return None, None, retry_queue, "Stopped"

                            self.log(f"{nickname}({fid}) - 使用 ONNX 识别验证码{'(重试 ' + str(ocr_retry) + '/' + str(OCR_MAX_RETRIES) + ')' if ocr_retry > 0 else ''}...")
                            ocr_start = time.time()
                            onnx_code = self._ocr.solve(img_bytes)
                            if onnx_code:
                                solved_code = onnx_code
                                self.counters["captcha_ocr_total_time"] += time.time() - ocr_start
                                self.counters["captcha_ocr_success_onnx"] += 1
                                break

                            ocr_retry += 1
                            if ocr_retry <= OCR_MAX_RETRIES:
                                self.counters["captcha_ocr_retry_triggered"] += 1
                                retry_delay = random.uniform(OCR_RETRY_DELAY_MIN, OCR_RETRY_DELAY_MAX)
                                self.log(f"{nickname}({fid}) - ONNX 识别失败，{int(retry_delay * 1000)}ms 后重试...", level='warn')
                                time.sleep(retry_delay)

                                retry_payload = encode_data({"fid": fid, "time": int(time.time() * 1000), "init": "0"})
                                retry_response = make_request(CAPTCHA_URL, retry_payload)
                                if retry_response and retry_response.status_code == 200:
                                    try:
                                        retry_data = retry_response.json()
                                        if "data" in retry_data and "img" in retry_data["data"]:
                                            retry_b64 = self._ocr._parse_captcha_base64(retry_data["data"]["img"])
                                            if retry_b64:
                                                try:
                                                    img_bytes = base64.b64decode(retry_b64)
                                                except base64.binascii.Error:
                                                    pass
                                    except (json.JSONDecodeError, Exception):
                                        pass

                        if solved_code:
                            self.log(f"{nickname}({fid}) - 验证码识别成功 [ONNX]: {solved_code}")
                            self.counters["captcha_ocr_success"] += 1
                            return solved_code, retry_queue, "ONNX"
                        else:
                            self.log(f"{nickname}({fid}) - 验证码识别失败（已重试 {OCR_MAX_RETRIES} 次），重新获取...", level='warn')
                    else:
                        self.log(f"{nickname}({fid}) - 验证码数据缺失: {captcha_data.get('msg', '')}", level='warn')

                except json.JSONDecodeError:
                    self.log(f"{nickname}({fid}) - 验证码响应 JSON 解析失败", level='error')
                except Exception as e:
                    self.log(f"{nickname}({fid}) - 处理验证码时出错: {e}", level='error')

            elif response is not None:
                self.log(f"{nickname}({fid}) - 获取验证码失败 (HTTP {response.status_code})，重试中...", level='warn')
            else:
                self.log(f"{nickname}({fid}) - 获取验证码失败（网络错误），重试中...", level='warn')

            attempts += 1
            if attempts < MAX_CAPTCHA_FETCH_ATTEMPTS:
                time.sleep(random.uniform(1.5, 3.0))

        self.log(f"{nickname}({fid}) - 验证码获取/识别失败（已尝试 {attempts} 次），加入重试队列", level='error')
        retry_queue[fid] = current_time + CAPTCHA_SLEEP
        return None, retry_queue, "Fetch/Solve Failed"

    def redeem_gift_code(self, fid, cdk, nickname, retry_queue):
        if not str(fid).strip().isdigit():
            self.log(f"跳过无效的玩家 ID 格式: '{fid}'", level='warn')
            return {"msg": "Invalid FID format"}, retry_queue

        fid = str(fid).strip()
        current_time = time.time()
        if fid in retry_queue and retry_queue[fid] > current_time:
            return {"msg": "In cooldown"}, retry_queue

        final_redeem_data = {"msg": "Processing Error"}

        for attempt in range(CAPTCHA_RETRIES):
            if self.stop_flag:
                return {"msg": "Stopped"}, retry_queue

            captcha_code_sent, retry_queue, ocr_method_succeeded = self.fetch_and_solve_captcha(fid, nickname, retry_queue)

            if captcha_code_sent is None:
                if ocr_method_succeeded == "RateLimited":
                    final_redeem_data = {"msg": "CAPTCHA CHECK TOO FREQUENT"}
                else:
                    final_redeem_data = {"msg": "Captcha fetch/solve failed"}
                break

            try:
                redeem_payload = encode_data({
                    "fid": fid, "cdk": cdk, "captcha_code": captcha_code_sent,
                    "time": int(time.time() * 1000)
                })
                redeem_resp = make_request(REDEEM_URL, redeem_payload)

                if not redeem_resp:
                    self.log(f"{nickname}({fid}) - 兑换请求失败（无响应），重试中...", level='warn')
                    if attempt < CAPTCHA_RETRIES - 1:
                        time.sleep(RETRY_DELAY)
                        continue
                    else:
                        final_redeem_data = {"msg": "Redemption request failed"}
                        break

                try:
                    final_redeem_data = redeem_resp.json()
                    msg = final_redeem_data.get('msg', 'Unknown error').strip('.')
                    err_code = final_redeem_data.get('err_code')

                    is_captcha_check_error = (msg == "CAPTCHA CHECK ERROR" or err_code == 40103)
                    is_captcha_rate_limit = (msg == "CAPTCHA CHECK TOO FREQUENT" or err_code == 40104)
                    is_sign_error = (msg == "Sign Error" or err_code == 40001)
                    is_server_retry_request = (msg in ["Server requested retry", "TIMEOUT RETRY"])
                    is_not_logged_in = (msg == "NOT LOGIN" or err_code == 40101)

                    if is_captcha_check_error:
                        self.log(f"{nickname}({fid}) - 验证码校验失败，重新获取...", level='warn')
                        self.counters["captcha_redeem_failure"] += 1
                        if attempt < CAPTCHA_RETRIES - 1:
                            time.sleep(random.uniform(2.0, 3.5))
                            continue
                        else:
                            self.log(f"{nickname}({fid}) - 验证码校验失败次数已达上限", level='error')
                            break

                    elif is_captcha_rate_limit:
                        self.log(f"{nickname}({fid}) - 验证码请求过于频繁，加入重试队列", level='warn')
                        retry_queue[fid] = time.time() + CAPTCHA_SLEEP
                        self.counters["captcha_rate_limited"] += 1
                        self.counters["captcha_redeem_failure"] += 1
                        break

                    elif is_sign_error or is_server_retry_request:
                        self.log(f"{nickname}({fid}) - 请求失败({msg})，重试中...", level='warn')
                        if attempt < CAPTCHA_RETRIES - 1:
                            time.sleep(RETRY_DELAY)
                            continue
                        else:
                            break

                    elif is_not_logged_in:
                        self.log(f"{nickname}({fid}) - 会话过期或无效，跳过", level='error')
                        break

                    else:
                        if not is_captcha_check_error and not is_captcha_rate_limit:
                            self.counters["captcha_redeem_success"] += 1
                        break

                except json.JSONDecodeError:
                    self.log(f"{nickname}({fid}) - 兑换响应 JSON 解析失败", level='error')
                    final_redeem_data = {"msg": "Redemption JSON Decode Error"}
                    break

            except Exception as e:
                self.log(f"{nickname}({fid}) - 兑换过程出错: {e}", level='error')
                final_redeem_data = {"msg": f"Unexpected Error: {e}"}
                break

        raw_msg = final_redeem_data.get('msg', 'Unknown error').strip('.')
        friendly_msg = RESULT_MESSAGES.get(raw_msg, raw_msg)

        is_queued_for_retry = fid in retry_queue and retry_queue[fid] > time.time()
        log_level = 'info'
        if not is_queued_for_retry:
            if raw_msg in ["SUCCESS", "SAME TYPE EXCHANGE"]:
                log_level = 'success'
            elif raw_msg == "RECEIVED":
                log_level = 'info'
            elif raw_msg in ["TIME ERROR", "USED"]:
                log_level = 'warn'
            else:
                log_level = 'error'
        else:
            log_level = 'warn'

        self.log(f"{nickname}({fid}) - 结果: {friendly_msg}", level=log_level)

        return final_redeem_data, retry_queue

    def read_csv_with_names(self, file_path):
        rows = []
        encodings_to_try = ['utf-8-sig', 'utf-8', 'latin-1', 'gbk']

        for encoding in encodings_to_try:
            try:
                with open(file_path, mode="r", newline="", encoding=encoding) as file:
                    content = file.read()
                    if not content.strip():
                        return rows

                    file_like = io.StringIO(content)
                    reader = csv.reader(file_like)

                    for row in reader:
                        if not row:
                            continue
                        fid = row[0].strip() if len(row) > 0 else ""
                        name = row[1].strip() if len(row) > 1 else ""
                        if fid.isdigit():
                            rows.append({"fid": fid, "name": name})

                    return rows

            except FileNotFoundError:
                raise
            except UnicodeDecodeError:
                continue
            except Exception as e:
                self.log(f"读取 CSV 文件出错: {e}", level='error')
                return rows

        self.log(f"无法解码文件 {os.path.basename(file_path)}", level='error')
        return rows

    def update_name_in_csv(self, file_path, fid, name):
        rows = self.read_csv_with_names(file_path)
        updated = False
        for row in rows:
            if row["fid"] == fid:
                row["name"] = name
                updated = True
                break

        if updated:
            self._write_csv(file_path, rows)
            if self.name_update_callback:
                self.name_update_callback(fid, name)

    def append_id_to_csv(self, file_path, fid, nickname=""):
        rows = self.read_csv_with_names(file_path)
        existing_fids = {r["fid"] for r in rows}
        if fid not in existing_fids:
            rows.append({"fid": fid, "name": nickname})
            self._write_csv(file_path, rows)

    def delete_id_from_csv(self, file_path, fid):
        rows = self.read_csv_with_names(file_path)
        rows = [r for r in rows if r["fid"] != fid]
        self._write_csv(file_path, rows)

    def update_id_in_csv(self, file_path, old_fid, new_fid):
        rows = self.read_csv_with_names(file_path)
        for row in rows:
            if row["fid"] == old_fid:
                row["fid"] = new_fid
                row["name"] = ""
                break
        self._write_csv(file_path, rows)

    def _write_csv(self, file_path, rows):
        with open(file_path, mode="w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            for row in rows:
                writer.writerow([row["fid"], row.get("name", "")])

    def redeem_all(self, gift_code, selected_fids=None, csv_filename="player.csv"):
        self.stop_flag = False
        self.running = True
        self._reset_counters()
        self.script_start_time = time.time()

        csv_path = self._get_runtime_path(csv_filename)
        if not os.path.exists(csv_path):
            self.log(f"未找到 {csv_filename} 文件（路径: {csv_path}）", level='error')
            self.running = False
            return self._build_summary(gift_code)

        try:
            csv_rows = self.read_csv_with_names(csv_path)
        except FileNotFoundError:
            self.log(f"{csv_filename} 文件不存在", level='error')
            self.running = False
            return self._build_summary(gift_code)

        all_ids_from_csv = [r["fid"] for r in csv_rows if r["fid"].isdigit()]

        if selected_fids:
            all_player_ids = sorted([fid for fid in all_ids_from_csv if fid in set(selected_fids)], key=int)
        else:
            all_player_ids = sorted(list(set(all_ids_from_csv)), key=int)

        if not all_player_ids:
            self.log("CSV 文件中未找到有效的玩家 ID", level='error')
            self.running = False
            return self._build_summary(gift_code)

        self.log(f"共加载 {len(all_player_ids)} 个有效玩家 ID")
        self.log(f"礼包码: {gift_code}")

        retry_queue = {}
        processed_fids = set()
        stop_processing = False

        while len(processed_fids) < len(all_player_ids) and not stop_processing and not self.stop_flag:
            current_time = time.time()
            fids_to_process_now = []
            fids_in_cooldown_count = 0

            for fid in all_player_ids:
                if fid in processed_fids:
                    continue
                if fid in retry_queue and retry_queue[fid] > current_time:
                    fids_in_cooldown_count += 1
                else:
                    fids_to_process_now.append(fid)

            if not fids_to_process_now and fids_in_cooldown_count > 0:
                next_retry_time = min(retry_queue[fid] for fid in all_player_ids
                                      if fid not in processed_fids and fid in retry_queue)
                wait_time = max(1, min(30, next_retry_time - current_time + 1))
                self.log(f"{fids_in_cooldown_count} 个玩家冷却中，等待 {int(wait_time)} 秒... 进度: {len(processed_fids)}/{len(all_player_ids)}")
                time.sleep(wait_time)
                continue

            if not fids_to_process_now and fids_in_cooldown_count == 0:
                break

            for fid in fids_to_process_now:
                if self.stop_flag:
                    stop_processing = True
                    break
                if fid in processed_fids:
                    continue

                login_payload = encode_data({"fid": fid, "time": int(time.time() * 1000)})
                login_resp = make_request(LOGIN_URL, login_payload)

                if not login_resp:
                    self.log(f"玩家 {fid} 登录请求失败", level='error')
                    processed_fids.add(fid)
                    self.counters["errors"] += 1
                    self.error_details[fid] = "登录请求失败"
                    self._update_progress(len(processed_fids), len(all_player_ids),
                                          self.counters["success"], self.counters["already_redeemed"],
                                          self.counters["errors"])
                    continue

                try:
                    login_data = login_resp.json()
                    if login_data.get("code") != 0:
                        login_msg = login_data.get('msg', '未知错误')
                        self.log(f"玩家 {fid} 登录失败: {login_msg}", level='error')
                        processed_fids.add(fid)
                        self.counters["errors"] += 1
                        self.error_details[fid] = f"登录失败: {login_msg}"
                        self._update_progress(len(processed_fids), len(all_player_ids),
                                              self.counters["success"], self.counters["already_redeemed"],
                                              self.counters["errors"])
                        continue

                    nickname = login_data.get("data", {}).get("nickname", "未知玩家")
                    server_id = login_data.get("data", {}).get("server_id", "???")
                    fid_index = all_player_ids.index(fid) + 1
                    self.log(f"处理 S{server_id}-{nickname}({fid}) [{fid_index}/{len(all_player_ids)}]")

                    self.update_name_in_csv(csv_path, fid, nickname)
                except Exception as e:
                    self.log(f"玩家 {fid} 登录异常: {e}", level='error')
                    processed_fids.add(fid)
                    self.counters["errors"] += 1
                    self.error_details[fid] = f"登录异常: {e}"
                    self._update_progress(len(processed_fids), len(all_player_ids),
                                          self.counters["success"], self.counters["already_redeemed"],
                                          self.counters["errors"])
                    continue

                result, retry_queue = self.redeem_gift_code(fid, gift_code, nickname, retry_queue)

                raw_msg = result.get('msg', 'Unknown error').strip('.')
                is_queued_for_retry = fid in retry_queue and retry_queue[fid] > time.time()
                is_final_state = not is_queued_for_retry

                if is_final_state:
                    processed_fids.add(fid)
                    if raw_msg in ["SUCCESS", "SAME TYPE EXCHANGE"]:
                        self.counters["success"] += 1
                    elif raw_msg == "RECEIVED":
                        self.counters["already_redeemed"] += 1
                    elif raw_msg not in ["TIME ERROR", "USED", "Invalid FID format", "In cooldown",
                                         "CAPTCHA CHECK TOO FREQUENT"]:
                        self.counters["errors"] += 1
                        friendly_msg = RESULT_MESSAGES.get(raw_msg, raw_msg)
                        self.error_details[fid] = friendly_msg

                if raw_msg == "TIME ERROR":
                    self.log("礼包码已过期！停止处理。", level='warn')
                    stop_processing = True
                elif raw_msg == "USED":
                    self.log("领取次数已达上限！停止处理。", level='warn')
                    stop_processing = True

                self._update_progress(len(processed_fids), len(all_player_ids),
                                      self.counters["success"], self.counters["already_redeemed"],
                                      self.counters["errors"])

                if not stop_processing and not self.stop_flag:
                    time.sleep(DELAY + random.uniform(0, 0.5))

        if self.stop_flag:
            self.log("用户已停止兑换")
        elif stop_processing:
            self.log("兑换因礼包码过期或上限而停止")
        elif len(processed_fids) == len(all_player_ids):
            self.log(f"所有 {len(processed_fids)} 个玩家处理完毕")

        self.running = False
        return self._build_summary(gift_code)

    def _build_summary(self, gift_code):
        total_seconds = time.time() - self.script_start_time if self.script_start_time else 0
        execution_time = str(timedelta(seconds=int(total_seconds)))

        total_server_validations = self.counters.get('captcha_redeem_success', 0) + self.counters.get('captcha_redeem_failure', 0)
        ocr_attempts = self.counters.get('captcha_ocr_attempts', 0)
        ocr_success_rate = (self.counters.get('captcha_ocr_success_onnx', 0) / ocr_attempts * 100) if ocr_attempts > 0 else 0
        server_pass_rate = (self.counters.get('captcha_redeem_success', 0) / total_server_validations * 100) if total_server_validations > 0 else 0
        avg_ocr_time = (self.counters.get('captcha_ocr_total_time', 0.0) / ocr_attempts) if ocr_attempts > 0 else 0.0

        return {
            "gift_code": gift_code,
            "success": self.counters.get("success", 0),
            "already_redeemed": self.counters.get("already_redeemed", 0),
            "errors": self.counters.get("errors", 0),
            "ocr_success_rate": ocr_success_rate,
            "server_pass_rate": server_pass_rate,
            "execution_time": execution_time,
            "onnx_successes": self.counters.get("captcha_ocr_success_onnx", 0),
            "ocr_attempts": ocr_attempts,
            "ocr_retry_triggered": self.counters.get("captcha_ocr_retry_triggered", 0),
            "avg_ocr_time": avg_ocr_time,
            "rate_limited": self.counters.get("captcha_rate_limited", 0),
        }
