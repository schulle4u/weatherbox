import os
import stat
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from weatherbox.assets import AssetManager
from weatherbox.errors import AssetPublicationError
from weatherbox.models import AnnouncementKind


def test_versioned_and_public_asset_are_published(tmp_path):
    manager = AssetManager(tmp_path / "generated", tmp_path / "public")
    source = tmp_path / "source.mp3"
    source.write_bytes(b"new audio")
    playback = datetime(2026, 8, 18, 14, tzinfo=ZoneInfo("Europe/Berlin"))
    asset = manager.paths("wittstock", AnnouncementKind.FULL_HOUR, playback)

    manager.publish(source, asset)

    assert asset.versioned_path.read_bytes() == b"new audio"
    assert asset.public_path.read_bytes() == b"new audio"
    assert asset.public_path.name == "full-hour.mp3"


def test_paths_use_requested_audio_extension(tmp_path):
    manager = AssetManager(tmp_path / "generated", tmp_path / "public")
    playback = datetime(2026, 8, 18, 14, tzinfo=ZoneInfo("Europe/Berlin"))

    asset = manager.paths(
        "wittstock", AnnouncementKind.FULL_HOUR, playback, "flac"
    )

    assert asset.versioned_path.name == "14-00-full.flac"
    assert asset.public_path.name == "full-hour.flac"


@pytest.mark.skipif(os.name != "posix", reason="POSIX file modes are required")
def test_public_asset_is_world_readable(tmp_path):
    manager = AssetManager(tmp_path / "generated", tmp_path / "public")
    source = tmp_path / "source.mp3"
    source.write_bytes(b"new audio")
    playback = datetime(2026, 8, 18, 14, tzinfo=ZoneInfo("Europe/Berlin"))
    asset = manager.paths("wittstock", AnnouncementKind.FULL_HOUR, playback)

    manager.publish(source, asset)

    assert stat.S_IMODE(asset.public_path.stat().st_mode) == 0o644
    assert stat.S_IMODE(asset.versioned_path.stat().st_mode) == 0o600


def test_invalid_source_keeps_existing_public_asset(tmp_path):
    manager = AssetManager(tmp_path / "generated", tmp_path / "public")
    playback = datetime(2026, 8, 18, 14, tzinfo=ZoneInfo("Europe/Berlin"))
    asset = manager.paths("wittstock", AnnouncementKind.FULL_HOUR, playback)
    asset.public_path.parent.mkdir(parents=True)
    asset.public_path.write_bytes(b"old audio")

    with pytest.raises(AssetPublicationError):
        manager.publish(tmp_path / "missing.mp3", asset)

    assert asset.public_path.read_bytes() == b"old audio"


def test_cleanup_deletes_expired_files_and_empty_directories(tmp_path):
    generated = tmp_path / "generated"
    manager = AssetManager(generated, tmp_path / "public")
    now = datetime(2026, 8, 18, 14, tzinfo=ZoneInfo("Europe/Berlin"))
    expired = generated / "wittstock" / "2026-07-01" / "14-00-full.mp3"
    current = generated / "wittstock" / "2026-08-18" / "14-00-full.mp3"
    expired.parent.mkdir(parents=True)
    current.parent.mkdir(parents=True)
    expired.write_bytes(b"old audio")
    current.write_bytes(b"current audio")
    expired_timestamp = (now - timedelta(days=31)).timestamp()
    os.utime(expired, (expired_timestamp, expired_timestamp))

    result = manager.cleanup(30, now=now)

    assert result == {
        "deleted_files": 1,
        "deleted_directories": 1,
        "freed_bytes": len(b"old audio"),
    }
    assert not expired.exists()
    assert not expired.parent.exists()
    assert current.read_bytes() == b"current audio"


def test_cleanup_does_not_touch_public_assets(tmp_path):
    generated = tmp_path / "generated"
    public = tmp_path / "public" / "wittstock" / "full-hour.mp3"
    manager = AssetManager(generated, tmp_path / "public")
    now = datetime(2026, 8, 18, 14, tzinfo=ZoneInfo("Europe/Berlin"))
    public.parent.mkdir(parents=True)
    public.write_bytes(b"published audio")
    old_timestamp = (now - timedelta(days=31)).timestamp()
    os.utime(public, (old_timestamp, old_timestamp))

    result = manager.cleanup(30, now=now)

    assert result["deleted_files"] == 0
    assert public.read_bytes() == b"published audio"
