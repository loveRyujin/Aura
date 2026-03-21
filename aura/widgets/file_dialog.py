"""File browser dialog for selecting PDF files."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import DirectoryTree, Label, ListItem, ListView

from aura.recent_files import RecentFile


class FilteredDirectoryTree(DirectoryTree):
    """DirectoryTree that only shows PDF files and directories."""

    def filter_paths(self, paths: list[Path]) -> list[Path]:
        return [
            p for p in paths
            if p.is_dir() or p.suffix.lower() == ".pdf"
        ]


class RecentFileItem(ListItem):
    """A single recent PDF entry."""

    def __init__(self, entry: RecentFile) -> None:
        super().__init__()
        self.entry = entry

    def compose(self) -> ComposeResult:
        page = self.entry.current_page + 1 if self.entry.current_page >= 0 else 1
        yield Label(f"[b]{self.entry.title}[/b]  [dim]p.{page}[/]")
        yield Label(f"[dim]{self.entry.path}[/]")


class FileDialog(ModalScreen[Path | None]):
    """Modal file picker that filters for PDF files."""

    DEFAULT_CSS = """
    FileDialog {
        align: center middle;
    }

    FileDialog #dialog-container {
        width: 70%;
        height: 80%;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    FileDialog #dialog-title {
        text-style: bold;
        padding: 1 0;
        color: $accent;
    }

    FileDialog #dialog-hint {
        color: $text-muted;
        padding: 0 0 1 0;
    }

    FileDialog #recent-title {
        padding: 1 0 0 0;
        color: $accent;
    }

    FileDialog #recent-list {
        height: auto;
        max-height: 8;
        margin-bottom: 1;
    }

    FileDialog DirectoryTree {
        height: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    class FileSelected(Message):
        """Emitted when a PDF file is selected."""

        def __init__(self, path: Path) -> None:
            super().__init__()
            self.path = path

    def __init__(
        self,
        start_dir: Path | None = None,
        recent_files: list[RecentFile] | None = None,
    ):
        super().__init__()
        self._start_dir = start_dir or Path.home()
        self._recent_files = recent_files or []

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog-container"):
            yield Label("Open PDF File", id="dialog-title")
            yield Label("Select a .pdf file (Escape to cancel)", id="dialog-hint")
            if self._recent_files:
                yield Label("Recent Files", id="recent-title")
                with ListView(id="recent-list"):
                    for entry in self._recent_files:
                        yield RecentFileItem(entry)
            yield FilteredDirectoryTree(str(self._start_dir))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if isinstance(item, RecentFileItem):
            self.dismiss(Path(item.entry.path))

    def on_directory_tree_file_selected(
        self, event: DirectoryTree.FileSelected
    ) -> None:
        path = Path(str(event.path))
        if path.suffix.lower() == ".pdf":
            self.dismiss(path)

    def action_cancel(self) -> None:
        self.dismiss(None)
