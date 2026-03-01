"""PDF content viewer widget using Markdown rendering."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, Markdown, Static

from aura.pdf_engine import PDFEngine


class PageIndicator(Static):
    """Displays current page number and total pages."""

    page = reactive(0)
    total = reactive(0)

    def render(self) -> str:
        if self.total == 0:
            return "No file loaded"
        return f" Page {self.page + 1} / {self.total} "


class PDFViewer(Widget):
    """Main PDF content display area with page navigation."""

    DEFAULT_CSS = """
    PDFViewer {
        width: 1fr;
        height: 1fr;
    }

    PDFViewer #pdf-scroll {
        height: 1fr;
    }

    PDFViewer #page-bar {
        dock: bottom;
        height: 1;
        background: $primary-background;
        color: $text;
        text-align: center;
    }

    PDFViewer #welcome-label {
        width: 100%;
        height: 100%;
        content-align: center middle;
        color: $text-muted;
    }
    """

    class PageChanged(Message):
        """Emitted when the current page changes."""

        def __init__(self, page: int, total: int) -> None:
            super().__init__()
            self.page = page
            self.total = total

    current_page: reactive[int] = reactive(0)

    def __init__(self) -> None:
        super().__init__()
        self._engine: PDFEngine | None = None

    def compose(self) -> ComposeResult:
        yield Label("Press [b]o[/b] to open a PDF file", id="welcome-label")
        with VerticalScroll(id="pdf-scroll"):
            yield Markdown("", id="pdf-content")
        yield PageIndicator(id="page-bar")

    def on_mount(self) -> None:
        self.query_one("#pdf-scroll").display = False
        self.query_one("#page-bar").display = False

    @property
    def engine(self) -> PDFEngine | None:
        return self._engine

    def load_pdf(self, engine: PDFEngine) -> None:
        """Load a PDF document into the viewer."""
        if self._engine:
            self._engine.close()
        self._engine = engine
        self.query_one("#welcome-label").display = False
        self.query_one("#pdf-scroll").display = True
        self.query_one("#page-bar").display = True
        indicator = self.query_one(PageIndicator)
        indicator.total = engine.page_count
        indicator.page = 0
        self.current_page = 0
        self._render_page()

    def watch_current_page(self, value: int) -> None:
        indicator = self.query_one(PageIndicator)
        indicator.page = value
        if self._engine:
            indicator.total = self._engine.page_count
            self.post_message(self.PageChanged(value, self._engine.page_count))

    def _render_page(self) -> None:
        if not self._engine:
            return
        md_text = self._engine.get_page_markdown(self.current_page)
        self.query_one("#pdf-content", Markdown).update(md_text)
        scroll = self.query_one("#pdf-scroll")
        scroll.scroll_home(animate=False)

    def next_page(self) -> None:
        if self._engine and self.current_page < self._engine.page_count - 1:
            self.current_page += 1
            self._render_page()

    def prev_page(self) -> None:
        if self._engine and self.current_page > 0:
            self.current_page -= 1
            self._render_page()

    def go_to_page(self, page: int) -> None:
        if self._engine and 0 <= page < self._engine.page_count:
            self.current_page = page
            self._render_page()

    def get_current_text(self) -> str:
        """Return current page markdown for AI context."""
        if not self._engine:
            return ""
        return self._engine.get_page_markdown(self.current_page)
