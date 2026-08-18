import pytest

from weatherbox.errors import TemplateRenderError
from weatherbox.templates import build_context, render_template


def test_render_valid_template(location, weather, now, german_formatter):
    context = build_context(location, now.replace(hour=14, minute=0), weather, german_formatter)
    result = render_template("{time} in {location}: {temperature} Grad, Wind aus {wind_direction}.", context)
    assert result == "vierzehn Uhr in Wittstock: 18,2 Grad, Wind aus Südwesten."


def test_unknown_variable_fails(location, weather, now, german_formatter):
    context = build_context(location, now, weather, german_formatter)
    with pytest.raises(TemplateRenderError, match="Unbekannte"):
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
