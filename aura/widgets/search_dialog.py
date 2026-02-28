"""Search dialog for finding text within the PDF."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Input, Label, ListItem, ListView


class SearchResult(ListItem):
    """A single search result entry."""

    def __init__(self, page: int, snippet: str) -> None:
        super().__init__()
        self.page = page
        self.snippet = snippet

    def compose(self) -> ComposeResult:
        yield Label(f"[b]p.{self.page + 1}[/b]  {self.snippet}")


class SearchDialog(ModalScreen[int | None]):
    """Modal search dialog that returns a page number."""

    DEFAULT_CSS = """
    SearchDialog {
        align: center middle;
    }

    SearchDialog #search-container {
        width: 70%;
        height: 60%;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    SearchDialog #search-title {
        text-style: bold;
        padding: 1 0;
        color: $accent;
    }

    SearchDialog #search-input {
        margin-bottom: 1;
    }

    SearchDialog ListView {
        height: 1fr;
    }

    SearchDialog #no-results {
        color: $text-muted;
        padding: 1 0;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    class SearchRequested(Message):
        def __init__(self, query: str) -> None:
            super().__init__()
            self.query = query

    def compose(self) -> ComposeResult:
        with Vertical(id="search-container"):
            yield Label("Search in PDF", id="search-title")
            yield Input(placeholder="Type to search...", id="search-input")
            yield Label("", id="no-results")
            yield ListView(id="search-results")

    def on_mount(self) -> None:
        self.query_one("#search-results", ListView).display = False
        self.query_one(Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        query = event.value.strip()
        if not query:
            return
        self.post_message(self.SearchRequested(query))

    def show_results(self, results: list[tuple[int, str]]) -> None:
        lv = self.query_one("#search-results", ListView)
        no_results = self.query_one("#no-results", Label)
        lv.clear()

        if not results:
            no_results.update("No results found.")
            no_results.display = True
            lv.display = False
            return

        no_results.display = False
        lv.display = True
        for page, snippet in results:
            lv.append(SearchResult(page, snippet))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if isinstance(item, SearchResult):
            self.dismiss(item.page)

    def action_cancel(self) -> None:
        self.dismiss(None)
