"""Build and safely render localized announcement templates."""

from __future__ import annotations

from datetime import datetime
from string import Formatter
from typing import Any

from weatherbox.errors import TemplateRenderError
from weatherbox.localization import LanguageFormatter
from weatherbox.models import Location, WeatherData


ALLOWED_FIELDS = frozenset(
    {
        "time", "hour", "minute", "date", "location", "latitude", "longitude",
        "temperature", "apparent_temperature", "dew_point", "humidity", "pressure",
        "weather_description", "weather_code", "cloud_cover", "wind_speed",
        "wind_direction", "wind_direction_degrees", "wind_gusts", "precipitation",
        "precipitation_probability", "sunrise", "sunset", "forecast_time",
        "warning_count", "warning_level", "warning_event", "warning_headline",
        "warning_description", "warning_instruction", "warning_start", "warning_end",
        "warning_text", "temperature_source", "weather_source", "warning_source",
    }
)


def build_context(
    location: Location,
    playback_at: datetime,
    weather: WeatherData,
    formatter: LanguageFormatter,
) -> dict[str, Any]:
    """Build the localized placeholder values for an announcement template."""
    context: dict[str, Any] = {
        "time": formatter.format_time(playback_at),
        "hour": formatter.format_hour(playback_at.hour),
        "minute": formatter.format_decimal(playback_at.minute),
        "date": formatter.format_date(playback_at),
        "location": location.name,
        "latitude": formatter.format_decimal(location.latitude),
        "longitude": formatter.format_decimal(location.longitude),
        "weather_description": formatter.weather_description(weather.weather_code),
        "weather_code": weather.weather_code,
        "wind_direction": formatter.wind_direction(weather.wind_direction),
        "wind_direction_degrees": formatter.format_decimal(weather.wind_direction),
        "sunrise": formatter.format_time(weather.sunrise) if weather.sunrise else None,
        "sunset": formatter.format_time(weather.sunset) if weather.sunset else None,
        "forecast_time": formatter.format_time(weather.forecast_at),
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
                formatter.format_time(primary_warning.start) if primary_warning else None
            ),
            "warning_end": (
                formatter.format_time(primary_warning.end)
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
    ):
        context[name] = formatter.format_decimal(getattr(weather, name))
    return context


def render_template(template: str, context: dict[str, Any]) -> str:
    """Render a template after validating its fields and required values."""
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
        raise TemplateRenderError(f"No data for template variables: {', '.join(missing)}")
    try:
        rendered = template.format_map(context)
    except (KeyError, ValueError) as exc:
        raise TemplateRenderError(f"Template could not be rendered: {exc}") from exc
    rendered = " ".join(rendered.split())
    if not rendered:
        raise TemplateRenderError("The rendered template is empty")
    return rendered
