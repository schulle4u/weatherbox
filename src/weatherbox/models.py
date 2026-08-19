"""Core domain models for weather forecasts and audio announcements."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any


class AnnouncementKind(StrEnum):
    """Supported announcement schedule types."""

    HALF_HOUR = "half_hour"
    FULL_HOUR = "full_hour"

    @property
    def minute(self) -> int:
        """Return the minute within an hour when the announcement plays."""
        return 30 if self is AnnouncementKind.HALF_HOUR else 0

    @property
    def filename(self) -> str:
        """Return the stable public filename for this announcement kind."""
        return "half-hour.mp3" if self is AnnouncementKind.HALF_HOUR else "full-hour.mp3"

    @property
    def short_name(self) -> str:
        """Return a compact name suitable for generated filenames."""
        return "half" if self is AnnouncementKind.HALF_HOUR else "full"


class AnnouncementStatus(StrEnum):
    """Lifecycle states of a scheduled announcement."""

    SCHEDULED = "SCHEDULED"
    GENERATING = "GENERATING"
    READY = "READY"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True, slots=True)
class WeatherWarning:
    """One official weather warning and its validity period."""

    level: int
    event: str
    headline: str
    start: datetime
    end: datetime | None = None
    description: str | None = None
    instruction: str | None = None
    source: str | None = None

    def is_active(self, target: datetime) -> bool:
        """Return whether the warning is valid at ``target``."""
        return self.start <= target and (self.end is None or target <= self.end)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the warning to JSON-compatible values."""
        return {
            "level": self.level,
            "event": self.event,
            "headline": self.headline,
            "start": self.start.isoformat(),
            "end": self.end.isoformat() if self.end else None,
            "description": self.description,
            "instruction": self.instruction,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WeatherWarning:
        """Create a warning from its serialized dictionary representation."""
        values = dict(data)
        values["start"] = datetime.fromisoformat(values["start"])
        if values.get("end"):
            values["end"] = datetime.fromisoformat(values["end"])
        return cls(**values)


WEATHER_VALUE_FIELDS = (
    "temperature",
    "apparent_temperature",
    "dew_point",
    "humidity",
    "pressure",
    "weather_code",
    "cloud_cover",
    "precipitation",
    "precipitation_probability",
    "wind_speed",
    "wind_direction",
    "wind_gusts",
    "sunrise",
    "sunset",
)


@dataclass(frozen=True, slots=True)
class WeatherData:
    """Weather values associated with a single forecast timestamp."""

    forecast_at: datetime
    temperature: float | None = None
    apparent_temperature: float | None = None
    dew_point: float | None = None
    humidity: float | None = None
    pressure: float | None = None
    weather_code: int | None = None
    cloud_cover: float | None = None
    precipitation: float | None = None
    precipitation_probability: float | None = None
    wind_speed: float | None = None
    wind_direction: float | None = None
    wind_gusts: float | None = None
    sunrise: datetime | None = None
    sunset: datetime | None = None
    warnings: tuple[WeatherWarning, ...] = ()
    data_sources: tuple[tuple[str, str], ...] = ()

    def source_for(self, field_name: str) -> str | None:
        """Return the provider that supplied a weather field."""
        return dict(self.data_sources).get(field_name)

    def with_source(self, source: str) -> WeatherData:
        """Record ``source`` for every populated weather field."""
        sources = tuple(
            (name, source)
            for name in WEATHER_VALUE_FIELDS
            if getattr(self, name) is not None
        )
        return replace(self, data_sources=sources)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the forecast to JSON-compatible values."""
        result: dict[str, Any] = {}
        for name in self.__dataclass_fields__:
            value = getattr(self, name)
            if name == "warnings":
                result[name] = [warning.to_dict() for warning in value]
            elif name == "data_sources":
                result[name] = dict(value)
            else:
                result[name] = value.isoformat() if isinstance(value, datetime) else value
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WeatherData:
        """Create a forecast from its serialized dictionary representation."""
        values = dict(data)
        for name in ("forecast_at", "sunrise", "sunset"):
            if values.get(name):
                values[name] = datetime.fromisoformat(values[name])
        values["warnings"] = tuple(
            WeatherWarning.from_dict(item) for item in values.get("warnings", [])
        )
        raw_sources = values.get("data_sources", {})
        values["data_sources"] = tuple(
            (str(name), str(source)) for name, source in raw_sources.items()
        )
        return cls(**values)


@dataclass(frozen=True, slots=True)
class ForecastBundle:
    """A timestamped collection of individual weather forecasts."""

    fetched_at: datetime
    forecasts: tuple[WeatherData, ...]
    warnings: tuple[WeatherWarning, ...] = ()

    def for_time(self, target: datetime, tolerance_minutes: int = 90) -> WeatherData | None:
        """Return the forecast nearest to ``target`` within the given tolerance."""
        if not self.forecasts:
            return None
        nearest = min(self.forecasts, key=lambda item: abs((item.forecast_at - target).total_seconds()))
        if abs((nearest.forecast_at - target).total_seconds()) > tolerance_minutes * 60:
            return None
        if self.warnings and nearest.warnings != self.warnings:
            return replace(nearest, warnings=self.warnings)
        return nearest


@dataclass(frozen=True, slots=True)
class AnnouncementSpec:
    """Configuration for one announcement kind at a location."""

    enabled: bool
    template: str


@dataclass(frozen=True, slots=True)
class Location:
    """A configured weather location and its announcement preferences."""

    id: str
    name: str
    latitude: float
    longitude: float
    timezone: str
    enabled: bool
    announcements: dict[AnnouncementKind, AnnouncementSpec]
    jingles: dict[AnnouncementKind, Path | None] = field(default_factory=dict)
    language: str = "de"
    dwd_station_id: str | None = None


@dataclass(frozen=True, slots=True)
class ScheduledAnnouncement:
    """An announcement scheduled for a location and playback time."""

    location: Location
    kind: AnnouncementKind
    playback_at: datetime

    @property
    def key(self) -> str:
        """Return the persistent identifier for this scheduled announcement."""
        return f"{self.location.id}:{self.kind.value}:{self.playback_at.isoformat()}"


@dataclass(frozen=True, slots=True)
class AudioAsset:
    """Paths and metadata for a generated and published audio file."""

    location_id: str
    kind: AnnouncementKind
    playback_at: datetime
    versioned_path: Path
    public_path: Path
