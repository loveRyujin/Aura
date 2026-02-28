"""AI assistant sidebar with chat interface and quick commands."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, Input, Label, RichLog

from aura.ai_service import AIService, QuickCommand


class AISidebar(Widget):
    """Toggleable AI assistant sidebar with chat and quick commands."""

    DEFAULT_CSS = """
    AISidebar {
        width: 45;
        dock: right;
        border-left: solid $primary;
        layout: vertical;
    }

    AISidebar.hidden {
        display: none;
    }

    AISidebar #ai-title {
        text-style: bold;
        padding: 1 1;
        color: $accent;
        text-align: center;
    }

    AISidebar #cmd-bar {
        height: auto;
        padding: 0 1;
    }

    AISidebar #cmd-bar Button {
        margin: 0 1 0 0;
        min-width: 12;
    }

    AISidebar #chat-log {
        height: 1fr;
        border-top: solid $primary-darken-2;
        border-bottom: solid $primary-darken-2;
        padding: 0 1;
    }

    AISidebar #ai-input {
        dock: bottom;
        margin: 0 1 1 1;
    }

    AISidebar #status-label {
        height: 1;
        padding: 0 1;
        color: $text-muted;
    }
    """

    class QuickCommandRequested(Message):
        """Emitted when a quick command button is pressed."""

        def __init__(self, command: QuickCommand) -> None:
            super().__init__()
            self.command = command

    class ChatMessageSent(Message):
        """Emitted when user sends a chat message."""

        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    def __init__(self) -> None:
        super().__init__()
        self._streaming = False

    def compose(self) -> ComposeResult:
        yield Label("AI Assistant", id="ai-title")
        with Horizontal(id="cmd-bar"):
            yield Button("Summarize", id="btn-summarize", variant="primary")
            yield Button("Key Points", id="btn-keypoints", variant="success")
            yield Button("Translate", id="btn-translate", variant="warning")
        yield Label("", id="status-label")
        yield RichLog(id="chat-log", wrap=True, markup=True, highlight=True)
        yield Input(placeholder="Ask about this page...", id="ai-input")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if self._streaming:
            return
        cmd_map = {
            "btn-summarize": QuickCommand.SUMMARIZE,
            "btn-keypoints": QuickCommand.KEY_POINTS,
            "btn-translate": QuickCommand.TRANSLATE,
        }
        if cmd := cmd_map.get(event.button.id or ""):
            self.post_message(self.QuickCommandRequested(cmd))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text or self._streaming:
            return
        event.input.clear()
        self.post_message(self.ChatMessageSent(text))

    def append_user_message(self, text: str) -> None:
        log = self.query_one("#chat-log", RichLog)
        log.write(f"[bold cyan]You:[/] {text}")

    def begin_ai_response(self) -> None:
        self._streaming = True
        log = self.query_one("#chat-log", RichLog)
        log.write("[bold green]AI:[/] ", shrink=False)
        self._set_status("Thinking...")

    def append_ai_token(self, token: str) -> None:
        log = self.query_one("#chat-log", RichLog)
        log.write(token, shrink=False, scroll_end=True)

    def end_ai_response(self) -> None:
        self._streaming = False
        log = self.query_one("#chat-log", RichLog)
        log.write("")  # newline
        self._set_status("")

    def show_error(self, error: str) -> None:
        self._streaming = False
        log = self.query_one("#chat-log", RichLog)
        log.write(f"[bold red]Error:[/] {error}")
        self._set_status("")

    def _set_status(self, text: str) -> None:
        self.query_one("#status-label", Label).update(text)

    def toggle(self) -> None:
        self.toggle_class("hidden")
