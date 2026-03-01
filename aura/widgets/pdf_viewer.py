"""PDF content viewer widget with text and image rendering modes."""

from __future__ import annotations

from enum import Enum

import textual_image.renderable  # noqa: F401 — detect terminal caps before App starts

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, Markdown, Static

from textual_image.widget import Image as TIImage

from aura.pdf_engine import PDFEngine


class ViewMode(Enum):
    TEXT = "text"
    IMAGE = "image"


class PageIndicator(Static):
    page = reactive(0)
    total = reactive(0)
    mode = reactive(ViewMode.TEXT)

    def render(self) -> str:
        if self.total == 0:
            return "No file loaded"
        mode_label = "TXT" if self.mode == ViewMode.TEXT else "IMG"
        return f" Page {self.page + 1}/{self.total}  [{mode_label}]  [v] toggle view "


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
    PDFViewer #pdf-image {
        width: 1fr;
        height: auto;
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
            yield TIImage(id="pdf-image")
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
        img_widget = self.query_one("#pdf-image", TIImage)

        if self.view_mode == ViewMode.TEXT:
            md_widget.display = True
            img_widget.display = False
            md_text = self._engine.get_page_markdown(self.current_page)
            md_widget.update(md_text)
        else:
            md_widget.display = False
            img_widget.display = True
            self.app.run_worker(self._render_image_async(), exclusive=True)

        self.query_one("#pdf-scroll").scroll_home(animate=False)

    async def _render_image_async(self) -> None:
        """Render PDF page via textual-image (auto-selects TGP/Sixel/Unicode)."""
        if not self._engine:
            return

        import asyncio

        from PIL import Image as PILImage

        scroll_area = self.query_one("#pdf-scroll")
        render_width = max(800, scroll_area.size.width * 12)
        page = self.current_page
        engine = self._engine

        def _cpu_work() -> PILImage.Image:
            pix = engine.render_page_pixmap(page, render_width)
            return PILImage.frombytes("RGB", (pix.width, pix.height), bytes(pix.samples))

        pil_img = await asyncio.to_thread(_cpu_work)

        img_widget = self.query_one("#pdf-image", TIImage)
        img_widget.image = pil_img
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
