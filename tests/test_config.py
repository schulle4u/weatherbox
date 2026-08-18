import pytest

from conftest import write_test_config
from weatherbox.config import load_config
from weatherbox.errors import ConfigurationError
from weatherbox.models import AnnouncementKind


def test_load_config_and_resolve_paths(tmp_path):
    config = load_config(write_test_config(tmp_path / "config.yaml"))
    assert config.locations["wittstock"].name == "Wittstock"
    assert config.output.public_dir == tmp_path / "runtime/public"
    assert config.locations["wittstock"].announcements[AnnouncementKind.FULL_HOUR].enabled


def test_non_stereo_configuration_is_rejected(tmp_path):
    path = write_test_config(tmp_path / "config.yaml")
    path.write_text(path.read_text(encoding="utf-8").replace("channels: 2", "channels: 1"), encoding="utf-8")
    with pytest.raises(ConfigurationError, match="Stereo"):
        load_config(path)


def test_location_override_does_not_require_code_change(tmp_path):
    locations = """
  forest:
    name: Waldstation
    latitude: 51.0
    longitude: 10.0
    timezone: Europe/Berlin
    announcements:
      half_hour:
        template: "Sondertext für {location}: {temperature} Grad."
"""
    config = load_config(write_test_config(tmp_path / "config.yaml", locations))
    assert config.locations["forest"].announcements[AnnouncementKind.HALF_HOUR].template.startswith("Sondertext")


def test_unsafe_location_id_is_rejected(tmp_path):
    locations = """
  ../outside:
    name: Unsicher
    latitude: 51.0
    longitude: 10.0
    timezone: Europe/Berlin
"""
    with pytest.raises(ConfigurationError, match="Standort-ID"):
        load_config(write_test_config(tmp_path / "config.yaml", locations))


def test_unknown_timezone_is_rejected(tmp_path):
    path = write_test_config(tmp_path / "config.yaml")
    path.write_text(
        path.read_text(encoding="utf-8").replace("Europe/Berlin", "Nowhere/Invalid"),
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError, match="Zeitzone"):
        load_config(path)
