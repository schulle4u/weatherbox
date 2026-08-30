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
    assert german.greeting(value) == "Guten Abend"
    assert german.format_decimal(18.2) == "18,2"
    assert german.weather_description(2) == "der Himmel ist teilweise bewölkt"
    assert german.wind_direction(225) == "Südwesten"
    assert german.day_cloud_summary(95) == (
        "Über den Tag ist der Himmel überwiegend bedeckt."
    )
    assert german.day_precipitation_summary(20, 0) == (
        "Niederschlag ist heute eher unwahrscheinlich."
    )
    assert german.day_precipitation_summary(10, 0.1) == (
        "Niederschlag ist heute eher unwahrscheinlich. "
        "Insgesamt werden 0,1 Millimeter erwartet."
    )


def test_builtin_english_language_formats_complete_context_values():
    english = LanguageCatalog().get("en")
    value = datetime(2026, 8, 18, 21, 5, tzinfo=ZoneInfo("Europe/London"))
    assert english.format_number(21) == "twenty-one"
    assert english.format_time(value) == "twenty-one oh five"
    assert english.format_date(value) == "August 18, 2026"
    assert english.greeting(value) == "Good evening"
    assert english.format_decimal(18.2) == "18.2"
    assert english.weather_description(2) == "partly cloudy"
    assert english.wind_direction(225) == "southwest"
    assert english.day_weather_summary("partly cloudy", "13.4", "22.8") == (
        "Today's expected conditions are partly cloudy. "
        "Temperatures range from 13.4 to 22.8 degrees."
    )
    assert english.day_cloud_summary(50) == (
        "Skies will be partly cloudy throughout the day."
    )


def test_custom_language_file_can_override_builtin_language(tmp_path):
    source = resources.files("weatherbox").joinpath("lang", "de.yaml")
    data = yaml.safe_load(source.read_text(encoding="utf-8"))
    data["numbers"]["ones"][2] = "zwo"
    data["greetings"]["day"] = "Mahlzeit"
    (tmp_path / "de.yaml").write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    german = LanguageCatalog(tmp_path).get("de")
    assert german.format_number(2) == "zwo"
    assert german.greeting(datetime(2026, 8, 18, 12, 0)) == "Mahlzeit"


def test_exact_number_overrides_support_irregular_languages(tmp_path):
    source = resources.files("weatherbox").joinpath("lang", "en.yaml")
    data = yaml.safe_load(source.read_text(encoding="utf-8"))
    data["code"] = "custom"
    data["numbers"]["overrides"][21] = "special twenty-one"
    (tmp_path / "custom.yaml").write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    assert LanguageCatalog(tmp_path).get("custom").format_number(21) == "special twenty-one"


def test_custom_language_without_daily_summaries_remains_compatible(tmp_path):
    source = resources.files("weatherbox").joinpath("lang", "en.yaml")
    data = yaml.safe_load(source.read_text(encoding="utf-8"))
    data["code"] = "legacy"
    del data["summaries"]
    (tmp_path / "legacy.yaml").write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    legacy = LanguageCatalog(tmp_path).get("legacy")

    assert legacy.day_weather_summary("clear sky", "10", "20") is None


def test_incomplete_language_file_is_rejected(tmp_path):
    (tmp_path / "broken.yaml").write_text("code: broken\n", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="Required field"):
        LanguageCatalog(tmp_path)
