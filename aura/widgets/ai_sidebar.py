"""AI assistant sidebar - clean chat interface, keyboard driven."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Input, Label, Static

from aura.ai_service import ContextScope


class ChatBubble(Static):
    """A single chat message."""

    DEFAULT_CSS = """
    ChatBubble {
        width: 100%;
        padding: 1 2;
        margin: 0 0 1 0;
    }
    ChatBubble.user-msg {
        background: $primary-darken-2;
        border-left: thick $primary;
    }
    ChatBubble.ai-msg {
        background: $surface;
        border-left: thick $success;
    }
    ChatBubble.error-msg {
        background: $error 20%;
        border-left: thick $error;
    }
    """


class AISidebar(Widget):
    """Keyboard-driven AI chat sidebar. No buttons — just type and talk."""

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

    AISidebar #scope-indicator {
        height: 1;
        padding: 0 2;
        color: $accent;
        text-style: bold;
        background: $primary-background;
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
    AISidebar #status-line {
        height: 1;
        padding: 0 2;
        color: $text-muted;
    }
    AISidebar #ai-input {
        dock: bottom;
        margin: 0 1 1 1;
    }
    """

    scope: reactive[ContextScope] = reactive(ContextScope.CURRENT_PAGE)

    class ChatMessageSent(Message):
        def __init__(self, text: str, scope: ContextScope) -> None:
            super().__init__()
            self.text = text
            self.scope = scope

    class BookContextRequested(Message):
        """Ask the app to load full book context."""

    def __init__(self) -> None:
        super().__init__()
        self._streaming = False
        self._current_bubble: ChatBubble | None = None
        self._ai_tokens: list[str] = []

    def compose(self) -> ComposeResult:
        yield Label("Page ← [s] switch scope", id="scope-indicator")
        with VerticalScroll(id="chat-scroll"):
            yield Label("Type a question below to start.", id="chat-empty")
        yield Label("", id="status-line")
        yield Input(placeholder="Ask about this page...", id="ai-input")

    def watch_scope(self, value: ContextScope) -> None:
        label = "Page" if value == ContextScope.CURRENT_PAGE else "Book"
        self.query_one("#scope-indicator", Label).update(
            f"{label} ← [dim][s] switch[/]"
        )
        placeholder = (
            "Ask about this page..."
            if value == ContextScope.CURRENT_PAGE
            else "Ask about the entire book..."
        )
        self.query_one("#ai-input", Input).placeholder = placeholder

    def toggle_scope(self) -> None:
        if self.scope == ContextScope.CURRENT_PAGE:
            self.scope = ContextScope.FULL_BOOK
            self.post_message(self.BookContextRequested())
        else:
            self.scope = ContextScope.CURRENT_PAGE

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text or self._streaming:
            return
        event.input.clear()
        self.post_message(self.ChatMessageSent(text, self.scope))

    # -- Chat display methods (called by App) --

    def _hide_empty(self) -> None:
        empty = self.query_one("#chat-empty", Label)
        if empty.display:
            empty.display = False

    def append_user_message(self, text: str) -> None:
        self._hide_empty()
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        bubble = ChatBubble(classes="user-msg")
        bubble.update(f"[bold cyan]You[/]\n{text}")
        scroll.mount(bubble)
        scroll.scroll_end(animate=False)

    def begin_ai_response(self) -> None:
        self._streaming = True
        self._hide_empty()
        self._ai_tokens.clear()
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        bubble = ChatBubble(classes="ai-msg")
        bubble.update("[bold green]AI[/]\n▍")
        scroll.mount(bubble)
        self._current_bubble = bubble
        scroll.scroll_end(animate=False)
        self.query_one("#status-line", Label).update("Thinking...")

    def append_ai_token(self, token: str) -> None:
        self._ai_tokens.append(token)
        if self._current_bubble:
            text = "".join(self._ai_tokens)
            self._current_bubble.update(f"[bold green]AI[/]\n{text}▍")
            self.query_one("#chat-scroll", VerticalScroll).scroll_end(animate=False)

    def end_ai_response(self) -> None:
        self._streaming = False
        if self._current_bubble:
            text = "".join(self._ai_tokens)
            self._current_bubble.update(f"[bold green]AI[/]\n{text}")
        self._current_bubble = None
        self._ai_tokens.clear()
        self.query_one("#status-line", Label).update("")

    def show_error(self, error: str) -> None:
        self._streaming = False
        self._hide_empty()
        if self._current_bubble:
            self._current_bubble.remove()
            self._current_bubble = None
        self._ai_tokens.clear()
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        bubble = ChatBubble(classes="error-msg")
        bubble.update(f"[bold red]Error[/]\n{error}")
        scroll.mount(bubble)
        scroll.scroll_end(animate=False)
        self.query_one("#status-line", Label).update("")

    def toggle(self) -> None:
        self.toggle_class("hidden")
