"""Build and safely render localized announcement templates."""

from __future__ import annotations

from datetime import datetime
from html import escape
import logging
import re
from string import Formatter
from typing import Any

from weatherbox.errors import TemplateRenderError
from weatherbox.localization import LanguageFormatter
from weatherbox.models import Location, WeatherData


logger = logging.getLogger(__name__)


TEMPERATURE_FIELDS = frozenset(
    {
        "temperature",
        "apparent_temperature",
        "dew_point",
        "day_temperature_min",
        "day_temperature_max",
    }
)

ALLOWED_FIELDS = frozenset(
    {
        "greeting", "time", "hour", "minute", "date", "location", "latitude", "longitude",
        "temperature", "apparent_temperature", "dew_point", "humidity", "pressure",
        "weather_description", "weather_code", "cloud_cover", "wind_speed",
        "wind_direction", "wind_direction_degrees", "wind_gusts", "precipitation",
        "precipitation_probability", "sunrise", "sunset", "forecast_time",
        "warning_count", "warning_level", "warning_event", "warning_headline",
        "warning_description", "warning_instruction", "warning_start", "warning_end",
        "warning_text", "temperature_source", "weather_source", "warning_source",
        "day_temperature_min", "day_temperature_max", "day_precipitation_sum",
        "day_precipitation_probability_max", "day_precipitation_hours",
        "day_cloud_cover_mean", "day_weather_description", "day_wind_speed_max",
        "day_wind_gusts_max", "day_weather_summary", "day_cloud_summary",
        "day_precipitation_summary",
    }
)

TEXT_ASSET_FIELDS = frozenset(
    {"language", "location", "location_id", "message", "kind", "date", "time", "year"}
)

DEFAULT_TEXT_ASSET_TEMPLATE = """<!DOCTYPE html>
<html lang="{language}">
<head>
<title>{location} - Weatherbox</title>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<link rel="stylesheet" href="https://cdn.simplecss.org/simple.min.css">
</head>
<body>
<main>
<h1>{location}</h1>
<p class="message">{message}</p>
</main>
<footer>
<p class="notice">Copyright &copy; {year}.</p>
</footer>
</body>
</html>
"""


def build_context(
    location: Location,
    playback_at: datetime,
    weather: WeatherData,
    formatter: LanguageFormatter,
    *,
    spoken: bool = True,
) -> dict[str, Any]:
    """Build the localized placeholder values for an announcement template."""
    format_time = formatter.format_time if spoken else _readable_time
    context: dict[str, Any] = {
        "greeting": formatter.greeting(playback_at),
        "time": format_time(playback_at),
        "hour": formatter.format_hour(playback_at.hour) if spoken else str(playback_at.hour),
        "minute": (
            formatter.format_decimal(playback_at.minute)
            if spoken
            else f"{playback_at.minute:02d}"
        ),
        "date": (
            formatter.format_date(playback_at)
            if spoken
            else _readable_date(playback_at, formatter.code)
        ),
        "location": location.name,
        "latitude": formatter.format_decimal(location.latitude),
        "longitude": formatter.format_decimal(location.longitude),
        "weather_description": formatter.weather_description(weather.weather_code),
        "day_weather_description": formatter.weather_description(weather.day_weather_code),
        "weather_code": weather.weather_code,
        "wind_direction": formatter.wind_direction(weather.wind_direction),
        "wind_direction_degrees": formatter.format_decimal(weather.wind_direction),
        "sunrise": format_time(weather.sunrise) if weather.sunrise else None,
        "sunset": format_time(weather.sunset) if weather.sunset else None,
        "forecast_time": format_time(weather.forecast_at),
        "temperature_source": weather.source_for("temperature"),
        "weather_source": weather.source_for("weather_code"),
    }
    active_warnings = sorted(
        (warning for warning in weather.warnings if warning.is_active(playback_at)),
        key=lambda warning: (-warning.level, warning.start),
    )
    primary_warning = active_warnings[0] if active_warnings else None
    context.update(
        {
            "warning_count": formatter.format_decimal(len(active_warnings)),
            "warning_level": (
                formatter.format_decimal(primary_warning.level) if primary_warning else None
            ),
            "warning_event": primary_warning.event if primary_warning else None,
            "warning_headline": primary_warning.headline if primary_warning else None,
            "warning_description": primary_warning.description if primary_warning else None,
            "warning_instruction": primary_warning.instruction if primary_warning else None,
            "warning_source": primary_warning.source if primary_warning else None,
            "warning_start": (
                format_time(primary_warning.start) if primary_warning else None
            ),
            "warning_end": (
                format_time(primary_warning.end)
                if primary_warning and primary_warning.end
                else None
            ),
            "warning_text": (
                formatter.warning_separator.join(
                    warning.headline or warning.event for warning in active_warnings
                )
                if active_warnings
                else formatter.no_active_warning
            ),
        }
    )
    for name in (
        "temperature", "apparent_temperature", "dew_point", "humidity", "pressure",
        "cloud_cover", "wind_speed", "wind_gusts", "precipitation",
        "precipitation_probability",
        "day_temperature_min", "day_temperature_max", "day_precipitation_sum",
        "day_precipitation_probability_max", "day_precipitation_hours",
        "day_cloud_cover_mean", "day_wind_speed_max", "day_wind_gusts_max",
    ):
        value = getattr(weather, name)
        if name in TEMPERATURE_FIELDS:
            value = location.temperature_unit.from_celsius(value)
        context[name] = formatter.format_decimal(value)
    context.update(
        {
            "day_weather_summary": formatter.day_weather_summary(
                context["day_weather_description"],
                context["day_temperature_min"],
                context["day_temperature_max"],
            ),
            "day_cloud_summary": formatter.day_cloud_summary(
                weather.day_cloud_cover_mean
            ),
            "day_precipitation_summary": formatter.day_precipitation_summary(
                weather.day_precipitation_probability_max,
                weather.day_precipitation_sum,
            ),
        }
    )
    return context


def _readable_time(value: datetime) -> str:
    """Format a compact, non-spoken time for display."""
    return value.strftime("%H:%M")


def _readable_date(value: datetime, language: str) -> str:
    """Format a numeric date without pronunciation dictionary rules."""
    if language == "de":
        return value.strftime("%d.%m.%Y")
    if language == "en":
        return value.strftime("%m/%d/%Y")
    return value.strftime("%Y-%m-%d")


def render_text_asset(template: str, context: dict[str, Any]) -> str:
    """Render an HTML wrapper while escaping every inserted text value."""
    fields: set[str] = set()
    try:
        for _, field_name, format_spec, conversion in Formatter().parse(template):
            if field_name is None:
                continue
            if not field_name or any(token in field_name for token in (".", "[", "]")):
                raise TemplateRenderError(f"Invalid text asset placeholder: {{{field_name}}}")
            if format_spec or conversion:
                raise TemplateRenderError(
                    f"Format specifications are not permitted: {{{field_name}}}"
                )
            fields.add(field_name)
    except ValueError as exc:
        raise TemplateRenderError(f"Invalid text asset template: {exc}") from exc

    unknown = fields - TEXT_ASSET_FIELDS
    if unknown:
        raise TemplateRenderError(
            f"Unknown text asset variables: {', '.join(sorted(unknown))}"
        )
    missing = sorted(name for name in fields if context.get(name) is None)
    if missing:
        raise TemplateRenderError(
            f"No data for text asset variables: {', '.join(missing)}"
        )
    escaped = {name: escape(str(value), quote=True) for name, value in context.items()}
    try:
        rendered = template.format_map(escaped)
    except (KeyError, ValueError) as exc:
        raise TemplateRenderError(f"Text asset template could not be rendered: {exc}") from exc
    if not rendered.strip():
        raise TemplateRenderError("The rendered text asset template is empty")
    return rendered


def render_template(template: str, context: dict[str, Any]) -> str:
    """Validate a template and omit sentences whose values are unavailable."""
    fields: set[str] = set()
    try:
        parsed = Formatter().parse(template)
        for _, field_name, format_spec, conversion in parsed:
            if field_name is None:
                continue
            if not field_name or any(token in field_name for token in (".", "[", "]")):
                raise TemplateRenderError(f"Invalid placeholder: {{{field_name}}}")
            if format_spec or conversion:
                raise TemplateRenderError(f"Format specifications are not permitted: {{{field_name}}}")
            fields.add(field_name)
    except ValueError as exc:
        raise TemplateRenderError(f"Invalid template: {exc}") from exc

    unknown = fields - ALLOWED_FIELDS
    if unknown:
        raise TemplateRenderError(f"Unknown template variables: {', '.join(sorted(unknown))}")
    missing = sorted(name for name in fields if context.get(name) is None)
    if missing:
        logger.warning(
            "Omitting template sentences with unavailable variables: %s",
            ", ".join(missing),
        )
        # Split before interpolation: decimal values and punctuation in provider
        # descriptions must not affect which template text gets omitted.
        sentences = re.split(r"(?<=[.!?])\s+|[\r\n]+", template)
        template = " ".join(
            sentence
            for sentence in sentences
            if not any(
                field_name in missing
                for _, field_name, _, _ in Formatter().parse(sentence)
                if field_name is not None
            )
        )
    try:
        rendered = template.format_map(context)
    except (KeyError, ValueError) as exc:
        raise TemplateRenderError(f"Template could not be rendered: {exc}") from exc
    rendered = " ".join(rendered.split())
    if not rendered:
        raise TemplateRenderError("The rendered template is empty")
    return rendered
