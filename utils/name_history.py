import os
import csv
import threading

NAME_ABANDONED_FILE = "nameAbandoned.csv"


class NameHistoryManager:
    def __init__(self, app_path):
        self.app_path = app_path
        self.lock = threading.Lock()
        self._cache = {}
        self._load_cache()

    def _get_file_path(self):
        if getattr(os.sys, 'frozen', False):
            return os.path.join(os.path.dirname(os.sys.executable), NAME_ABANDONED_FILE)
        return os.path.join(self.app_path, NAME_ABANDONED_FILE)

    def _load_cache(self):
        file_path = self._get_file_path()
        if not os.path.exists(file_path):
            return

        try:
            with self.lock:
                with open(file_path, 'r', encoding='utf-8-sig', newline='') as f:
                    reader = csv.reader(f)
                    for row in reader:
                        if len(row) >= 2:
                            fid = row[0].strip()
                            names = [name.strip() for name in row[1:] if name.strip()]
                            if fid and names:
                                self._cache[fid] = names
        except Exception:
            pass

    def _save_to_file(self):
        file_path = self._get_file_path()
        try:
            with self.lock:
                temp_path = file_path + ".tmp"
                with open(temp_path, 'w', encoding='utf-8-sig', newline='') as f:
                    writer = csv.writer(f)
                    for fid, names in self._cache.items():
                        writer.writerow([fid] + names)
                os.replace(temp_path, file_path)
            return True
        except Exception:
            return False

    def get_name_history(self, fid):
        fid = str(fid).strip()
        return self._cache.get(fid, [])

    def update_name(self, fid, new_name):
        fid = str(fid).strip()
        new_name = new_name.strip() if new_name else ""

        if not fid or not new_name:
            return False

        current_names = self._cache.get(fid, [])

        if current_names and current_names[-1] == new_name:
            return False

        current_names.append(new_name)
        self._cache[fid] = current_names
        return self._save_to_file()

    def get_latest_name(self, fid):
        fid = str(fid).strip()
        names = self._cache.get(fid, [])
        return names[-1] if names else None

    def has_history(self, fid):
        fid = str(fid).strip()
        names = self._cache.get(fid, [])
        return len(names) > 1

    def get_all_fids(self):
        return list(self._cache.keys())

    def clear_history(self, fid):
        fid = str(fid).strip()
        if fid in self._cache:
            del self._cache[fid]
            return self._save_to_file()
        return False

    def get_history_count(self):
        return sum(len(names) - 1 for names in self._cache.values())
