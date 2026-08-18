"""Determine which configured announcements are ready for generation."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from weatherbox.config import SchedulerSettings
from weatherbox.models import AnnouncementKind, AnnouncementStatus, Location, ScheduledAnnouncement
from weatherbox.state import StateStore


class Scheduler:
    """Select due announcements according to preparation and retry settings."""

    def __init__(self, settings: SchedulerSettings, state: StateStore) -> None:
        """Initialize the scheduler with its policy and persistent state."""
        self.settings = settings
        self.state = state

    def due(self, locations: tuple[Location, ...], now: datetime) -> tuple[ScheduledAnnouncement, ...]:
        """Return announcements due within the configured preparation window."""
        due: list[ScheduledAnnouncement] = []
        horizon = timedelta(minutes=self.settings.preparation_minutes)
        for location in locations:
            local_now = now.astimezone(ZoneInfo(location.timezone))
            for kind, spec in location.announcements.items():
                if not spec.enabled:
                    continue
                playback_at = next_playback(local_now, kind)
                if not timedelta(0) <= playback_at - local_now <= horizon:
                    continue
                item = ScheduledAnnouncement(location=location, kind=kind, playback_at=playback_at)
                if self._may_attempt(item, now):
                    due.append(item)
                    if self.state.get(item) is None:
                        self.state.set(item, AnnouncementStatus.SCHEDULED, now)
        return tuple(sorted(due, key=lambda item: (item.playback_at, item.location.id, item.kind.value)))

    def _may_attempt(self, item: ScheduledAnnouncement, now: datetime) -> bool:
        """Return whether state and retry policy permit another attempt."""
        entry = self.state.get(item)
        if entry is None:
            return True
        if entry.status in {AnnouncementStatus.PUBLISHED, AnnouncementStatus.GENERATING, AnnouncementStatus.EXPIRED}:
            return False
        if entry.status is AnnouncementStatus.FAILED:
            if entry.attempts >= self.settings.retry.max_attempts:
                return False
            elapsed = now - entry.updated_at.astimezone(now.tzinfo)
            return elapsed >= timedelta(seconds=self.settings.retry.interval_seconds)
        return True


def next_playback(now: datetime, kind: AnnouncementKind) -> datetime:
    """Return the next half-hour or full-hour playback time at or after ``now``."""
    if kind is AnnouncementKind.FULL_HOUR:
        candidate = now.replace(minute=0, second=0, microsecond=0)
        if now > candidate:
            candidate += timedelta(hours=1)
        return candidate
    candidate = now.replace(minute=30, second=0, microsecond=0)
    if now > candidate:
        candidate += timedelta(hours=1)
    return candidate
