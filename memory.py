import json
import os
import sqlite3
import tempfile
from datetime import datetime
from typing import Dict, List, Optional


class MemoryModule:
    def __init__(self, db_path: str = "memory.db", json_path: str = "memory.json"):
        self.db_path = db_path
        self.json_path = json_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            """CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            user_message TEXT,
            geny_reply TEXT
        )"""
        )
        conn.commit()
        conn.close()

    def save_interaction(self, user_message: str, geny_reply: str):
        timestamp = datetime.utcnow().isoformat()
        # Save to SQLite
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            "INSERT INTO conversations (timestamp, user_message, geny_reply) VALUES (?, ?, ?)",
            (timestamp, user_message, geny_reply),
        )
        conn.commit()
        conn.close()
        # Save to JSON
        try:
            with open(self.json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {"interactions": []}
        data["interactions"].append(
            {"timestamp": timestamp, "message": user_message, "reply": geny_reply}
        )
        # Atomic write to avoid corruption
        tmp_fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(self.json_path) or ".")
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.json_path)
        except Exception:
            try:
                os.remove(tmp_path)
            except Exception:
                pass

    def get_last_n(self, n: int = 5) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            "SELECT timestamp, user_message, geny_reply FROM conversations ORDER BY id DESC LIMIT ?",
            (n,),
        )
        rows = c.fetchall()
        conn.close()
        # rows are returned newest-first; reverse to chronological order
        rows = list(reversed(rows))
        return [{"timestamp": r[0], "message": r[1], "reply": r[2]} for r in rows]

    def load_memory_dict(self) -> Dict:
        """Load the JSON memory file as a dict. Returns default structure on error."""
        try:
            if not os.path.exists(self.json_path):
                return {"interactions": []}
            with open(self.json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {"interactions": []}
            # ensure interactions key
            data.setdefault("interactions", [])
            return data
        except Exception:
            return {"interactions": []}

    def save_memory_dict(self, mem: Dict) -> None:
        """Atomically save a memory dict to the JSON path."""
        try:
            tmp_fd, tmp_path = tempfile.mkstemp(
                dir=os.path.dirname(self.json_path) or "."
            )
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(mem, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.json_path)
        except Exception:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        # Also persist interactions to SQLite for consistency
        try:
            interactions = mem.get("interactions", []) if isinstance(mem, dict) else []
            if interactions:
                conn = sqlite3.connect(self.db_path)
                c = conn.cursor()
                for it in interactions:
                    ts = it.get("timestamp") or datetime.utcnow().isoformat()
                    msg = it.get("message") or it.get("user_message") or ""
                    reply = it.get("reply") or it.get("geny_reply") or ""
                    # Avoid duplicates: check for exact timestamp+message
                    c.execute(
                        "SELECT id FROM conversations WHERE timestamp = ? AND user_message = ? LIMIT 1",
                        (ts, msg),
                    )
                    if not c.fetchone():
                        c.execute(
                            "INSERT INTO conversations (timestamp, user_message, geny_reply) VALUES (?, ?, ?)",
                            (ts, msg, reply),
                        )
                conn.commit()
                conn.close()
        except Exception:
            # best-effort only
            pass

    def search(self, query: str) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            """SELECT timestamp, user_message, geny_reply FROM conversations
                     WHERE user_message LIKE ? OR geny_reply LIKE ? ORDER BY id DESC""",
            (f"%{query}%", f"%{query}%"),
        )
        rows = c.fetchall()
        conn.close()
        return [{"timestamp": r[0], "message": r[1], "reply": r[2]} for r in rows]

    def export_json(self, export_path: Optional[str] = None):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            "SELECT timestamp, user_message, geny_reply FROM conversations ORDER BY id ASC"
        )
        rows = c.fetchall()
        conn.close()
        data = {
            "interactions": [
                {"timestamp": r[0], "message": r[1], "reply": r[2]} for r in rows
            ]
        }
        path = export_path or self.json_path
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


# Example usage:
# mem = MemoryModule()
# mem.save_interaction("Hello Geny!", "Hi! How can I help?")
# print(mem.get_last_n(5))
# print(mem.search("help"))
# mem.export_json("backup.json")
