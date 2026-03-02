"""Aura TUI application."""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Input as TextInput, Label

from aura.ai_service import AIService
from aura.config import AppConfig
from aura.pdf_engine import PDFEngine
from aura.widgets.ai_sidebar import AISidebar
from aura.widgets.file_dialog import FileDialog
from aura.widgets.pdf_viewer import PDFViewer
from aura.widgets.search_dialog import SearchDialog
from aura.widgets.toc_panel import TOCPanel


class _GoToPageScreen(ModalScreen[int | None]):
    """Simple modal to enter a page number."""

    DEFAULT_CSS = """
    _GoToPageScreen {
        align: center middle;
    }

    _GoToPageScreen #goto-container {
        width: 40;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    """

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, total_pages: int) -> None:
        super().__init__()
        self._total = total_pages

    def compose(self) -> ComposeResult:
        with Vertical(id="goto-container"):
            yield Label(f"Go to page (1-{self._total}):")
            yield TextInput(placeholder="Page number", id="goto-input")

    def on_mount(self) -> None:
        self.query_one("#goto-input", TextInput).focus()

    def on_input_submitted(self, event: TextInput.Submitted) -> None:
        try:
            page = int(event.value)
            if 1 <= page <= self._total:
                self.dismiss(page - 1)
            else:
                self.notify(f"Page must be 1-{self._total}", severity="error")
        except ValueError:
            self.notify("Enter a valid number", severity="error")

    def action_cancel(self) -> None:
        self.dismiss(None)


class AuraApp(App):
    """A modern TUI PDF reader with AI assistant."""

    TITLE = "Aura PDF Reader"
    CSS_PATH = "styles/app.tcss"

    DEFAULT_CSS = """
    Screen { layout: horizontal; scrollbar-size: 1 1; }
    * { scrollbar-size: 1 1; }
    Header { dock: top; }
    Footer { dock: bottom; }
    PDFViewer { width: 1fr; }
    Markdown { padding: 1 2; }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("o", "open_file", "Open"),
        ("t", "toggle_toc", "TOC"),
        ("a", "toggle_ai", "AI"),
        ("s", "toggle_scope", "Scope"),
        ("v", "toggle_view", "View"),
        ("c", "toggle_scroll", "Scroll"),
        ("slash", "search", "Search"),
        ("g", "go_to_page", "Go to"),
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

        self._ai_service.clear_all()
        self.sub_title = f"{engine.filename}  p.1/{engine.page_count}"

    def _get_page_context(self) -> str:
        return self.query_one(PDFViewer).get_current_text()

    # -- Event handlers --

    def on_pdfviewer_page_changed(self, event: PDFViewer.PageChanged) -> None:
        viewer = self.query_one(PDFViewer)
        if viewer.engine:
            self.sub_title = (
                f"{viewer.engine.filename}  "
                f"p.{event.page + 1}/{event.total}"
            )

    def on_tocpanel_entry_selected(self, event: TOCPanel.EntrySelected) -> None:
        self.query_one(PDFViewer).go_to_page(event.page)

    def on_aisidebar_book_context_requested(
        self, event: AISidebar.BookContextRequested
    ) -> None:
        viewer = self.query_one(PDFViewer)
        if viewer.engine and not self._ai_service.has_book_context:
            self.notify("Loading book context...", severity="information")
            self.run_worker(self._load_book_context(), exclusive=False)

    async def _load_book_context(self) -> None:
        viewer = self.query_one(PDFViewer)
        if viewer.engine:
            text = viewer.engine.get_full_text(max_pages=100)
            self._ai_service.set_book_context(text)
            self.notify("Book context ready.", severity="information")

    def on_aisidebar_chat_message_sent(
        self, event: AISidebar.ChatMessageSent
    ) -> None:
        sidebar = self.query_one(AISidebar)
        sidebar.append_user_message(event.text)
        page_context = self._get_page_context()
        self._run_ai_stream(
            self._ai_service.stream_response(event.text, page_context, event.scope)
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

    def action_search(self) -> None:
        viewer = self.query_one(PDFViewer)
        if not viewer.engine:
            self.notify("No PDF loaded.", severity="warning")
            return
        dialog = SearchDialog()
        self.push_screen(dialog, callback=self._on_search_result)

    def _on_search_result(self, page: int | None) -> None:
        if page is not None:
            self.query_one(PDFViewer).go_to_page(page)

    def on_search_dialog_search_requested(
        self, event: SearchDialog.SearchRequested
    ) -> None:
        viewer = self.query_one(PDFViewer)
        if viewer.engine:
            results = viewer.engine.search_text(event.query)
            for screen in self.screen_stack:
                if isinstance(screen, SearchDialog):
                    screen.show_results(results)
                    break

    def action_go_to_page(self) -> None:
        viewer = self.query_one(PDFViewer)
        if not viewer.engine:
            return
        self.push_screen(
            _GoToPageScreen(viewer.engine.page_count),
            callback=self._on_goto_page,
        )

    def _on_goto_page(self, page: int | None) -> None:
        if page is not None:
            self.query_one(PDFViewer).go_to_page(page)

    def action_open_file(self) -> None:
        self.push_screen(FileDialog(), callback=self._on_file_selected)

    def _on_file_selected(self, path: Path | None) -> None:
        if path:
            self._open_pdf(path)

    def action_toggle_toc(self) -> None:
        self.query_one(TOCPanel).toggle()

    def action_toggle_ai(self) -> None:
        self.query_one(AISidebar).toggle()

    def action_toggle_scope(self) -> None:
        self.query_one(AISidebar).toggle_scope()

    def action_toggle_view(self) -> None:
        self.query_one(PDFViewer).toggle_view_mode()

    def action_toggle_scroll(self) -> None:
        self.query_one(PDFViewer).toggle_scroll_mode()

    def action_next_page(self) -> None:
        self.query_one(PDFViewer).next_page()

    def action_prev_page(self) -> None:
        self.query_one(PDFViewer).prev_page()
