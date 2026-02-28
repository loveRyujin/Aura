"""Aura TUI application."""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header

from aura.ai_service import AIService
from aura.config import AppConfig
from aura.pdf_engine import PDFEngine
from aura.widgets.ai_sidebar import AISidebar
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
        ("a", "toggle_ai", "AI"),
        ("right,l", "next_page", "Next"),
        ("left,h", "prev_page", "Prev"),
    ]

    def __init__(self, file_path: Path | None = None, config: AppConfig | None = None):
        super().__init__()
        self.file_path = file_path
        self.config = config or AppConfig.load()
        self._ai_service = AIService(self.config.ai)

    def compose(self) -> ComposeResult:
        yield Header()
        yield TOCPanel()
        yield PDFViewer()
        yield AISidebar()
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(TOCPanel).add_class("hidden")
        self.query_one(AISidebar).add_class("hidden")

        if self.file_path and self.file_path.exists():
            self._open_pdf(self.file_path)

    def _open_pdf(self, path: Path) -> None:
        engine = PDFEngine(path)
        viewer = self.query_one(PDFViewer)
        viewer.load_pdf(engine)

        toc_panel = self.query_one(TOCPanel)
        toc_entries = engine.get_toc()
        toc_panel.load_toc(toc_entries)

        self._ai_service.clear_history()
        self.sub_title = f"{engine.filename}  p.1/{engine.page_count}"

    def _get_page_context(self) -> str:
        return self.query_one(PDFViewer).get_current_text()

    # -- Event handlers --

    def on_pdf_viewer_page_changed(self, event: PDFViewer.PageChanged) -> None:
        viewer = self.query_one(PDFViewer)
        if viewer.engine:
            self.sub_title = (
                f"{viewer.engine.filename}  "
                f"p.{event.page + 1}/{event.total}"
            )

    def on_toc_panel_entry_selected(self, event: TOCPanel.EntrySelected) -> None:
        self.query_one(PDFViewer).go_to_page(event.page)

    def on_ai_sidebar_quick_command_requested(
        self, event: AISidebar.QuickCommandRequested
    ) -> None:
        page_content = self._get_page_context()
        if not page_content:
            self.query_one(AISidebar).show_error("No PDF page loaded.")
            return
        sidebar = self.query_one(AISidebar)
        sidebar.append_user_message(f"[{event.command.value}]")
        self._run_ai_stream(
            self._ai_service.quick_command(event.command, page_content)
        )

    def on_ai_sidebar_chat_message_sent(
        self, event: AISidebar.ChatMessageSent
    ) -> None:
        sidebar = self.query_one(AISidebar)
        sidebar.append_user_message(event.text)
        page_context = self._get_page_context()
        self._run_ai_stream(
            self._ai_service.stream_response(event.text, page_context)
        )

    def _run_ai_stream(self, stream) -> None:
        """Launch async task to consume an AI token stream."""
        self.run_worker(self._consume_stream(stream), exclusive=True)

    async def _consume_stream(self, stream) -> None:
        sidebar = self.query_one(AISidebar)
        sidebar.begin_ai_response()
        try:
            async for token in stream:
                sidebar.append_ai_token(token)
        except Exception as exc:
            sidebar.show_error(str(exc))
        else:
            sidebar.end_ai_response()

    # -- Actions --

    def action_open_file(self) -> None:
        self.push_screen(FileDialog(), callback=self._on_file_selected)

    def _on_file_selected(self, path: Path | None) -> None:
        if path:
            self._open_pdf(path)

    def action_toggle_toc(self) -> None:
        self.query_one(TOCPanel).toggle()

    def action_toggle_ai(self) -> None:
        self.query_one(AISidebar).toggle()

    def action_next_page(self) -> None:
        self.query_one(PDFViewer).next_page()

    def action_prev_page(self) -> None:
        self.query_one(PDFViewer).prev_page()
