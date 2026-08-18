from datetime import timedelta

from weatherbox.config import RetrySettings, SchedulerSettings
from weatherbox.models import AnnouncementKind, AnnouncementStatus
from weatherbox.scheduler import Scheduler
from weatherbox.state import StateStore


def test_only_full_hour_due_at_preparation_boundary(tmp_path, location, now):
    scheduler = Scheduler(
        SchedulerSettings(10, RetrySettings(60, 3)),
        StateStore(tmp_path / "state.json"),
    )
    due = scheduler.due((location,), now)
    assert [(item.location.id, item.kind, item.playback_at.minute) for item in due] == [
        ("wittstock", AnnouncementKind.FULL_HOUR, 0)
    ]


def test_published_item_is_not_repeated(tmp_path, location, now):
    state = StateStore(tmp_path / "state.json")
    scheduler = Scheduler(SchedulerSettings(10, RetrySettings(60, 3)), state)
    item = scheduler.due((location,), now)[0]
    state.set(item, AnnouncementStatus.PUBLISHED, now)
    assert scheduler.due((location,), now + timedelta(seconds=30)) == ()


def test_failed_item_retries_after_interval(tmp_path, location, now):
    state = StateStore(tmp_path / "state.json")
    scheduler = Scheduler(SchedulerSettings(10, RetrySettings(60, 3)), state)
    item = scheduler.due((location,), now)[0]
    state.set(item, AnnouncementStatus.GENERATING, now, increment_attempts=True)
    state.set(item, AnnouncementStatus.FAILED, now, error="test")
    assert scheduler.due((location,), now + timedelta(seconds=59)) == ()
    assert scheduler.due((location,), now + timedelta(seconds=60)) == (item,)


def test_multiple_locations_are_scheduled(tmp_path, location, now):
    second = location.__class__(
        id="berlin",
        name="Berlin",
        latitude=52.52,
        longitude=13.4,
        timezone=location.timezone,
        enabled=True,
        announcements=location.announcements,
        jingles=location.jingles,
    )
    scheduler = Scheduler(
        SchedulerSettings(10, RetrySettings(60, 3)), StateStore(tmp_path / "state.json")
    )
    assert {item.location.id for item in scheduler.due((location, second), now)} == {"wittstock", "berlin"}

