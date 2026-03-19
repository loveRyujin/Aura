"""Aura TUI application."""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Input as TextInput, Label
from textual.worker import Worker

from aura.ai_service import AIService
from aura.config import AppConfig
from aura.pdf_engine import PDFEngine
from aura.rag import RAGService
from aura.session import SessionManager
from aura.widgets.ai_sidebar import AISidebar
from aura.widgets.file_dialog import FileDialog
from aura.widgets.pdf_viewer import PDFViewer
from aura.widgets.search_dialog import SearchDialog
from aura.widgets.toc_panel import TOCPanel

_INDEX_BUILDING_MSG = "正在为本书建立检索索引，请等待完成后再提问"
_INDEX_READY_MSG = "索引已就绪，可以开始提问"
_INDEX_STALE_MSG = "文档已变更，正在重建索引，请稍候"


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
        ("v", "toggle_view", "View"),
        ("c", "toggle_scroll", "Scroll"),
        ("slash", "search", "Search"),
        ("g", "go_to_page", "Go to"),
        ("right,n", "next_page", "Next"),
        ("left,b", "prev_page", "Prev"),
    ]

    def __init__(self, file_path: Path | None = None, config: AppConfig | None = None):
        super().__init__()
        self.file_path = file_path
        self.config = config or AppConfig.load()
        self._ai_service = AIService(self.config.ai)
        self._rag_service = RAGService(self.config.embedding)
        self._session_mgr = SessionManager()
        self._ai_worker: Worker | None = None
        self._rag_indexing = False
        self._active_book_path = ""

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

    # ── PDF lifecycle ────────────────────────────────────────────

    def _open_pdf(self, path: Path) -> None:
        engine = PDFEngine(path)
        viewer = self.query_one(PDFViewer)
        viewer.load_pdf(engine)
        self._active_book_path = str(path)

        toc_panel = self.query_one(TOCPanel)
        toc_entries = engine.get_toc()
        toc_panel.load_toc(toc_entries)

        self._ai_service.clear_all()
        self._ai_service.set_pdf_metadata(
            filename=engine.filename,
            page_count=engine.page_count,
            toc_outline=engine.get_toc_outline(),
        )

        session = self._session_mgr.get_or_create_for_book(str(path))
        self._ai_service.bind_session(session)

        # Restore reading progress
        start_page = session.current_page
        if start_page > 0:
            viewer.go_to_page(start_page)

        sidebar = self.query_one(AISidebar)
        sidebar.update_session_bar(session)
        sidebar.rebuild_chat(session)

        self.sub_title = f"{engine.filename}  p.{start_page + 1}/{engine.page_count}"

        status = self._rag_service.get_index_status(str(path))
        if status.ready:
            chunk_text = f" ({status.chunk_count} chunks)" if status.chunk_count else ""
            sidebar.update_rag_status(f"{_INDEX_READY_MSG}{chunk_text}", ready=True)
        else:
            self._rag_indexing = True
            start_msg = _INDEX_STALE_MSG if status.stale else _INDEX_BUILDING_MSG
            sidebar.update_rag_status(start_msg, ready=False)
            self.run_worker(
                self._build_rag_index(engine, str(path)), exclusive=False
            )

    def _update_ai_location(self) -> None:
        viewer = self.query_one(PDFViewer)
        if viewer.engine:
            page = viewer.current_page
            section = viewer.engine.get_section_for_page(page)
            self._ai_service.update_location(page, section)

    # ── Page change ──────────────────────────────────────────────

    def on_pdfviewer_page_changed(self, event: PDFViewer.PageChanged) -> None:
        viewer = self.query_one(PDFViewer)
        if viewer.engine:
            self.sub_title = (
                f"{viewer.engine.filename}  "
                f"p.{event.page + 1}/{event.total}"
            )
            self._update_ai_location()
            sidebar = self.query_one(AISidebar)
            session = self._session_mgr.active_session
            if session:
                session.current_page = event.page
                self._session_mgr.save_session(session)
            sidebar.update_context_info(
                page=event.page,
                section=viewer.engine.get_section_for_page(event.page),
                compressed=bool(session and session.compressed_summary),
            )

    def on_tocpanel_entry_selected(self, event: TOCPanel.EntrySelected) -> None:
        self.query_one(PDFViewer).go_to_page(event.page)

    # ── RAG indexing ────────────────────────────────────────────

    async def _build_rag_index(self, engine: PDFEngine, book_path: str) -> None:
        sidebar = self.query_one(AISidebar)

        def _on_progress(done: int, total: int) -> None:
            sidebar.update_rag_status(f"索引构建中：{done}/{total}", ready=False)

        try:
            count = await self._rag_service.build_index(
                engine, book_path, on_progress=_on_progress
            )
            status = self._rag_service.get_index_status(book_path)
            if self._active_book_path == book_path:
                chunk_count = status.chunk_count or count
                chunk_text = f" ({chunk_count} chunks)" if chunk_count else ""
                sidebar.update_rag_status(f"{_INDEX_READY_MSG}{chunk_text}", ready=True)
        except Exception as exc:
            if self._active_book_path == book_path:
                sidebar.update_rag_status(f"索引构建失败：{exc!s:.40}", ready=False)
        finally:
            self._rag_indexing = False

    def on_aisidebar_chat_message_sent(
        self, event: AISidebar.ChatMessageSent
    ) -> None:
        if event.text == "__clear__":
            session = self._session_mgr.active_session
            if session:
                session.messages.clear()
                session.compressed_summary = ""
                self._session_mgr.save_session(session)
            return

        self._update_ai_location()
        sidebar = self.query_one(AISidebar)
        sidebar.append_user_message(event.text)
        self._ai_worker = self.run_worker(
            self._run_ai_query(event.text), exclusive=True
        )

    async def _run_ai_query(self, text: str) -> None:
        """Retrieve RAG context, then stream the AI response."""
        rag_context = ""
        viewer = self.query_one(PDFViewer)
        if viewer.engine:
            book_path = str(viewer.engine._path)
            if await self._rag_service.has_index_async(book_path):
                chunks = await self._rag_service.retrieve(text, book_path)
                rag_context = RAGService.format_context(chunks)

        stream = self._ai_service.stream_response(
            text, rag_context=rag_context
        )
        await self._consume_stream(stream)

    async def _consume_stream(self, stream) -> None:
        sidebar = self.query_one(AISidebar)
        model_name = self._ai_service._config.resolved_model
        sidebar.begin_ai_response(model_name)
        try:
            async for token in stream:
                sidebar.append_ai_token(token)
        except Exception as exc:
            sidebar.show_error(str(exc))
        else:
            sidebar.end_ai_response()

        session = self._session_mgr.active_session
        if session:
            self._session_mgr.save_session(session)

        self.run_worker(self._ai_service.maybe_compress(), exclusive=False)

    # ── Cancel ───────────────────────────────────────────────────

    def on_aisidebar_cancel_requested(
        self, event: AISidebar.CancelRequested
    ) -> None:
        if self._ai_worker and self._ai_worker.is_running:
            self._ai_worker.cancel()
            sidebar = self.query_one(AISidebar)
            sidebar.end_ai_response_cancelled()

    # ── Session management ───────────────────────────────────────

    def on_aisidebar_new_session_requested(
        self, event: AISidebar.NewSessionRequested
    ) -> None:
        viewer = self.query_one(PDFViewer)
        book_path = str(viewer.engine._path) if viewer.engine else ""
        self._session_mgr.save_session()
        session = self._session_mgr.create_session(book_path)
        self._session_mgr.set_active(session)
        self._ai_service.bind_session(session)

        sidebar = self.query_one(AISidebar)
        sidebar.update_session_bar(session)
        sidebar.rebuild_chat(session)
        self._refresh_session_list()

    def on_aisidebar_session_switched(
        self, event: AISidebar.SessionSwitched
    ) -> None:
        self._session_mgr.save_session()
        session = self._session_mgr.get_session(event.session_id)
        if not session:
            return
        self._session_mgr.set_active(session)
        self._ai_service.bind_session(session)

        sidebar = self.query_one(AISidebar)
        sidebar.update_session_bar(session)
        sidebar.rebuild_chat(session)

    def _refresh_session_list(self) -> None:
        viewer = self.query_one(PDFViewer)
        book_path = str(viewer.engine._path) if viewer.engine else None
        sessions = self._session_mgr.list_sessions(book_path)
        active = self._session_mgr.active_session
        active_id = active.id if active else ""
        self.query_one(AISidebar).refresh_session_list(sessions, active_id)

    # ── Actions ──────────────────────────────────────────────────

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
        if not self.query_one(AISidebar).has_class("hidden"):
            self._refresh_session_list()

    def action_toggle_view(self) -> None:
        self.query_one(PDFViewer).toggle_view_mode()

    def action_toggle_scroll(self) -> None:
        self.query_one(PDFViewer).toggle_scroll_mode()

    def action_next_page(self) -> None:
        self.query_one(PDFViewer).next_page()

    def action_prev_page(self) -> None:
        self.query_one(PDFViewer).prev_page()
