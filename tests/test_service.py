import os
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

from conftest import write_test_config
from weatherbox.config import load_config
from weatherbox.models import AnnouncementKind, ForecastBundle
from weatherbox.service import WeatherboxService
from weatherbox.weather.merged import MergedWeatherProvider


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
        self.outputs = []

    def process(self, speech_path, output_path, jingles=None):
        if self.fails:
            raise RuntimeError("ffmpeg failed")
        self.outputs.append(output_path)
        output_path.write_bytes(b"valid fake mp3")


def test_provider_fallback_with_missing_values_publishes_audio_and_html(tmp_path, now, weather):
    path = write_test_config(tmp_path / "config.yaml")
    path.write_text(
        path.read_text(encoding="utf-8")
        .replace("audio:\n", "text:\n  enabled: true\naudio:\n", 1)
        .replace(
            "{temperature} Grad.",
            "{temperature} Grad. Gefühlt {apparent_temperature} Grad. "
            "Regenwahrscheinlichkeit: {precipitation_probability} Prozent.",
        ),
        encoding="utf-8",
    )
    config = load_config(path)
    provider = MergedWeatherProvider(
        (
            ("open-meteo", FakeWeatherProvider(now, weather, ("wittstock",))),
            ("dwd", FakeWeatherProvider(now, replace(
                weather, apparent_temperature=None, precipitation_probability=None,
            ))),
        ),
        default_priority=("open-meteo", "dwd"),
        field_priority={},
    )
    tts = FakeTTS()
    service = WeatherboxService(
        config, weather_provider=provider, tts_provider=tts,
        audio_pipeline=FakeAudio(), now_fn=lambda: now,
    )
    item = service.manual_items(
        (config.locations["wittstock"],), (AnnouncementKind.FULL_HOUR,)
    )[0]

    asset = service.generate(item)

    assert asset.public_path.read_bytes() == b"valid fake mp3"
    assert tts.texts == ["Es ist vierzehn Uhr in Wittstock. 18,2 Grad."]
    html = (config.output.public_dir / "wittstock/full-hour.html").read_text(encoding="utf-8")
    assert "Es ist 14:00 in Wittstock. 18,2 Grad." in html
    assert "Gefühlt" not in html
    assert "Regenwahrscheinlichkeit" not in html


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


def test_generation_publishes_every_configured_audio_format(tmp_path, now, weather):
    path = write_test_config(tmp_path / "config.yaml")
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "  output:\n", "  output:\n    format: mp3, flac, opus\n", 1
        ),
        encoding="utf-8",
    )
    config = load_config(path)
    audio = FakeAudio()
    service = WeatherboxService(
        config,
        weather_provider=FakeWeatherProvider(now, weather),
        tts_provider=FakeTTS(),
        audio_pipeline=audio,
        now_fn=lambda: now,
    )
    item = service.manual_items(
        (config.locations["wittstock"],), (AnnouncementKind.FULL_HOUR,)
    )[0]

    service.generate(item)

    public = config.output.public_dir / "wittstock"
    generated = config.output.generated_dir / "wittstock" / "2026-08-18"
    assert {path.name for path in public.iterdir()} == {
        "full-hour.mp3", "full-hour.flac", "full-hour.opus"
    }
    assert {path.name for path in generated.iterdir()} == {
        "14-00-full.mp3", "14-00-full.flac", "14-00-full.opus"
    }
    assert tuple(path.suffix for path in audio.outputs) == (".mp3", ".flac", ".opus")


def test_generation_publishes_readable_html_alongside_audio(tmp_path, now, weather):
    path = write_test_config(tmp_path / "config.yaml")
    template = tmp_path / "weather.html"
    template.write_text(
        '<html lang="{language}"><title>{location}</title><p>{message}</p>'
        '<small>{date} {time} {kind} {year}</small></html>',
        encoding="utf-8",
    )
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "audio:\n", "text:\n  enabled: true\n  template: weather.html\naudio:\n", 1
        ),
        encoding="utf-8",
    )
    config = load_config(path)
    tts = FakeTTS()
    service = WeatherboxService(
        config,
        weather_provider=FakeWeatherProvider(now, weather),
        tts_provider=tts,
        audio_pipeline=FakeAudio(),
        now_fn=lambda: now,
    )
    item = service.manual_items(
        (config.locations["wittstock"],), (AnnouncementKind.FULL_HOUR,)
    )[0]

    service.generate(item)

    public_html = config.output.public_dir / "wittstock/full-hour.html"
    versioned_html = config.output.generated_dir / "wittstock/2026-08-18/14-00-full.html"
    assert public_html.is_file()
    assert versioned_html.read_text(encoding="utf-8") == public_html.read_text(encoding="utf-8")
    assert "Es ist 14:00 in Wittstock. 18,2 Grad." in public_html.read_text(encoding="utf-8")
    assert "18.08.2026 14:00 full_hour 2026" in public_html.read_text(encoding="utf-8")
    assert tts.texts == ["Es ist vierzehn Uhr in Wittstock. 18,2 Grad."]


def test_text_only_generation_does_not_invoke_tts_or_audio(tmp_path, now, weather):
    path = write_test_config(tmp_path / "config.yaml")
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "audio:\n", "text:\n  enabled: true\naudio:\n  enabled: false\n", 1
        ),
        encoding="utf-8",
    )
    config = load_config(path)

    class UnexpectedTTS(FakeTTS):
        def synthesize(self, text, output_path):
            raise AssertionError("TTS must not run for text-only output")

    class UnexpectedAudio(FakeAudio):
        def process(self, speech_path, output_path, jingles=None):
            raise AssertionError("Audio processing must not run for text-only output")

    service = WeatherboxService(
        config,
        weather_provider=FakeWeatherProvider(now, weather),
        tts_provider=UnexpectedTTS(),
        audio_pipeline=UnexpectedAudio(),
        now_fn=lambda: now,
    )
    item = service.manual_items(
        (config.locations["wittstock"],), (AnnouncementKind.FULL_HOUR,)
    )[0]

    asset = service.generate(item)

    assert asset.public_path.name == "full-hour.html"
    assert "Es ist 14:00" in asset.public_path.read_text(encoding="utf-8")


def test_text_asset_escapes_location_and_message(tmp_path, now, weather):
    locations = """
  coast:
    name: Rügen & Meer
    latitude: 54.4
    longitude: 13.4
    timezone: Europe/Berlin
    announcements:
      full_hour:
        template: 'Wetter <stark> für {location}: {temperature} Grad.'
"""
    path = write_test_config(tmp_path / "config.yaml", locations)
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "audio:\n", "text:\n  enabled: true\naudio:\n  enabled: false\n", 1
        ),
        encoding="utf-8",
    )
    config = load_config(path)
    service = WeatherboxService(
        config,
        weather_provider=FakeWeatherProvider(now, weather),
        now_fn=lambda: now,
    )
    item = service.manual_items(
        (config.locations["coast"],), (AnnouncementKind.FULL_HOUR,)
    )[0]

    html = service.generate(item).public_path.read_text(encoding="utf-8")

    assert "Rügen &amp; Meer" in html
    assert "Wetter &lt;stark&gt;" in html


def test_format_failure_does_not_replace_any_existing_asset(tmp_path, now, weather):
    path = write_test_config(tmp_path / "config.yaml")
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "  output:\n", "  output:\n    format: mp3, opus\n", 1
        ),
        encoding="utf-8",
    )
    config = load_config(path)
    public = config.output.public_dir / "wittstock"
    public.mkdir(parents=True)
    for name in ("full-hour.mp3", "full-hour.opus"):
        (public / name).write_bytes(b"old audio")

    class FailingOpusAudio(FakeAudio):
        def process(self, speech_path, output_path, jingles=None):
            if output_path.suffix == ".opus":
                raise RuntimeError("opus encoding failed")
            super().process(speech_path, output_path, jingles)

    service = WeatherboxService(
        config,
        weather_provider=FakeWeatherProvider(now, weather),
        tts_provider=FakeTTS(),
        audio_pipeline=FailingOpusAudio(),
        now_fn=lambda: now,
    )
    item = service.manual_items(
        (config.locations["wittstock"],), (AnnouncementKind.FULL_HOUR,)
    )[0]

    result = service.generate_many((item,))

    assert result[item.key].startswith("ERROR:")
    assert (public / "full-hour.mp3").read_bytes() == b"old audio"
    assert (public / "full-hour.opus").read_bytes() == b"old audio"


def test_run_due_cleans_generated_assets_when_retention_is_configured(
    tmp_path, now, weather
):
    config = load_config(write_test_config(tmp_path / "config.yaml"))
    config = replace(
        config,
        output=replace(config.output, generated_retention_days=30),
    )
    run_at = now.replace(minute=1)
    expired = config.output.generated_dir / "wittstock" / "2026-07-01" / "old.mp3"
    expired.parent.mkdir(parents=True)
    expired.write_bytes(b"old audio")
    expired_timestamp = (run_at - timedelta(days=31)).timestamp()
    os.utime(expired, (expired_timestamp, expired_timestamp))
    service = WeatherboxService(
        config,
        weather_provider=FakeWeatherProvider(run_at, weather),
        tts_provider=FakeTTS(),
        audio_pipeline=FakeAudio(),
        now_fn=lambda: run_at,
    )

    assert service.run_due() == {}
    assert not expired.exists()


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


def test_freshly_fetched_cache_is_checked_against_time_after_request(
    tmp_path, now, weather
):
    config = load_config(write_test_config(tmp_path / "config.yaml"))
    fetched_at = now + timedelta(seconds=2)
    clock = iter((now, now + timedelta(seconds=3)))
    service = WeatherboxService(
        config,
        weather_provider=FakeWeatherProvider(fetched_at, weather),
        tts_provider=FakeTTS(),
        audio_pipeline=FakeAudio(),
        now_fn=lambda: next(clock),
    )

    result = service.get_weather(config.locations["wittstock"], weather.forecast_at)

    assert result == weather


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
