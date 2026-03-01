"""Convert PyMuPDF Pixmap to terminal art using half-block characters.

Each terminal cell encodes two vertical pixels:
  - foreground color = top pixel
  - background color = bottom pixel
  - character = '▀' (upper half block)

This doubles the effective vertical resolution.
"""

from __future__ import annotations

import pymupdf
from rich.text import Text


def pixmap_to_rich_text(pix: pymupdf.Pixmap) -> Text:
    """Convert a PyMuPDF Pixmap (RGB, no alpha) to a Rich Text block."""
    width = pix.width
    height = pix.height
    samples = pix.samples
    stride = pix.stride

    lines: list[str] = []
    styles: list[list[tuple[str, int, int]]] = []

    for y in range(0, height - 1, 2):
        line_chars: list[str] = []
        line_styles: list[tuple[str, int, int]] = []
        pos = 0

        for x in range(width):
            off_top = y * stride + x * 3
            r1, g1, b1 = samples[off_top], samples[off_top + 1], samples[off_top + 2]

            off_bot = (y + 1) * stride + x * 3
            r2, g2, b2 = samples[off_bot], samples[off_bot + 1], samples[off_bot + 2]

            style = f"rgb({r1},{g1},{b1}) on rgb({r2},{g2},{b2})"
            line_chars.append("▀")
            line_styles.append((style, pos, pos + 1))
            pos += 1

        lines.append("".join(line_chars))
        styles.append(line_styles)

    # Handle odd last row
    if height % 2 == 1:
        y = height - 1
        line_chars = []
        line_styles = []
        pos = 0
        for x in range(width):
            off = y * stride + x * 3
            r, g, b = samples[off], samples[off + 1], samples[off + 2]
            style = f"rgb({r},{g},{b})"
            line_chars.append("▀")
            line_styles.append((style, pos, pos + 1))
            pos += 1
        lines.append("".join(line_chars))
        styles.append(line_styles)

    result = Text()
    for i, (line, spans) in enumerate(zip(lines, styles)):
        t = Text(line)
        for style, start, end in spans:
            t.stylize(style, start, end)
        result.append(t)
        if i < len(lines) - 1:
            result.append("\n")

    return result
