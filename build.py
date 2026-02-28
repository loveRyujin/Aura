"""Build script to package Aura as a standalone executable via PyInstaller."""

import PyInstaller.__main__
import sys
from pathlib import Path

ROOT = Path(__file__).parent


def build() -> None:
    args = [
        str(ROOT / "aura" / "__main__.py"),
        "--name=aura",
        "--onefile",
        "--console",
        f"--add-data={ROOT / 'aura' / 'styles' / 'app.tcss'}:aura/styles",
        "--hidden-import=aura",
        "--hidden-import=aura.app",
        "--hidden-import=aura.config",
        "--hidden-import=aura.pdf_engine",
        "--hidden-import=aura.ai_service",
        "--hidden-import=aura.widgets",
        "--hidden-import=aura.widgets.pdf_viewer",
        "--hidden-import=aura.widgets.ai_sidebar",
        "--hidden-import=aura.widgets.toc_panel",
        "--hidden-import=aura.widgets.file_dialog",
        "--hidden-import=aura.widgets.search_dialog",
        "--hidden-import=litellm",
        "--hidden-import=pymupdf",
        "--hidden-import=pymupdf4llm",
        "--hidden-import=textual",
        f"--distpath={ROOT / 'dist'}",
        f"--workpath={ROOT / 'build'}",
        f"--specpath={ROOT}",
        "--clean",
    ]
    if "--debug" in sys.argv:
        args.append("--debug=all")

    PyInstaller.__main__.run(args)


if __name__ == "__main__":
    build()
