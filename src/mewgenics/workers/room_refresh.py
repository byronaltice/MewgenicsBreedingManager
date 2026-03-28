"""QuickRoomRefreshWorker: fast room assignment refresh without full parse."""
import sqlite3

from PySide6.QtCore import QThread, Signal

from save_parser import _get_house_info, _get_adventure_keys


class QuickRoomRefreshWorker(QThread):
    """Fast path: re-reads only house_state/adventure_state to update room assignments.

    If the set of cat keys in the DB has changed (birth/death), emits needs_full_reload
    instead so the caller can fall back to a full SaveLoadWorker parse.
    """
    room_patch = Signal(object)      # dict[int, tuple[str, str]]  db_key → (room, status)
    needs_full_reload = Signal()

    def __init__(self, path: str, expected_keys: set, parent=None):
        super().__init__(parent)
        self._path = path
        self._expected_keys = expected_keys

    def run(self):
        try:
            conn = sqlite3.connect(f"file:{self._path}?mode=ro", uri=True)
            live_keys = {row[0] for row in conn.execute("SELECT key FROM cats").fetchall()}
            if live_keys != self._expected_keys:
                conn.close()
                self.needs_full_reload.emit()
                return
            house = _get_house_info(conn)
            adv = _get_adventure_keys(conn)
            conn.close()
            patch: dict[int, tuple[str, str]] = {}
            for key in live_keys:
                if key in adv:
                    patch[key] = ("Adventure", "Adventure")
                elif key in house:
                    patch[key] = (house[key], "In House")
                else:
                    patch[key] = ("", "Gone")
            self.room_patch.emit(patch)
        except Exception:
            self.needs_full_reload.emit()
