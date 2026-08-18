from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

from weatherbox.errors import ConfigurationError
from weatherbox.models import AnnouncementKind, AnnouncementSpec, Location


@dataclass(frozen=True, slots=True)
class ApplicationSettings:
    log_level: str
    json_logs: bool


@dataclass(frozen=True, slots=True)
class WeatherSettings:
    update_interval_minutes: int
    max_cache_age_minutes: int
    request_timeout_seconds: float
    endpoint: str


@dataclass(frozen=True, slots=True)
class RetrySettings:
    interval_seconds: int
    max_attempts: int


@dataclass(frozen=True, slots=True)
class SchedulerSettings:
    preparation_minutes: int
    retry: RetrySettings


@dataclass(frozen=True, slots=True)
class PiperSettings:
    executable: str
    model: Path


@dataclass(frozen=True, slots=True)
class EspeakSettings:
    executable: str
    voice: str
    speed: int


@dataclass(frozen=True, slots=True)
class TTSSettings:
    provider: str
    fallback_provider: str | None
    piper: PiperSettings
    espeak: EspeakSettings


@dataclass(frozen=True, slots=True)
class LoudnessSettings:
    enabled: bool
    target_lufs: float
    true_peak_db: float
    loudness_range: float


@dataclass(frozen=True, slots=True)
class AudioOutputSettings:
    sample_rate: int
    channels: int
    bitrate: str


@dataclass(frozen=True, slots=True)
class AudioSettings:
    ffmpeg: str
    ffprobe: str
    loudness: LoudnessSettings
    output: AudioOutputSettings


@dataclass(frozen=True, slots=True)
class OutputSettings:
    cache_dir: Path
    generated_dir: Path
    public_dir: Path
    state_dir: Path


@dataclass(frozen=True, slots=True)
class Config:
    source_path: Path
    application: ApplicationSettings
    weather: WeatherSettings
    scheduler: SchedulerSettings
    tts: TTSSettings
    audio: AudioSettings
    output: OutputSettings
    locations: dict[str, Location]

    @property
    def enabled_locations(self) -> tuple[Location, ...]:
        return tuple(location for location in self.locations.values() if location.enabled)


def _mapping(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key, {})
    if not isinstance(value, dict):
        raise ConfigurationError(f"'{key}' muss ein YAML-Objekt sein")
    return value


def _positive(value: Any, path: str, *, allow_zero: bool = False) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"'{path}' muss eine Ganzzahl sein") from exc
    minimum = 0 if allow_zero else 1
    if number < minimum:
        raise ConfigurationError(f"'{path}' muss mindestens {minimum} sein")
    return number


def _resolve(base: Path, value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else (base / path).resolve()


def load_config(path: str | Path) -> Config:
    source = Path(path).expanduser().resolve()
    try:
        raw = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    except OSError as exc:
        raise ConfigurationError(f"Konfiguration kann nicht gelesen werden: {source}") from exc
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"Ungültiges YAML in {source}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigurationError("Die YAML-Wurzel muss ein Objekt sein")

    base = source.parent
    app = _mapping(raw, "application")
    weather = _mapping(raw, "weather")
    scheduler = _mapping(raw, "scheduler")
    retry = _mapping(scheduler, "retry")
    tts = _mapping(raw, "tts")
    piper = _mapping(tts, "piper")
    espeak = _mapping(tts, "espeak-ng")
    audio = _mapping(raw, "audio")
    loudness = _mapping(audio, "loudness")
    audio_output = _mapping(audio, "output")
    output = _mapping(raw, "output")

    default_announcements = _mapping(raw, "announcements")
    jingles_section = _mapping(audio, "jingles")
    default_jingles = (
        _mapping(jingles_section, "defaults")
        if "defaults" in jingles_section
        else jingles_section
    )
    locations_raw = _mapping(raw, "locations")
    if not locations_raw:
        raise ConfigurationError("Mindestens ein Standort unter 'locations' ist erforderlich")

    locations: dict[str, Location] = {}
    for location_id, location_raw in locations_raw.items():
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", str(location_id)):
            raise ConfigurationError(
                f"Ungültige Standort-ID '{location_id}'; erlaubt sind Buchstaben, Zahlen, '_' und '-'"
            )
        if not isinstance(location_raw, dict):
            raise ConfigurationError(f"Standort '{location_id}' muss ein Objekt sein")
        try:
            latitude = float(location_raw["latitude"])
            longitude = float(location_raw["longitude"])
            name = str(location_raw["name"])
            timezone = str(location_raw["timezone"])
        except KeyError as exc:
            raise ConfigurationError(f"Standort '{location_id}': Pflichtfeld {exc} fehlt") from exc
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise ConfigurationError(f"Standort '{location_id}': ungültige Koordinaten")
        try:
            ZoneInfo(timezone)
        except ZoneInfoNotFoundError as exc:
            raise ConfigurationError(
                f"Standort '{location_id}': unbekannte Zeitzone '{timezone}'"
            ) from exc

        location_announcements = _mapping(location_raw, "announcements")
        announcement_specs: dict[AnnouncementKind, AnnouncementSpec] = {}
        for kind in AnnouncementKind:
            merged = dict(_mapping(default_announcements, kind.value))
            merged.update(_mapping(location_announcements, kind.value))
            template = merged.get("template")
            if merged.get("enabled", True) and not isinstance(template, str):
                raise ConfigurationError(
                    f"Standort '{location_id}': Template für '{kind.value}' fehlt"
                )
            announcement_specs[kind] = AnnouncementSpec(
                enabled=bool(merged.get("enabled", True)), template=str(template or "")
            )

        location_audio = _mapping(location_raw, "audio")
        location_jingles = _mapping(location_audio, "jingles")
        jingles: dict[AnnouncementKind, Path | None] = {}
        for kind in AnnouncementKind:
            value = location_jingles.get(kind.value, default_jingles.get(kind.value))
            jingles[kind] = _resolve(base, value) if value else None

        locations[str(location_id)] = Location(
            id=str(location_id),
            name=name,
            latitude=latitude,
            longitude=longitude,
            timezone=timezone,
            enabled=bool(location_raw.get("enabled", True)),
            announcements=announcement_specs,
            jingles=jingles,
        )

    provider = str(tts.get("provider", "piper"))
    fallback = tts.get("fallback_provider", "espeak-ng")
    valid_providers = {"piper", "espeak-ng"}
    if provider not in valid_providers or (fallback is not None and fallback not in valid_providers):
        raise ConfigurationError("TTS-Provider muss 'piper' oder 'espeak-ng' sein")

    if str(audio_output.get("format", "mp3")).lower() != "mp3":
        raise ConfigurationError("'audio.output.format' muss 'mp3' sein")
    channels = _positive(audio_output.get("channels", 2), "audio.output.channels")
    if channels != 2:
        raise ConfigurationError("'audio.output.channels' muss für Weatherbox 2 (Stereo) sein")

    return Config(
        source_path=source,
        application=ApplicationSettings(
            log_level=str(app.get("log_level", "INFO")).upper(),
            json_logs=bool(app.get("json_logs", False)),
        ),
        weather=WeatherSettings(
            update_interval_minutes=_positive(weather.get("update_interval_minutes", 30), "weather.update_interval_minutes"),
            max_cache_age_minutes=_positive(weather.get("max_cache_age_minutes", 60), "weather.max_cache_age_minutes"),
            request_timeout_seconds=float(weather.get("request_timeout_seconds", 15)),
            endpoint=str(weather.get("endpoint", "https://api.open-meteo.com/v1/forecast")),
        ),
        scheduler=SchedulerSettings(
            preparation_minutes=_positive(scheduler.get("preparation_minutes", 10), "scheduler.preparation_minutes"),
            retry=RetrySettings(
                interval_seconds=_positive(retry.get("interval_seconds", 60), "scheduler.retry.interval_seconds"),
                max_attempts=_positive(retry.get("max_attempts", 5), "scheduler.retry.max_attempts"),
            ),
        ),
        tts=TTSSettings(
            provider=provider,
            fallback_provider=str(fallback) if fallback is not None else None,
            piper=PiperSettings(
                executable=str(piper.get("executable", "piper")),
                model=_resolve(base, piper.get("model", "models/de_DE-kerstin-low.onnx")),
            ),
            espeak=EspeakSettings(
                executable=str(espeak.get("executable", "espeak-ng")),
                voice=str(espeak.get("voice", "de")),
                speed=_positive(espeak.get("speed", 155), "tts.espeak-ng.speed"),
            ),
        ),
        audio=AudioSettings(
            ffmpeg=str(audio.get("ffmpeg", "ffmpeg")),
            ffprobe=str(audio.get("ffprobe", "ffprobe")),
            loudness=LoudnessSettings(
                enabled=bool(loudness.get("enabled", True)),
                target_lufs=float(loudness.get("target_lufs", -16)),
                true_peak_db=float(loudness.get("true_peak_db", -1.5)),
                loudness_range=float(loudness.get("loudness_range", 11)),
            ),
            output=AudioOutputSettings(
                sample_rate=_positive(audio_output.get("sample_rate", 48000), "audio.output.sample_rate"),
                channels=channels,
                bitrate=str(audio_output.get("bitrate", "192k")),
            ),
        ),
        output=OutputSettings(
            cache_dir=_resolve(base, output.get("cache_dir", "var/cache")),
            generated_dir=_resolve(base, output.get("generated_dir", "var/generated")),
            public_dir=_resolve(base, output.get("public_dir", "var/public")),
            state_dir=_resolve(base, output.get("state_dir", "var/state")),
        ),
        locations=locations,
    )
