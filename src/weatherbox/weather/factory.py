"""Create the configured weather provider."""

from __future__ import annotations

from typing import TYPE_CHECKING

from weatherbox.weather.base import WeatherProvider
from weatherbox.weather.dwd import DWDProvider
from weatherbox.weather.merged import MergedWeatherProvider
from weatherbox.weather.open_meteo import OpenMeteoProvider

if TYPE_CHECKING:
    from weatherbox.config import WeatherProviderSettings, WeatherSettings


def create_weather_provider(settings: WeatherSettings) -> WeatherProvider:
    """Build a provider from validated weather settings."""
    providers = tuple(
        (provider.name, _create_provider(provider)) for provider in settings.providers
    )
    if len(providers) == 1:
        return providers[0][1]
    return MergedWeatherProvider(
        providers,
        default_priority=settings.merge.default_priority,
        field_priority=settings.merge.field_priority,
        tolerance_minutes=settings.merge.tolerance_minutes,
    )


def _create_provider(settings: WeatherProviderSettings) -> WeatherProvider:
    """Build one concrete provider from its connection settings."""
    if settings.name == "dwd":
        return DWDProvider(settings.endpoint, settings.request_timeout_seconds)
    return OpenMeteoProvider(settings.endpoint, settings.request_timeout_seconds)
