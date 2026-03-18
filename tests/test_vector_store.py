"""Tests for vector_store.py - SQLite vector storage."""

import tempfile
from pathlib import Path

import numpy as np
import pytest

from aura.chunker import Chunk
from aura.vector_store import SearchResult, VectorStore


class TestSearchResult:
    """Tests for the SearchResult dataclass."""

    def test_create(self):
        result = SearchResult(
            text="Sample text",
            page_num=5,
            section="Chapter 1",
            distance=0.1,
        )
        assert result.text == "Sample text"
        assert result.page_num == 5
        assert result.section == "Chapter 1"
        assert result.distance == 0.1


class TestVectorStore:
    """Tests for the VectorStore class."""

    def test_create_and_close(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = VectorStore(db_path, dimension=512)
            assert store._db_path == db_path
            assert store._dimension == 512
            store.close()

    def test_is_indexed_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = VectorStore(db_path, dimension=512)
            assert store.is_indexed() is False
            store.close()

    def test_add_chunks_and_is_indexed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = VectorStore(db_path, dimension=3)

            chunks = [
                Chunk(text="First chunk", page_num=0, section="Intro", chunk_index=0),
                Chunk(text="Second chunk", page_num=1, section="Intro", chunk_index=1),
            ]
            embeddings = [
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
            ]

            store.add_chunks(chunks, embeddings)
            assert store.is_indexed() is True
            store.close()

    def test_search_returns_results(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = VectorStore(db_path, dimension=3)

            chunks = [
                Chunk(text="Cat sitting", page_num=0, section="Animals", chunk_index=0),
                Chunk(text="Dog running", page_num=1, section="Animals", chunk_index=1),
            ]
            embeddings = [
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
            ]
            store.add_chunks(chunks, embeddings)

            # Search for something similar to first chunk
            results = store.search([0.9, 0.1, 0.0], top_k=1)

            assert len(results) >= 1
            assert results[0].text == "Cat sitting"
            store.close()

    def test_search_top_k(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = VectorStore(db_path, dimension=3)

            chunks = [
                Chunk(text=f"Chunk {i}", page_num=i, section="Section", chunk_index=i)
                for i in range(10)
            ]
            # Create embeddings that will rank chunk 0 highest for query [1, 0, 0]
            embeddings = [[1.0 - i * 0.05, 0.1, 0.1] for i in range(10)]
            store.add_chunks(chunks, embeddings)

            results = store.search([1.0, 0.0, 0.0], top_k=3)
            assert len(results) == 3
            store.close()

    def test_clear(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = VectorStore(db_path, dimension=3)

            chunks = [
                Chunk(text="Test chunk", page_num=0, section="Test", chunk_index=0),
            ]
            embeddings = [[1.0, 0.0, 0.0]]
            store.add_chunks(chunks, embeddings)

            assert store.is_indexed() is True
            store.clear()
            assert store.is_indexed() is False
            store.close()

    def test_close_multiple_times(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = VectorStore(db_path, dimension=3)
            store.close()
            # Should not raise
            store.close()

    def test_search_empty_store(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = VectorStore(db_path, dimension=3)

            results = store.search([1.0, 0.0, 0.0], top_k=5)
            assert results == []
            store.close()

    def test_search_result_attributes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = VectorStore(db_path, dimension=3)

            chunks = [
                Chunk(text="Test text", page_num=5, section="Chapter 1", chunk_index=0),
            ]
            embeddings = [[1.0, 0.0, 0.0]]
            store.add_chunks(chunks, embeddings)

            results = store.search([1.0, 0.0, 0.0], top_k=1)
            assert len(results) == 1
            result = results[0]
            assert result.text == "Test text"
            assert result.page_num == 5
            assert result.section == "Chapter 1"
            store.close()

    def test_creates_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "subdir" / "test.db"
            store = VectorStore(db_path, dimension=3)
            # Add some data to trigger connection and directory creation
            chunks = [Chunk(text="test", page_num=0, section="test", chunk_index=0)]
            embeddings = [[1.0, 0.0, 0.0]]
            store.add_chunks(chunks, embeddings)
            # Should create the directory
            assert db_path.parent.exists()
            store.close()
