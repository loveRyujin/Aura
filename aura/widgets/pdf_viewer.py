"""PDF content viewer widget with text and image rendering modes.

Supports AURA_RENDERER env var to force a specific graphics protocol:
    sixel   - Sixel (WezTerm, Windows Terminal 1.22+, iTerm2, xterm)
    tgp     - Kitty Terminal Graphics Protocol (Kitty)
    halfcell - Colored half-cell characters (any terminal)
    unicode - Unicode block characters (any terminal)
    auto    - Auto-detect best available (default)
"""

from __future__ import annotations

import os
from enum import Enum
from typing import TYPE_CHECKING

import textual_image.renderable  # noqa: F401 — detect terminal caps before App starts

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, Markdown, Static

from aura.pdf_engine import PDFEngine

if TYPE_CHECKING:
    from textual_image.widget._base import Image as _BaseImageWidget

_RENDERER_OVERRIDE = os.environ.get("AURA_RENDERER", "auto").lower()


def _select_image_widget() -> type[_BaseImageWidget]:
    """Select the textual-image widget class.

    Explicit AURA_RENDERER override takes priority; otherwise textual-image's
    own escape-sequence detection decides (halfcell on most WSL2 setups).
    """
    if _RENDERER_OVERRIDE == "sixel":
        from textual_image.widget.sixel import Image as SixelWidget
        return SixelWidget
    elif _RENDERER_OVERRIDE == "tgp":
        from textual_image.widget import TGPImage
        return TGPImage
    elif _RENDERER_OVERRIDE == "halfcell":
        from textual_image.widget import HalfcellImage
        return HalfcellImage
    elif _RENDERER_OVERRIDE == "unicode":
        from textual_image.widget import UnicodeImage
        return UnicodeImage
    else:
        from textual_image.widget import Image as AutoWidget
        return AutoWidget


TIImage = _select_image_widget()


def _renderer_label() -> str:
    name = TIImage.__module__
    if "sixel" in name:
        return "SIXEL"
    if "tgp" in name.lower() or TIImage.__name__ == "TGPImage":
        return "TGP"
    return "IMG"


class ViewMode(Enum):
    TEXT = "text"
    IMAGE = "image"


class ScrollMode(Enum):
    PAGINATED = "paginated"
    CONTINUOUS = "continuous"


class PageIndicator(Static):
    page = reactive(0)
    total = reactive(0)
    mode = reactive(ViewMode.TEXT)
    scroll_mode = reactive(ScrollMode.PAGINATED)

    def render(self) -> str:
        if self.total == 0:
            return "No file loaded"
        if self.mode == ViewMode.TEXT:
            mode_label = "TXT"
        else:
            mode_label = _renderer_label()
        scroll_label = "SCROLL" if self.scroll_mode == ScrollMode.CONTINUOUS else "PAGE"
        return (
            f" Page {self.page + 1}/{self.total}"
            f"  [{mode_label}]  [{scroll_label}]"
            f"  [v]view [c]scroll "
        )


class PDFViewer(Widget):
    """Main PDF content display with text/image mode toggle.

    Supports two scroll modes (toggled with ``c``):
    - PAGINATED: classic single-page view (left/right to flip).
    - CONTINUOUS: pages load dynamically as the user scrolls down.

    IMAGE view is always paginated.
    """

    _LOAD_AHEAD = 5

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
    PDFViewer .page-sep {
        text-align: center;
        color: $text-muted;
        margin: 1 0 0 0;
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
    scroll_mode: reactive[ScrollMode] = reactive(ScrollMode.PAGINATED)

    def __init__(self) -> None:
        super().__init__()
        self._engine: PDFEngine | None = None
        self._loaded_pages: set[int] = set()
        self._render_seq: int = 0
        self._text_render_seq: int = 0

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
        self.query_one("#pdf-content").display = False
        self.set_interval(0.2, self._check_scroll)

    @property
    def engine(self) -> PDFEngine | None:
        return self._engine

    # ── Lifecycle ────────────────────────────────────────────────

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
        self._rebuild()

    # ── Reactive watchers ────────────────────────────────────────

    def watch_current_page(self, value: int) -> None:
        indicator = self.query_one(PageIndicator)
        indicator.page = value
        if self._engine:
            indicator.total = self._engine.page_count
            self.post_message(self.PageChanged(value, self._engine.page_count))

    def watch_view_mode(self, _value: ViewMode) -> None:
        self.query_one(PageIndicator).mode = _value
        self._rebuild()

    def watch_scroll_mode(self, _value: ScrollMode) -> None:
        self.query_one(PageIndicator).scroll_mode = _value
        self._rebuild()

    # ── Mode toggles ─────────────────────────────────────────────

    def toggle_view_mode(self) -> None:
        if self.view_mode == ViewMode.TEXT:
            self.view_mode = ViewMode.IMAGE
        else:
            self.view_mode = ViewMode.TEXT

    def toggle_scroll_mode(self) -> None:
        if self.scroll_mode == ScrollMode.PAGINATED:
            self.scroll_mode = ScrollMode.CONTINUOUS
        else:
            self.scroll_mode = ScrollMode.PAGINATED

    # ── Rendering ────────────────────────────────────────────────

    def _rebuild(self) -> None:
        """Rebuild content for the current view + scroll mode combination."""
        if not self._engine:
            return

        md_widget = self.query_one("#pdf-content", Markdown)
        img_widget = self.query_one("#pdf-image", TIImage)

        self._clear_dynamic_pages()

        if self.view_mode == ViewMode.IMAGE:
            md_widget.display = False
            img_widget.display = True
            self.app.run_worker(self._render_image_async(), exclusive=True)
        elif self.scroll_mode == ScrollMode.PAGINATED:
            img_widget.display = False
            md_widget.display = True
            md_widget.update("Loading page...")
            self._schedule_text_render(self.current_page)
        else:
            img_widget.display = False
            md_widget.display = False
            end = min(
                self.current_page + self._LOAD_AHEAD + 1, self._engine.page_count
            )
            self._load_dynamic_pages(self.current_page, end)

        self.query_one("#pdf-scroll").scroll_home(animate=False)
        self._prefetch_adjacent()

    # ── Paginated helpers ────────────────────────────────────────

    def _show_single_page(self) -> None:
        """Update the single Markdown widget to show current_page."""
        if not self._engine:
            return
        md_widget = self.query_one("#pdf-content", Markdown)
        md_widget.update("Loading page...")
        self._schedule_text_render(self.current_page)
        self.query_one("#pdf-scroll").scroll_home(animate=False)

    # ── Continuous-mode helpers ──────────────────────────────────

    def _clear_dynamic_pages(self) -> None:
        """Remove all dynamically mounted sep / page widgets."""
        scroll = self.query_one("#pdf-scroll")
        keep = {
            self.query_one("#pdf-content", Markdown),
            self.query_one("#pdf-image", TIImage),
        }
        for child in list(scroll.children):
            if child not in keep:
                child.remove()
        self._loaded_pages.clear()

    def _load_dynamic_pages(self, start: int, end: int) -> None:
        """Mount Markdown widgets for pages [start, end) in one batch."""
        if not self._engine:
            return
        scroll = self.query_one("#pdf-scroll")
        img_widget = self.query_one("#pdf-image", TIImage)

        batch: list[Widget] = []
        for p in range(start, end):
            if p in self._loaded_pages:
                continue
            self._loaded_pages.add(p)
            batch.append(
                Static(
                    f"── Page {p + 1} / {self._engine.page_count} ──",
                    id=f"sep-{p}",
                    classes="page-sep",
                )
            )
            batch.append(
                Markdown(
                    self._engine.get_page_markdown(p),
                    id=f"page-{p}",
                )
            )
        if batch:
            scroll.mount_all(batch, before=img_widget)

    # ── Scroll-driven page loading (CONTINUOUS only) ─────────────

    def _check_scroll(self) -> None:
        """Periodic: load-ahead near bottom + track visible page."""
        try:
            if (
                not self._engine
                or self.view_mode != ViewMode.TEXT
                or self.scroll_mode != ScrollMode.CONTINUOUS
                or not self._loaded_pages
            ):
                return

            scroll = self.query_one("#pdf-scroll")
            if scroll.max_scroll_y > 0 and scroll.scroll_y >= scroll.max_scroll_y * 0.7:
                max_loaded = max(self._loaded_pages)
                if max_loaded < self._engine.page_count - 1:
                    next_end = min(
                        max_loaded + self._LOAD_AHEAD + 1,
                        self._engine.page_count,
                    )
                    self._load_dynamic_pages(max_loaded + 1, next_end)

            self._update_visible_page()
        except Exception:
            pass

    def _update_visible_page(self) -> None:
        """Determine which page is at the top of the viewport."""
        if not self._loaded_pages:
            return
        scroll = self.query_one("#pdf-scroll")
        viewport_top = scroll.region.y

        best = min(self._loaded_pages)
        for p in sorted(self._loaded_pages):
            try:
                sep = self.query_one(f"#sep-{p}")
                if sep.region.y <= viewport_top + 2:
                    best = p
            except Exception:
                pass

        if best != self.current_page:
            self.current_page = best

    # ── Image rendering (single-page) ────────────────────────────

    async def _render_image_async(self) -> None:
        """Render PDF page via textual-image (auto-selects TGP/Sixel/Unicode)."""
        if not self._engine:
            return

        import asyncio

        scroll_area = self.query_one("#pdf-scroll")
        cols = scroll_area.size.width
        render_width = max(800, cols * 10)
        page = self.current_page
        engine = self._engine

        def _cpu_work():
            return engine.render_page_image(page, render_width)

        pil_img = await asyncio.to_thread(_cpu_work)

        img_widget = self.query_one("#pdf-image", TIImage)
        img_widget.image = pil_img
        self.query_one("#pdf-scroll").scroll_home(animate=False)

    async def _render_text_async(self, page: int, seq: int) -> None:
        """Render a text page in the background to avoid UI stalls."""
        if not self._engine:
            return

        import asyncio

        engine = self._engine
        markdown = await asyncio.to_thread(engine.get_page_markdown, page)
        if (
            seq != self._text_render_seq
            or not self._engine
            or self.current_page != page
            or self.view_mode != ViewMode.TEXT
            or self.scroll_mode != ScrollMode.PAGINATED
        ):
            return
        self.query_one("#pdf-content", Markdown).update(markdown)
        self.query_one("#pdf-scroll").scroll_home(animate=False)

    def _schedule_text_render(self, page: int) -> None:
        self._text_render_seq += 1
        seq = self._text_render_seq
        self.app.run_worker(
            self._render_text_async(page, seq),
            exclusive=True,
        )

    # ── Debounced rendering ──────────────────────────────────────

    def _schedule_render(self) -> None:
        """Debounce: coalesce rapid page flips into a single render."""
        self._render_seq += 1
        seq = self._render_seq
        self.set_timer(0.04, lambda: self._do_deferred_render(seq))

    def _do_deferred_render(self, seq: int) -> None:
        if seq != self._render_seq:
            return
        if not self._engine:
            return

        if self.view_mode == ViewMode.IMAGE:
            self.app.run_worker(self._render_image_async(), exclusive=True)
            self.query_one("#pdf-scroll").scroll_home(animate=False)
        elif self.scroll_mode == ScrollMode.PAGINATED:
            self._show_single_page()
        else:
            self._scroll_to_loaded_page(self.current_page)

        self._prefetch_adjacent()

    # ── Cooperative prefetch ─────────────────────────────────────

    def _prefetch_adjacent(self) -> None:
        """Schedule background cache warm-up for nearby pages."""
        if not self._engine:
            return
        page = self.current_page
        for offset in (1, -1, 2, -2, 3, -3):
            p = page + offset
            if 0 <= p < self._engine.page_count and not self._engine.is_page_cached(p):
                self.set_timer(0.05, lambda pp=p: self._prefetch_one(pp))
                return

    def _prefetch_one(self, page_num: int) -> None:
        """Prefetch a single page, then chain to next."""
        if not self._engine or self._engine.is_page_cached(page_num):
            return
        self._engine.get_page_markdown(page_num)
        self._prefetch_adjacent()

    # ── Navigation ───────────────────────────────────────────────

    def next_page(self) -> None:
        if not self._engine:
            return
        target = self.current_page + 1
        if target >= self._engine.page_count:
            return
        self.current_page = target
        self._schedule_render()

    def prev_page(self) -> None:
        if not self._engine:
            return
        target = self.current_page - 1
        if target < 0:
            return
        self.current_page = target
        self._schedule_render()

    def go_to_page(self, page: int) -> None:
        if not self._engine or not (0 <= page < self._engine.page_count):
            return
        self.current_page = page
        self._schedule_render()

    def _scroll_to_loaded_page(self, page: int) -> None:
        """Ensure *page* is loaded and scroll to its separator."""
        if page not in self._loaded_pages:
            self._clear_dynamic_pages()
            self.query_one("#pdf-content", Markdown).display = False
            start = max(0, page - 1)
            end = min(page + self._LOAD_AHEAD + 1, self._engine.page_count)  # type: ignore[union-attr]
            self._load_dynamic_pages(start, end)

        try:
            sep = self.query_one(f"#sep-{page}")
            sep.scroll_visible(top=True, animate=False)
        except Exception:
            pass

    def get_current_text(self) -> str:
        if not self._engine:
            return ""
        return self._engine.get_page_markdown(self.current_page)
