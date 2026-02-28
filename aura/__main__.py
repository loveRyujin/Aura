"""Entry point for Aura: python -m aura [file.pdf]"""

from __future__ import annotations

import argparse
from pathlib import Path

from aura.app import AuraApp
from aura.config import AppConfig


def main() -> None:
    parser = argparse.ArgumentParser(description="Aura - TUI PDF Reader with AI")
    parser.add_argument("file", nargs="?", help="PDF file to open")
    parser.add_argument("--config", "-c", help="Path to config file (aura.toml)")
    args = parser.parse_args()

    file_path = Path(args.file) if args.file else None
    config_path = Path(args.config) if args.config else None
    config = AppConfig.load(config_path)

    app = AuraApp(file_path=file_path, config=config)
    app.run()


if __name__ == "__main__":
    main()
