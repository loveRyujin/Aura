"""Document chunker — splits PDF pages into semantically meaningful chunks."""

from __future__ import annotations

from dataclasses import dataclass

from aura.pdf_engine import PDFEngine


@dataclass
class Chunk:
    text: str
    page_num: int
    section: str
    chunk_index: int


def chunk_document(
    engine: PDFEngine,
    chunk_size: int = 1024,
    chunk_overlap: int = 128,
) -> list[Chunk]:
    """Split every page of *engine* into overlapping text chunks."""
    chunks: list[Chunk] = []
    idx = 0

    for page_num in range(engine.page_count):
        page_md = engine.get_page_markdown(page_num)
        if not page_md.strip():
            continue

        section = engine.get_section_for_page(page_num)
        paragraphs = _split_paragraphs(page_md)
        page_chunks = _merge_and_split(paragraphs, chunk_size, chunk_overlap)

        for text in page_chunks:
            chunks.append(Chunk(
                text=text,
                page_num=page_num,
                section=section,
                chunk_index=idx,
            ))
            idx += 1

    return chunks


def _split_paragraphs(text: str) -> list[str]:
    """Split text on double-newlines, dropping empty fragments."""
    raw = text.split("\n\n")
    return [p.strip() for p in raw if p.strip()]


def _merge_and_split(
    paragraphs: list[str],
    chunk_size: int,
    overlap: int,
) -> list[str]:
    """Merge small paragraphs up to *chunk_size*; split oversized ones."""
    results: list[str] = []
    buffer: list[str] = []
    buf_len = 0

    for para in paragraphs:
        if len(para) > chunk_size:
            if buffer:
                results.append("\n\n".join(buffer))
                buffer.clear()
                buf_len = 0
            results.extend(_sliding_window(para, chunk_size, overlap))
            continue

        candidate_len = buf_len + len(para) + (2 if buffer else 0)
        if candidate_len > chunk_size and buffer:
            results.append("\n\n".join(buffer))
            # Keep last paragraph as overlap seed
            if overlap > 0 and buffer:
                last = buffer[-1]
                buffer.clear()
                buffer.append(last)
                buf_len = len(last)
            else:
                buffer.clear()
                buf_len = 0

        buffer.append(para)
        buf_len += len(para) + (2 if len(buffer) > 1 else 0)

    if buffer:
        results.append("\n\n".join(buffer))

    return results


def _sliding_window(text: str, size: int, overlap: int) -> list[str]:
    """Break a long string into overlapping windows."""
    step = max(size - overlap, 1)
    parts: list[str] = []
    for start in range(0, len(text), step):
        segment = text[start : start + size]
        if segment.strip():
            parts.append(segment.strip())
        if start + size >= len(text):
            break
    return parts
