import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Optional

from bingus_ia.core.types import MemoryEntry


class SQLiteStore:
    def __init__(self, db_path: str = "memory_store/bingus_memory.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    prompt TEXT NOT NULL,
                    response TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    metadata TEXT DEFAULT '{}'
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp
                ON memories(timestamp DESC)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS embeddings (
                    memory_id TEXT PRIMARY KEY,
                    vector BLOB,
                    FOREIGN KEY (memory_id) REFERENCES memories(id)
                )
            """)

    def store(self, entry: MemoryEntry) -> str:
        entry.id = entry.id or str(uuid.uuid4())
        entry.timestamp = entry.timestamp or time.time()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO memories (id, prompt, response, timestamp, metadata) VALUES (?, ?, ?, ?, ?)",
                (entry.id, entry.prompt, entry.response, entry.timestamp, json.dumps(entry.metadata)),
            )
            if entry.embedding:
                import struct
                blob = struct.pack(f"{len(entry.embedding)}d", *entry.embedding)
                conn.execute(
                    "INSERT OR REPLACE INTO embeddings (memory_id, vector) VALUES (?, ?)",
                    (entry.id, blob),
                )
        return entry.id

    def search_by_text(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT id, prompt, response, timestamp, metadata FROM memories "
                "WHERE prompt LIKE ? OR response LIKE ? "
                "ORDER BY timestamp DESC LIMIT ?",
                (f"%{query}%", f"%{query}%", limit),
            ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def get_recent(self, limit: int = 20) -> list[MemoryEntry]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT id, prompt, response, timestamp, metadata FROM memories "
                "ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def get_by_id(self, memory_id: str) -> Optional[MemoryEntry]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT id, prompt, response, timestamp, metadata FROM memories WHERE id = ?",
                (memory_id,),
            ).fetchone()
        return self._row_to_entry(row) if row else None

    def delete_old(self, older_than: float) -> int:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM embeddings WHERE memory_id IN (SELECT id FROM memories WHERE timestamp < ?)", (older_than,))
            deleted = conn.execute("DELETE FROM memories WHERE timestamp < ?", (older_than,)).rowcount
        return deleted

    def _row_to_entry(self, row) -> MemoryEntry:
        return MemoryEntry(
            id=row[0],
            prompt=row[1],
            response=row[2],
            timestamp=row[3],
            metadata=json.loads(row[4]) if row[4] else {},
        )
