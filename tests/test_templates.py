from datetime import timedelta

import pytest

from weatherbox.errors import TemplateRenderError
from weatherbox.models import WeatherWarning
from weatherbox.templates import build_context, render_template


def test_render_valid_template(location, weather, now, german_formatter):
    context = build_context(location, now.replace(hour=14, minute=0), weather, german_formatter)
    result = render_template("{time} in {location}: {temperature} Grad, Wind aus {wind_direction}.", context)
    assert result == "vierzehn Uhr in Wittstock: 18,2 Grad, Wind aus Südwesten."


def test_unknown_variable_fails(location, weather, now, german_formatter):
    context = build_context(location, now, weather, german_formatter)
    with pytest.raises(TemplateRenderError, match="Unknown template variables"):
        render_template("{not_a_field}", context)


def test_missing_weather_value_fails(location, weather, now, german_formatter):
    context = build_context(location, now, weather, german_formatter)
    context["temperature"] = None
    with pytest.raises(TemplateRenderError, match="temperature"):
        render_template("{temperature}", context)


def test_unused_missing_value_is_allowed(location, weather, now, german_formatter):
    context = build_context(location, now, weather, german_formatter)
    context["dew_point"] = None
    assert render_template("Hallo {location}", context) == "Hallo Wittstock"


def test_warning_placeholders_use_highest_active_warning(
    location, weather, now, german_formatter
):
    low = WeatherWarning(
        level=1,
        event="WIND",
        headline="Amtliche Warnung vor Windböen",
        start=now - timedelta(hours=1),
        end=now + timedelta(hours=2),
    )
    high = WeatherWarning(
        level=3,
        event="GEWITTER",
        headline="Amtliche Unwetterwarnung vor Gewitter",
        start=now - timedelta(minutes=30),
        end=now + timedelta(hours=1),
        instruction="Meiden Sie den Aufenthalt im Freien.",
    )
    values = {
        name: getattr(weather, name)
        for name in weather.__dataclass_fields__
        if name != "warnings"
    }
    weather_with_warnings = weather.__class__(**values, warnings=(low, high))
    context = build_context(location, now, weather_with_warnings, german_formatter)

    assert context["warning_count"] == "2"
    assert context["warning_level"] == "3"
    assert context["warning_event"] == "GEWITTER"
    assert context["warning_instruction"].startswith("Meiden")
    assert context["warning_text"].startswith("Amtliche Unwetterwarnung")


def test_warning_text_has_localized_no_warning_value(
    location, weather, now, german_formatter
):
    context = build_context(location, now, weather, german_formatter)
    assert context["warning_count"] == "0"
    assert context["warning_text"] == "Keine amtliche Wetterwarnung aktiv"


def test_provider_source_placeholders_are_available(
    location, weather, now, german_formatter
):
    warning = WeatherWarning(
        level=1,
        event="WIND",
        headline="Amtliche Warnung vor Windböen",
        start=now - timedelta(hours=1),
        end=now + timedelta(hours=1),
        source="dwd",
    )
    values = {
        name: getattr(weather, name)
        for name in weather.__dataclass_fields__
        if name not in {"warnings", "data_sources"}
    }
    sourced = weather.__class__(**values, warnings=(warning,)).with_source("open-meteo")
    context = build_context(location, now, sourced, german_formatter)

    assert context["temperature_source"] == "open-meteo"
    assert context["weather_source"] == "open-meteo"
    assert context["warning_source"] == "dwd"
