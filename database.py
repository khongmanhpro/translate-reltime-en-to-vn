"""💾 Transcript database: SQLite storage with export."""

import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Optional
from loguru import logger
from config import DB_PATH


class TranscriptDB:
    """Store and retrieve meeting transcripts."""

    def __init__(self, db_path: Path = DB_PATH):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._init_tables()
        logger.info(f"💾 Database ready: {db_path}")

    def _init_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                title TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS transcripts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                original_text TEXT NOT NULL,
                translated_text TEXT DEFAULT '',
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );
            CREATE INDEX IF NOT EXISTS idx_session ON transcripts(session_id);
        """)
        self.conn.commit()

    def start_session(self, title: str = "") -> int:
        cur = self.conn.execute(
            "INSERT INTO sessions (started_at, title) VALUES (?, ?)",
            (datetime.now().isoformat(), title)
        )
        self.conn.commit()
        session_id = cur.lastrowid
        logger.info(f"📝 Session #{session_id} started: {title or '(untitled)'}")
        return session_id

    def end_session(self, session_id: int):
        self.conn.execute(
            "UPDATE sessions SET ended_at = ? WHERE id = ?",
            (datetime.now().isoformat(), session_id)
        )
        self.conn.commit()

    def add_entry(self, session_id: int, original: str, translated: str = ""):
        self.conn.execute(
            "INSERT INTO transcripts (session_id, timestamp, original_text, translated_text) VALUES (?, ?, ?, ?)",
            (session_id, datetime.now().isoformat(), original, translated)
        )
        self.conn.commit()

    def get_session(self, session_id: int) -> Optional[dict]:
        cur = self.conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        row = cur.fetchone()
        if not row:
            return None
        return {"id": row[0], "started_at": row[1], "ended_at": row[2], "title": row[3]}

    def get_transcripts(self, session_id: int) -> list[dict]:
        cur = self.conn.execute(
            "SELECT timestamp, original_text, translated_text FROM transcripts WHERE session_id = ? ORDER BY id",
            (session_id,)
        )
        return [{"timestamp": r[0], "original": r[1], "translated": r[2]} for r in cur.fetchall()]

    def get_sessions(self, limit: int = 50) -> list[dict]:
        cur = self.conn.execute(
            "SELECT id, started_at, ended_at, title FROM sessions ORDER BY id DESC LIMIT ?",
            (limit,)
        )
        return [{"id": r[0], "started_at": r[1], "ended_at": r[2], "title": r[3]} for r in cur.fetchall()]

    def export_srt(self, session_id: int) -> str:
        """Export transcript as SRT subtitle format."""
        entries = self.get_transcripts(session_id)
        srt_lines = []
        for i, entry in enumerate(entries, 1):
            ts = entry["timestamp"]
            orig = entry["original"]
            trans = entry["translated"]
            srt_lines.append(f"{i}")
            srt_lines.append(f"00:00:{i*2:02d},000 --> 00:00:{i*2+2:02d},000")
            srt_lines.append(orig)
            if trans:
                srt_lines.append(trans)
            srt_lines.append("")
        return "\n".join(srt_lines)

    def export_txt(self, session_id: int) -> str:
        """Export transcript as plain text."""
        entries = self.get_transcripts(session_id)
        lines = []
        for entry in entries:
            ts = entry["timestamp"]
            lines.append(f"[{ts}] {entry['original']}")
            if entry["translated"]:
                lines.append(f"         → {entry['translated']}")
            lines.append("")
        return "\n".join(lines)

    def close(self):
        self.conn.close()
        logger.info("💾 Database closed")
