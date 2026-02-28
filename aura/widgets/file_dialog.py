"""File browser dialog for selecting PDF files."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import DirectoryTree, Footer, Header, Label


class FilteredDirectoryTree(DirectoryTree):
    """DirectoryTree that only shows PDF files and directories."""

    def filter_paths(self, paths: list[Path]) -> list[Path]:
        return [
            p for p in paths
            if p.is_dir() or p.suffix.lower() == ".pdf"
        ]


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

    def __init__(self, start_dir: Path | None = None):
        super().__init__()
        self._start_dir = start_dir or Path.home()

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog-container"):
            yield Label("Open PDF File", id="dialog-title")
            yield Label("Select a .pdf file (Escape to cancel)", id="dialog-hint")
            yield FilteredDirectoryTree(str(self._start_dir))

    def on_directory_tree_file_selected(
        self, event: DirectoryTree.FileSelected
    ) -> None:
        path = Path(str(event.path))
        if path.suffix.lower() == ".pdf":
            self.dismiss(path)

    def action_cancel(self) -> None:
        self.dismiss(None)
