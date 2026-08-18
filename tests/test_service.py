from datetime import timedelta
from pathlib import Path

from conftest import write_test_config
from weatherbox.config import load_config
from weatherbox.models import AnnouncementKind, ForecastBundle
from weatherbox.service import WeatherboxService


class FakeWeatherProvider:
    def __init__(self, now, weather, failing_locations=()):
        self.now = now
        self.weather = weather
        self.failing_locations = set(failing_locations)

    def fetch(self, location):
        if location.id in self.failing_locations:
            raise OSError("offline")
        return ForecastBundle(self.now, (self.weather,))


class FakeTTS:
    last_provider = "fake"

    def __init__(self):
        self.texts = []

    def synthesize(self, text: str, output_path: Path) -> None:
        self.texts.append(text)
        output_path.write_bytes(b"RIFF" + b"0" * 44)


class FakeAudio:
    def __init__(self, fails=False):
        self.fails = fails

    def process(self, speech_path, output_path, jingle_path=None):
        if self.fails:
            raise RuntimeError("ffmpeg failed")
        output_path.write_bytes(b"valid fake mp3")


def test_end_to_end_generation_publishes_both_asset_paths(tmp_path, now, weather):
    config = load_config(write_test_config(tmp_path / "config.yaml"))
    service = WeatherboxService(
        config,
        weather_provider=FakeWeatherProvider(now, weather),
        tts_provider=FakeTTS(),
        audio_pipeline=FakeAudio(),
        now_fn=lambda: now,
    )
    item = service.manual_items(
        (config.locations["wittstock"],), (AnnouncementKind.FULL_HOUR,)
    )[0]
    asset = service.generate(item)
    assert asset.public_path.read_bytes() == b"valid fake mp3"
    assert asset.versioned_path.is_file()


def test_stale_cache_and_provider_failure_keeps_existing_asset(tmp_path, now, weather):
    config = load_config(write_test_config(tmp_path / "config.yaml"))
    good = WeatherboxService(
        config,
        weather_provider=FakeWeatherProvider(now, weather),
        tts_provider=FakeTTS(),
        audio_pipeline=FakeAudio(),
        now_fn=lambda: now,
    )
    item = good.manual_items((config.locations["wittstock"],), (AnnouncementKind.FULL_HOUR,))[0]
    asset = good.generate(item)
    original = asset.public_path.read_bytes()

    stale_now = now + timedelta(minutes=75)
    failing = WeatherboxService(
        config,
        weather_provider=FakeWeatherProvider(stale_now, weather, {"wittstock"}),
        tts_provider=FakeTTS(),
        audio_pipeline=FakeAudio(),
        now_fn=lambda: stale_now,
    )
    failed_item = failing.manual_items((config.locations["wittstock"],), (AnnouncementKind.FULL_HOUR,))[0]
    result = failing.generate_many((failed_item,))
    assert result[failed_item.key].startswith("ERROR:")
    assert asset.public_path.read_bytes() == original


def test_provider_failure_uses_cache_within_maximum_age(tmp_path, now, weather):
    config = load_config(write_test_config(tmp_path / "config.yaml"))
    warmup = WeatherboxService(
        config,
        weather_provider=FakeWeatherProvider(now, weather),
        tts_provider=FakeTTS(),
        audio_pipeline=FakeAudio(),
        now_fn=lambda: now,
    )
    warmup.update_weather()

    cached_now = now + timedelta(minutes=40)
    offline = WeatherboxService(
        config,
        weather_provider=FakeWeatherProvider(cached_now, weather, {"wittstock"}),
        tts_provider=FakeTTS(),
        audio_pipeline=FakeAudio(),
        now_fn=lambda: cached_now,
    )
    item = offline.manual_items(
        (config.locations["wittstock"],), (AnnouncementKind.FULL_HOUR,)
    )[0]
    result = offline.generate_many((item,))
    assert not result[item.key].startswith("ERROR:")


def test_ffmpeg_failure_keeps_existing_asset(tmp_path, now, weather):
    config = load_config(write_test_config(tmp_path / "config.yaml"))
    working = WeatherboxService(
        config,
        weather_provider=FakeWeatherProvider(now, weather),
        tts_provider=FakeTTS(),
        audio_pipeline=FakeAudio(),
        now_fn=lambda: now,
    )
    item = working.manual_items(
        (config.locations["wittstock"],), (AnnouncementKind.FULL_HOUR,)
    )[0]
    asset = working.generate(item)
    original = asset.public_path.read_bytes()

    broken = WeatherboxService(
        config,
        weather_provider=FakeWeatherProvider(now, weather),
        tts_provider=FakeTTS(),
        audio_pipeline=FakeAudio(fails=True),
        now_fn=lambda: now,
    )
    result = broken.generate_many((item,))
    assert result[item.key].startswith("ERROR:")
    assert asset.public_path.read_bytes() == original


def test_one_location_failure_does_not_block_another(tmp_path, now, weather):
    locations = """
  broken:
    name: Broken
    latitude: 53.0
    longitude: 12.0
    timezone: Europe/Berlin
  working:
    name: Working
    latitude: 52.0
    longitude: 13.0
    timezone: Europe/Berlin
"""
    config = load_config(write_test_config(tmp_path / "config.yaml", locations))
    service = WeatherboxService(
        config,
        weather_provider=FakeWeatherProvider(now, weather, {"broken"}),
        tts_provider=FakeTTS(),
        audio_pipeline=FakeAudio(),
        now_fn=lambda: now,
    )
    items = service.manual_items(config.enabled_locations, (AnnouncementKind.FULL_HOUR,))
    results = service.generate_many(items)
    assert next(value for key, value in results.items() if key.startswith("broken:")).startswith("ERROR:")
    assert not next(value for key, value in results.items() if key.startswith("working:")).startswith("ERROR:")


def test_location_language_controls_generated_announcement(tmp_path, now, weather):
    locations = """
  london:
    name: London
    latitude: 51.51
    longitude: -0.13
    timezone: Europe/London
    language: en
    announcements:
      full_hour:
        template: "It is {time} in {location}. It is {weather_description} and {temperature} degrees."
"""
    config = load_config(write_test_config(tmp_path / "config.yaml", locations))
    tts = FakeTTS()
    service = WeatherboxService(
        config,
        weather_provider=FakeWeatherProvider(now, weather),
        tts_provider=tts,
        audio_pipeline=FakeAudio(),
        now_fn=lambda: now,
    )
    item = service.manual_items(
        config.enabled_locations, (AnnouncementKind.FULL_HOUR,)
    )[0]
    service.generate(item)
    assert tts.texts == [
        "It is thirteen o'clock in London. It is partly cloudy and 18.2 degrees."
    ]
