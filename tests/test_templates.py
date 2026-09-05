from dataclasses import replace
from datetime import timedelta

import pytest

from weatherbox.errors import TemplateRenderError
from weatherbox.models import TemperatureUnit, WeatherWarning
from weatherbox.templates import build_context, render_template, render_text_asset


def test_render_valid_template(location, weather, now, german_formatter):
    context = build_context(location, now.replace(hour=14, minute=0), weather, german_formatter)
    result = render_template("{time} in {location}: {temperature} Grad, Wind aus {wind_direction}.", context)
    assert result == "vierzehn Uhr in Wittstock: 18,2 Grad, Wind aus Südwesten."


def test_readable_context_does_not_spell_time_or_date(
    location, weather, now, german_formatter
):
    context = build_context(
        location, now.replace(hour=14, minute=5), weather, german_formatter, spoken=False
    )

    assert context["time"] == "14:05"
    assert context["hour"] == "14"
    assert context["minute"] == "05"
    assert context["date"] == "18.08.2026"


def test_text_asset_renderer_escapes_inserted_values():
    result = render_text_asset(
        '<html lang="{language}"><p>{message}</p></html>',
        {"language": 'de" data-test="x', "message": "Wind < Sturm"},
    )

    assert 'lang="de&quot; data-test=&quot;x"' in result
    assert "Wind &lt; Sturm" in result


def test_temperature_values_are_converted_to_location_unit(
    location, weather, now, german_formatter
):
    fahrenheit_location = replace(
        location, temperature_unit=TemperatureUnit.FAHRENHEIT
    )

    context = build_context(fahrenheit_location, now, weather, german_formatter)

    assert context["temperature"] == "64,8"
    assert context["apparent_temperature"] == "63,5"
    assert context["dew_point"] == "53,8"
    assert context["day_temperature_min"] == "56,1"
    assert context["day_temperature_max"] == "73"
    assert weather.temperature == 18.2


def test_daily_weather_placeholders_and_summaries_are_available(
    location, weather, now, german_formatter
):
    context = build_context(location, now, weather, german_formatter)

    assert context["day_temperature_min"] == "13,4"
    assert context["day_temperature_max"] == "22,8"
    assert context["day_precipitation_sum"] == "2,4"
    assert context["day_precipitation_probability_max"] == "65"
    assert context["day_precipitation_hours"] == "3"
    assert context["day_cloud_cover_mean"] == "78"
    assert context["day_weather_description"] == "leichte Regenschauer"
    assert context["day_wind_speed_max"] == "24,6"
    assert context["day_wind_gusts_max"] == "41,2"
    assert "zwischen 13,4 und 22,8 Grad" in context["day_weather_summary"]
    assert context["day_cloud_summary"] == "Über den Tag ist es stark bewölkt."
    assert context["day_precipitation_summary"] == (
        "Im Tagesverlauf ist Niederschlag wahrscheinlich. "
        "Insgesamt werden 2,4 Millimeter erwartet."
    )

    rendered = render_template(
        "{day_weather_summary} {day_cloud_summary} {day_precipitation_summary}",
        context,
    )
    assert rendered.startswith("Für heute wird folgende Wetterlage erwartet")


@pytest.mark.parametrize(
    ("hour", "expected"),
    [
        (0, "Guten Morgen"),
        (11, "Guten Morgen"),
        (12, "Guten Tag"),
        (17, "Guten Tag"),
        (18, "Guten Abend"),
        (23, "Guten Abend"),
    ],
)
def test_greeting_uses_location_playback_hour(
    location, weather, now, german_formatter, hour, expected
):
    playback_at = now.replace(hour=hour, minute=30)
    context = build_context(location, playback_at, weather, german_formatter)

    assert render_template("{greeting}, {location}!", context) == f"{expected}, Wittstock!"


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
