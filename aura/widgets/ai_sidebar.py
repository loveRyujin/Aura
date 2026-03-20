"""AI assistant sidebar — chat UI with sessions, slash commands, and markdown."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.events import MouseDown, MouseMove, MouseUp
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Input, Label, Markdown, Static

from aura.ai_service import SLASH_COMMANDS, expand_slash_command
from aura.session import ChatSession

MIN_WIDTH = 30
MAX_WIDTH_RATIO = 0.7


# ── Chat bubble ──────────────────────────────────────────────────


class ChatBubble(Static):
    """A single chat message (plain text during streaming)."""

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


class AiMarkdownBubble(Markdown):
    """Rendered markdown bubble for finalized AI responses."""

    DEFAULT_CSS = """
    AiMarkdownBubble {
        width: 100%;
        padding: 1 2;
        margin: 0 0 1 0;
        background: $surface;
        border-left: thick $success;
    }
    """


# ── Quick-prompt suggestion chip ─────────────────────────────────


class QuickPrompt(Static):
    """A clickable quick-prompt suggestion."""

    DEFAULT_CSS = """
    QuickPrompt {
        width: 100%;
        padding: 0 2;
        margin: 0 0 0 0;
        color: $accent;
    }
    QuickPrompt:hover {
        background: $primary-darken-2;
        text-style: bold;
    }
    """

    class Clicked(Message):
        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    def __init__(self, prompt_text: str) -> None:
        super().__init__()
        self._prompt = prompt_text

    def render(self) -> str:
        return f"  › {self._prompt}"

    def on_click(self) -> None:
        self.post_message(self.Clicked(self._prompt))


# ── Session list item ────────────────────────────────────────────


class SessionItem(Static):
    """A clickable session entry in the session picker."""

    DEFAULT_CSS = """
    SessionItem {
        width: 100%;
        padding: 0 2;
        height: 1;
    }
    SessionItem:hover {
        background: $primary-darken-2;
    }
    SessionItem.-active {
        color: $accent;
        text-style: bold;
    }
    """

    class Selected(Message):
        def __init__(self, session_id: str) -> None:
            super().__init__()
            self.session_id = session_id

    def __init__(self, session: ChatSession, is_active: bool = False) -> None:
        super().__init__()
        self._session = session
        self._is_active = is_active

    def on_mount(self) -> None:
        if self._is_active:
            self.add_class("-active")

    def render(self) -> str:
        marker = "▸ " if self._is_active else "  "
        title = self._session.title[:30]
        n = len(self._session.messages)
        return f"{marker}{title} ({n} msgs)"

    def on_click(self) -> None:
        self.post_message(self.Selected(self._session.id))


# ── Drag handle ──────────────────────────────────────────────────


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


# ── Main sidebar ─────────────────────────────────────────────────

_QUICK_PROMPTS = [
    "Summarize the document",
    "Explain the key concepts",
    "What are the main takeaways?",
    "Translate to Chinese",
]


class AISidebar(Widget):
    """Keyboard-driven AI chat sidebar with sessions, slash commands, and markdown."""

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

    AISidebar #session-bar {
        height: 1;
        padding: 0 1;
        background: $primary-background;
        color: $text;
    }

    AISidebar #session-list {
        height: auto;
        max-height: 8;
        display: none;
        background: $surface;
    }

    AISidebar #chat-scroll {
        height: 1fr;
        padding: 1 1;
    }
    AISidebar #chat-empty {
        color: $text-muted;
        text-align: center;
        padding: 2 1 0 1;
        width: 100%;
    }
    AISidebar #slash-hint {
        height: auto;
        display: none;
        padding: 0 2;
        color: $text-muted;
        background: $surface;
    }
    AISidebar #rag-status {
        height: 1;
        padding: 0 2;
        color: $warning;
    }
    AISidebar #rag-status.ready {
        color: $success;
    }
    AISidebar #status-line {
        height: 1;
        padding: 0 2;
        color: $text-muted;
    }
    AISidebar #ai-input {
        dock: bottom;
        height: 3;
        margin: 0 1 1 1;
    }
    """

    # ── Messages ─────────────────────────────────────────────────

    class ChatMessageSent(Message):
        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    class CancelRequested(Message):
        """Ask the app to cancel the in-flight AI stream."""

    class SessionSwitched(Message):
        def __init__(self, session_id: str) -> None:
            super().__init__()
            self.session_id = session_id

    class NewSessionRequested(Message):
        """Ask the app to create a new session."""

    class RenameSessionRequested(Message):
        """Ask the app to rename the current session."""

    class DeleteSessionRequested(Message):
        """Ask the app to delete the current session."""

    # ── Init ─────────────────────────────────────────────────────

    def __init__(self) -> None:
        super().__init__()
        self._streaming = False
        self._ready_for_questions = False
        self._current_bubble: ChatBubble | None = None
        self._ai_tokens: list[str] = []
        self._session_list_open = False
        self._model_name = "AI"

    def compose(self) -> ComposeResult:
        yield SidebarDragHandle()
        with Widget(id="sidebar-body"):
            yield Label("Session ▾  [Ctrl+N] new", id="session-bar")
            with VerticalScroll(id="session-list"):
                pass
            with VerticalScroll(id="chat-scroll"):
                yield Label("Ask a question or try a quick prompt:", id="chat-empty")
                for prompt_text in _QUICK_PROMPTS:
                    yield QuickPrompt(prompt_text)
            yield Label("", id="slash-hint")
            yield Label("", id="rag-status")
            yield Label("", id="status-line")
            yield Input(id="ai-input", placeholder="Ask about the book... (/ for commands)")

    BINDINGS = [
        ("escape", "cancel_stream", "Cancel"),
        ("ctrl+l", "clear_chat", "Clear"),
        ("ctrl+n", "new_session", "New Session"),
        ("ctrl+r", "rename_session", "Rename Session"),
        ("ctrl+d", "delete_session", "Delete Session"),
    ]

    # ── Resize ───────────────────────────────────────────────────

    def on_sidebar_drag_handle_resized(self, event: SidebarDragHandle.Resized) -> None:
        screen_width = self.screen.size.width
        max_width = int(screen_width * MAX_WIDTH_RATIO)
        new_width = max(MIN_WIDTH, min(event.width, max_width))
        self.styles.width = new_width

    # ── Input handling ───────────────────────────────────────────

    def on_input_changed(self, event: Input.Changed) -> None:
        """Show slash-command hints when input starts with /."""
        if event.input.id != "ai-input":
            return
        hint_label = self.query_one("#slash-hint", Label)
        text = event.value.strip()
        if text.startswith("/") and not self._streaming:
            typed_cmd = text.split()[0][1:] if text else ""
            lines: list[str] = []
            for name, cmd in SLASH_COMMANDS.items():
                if not typed_cmd or name.startswith(typed_cmd):
                    lines.append(f"  /{name} — {cmd.description}")
            if lines:
                hint_label.update("\n".join(lines))
                hint_label.display = True
                return
        hint_label.display = False

    def _handle_input_submit(self) -> None:
        """Handle Enter key to submit the input."""
        input_widget = self.query_one("#ai-input", Input)
        text = input_widget.value.strip()
        if not text or self._streaming:
            return
        if not self._ready_for_questions:
            self.show_index_blocked_hint()
            return
        input_widget.value = ""
        self.query_one("#slash-hint", Label).display = False

        expanded = expand_slash_command(text)
        final_text = expanded if expanded else text

        self.post_message(self.ChatMessageSent(final_text))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "ai-input":
            self._handle_input_submit()

    # ── Quick prompts ────────────────────────────────────────────

    def on_quick_prompt_clicked(self, event: QuickPrompt.Clicked) -> None:
        if self._streaming:
            return
        if not self._ready_for_questions:
            self.show_index_blocked_hint()
            return
        self.post_message(self.ChatMessageSent(event.text))

    # ── Session picker ───────────────────────────────────────────

    def update_session_bar(self, session: ChatSession | None) -> None:
        title = session.title[:25] if session else "No session"
        self.query_one("#session-bar", Label).update(
            f"{title} ▾  [dim][Ctrl+N] new [Ctrl+R] rename [Ctrl+D] delete[/]"
        )

    def refresh_session_list(self, sessions: list[ChatSession], active_id: str) -> None:
        container = self.query_one("#session-list", VerticalScroll)
        container.remove_children()
        for s in sessions[:10]:
            container.mount(SessionItem(s, is_active=(s.id == active_id)))

    def toggle_session_list(self) -> None:
        container = self.query_one("#session-list", VerticalScroll)
        self._session_list_open = not self._session_list_open
        container.display = self._session_list_open

    def on_session_item_selected(self, event: SessionItem.Selected) -> None:
        self._session_list_open = False
        self.query_one("#session-list", VerticalScroll).display = False
        self.post_message(self.SessionSwitched(event.session_id))

    def on_label_clicked(self, event: Label) -> None:
        """Toggle session list when the session bar is clicked."""

    def on_click(self, event) -> None:
        try:
            label = self.query_one("#session-bar", Label)
            if label.region.contains_point(event.screen_offset):
                self.toggle_session_list()
        except Exception:
            pass

    # ── Chat display ─────────────────────────────────────────────

    def _hide_empty_and_prompts(self) -> None:
        try:
            empty = self.query_one("#chat-empty", Label)
            if empty.display:
                empty.display = False
        except Exception:
            pass
        for qp in self.query(QuickPrompt):
            qp.display = False

    def append_user_message(self, text: str) -> None:
        self._hide_empty_and_prompts()
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        bubble = ChatBubble(classes="user-msg")
        bubble.update(f"[bold cyan]You[/]\n{text}")
        scroll.mount(bubble)
        scroll.scroll_end(animate=False)

    def begin_ai_response(self, model_name: str = "AI") -> None:
        self._streaming = True
        self._model_name = model_name
        self._hide_empty_and_prompts()
        self._ai_tokens.clear()
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        bubble = ChatBubble(classes="ai-msg")
        bubble.update(f"[bold green]{model_name}[/]\n▍")
        scroll.mount(bubble)
        self._current_bubble = bubble
        scroll.scroll_end(animate=False)
        self.query_one("#status-line", Label).update(
            "Thinking... [dim]Esc to cancel[/]"
        )

    def append_ai_token(self, token: str) -> None:
        self._ai_tokens.append(token)
        if self._current_bubble:
            text = "".join(self._ai_tokens)
            self._current_bubble.update(f"[bold green]{self._model_name}[/]\n{text}▍")
            self.query_one("#chat-scroll", VerticalScroll).scroll_end(
                animate=False
            )

    def end_ai_response(self) -> None:
        self._streaming = False
        text = "".join(self._ai_tokens)
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        if self._current_bubble:
            self._current_bubble.remove()
            self._current_bubble = None
        md_bubble = AiMarkdownBubble(text)
        scroll.mount(md_bubble)
        scroll.scroll_end(animate=False)
        self._ai_tokens.clear()
        self.query_one("#status-line", Label).update("")

    def end_ai_response_cancelled(self) -> None:
        """Finalize a partial response after cancellation."""
        self._streaming = False
        text = "".join(self._ai_tokens)
        if self._current_bubble:
            self._current_bubble.update(
                f"[bold green]{self._model_name}[/]\n{text}\n[dim italic]\\[Cancelled][/]"
            )
        self._current_bubble = None
        self._ai_tokens.clear()
        self.query_one("#status-line", Label).update("")

    def show_error(self, error: str) -> None:
        self._streaming = False
        self._hide_empty_and_prompts()
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

    def _show_empty_state(self) -> None:
        """Re-show the initial empty-state label and quick prompts."""
        try:
            self.query_one("#chat-empty", Label).display = True
        except Exception:
            pass
        for qp in self.query(QuickPrompt):
            qp.display = True

    def rebuild_chat(self, session: ChatSession) -> None:
        """Rebuild bubbles from a loaded session's history."""
        scroll = self.query_one("#chat-scroll", VerticalScroll)

        for child in list(scroll.children):
            if isinstance(child, (ChatBubble, AiMarkdownBubble)):
                child.remove()

        if not session.messages:
            self._show_empty_state()
            return

        self._hide_empty_and_prompts()
        for msg in session.messages:
            if msg.role == "user":
                bubble = ChatBubble(classes="user-msg")
                bubble.update(f"[bold cyan]You[/]\n{msg.content}")
                scroll.mount(bubble)
            elif msg.role == "assistant":
                md_bubble = AiMarkdownBubble(msg.content)
                scroll.mount(md_bubble)
        scroll.scroll_end(animate=False)

    # ── Actions ──────────────────────────────────────────────────

    def action_cancel_stream(self) -> None:
        if self._streaming:
            self.post_message(self.CancelRequested())

    def action_clear_chat(self) -> None:
        if self._streaming:
            return
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        for child in list(scroll.children):
            if isinstance(child, (ChatBubble, AiMarkdownBubble)):
                child.remove()
        self._show_empty_state()
        self.post_message(self.ChatMessageSent("__clear__"))

    def action_new_session(self) -> None:
        self.post_message(self.NewSessionRequested())

    def action_rename_session(self) -> None:
        if self._streaming:
            return
        self.post_message(self.RenameSessionRequested())

    def action_delete_session(self) -> None:
        if self._streaming:
            return
        self.post_message(self.DeleteSessionRequested())

    # ── Toggle ───────────────────────────────────────────────────

    def toggle(self) -> None:
        self.toggle_class("hidden")
        if not self.has_class("hidden"):
            self.call_later(self._focus_input)

    def _focus_input(self) -> None:
        try:
            self.query_one("#ai-input", Input).focus()
        except Exception:
            pass

    # ── RAG status ────────────────────────────────────────────────

    def update_rag_status(self, text: str, ready: bool = False) -> None:
        label = self.query_one("#rag-status", Label)
        label.update(text)
        self._ready_for_questions = ready
        input_widget = self.query_one("#ai-input", Input)
        input_widget.disabled = not ready
        input_widget.placeholder = (
            "Ask about the book... (/ for commands)"
            if ready
            else "Wait for indexing to finish before asking questions"
        )
        if ready:
            label.add_class("ready")
        else:
            label.remove_class("ready")

    def show_index_blocked_hint(self) -> None:
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        hint = ChatBubble(classes="ai-msg")
        hint.update(
            "[dim]The retrieval index for this book is still being built. "
            "Please wait until indexing finishes before asking questions.[/]"
        )
        scroll.mount(hint)
        scroll.scroll_end(animate=False)

    # ── Context indicator ────────────────────────────────────────

    def update_context_info(
        self, page: int, section: str, compressed: bool
    ) -> None:
        parts = [f"p.{page + 1}"]
        if section:
            parts.append(section[:20])
        if compressed:
            parts.append("compressed")
        self.query_one("#status-line", Label).update(
            " | ".join(parts) if not self._streaming else ""
        )
