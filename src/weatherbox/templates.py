from __future__ import annotations

from datetime import datetime
from string import Formatter
from typing import Any

from weatherbox.errors import TemplateRenderError
from weatherbox.formatting import (
    format_date_german,
    format_number,
    format_time_german,
    weather_description,
    wind_direction_name,
)
from weatherbox.models import Location, WeatherData


ALLOWED_FIELDS = frozenset(
    {
        "time", "hour", "minute", "date", "location", "latitude", "longitude",
        "temperature", "apparent_temperature", "dew_point", "humidity", "pressure",
        "weather_description", "weather_code", "cloud_cover", "wind_speed",
        "wind_direction", "wind_direction_degrees", "wind_gusts", "precipitation",
        "precipitation_probability", "sunrise", "sunset", "forecast_time",
    }
)


def build_context(location: Location, playback_at: datetime, weather: WeatherData) -> dict[str, Any]:
    context: dict[str, Any] = {
        "time": format_time_german(playback_at),
        "hour": german_hour(playback_at.hour),
        "minute": format_number(playback_at.minute),
        "date": format_date_german(playback_at),
        "location": location.name,
        "latitude": format_number(location.latitude),
        "longitude": format_number(location.longitude),
        "weather_description": weather_description(weather.weather_code),
        "weather_code": weather.weather_code,
        "wind_direction": wind_direction_name(weather.wind_direction),
        "wind_direction_degrees": format_number(weather.wind_direction),
        "sunrise": format_time_german(weather.sunrise) if weather.sunrise else None,
        "sunset": format_time_german(weather.sunset) if weather.sunset else None,
        "forecast_time": format_time_german(weather.forecast_at),
    }
    for name in (
        "temperature", "apparent_temperature", "dew_point", "humidity", "pressure",
        "cloud_cover", "wind_speed", "wind_gusts", "precipitation",
        "precipitation_probability",
    ):
        context[name] = format_number(getattr(weather, name))
    return context


def german_hour(hour: int) -> str:
    from weatherbox.formatting import german_number

    return german_number(hour, hour=True)


def render_template(template: str, context: dict[str, Any]) -> str:
    fields: set[str] = set()
    try:
        parsed = Formatter().parse(template)
        for _, field_name, format_spec, conversion in parsed:
            if field_name is None:
                continue
            if not field_name or any(token in field_name for token in (".", "[", "]")):
                raise TemplateRenderError(f"Ungültiger Platzhalter: {{{field_name}}}")
            if format_spec or conversion:
                raise TemplateRenderError(f"Formatangaben sind nicht erlaubt: {{{field_name}}}")
            fields.add(field_name)
    except ValueError as exc:
        raise TemplateRenderError(f"Ungültiges Template: {exc}") from exc

    unknown = fields - ALLOWED_FIELDS
    if unknown:
        raise TemplateRenderError(f"Unbekannte Template-Variable(n): {', '.join(sorted(unknown))}")
    missing = sorted(name for name in fields if context.get(name) is None)
    if missing:
        raise TemplateRenderError(f"Keine Daten für Template-Variable(n): {', '.join(missing)}")
    try:
        rendered = template.format_map(context)
    except (KeyError, ValueError) as exc:
        raise TemplateRenderError(f"Template konnte nicht gerendert werden: {exc}") from exc
    rendered = " ".join(rendered.split())
    if not rendered:
        raise TemplateRenderError("Das gerenderte Template ist leer")
    return rendered

