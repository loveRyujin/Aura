"""Multi-session chat management with JSON persistence."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class ChatMessage:
    role: str
    content: str


@dataclass
class ChatSession:
    id: str
    title: str
    book_path: str
    messages: list[ChatMessage] = field(default_factory=list)
    compressed_summary: str = ""
    current_page: int = 0
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc).isoformat()


def _book_hash(book_path: str) -> str:
    return hashlib.md5(book_path.encode()).hexdigest()[:8]


_DEFAULT_DIR = Path.home() / ".config" / "aura" / "sessions"


class SessionManager:
    """CRUD for chat sessions with JSON file persistence."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self._base_dir = base_dir or _DEFAULT_DIR
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._active: ChatSession | None = None

    @property
    def active_session(self) -> ChatSession | None:
        return self._active

    def set_active(self, session: ChatSession) -> None:
        self._active = session

    # ── CRUD ─────────────────────────────────────────────────────

    def create_session(
        self, book_path: str = "", title: str = ""
    ) -> ChatSession:
        if not title and book_path:
            title = Path(book_path).stem[:40]
        title = title or "New Chat"
        session = ChatSession(
            id=uuid.uuid4().hex[:12],
            title=title,
            book_path=book_path,
        )
        self.save_session(session)
        return session

    def list_sessions(self, book_path: str | None = None) -> list[ChatSession]:
        sessions: list[ChatSession] = []
        for fp in sorted(self._base_dir.glob("*.json"), reverse=True):
            try:
                s = self._load_file(fp)
                if book_path is None or s.book_path == book_path:
                    sessions.append(s)
            except Exception:
                continue
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return sessions

    def get_session(self, session_id: str) -> ChatSession | None:
        for fp in self._base_dir.glob(f"*_{session_id}.json"):
            try:
                return self._load_file(fp)
            except Exception:
                return None
        return None

    def delete_session(self, session_id: str) -> None:
        for fp in self._base_dir.glob(f"*_{session_id}.json"):
            fp.unlink(missing_ok=True)
        if self._active and self._active.id == session_id:
            self._active = None

    def save_session(self, session: ChatSession | None = None) -> None:
        session = session or self._active
        if not session:
            return
        session.touch()
        h = _book_hash(session.book_path) if session.book_path else "global"
        fp = self._base_dir / f"{h}_{session.id}.json"
        data = asdict(session)
        fp.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def get_or_create_for_book(self, book_path: str) -> ChatSession:
        """Resume the most recent session for *book_path*, or create one."""
        existing = self.list_sessions(book_path)
        if existing:
            session = existing[0]
        else:
            session = self.create_session(book_path)
        self._active = session
        return session

    # ── Internal ─────────────────────────────────────────────────

    @staticmethod
    def _load_file(fp: Path) -> ChatSession:
        data = json.loads(fp.read_text())
        msgs = [ChatMessage(**m) for m in data.pop("messages", [])]
        return ChatSession(**data, messages=msgs)
