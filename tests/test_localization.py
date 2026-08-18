from __future__ import annotations

from datetime import datetime
from importlib import resources
from zoneinfo import ZoneInfo

import pytest
import yaml

from weatherbox.errors import ConfigurationError
from weatherbox.localization import LanguageCatalog


def test_builtin_german_language_preserves_pronunciation():
    german = LanguageCatalog().get("de")
    value = datetime(2026, 8, 18, 21, 5, tzinfo=ZoneInfo("Europe/Berlin"))
    assert german.format_number(21) == "einundzwanzig"
    assert german.format_time(value) == "einundzwanzig Uhr fünf"
    assert german.format_date(value) == "18. August 2026"
    assert german.format_decimal(18.2) == "18,2"
    assert german.weather_description(2) == "teilweise bewölkt"
    assert german.wind_direction(225) == "Südwesten"


def test_builtin_english_language_formats_complete_context_values():
    english = LanguageCatalog().get("en")
    value = datetime(2026, 8, 18, 21, 5, tzinfo=ZoneInfo("Europe/London"))
    assert english.format_number(21) == "twenty-one"
    assert english.format_time(value) == "twenty-one oh five"
    assert english.format_date(value) == "August 18, 2026"
    assert english.format_decimal(18.2) == "18.2"
    assert english.weather_description(2) == "partly cloudy"
    assert english.wind_direction(225) == "southwest"


def test_custom_language_file_can_override_builtin_language(tmp_path):
    source = resources.files("weatherbox").joinpath("lang", "de.yaml")
    data = yaml.safe_load(source.read_text(encoding="utf-8"))
    data["numbers"]["ones"][2] = "zwo"
    (tmp_path / "de.yaml").write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    assert LanguageCatalog(tmp_path).get("de").format_number(2) == "zwo"


def test_exact_number_overrides_support_irregular_languages(tmp_path):
    source = resources.files("weatherbox").joinpath("lang", "en.yaml")
    data = yaml.safe_load(source.read_text(encoding="utf-8"))
    data["code"] = "custom"
    data["numbers"]["overrides"][21] = "special twenty-one"
    (tmp_path / "custom.yaml").write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    assert LanguageCatalog(tmp_path).get("custom").format_number(21) == "special twenty-one"


def test_incomplete_language_file_is_rejected(tmp_path):
    (tmp_path / "broken.yaml").write_text("code: broken\n", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="Pflichtfeld"):
        LanguageCatalog(tmp_path)
