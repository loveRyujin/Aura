#!/usr/bin/env python3
"""Test if WezTerm can render Sixel at all (bypasses Textual entirely).

Run in WezTerm:
    .venv/bin/python scripts/test_raw_sixel.py [path/to/pdf]
"""

import sys
from pathlib import Path

from PIL import Image as PILImage


def main() -> None:
    if len(sys.argv) > 1:
        pdf_path = Path(sys.argv[1])
        import pymupdf
        doc = pymupdf.open(str(pdf_path))
        page = doc[0]
        zoom = 800 / page.rect.width
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
        img = PILImage.frombytes("RGB", (pix.width, pix.height), bytes(pix.samples))
        doc.close()
    else:
        img = PILImage.new("RGB", (400, 300), (50, 50, 200))
        for y in range(300):
            for x in range(400):
                img.putpixel((x, y), (x % 256, y % 256, (x + y) % 256))

    print(f"Image: {img.width}x{img.height}px")
    print()

    # Test 1: Rich + textual-image Sixel renderable (no Textual)
    print("=== Test 1: Rich console + Sixel renderable ===")
    try:
        from rich.console import Console
        from textual_image.renderable.sixel import Image as SixelRenderable
        console = Console()
        console.print(SixelRenderable(img, width="100%"))
        print("(If you see a colorful image above, Sixel works!)")
    except Exception as e:
        print(f"Sixel renderable failed: {e}")

    print()

    # Test 2: Raw libsixel/pillow-based Sixel output
    print("=== Test 2: Raw Sixel via textual-image encoder ===")
    try:
        from textual_image._sixel import image_to_sixels
        sixel_data = image_to_sixels(img.resize((200, 150)))
        sys.stdout.write(sixel_data)
        sys.stdout.write("\n")
        print("(If you see a colorful image above, raw Sixel works!)")
    except Exception as e:
        print(f"Raw Sixel failed: {e}")

    print()

    # Test 3: Halfcell via Rich (should always work)
    print("=== Test 3: Halfcell renderable (baseline) ===")
    try:
        from rich.console import Console
        from textual_image.renderable.halfcell import Image as HalfcellRenderable
        console = Console()
        console.print(HalfcellRenderable(img, width="80%"))
        print("(This is what Aura currently uses)")
    except Exception as e:
        print(f"Halfcell failed: {e}")


if __name__ == "__main__":
    main()
