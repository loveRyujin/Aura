"""Aura TUI application."""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header

from aura.config import AppConfig
from aura.pdf_engine import PDFEngine
from aura.widgets.file_dialog import FileDialog
from aura.widgets.pdf_viewer import PDFViewer
from aura.widgets.toc_panel import TOCPanel


class AuraApp(App):
    """A modern TUI PDF reader with AI assistant."""

    TITLE = "Aura PDF Reader"
    CSS_PATH = "styles/app.tcss"

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("o", "open_file", "Open"),
        ("t", "toggle_toc", "TOC"),
        ("right,l", "next_page", "Next"),
        ("left,h", "prev_page", "Prev"),
    ]

    def __init__(self, file_path: Path | None = None, config: AppConfig | None = None):
        super().__init__()
        self.file_path = file_path
        self.config = config or AppConfig.load()

    def compose(self) -> ComposeResult:
        yield Header()
        yield TOCPanel()
        yield PDFViewer()
        yield Footer()

    def on_mount(self) -> None:
        toc = self.query_one(TOCPanel)
        toc.add_class("hidden")

        if self.file_path and self.file_path.exists():
            self._open_pdf(self.file_path)

    def _open_pdf(self, path: Path) -> None:
        engine = PDFEngine(path)
        viewer = self.query_one(PDFViewer)
        viewer.load_pdf(engine)

        toc_panel = self.query_one(TOCPanel)
        toc_entries = engine.get_toc()
        toc_panel.load_toc(toc_entries)

        self.sub_title = f"{engine.filename}  p.1/{engine.page_count}"

    def on_pdf_viewer_page_changed(self, event: PDFViewer.PageChanged) -> None:
        viewer = self.query_one(PDFViewer)
        if viewer.engine:
            self.sub_title = (
                f"{viewer.engine.filename}  "
                f"p.{event.page + 1}/{event.total}"
            )

    def on_toc_panel_entry_selected(self, event: TOCPanel.EntrySelected) -> None:
        self.query_one(PDFViewer).go_to_page(event.page)

    def action_open_file(self) -> None:
        self.push_screen(FileDialog(), callback=self._on_file_selected)

    def _on_file_selected(self, path: Path | None) -> None:
        if path:
            self._open_pdf(path)

    def action_toggle_toc(self) -> None:
        self.query_one(TOCPanel).toggle()

    def action_next_page(self) -> None:
        self.query_one(PDFViewer).next_page()

    def action_prev_page(self) -> None:
        self.query_one(PDFViewer).prev_page()
