from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from weatherbox.errors import WeatherUnavailableError
from weatherbox.models import AnnouncementKind, AnnouncementSpec, Location
from weatherbox.weather.dwd import DWDProvider


def _location(station_id: str | None = "G005") -> Location:
    return Location(
        id="wittstock",
        name="Wittstock",
        latitude=53.16,
        longitude=12.48,
        timezone="Europe/Berlin",
        enabled=True,
        announcements={
            AnnouncementKind.HALF_HOUR: AnnouncementSpec(True, "{temperature}"),
            AnnouncementKind.FULL_HOUR: AnnouncementSpec(True, "{temperature}"),
        },
        dwd_station_id=station_id,
    )


def test_dwd_payload_maps_forecast_units_daily_values_and_warning():
    payload = {
        "G005": {
            "forecast1": {
                "start": 1787040000000,
                "timeStep": 3600000,
                "temperature": [182, 190],
                "dewPoint2m": [121, 125],
                "humidity": [710, 680],
                "surfacePressure": [10132, 10128],
                "precipitationTotal": [0, 4],
                "icon1h": [3, 7],
                "windSpeed": None,
            },
            "days": [
                {
                    "dayDate": "2026-08-18",
                    "windSpeed": 124,
                    "windDirection": 2250,
                    "windGust": 210,
                    "sunrise": 1787024880000,
                    "sunset": 1787077680000,
                }
            ],
            "warnings": [
                {
                    "level": 2,
                    "event": "STARKES GEWITTER",
                    "headLine": "Amtliche Warnung vor starkem Gewitter",
                    "descriptionText": "Es treten Gewitter auf.",
                    "instruction": "Aufenthalt im Freien vermeiden.",
                    "start": 1787040000000,
                    "end": 1787047200000,
                }
            ],
        }
    }

    bundle = DWDProvider._parse(payload, "G005", "Europe/Berlin")
    first, second = bundle.forecasts

    assert first.forecast_at == datetime(
        2026, 8, 18, 10, 0, tzinfo=ZoneInfo("Europe/Berlin")
    )
    assert first.temperature == 18.2
    assert first.humidity == 71
    assert first.pressure == 1013.2
    assert first.weather_code == 2
    assert first.wind_speed == 12.4
    assert first.wind_direction == 225
    assert first.sunrise is not None
    assert second.precipitation == 0.4
    assert second.weather_code == 61
    assert bundle.warnings[0].level == 2
    assert bundle.warnings[0].headline.startswith("Amtliche Warnung")
    assert bundle.for_time(first.forecast_at).warnings == bundle.warnings


def test_dwd_payload_requires_requested_station():
    with pytest.raises(ValueError, match="WarnWetter/MOS station code"):
        DWDProvider._parse({}, "missing", "Europe/Berlin")


def test_dwd_fetch_requires_station_id():
    provider = DWDProvider("https://example.invalid")
    with pytest.raises(WeatherUnavailableError, match="station ID"):
        provider.fetch(_location(None))
