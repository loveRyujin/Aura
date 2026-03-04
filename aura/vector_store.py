"""Vector store — sqlite-vec backed chunk storage and similarity search."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import sqlite_vec

from aura.chunker import Chunk


@dataclass
class SearchResult:
    text: str
    page_num: int
    section: str
    distance: float


class VectorStore:
    """Wraps a SQLite database with sqlite-vec for vector similarity search."""

    def __init__(self, db_path: Path, dimension: int) -> None:
        self._db_path = db_path
        self._dimension = dimension
        self._conn: sqlite3.Connection | None = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            conn.enable_load_extension(False)
            self._conn = conn
            self._ensure_schema()
        return self._conn

    def _ensure_schema(self) -> None:
        conn = self._conn
        assert conn is not None
        conn.execute(
            "CREATE TABLE IF NOT EXISTS chunks ("
            "  id INTEGER PRIMARY KEY,"
            "  page INTEGER NOT NULL,"
            "  section TEXT NOT NULL,"
            "  text TEXT NOT NULL,"
            "  chunk_index INTEGER NOT NULL"
            ")"
        )
        conn.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0("
            f"  embedding float[{self._dimension}]"
            f")"
        )
        conn.commit()

    def is_indexed(self) -> bool:
        if not self._db_path.exists():
            return False
        conn = self._get_conn()
        row = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()
        return bool(row and row[0] > 0)

    def add_chunks(
        self,
        chunks: list[Chunk],
        embeddings: list[list[float]],
    ) -> None:
        conn = self._get_conn()
        for chunk, emb in zip(chunks, embeddings):
            rowid = chunk.chunk_index
            conn.execute(
                "INSERT INTO chunks (id, page, section, text, chunk_index) "
                "VALUES (?, ?, ?, ?, ?)",
                (rowid, chunk.page_num, chunk.section, chunk.text, rowid),
            )
            vec = np.array(emb, dtype=np.float32)
            conn.execute(
                "INSERT INTO vec_chunks (rowid, embedding) VALUES (?, ?)",
                (rowid, vec),
            )
        conn.commit()

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[SearchResult]:
        conn = self._get_conn()
        query_vec = np.array(query_embedding, dtype=np.float32)
        rows = conn.execute(
            "SELECT v.rowid, v.distance, c.text, c.page, c.section "
            "FROM vec_chunks v "
            "JOIN chunks c ON c.id = v.rowid "
            "WHERE v.embedding MATCH ? AND k = ?",
            (query_vec, top_k),
        ).fetchall()
        return [
            SearchResult(
                text=row[2],
                page_num=row[3],
                section=row[4],
                distance=row[1],
            )
            for row in rows
        ]

    def clear(self) -> None:
        conn = self._get_conn()
        conn.execute("DELETE FROM chunks")
        conn.execute("DELETE FROM vec_chunks")
        conn.commit()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
