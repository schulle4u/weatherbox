"""Merge forecasts and warnings from multiple weather providers."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from datetime import datetime

from weatherbox.errors import WeatherUnavailableError
from weatherbox.models import (
    WEATHER_VALUE_FIELDS,
    ForecastBundle,
    Location,
    WeatherData,
    WeatherWarning,
)
from weatherbox.weather.base import WeatherProvider


LOG = logging.getLogger(__name__)


class MergedWeatherProvider:
    """Fetch providers concurrently and combine their data by field priority."""

    name = "merged"

    def __init__(
        self,
        providers: tuple[tuple[str, WeatherProvider], ...],
        *,
        default_priority: tuple[str, ...],
        field_priority: dict[str, tuple[str, ...]],
        tolerance_minutes: int = 30,
    ) -> None:
        """Initialize the provider collection and deterministic merge rules."""
        if not providers:
            raise ValueError("At least one weather provider is required")
        self.providers = providers
        self.default_priority = default_priority
        self.field_priority = field_priority
        self.tolerance_minutes = tolerance_minutes

    def fetch(self, location: Location) -> ForecastBundle:
        """Fetch all providers, tolerating partial failures, and merge results."""
        bundles: dict[str, ForecastBundle] = {}
        errors: dict[str, Exception] = {}
        with ThreadPoolExecutor(max_workers=len(self.providers)) as executor:
            futures = {
                executor.submit(provider.fetch, location): name
                for name, provider in self.providers
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    bundles[name] = future.result()
                except Exception as exc:
                    errors[name] = exc
                    LOG.warning(
                        "Weather provider unavailable during merged fetch",
                        extra={
                            "location_id": location.id,
                            "provider": name,
                            "error": str(exc),
                        },
                    )
        if not bundles:
            details = "; ".join(
                f"{name}: {error}" for name, error in sorted(errors.items())
            )
            raise WeatherUnavailableError(f"All weather providers failed: {details}")
        return self._merge(bundles)

    def _merge(self, bundles: dict[str, ForecastBundle]) -> ForecastBundle:
        """Align successful bundles to the primary timeline and merge each field."""
        base_name = next(
            (
                name
                for name in self.default_priority
                if name in bundles and bundles[name].forecasts
            ),
            None,
        )
        if base_name is None:
            raise WeatherUnavailableError("Weather providers returned no forecasts")

        forecasts = tuple(
            self._merge_forecast(item.forecast_at, bundles)
            for item in bundles[base_name].forecasts
        )
        warnings = self._merge_warnings(bundles)
        return ForecastBundle(
            fetched_at=min(bundle.fetched_at for bundle in bundles.values()),
            forecasts=forecasts,
            warnings=warnings,
        )

    def _merge_forecast(
        self,
        forecast_at: datetime,
        bundles: dict[str, ForecastBundle],
    ) -> WeatherData:
        """Merge all values nearest to one timestamp according to field priority."""
        nearest = {
            name: bundle.for_time(forecast_at, self.tolerance_minutes)
            for name, bundle in bundles.items()
        }
        values: dict[str, object] = {}
        sources: list[tuple[str, str]] = []
        for field_name in WEATHER_VALUE_FIELDS:
            priority = self.field_priority.get(field_name, self.default_priority)
            for provider_name in priority:
                candidate = nearest.get(provider_name)
                if candidate is None:
                    continue
                value = getattr(candidate, field_name)
                if value is None:
                    continue
                values[field_name] = value
                sources.append((field_name, provider_name))
                break
        return WeatherData(
            forecast_at=forecast_at,
            **values,
            data_sources=tuple(sources),
        )

    def _merge_warnings(
        self, bundles: dict[str, ForecastBundle]
    ) -> tuple[WeatherWarning, ...]:
        """Union warnings, preferring the configured provider for duplicates."""
        priority = self.field_priority.get("warnings", self.default_priority)
        warnings: dict[tuple[object, ...], WeatherWarning] = {}
        for provider_name in priority:
            bundle = bundles.get(provider_name)
            if bundle is None:
                continue
            for warning in bundle.warnings:
                normalized = replace(warning, source=warning.source or provider_name)
                key = (
                    normalized.headline.casefold(),
                    normalized.start,
                    normalized.end,
                )
                warnings.setdefault(key, normalized)
        return tuple(
            sorted(
                warnings.values(),
                key=lambda warning: (-warning.level, warning.start, warning.headline),
            )
        )
