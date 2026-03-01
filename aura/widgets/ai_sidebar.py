"""AI assistant sidebar with Cursor-style chat interface."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Button, Input, Label, Markdown, Static

from aura.ai_service import ContextScope, QuickCommand

SCOPE_LABELS = {
    ContextScope.CURRENT_PAGE: "Current Page",
    ContextScope.FULL_BOOK: "Entire Book",
}


class ChatBubble(Static):
    """A single chat message bubble."""

    DEFAULT_CSS = """
    ChatBubble {
        width: 100%;
        padding: 1 2;
        margin: 0 0 1 0;
    }

    ChatBubble.user-bubble {
        background: $primary-darken-2;
        border-left: thick $primary;
    }

    ChatBubble.ai-bubble {
        background: $surface;
        border-left: thick $success;
    }

    ChatBubble.error-bubble {
        background: $error 20%;
        border-left: thick $error;
    }

    ChatBubble .bubble-role {
        text-style: bold;
        margin-bottom: 1;
    }

    ChatBubble .bubble-content {
        width: 100%;
    }
    """


class AISidebar(Widget):
    """Toggleable AI assistant sidebar with modern chat UI."""

    DEFAULT_CSS = """
    AISidebar {
        width: 50;
        dock: right;
        border-left: solid $primary;
        layout: vertical;
    }

    AISidebar.hidden {
        display: none;
    }

    AISidebar.wide {
        width: 80;
    }

    AISidebar #sidebar-header {
        height: 3;
        background: $primary-background;
        padding: 1 1;
        layout: horizontal;
    }

    AISidebar #ai-title {
        text-style: bold;
        color: $accent;
        width: 1fr;
    }

    AISidebar #btn-resize {
        min-width: 3;
        max-width: 3;
        height: 1;
        margin: 0 0 0 1;
    }

    AISidebar #scope-bar {
        height: auto;
        padding: 0 1;
        layout: horizontal;
    }

    AISidebar #scope-bar Button {
        margin: 0 1 0 0;
        min-width: 14;
        height: 3;
    }

    AISidebar #scope-bar Button.active-scope {
        text-style: bold reverse;
    }

    AISidebar #cmd-bar {
        height: auto;
        padding: 0 1;
        layout: horizontal;
    }

    AISidebar #cmd-bar Button {
        margin: 0 1 0 0;
        min-width: 10;
        height: 3;
    }

    AISidebar #chat-scroll {
        height: 1fr;
        padding: 1 1;
    }

    AISidebar #chat-empty {
        color: $text-muted;
        text-align: center;
        padding: 3 1;
        width: 100%;
    }

    AISidebar #input-area {
        dock: bottom;
        height: auto;
        padding: 0 1 1 1;
    }

    AISidebar #ai-input {
        width: 1fr;
    }

    AISidebar #status-label {
        height: 1;
        padding: 0 1;
        color: $text-muted;
    }
    """

    scope: reactive[ContextScope] = reactive(ContextScope.CURRENT_PAGE)

    class QuickCommandRequested(Message):
        def __init__(self, command: QuickCommand, scope: ContextScope) -> None:
            super().__init__()
            self.command = command
            self.scope = scope

    class ChatMessageSent(Message):
        def __init__(self, text: str, scope: ContextScope) -> None:
            super().__init__()
            self.text = text
            self.scope = scope

    class BookContextRequested(Message):
        """Ask the app to load full book context into AIService."""

    def __init__(self) -> None:
        super().__init__()
        self._streaming = False
        self._current_ai_bubble: ChatBubble | None = None
        self._ai_buffer: list[str] = []

    def compose(self) -> ComposeResult:
        with Horizontal(id="sidebar-header"):
            yield Label("AI Assistant", id="ai-title")
            yield Button("⇔", id="btn-resize", variant="default")
        with Horizontal(id="scope-bar"):
            yield Button("Page", id="btn-scope-page", variant="primary", classes="active-scope")
            yield Button("Book", id="btn-scope-book", variant="default")
        with Horizontal(id="cmd-bar"):
            yield Button("Summary", id="btn-summarize", variant="primary")
            yield Button("Points", id="btn-keypoints", variant="success")
            yield Button("Trans", id="btn-translate", variant="warning")
        yield Label("", id="status-label")
        with VerticalScroll(id="chat-scroll"):
            yield Label("Ask a question or use a command above.", id="chat-empty")
        with Horizontal(id="input-area"):
            yield Input(placeholder="Ask about the PDF...", id="ai-input")

    def watch_scope(self, value: ContextScope) -> None:
        page_btn = self.query_one("#btn-scope-page", Button)
        book_btn = self.query_one("#btn-scope-book", Button)
        if value == ContextScope.CURRENT_PAGE:
            page_btn.add_class("active-scope")
            book_btn.remove_class("active-scope")
            self.query_one("#ai-input", Input).placeholder = "Ask about this page..."
        else:
            page_btn.remove_class("active-scope")
            book_btn.add_class("active-scope")
            self.query_one("#ai-input", Input).placeholder = "Ask about the entire book..."

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""

        if btn_id == "btn-resize":
            self.toggle_class("wide")
            return

        if btn_id == "btn-scope-page":
            self.scope = ContextScope.CURRENT_PAGE
            return
        if btn_id == "btn-scope-book":
            self.scope = ContextScope.FULL_BOOK
            self.post_message(self.BookContextRequested())
            return

        if self._streaming:
            return

        cmd_map = {
            "btn-summarize": QuickCommand.SUMMARIZE,
            "btn-keypoints": QuickCommand.KEY_POINTS,
            "btn-translate": QuickCommand.TRANSLATE,
        }
        if cmd := cmd_map.get(btn_id):
            self.post_message(self.QuickCommandRequested(cmd, self.scope))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text or self._streaming:
            return
        event.input.clear()
        self.post_message(self.ChatMessageSent(text, self.scope))

    def _hide_empty(self) -> None:
        empty = self.query_one("#chat-empty", Label)
        if empty.display:
            empty.display = False

    def append_user_message(self, text: str) -> None:
        self._hide_empty()
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        bubble = ChatBubble(classes="user-bubble")
        bubble.update(f"[bold cyan]You[/]\n{text}")
        scroll.mount(bubble)
        scroll.scroll_end(animate=False)

    def begin_ai_response(self) -> None:
        self._streaming = True
        self._hide_empty()
        self._ai_buffer.clear()
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        bubble = ChatBubble(classes="ai-bubble")
        bubble.update("[bold green]AI[/]\n▍")
        scroll.mount(bubble)
        self._current_ai_bubble = bubble
        scroll.scroll_end(animate=False)
        self._set_status("Thinking...")

    def append_ai_token(self, token: str) -> None:
        self._ai_buffer.append(token)
        if self._current_ai_bubble:
            text = "".join(self._ai_buffer)
            self._current_ai_bubble.update(f"[bold green]AI[/]\n{text}▍")
            scroll = self.query_one("#chat-scroll", VerticalScroll)
            scroll.scroll_end(animate=False)

    def end_ai_response(self) -> None:
        self._streaming = False
        if self._current_ai_bubble:
            text = "".join(self._ai_buffer)
            self._current_ai_bubble.update(f"[bold green]AI[/]\n{text}")
        self._current_ai_bubble = None
        self._ai_buffer.clear()
        self._set_status("")

    def show_error(self, error: str) -> None:
        self._streaming = False
        self._hide_empty()
        if self._current_ai_bubble:
            self._current_ai_bubble.remove()
            self._current_ai_bubble = None
        self._ai_buffer.clear()
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        bubble = ChatBubble(classes="error-bubble")
        bubble.update(f"[bold red]Error[/]\n{error}")
        scroll.mount(bubble)
        scroll.scroll_end(animate=False)
        self._set_status("")

    def _set_status(self, text: str) -> None:
        self.query_one("#status-label", Label).update(text)

    def toggle(self) -> None:
        self.toggle_class("hidden")
