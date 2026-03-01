"""PDF content viewer widget with text and image rendering modes."""

from __future__ import annotations

from enum import Enum

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, Markdown, Static

from aura.image_render import pixmap_to_rich_text
from aura.pdf_engine import PDFEngine


class ViewMode(Enum):
    TEXT = "text"
    IMAGE = "image"


class PageIndicator(Static):
    """Displays current page number, total pages, and view mode."""

    page = reactive(0)
    total = reactive(0)
    mode = reactive(ViewMode.TEXT)

    def render(self) -> str:
        if self.total == 0:
            return "No file loaded"
        mode_label = "TXT" if self.mode == ViewMode.TEXT else "IMG"
        return f" Page {self.page + 1}/{self.total}  [{mode_label}]  [v] toggle view "


class ImageView(Static):
    """Displays a rasterized PDF page as terminal art."""

    DEFAULT_CSS = """
    ImageView {
        width: auto;
        height: auto;
    }
    """

    def set_content(self, rich_text: Text) -> None:
        self.update(rich_text)


class PDFViewer(Widget):
    """Main PDF content display with text/image mode toggle."""

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
        def __init__(self, page: int, total: int) -> None:
            super().__init__()
            self.page = page
            self.total = total

    current_page: reactive[int] = reactive(0)
    view_mode: reactive[ViewMode] = reactive(ViewMode.TEXT)

    def __init__(self) -> None:
        super().__init__()
        self._engine: PDFEngine | None = None

    def compose(self) -> ComposeResult:
        yield Label("Press [b]o[/b] to open a PDF file", id="welcome-label")
        with VerticalScroll(id="pdf-scroll"):
            yield Markdown("", id="pdf-content")
            yield ImageView(id="pdf-image")
        yield PageIndicator(id="page-bar")

    def on_mount(self) -> None:
        self.query_one("#pdf-scroll").display = False
        self.query_one("#page-bar").display = False
        self.query_one("#pdf-image").display = False

    @property
    def engine(self) -> PDFEngine | None:
        return self._engine

    def load_pdf(self, engine: PDFEngine) -> None:
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

    def watch_view_mode(self, value: ViewMode) -> None:
        self.query_one(PageIndicator).mode = value
        self._render_page()

    def toggle_view_mode(self) -> None:
        if self.view_mode == ViewMode.TEXT:
            self.view_mode = ViewMode.IMAGE
        else:
            self.view_mode = ViewMode.TEXT

    def _render_page(self) -> None:
        if not self._engine:
            return

        md_widget = self.query_one("#pdf-content", Markdown)
        img_widget = self.query_one("#pdf-image", ImageView)

        if self.view_mode == ViewMode.TEXT:
            md_widget.display = True
            img_widget.display = False
            md_text = self._engine.get_page_markdown(self.current_page)
            md_widget.update(md_text)
        else:
            md_widget.display = False
            img_widget.display = True
            scroll_area = self.query_one("#pdf-scroll")
            render_width = max(40, scroll_area.size.width - 2)
            pix = self._engine.render_page_pixmap(self.current_page, render_width * 2)
            rich_text = pixmap_to_rich_text(pix)
            img_widget.set_content(rich_text)

        self.query_one("#pdf-scroll").scroll_home(animate=False)

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
        if not self._engine:
            return ""
        return self._engine.get_page_markdown(self.current_page)
