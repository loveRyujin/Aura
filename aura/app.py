"""Aura TUI application."""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header

from aura.config import AppConfig
from aura.pdf_engine import PDFEngine
from aura.widgets.pdf_viewer import PDFViewer


class AuraApp(App):
    """A modern TUI PDF reader with AI assistant."""

    TITLE = "Aura PDF Reader"
    CSS_PATH = "styles/app.tcss"

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("right,l", "next_page", "Next"),
        ("left,h", "prev_page", "Prev"),
    ]

    def __init__(self, file_path: Path | None = None, config: AppConfig | None = None):
        super().__init__()
        self.file_path = file_path
        self.config = config or AppConfig.load()

    def compose(self) -> ComposeResult:
        yield Header()
        yield PDFViewer()
        yield Footer()

    def on_mount(self) -> None:
        if self.file_path and self.file_path.exists():
            self._open_pdf(self.file_path)

    def _open_pdf(self, path: Path) -> None:
        engine = PDFEngine(path)
        viewer = self.query_one(PDFViewer)
        viewer.load_pdf(engine)
        self.sub_title = f"{engine.filename}  p.1/{engine.page_count}"

    def on_pdf_viewer_page_changed(self, event: PDFViewer.PageChanged) -> None:
        if viewer := self.query_one(PDFViewer):
            if viewer.engine:
                self.sub_title = (
                    f"{viewer.engine.filename}  "
                    f"p.{event.page + 1}/{event.total}"
                )

    def action_next_page(self) -> None:
        self.query_one(PDFViewer).next_page()

    def action_prev_page(self) -> None:
        self.query_one(PDFViewer).prev_page()
