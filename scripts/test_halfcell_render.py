#!/usr/bin/env python3
"""Minimal test: render a PDF page using textual-image HalfcellWidget (current fallback).

Run in WezTerm:
    .venv/bin/python scripts/test_halfcell_render.py [path/to/pdf]
"""

import sys
from pathlib import Path

from PIL import Image as PILImage
from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, Static
from textual_image.widget import HalfcellImage


class TestApp(App):
    CSS = """
    Screen { layout: vertical; }
    #status { dock: bottom; height: 1; }
    #image { width: 1fr; height: 1fr; }
    """
    BINDINGS = [("q", "quit", "Quit")]

    def __init__(self, img: PILImage.Image):
        super().__init__()
        self._img = img

    def compose(self) -> ComposeResult:
        yield Header()
        yield HalfcellImage(self._img, id="image")
        yield Static("Halfcell test — press q to quit", id="status")
        yield Footer()


def main() -> None:
    if len(sys.argv) > 1:
        pdf_path = Path(sys.argv[1])
        if not pdf_path.exists():
            print(f"File not found: {pdf_path}")
            return

        import pymupdf

        doc = pymupdf.open(str(pdf_path))
        page = doc[0]
        zoom = 1600 / page.rect.width
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
        img = PILImage.frombytes("RGB", (pix.width, pix.height), bytes(pix.samples))
        doc.close()
        print(f"Rendered page 1: {img.width}x{img.height}px")
    else:
        img = PILImage.new("RGB", (800, 600))
        for y in range(600):
            for x in range(800):
                img.putpixel((x, y), (x % 256, y % 256, (x + y) % 256))
        print("Using synthetic test image 800x600")

    app = TestApp(img)
    app.run()


if __name__ == "__main__":
    main()
