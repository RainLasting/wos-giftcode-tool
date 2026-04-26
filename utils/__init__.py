import os
import time
from datetime import datetime, timedelta

LOG_FILE_NAME = "redeemed_codes.txt"
DEFAULT_MAX_DAYS = 30
DEFAULT_MAX_SIZE_MB = 10


class LogManager:
    def __init__(self, app_path, max_days=None, max_size_mb=None):
        self.app_path = app_path
        self.max_days = max_days if max_days is not None else DEFAULT_MAX_DAYS
        self.max_size_mb = max_size_mb if max_size_mb is not None else DEFAULT_MAX_SIZE_MB

    def get_log_path(self, filename=LOG_FILE_NAME):
        if getattr(os.sys, 'frozen', False):
            return os.path.join(os.path.dirname(os.sys.executable), filename)
        return os.path.join(self.app_path, filename)

    def get_log_dir(self):
        log_path = self.get_log_path()
        return os.path.dirname(log_path)

    def get_log_info(self):
        log_path = self.get_log_path()
        abs_path = os.path.abspath(log_path)

        if not os.path.exists(log_path):
            return {
                "exists": False,
                "size_bytes": 0,
                "size_mb": 0.0,
                "line_count": 0,
                "oldest_entry": None,
                "newest_entry": None,
                "path": abs_path,
                "created_time": None,
                "modified_time": None
            }

        try:
            stat_info = os.stat(log_path)
            size_bytes = stat_info.st_size
            modified_time = datetime.fromtimestamp(stat_info.st_mtime)
            created_time = datetime.fromtimestamp(stat_info.st_ctime)

            with open(log_path, "r", encoding="utf-8-sig") as f:
                lines = f.readlines()

            line_count = len(lines)
            oldest = lines[0].strip() if lines else None
            newest = lines[-1].strip() if lines else None

            return {
                "exists": True,
                "size_bytes": size_bytes,
                "size_mb": round(size_bytes / (1024 * 1024), 2),
                "line_count": line_count,
                "oldest_entry": oldest[:80] if oldest else None,
                "newest_entry": newest[:80] if newest else None,
                "path": abs_path,
                "created_time": created_time.strftime("%Y-%m-%d %H:%M:%S"),
                "modified_time": modified_time.strftime("%Y-%m-%d %H:%M:%S")
            }
        except Exception as e:
            return {
                "exists": False,
                "size_bytes": 0,
                "size_mb": 0.0,
                "line_count": 0,
                "oldest_entry": None,
                "newest_entry": None,
                "path": abs_path,
                "created_time": None,
                "modified_time": None,
                "error": f"无法读取日志文件: {str(e)}"
            }

    def clean_by_days(self, days=None):
        if days is None:
            days = self.max_days

        log_path = self.get_log_path()
        if not os.path.exists(log_path):
            return {"deleted": 0, "kept": 0, "method": "days", "days": days}

        try:
            with open(log_path, "r", encoding="utf-8-sig") as f:
                lines = f.readlines()

            if not lines:
                return {"deleted": 0, "kept": 0, "method": "days", "days": days}

            cutoff_time = time.time() - (days * 86400)
            kept_lines = []
            deleted_count = 0

            for line in lines:
                try:
                    timestamp_str = line.split(" - ")[0]
                    entry_time = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                    if entry_time.timestamp() < cutoff_time:
                        deleted_count += 1
                    else:
                        kept_lines.append(line)
                except (ValueError, IndexError):
                    kept_lines.append(line)

            if deleted_count > 0:
                with open(log_path, "w", encoding="utf-8-sig", newline='') as f:
                    f.writelines(kept_lines)

            return {"deleted": deleted_count, "kept": len(kept_lines), "method": "days", "days": days}
        except Exception as e:
            return {"error": str(e), "method": "days"}

    def clean_by_size(self, max_size_mb=None):
        if max_size_mb is None:
            max_size_mb = self.max_size_mb

        log_path = self.get_log_path()
        if not os.path.exists(log_path):
            return {"deleted": 0, "kept": 0, "method": "size", "max_size_mb": max_size_mb}

        try:
            size_bytes = os.path.getsize(log_path)
            max_size_bytes = max_size_mb * 1024 * 1024

            if size_bytes <= max_size_bytes:
                return {"deleted": 0, "kept": -1, "method": "size", "max_size_mb": max_size_mb, "current_size_mb": round(size_bytes / (1024 * 1024), 2)}

            with open(log_path, "r", encoding="utf-8-sig") as f:
                lines = f.readlines()

            if not lines:
                return {"deleted": 0, "kept": 0, "method": "size", "max_size_mb": max_size_mb}

            target_size = max_size_bytes * 0.8
            kept_lines = []
            deleted_count = 0
            current_size = 0

            for line in reversed(lines):
                line_size = len(line.encode('utf-8-sig'))
                if current_size + line_size <= target_size:
                    kept_lines.insert(0, line)
                    current_size += line_size
                else:
                    deleted_count += 1

            if deleted_count > 0:
                with open(log_path, "w", encoding="utf-8-sig", newline='') as f:
                    f.writelines(kept_lines)

            return {
                "deleted": deleted_count,
                "kept": len(kept_lines),
                "method": "size",
                "max_size_mb": max_size_mb,
                "new_size_mb": round(current_size / (1024 * 1024), 2)
            }
        except Exception as e:
            return {"error": str(e), "method": "size"}

    def clean_all(self):
        log_path = self.get_log_path()
        if not os.path.exists(log_path):
            return {"deleted": 0, "method": "all"}

        try:
            size = os.path.getsize(log_path)
            with open(log_path, "r", encoding="utf-8-sig") as f:
                line_count = len(f.readlines())

            with open(log_path, "w", encoding="utf-8-sig", newline='') as f:
                pass

            return {
                "deleted": line_count,
                "method": "all",
                "size_freed_mb": round(size / (1024 * 1024), 2)
            }
        except Exception as e:
            return {"error": str(e), "method": "all"}

    def clean_auto(self):
        results = []

        size_result = self.clean_by_size()
        results.append(("size", size_result))

        days_result = self.clean_by_days()
        results.append(("days", days_result))

        return results

    def parse_log_entry(self, line):
        try:
            parts = line.strip().split(" - ", 1)
            if len(parts) == 2:
                timestamp_str, message = parts
                try:
                    timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                    return {"timestamp": timestamp, "message": message, "valid": True}
                except ValueError:
                    return {"timestamp": None, "message": line.strip(), "valid": False}
            return {"timestamp": None, "message": line.strip(), "valid": False}
        except Exception:
            return {"timestamp": None, "message": line.strip(), "valid": False}
