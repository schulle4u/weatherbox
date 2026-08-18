from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from importlib import resources
from pathlib import Path
from string import Formatter
from typing import Any, Iterable

import yaml

from weatherbox.errors import ConfigurationError


@dataclass(frozen=True, slots=True)
class NumberRules:
    ones: dict[int, str]
    tens: dict[int, str]
    compound_order: str
    compound_separator: str
    compound_overrides: dict[int, str]
    exact_overrides: dict[int, str]
    context_overrides: dict[str, dict[int, str]]
    decimal_separator: str


@dataclass(frozen=True, slots=True)
class TimeRules:
    exact_hour: str
    with_minutes: str
    minute_prefix_under_ten: str
    hour_mode: int


@dataclass(frozen=True, slots=True)
class DateRules:
    pattern: str
    months: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LanguageFormatter:
    code: str
    numbers: NumberRules
    time: TimeRules
    date: DateRules
    weather_descriptions: dict[int, str]
    unknown_weather: str
    wind_directions: tuple[str, ...]

    def format_number(self, number: int, *, context: str | None = None) -> str:
        if not 0 <= number <= 59:
            raise ValueError("Only numbers from 0 to 59 are supported")
        if context and number in self.numbers.context_overrides.get(context, {}):
            return self.numbers.context_overrides[context][number]
        if number in self.numbers.exact_overrides:
            return self.numbers.exact_overrides[number]
        if number < 20:
            return self.numbers.ones[number]
        tens = number - number % 10
        ones = number % 10
        if ones == 0:
            return self.numbers.tens[tens]
        ones_word = self.numbers.compound_overrides.get(ones, self.numbers.ones[ones])
        tens_word = self.numbers.tens[tens]
        if self.numbers.compound_order == "ones_tens":
            return f"{ones_word}{self.numbers.compound_separator}{tens_word}"
        return f"{tens_word}{self.numbers.compound_separator}{ones_word}"

    def format_time(self, value: datetime) -> str:
        hour = self.format_hour(value.hour)
        if value.minute == 0:
            return self.time.exact_hour.format(hour=hour)
        minute = self.format_number(value.minute, context="minute")
        if value.minute < 10:
            minute = f"{self.time.minute_prefix_under_ten}{minute}"
        return self.time.with_minutes.format(hour=hour, minute=minute)

    def format_hour(self, hour: int) -> str:
        display_hour = hour
        if self.time.hour_mode == 12:
            display_hour = hour % 12 or 12
        return self.format_number(display_hour, context="hour")

    def format_date(self, value: datetime) -> str:
        return self.date.pattern.format(
            day=value.day,
            month=self.date.months[value.month - 1],
            year=value.year,
        )

    def format_decimal(self, value: float | int | None) -> str | None:
        if value is None:
            return None
        rounded = round(float(value), 1)
        if rounded.is_integer():
            return str(int(rounded))
        return f"{rounded:.1f}".replace(".", self.numbers.decimal_separator)

    def weather_description(self, code: int | None) -> str | None:
        if code is None:
            return None
        return self.weather_descriptions.get(code, self.unknown_weather.format(code=code))

    def wind_direction(self, degrees: float | None) -> str | None:
        if degrees is None:
            return None
        return self.wind_directions[int((degrees % 360) / 22.5 + 0.5) % 16]


class LanguageCatalog:
    def __init__(self, custom_directory: Path | None = None) -> None:
        self._languages: dict[str, LanguageFormatter] = {}
        builtin_directory = resources.files("weatherbox").joinpath("lang")
        self._load_resources(item for item in builtin_directory.iterdir() if item.name.endswith(".yaml"))
        if custom_directory is not None:
            if not custom_directory.is_dir():
                raise ConfigurationError(f"Sprachverzeichnis existiert nicht: {custom_directory}")
            self._load_resources(sorted(custom_directory.glob("*.yaml")))

    @property
    def available(self) -> tuple[str, ...]:
        return tuple(sorted(self._languages))

    def get(self, code: str) -> LanguageFormatter:
        try:
            return self._languages[code]
        except KeyError as exc:
            available = ", ".join(self.available)
            raise ConfigurationError(
                f"Unbekannte Sprache '{code}'. Verfügbar: {available or 'keine'}"
            ) from exc

    def _load_resources(self, files: Iterable[Any]) -> None:
        for source in files:
            try:
                raw = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
            except (OSError, yaml.YAMLError) as exc:
                raise ConfigurationError(f"Sprachdatei kann nicht geladen werden: {source}: {exc}") from exc
            formatter = _parse_language(raw, str(source))
            self._languages[formatter.code] = formatter


def _parse_language(raw: Any, source: str) -> LanguageFormatter:
    if not isinstance(raw, dict):
        raise ConfigurationError(f"Sprachdatei muss ein YAML-Objekt sein: {source}")
    try:
        code = str(raw["code"])
        number_raw = _required_mapping(raw, "numbers", source)
        ones = _integer_words(number_raw, "ones", source, range(0, 20))
        tens = _integer_words(number_raw, "tens", source, (20, 30, 40, 50))
        compound = _required_mapping(number_raw, "compound", source)
        order = str(compound["order"])
        if order not in {"ones_tens", "tens_ones"}:
            raise ConfigurationError(
                f"numbers.compound.order muss 'ones_tens' oder 'tens_ones' sein: {source}"
            )
        compound_overrides = _optional_integer_words(compound.get("ones_overrides", {}), source)
        exact_overrides = _optional_integer_words(number_raw.get("overrides", {}), source)
        context_raw = number_raw.get("context_overrides", {})
        if not isinstance(context_raw, dict):
            raise ConfigurationError(f"numbers.context_overrides muss ein Objekt sein: {source}")
        context_overrides = {
            str(context): _optional_integer_words(values, source)
            for context, values in context_raw.items()
        }

        time_raw = _required_mapping(raw, "time", source)
        exact_hour = _validated_pattern(time_raw["exact_hour"], {"hour"}, source)
        with_minutes = _validated_pattern(time_raw["with_minutes"], {"hour", "minute"}, source)
        hour_mode = int(time_raw.get("hour_mode", 24))
        if hour_mode not in {12, 24}:
            raise ConfigurationError(f"time.hour_mode muss 12 oder 24 sein: {source}")
        date_raw = _required_mapping(raw, "date", source)
        date_pattern = _validated_pattern(date_raw["pattern"], {"day", "month", "year"}, source)
        months = tuple(str(value) for value in date_raw["months"])
        if len(months) != 12 or not all(months):
            raise ConfigurationError(f"date.months muss genau zwölf Einträge enthalten: {source}")

        weather_raw = _required_mapping(raw, "weather", source)
        weather_descriptions = _optional_integer_words(weather_raw["descriptions"], source)
        unknown_weather = _validated_pattern(weather_raw["unknown"], {"code"}, source)
        wind_raw = _required_mapping(raw, "wind", source)
        wind_directions = tuple(str(value) for value in wind_raw["directions"])
        if len(wind_directions) != 16 or not all(wind_directions):
            raise ConfigurationError(f"wind.directions muss genau 16 Einträge enthalten: {source}")
    except KeyError as exc:
        raise ConfigurationError(f"Pflichtfeld {exc} fehlt in Sprachdatei: {source}") from exc
    except TypeError as exc:
        raise ConfigurationError(f"Ungültige Struktur in Sprachdatei: {source}") from exc

    return LanguageFormatter(
        code=code,
        numbers=NumberRules(
            ones=ones,
            tens=tens,
            compound_order=order,
            compound_separator=str(compound.get("separator", "")),
            compound_overrides=compound_overrides,
            exact_overrides=exact_overrides,
            context_overrides=context_overrides,
            decimal_separator=str(number_raw.get("decimal_separator", ".")),
        ),
        time=TimeRules(
            exact_hour=exact_hour,
            with_minutes=with_minutes,
            minute_prefix_under_ten=str(time_raw.get("minute_prefix_under_ten", "")),
            hour_mode=hour_mode,
        ),
        date=DateRules(pattern=date_pattern, months=months),
        weather_descriptions=weather_descriptions,
        unknown_weather=unknown_weather,
        wind_directions=wind_directions,
    )


def _required_mapping(parent: dict[str, Any], key: str, source: str) -> dict[str, Any]:
    value = parent[key]
    if not isinstance(value, dict):
        raise ConfigurationError(f"'{key}' muss ein Objekt sein: {source}")
    return value


def _integer_words(
    parent: dict[str, Any], key: str, source: str, required: Iterable[int]
) -> dict[int, str]:
    values = _optional_integer_words(parent[key], source)
    missing = [number for number in required if number not in values]
    if missing:
        raise ConfigurationError(f"{key} fehlen Zahlen {missing}: {source}")
    return values


def _optional_integer_words(raw: Any, source: str) -> dict[int, str]:
    if not isinstance(raw, dict):
        raise ConfigurationError(f"Zahlenwörter müssen ein Objekt sein: {source}")
    try:
        return {int(number): str(word) for number, word in raw.items()}
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"Ungültiger Zahlenwert in Sprachdatei: {source}") from exc


def _validated_pattern(raw: Any, allowed: set[str], source: str) -> str:
    pattern = str(raw)
    try:
        fields = {field for _, field, _, _ in Formatter().parse(pattern) if field is not None}
    except ValueError as exc:
        raise ConfigurationError(f"Ungültiges Formatmuster in Sprachdatei: {source}") from exc
    if fields != allowed:
        raise ConfigurationError(
            f"Formatmuster in {source} benötigt genau: {', '.join(sorted(allowed))}"
        )
    return pattern


@lru_cache(maxsize=8)
def builtin_language(code: str) -> LanguageFormatter:
    return LanguageCatalog().get(code)
