from datetime import timedelta

import pytest

from weatherbox.errors import WeatherUnavailableError
from weatherbox.models import ForecastBundle, WeatherData, WeatherWarning
from weatherbox.weather.merged import MergedWeatherProvider


class FakeProvider:
    def __init__(self, bundle=None, error=None):
        self.bundle = bundle
        self.error = error

    def fetch(self, location):
        if self.error:
            raise self.error
        return self.bundle


def _bundle(now, weather, *, warnings=()):
    return ForecastBundle(now, (weather,), warnings)


def test_merge_uses_field_priority_fallback_and_time_tolerance(location, now):
    open_weather = WeatherData(
        forecast_at=now.replace(hour=14, minute=0),
        temperature=18,
        apparent_temperature=17,
        weather_code=2,
        precipitation_probability=30,
    ).with_source("open-meteo")
    dwd_weather = WeatherData(
        forecast_at=now.replace(hour=14, minute=15),
        temperature=19,
        humidity=70,
        weather_code=61,
    ).with_source("dwd")
    provider = MergedWeatherProvider(
        (
            ("open-meteo", FakeProvider(_bundle(now, open_weather))),
            ("dwd", FakeProvider(_bundle(now, dwd_weather))),
        ),
        default_priority=("open-meteo", "dwd"),
        field_priority={
            "temperature": ("dwd", "open-meteo"),
            "humidity": ("dwd", "open-meteo"),
        },
        tolerance_minutes=30,
    )

    merged = provider.fetch(location).forecasts[0]

    assert merged.forecast_at == open_weather.forecast_at
    assert merged.temperature == 19
    assert merged.source_for("temperature") == "dwd"
    assert merged.humidity == 70
    assert merged.apparent_temperature == 17
    assert merged.weather_code == 2
    assert merged.source_for("weather_code") == "open-meteo"


def test_merge_unions_and_deduplicates_warnings_by_priority(location, now, weather):
    warning = WeatherWarning(
        level=2,
        event="WIND",
        headline="Amtliche Warnung vor Windböen",
        start=now,
        end=now + timedelta(hours=2),
    )
    provider = MergedWeatherProvider(
        (
            ("open-meteo", FakeProvider(_bundle(now, weather, warnings=(warning,)))),
            ("dwd", FakeProvider(_bundle(now, weather, warnings=(warning,)))),
        ),
        default_priority=("open-meteo", "dwd"),
        field_priority={"warnings": ("dwd", "open-meteo")},
    )

    warnings = provider.fetch(location).warnings

    assert len(warnings) == 1
    assert warnings[0].source == "dwd"


def test_merge_tolerates_one_provider_failure(location, now, weather):
    provider = MergedWeatherProvider(
        (
            ("open-meteo", FakeProvider(_bundle(now, weather))),
            ("dwd", FakeProvider(error=OSError("offline"))),
        ),
        default_priority=("open-meteo", "dwd"),
        field_priority={},
    )

    result = provider.fetch(location)

    assert result.forecasts[0].temperature == weather.temperature


def test_merge_reports_all_provider_failures(location):
    provider = MergedWeatherProvider(
        (
            ("open-meteo", FakeProvider(error=OSError("offline"))),
            ("dwd", FakeProvider(error=TimeoutError("timeout"))),
        ),
        default_priority=("open-meteo", "dwd"),
        field_priority={},
    )

    with pytest.raises(WeatherUnavailableError, match="All weather providers failed"):
        provider.fetch(location)
