from __future__ import annotations

from typing import Protocol

from weatherbox.models import ForecastBundle, Location


class WeatherProvider(Protocol):
    def fetch(self, location: Location) -> ForecastBundle: ...

