from __future__ import annotations

from datetime import datetime


_ONES = (
    "null",
    "eins",
    "zwei",
    "drei",
    "vier",
    "fünf",
    "sechs",
    "sieben",
    "acht",
    "neun",
    "zehn",
    "elf",
    "zwölf",
    "dreizehn",
    "vierzehn",
    "fünfzehn",
    "sechzehn",
    "siebzehn",
    "achtzehn",
    "neunzehn",
)
_TENS = {20: "zwanzig", 30: "dreißig", 40: "vierzig", 50: "fünfzig"}
_MONTHS = (
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
)


def german_number(number: int, *, hour: bool = False) -> str:
    if not 0 <= number <= 59:
        raise ValueError("Nur Zahlen von 0 bis 59 werden unterstützt")
    if number < 20:
        value = _ONES[number]
    else:
        tens = number - number % 10
        ones = number % 10
        if ones == 0:
            value = _TENS[tens]
        else:
            # In zusammengesetzten Zahlen heißt es "einundzwanzig",
            # nicht "einsundzwanzig".
            ones_word = "ein" if ones == 1 else _ONES[ones]
            value = f"{ones_word}und{_TENS[tens]}"
    if hour and number == 1:
        return "ein"
    return value


def format_time_german(value: datetime) -> str:
    hour = german_number(value.hour, hour=True)
    if value.minute == 0:
        return f"{hour} Uhr"
    return f"{hour} Uhr {german_number(value.minute)}"


def format_date_german(value: datetime) -> str:
    return f"{value.day}. {_MONTHS[value.month - 1]} {value.year}"


def format_number(value: float | int | None) -> str | None:
    if value is None:
        return None
    rounded = round(float(value), 1)
    if rounded.is_integer():
        return str(int(rounded))
    return f"{rounded:.1f}".replace(".", ",")


def weather_description(code: int | None) -> str | None:
    descriptions = {
        0: "klar",
        1: "überwiegend klar",
        2: "teilweise bewölkt",
        3: "bedeckt",
        45: "neblig",
        48: "neblig mit Reifablagerungen",
        51: "leichter Nieselregen",
        53: "mäßiger Nieselregen",
        55: "starker Nieselregen",
        56: "leichter gefrierender Nieselregen",
        57: "starker gefrierender Nieselregen",
        61: "leichter Regen",
        63: "mäßiger Regen",
        65: "starker Regen",
        66: "leichter gefrierender Regen",
        67: "starker gefrierender Regen",
        71: "leichter Schneefall",
        73: "mäßiger Schneefall",
        75: "starker Schneefall",
        77: "Schneegriesel",
        80: "leichte Regenschauer",
        81: "mäßige Regenschauer",
        82: "starke Regenschauer",
        85: "leichte Schneeschauer",
        86: "starke Schneeschauer",
        95: "Gewitter",
        96: "Gewitter mit leichtem Hagel",
        99: "Gewitter mit starkem Hagel",
    }
    return descriptions.get(code, f"Wettercode {code}" if code is not None else None)


def wind_direction_name(degrees: float | None) -> str | None:
    if degrees is None:
        return None
    names = (
        "Norden", "Nordnordost", "Nordosten", "Ostnordost",
        "Osten", "Ostsüdost", "Südosten", "Südsüdost",
        "Süden", "Südsüdwest", "Südwesten", "Westsüdwest",
        "Westen", "Westnordwest", "Nordwesten", "Nordnordwest",
    )
    return names[int((degrees % 360) / 22.5 + 0.5) % 16]
