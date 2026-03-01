"""AI assistant sidebar - clean chat interface, keyboard driven, drag-resizable."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.events import MouseDown, MouseMove, MouseUp
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Input, Label, Static

from aura.ai_service import ContextScope

MIN_WIDTH = 30
MAX_WIDTH_RATIO = 0.7


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


class SidebarDragHandle(Widget):
    """A draggable resize handle on the left edge of the sidebar."""

    DEFAULT_CSS = """
    SidebarDragHandle {
        width: 1;
        height: 100%;
        dock: left;
        background: $primary-darken-1;
    }
    SidebarDragHandle:hover {
        background: $accent;
    }
    SidebarDragHandle.-active {
        background: $accent;
    }
    """

    class Resized(Message):
        def __init__(self, width: int) -> None:
            super().__init__()
            self.width = width

    def __init__(self) -> None:
        super().__init__()
        self._dragging = False

    def on_mouse_down(self, event: MouseDown) -> None:
        self._dragging = True
        self.add_class("-active")
        self.capture_mouse()
        event.stop()

    def on_mouse_move(self, event: MouseMove) -> None:
        if not self._dragging:
            return
        new_width = self.screen.size.width - event.screen_x
        self.post_message(self.Resized(new_width))
        event.stop()

    def on_mouse_up(self, event: MouseUp) -> None:
        if self._dragging:
            self._dragging = False
            self.remove_class("-active")
            self.release_mouse()
            event.stop()

    def render(self) -> str:
        return "┃"


class AISidebar(Widget):
    """Keyboard-driven AI chat sidebar with drag-to-resize."""

    DEFAULT_CSS = """
    AISidebar {
        width: 50;
        dock: right;
        layout: horizontal;
    }
    AISidebar.hidden {
        display: none;
    }

    AISidebar #sidebar-body {
        width: 1fr;
        layout: vertical;
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
        yield SidebarDragHandle()
        with Widget(id="sidebar-body"):
            yield Label("Page ← [s] switch scope", id="scope-indicator")
            with VerticalScroll(id="chat-scroll"):
                yield Label("Type a question below to start.", id="chat-empty")
            yield Label("", id="status-line")
            yield Input(placeholder="Ask about this page...", id="ai-input")

    def on_sidebar_drag_handle_resized(self, event: SidebarDragHandle.Resized) -> None:
        screen_width = self.screen.size.width
        max_width = int(screen_width * MAX_WIDTH_RATIO)
        new_width = max(MIN_WIDTH, min(event.width, max_width))
        self.styles.width = new_width

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

    # -- Chat display --

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
