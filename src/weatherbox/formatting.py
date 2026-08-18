from __future__ import annotations

from datetime import datetime

from weatherbox.localization import builtin_language


def german_number(number: int, *, hour: bool = False) -> str:
    return builtin_language("de").format_number(number, context="hour" if hour else None)


def format_time_german(value: datetime) -> str:
    return builtin_language("de").format_time(value)


def format_date_german(value: datetime) -> str:
    return builtin_language("de").format_date(value)


def format_number(value: float | int | None) -> str | None:
    return builtin_language("de").format_decimal(value)


def weather_description(code: int | None) -> str | None:
    return builtin_language("de").weather_description(code)


def wind_direction_name(degrees: float | None) -> str | None:
    return builtin_language("de").wind_direction(degrees)
