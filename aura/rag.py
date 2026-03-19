"""RAG service — orchestrates indexing and retrieval."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from collections.abc import Callable
from pathlib import Path

from aura.chunker import Chunk, chunk_document
from aura.config import EmbeddingConfig
from aura.embedding import EmbeddingService
from aura.pdf_engine import PDFEngine
from aura.vector_store import SearchResult, VectorStore

_INDEX_DIR = Path.home() / ".config" / "aura" / "indexes"

_EMBED_BATCH = 50


@dataclass
class RetrievedChunk:
    text: str
    page_num: int
    section: str
    distance: float


@dataclass
class IndexStatus:
    exists: bool
    ready: bool
    stale: bool
    chunk_count: int = 0


class RAGService:
    """Builds vector indexes for PDFs and retrieves relevant chunks."""

    def __init__(self, config: EmbeddingConfig) -> None:
        self._config = config
        self._embedder = EmbeddingService(config)
        self._stores: dict[str, VectorStore] = {}

    def _db_path(self, book_path: str) -> Path:
        h = hashlib.sha256(book_path.encode()).hexdigest()[:16]
        return _INDEX_DIR / f"{h}.db"

    def _get_store(self, book_path: str) -> VectorStore:
        if book_path not in self._stores:
            self._stores[book_path] = VectorStore(
                self._db_path(book_path), self._config.dimension
            )
        return self._stores[book_path]

    @staticmethod
    def _file_mtime(book_path: str) -> str:
        return str(Path(book_path).stat().st_mtime_ns)

    def get_index_status(self, book_path: str) -> IndexStatus:
        store = self._get_store(book_path)
        if not store.is_indexed():
            return IndexStatus(exists=False, ready=False, stale=False)

        stored_mtime = store.get_metadata("file_mtime")
        chunk_count = int(store.get_metadata("chunk_count") or "0")
        current_mtime = self._file_mtime(book_path)
        stale = stored_mtime is not None and stored_mtime != current_mtime
        return IndexStatus(
            exists=True,
            ready=not stale,
            stale=stale,
            chunk_count=chunk_count,
        )

    def has_index(self, book_path: str) -> bool:
        return self.get_index_status(book_path).ready

    async def has_index_async(self, book_path: str) -> bool:
        """Thread-safe async version of has_index."""
        return self.has_index(book_path)

    async def build_index(
        self,
        engine: PDFEngine,
        book_path: str,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> int:
        """Chunk the document, embed all chunks, and store them.

        Returns the total number of chunks indexed.
        """
        store = self._get_store(book_path)
        status = self.get_index_status(book_path)
        if status.ready:
            return 0
        if status.stale:
            store.clear()

        chunks = chunk_document(
            engine,
            chunk_size=self._config.chunk_size,
            chunk_overlap=self._config.chunk_overlap,
        )
        if not chunks:
            return 0

        total = len(chunks)
        all_embeddings: list[list[float]] = []

        for start in range(0, total, _EMBED_BATCH):
            batch = chunks[start : start + _EMBED_BATCH]
            texts = [c.text for c in batch]
            embs = await self._embedder.embed_texts(texts)
            all_embeddings.extend(embs)
            if on_progress:
                on_progress(min(start + _EMBED_BATCH, total), total)

        store.add_chunks(chunks, all_embeddings)
        store.set_metadata("file_mtime", self._file_mtime(book_path))
        store.set_metadata("chunk_count", str(total))
        return total

    async def retrieve(
        self,
        query: str,
        book_path: str,
        top_k: int | None = None,
    ) -> list[RetrievedChunk]:
        """Embed the query and return the most relevant chunks."""
        store = self._get_store(book_path)
        is_indexed = store.is_indexed()
        if not is_indexed:
            return []

        k = top_k or self._config.top_k
        query_emb = await self._embedder.embed_query(query)
        results: list[SearchResult] = store.search(query_emb, k)
        return [
            RetrievedChunk(
                text=r.text,
                page_num=r.page_num,
                section=r.section,
                distance=r.distance,
            )
            for r in results
        ]

    @staticmethod
    def format_context(chunks: list[RetrievedChunk]) -> str:
        """Format retrieved chunks into a context string for the LLM."""
        if not chunks:
            return ""
        parts: list[str] = []
        for c in chunks:
            header = f"--- p.{c.page_num + 1}"
            if c.section:
                header += f", {c.section}"
            header += " ---"
            parts.append(f"{header}\n{c.text}")
        return "\n\n".join(parts)

    def close(self) -> None:
        for store in self._stores.values():
            store.close()
        self._stores.clear()
