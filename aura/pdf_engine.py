"""PDF parsing engine using PyMuPDF and PyMuPDF4LLM."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pymupdf
import pymupdf4llm


@dataclass
class TOCEntry:
    level: int
    title: str
    page: int


class PDFEngine:
    """Handles PDF file loading, text extraction, and TOC parsing."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._doc = pymupdf.open(str(path))
        self._cache: dict[int, str] = {}

    @property
    def filename(self) -> str:
        return self._path.name

    @property
    def page_count(self) -> int:
        return len(self._doc)

    def get_page_markdown(self, page_num: int) -> str:
        """Return Markdown text for a single page (0-indexed)."""
        if page_num in self._cache:
            return self._cache[page_num]

        md = pymupdf4llm.to_markdown(self._doc, pages=[page_num])
        self._cache[page_num] = md
        return md

    def get_toc(self) -> list[TOCEntry]:
        """Extract the document's table of contents."""
        raw_toc = self._doc.get_toc()
        return [
            TOCEntry(level=level, title=title, page=page - 1)
            for level, title, page in raw_toc
        ]

    def get_page_text(self, page_num: int) -> str:
        """Return plain text for a page (for AI context, fallback)."""
        return self._doc[page_num].get_text()

    def search_text(self, query: str) -> list[tuple[int, str]]:
        """Search all pages for query, return list of (page_num, snippet)."""
        results: list[tuple[int, str]] = []
        for i in range(len(self._doc)):
            page = self._doc[i]
            hits = page.search_for(query)
            if hits:
                text = page.get_text()
                idx = text.lower().find(query.lower())
                start = max(0, idx - 40)
                end = min(len(text), idx + len(query) + 40)
                snippet = text[start:end].replace("\n", " ")
                results.append((i, f"...{snippet}..."))
        return results

    def close(self) -> None:
        self._doc.close()
        self._cache.clear()

    def __del__(self) -> None:
        try:
            self._doc.close()
        except Exception:
            pass
