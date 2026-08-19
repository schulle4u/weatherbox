from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from weatherbox.formatting import (
    format_time_german,
    german_number,
    weather_description,
    wind_direction_name,
)


@pytest.mark.parametrize(
    ("hour", "minute", "expected"),
    [
        (0, 0, "null Uhr"),
        (1, 0, "ein Uhr"),
        (1, 1, "ein Uhr eins"),
        (8, 5, "acht Uhr fünf"),
        (12, 30, "zwölf Uhr dreißig"),
        (21, 0, "einundzwanzig Uhr"),
        (21, 21, "einundzwanzig Uhr einundzwanzig"),
        (23, 59, "dreiundzwanzig Uhr neunundfünfzig"),
    ],
)
def test_german_time(hour, minute, expected):
    value = datetime(2026, 1, 1, hour, minute, tzinfo=ZoneInfo("Europe/Berlin"))
    assert format_time_german(value) == expected


@pytest.mark.parametrize(
    ("number", "expected"),
    [
        (21, "einundzwanzig"),
        (31, "einunddreißig"),
        (41, "einundvierzig"),
        (51, "einundfünfzig"),
    ],
)
def test_compound_numbers_use_ein(number, expected):
    assert german_number(number) == expected


def test_weather_codes_and_wind_direction():
    assert weather_description(0) == "der Himmel ist klar"
    assert weather_description(95) == "Gewitter"
    assert weather_description(123) == "Wettercode 123"
    assert wind_direction_name(0) == "Norden"
    assert wind_direction_name(225) == "Südwesten"
