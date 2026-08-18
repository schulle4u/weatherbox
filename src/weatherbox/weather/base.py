"""Common interface for weather forecast providers."""

from __future__ import annotations

from typing import Protocol

from weatherbox.models import ForecastBundle, Location


class WeatherProvider(Protocol):
    """Interface for retrieving forecasts for a configured location."""

    def fetch(self, location: Location) -> ForecastBundle:
        """Fetch a forecast bundle for ``location``."""
        ...
