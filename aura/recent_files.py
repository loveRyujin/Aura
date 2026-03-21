"""Recent file tracking with JSON persistence."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

_DEFAULT_PATH = Path.home() / ".config" / "aura" / "recent_files.json"
_MAX_RECENT = 20


@dataclass
class RecentFile:
    path: str
    title: str
    last_opened: str
    current_page: int = 0


class RecentFileManager:
    """Tracks recently opened PDFs and their reading progress."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _DEFAULT_PATH
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def list_recent(self, limit: int = 8) -> list[RecentFile]:
        records = self._load_all()
        records.sort(key=lambda item: item.last_opened, reverse=True)
        existing = [item for item in records if Path(item.path).exists()]
        return existing[:limit]

    def record_open(self, path: str, current_page: int = 0) -> None:
        records = self._load_all()
        target = str(Path(path))
        title = Path(target).name
        now = datetime.now(timezone.utc).isoformat()

        updated = False
        for item in records:
            if item.path == target:
                item.last_opened = now
                item.current_page = current_page
                item.title = title
                updated = True
                break

        if not updated:
            records.append(
                RecentFile(
                    path=target,
                    title=title,
                    last_opened=now,
                    current_page=current_page,
                )
            )

        self._save_all(records)

    def update_progress(self, path: str, current_page: int) -> None:
        records = self._load_all()
        target = str(Path(path))
        for item in records:
            if item.path == target:
                item.current_page = current_page
                self._save_all(records)
                return

    def most_recent_dir(self) -> Path | None:
        recent = self.list_recent(limit=1)
        if not recent:
            return None
        return Path(recent[0].path).parent

    def _load_all(self) -> list[RecentFile]:
        if not self._path.exists():
            return []

        try:
            data = json.loads(self._path.read_text())
        except Exception:
            return []

        items: list[RecentFile] = []
        for row in data:
            try:
                items.append(RecentFile(**row))
            except Exception:
                continue
        return items

    def _save_all(self, records: list[RecentFile]) -> None:
        deduped: dict[str, RecentFile] = {}
        for item in records:
            deduped[item.path] = item

        ordered = sorted(
            deduped.values(),
            key=lambda item: item.last_opened,
            reverse=True,
        )[:_MAX_RECENT]
        payload = [asdict(item) for item in ordered]
        self._path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
