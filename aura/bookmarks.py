"""Bookmark tracking with JSON persistence."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

_DEFAULT_PATH = Path.home() / ".config" / "aura" / "bookmarks.json"


@dataclass
class Bookmark:
    book_path: str
    page: int
    title: str
    created_at: str


class BookmarkManager:
    """Stores page-level bookmarks for PDF files."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _DEFAULT_PATH
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def list_bookmarks(self, book_path: str) -> list[Bookmark]:
        items = [b for b in self._load_all() if b.book_path == book_path]
        return sorted(items, key=lambda b: (b.page, b.created_at))

    def get_bookmark(self, book_path: str, page: int) -> Bookmark | None:
        for item in self._load_all():
            if item.book_path == book_path and item.page == page:
                return item
        return None

    def is_bookmarked(self, book_path: str, page: int) -> bool:
        return self.get_bookmark(book_path, page) is not None

    def add_bookmark(self, book_path: str, page: int, title: str) -> Bookmark:
        records = self._load_all()
        existing = self.get_bookmark(book_path, page)
        if existing is not None:
            return existing

        bookmark = Bookmark(
            book_path=book_path,
            page=page,
            title=title.strip() or f"p.{page + 1}",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        records.append(bookmark)
        self._save_all(records)
        return bookmark

    def update_bookmark(
        self,
        book_path: str,
        page: int,
        title: str,
    ) -> Bookmark | None:
        records = self._load_all()
        cleaned = title.strip()
        if not cleaned:
            return None

        for item in records:
            if item.book_path == book_path and item.page == page:
                item.title = cleaned
                self._save_all(records)
                return item
        return None

    def remove_bookmark(self, book_path: str, page: int) -> bool:
        records = self._load_all()
        filtered = [
            item for item in records if not (item.book_path == book_path and item.page == page)
        ]
        if len(filtered) == len(records):
            return False
        self._save_all(filtered)
        return True

    def toggle_bookmark(self, book_path: str, page: int, title: str) -> bool:
        if self.remove_bookmark(book_path, page):
            return False
        self.add_bookmark(book_path, page, title)
        return True

    def _load_all(self) -> list[Bookmark]:
        if not self._path.exists():
            return []
        try:
            data = json.loads(self._path.read_text())
        except Exception:
            return []

        items: list[Bookmark] = []
        for row in data:
            try:
                items.append(Bookmark(**row))
            except Exception:
                continue
        return items

    def _save_all(self, records: list[Bookmark]) -> None:
        payload = [asdict(item) for item in records]
        self._path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
