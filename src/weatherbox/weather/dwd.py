"""Retrieve forecasts and official warnings from the DWD WarnWetter API."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from weatherbox.errors import WeatherUnavailableError
from weatherbox.models import ForecastBundle, Location, WeatherData, WeatherWarning


# The DWD ``icon`` values use the present-weather code table. Weatherbox uses
# WMO codes internally so all providers share the existing localized terms.
DWD_TO_WMO_CODE = {
    1: 0, 2: 1, 3: 2, 4: 3, 5: 45, 6: 48,
    7: 61, 8: 63, 9: 65, 10: 66, 11: 67, 12: 68, 13: 69,
    14: 71, 15: 73, 16: 75, 17: 79, 18: 80, 19: 82,
    20: 83, 21: 84, 22: 85, 23: 86, 24: 87, 25: 88,
    26: 95, 27: 95, 28: 95, 29: 96, 30: 99,
}


class DWDProvider:
    """Fetch station forecasts and station-related warnings from DWD."""

    name = "dwd"

    def __init__(self, endpoint: str, timeout_seconds: float = 15) -> None:
        """Initialize the provider with an endpoint and request timeout."""
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds

    def fetch(self, location: Location) -> ForecastBundle:
        """Fetch and parse the forecast for a location's configured station."""
        if not location.dwd_station_id:
            raise WeatherUnavailableError(
                f"No DWD station ID configured for location {location.id}"
            )
        separator = "&" if "?" in self.endpoint else "?"
        query = urlencode({"stationIds": location.dwd_station_id})
        request = Request(
            f"{self.endpoint}{separator}{query}",
            headers={"User-Agent": "weatherbox/0.1"},
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.load(response)
        except (OSError, HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise WeatherUnavailableError(f"Fetching from DWD failed: {exc}") from exc
        try:
            return self._parse(payload, location.dwd_station_id, location.timezone)
        except (
            KeyError,
            TypeError,
            ValueError,
            IndexError,
            ZoneInfoNotFoundError,
        ) as exc:
            raise WeatherUnavailableError(f"Invalid DWD response: {exc}") from exc

    @staticmethod
    def _parse(
        payload: dict[str, Any], station_id: str, timezone: str
    ) -> ForecastBundle:
        """Convert a DWD station response into the internal forecast model."""
        zone = ZoneInfo(timezone)
        station = payload.get(station_id)
        if station is None:
            raise ValueError(
                f"DWD station '{station_id}' was not returned; "
                "stationOverviewExtended requires a WarnWetter/MOS station code, "
                "not a CDC station ID"
            )
        forecast = station["forecast1"]
        start = _timestamp(forecast["start"], zone)
        step = timedelta(milliseconds=int(forecast["timeStep"]))
        temperatures = _series(forecast.get("temperature"))
        if not temperatures:
            raise ValueError("forecast1.temperature is empty")

        warnings = tuple(_parse_warning(item, zone) for item in station.get("warnings", []))
        days = {
            str(item["dayDate"]): item
            for item in station.get("days", [])
            if isinstance(item, dict) and item.get("dayDate")
        }
        forecasts: list[WeatherData] = []
        for index in range(len(temperatures)):
            forecast_at = start + index * step
            day = days.get(forecast_at.date().isoformat(), {})
            icon = _at(forecast, "icon1h", index)
            if icon is None:
                icon = _at(forecast, "icon", index)
            dwd_code = int(icon) if icon is not None else None
            forecasts.append(
                WeatherData(
                    forecast_at=forecast_at,
                    temperature=_tenths_at(forecast, "temperature", index),
                    dew_point=_tenths_at(forecast, "dewPoint2m", index),
                    humidity=_tenths_at(forecast, "humidity", index),
                    pressure=_tenths_at(forecast, "surfacePressure", index),
                    weather_code=DWD_TO_WMO_CODE.get(dwd_code) if dwd_code else None,
                    precipitation=_tenths_at(forecast, "precipitationTotal", index),
                    wind_speed=_tenths_at_or_day(forecast, "windSpeed", index, day),
                    wind_direction=_tenths_at_or_day(
                        forecast, "windDirection", index, day
                    ),
                    wind_gusts=_tenths_at_or_day(forecast, "windGust", index, day),
                    sunrise=_optional_timestamp(day.get("sunrise"), zone),
                    sunset=_optional_timestamp(day.get("sunset"), zone),
                ).with_source("dwd")
            )
        return ForecastBundle(
            fetched_at=datetime.now().astimezone(),
            forecasts=tuple(forecasts),
            warnings=warnings,
        )


def _series(value: Any) -> list[Any]:
    """Return an API series, tolerating absent or JSON-encoded arrays."""
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def _at(data: dict[str, Any], field: str, index: int) -> float | None:
    """Return a numeric series item if present."""
    values = _series(data.get(field))
    if index >= len(values) or values[index] is None:
        return None
    return float(values[index])


def _tenths_at(data: dict[str, Any], field: str, index: int) -> float | None:
    """Return a DWD series item converted from tenths to its display unit."""
    value = _at(data, field, index)
    return value / 10 if value is not None else None


def _tenths_at_or_day(
    forecast: dict[str, Any], field: str, index: int, day: dict[str, Any]
) -> float | None:
    """Use hourly data when available, otherwise the corresponding daily value."""
    value = _tenths_at(forecast, field, index)
    if value is not None:
        return value
    daily = day.get(field)
    return float(daily) / 10 if daily is not None else None


def _timestamp(value: Any, zone: ZoneInfo) -> datetime:
    """Convert a DWD Unix timestamp in milliseconds to a local datetime."""
    numeric = float(value)
    seconds = numeric / 1000 if abs(numeric) >= 100_000_000_000 else numeric
    return datetime.fromtimestamp(seconds, tz=UTC).astimezone(zone)


def _optional_timestamp(value: Any, zone: ZoneInfo) -> datetime | None:
    """Convert an optional DWD Unix timestamp."""
    return _timestamp(value, zone) if value is not None else None


def _parse_warning(data: dict[str, Any], zone: ZoneInfo) -> WeatherWarning:
    """Parse one warning, accepting the headline spellings used by DWD payloads."""
    event = _clean_text(data.get("event"))
    headline = _clean_text(data.get("headline") or data.get("headLine")) or event
    if not headline:
        raise ValueError("warning has neither headline nor event")
    return WeatherWarning(
        level=int(data.get("level", 0)),
        event=event or headline,
        headline=headline,
        start=_timestamp(data["start"], zone),
        end=_optional_timestamp(data.get("end"), zone),
        description=_clean_text(data.get("descriptionText") or data.get("description")),
        instruction=_clean_text(data.get("instruction")),
        source="dwd",
    )


def _clean_text(value: Any) -> str | None:
    """Normalize optional API text for spoken output."""
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None
