"""Backward-compatible German formatting helpers."""

from __future__ import annotations

from datetime import datetime

from weatherbox.localization import builtin_language


def german_number(number: int, *, hour: bool = False) -> str:
    """Spell an integer in German, optionally using its hour-specific form."""
    return builtin_language("de").format_number(number, context="hour" if hour else None)


def format_time_german(value: datetime) -> str:
    """Format a time for spoken German output."""
    return builtin_language("de").format_time(value)


def format_date_german(value: datetime) -> str:
    """Format a date for spoken German output."""
    return builtin_language("de").format_date(value)


def format_number(value: float | int | None) -> str | None:
    """Format a numeric weather value using German decimal conventions."""
    return builtin_language("de").format_decimal(value)


def weather_description(code: int | None) -> str | None:
    """Return the German description for a WMO weather code."""
    return builtin_language("de").weather_description(code)


def wind_direction_name(degrees: float | None) -> str | None:
    """Return the German compass direction nearest to an angle in degrees."""
    return builtin_language("de").wind_direction(degrees)
