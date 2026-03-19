"""Tests for rag.py - index status and rebuild behavior."""

import asyncio
import tempfile
from pathlib import Path

from aura.chunker import Chunk
from aura.config import EmbeddingConfig
from aura.rag import RAGService


class FakeEngine:
    """Minimal PDF engine stub for chunking tests."""

    def __init__(self, path: Path):
        self._path = path
        self.page_count = 1

    def get_page_markdown(self, page_num: int) -> str:
        return "Paragraph one.\n\nParagraph two."

    def get_section_for_page(self, page_num: int) -> str:
        return "Intro"


class FakeEmbedder:
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in texts]

    async def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0]


class TestRAGService:
    def test_get_index_status_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rag = RAGService(EmbeddingConfig(dimension=3))
            rag._embedder = FakeEmbedder()
            rag._db_path = lambda _: Path(tmpdir) / "index.db"

            status = rag.get_index_status("/tmp/book.pdf")

            assert status.exists is False
            assert status.ready is False
            assert status.stale is False

    def test_build_index_sets_metadata_and_is_reused(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            book_path = Path(tmpdir) / "book.pdf"
            book_path.write_text("test")

            rag = RAGService(EmbeddingConfig(dimension=3))
            rag._embedder = FakeEmbedder()
            rag._db_path = lambda _: Path(tmpdir) / "index.db"
            engine = FakeEngine(book_path)

            count = asyncio.run(rag.build_index(engine, str(book_path)))
            status = rag.get_index_status(str(book_path))
            second_count = asyncio.run(rag.build_index(engine, str(book_path)))

            assert count > 0
            assert status.exists is True
            assert status.ready is True
            assert status.stale is False
            assert status.chunk_count == count
            assert second_count == 0

    def test_stale_index_is_detected_and_rebuilt(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            book_path = Path(tmpdir) / "book.pdf"
            book_path.write_text("version1")

            rag = RAGService(EmbeddingConfig(dimension=3))
            rag._embedder = FakeEmbedder()
            rag._db_path = lambda _: Path(tmpdir) / "index.db"
            engine = FakeEngine(book_path)

            initial_count = asyncio.run(rag.build_index(engine, str(book_path)))
            book_path.write_text("version2")

            stale_status = rag.get_index_status(str(book_path))
            rebuilt_count = asyncio.run(rag.build_index(engine, str(book_path)))
            ready_status = rag.get_index_status(str(book_path))

            assert initial_count > 0
            assert stale_status.exists is True
            assert stale_status.ready is False
            assert stale_status.stale is True
            assert rebuilt_count > 0
            assert ready_status.ready is True
            assert ready_status.stale is False
