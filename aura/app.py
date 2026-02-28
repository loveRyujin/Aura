"""Aura TUI application."""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header

from aura.config import AppConfig


class AuraApp(App):
    """A modern TUI PDF reader with AI assistant."""

    TITLE = "Aura PDF Reader"
    CSS_PATH = "styles/app.tcss"

    BINDINGS = [
        ("q", "quit", "Quit"),
    ]

    def __init__(self, file_path: Path | None = None, config: AppConfig | None = None):
        super().__init__()
        self.file_path = file_path
        self.config = config or AppConfig.load()

    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()
