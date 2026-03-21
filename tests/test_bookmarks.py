"""Tests for bookmarks.py - bookmark persistence."""

import tempfile
from pathlib import Path

from aura.bookmarks import BookmarkManager


class TestBookmarkManager:
    def test_add_and_list_bookmarks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = BookmarkManager(Path(tmpdir) / "bookmarks.json")

            manager.add_bookmark("/tmp/book.pdf", 5, "Chapter 1")

            items = manager.list_bookmarks("/tmp/book.pdf")
            assert len(items) == 1
            assert items[0].page == 5
            assert items[0].title == "Chapter 1"

    def test_toggle_bookmark_adds_then_removes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = BookmarkManager(Path(tmpdir) / "bookmarks.json")

            assert manager.toggle_bookmark("/tmp/book.pdf", 1, "Intro") is True
            assert manager.is_bookmarked("/tmp/book.pdf", 1) is True
            assert manager.toggle_bookmark("/tmp/book.pdf", 1, "Intro") is False
            assert manager.is_bookmarked("/tmp/book.pdf", 1) is False

    def test_bookmarks_are_scoped_by_book(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = BookmarkManager(Path(tmpdir) / "bookmarks.json")

            manager.add_bookmark("/tmp/book1.pdf", 1, "One")
            manager.add_bookmark("/tmp/book2.pdf", 2, "Two")

            assert len(manager.list_bookmarks("/tmp/book1.pdf")) == 1
            assert len(manager.list_bookmarks("/tmp/book2.pdf")) == 1

    def test_list_bookmarks_sorted_by_page(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = BookmarkManager(Path(tmpdir) / "bookmarks.json")

            manager.add_bookmark("/tmp/book.pdf", 10, "Ten")
            manager.add_bookmark("/tmp/book.pdf", 2, "Two")

            pages = [item.page for item in manager.list_bookmarks("/tmp/book.pdf")]
            assert pages == [2, 10]

    def test_update_bookmark_title(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = BookmarkManager(Path(tmpdir) / "bookmarks.json")

            manager.add_bookmark("/tmp/book.pdf", 3, "Old")
            updated = manager.update_bookmark("/tmp/book.pdf", 3, "New")

            assert updated is not None
            assert updated.title == "New"
            assert manager.get_bookmark("/tmp/book.pdf", 3).title == "New"

    def test_update_bookmark_rejects_blank_title(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = BookmarkManager(Path(tmpdir) / "bookmarks.json")

            manager.add_bookmark("/tmp/book.pdf", 3, "Old")
            updated = manager.update_bookmark("/tmp/book.pdf", 3, "   ")

            assert updated is None
            assert manager.get_bookmark("/tmp/book.pdf", 3).title == "Old"
