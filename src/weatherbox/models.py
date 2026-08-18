from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any


class AnnouncementKind(StrEnum):
    HALF_HOUR = "half_hour"
    FULL_HOUR = "full_hour"

    @property
    def minute(self) -> int:
        return 30 if self is AnnouncementKind.HALF_HOUR else 0

    @property
    def filename(self) -> str:
        return "half-hour.mp3" if self is AnnouncementKind.HALF_HOUR else "full-hour.mp3"

    @property
    def short_name(self) -> str:
        return "half" if self is AnnouncementKind.HALF_HOUR else "full"


class AnnouncementStatus(StrEnum):
    SCHEDULED = "SCHEDULED"
    GENERATING = "GENERATING"
    READY = "READY"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True, slots=True)
class WeatherData:
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

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for name in self.__dataclass_fields__:
            value = getattr(self, name)
            result[name] = value.isoformat() if isinstance(value, datetime) else value
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WeatherData:
        values = dict(data)
        for name in ("forecast_at", "sunrise", "sunset"):
            if values.get(name):
                values[name] = datetime.fromisoformat(values[name])
        return cls(**values)


@dataclass(frozen=True, slots=True)
class ForecastBundle:
    fetched_at: datetime
    forecasts: tuple[WeatherData, ...]

    def for_time(self, target: datetime, tolerance_minutes: int = 90) -> WeatherData | None:
        if not self.forecasts:
            return None
        nearest = min(self.forecasts, key=lambda item: abs((item.forecast_at - target).total_seconds()))
        if abs((nearest.forecast_at - target).total_seconds()) > tolerance_minutes * 60:
            return None
        return nearest


@dataclass(frozen=True, slots=True)
class AnnouncementSpec:
    enabled: bool
    template: str


@dataclass(frozen=True, slots=True)
class Location:
    id: str
    name: str
    latitude: float
    longitude: float
    timezone: str
    enabled: bool
    announcements: dict[AnnouncementKind, AnnouncementSpec]
    jingles: dict[AnnouncementKind, Path | None] = field(default_factory=dict)
    language: str = "de"


@dataclass(frozen=True, slots=True)
class ScheduledAnnouncement:
    location: Location
    kind: AnnouncementKind
    playback_at: datetime

    @property
    def key(self) -> str:
        return f"{self.location.id}:{self.kind.value}:{self.playback_at.isoformat()}"


@dataclass(frozen=True, slots=True)
class AudioAsset:
    location_id: str
    kind: AnnouncementKind
    playback_at: datetime
    versioned_path: Path
    public_path: Path
