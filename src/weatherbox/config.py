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
    JingleAssets,
    Location,
    TemperatureUnit,
)


WEATHER_PROVIDER_ENDPOINTS = {
    "open-meteo": "https://api.open-meteo.com/v1/forecast",
    "dwd": "https://app-prod-ws.warnwetter.de/v30/stationOverviewExtended",
}

AUDIO_FORMAT_SPECS = {
    "mp3": ("mp3", "libmp3lame", "mp3", "192k"),
    "wav": ("wav", "pcm_s16le", "wav", None),
    "flac": ("flac", "flac", "flac", None),
    "ogg": ("ogg", "libvorbis", "ogg", "192k"),
    "opus": ("opus", "libopus", "opus", "128k"),
    "m4a": ("m4a", "aac", "ipod", "192k"),
}
AUDIO_FORMAT_ALIASES = {"vorbis": "ogg", "aac": "m4a"}


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
class AudioFormatSettings:
    """FFmpeg encoding settings for one published audio format."""

    name: str
    extension: str
    codec: str
    container: str
    bitrate: str | None


@dataclass(frozen=True, slots=True)
class AudioOutputSettings:
    """Common and format-specific settings for generated audio files."""

    sample_rate: int
    channels: int
    bitrate: str = "192k"
    formats: tuple[AudioFormatSettings, ...] = (
        AudioFormatSettings("mp3", "mp3", "libmp3lame", "mp3", "192k"),
    )

    def format_for_extension(self, extension: str) -> AudioFormatSettings:
        """Return the configured format matching a filename extension."""
        normalized = extension.lower().lstrip(".")
        for audio_format in self.formats:
            if audio_format.extension == normalized:
                return audio_format
        raise ValueError(f"No configured audio format uses '.{normalized}'")


@dataclass(frozen=True, slots=True)
class AudioSettings:
    """Audio tool locations, normalization, and output settings."""

    ffmpeg: str
    ffprobe: str
    loudness: LoudnessSettings
    output: AudioOutputSettings
    music_attenuation_db: float = -10.0
    music_fade_out_seconds: float = 2.5
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class TextAssetSettings:
    """Static HTML announcement output settings."""

    enabled: bool
    template: Path | None


@dataclass(frozen=True, slots=True)
class OutputSettings:
    """Filesystem destinations and generated asset retention settings."""

    cache_dir: Path
    generated_dir: Path
    generated_retention_days: int | None
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
    text: TextAssetSettings
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


def _number(value: Any, path: str) -> float:
    """Parse a finite configuration number."""
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"'{path}' must be a number") from exc
    if not -float("inf") < number < float("inf"):
        raise ConfigurationError(f"'{path}' must be a finite number")
    return number


def _resolve(base: Path, value: str | Path) -> Path:
    """Resolve a configured path relative to the configuration directory."""
    path = Path(value).expanduser()
    return path if path.is_absolute() else (base / path).resolve()


def _audio_formats(raw: dict[str, Any]) -> tuple[AudioFormatSettings, ...]:
    """Parse short or per-format audio output configuration."""
    if "format" in raw and "formats" in raw:
        raise ConfigurationError(
            "Configure either 'audio.output.format' or 'audio.output.formats', not both"
        )

    individual_options: dict[str, Any] = {}
    if "formats" in raw:
        formats_raw = raw["formats"]
        if not isinstance(formats_raw, dict) or not formats_raw:
            raise ConfigurationError(
                "'audio.output.formats' must be a non-empty YAML object"
            )
        raw_names = list(formats_raw)
        individual_options = formats_raw
    else:
        short = raw.get("format", "mp3")
        if isinstance(short, str):
            raw_names = [name.strip() for name in short.split(",") if name.strip()]
        elif isinstance(short, list):
            raw_names = list(short)
        else:
            raise ConfigurationError(
                "'audio.output.format' must be a format name, comma-separated names, or a YAML list"
            )
        if not raw_names:
            raise ConfigurationError("At least one audio output format is required")

    global_bitrate = str(raw["bitrate"]) if raw.get("bitrate") is not None else None
    formats: list[AudioFormatSettings] = []
    seen: set[str] = set()
    for raw_name in raw_names:
        name = str(raw_name).strip().lower()
        name = AUDIO_FORMAT_ALIASES.get(name, name)
        if name not in AUDIO_FORMAT_SPECS:
            supported = ", ".join(AUDIO_FORMAT_SPECS)
            raise ConfigurationError(
                f"Unknown audio output format '{raw_name}'; expected one of: {supported}"
            )
        if name in seen:
            raise ConfigurationError(
                f"Audio output format '{name}' is configured more than once"
            )
        seen.add(name)

        options = individual_options.get(raw_name, {})
        if options is None:
            options = {}
        if not isinstance(options, dict):
            raise ConfigurationError(
                f"'audio.output.formats.{raw_name}' must be a YAML object"
            )
        _reject_unknown_keys(
            options, {"bitrate"}, f"audio.output.formats.{raw_name}"
        )
        extension, codec, container, default_bitrate = AUDIO_FORMAT_SPECS[name]
        if default_bitrate is None and options.get("bitrate") is not None:
            raise ConfigurationError(
                f"'audio.output.formats.{raw_name}.bitrate' is not valid for lossless format '{name}'"
            )
        configured_bitrate = options.get("bitrate", global_bitrate)
        bitrate = (
            None
            if default_bitrate is None
            else str(configured_bitrate or default_bitrate)
        )
        formats.append(
            AudioFormatSettings(name, extension, codec, container, bitrate)
        )
    return tuple(formats)


def _reject_unknown_keys(
    raw: dict[str, Any], allowed: set[str], path: str
) -> None:
    """Reject misspelled or obsolete configuration keys."""
    unknown = set(raw) - allowed
    if unknown:
        raise ConfigurationError(
            f"Unknown settings at '{path}': {', '.join(sorted(unknown))}"
        )


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
    """Parse weather providers and their merge configuration."""
    _reject_unknown_keys(
        raw,
        {
            "providers",
            "merge",
            "update_interval_minutes",
            "max_cache_age_minutes",
            "request_timeout_seconds",
        },
        "weather",
    )
    global_timeout = _positive_float(
        raw.get("request_timeout_seconds", 15), "weather.request_timeout_seconds"
    )
    providers_raw = raw.get("providers")
    if not isinstance(providers_raw, dict) or not providers_raw:
        raise ConfigurationError(
            "'weather.providers' must be a non-empty YAML object"
        )

    providers: list[WeatherProviderSettings] = []
    for raw_name, options in providers_raw.items():
        if options is None:
            options = {}
        if not isinstance(options, dict):
            raise ConfigurationError(
                f"'weather.providers.{raw_name}' must be a YAML object"
            )
        name = str(raw_name).lower()
        if name not in WEATHER_PROVIDER_ENDPOINTS:
            raise ConfigurationError(
                f"Unknown weather provider '{raw_name}'; expected 'open-meteo' or 'dwd'"
            )
        _reject_unknown_keys(
            options,
            {"endpoint", "request_timeout_seconds"},
            f"weather.providers.{name}",
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

    provider_names = tuple(provider.name for provider in providers)
    if len(set(provider_names)) != len(provider_names):
        raise ConfigurationError("'weather.providers' must not contain duplicates")
    merge_raw = _mapping(raw, "merge")
    _reject_unknown_keys(
        merge_raw,
        {"tolerance_minutes", "default_priority", "field_priority"},
        "weather.merge",
    )
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
    text_assets = _mapping(raw, "text")
    _reject_unknown_keys(text_assets, {"enabled", "template"}, "text")
    text_template_value = text_assets.get("template")
    text_template = (
        _resolve(base, text_template_value) if text_template_value else None
    )
    if text_assets.get("enabled", False) and text_template is not None:
        if not text_template.is_file():
            raise ConfigurationError(
                f"Text asset template does not exist: {text_template}"
            )
    loudness = _mapping(audio, "loudness")
    audio_output = _mapping(audio, "output")
    output = _mapping(raw, "output")
    _reject_unknown_keys(
        output,
        {
            "cache_dir",
            "generated_dir",
            "generated_retention_days",
            "public_dir",
            "state_dir",
        },
        "output",
    )

    default_announcements = _mapping(raw, "announcements")
    jingles_section = _mapping(audio, "jingles")
    _reject_unknown_keys(
        jingles_section,
        {kind.value for kind in AnnouncementKind}
        | {"music_attenuation", "music_fade_out"},
        "audio.jingles",
    )
    default_jingles: dict[AnnouncementKind, dict[str, Any]] = {}
    for kind in AnnouncementKind:
        values = _mapping(jingles_section, kind.value)
        _reject_unknown_keys(
            values, {"intro", "outro", "music"}, f"audio.jingles.{kind.value}"
        )
        default_jingles[kind] = values

    music_attenuation = _number(
        jingles_section.get("music_attenuation", -10),
        "audio.jingles.music_attenuation",
    )
    if music_attenuation > 0:
        raise ConfigurationError(
            "'audio.jingles.music_attenuation' must be zero or negative"
        )
    music_fade_out = _number(
        jingles_section.get("music_fade_out", 2.5),
        "audio.jingles.music_fade_out",
    )
    if music_fade_out < 0:
        raise ConfigurationError(
            "'audio.jingles.music_fade_out' must be zero or positive"
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
        raw_temperature_unit = str(
            location_raw.get("temperature_unit", TemperatureUnit.CELSIUS.value)
        ).lower()
        try:
            temperature_unit = TemperatureUnit(raw_temperature_unit)
        except ValueError as exc:
            raise ConfigurationError(
                f"Location '{location_id}': temperature_unit must be 'c' or 'f'"
            ) from exc

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
        _reject_unknown_keys(
            location_jingles,
            {kind.value for kind in AnnouncementKind},
            f"locations.{location_id}.audio.jingles",
        )
        jingles: dict[AnnouncementKind, JingleAssets] = {}
        for kind in AnnouncementKind:
            override = _mapping(location_jingles, kind.value)
            _reject_unknown_keys(
                override,
                {"intro", "outro", "music"},
                f"locations.{location_id}.audio.jingles.{kind.value}",
            )
            values = dict(default_jingles[kind])
            values.update(override)
            jingles[kind] = JingleAssets(
                intro=_resolve(base, values["intro"]) if values.get("intro") else None,
                outro=_resolve(base, values["outro"]) if values.get("outro") else None,
                music=_resolve(base, values["music"]) if values.get("music") else None,
            )

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
            temperature_unit=temperature_unit,
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

    _reject_unknown_keys(
        audio_output,
        {"format", "formats", "sample_rate", "channels", "bitrate"},
        "audio.output",
    )
    audio_formats = _audio_formats(audio_output)
    audio_enabled = bool(audio.get("enabled", True))
    text_enabled = bool(text_assets.get("enabled", False))
    if not audio_enabled and not text_enabled:
        raise ConfigurationError(
            "At least one asset output must be enabled under 'audio' or 'text'"
        )
    sample_rate = _positive(
        audio_output.get("sample_rate", 48000), "audio.output.sample_rate"
    )
    if any(item.name == "opus" for item in audio_formats) and sample_rate not in {
        8000,
        12000,
        16000,
        24000,
        48000,
    }:
        raise ConfigurationError(
            "'audio.output.sample_rate' must be 8000, 12000, 16000, 24000, "
            "or 48000 when Opus output is enabled"
        )
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
            enabled=audio_enabled,
            ffmpeg=str(audio.get("ffmpeg", "ffmpeg")),
            ffprobe=str(audio.get("ffprobe", "ffprobe")),
            loudness=LoudnessSettings(
                enabled=bool(loudness.get("enabled", True)),
                target_lufs=float(loudness.get("target_lufs", -16)),
                true_peak_db=float(loudness.get("true_peak_db", -1.5)),
                loudness_range=float(loudness.get("loudness_range", 11)),
            ),
            output=AudioOutputSettings(
                sample_rate=sample_rate,
                channels=channels,
                bitrate=str(audio_output.get("bitrate", "192k")),
                formats=audio_formats,
            ),
            music_attenuation_db=music_attenuation,
            music_fade_out_seconds=music_fade_out,
        ),
        text=TextAssetSettings(enabled=text_enabled, template=text_template),
        output=OutputSettings(
            cache_dir=_resolve(base, output.get("cache_dir", "var/cache")),
            generated_dir=_resolve(base, output.get("generated_dir", "var/generated")),
            generated_retention_days=(
                _positive(
                    output["generated_retention_days"],
                    "output.generated_retention_days",
                )
                if output.get("generated_retention_days") is not None
                else None
            ),
            public_dir=_resolve(base, output.get("public_dir", "var/public")),
            state_dir=_resolve(base, output.get("state_dir", "var/state")),
        ),
        locations=locations,
    )
