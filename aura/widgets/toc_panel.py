"""Table of Contents sidebar panel."""

from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Label, Tree
from textual.widgets.tree import TreeNode

from aura.pdf_engine import TOCEntry

_MIN_PANEL_WIDTH = 15


class ResizeHandle(Widget):
    """Draggable handle on the panel's right edge for width adjustment."""

    DEFAULT_CSS = """
    ResizeHandle {
        width: 1;
        height: 100%;
        dock: right;
        background: $primary;
    }
    ResizeHandle:hover, ResizeHandle.-active {
        background: $accent;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._dragging = False

    def render(self) -> str:
        return ""

    def on_mouse_down(self, event: events.MouseDown) -> None:
        self._dragging = True
        self.add_class("-active")
        self.capture_mouse()
        event.stop()

    def on_mouse_up(self, event: events.MouseUp) -> None:
        if self._dragging:
            self._dragging = False
            self.remove_class("-active")
            self.release_mouse()
            event.stop()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if self._dragging and self.parent and self.screen:
            max_width = self.screen.size.width // 2
            new_width = max(_MIN_PANEL_WIDTH, min(event.screen_x + 1, max_width))
            self.parent.styles.width = new_width
            event.stop()


class TOCPanel(Widget):
    """A collapsible panel showing the PDF table of contents."""

    DEFAULT_CSS = """
    TOCPanel {
        width: 30;
        dock: left;
        padding: 0 0 0 1;
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
        yield ResizeHandle()
        yield Label("Table of Contents", id="toc-title")
        yield Tree("TOC", id="toc-tree")

    def on_mount(self) -> None:
        tree = self.query_one(Tree)
        tree.show_root = False
        tree.guide_depth = 2
        tree.auto_expand = False

    def load_toc(self, entries: list[TOCEntry]) -> None:
        """Populate the tree from TOC entries."""
        tree = self.query_one(Tree)
        tree.clear()

        if not entries:
            tree.root.add_leaf("(No table of contents)")
            return

        branches = self._find_branch_indices(entries)

        node_stack: list[TreeNode] = []
        for i, entry in enumerate(entries):
            while len(node_stack) >= entry.level:
                node_stack.pop()

            parent = node_stack[-1] if node_stack else tree.root
            if i in branches:
                node = parent.add(entry.title, data=entry.page)
            else:
                node = parent.add_leaf(entry.title, data=entry.page)
            node_stack.append(node)

        tree.root.expand_all()

    @staticmethod
    def _find_branch_indices(entries: list[TOCEntry]) -> set[int]:
        """Return indices of entries whose next sibling has a deeper level."""
        return {
            i
            for i, entry in enumerate(entries)
            if i + 1 < len(entries) and entries[i + 1].level > entry.level
        }

    def _navigate_to(self, page: int | None) -> None:
        if page is not None:
            self.post_message(self.EntrySelected(page=page))

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        self._navigate_to(event.node.data)

    def toggle(self) -> None:
        self.toggle_class("hidden")
