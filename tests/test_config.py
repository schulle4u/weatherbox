import pytest

from conftest import write_test_config
from weatherbox.config import load_config
from weatherbox.errors import ConfigurationError
from weatherbox.models import AnnouncementKind
from weatherbox.tts import EspeakProvider, GTTSProvider, PiperProvider, create_tts_provider
from weatherbox.weather import DWDProvider, MergedWeatherProvider, create_weather_provider


def test_load_config_and_resolve_paths(tmp_path):
    config = load_config(write_test_config(tmp_path / "config.yaml"))
    assert config.locations["wittstock"].name == "Wittstock"
    assert config.output.public_dir == tmp_path / "runtime/public"
    assert config.locations["wittstock"].announcements[AnnouncementKind.FULL_HOUR].enabled


def test_non_stereo_configuration_is_rejected(tmp_path):
    path = write_test_config(tmp_path / "config.yaml")
    path.write_text(path.read_text(encoding="utf-8").replace("channels: 2", "channels: 1"), encoding="utf-8")
    with pytest.raises(ConfigurationError, match="stereo"):
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
    with pytest.raises(ConfigurationError, match="location ID"):
        load_config(write_test_config(tmp_path / "config.yaml", locations))


def test_unknown_timezone_is_rejected(tmp_path):
    path = write_test_config(tmp_path / "config.yaml")
    path.write_text(
        path.read_text(encoding="utf-8").replace("Europe/Berlin", "Nowhere/Invalid"),
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError, match="time zone"):
        load_config(path)


def test_location_language_and_tts_voice_can_be_overridden(tmp_path):
    path = write_test_config(tmp_path / "config.yaml")
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "  piper:\n    model: model.onnx",
        "  piper:\n    model: model.onnx\n"
        "  languages:\n"
        "    en:\n"
        "      piper:\n"
        "        model: english.onnx\n"
        "      espeak-ng:\n"
        "        voice: en-gb",
    )
    text = text.replace("    timezone: Europe/Berlin", "    timezone: Europe/Berlin\n    language: en")
    path.write_text(text, encoding="utf-8")

    config = load_config(path)
    assert config.locations["wittstock"].language == "en"
    provider = create_tts_provider(config.tts, "en")
    assert isinstance(provider.primary, PiperProvider)
    assert provider.primary.settings.model == tmp_path / "english.onnx"
    assert isinstance(provider.fallback, EspeakProvider)
    assert provider.fallback.settings.voice == "en-gb"


def test_gtts_can_be_configured_with_language_override(tmp_path):
    path = write_test_config(tmp_path / "config.yaml")
    text = path.read_text(encoding="utf-8")
    text = text.replace("provider: piper", "provider: gtts")
    text = text.replace(
        "  piper:\n    model: model.onnx",
        "  gtts:\n"
        "    language: de\n"
        "    tld: de\n"
        "    timeout_seconds: 8.5\n"
        "  piper:\n"
        "    model: model.onnx\n"
        "  languages:\n"
        "    en:\n"
        "      gtts:\n"
        "        language: en\n"
        "        tld: co.uk",
    )
    path.write_text(text, encoding="utf-8")

    config = load_config(path)
    provider = create_tts_provider(config.tts, "en")

    assert isinstance(provider.primary, GTTSProvider)
    assert provider.primary.settings.language == "en"
    assert provider.primary.settings.tld == "co.uk"
    assert provider.primary.settings.timeout_seconds == 8.5


def test_gtts_uses_location_language_without_explicit_override(tmp_path):
    path = write_test_config(tmp_path / "config.yaml")
    text = path.read_text(encoding="utf-8").replace("provider: piper", "provider: gtts")
    path.write_text(text, encoding="utf-8")

    provider = create_tts_provider(load_config(path).tts, "en")

    assert isinstance(provider.primary, GTTSProvider)
    assert provider.primary.settings.language == "en"


def test_gtts_timeout_must_be_positive(tmp_path):
    path = write_test_config(tmp_path / "config.yaml")
    text = path.read_text(encoding="utf-8").replace(
        "  piper:\n    model: model.onnx",
        "  gtts:\n    timeout_seconds: 0\n  piper:\n    model: model.onnx",
    )
    path.write_text(text, encoding="utf-8")

    with pytest.raises(ConfigurationError, match="timeout_seconds"):
        load_config(path)


def test_dwd_weather_provider_and_station_are_configured(tmp_path):
    path = write_test_config(tmp_path / "config.yaml")
    text = path.read_text(encoding="utf-8")
    text = text.replace("weather:\n", "weather:\n  provider: dwd\n", 1).replace(
        "    timezone: Europe/Berlin",
        "    timezone: Europe/Berlin\n    weather:\n      dwd_station_id: G005",
    )
    path.write_text(text, encoding="utf-8")

    config = load_config(path)
    provider = create_weather_provider(config.weather)

    assert config.weather.provider == "dwd"
    assert config.locations["wittstock"].dwd_station_id == "G005"
    assert isinstance(provider, DWDProvider)
    assert provider.endpoint.endswith("stationOverviewExtended")


def test_dwd_provider_requires_station_for_enabled_location(tmp_path):
    path = write_test_config(tmp_path / "config.yaml")
    text = path.read_text(encoding="utf-8").replace(
        "weather:\n", "weather:\n  provider: dwd\n", 1
    )
    path.write_text(text, encoding="utf-8")

    with pytest.raises(ConfigurationError, match="dwd_station_id"):
        load_config(path)


def test_multiple_weather_providers_and_merge_priorities_are_configured(tmp_path):
    path = write_test_config(tmp_path / "config.yaml")
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "weather:\n",
        "weather:\n"
        "  providers:\n"
        "    open-meteo: {}\n"
        "    dwd: {}\n"
        "  merge:\n"
        "    tolerance_minutes: 20\n"
        "    default_priority: [open-meteo, dwd]\n"
        "    field_priority:\n"
        "      temperature: [dwd, open-meteo]\n"
        "      warnings: [dwd, open-meteo]\n",
        1,
    ).replace(
        "    timezone: Europe/Berlin",
        "    timezone: Europe/Berlin\n    weather:\n      dwd_station_id: G005",
    )
    path.write_text(text, encoding="utf-8")

    config = load_config(path)
    provider = create_weather_provider(config.weather)

    assert tuple(item.name for item in config.weather.providers) == (
        "open-meteo",
        "dwd",
    )
    assert config.weather.merge.tolerance_minutes == 20
    assert config.weather.merge.field_priority["temperature"] == (
        "dwd",
        "open-meteo",
    )
    assert isinstance(provider, MergedWeatherProvider)


def test_merge_priority_rejects_unconfigured_provider(tmp_path):
    path = write_test_config(tmp_path / "config.yaml")
    text = path.read_text(encoding="utf-8").replace(
        "weather:\n",
        "weather:\n"
        "  providers: [open-meteo]\n"
        "  merge:\n"
        "    default_priority: [dwd]\n",
        1,
    )
    path.write_text(text, encoding="utf-8")

    with pytest.raises(ConfigurationError, match="unconfigured providers"):
        load_config(path)
