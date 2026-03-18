"""Tests for session.py - ChatSession and SessionManager."""

import json
import tempfile
from pathlib import Path

import pytest

from aura.session import ChatSession, SessionManager, _book_hash


class TestBookHash:
    """Tests for the _book_hash function."""

    def test_same_path_produces_same_hash(self):
        path = "/path/to/book.pdf"
        assert _book_hash(path) == _book_hash(path)

    def test_different_paths_produce_different_hashes(self):
        path1 = "/path/to/book1.pdf"
        path2 = "/path/to/book2.pdf"
        assert _book_hash(path1) != _book_hash(path2)

    def test_hash_length(self):
        path = "/path/to/book.pdf"
        assert len(_book_hash(path)) == 8


class TestChatSession:
    """Tests for the ChatSession dataclass."""

    def test_create_session(self):
        session = ChatSession(
            id="test123",
            title="Test Book",
            book_path="/path/to/book.pdf",
        )
        assert session.id == "test123"
        assert session.title == "Test Book"
        assert session.book_path == "/path/to/book.pdf"
        assert session.messages == []
        assert session.compressed_summary == ""
        assert session.current_page == 0
        assert session.created_at != ""
        assert session.updated_at != ""

    def test_current_page_default(self):
        session = ChatSession(
            id="test",
            title="Test",
            book_path="/test.pdf",
        )
        assert session.current_page == 0

    def test_current_page_can_be_set(self):
        session = ChatSession(
            id="test",
            title="Test",
            book_path="/test.pdf",
            current_page=42,
        )
        assert session.current_page == 42

    def test_touch_updates_timestamp(self):
        session = ChatSession(
            id="test",
            title="Test",
            book_path="/test.pdf",
        )
        original_updated_at = session.updated_at
        session.touch()
        assert session.updated_at >= original_updated_at


class TestSessionManager:
    """Tests for the SessionManager class."""

    def test_create_session(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = SessionManager(base_dir=Path(tmpdir))
            session = mgr.create_session("/path/to/book.pdf", "Test Book")

            assert session.title == "Test Book"
            assert session.book_path == "/path/to/book.pdf"
            assert session.id != ""

    def test_save_and_load_session(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = SessionManager(base_dir=Path(tmpdir))
            session = mgr.create_session("/path/to/book.pdf", "Test Book")
            session.current_page = 42
            mgr.save_session(session)

            loaded = mgr.get_session(session.id)
            assert loaded is not None
            assert loaded.id == session.id
            assert loaded.current_page == 42
            assert loaded.title == "Test Book"

    def test_list_sessions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = SessionManager(base_dir=Path(tmpdir))
            mgr.create_session("/path/to/book1.pdf", "Book 1")
            mgr.create_session("/path/to/book2.pdf", "Book 2")

            sessions = mgr.list_sessions()
            assert len(sessions) == 2

    def test_list_sessions_for_specific_book(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = SessionManager(base_dir=Path(tmpdir))
            mgr.create_session("/path/to/book1.pdf", "Book 1")
            mgr.create_session("/path/to/book1.pdf", "Book 1 Session 2")
            mgr.create_session("/path/to/book2.pdf", "Book 2")

            sessions = mgr.list_sessions("/path/to/book1.pdf")
            assert len(sessions) == 2

    def test_delete_session(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = SessionManager(base_dir=Path(tmpdir))
            session = mgr.create_session("/path/to/book.pdf", "Test")

            mgr.delete_session(session.id)
            loaded = mgr.get_session(session.id)
            assert loaded is None

    def test_get_or_create_for_book_existing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = SessionManager(base_dir=Path(tmpdir))
            existing = mgr.create_session("/path/to/book.pdf", "Existing")
            existing.current_page = 10
            mgr.save_session(existing)

            # Create again should return existing
            result = mgr.get_or_create_for_book("/path/to/book.pdf")
            assert result.id == existing.id
            assert result.current_page == 10

    def test_get_or_create_for_book_new(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = SessionManager(base_dir=Path(tmpdir))
            result = mgr.get_or_create_for_book("/path/to/new.pdf")

            assert result.book_path == "/path/to/new.pdf"
            assert result.current_page == 0  # New sessions start at page 0

    def test_set_active_session(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = SessionManager(base_dir=Path(tmpdir))
            session = mgr.create_session("/path/to/book.pdf")

            mgr.set_active(session)
            assert mgr.active_session == session

    def test_save_session_no_active(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = SessionManager(base_dir=Path(tmpdir))
            # Should not raise
            mgr.save_session(None)
            mgr.save_session()  # No args, uses active_session
