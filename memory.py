import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional

class MemoryModule:
    def __init__(self, db_path: str = 'memory.db', json_path: str = 'memory.json'):
        self.db_path = db_path
        self.json_path = json_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            user_message TEXT,
            geny_reply TEXT
        )''')
        conn.commit()
        conn.close()

    def save_interaction(self, user_message: str, geny_reply: str):
        timestamp = datetime.utcnow().isoformat()
        # Save to SQLite
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('INSERT INTO conversations (timestamp, user_message, geny_reply) VALUES (?, ?, ?)',
                  (timestamp, user_message, geny_reply))
        conn.commit()
        conn.close()
        # Save to JSON
        try:
            with open(self.json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {"interactions": []}
        data["interactions"].append({
            "timestamp": timestamp,
            "message": user_message,
            "reply": geny_reply
        })
        with open(self.json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_last_n(self, n: int = 5) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT timestamp, user_message, geny_reply FROM conversations ORDER BY id DESC LIMIT ?', (n,))
        rows = c.fetchall()
        conn.close()
        return [{"timestamp": r[0], "message": r[1], "reply": r[2]} for r in rows]

    def search(self, query: str) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''SELECT timestamp, user_message, geny_reply FROM conversations
                     WHERE user_message LIKE ? OR geny_reply LIKE ? ORDER BY id DESC''',
                  (f'%{query}%', f'%{query}%'))
        rows = c.fetchall()
        conn.close()
        return [{"timestamp": r[0], "message": r[1], "reply": r[2]} for r in rows]

    def export_json(self, export_path: Optional[str] = None):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT timestamp, user_message, geny_reply FROM conversations ORDER BY id ASC')
        rows = c.fetchall()
        conn.close()
        data = {"interactions": [{"timestamp": r[0], "message": r[1], "reply": r[2]} for r in rows]}
        path = export_path or self.json_path
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

# Example usage:
# mem = MemoryModule()
# mem.save_interaction("Hello Geny!", "Hi! How can I help?")
# print(mem.get_last_n(5))
# print(mem.search("help"))
# mem.export_json("backup.json")
