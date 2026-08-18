from datetime import datetime
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


def test_invalid_source_keeps_existing_public_asset(tmp_path):
    manager = AssetManager(tmp_path / "generated", tmp_path / "public")
    playback = datetime(2026, 8, 18, 14, tzinfo=ZoneInfo("Europe/Berlin"))
    asset = manager.paths("wittstock", AnnouncementKind.FULL_HOUR, playback)
    asset.public_path.parent.mkdir(parents=True)
    asset.public_path.write_bytes(b"old audio")

    with pytest.raises(AssetPublicationError):
        manager.publish(tmp_path / "missing.mp3", asset)

    assert asset.public_path.read_bytes() == b"old audio"

