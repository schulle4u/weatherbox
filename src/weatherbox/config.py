"""Load and validate Weatherbox YAML configuration."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

from weatherbox.errors import ConfigurationError
from weatherbox.localization import LanguageCatalog
from weatherbox.models import (
    WEATHER_VALUE_FIELDS,
    AnnouncementKind,
    AnnouncementSpec,
    Location,
)


WEATHER_PROVIDER_ENDPOINTS = {
    "open-meteo": "https://api.open-meteo.com/v1/forecast",
    "dwd": "https://app-prod-ws.warnwetter.de/v30/stationOverviewExtended",
}


@dataclass(frozen=True, slots=True)
class ApplicationSettings:
    """Application-wide logging settings."""

    log_level: str
    json_logs: bool


@dataclass(frozen=True, slots=True)
class LocalizationSettings:
    """Language defaults and optional custom resource location."""

    default_language: str
    directory: Path | None


@dataclass(frozen=True, slots=True)
class WeatherProviderSettings:
    """Connection settings for one weather provider."""

    name: str
    endpoint: str
    request_timeout_seconds: float


@dataclass(frozen=True, slots=True)
class WeatherMergeSettings:
    """Rules for aligning and merging provider data."""

    tolerance_minutes: int
    default_priority: tuple[str, ...]
    field_priority: dict[str, tuple[str, ...]]


@dataclass(frozen=True, slots=True)
class WeatherSettings:
    """Weather providers, merge rules, and cache freshness settings."""

    update_interval_minutes: int
    max_cache_age_minutes: int
    providers: tuple[WeatherProviderSettings, ...]
    merge: WeatherMergeSettings

    @property
    def provider(self) -> str:
        """Return the first provider name for legacy callers."""
        return self.providers[0].name

    @property
    def endpoint(self) -> str:
        """Return the first provider endpoint for legacy callers."""
        return self.providers[0].endpoint

    @property
    def request_timeout_seconds(self) -> float:
        """Return the first provider timeout for legacy callers."""
        return self.providers[0].request_timeout_seconds


@dataclass(frozen=True, slots=True)
class RetrySettings:
    """Retry interval and attempt limit for failed announcements."""

    interval_seconds: int
    max_attempts: int


@dataclass(frozen=True, slots=True)
class SchedulerSettings:
    """Announcement preparation window and retry policy."""

    preparation_minutes: int
    retry: RetrySettings


@dataclass(frozen=True, slots=True)
class PiperSettings:
    """Piper executable and voice model settings."""

    executable: str
    model: Path


@dataclass(frozen=True, slots=True)
class EspeakSettings:
    """eSpeak NG executable, voice, and speech rate settings."""

    executable: str
    voice: str
    speed: int


@dataclass(frozen=True, slots=True)
class GTTSSettings:
    """Google Translate TTS language, host, and request settings."""

    language: str
    tld: str
    slow: bool
    timeout_seconds: float


@dataclass(frozen=True, slots=True)
class TTSSettings:
    """Text-to-speech providers and language-specific overrides."""

    provider: str
    fallback_provider: str | None
    piper: PiperSettings
    espeak: EspeakSettings
    gtts: GTTSSettings
    languages: dict[str, "TTSLanguageSettings"]


@dataclass(frozen=True, slots=True)
class TTSLanguageSettings:
    """Optional provider overrides for a single language."""

    piper_model: Path | None
    espeak_voice: str | None
    gtts_language: str | None
    gtts_tld: str | None


@dataclass(frozen=True, slots=True)
class LoudnessSettings:
    """Target values for optional loudness normalization."""

    enabled: bool
    target_lufs: float
    true_peak_db: float
    loudness_range: float


@dataclass(frozen=True, slots=True)
class AudioOutputSettings:
    """Encoding settings for generated MP3 files."""

    sample_rate: int
    channels: int
    bitrate: str


@dataclass(frozen=True, slots=True)
class AudioSettings:
    """Audio tool locations, normalization, and output settings."""

    ffmpeg: str
    ffprobe: str
    loudness: LoudnessSettings
    output: AudioOutputSettings


@dataclass(frozen=True, slots=True)
class OutputSettings:
    """Filesystem destinations for caches, assets, and state."""

    cache_dir: Path
    generated_dir: Path
    public_dir: Path
    state_dir: Path


@dataclass(frozen=True, slots=True)
class Config:
    """Fully validated Weatherbox configuration."""

    source_path: Path
    application: ApplicationSettings
    localization: LocalizationSettings
    weather: WeatherSettings
    scheduler: SchedulerSettings
    tts: TTSSettings
    audio: AudioSettings
    output: OutputSettings
    locations: dict[str, Location]

    @property
    def enabled_locations(self) -> tuple[Location, ...]:
        """Return all locations enabled for announcement generation."""
        return tuple(location for location in self.locations.values() if location.enabled)


def _mapping(data: dict[str, Any], key: str) -> dict[str, Any]:
    """Return a configuration section and ensure it is a mapping."""
    value = data.get(key, {})
    if not isinstance(value, dict):
        raise ConfigurationError(f"'{key}' must be a YAML object")
    return value


def _positive(value: Any, path: str, *, allow_zero: bool = False) -> int:
    """Parse and validate a positive configuration integer."""
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"'{path}' must be an integer") from exc
    minimum = 0 if allow_zero else 1
    if number < minimum:
        raise ConfigurationError(f"'{path}' must be at least {minimum}")
    return number


def _positive_float(value: Any, path: str) -> float:
    """Parse and validate a positive configuration number."""
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"'{path}' must be a number") from exc
    if number <= 0:
        raise ConfigurationError(f"'{path}' must be greater than zero")
    return number


def _resolve(base: Path, value: str | Path) -> Path:
    """Resolve a configured path relative to the configuration directory."""
    path = Path(value).expanduser()
    return path if path.is_absolute() else (base / path).resolve()


def _weather_priority(
    raw: Any,
    path: str,
    configured: tuple[str, ...],
) -> tuple[str, ...]:
    """Validate a provider priority and append omitted providers as fallbacks."""
    if not isinstance(raw, list) or not raw:
        raise ConfigurationError(f"'{path}' must be a non-empty YAML list")
    priority = tuple(str(value).lower() for value in raw)
    if len(set(priority)) != len(priority):
        raise ConfigurationError(f"'{path}' must not contain duplicate providers")
    unknown = set(priority) - set(configured)
    if unknown:
        raise ConfigurationError(
            f"'{path}' references unconfigured providers: {', '.join(sorted(unknown))}"
        )
    return priority + tuple(name for name in configured if name not in priority)


def _weather_settings(raw: dict[str, Any]) -> WeatherSettings:
    """Parse legacy or multi-provider weather configuration."""
    global_timeout = _positive_float(
        raw.get("request_timeout_seconds", 15), "weather.request_timeout_seconds"
    )
    providers: list[WeatherProviderSettings] = []
    if "providers" in raw:
        if "provider" in raw or "endpoint" in raw:
            raise ConfigurationError(
                "Use either 'weather.provider'/'weather.endpoint' or 'weather.providers'"
            )
        providers_raw = raw["providers"]
        if isinstance(providers_raw, list):
            entries = [(str(name), {}) for name in providers_raw]
        elif isinstance(providers_raw, dict):
            entries = []
            for name, options in providers_raw.items():
                if options is None:
                    options = {}
                if not isinstance(options, dict):
                    raise ConfigurationError(
                        f"'weather.providers.{name}' must be a YAML object"
                    )
                entries.append((str(name), options))
        else:
            raise ConfigurationError(
                "'weather.providers' must be a YAML list or object"
            )
        if not entries:
            raise ConfigurationError("At least one weather provider is required")
        for raw_name, options in entries:
            name = raw_name.lower()
            if name not in WEATHER_PROVIDER_ENDPOINTS:
                raise ConfigurationError(
                    f"Unknown weather provider '{raw_name}'; expected 'open-meteo' or 'dwd'"
                )
            providers.append(
                WeatherProviderSettings(
                    name=name,
                    endpoint=str(options.get("endpoint", WEATHER_PROVIDER_ENDPOINTS[name])),
                    request_timeout_seconds=_positive_float(
                        options.get("request_timeout_seconds", global_timeout),
                        f"weather.providers.{name}.request_timeout_seconds",
                    ),
                )
            )
    else:
        name = str(raw.get("provider", "open-meteo")).lower()
        if name not in WEATHER_PROVIDER_ENDPOINTS:
            raise ConfigurationError("Weather provider must be 'open-meteo' or 'dwd'")
        providers.append(
            WeatherProviderSettings(
                name=name,
                endpoint=str(raw.get("endpoint", WEATHER_PROVIDER_ENDPOINTS[name])),
                request_timeout_seconds=global_timeout,
            )
        )

    provider_names = tuple(provider.name for provider in providers)
    if len(set(provider_names)) != len(provider_names):
        raise ConfigurationError("'weather.providers' must not contain duplicates")
    merge_raw = _mapping(raw, "merge")
    default_priority = _weather_priority(
        merge_raw.get("default_priority", list(provider_names)),
        "weather.merge.default_priority",
        provider_names,
    )
    field_priority_raw = _mapping(merge_raw, "field_priority")
    valid_fields = set(WEATHER_VALUE_FIELDS) | {"warnings"}
    unknown_fields = set(field_priority_raw) - valid_fields
    if unknown_fields:
        raise ConfigurationError(
            "Unknown weather merge fields: " + ", ".join(sorted(unknown_fields))
        )
    field_priority = {
        str(field): _weather_priority(
            value, f"weather.merge.field_priority.{field}", provider_names
        )
        for field, value in field_priority_raw.items()
    }
    return WeatherSettings(
        update_interval_minutes=_positive(
            raw.get("update_interval_minutes", 30), "weather.update_interval_minutes"
        ),
        max_cache_age_minutes=_positive(
            raw.get("max_cache_age_minutes", 60), "weather.max_cache_age_minutes"
        ),
        providers=tuple(providers),
        merge=WeatherMergeSettings(
            tolerance_minutes=_positive(
                merge_raw.get("tolerance_minutes", 30),
                "weather.merge.tolerance_minutes",
            ),
            default_priority=default_priority,
            field_priority=field_priority,
        ),
    )


def load_config(path: str | Path) -> Config:
    """Load a YAML file and return its validated application configuration."""
    source = Path(path).expanduser().resolve()
    try:
        raw = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    except OSError as exc:
        raise ConfigurationError(f"Configuration cannot be read: {source}") from exc
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"Invalid YAML in {source}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigurationError("YAML root must be an object")

    base = source.parent
    app = _mapping(raw, "application")
    localization = _mapping(raw, "localization")
    weather = _mapping(raw, "weather")
    weather_settings = _weather_settings(weather)
    scheduler = _mapping(raw, "scheduler")
    retry = _mapping(scheduler, "retry")
    tts = _mapping(raw, "tts")
    piper = _mapping(tts, "piper")
    espeak = _mapping(tts, "espeak-ng")
    gtts = _mapping(tts, "gtts")
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
        raise ConfigurationError("At least one entry is required at 'locations'")

    default_language = str(localization.get("default_language", "de"))
    language_directory_value = localization.get("directory")
    language_directory = (
        _resolve(base, language_directory_value) if language_directory_value else None
    )
    language_catalog = LanguageCatalog(language_directory)
    language_catalog.get(default_language)

    locations: dict[str, Location] = {}
    for location_id, location_raw in locations_raw.items():
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", str(location_id)):
            raise ConfigurationError(
                f"Invalid location ID '{location_id}'; only letters, numbers, '_' and '-' are allowed"
            )
        if not isinstance(location_raw, dict):
            raise ConfigurationError(f"Location '{location_id}' must be an object")
        try:
            latitude = float(location_raw["latitude"])
            longitude = float(location_raw["longitude"])
            name = str(location_raw["name"])
            timezone = str(location_raw["timezone"])
        except KeyError as exc:
            raise ConfigurationError(f"Location '{location_id}': required field {exc} is missing") from exc
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise ConfigurationError(f"Location '{location_id}': invalid coordinates")
        try:
            ZoneInfo(timezone)
        except ZoneInfoNotFoundError as exc:
            raise ConfigurationError(
                f"Location '{location_id}': unknown time zone '{timezone}'"
            ) from exc
        language = str(location_raw.get("language", default_language))
        language_catalog.get(language)

        location_announcements = _mapping(location_raw, "announcements")
        announcement_specs: dict[AnnouncementKind, AnnouncementSpec] = {}
        for kind in AnnouncementKind:
            merged = dict(_mapping(default_announcements, kind.value))
            merged.update(_mapping(location_announcements, kind.value))
            template = merged.get("template")
            if merged.get("enabled", True) and not isinstance(template, str):
                raise ConfigurationError(
                    f"Location '{location_id}': Template for '{kind.value}' is missing"
                )
            announcement_specs[kind] = AnnouncementSpec(
                enabled=bool(merged.get("enabled", True)), template=str(template or "")
            )

        location_audio = _mapping(location_raw, "audio")
        location_weather = _mapping(location_raw, "weather")
        dwd_station_value = location_weather.get("dwd_station_id")
        dwd_station_id = str(dwd_station_value) if dwd_station_value is not None else None
        if dwd_station_id is not None and not re.fullmatch(r"[A-Za-z0-9]+", dwd_station_id):
            raise ConfigurationError(
                f"Location '{location_id}': invalid DWD station ID '{dwd_station_id}'"
            )
        dwd_enabled = any(
            provider.name == "dwd" for provider in weather_settings.providers
        )
        if dwd_enabled and bool(location_raw.get("enabled", True)) and not dwd_station_id:
            raise ConfigurationError(
                f"Location '{location_id}': weather.dwd_station_id is required for DWD"
            )
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
            language=language,
            dwd_station_id=dwd_station_id,
        )

    provider = str(tts.get("provider", "piper"))
    fallback = tts.get("fallback_provider", "espeak-ng")
    valid_providers = {"piper", "espeak-ng", "gtts"}
    if provider not in valid_providers or (fallback is not None and fallback not in valid_providers):
        raise ConfigurationError("TTS provider must be 'piper', 'espeak-ng', or 'gtts'")

    tts_languages_raw = _mapping(tts, "languages")
    tts_languages: dict[str, TTSLanguageSettings] = {}
    for language_code, override_raw in tts_languages_raw.items():
        language_catalog.get(str(language_code))
        if not isinstance(override_raw, dict):
            raise ConfigurationError(f"tts.languages.{language_code} must be an object")
        piper_override = _mapping(override_raw, "piper")
        espeak_override = _mapping(override_raw, "espeak-ng")
        gtts_override = _mapping(override_raw, "gtts")
        model_value = piper_override.get("model")
        voice_value = espeak_override.get("voice")
        gtts_language_value = gtts_override.get("language")
        gtts_tld_value = gtts_override.get("tld")
        tts_languages[str(language_code)] = TTSLanguageSettings(
            piper_model=_resolve(base, model_value) if model_value else None,
            espeak_voice=str(voice_value) if voice_value else None,
            gtts_language=str(gtts_language_value) if gtts_language_value else None,
            gtts_tld=str(gtts_tld_value) if gtts_tld_value else None,
        )

    if str(audio_output.get("format", "mp3")).lower() != "mp3":
        raise ConfigurationError("'audio.output.format' must be 'mp3'")
    channels = _positive(audio_output.get("channels", 2), "audio.output.channels")
    if channels != 2:
        raise ConfigurationError("'audio.output.channels' must be 2 (stereo)")

    return Config(
        source_path=source,
        application=ApplicationSettings(
            log_level=str(app.get("log_level", "INFO")).upper(),
            json_logs=bool(app.get("json_logs", False)),
        ),
        localization=LocalizationSettings(
            default_language=default_language,
            directory=language_directory,
        ),
        weather=weather_settings,
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
            gtts=GTTSSettings(
                language=str(gtts.get("language", default_language)),
                tld=str(gtts.get("tld", "com")),
                slow=bool(gtts.get("slow", False)),
                timeout_seconds=_positive_float(
                    gtts.get("timeout_seconds", 15), "tts.gtts.timeout_seconds"
                ),
            ),
            languages=tts_languages,
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
