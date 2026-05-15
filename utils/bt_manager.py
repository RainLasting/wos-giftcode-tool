import os
import csv
import threading

BT1_FILE = "BT1.csv"
BT2_FILE = "BT2.csv"

ALLOWED_SOURCE_FILES = ["playerR1.csv", "playerR2.csv", "playerR3.csv", "playerR4R5.csv"]


class BTManager:
    def __init__(self, app_path):
        self.app_path = app_path
        self.lock = threading.Lock()
        self._bt1_cache = {}
        self._bt2_cache = {}
        self._load_cache()

    def _get_file_path(self, filename):
        if getattr(os.sys, 'frozen', False):
            return os.path.join(os.path.dirname(os.sys.executable), filename)
        return os.path.join(self.app_path, filename)

    def _load_cache(self):
        self._load_bt_cache(BT1_FILE, self._bt1_cache)
        self._load_bt_cache(BT2_FILE, self._bt2_cache)

    def _load_bt_cache(self, filename, cache):
        file_path = self._get_file_path(filename)
        if not os.path.exists(file_path):
            return

        try:
            with open(file_path, 'r', encoding='utf-8-sig', newline='') as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) >= 3:
                        fid = row[0].strip()
                        name = row[1].strip()
                        try:
                            count = int(row[2].strip())
                        except ValueError:
                            count = 0
                        if fid:
                            cache[fid] = {"name": name, "count": count}
        except Exception:
            pass

    def _save_to_file(self, filename, cache):
        file_path = self._get_file_path(filename)
        try:
            with self.lock:
                temp_path = file_path + ".tmp"
                with open(temp_path, 'w', encoding='utf-8-sig', newline='') as f:
                    writer = csv.writer(f)
                    for fid, data in cache.items():
                        writer.writerow([fid, data["name"], data["count"]])
                os.replace(temp_path, file_path)
            return True
        except Exception:
            return False

    def get_bt_count(self, fid, bt_type=1):
        fid = str(fid).strip()
        cache = self._bt1_cache if bt_type == 1 else self._bt2_cache
        return cache.get(fid, {}).get("count", 0)

    def get_bt_data(self, fid, bt_type=1):
        fid = str(fid).strip()
        cache = self._bt1_cache if bt_type == 1 else self._bt2_cache
        return cache.get(fid, {"name": "", "count": 0})

    def add_bt(self, fid, name, bt_type=1):
        fid = str(fid).strip()
        name = name.strip() if name else ""

        if not fid:
            return False

        cache = self._bt1_cache if bt_type == 1 else self._bt2_cache

        if fid in cache:
            cache[fid]["count"] += 1
            if name:
                cache[fid]["name"] = name
        else:
            cache[fid] = {"name": name, "count": 1}

        filename = BT1_FILE if bt_type == 1 else BT2_FILE
        return self._save_to_file(filename, cache)

    def subtract_bt(self, fid, name, bt_type=1):
        fid = str(fid).strip()
        name = name.strip() if name else ""

        if not fid:
            return False

        cache = self._bt1_cache if bt_type == 1 else self._bt2_cache

        if fid in cache:
            cache[fid]["count"] = max(0, cache[fid]["count"] - 1)
            if name:
                cache[fid]["name"] = name
        else:
            cache[fid] = {"name": name, "count": 0}

        filename = BT1_FILE if bt_type == 1 else BT2_FILE
        return self._save_to_file(filename, cache)

    def set_bt_count(self, fid, name, count, bt_type=1):
        fid = str(fid).strip()
        name = name.strip() if name else ""

        if not fid:
            return False

        cache = self._bt1_cache if bt_type == 1 else self._bt2_cache
        cache[fid] = {"name": name, "count": max(0, count)}

        filename = BT1_FILE if bt_type == 1 else BT2_FILE
        return self._save_to_file(filename, cache)

    def remove_player(self, fid):
        fid = str(fid).strip()
        removed = False

        if fid in self._bt1_cache:
            del self._bt1_cache[fid]
            self._save_to_file(BT1_FILE, self._bt1_cache)
            removed = True

        if fid in self._bt2_cache:
            del self._bt2_cache[fid]
            self._save_to_file(BT2_FILE, self._bt2_cache)
            removed = True

        return removed

    def has_player(self, fid, bt_type=1):
        fid = str(fid).strip()
        cache = self._bt1_cache if bt_type == 1 else self._bt2_cache
        return fid in cache

    def ensure_player_exists(self, fid, name, bt_type=1):
        fid = str(fid).strip()
        cache = self._bt1_cache if bt_type == 1 else self._bt2_cache

        if fid not in cache:
            cache[fid] = {"name": name, "count": 0}
            filename = BT1_FILE if bt_type == 1 else BT2_FILE
            return self._save_to_file(filename, cache)
        return True

    def get_all_players(self, bt_type=1):
        cache = self._bt1_cache if bt_type == 1 else self._bt2_cache
        return list(cache.keys())

    def get_total_count(self, bt_type=1):
        cache = self._bt1_cache if bt_type == 1 else self._bt2_cache
        return sum(data["count"] for data in cache.values())

    def cleanup_missing_players(self, valid_fids):
        valid_set = set(str(f).strip() for f in valid_fids)

        bt1_removed = [fid for fid in self._bt1_cache if fid not in valid_set]
        bt2_removed = [fid for fid in self._bt2_cache if fid not in valid_set]

        for fid in bt1_removed:
            del self._bt1_cache[fid]
        for fid in bt2_removed:
            del self._bt2_cache[fid]

        if bt1_removed:
            self._save_to_file(BT1_FILE, self._bt1_cache)
        if bt2_removed:
            self._save_to_file(BT2_FILE, self._bt2_cache)

        return {"bt1_removed": len(bt1_removed), "bt2_removed": len(bt2_removed)}