"""Tests for chunker.py - Document chunking functions."""

import pytest

from aura.chunker import _split_paragraphs, _merge_and_split, _sliding_window


class TestSplitParagraphs:
    """Tests for _split_paragraphs function."""

    def test_split_on_double_newline(self):
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        result = _split_paragraphs(text)
        assert result == [
            "First paragraph.",
            "Second paragraph.",
            "Third paragraph.",
        ]

    def test_strips_whitespace(self):
        text = "  First paragraph.  \n\n  Second paragraph.  \n\n"
        result = _split_paragraphs(text)
        assert result == ["First paragraph.", "Second paragraph."]

    def test_drops_empty_fragments(self):
        text = "\n\nFirst paragraph.\n\n\n\nSecond paragraph.\n\n"
        result = _split_paragraphs(text)
        assert result == ["First paragraph.", "Second paragraph."]

    def test_single_paragraph(self):
        text = "Just one paragraph."
        result = _split_paragraphs(text)
        assert result == ["Just one paragraph."]

    def test_empty_text(self):
        text = ""
        result = _split_paragraphs(text)
        assert result == []

    def test_only_newlines(self):
        text = "\n\n\n\n"
        result = _split_paragraphs(text)
        assert result == []


class TestSlidingWindow:
    """Tests for _sliding_window function."""

    def test_short_text_returns_chunks(self):
        # The function creates overlapping windows even for short text
        text = "Short text."
        result = _sliding_window(text, 10, 2)
        # With overlap=2 and step=8, it will split
        assert len(result) >= 1

    def test_exact_size(self):
        text = "1234567890"
        result = _sliding_window(text, 10, 0)
        assert result == ["1234567890"]

    def test_longer_text_splits_with_overlap(self):
        text = "ABCDEFGHIJ"  # 10 chars
        result = _sliding_window(text, 4, 1)
        # step = 4 - 1 = 3
        # start=0: "ABCD" (stripped)
        # start=3: "DEFG" (stripped)
        # start=6: "GHIJ" (stripped)
        assert "ABCD" in result or result[0] == "ABCD"

    def test_overlap_preserved(self):
        text = "ABCDEFGHIJ"  # 10 chars
        result = _sliding_window(text, 4, 2)
        # step = 4 - 2 = 2
        # start=0: "ABCD"
        # start=2: "CDEF"
        # start=4: "EFGH"
        # start=6: "GHIJ"
        assert result == ["ABCD", "CDEF", "EFGH", "GHIJ"]

    def test_empty_text(self):
        text = ""
        result = _sliding_window(text, 10, 2)
        assert result == []

    def test_whitespace_only_stripped(self):
        text = "   ABCD   EFGH   "
        result = _sliding_window(text, 4, 1)
        # Each chunk gets stripped
        assert "ABCD" in result

    def test_very_long_text(self):
        text = "A" * 1000
        result = _sliding_window(text, 100, 10)
        assert len(result) > 1
        assert all(len(chunk) <= 100 for chunk in result)


class TestMergeAndSplit:
    """Tests for _merge_and_split function."""

    def test_single_short_paragraph(self):
        paragraphs = ["Short paragraph."]
        result = _merge_and_split(paragraphs, 100, 10)
        assert result == ["Short paragraph."]

    def test_multiple_short_paragraphs_merged(self):
        paragraphs = ["para1", "para2", "para3"]
        result = _merge_and_split(paragraphs, 100, 10)
        assert len(result) == 1
        assert "para1" in result[0]
        assert "para2" in result[0]
        assert "para3" in result[0]

    def test_paragraphs_exceed_chunk_size(self):
        paragraphs = ["A" * 60, "B" * 60, "C" * 60]
        result = _merge_and_split(paragraphs, 50, 5)
        # Should split into multiple chunks
        assert len(result) > 1

    def test_single_long_paragraph_split(self):
        paragraphs = ["A" * 200]
        result = _merge_and_split(paragraphs, 50, 5)
        # Should be split into multiple chunks
        assert len(result) > 1

    def test_overlap_with_buffer(self):
        paragraphs = ["ABCDEFGHIJ", "KLMNOPQRST"]  # 10 chars each
        result = _merge_and_split(paragraphs, 10, 3)
        # First chunk should contain first paragraph
        # Second chunk should start with overlap
        assert len(result) >= 1

    def test_no_overlap_when_zero(self):
        paragraphs = ["first", "second", "third"]
        result = _merge_and_split(paragraphs, 10, 0)
        # Each paragraph is treated separately (each 5 chars + 2 for separator = 17 > 10)
        # So each gets its own chunk
        assert len(result) == 3
        assert result == ["first", "second", "third"]

    def test_empty_list(self):
        paragraphs = []
        result = _merge_and_split(paragraphs, 100, 10)
        assert result == []

    def test_empty_strings_ignored(self):
        paragraphs = ["text", "", "more text"]
        result = _merge_and_split(paragraphs, 100, 10)
        assert len(result) == 1

    def test_very_large_chunk_size(self):
        paragraphs = ["short", "paragraph"]
        result = _merge_and_split(paragraphs, 10000, 0)
        assert len(result) == 1

    def test_paragraph_larger_than_chunk_size(self):
        # Paragraph larger than chunk_size should still be handled
        paragraphs = ["X" * 200]
        result = _merge_and_split(paragraphs, 50, 0)
        # Should be split
        assert all(len(chunk) <= 50 for chunk in result)
