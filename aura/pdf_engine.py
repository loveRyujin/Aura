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

    def is_page_cached(self, page_num: int) -> bool:
        return page_num in self._cache

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

    def get_toc_outline(self, max_depth: int = 2) -> str:
        """Return a compact text outline of the TOC (for system prompt)."""
        entries = self.get_toc()
        lines: list[str] = []
        for e in entries:
            if e.level <= max_depth:
                indent = "  " * (e.level - 1)
                lines.append(f"{indent}- {e.title} (p.{e.page + 1})")
        return "\n".join(lines) if lines else "(no table of contents)"

    def get_section_for_page(self, page_num: int) -> str:
        """Return the chapter/section title that contains *page_num*."""
        entries = self.get_toc()
        current_section = ""
        for e in entries:
            if e.page <= page_num:
                current_section = e.title
            else:
                break
        return current_section

    def get_page_text(self, page_num: int) -> str:
        """Return plain text for a page (for AI context, fallback)."""
        return self._doc[page_num].get_text()

    def get_full_text(self, max_pages: int | None = None) -> str:
        """Return Markdown text for the entire document (or first N pages)."""
        total = min(max_pages, self.page_count) if max_pages else self.page_count
        pages = list(range(total))
        return pymupdf4llm.to_markdown(self._doc, pages=pages)

    def get_page_range_text(self, start: int, end: int) -> str:
        """Return Markdown for a range of pages [start, end) (0-indexed)."""
        start = max(0, start)
        end = min(end, self.page_count)
        pages = list(range(start, end))
        return pymupdf4llm.to_markdown(self._doc, pages=pages)

    def render_page_pixmap(self, page_num: int, width: int) -> pymupdf.Pixmap:
        """Rasterize a page to a Pixmap scaled to fit the given width in pixels."""
        page = self._doc[page_num]
        page_rect = page.rect
        zoom = width / page_rect.width
        mat = pymupdf.Matrix(zoom, zoom)
        return page.get_pixmap(matrix=mat, alpha=False)

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
