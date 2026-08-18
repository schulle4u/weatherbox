"""Persist the lifecycle state of scheduled announcements."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from weatherbox.models import AnnouncementStatus, ScheduledAnnouncement


@dataclass(frozen=True, slots=True)
class StateEntry:
    """Persistent status and retry metadata for one announcement."""

    status: AnnouncementStatus
    attempts: int
    updated_at: datetime
    error: str | None = None
    public_path: str | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> StateEntry:
        """Deserialize an entry from JSON-compatible values."""
        return cls(
            status=AnnouncementStatus(value["status"]),
            attempts=int(value.get("attempts", 0)),
            updated_at=datetime.fromisoformat(value["updated_at"]),
            error=value.get("error"),
            public_path=value.get("public_path"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the entry to JSON-compatible values."""
        return {
            "status": self.status.value,
            "attempts": self.attempts,
            "updated_at": self.updated_at.isoformat(),
            "error": self.error,
            "public_path": self.public_path,
        }


class StateStore:
    """Maintain announcement state in an atomically updated JSON file."""

    def __init__(self, path: Path) -> None:
        """Initialize the store from a JSON state file."""
        self.path = path
        self._entries = self._read()

    def _read(self) -> dict[str, StateEntry]:
        """Read valid entries from disk, returning an empty store on failure."""
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return {key: StateEntry.from_dict(value) for key, value in raw.items()}
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            return {}

    def get(self, item: ScheduledAnnouncement) -> StateEntry | None:
        """Return the stored entry for an announcement, if present."""
        return self._entries.get(item.key)

    def set(
        self,
        item: ScheduledAnnouncement,
        status: AnnouncementStatus,
        now: datetime,
        *,
        error: str | None = None,
        public_path: Path | None = None,
        increment_attempts: bool = False,
    ) -> StateEntry:
        """Update and persist an announcement's status and metadata."""
        previous = self.get(item)
        attempts = (previous.attempts if previous else 0) + (1 if increment_attempts else 0)
        entry = StateEntry(
            status=status,
            attempts=attempts,
            updated_at=now,
            error=error,
            public_path=str(public_path) if public_path else (previous.public_path if previous else None),
        )
        self._entries[item.key] = entry
        self._write()
        return entry

    def entries(self) -> dict[str, StateEntry]:
        """Return a shallow copy of all stored entries."""
        return dict(self._entries)

    def expire_before(self, cutoff: datetime) -> None:
        """Mark unfinished announcements before ``cutoff`` as expired."""
        changed = False
        for key, entry in tuple(self._entries.items()):
            try:
                playback = datetime.fromisoformat(key.split(":", 2)[2])
            except ValueError:
                continue
            if playback < cutoff and entry.status not in {AnnouncementStatus.PUBLISHED, AnnouncementStatus.EXPIRED}:
                self._entries[key] = StateEntry(
                    status=AnnouncementStatus.EXPIRED,
                    attempts=entry.attempts,
                    updated_at=cutoff,
                    error=entry.error,
                    public_path=entry.public_path,
                )
                changed = True
        if changed:
            self._write()

    def _write(self) -> None:
        """Persist all entries using an atomic file replacement."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(prefix=".announcements-", suffix=".tmp", dir=self.path.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(
                    {key: value.to_dict() for key, value in self._entries.items()},
                    handle,
                    ensure_ascii=False,
                    indent=2,
                )
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)
