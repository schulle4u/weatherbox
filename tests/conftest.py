from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from weatherbox.models import AnnouncementKind, AnnouncementSpec, Location, WeatherData
from weatherbox.localization import builtin_language


@pytest.fixture
def berlin() -> ZoneInfo:
    return ZoneInfo("Europe/Berlin")


@pytest.fixture
def now(berlin: ZoneInfo) -> datetime:
    return datetime(2026, 8, 18, 13, 50, tzinfo=berlin)


@pytest.fixture
def location() -> Location:
    return Location(
        id="wittstock",
        name="Wittstock",
        latitude=53.16,
        longitude=12.48,
        timezone="Europe/Berlin",
        enabled=True,
        announcements={
            AnnouncementKind.HALF_HOUR: AnnouncementSpec(True, "Es ist {time}. {temperature} Grad."),
            AnnouncementKind.FULL_HOUR: AnnouncementSpec(
                True, "Es ist {time} in {location}. {weather_description}, {temperature} Grad."
            ),
        },
        jingles={AnnouncementKind.HALF_HOUR: None, AnnouncementKind.FULL_HOUR: None},
    )


@pytest.fixture
def weather(now: datetime) -> WeatherData:
    return WeatherData(
        forecast_at=now.replace(hour=14, minute=0),
        temperature=18.2,
        apparent_temperature=17.5,
        dew_point=12.1,
        humidity=71,
        pressure=1013.2,
        weather_code=2,
        cloud_cover=42,
        precipitation=0,
        precipitation_probability=10,
        wind_speed=12.4,
        wind_direction=225,
        wind_gusts=21,
        sunrise=now.replace(hour=5, minute=48),
        sunset=now.replace(hour=20, minute=28),
    )


@pytest.fixture
def german_formatter():
    return builtin_language("de")


def write_test_config(path: Path, locations: str = "") -> Path:
    if not locations:
        locations = """
  wittstock:
    name: Wittstock
    latitude: 53.16
    longitude: 12.48
    timezone: Europe/Berlin
    enabled: true
"""
    text = f"""
weather:
  providers:
    open-meteo: {{}}
  update_interval_minutes: 30
  max_cache_age_minutes: 60
scheduler:
  preparation_minutes: 10
  retry:
    interval_seconds: 60
    max_attempts: 3
tts:
  provider: piper
  fallback_provider: espeak-ng
  piper:
    model: model.onnx
audio:
  loudness:
    enabled: true
  output:
    sample_rate: 48000
    channels: 2
    bitrate: 192k
output:
  cache_dir: runtime/cache
  generated_dir: runtime/generated
  public_dir: runtime/public
  state_dir: runtime/state
announcements:
  half_hour:
    enabled: true
    template: "Es ist {{time}}. {{temperature}} Grad."
  full_hour:
    enabled: true
    template: "Es ist {{time}} in {{location}}. {{temperature}} Grad."
locations:
{locations}
"""
    path.write_text(text, encoding="utf-8")
    return path
