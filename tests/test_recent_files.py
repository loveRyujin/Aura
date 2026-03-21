"""Tests for recent_files.py - recent file tracking."""

import tempfile
from pathlib import Path

from aura.recent_files import RecentFileManager


class TestRecentFileManager:
    def test_record_open_and_list_recent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            recent_path = Path(tmpdir) / "recent.json"
            book = Path(tmpdir) / "book.pdf"
            book.write_text("test")

            mgr = RecentFileManager(recent_path)
            mgr.record_open(str(book), current_page=3)

            items = mgr.list_recent()
            assert len(items) == 1
            assert items[0].path == str(book)
            assert items[0].current_page == 3
            assert items[0].title == "book.pdf"

    def test_update_progress(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            recent_path = Path(tmpdir) / "recent.json"
            book = Path(tmpdir) / "book.pdf"
            book.write_text("test")

            mgr = RecentFileManager(recent_path)
            mgr.record_open(str(book), current_page=1)
            mgr.update_progress(str(book), 7)

            items = mgr.list_recent()
            assert items[0].current_page == 7

    def test_most_recent_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            recent_path = Path(tmpdir) / "recent.json"
            books_dir = Path(tmpdir) / "books"
            books_dir.mkdir()
            book = books_dir / "book.pdf"
            book.write_text("test")

            mgr = RecentFileManager(recent_path)
            mgr.record_open(str(book))

            assert mgr.most_recent_dir() == books_dir

    def test_list_recent_skips_missing_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            recent_path = Path(tmpdir) / "recent.json"
            missing = Path(tmpdir) / "missing.pdf"

            mgr = RecentFileManager(recent_path)
            mgr.record_open(str(missing))

            assert mgr.list_recent() == []
