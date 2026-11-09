from __future__ import annotations
import json
import sqlite3
import time
import uuid


class Store:
    def __init__(self, path):
        self.path = str(path)
        with self.db() as db:
            db.executescript("CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, title TEXT, workspace TEXT, updated REAL, messages TEXT); CREATE TABLE IF NOT EXISTS events (run TEXT, idx INTEGER, session TEXT, data TEXT, PRIMARY KEY(run,idx));")

    def db(self):
        return sqlite3.connect(self.path, timeout=15)

    def create(self, workspace):
        sid = uuid.uuid4().hex
        with self.db() as db:
            db.execute("INSERT INTO sessions VALUES (?,?,?,?,?)", (sid, "新对话", workspace, time.time(), "[]"))
        return sid

    def sessions(self, workspace):
        with self.db() as db:
            rows = db.execute("SELECT id,title,updated FROM sessions WHERE workspace=? ORDER BY updated DESC LIMIT 50", (workspace,)).fetchall()
        return [{"id": r[0], "title": r[1], "updated": r[2]} for r in rows]

    def load(self, sid, workspace):
        with self.db() as db:
            row = db.execute("SELECT messages FROM sessions WHERE id=? AND workspace=?", (sid, workspace)).fetchone()
        if not row:
            raise ValueError("会话不存在或不属于当前工作区")
        return json.loads(row[0])

    def save(self, sid, title, messages):
        with self.db() as db:
            db.execute("UPDATE sessions SET title=?,updated=?,messages=? WHERE id=?", (title[:50], time.time(), json.dumps(messages, ensure_ascii=False), sid))

    def event(self, run, sid, event):
        with self.db() as db:
            db.execute("INSERT OR REPLACE INTO events VALUES (?,?,?,?)", (run, event["id"], sid, json.dumps(event, ensure_ascii=False)))

    def events(self, sid):
        with self.db() as db:
            rows = db.execute("SELECT data FROM events WHERE session=? ORDER BY rowid", (sid,)).fetchall()
        return [json.loads(r[0]) for r in rows]

