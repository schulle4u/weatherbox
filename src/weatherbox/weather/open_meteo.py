from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from weatherbox.errors import WeatherUnavailableError
from weatherbox.models import ForecastBundle, Location, WeatherData


HOURLY_FIELDS = (
    "temperature_2m", "apparent_temperature", "dew_point_2m", "relative_humidity_2m",
    "surface_pressure", "weather_code", "cloud_cover", "precipitation",
    "precipitation_probability", "wind_speed_10m", "wind_direction_10m", "wind_gusts_10m",
)


class OpenMeteoProvider:
    def __init__(self, endpoint: str, timeout_seconds: float = 15) -> None:
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds

    def fetch(self, location: Location) -> ForecastBundle:
        query = urlencode(
            {
                "latitude": location.latitude,
                "longitude": location.longitude,
                "hourly": ",".join(HOURLY_FIELDS),
                "daily": "sunrise,sunset",
                "timezone": location.timezone,
                "forecast_days": 2,
                "wind_speed_unit": "kmh",
            }
        )
        request = Request(f"{self.endpoint}?{query}", headers={"User-Agent": "weatherbox/0.1"})
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.load(response)
        except (OSError, HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise WeatherUnavailableError(f"Open-Meteo-Abruf fehlgeschlagen: {exc}") from exc
        try:
            return self._parse(payload, location.timezone)
        except (KeyError, TypeError, ValueError, IndexError, ZoneInfoNotFoundError) as exc:
            raise WeatherUnavailableError(f"Ungültige Open-Meteo-Antwort: {exc}") from exc

    @staticmethod
    def _parse(payload: dict[str, Any], timezone: str) -> ForecastBundle:
        zone = ZoneInfo(timezone)
        hourly = payload["hourly"]
        daily = payload.get("daily", {})
        sunrise_by_date: dict[str, datetime] = {}
        sunset_by_date: dict[str, datetime] = {}
        for index, date in enumerate(daily.get("time", [])):
            sunrise = daily.get("sunrise", [])[index]
            sunset = daily.get("sunset", [])[index]
            sunrise_by_date[date] = _local_datetime(sunrise, zone)
            sunset_by_date[date] = _local_datetime(sunset, zone)

        forecasts: list[WeatherData] = []
        times = hourly["time"]
        for index, value in enumerate(times):
            forecast_at = _local_datetime(value, zone)
            values = {field: _at(hourly, field, index) for field in HOURLY_FIELDS}
            forecasts.append(
                WeatherData(
                    forecast_at=forecast_at,
                    temperature=values["temperature_2m"],
                    apparent_temperature=values["apparent_temperature"],
                    dew_point=values["dew_point_2m"],
                    humidity=values["relative_humidity_2m"],
                    pressure=values["surface_pressure"],
                    weather_code=int(values["weather_code"]) if values["weather_code"] is not None else None,
                    cloud_cover=values["cloud_cover"],
                    precipitation=values["precipitation"],
                    precipitation_probability=values["precipitation_probability"],
                    wind_speed=values["wind_speed_10m"],
                    wind_direction=values["wind_direction_10m"],
                    wind_gusts=values["wind_gusts_10m"],
                    sunrise=sunrise_by_date.get(forecast_at.date().isoformat()),
                    sunset=sunset_by_date.get(forecast_at.date().isoformat()),
                )
            )
        return ForecastBundle(fetched_at=datetime.now().astimezone(), forecasts=tuple(forecasts))


def _local_datetime(value: str, zone: ZoneInfo) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed.replace(tzinfo=zone) if parsed.tzinfo is None else parsed.astimezone(zone)


def _at(hourly: dict[str, list[Any]], field: str, index: int) -> float | None:
    values = hourly.get(field, [])
    if index >= len(values) or values[index] is None:
        return None
    return float(values[index])
