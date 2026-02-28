"""Table of Contents sidebar panel."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Label, Tree
from textual.widgets.tree import TreeNode

from aura.pdf_engine import TOCEntry


class TOCPanel(Widget):
    """A collapsible panel showing the PDF table of contents."""

    DEFAULT_CSS = """
    TOCPanel {
        width: 30;
        dock: left;
        border-right: solid $primary;
        padding: 0 1;
    }

    TOCPanel.hidden {
        display: none;
    }

    TOCPanel #toc-title {
        text-style: bold;
        padding: 1 0;
        color: $accent;
    }

    TOCPanel Tree {
        height: 1fr;
    }
    """

    class EntrySelected(Message):
        """Emitted when a TOC entry is clicked."""

        def __init__(self, page: int) -> None:
            super().__init__()
            self.page = page

    def compose(self) -> ComposeResult:
        yield Label("Table of Contents", id="toc-title")
        yield Tree("TOC", id="toc-tree")

    def on_mount(self) -> None:
        tree = self.query_one(Tree)
        tree.show_root = False
        tree.guide_depth = 2

    def load_toc(self, entries: list[TOCEntry]) -> None:
        """Populate the tree from TOC entries."""
        tree = self.query_one(Tree)
        tree.clear()

        if not entries:
            tree.root.add_leaf("(No table of contents)")
            return

        node_stack: list[TreeNode] = []
        for entry in entries:
            while len(node_stack) >= entry.level:
                node_stack.pop()

            parent = node_stack[-1] if node_stack else tree.root
            label = f"{entry.title}"
            node = parent.add(label, data=entry.page)
            node_stack.append(node)

        tree.root.expand_all()

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        if event.node.data is not None:
            self.post_message(self.EntrySelected(page=event.node.data))

    def toggle(self) -> None:
        self.toggle_class("hidden")
