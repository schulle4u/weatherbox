"""Load language resources and format values for spoken announcements."""

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
    """Language-specific rules for spelling integers and decimals."""

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
    """Language-specific patterns for spoken times."""

    exact_hour: str
    with_minutes: str
    minute_prefix_under_ten: str
    hour_mode: int


@dataclass(frozen=True, slots=True)
class DateRules:
    """Language-specific date pattern and month names."""

    pattern: str
    months: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GreetingRules:
    """Language-specific greetings for the local time of day."""

    morning: str
    day: str
    evening: str


@dataclass(frozen=True, slots=True)
class DaySummaryRules:
    """Localized sentence patterns for daily weather summaries."""

    weather_with_temperatures: str
    weather_conditions_only: str
    weather_temperatures_only: str
    cloud_clear: str
    cloud_mostly_clear: str
    cloud_partly_cloudy: str
    cloud_mostly_cloudy: str
    cloud_overcast: str
    precipitation_none: str
    precipitation_unlikely: str
    precipitation_possible: str
    precipitation_likely: str
    precipitation_very_likely: str
    precipitation_expected: str
    precipitation_with_amount: str


@dataclass(frozen=True, slots=True)
class LanguageFormatter:
    """Format numbers, dates, times, and weather terms for one language."""

    code: str
    numbers: NumberRules
    time: TimeRules
    date: DateRules
    greetings: GreetingRules
    weather_descriptions: dict[int, str]
    unknown_weather: str
    wind_directions: tuple[str, ...]
    no_active_warning: str
    warning_separator: str
    day_summaries: DaySummaryRules | None

    def format_number(self, number: int, *, context: str | None = None) -> str:
        """Spell an integer from 0 through 59, applying contextual overrides."""
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
        """Format a time according to the language's spoken-time rules."""
        hour = self.format_hour(value.hour)
        if value.minute == 0:
            return self.time.exact_hour.format(hour=hour)
        minute = self.format_number(value.minute, context="minute")
        if value.minute < 10:
            minute = f"{self.time.minute_prefix_under_ten}{minute}"
        return self.time.with_minutes.format(hour=hour, minute=minute)

    def format_hour(self, hour: int) -> str:
        """Spell an hour using the configured 12- or 24-hour mode."""
        display_hour = hour
        if self.time.hour_mode == 12:
            display_hour = hour % 12 or 12
        return self.format_number(display_hour, context="hour")

    def format_date(self, value: datetime) -> str:
        """Format a date using localized month names."""
        return self.date.pattern.format(
            day=value.day,
            month=self.date.months[value.month - 1],
            year=value.year,
        )

    def greeting(self, value: datetime) -> str:
        """Return the greeting for the local hour represented by ``value``."""
        if value.hour < 12:
            return self.greetings.morning
        if value.hour < 18:
            return self.greetings.day
        return self.greetings.evening

    def format_decimal(self, value: float | int | None) -> str | None:
        """Format an optional number with at most one fractional digit."""
        if value is None:
            return None
        rounded = round(float(value), 1)
        if rounded.is_integer():
            return str(int(rounded))
        return f"{rounded:.1f}".replace(".", self.numbers.decimal_separator)

    def weather_description(self, code: int | None) -> str | None:
        """Return the localized description of a WMO weather code."""
        if code is None:
            return None
        return self.weather_descriptions.get(code, self.unknown_weather.format(code=code))

    def wind_direction(self, degrees: float | None) -> str | None:
        """Return the localized compass direction nearest to an angle."""
        if degrees is None:
            return None
        return self.wind_directions[int((degrees % 360) / 22.5 + 0.5) % 16]

    def day_weather_summary(
        self,
        description: str | None,
        temperature_min: str | None,
        temperature_max: str | None,
    ) -> str | None:
        """Build a localized daily conditions and temperature summary."""
        rules = self.day_summaries
        if rules is None:
            return None
        if description is not None and temperature_min is not None and temperature_max is not None:
            return rules.weather_with_temperatures.format(
                description=description,
                temperature_min=temperature_min,
                temperature_max=temperature_max,
            )
        if description is not None:
            return rules.weather_conditions_only.format(description=description)
        if temperature_min is not None and temperature_max is not None:
            return rules.weather_temperatures_only.format(
                temperature_min=temperature_min,
                temperature_max=temperature_max,
            )
        return None

    def day_cloud_summary(self, cloud_cover_mean: float | None) -> str | None:
        """Describe mean daily cloud cover using stable meteorological bands."""
        rules = self.day_summaries
        if rules is None or cloud_cover_mean is None:
            return None
        if cloud_cover_mean <= 10:
            return rules.cloud_clear
        if cloud_cover_mean <= 30:
            return rules.cloud_mostly_clear
        if cloud_cover_mean <= 70:
            return rules.cloud_partly_cloudy
        if cloud_cover_mean <= 90:
            return rules.cloud_mostly_cloudy
        return rules.cloud_overcast

    def day_precipitation_summary(
        self,
        probability_max: float | None,
        precipitation_sum: float | None,
    ) -> str | None:
        """Describe daily precipitation likelihood and an optional total amount."""
        rules = self.day_summaries
        if rules is None:
            return None
        if probability_max is None:
            if precipitation_sum is None:
                return None
            summary = (
                rules.precipitation_none
                if precipitation_sum <= 0
                else rules.precipitation_expected
            )
        elif probability_max <= 10:
            summary = (
                rules.precipitation_unlikely
                if precipitation_sum is not None and precipitation_sum > 0
                else rules.precipitation_none
            )
        elif probability_max <= 30:
            summary = rules.precipitation_unlikely
        elif probability_max <= 60:
            summary = rules.precipitation_possible
        elif probability_max <= 80:
            summary = rules.precipitation_likely
        else:
            summary = rules.precipitation_very_likely
        if precipitation_sum is not None and precipitation_sum > 0:
            return rules.precipitation_with_amount.format(
                summary=summary,
                amount=self.format_decimal(precipitation_sum),
            )
        return summary


class LanguageCatalog:
    """Registry of built-in and optionally user-defined languages."""

    def __init__(self, custom_directory: Path | None = None) -> None:
        """Load built-in languages and optional custom YAML definitions."""
        self._languages: dict[str, LanguageFormatter] = {}
        builtin_directory = resources.files("weatherbox").joinpath("lang")
        self._load_resources(item for item in builtin_directory.iterdir() if item.name.endswith(".yaml"))
        if custom_directory is not None:
            if not custom_directory.is_dir():
                raise ConfigurationError(f"Language directory doesn't exist: {custom_directory}")
            self._load_resources(sorted(custom_directory.glob("*.yaml")))

    @property
    def available(self) -> tuple[str, ...]:
        """Return the available language codes in lexical order."""
        return tuple(sorted(self._languages))

    def get(self, code: str) -> LanguageFormatter:
        """Return the formatter for ``code`` or raise a configuration error."""
        try:
            return self._languages[code]
        except KeyError as exc:
            available = ", ".join(self.available)
            raise ConfigurationError(
                f"Unknown language '{code}'. Available: {available or 'none'}"
            ) from exc

    def _load_resources(self, files: Iterable[Any]) -> None:
        """Load language definitions from an iterable of text resources."""
        for source in files:
            try:
                raw = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
            except (OSError, yaml.YAMLError) as exc:
                raise ConfigurationError(f"Language file cannot be loaded: {source}: {exc}") from exc
            formatter = _parse_language(raw, str(source))
            self._languages[formatter.code] = formatter


def _parse_language(raw: Any, source: str) -> LanguageFormatter:
    """Validate a raw language mapping and build its formatter."""
    if not isinstance(raw, dict):
        raise ConfigurationError(f"Language file must be a YAML object: {source}")
    try:
        code = str(raw["code"])
        number_raw = _required_mapping(raw, "numbers", source)
        ones = _integer_words(number_raw, "ones", source, range(0, 20))
        tens = _integer_words(number_raw, "tens", source, (20, 30, 40, 50))
        compound = _required_mapping(number_raw, "compound", source)
        order = str(compound["order"])
        if order not in {"ones_tens", "tens_ones"}:
            raise ConfigurationError(
                f"numbers.compound.order must be 'ones_tens' or 'tens_ones': {source}"
            )
        compound_overrides = _optional_integer_words(compound.get("ones_overrides", {}), source)
        exact_overrides = _optional_integer_words(number_raw.get("overrides", {}), source)
        context_raw = number_raw.get("context_overrides", {})
        if not isinstance(context_raw, dict):
            raise ConfigurationError(f"numbers.context_overrides must be an object: {source}")
        context_overrides = {
            str(context): _optional_integer_words(values, source)
            for context, values in context_raw.items()
        }

        time_raw = _required_mapping(raw, "time", source)
        exact_hour = _validated_pattern(time_raw["exact_hour"], {"hour"}, source)
        with_minutes = _validated_pattern(time_raw["with_minutes"], {"hour", "minute"}, source)
        hour_mode = int(time_raw.get("hour_mode", 24))
        if hour_mode not in {12, 24}:
            raise ConfigurationError(f"time.hour_mode must be 12 or 24: {source}")
        date_raw = _required_mapping(raw, "date", source)
        date_pattern = _validated_pattern(date_raw["pattern"], {"day", "month", "year"}, source)
        months = tuple(str(value) for value in date_raw["months"])
        if len(months) != 12 or not all(months):
            raise ConfigurationError(f"date.months must contain exactly 12 entries: {source}")

        greetings_raw = _required_mapping(raw, "greetings", source)
        morning_greeting = _required_text(greetings_raw, "morning", source)
        day_greeting = _required_text(greetings_raw, "day", source)
        evening_greeting = _required_text(greetings_raw, "evening", source)

        weather_raw = _required_mapping(raw, "weather", source)
        weather_descriptions = _optional_integer_words(weather_raw["descriptions"], source)
        unknown_weather = _validated_pattern(weather_raw["unknown"], {"code"}, source)
        wind_raw = _required_mapping(raw, "wind", source)
        wind_directions = tuple(str(value) for value in wind_raw["directions"])
        if len(wind_directions) != 16 or not all(wind_directions):
            raise ConfigurationError(f"wind.directions must contain exactly 16 entries: {source}")
        warning_raw = raw.get("warnings", {})
        if not isinstance(warning_raw, dict):
            raise ConfigurationError(f"'warnings' must be an object: {source}")
        day_summaries = _parse_day_summaries(raw.get("summaries"), source)
    except KeyError as exc:
        raise ConfigurationError(f"Required field {exc} is missing in language file: {source}") from exc
    except TypeError as exc:
        raise ConfigurationError(f"Invalid structure in language file: {source}") from exc

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
        greetings=GreetingRules(
            morning=morning_greeting,
            day=day_greeting,
            evening=evening_greeting,
        ),
        weather_descriptions=weather_descriptions,
        unknown_weather=unknown_weather,
        wind_directions=wind_directions,
        no_active_warning=str(warning_raw.get("none", "No active weather warning")),
        warning_separator=str(warning_raw.get("separator", "; ")),
        day_summaries=day_summaries,
    )


def _parse_day_summaries(raw: Any, source: str) -> DaySummaryRules | None:
    """Parse optional localized daily-summary patterns."""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ConfigurationError(f"'summaries' must be an object: {source}")
    weather = _required_mapping(raw, "weather", source)
    cloud = _required_mapping(raw, "cloud", source)
    precipitation = _required_mapping(raw, "precipitation", source)
    try:
        return DaySummaryRules(
            weather_with_temperatures=_validated_pattern(
                weather["with_temperatures"],
                {"description", "temperature_min", "temperature_max"},
                source,
            ),
            weather_conditions_only=_validated_pattern(
                weather["conditions_only"], {"description"}, source
            ),
            weather_temperatures_only=_validated_pattern(
                weather["temperatures_only"],
                {"temperature_min", "temperature_max"},
                source,
            ),
            cloud_clear=_required_text(cloud, "clear", source),
            cloud_mostly_clear=_required_text(cloud, "mostly_clear", source),
            cloud_partly_cloudy=_required_text(cloud, "partly_cloudy", source),
            cloud_mostly_cloudy=_required_text(cloud, "mostly_cloudy", source),
            cloud_overcast=_required_text(cloud, "overcast", source),
            precipitation_none=_required_text(precipitation, "none", source),
            precipitation_unlikely=_required_text(precipitation, "unlikely", source),
            precipitation_possible=_required_text(precipitation, "possible", source),
            precipitation_likely=_required_text(precipitation, "likely", source),
            precipitation_very_likely=_required_text(
                precipitation, "very_likely", source
            ),
            precipitation_expected=_required_text(precipitation, "expected", source),
            precipitation_with_amount=_validated_pattern(
                precipitation["with_amount"], {"summary", "amount"}, source
            ),
        )
    except KeyError as exc:
        raise ConfigurationError(
            f"Required summary field {exc} is missing in language file: {source}"
        ) from exc


def _required_mapping(parent: dict[str, Any], key: str, source: str) -> dict[str, Any]:
    """Return a required mapping from a language definition."""
    value = parent[key]
    if not isinstance(value, dict):
        raise ConfigurationError(f"'{key}' must be an object: {source}")
    return value


def _required_text(parent: dict[str, Any], key: str, source: str) -> str:
    """Return a required non-empty text value from a language definition."""
    value = str(parent[key]).strip()
    if not value:
        raise ConfigurationError(f"'{key}' must not be empty: {source}")
    return value


def _integer_words(
    parent: dict[str, Any], key: str, source: str, required: Iterable[int]
) -> dict[int, str]:
    """Parse an integer-word mapping and verify its required keys."""
    values = _optional_integer_words(parent[key], source)
    missing = [number for number in required if number not in values]
    if missing:
        raise ConfigurationError(f"{key} missing numbers {missing}: {source}")
    return values


def _optional_integer_words(raw: Any, source: str) -> dict[int, str]:
    """Convert a mapping's keys to integers and its values to strings."""
    if not isinstance(raw, dict):
        raise ConfigurationError(f"Number words must be an object: {source}")
    try:
        return {int(number): str(word) for number, word in raw.items()}
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"Invalid number value in language file: {source}") from exc


def _validated_pattern(raw: Any, allowed: set[str], source: str) -> str:
    """Validate that a format pattern uses exactly the allowed fields."""
    pattern = str(raw)
    try:
        fields = {field for _, field, _, _ in Formatter().parse(pattern) if field is not None}
    except ValueError as exc:
        raise ConfigurationError(f"Invalid format pattern in language file: {source}") from exc
    if fields != allowed:
        raise ConfigurationError(
            f"Format pattern in {source} requires exactly: {', '.join(sorted(allowed))}"
        )
    return pattern


@lru_cache(maxsize=8)
def builtin_language(code: str) -> LanguageFormatter:
    """Return a cached formatter loaded from built-in language resources."""
    return LanguageCatalog().get(code)
