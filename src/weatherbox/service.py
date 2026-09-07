"""Coordinate weather retrieval, speech generation, and asset publication."""

from __future__ import annotations

import logging
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo

from weatherbox.assets import AssetManager
from weatherbox.audio import AudioPipeline
from weatherbox.config import Config
from weatherbox.errors import WeatherUnavailableError, WeatherboxError
from weatherbox.localization import LanguageCatalog
from weatherbox.models import (
    AnnouncementKind,
    AnnouncementStatus,
    AudioAsset,
    Location,
    ScheduledAnnouncement,
    WeatherData,
)
from weatherbox.scheduler import Scheduler, next_playback
from weatherbox.state import StateStore
from weatherbox.templates import (
    DEFAULT_TEXT_ASSET_TEMPLATE,
    build_context,
    render_template,
    render_text_asset,
)
from weatherbox.tts import FallbackTTSProvider, create_tts_provider
from weatherbox.weather import WeatherCache, create_weather_provider
from weatherbox.weather.base import WeatherProvider


LOG = logging.getLogger(__name__)


class WeatherboxService:
    """Orchestrate the complete weather announcement workflow."""

    def __init__(
        self,
        config: Config,
        *,
        weather_provider: WeatherProvider | None = None,
        tts_provider: FallbackTTSProvider | None = None,
        audio_pipeline: AudioPipeline | None = None,
        now_fn=None,
    ) -> None:
        """Initialize services, using injected adapters where provided."""
        self.config = config
        self.now_fn = now_fn or (lambda: datetime.now().astimezone())
        self.weather_provider = weather_provider or create_weather_provider(config.weather)
        self.weather_cache = WeatherCache(config.output.cache_dir)
        self.languages = LanguageCatalog(config.localization.directory)
        self._injected_tts_provider = tts_provider
        self._tts_providers: dict[str, FallbackTTSProvider] = {}
        self.tts_provider = tts_provider
        if config.audio.enabled:
            self.tts_provider = tts_provider or self._tts_for_language(
                config.localization.default_language
            )
        self.audio = audio_pipeline or (
            AudioPipeline(config.audio) if config.audio.enabled else None
        )
        self.assets = AssetManager(config.output.generated_dir, config.output.public_dir)
        self.state = StateStore(config.output.state_dir / "announcements.json")
        self.scheduler = Scheduler(config.scheduler, self.state)

    def update_weather(self, locations: Iterable[Location] | None = None) -> dict[str, bool]:
        """Refresh weather caches and report success for each location."""
        results: dict[str, bool] = {}
        for location in locations or self.config.enabled_locations:
            LOG.info("Weather update started", extra={"location_id": location.id})
            try:
                bundle = self.weather_provider.fetch(location)
                self.weather_cache.save(location.id, bundle)
                results[location.id] = True
                LOG.info("Weather data updated", extra={"location_id": location.id})
            except Exception as exc:
                results[location.id] = False
                LOG.error("Weather update failed", extra={"location_id": location.id, "error": str(exc)})
        return results

    def get_weather(self, location: Location, playback_at: datetime) -> WeatherData:
        """Return a suitable forecast, refreshing or falling back to cache as needed."""
        now = self.now_fn()
        cached = self.weather_cache.load(location.id)
        update_due = not cached or not self.weather_cache.is_fresh(
            cached, now, self.config.weather.update_interval_minutes
        )
        if update_due:
            try:
                fresh = self.weather_provider.fetch(location)
                self.weather_cache.save(location.id, fresh)
                cached = fresh
                # Fetching may take long enough that the new bundle's timestamp
                # is later than the value captured before the request.  Use a
                # current reference time for the final freshness check.
                now = self.now_fn()
                LOG.info("Weather data updated", extra={"location_id": location.id})
            except Exception as exc:
                if cached and self.weather_cache.is_fresh(
                    cached, now, self.config.weather.max_cache_age_minutes
                ):
                    LOG.warning(
                        "Weather provider unavailable; using valid cache",
                        extra={"location_id": location.id, "error": str(exc)},
                    )
                else:
                    raise WeatherUnavailableError(
                        f"Not enough recent weather data for {location.id}: {exc}"
                    ) from exc
        if not cached or not self.weather_cache.is_fresh(
            cached, now, self.config.weather.max_cache_age_minutes
        ):
            raise WeatherUnavailableError(f"Weather cache for {location.id} is too old")
        forecast = cached.for_time(playback_at)
        if forecast is None:
            raise WeatherUnavailableError(
                f"No matching forecast for {location.id} at {playback_at.isoformat()}"
            )
        return forecast

    def generate(self, item: ScheduledAnnouncement, *, track_state: bool = True) -> AudioAsset:
        """Generate, validate, and publish all configured formats for an announcement."""
        now = self.now_fn()
        if track_state:
            self.state.set(
                item, AnnouncementStatus.GENERATING, now, increment_attempts=True
            )
        LOG.info(
            "Preparing announcement",
            extra={
                "location_id": item.location.id,
                "kind": item.kind.value,
                "playback_at": item.playback_at.isoformat(),
            },
        )
        try:
            weather = self.get_weather(item.location, item.playback_at)
            formatter = self.languages.get(item.location.language)
            announcement_template = item.location.announcements[item.kind].template
            spoken_text = None
            if self.config.audio.enabled:
                spoken_context = build_context(
                    item.location, item.playback_at, weather, formatter
                )
                spoken_text = render_template(announcement_template, spoken_context)

            html = None
            if self.config.text.enabled:
                readable_context = build_context(
                    item.location,
                    item.playback_at,
                    weather,
                    formatter,
                    spoken=False,
                )
                message = render_template(announcement_template, readable_context)
                wrapper = DEFAULT_TEXT_ASSET_TEMPLATE
                if self.config.text.template is not None:
                    wrapper = self.config.text.template.read_text(encoding="utf-8")
                html = render_text_asset(
                    wrapper,
                    {
                        "language": item.location.language,
                        "location": item.location.name,
                        "location_id": item.location.id,
                        "message": message,
                        "kind": item.kind.value,
                        "date": readable_context["date"],
                        "time": readable_context["time"],
                        "year": item.playback_at.year,
                    },
                )
            LOG.info(
                "Template rendered",
                extra={"location_id": item.location.id, "kind": item.kind.value},
            )

            self.config.output.generated_dir.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(
                prefix=f".{item.location.id}-{item.kind.short_name}-",
                dir=self.config.output.generated_dir,
            ) as temporary_dir:
                temporary = Path(temporary_dir)
                rendered_assets: list[tuple[Path, AudioAsset]] = []
                if self.config.audio.enabled:
                    # Providers may produce WAV (Piper/eSpeak) or MP3 (gTTS).
                    # FFmpeg detects the actual input format from the file contents.
                    speech_path = temporary / "speech.audio"
                    tts_provider = self._tts_for_language(item.location.language)
                    tts_provider.synthesize(spoken_text, speech_path)
                    LOG.info(
                        "TTS synthesis completed",
                        extra={
                            "location_id": item.location.id,
                            "provider": tts_provider.last_provider,
                            "language": item.location.language,
                        },
                    )
                    for audio_format in self.config.audio.output.formats:
                        audio_path = temporary / f"announcement.{audio_format.extension}"
                        self.audio.process(
                            speech_path,
                            audio_path,
                            item.location.jingles.get(item.kind),
                        )
                        rendered_assets.append(
                            (
                                audio_path,
                                self.assets.paths(
                                    item.location.id,
                                    item.kind,
                                    item.playback_at,
                                    audio_format.extension,
                                ),
                            )
                        )
                        LOG.info(
                            "Audio format validated",
                            extra={
                                "location_id": item.location.id,
                                "format": audio_format.name,
                            },
                        )

                if html is not None:
                    html_path = temporary / "announcement.html"
                    html_path.write_text(html, encoding="utf-8")
                    rendered_assets.append(
                        (
                            html_path,
                            self.assets.paths(
                                item.location.id,
                                item.kind,
                                item.playback_at,
                                "html",
                            ),
                        )
                    )
                    LOG.info(
                        "Text asset rendered",
                        extra={
                            "location_id": item.location.id,
                            "format": "html",
                        },
                    )

                # Validate every configured representation before replacing any
                # already-published public asset.
                for audio_path, rendered_asset in rendered_assets:
                    self.assets.publish(audio_path, rendered_asset)
                asset = rendered_assets[0][1]
            if track_state:
                self.state.set(
                    item,
                    AnnouncementStatus.PUBLISHED,
                    self.now_fn(),
                    public_path=asset.public_path,
                )
            LOG.info(
                "Assets published",
                extra={
                    "location_id": item.location.id,
                    "public_paths": [
                        str(rendered_asset.public_path)
                        for _, rendered_asset in rendered_assets
                    ],
                },
            )
            return asset
        except Exception as exc:
            if track_state:
                self.state.set(
                    item, AnnouncementStatus.FAILED, self.now_fn(), error=str(exc)
                )
            if isinstance(exc, WeatherboxError):
                raise
            raise WeatherboxError(str(exc)) from exc

    def run_due(self) -> dict[str, str]:
        """Generate all currently due announcements and return per-item results."""
        if self.config.output.generated_retention_days is not None:
            try:
                self.cleanup_generated()
            except WeatherboxError as exc:
                LOG.warning(
                    "Generated asset cleanup failed; continuing with generation",
                    extra={"error": str(exc)},
                )
        now = self.now_fn()
        due = self.scheduler.due(self.config.enabled_locations, now)
        results: dict[str, str] = {}
        for item in due:
            try:
                asset = self.generate(item)
                results[item.key] = str(asset.public_path)
            except Exception as exc:
                results[item.key] = f"ERROR: {exc}"
                LOG.exception(
                    "Announcement generation failed",
                    extra={"location_id": item.location.id, "kind": item.kind.value},
                )
        return results

    def cleanup_generated(self, retention_days: int | None = None) -> dict[str, int]:
        """Remove expired files from the generated asset directory."""
        days = (
            retention_days
            if retention_days is not None
            else self.config.output.generated_retention_days
        )
        if days is None:
            raise WeatherboxError(
                "No retention period configured; set "
                "'output.generated_retention_days' or use '--older-than-days'"
            )
        try:
            result = self.assets.cleanup(days, now=self.now_fn())
        except (OSError, ValueError) as exc:
            raise WeatherboxError(f"Generated assets could not be cleaned up: {exc}") from exc
        LOG.info("Generated asset cleanup completed", extra=result)
        return result

    def _tts_for_language(self, language: str) -> FallbackTTSProvider:
        """Return the injected or cached TTS provider for a language."""
        if self._injected_tts_provider is not None:
            return self._injected_tts_provider
        if language not in self._tts_providers:
            self._tts_providers[language] = create_tts_provider(self.config.tts, language)
        return self._tts_providers[language]

    def manual_items(
        self,
        locations: Iterable[Location],
        kinds: Iterable[AnnouncementKind],
        at: datetime | None = None,
    ) -> tuple[ScheduledAnnouncement, ...]:
        """Build scheduled items for a manual generation request."""
        now = self.now_fn()
        items: list[ScheduledAnnouncement] = []
        for location in locations:
            local_now = now.astimezone(ZoneInfo(location.timezone))
            for kind in kinds:
                playback = at.astimezone(ZoneInfo(location.timezone)) if at else next_playback(local_now, kind)
                items.append(ScheduledAnnouncement(location, kind, playback))
        return tuple(items)

    def generate_many(self, items: Iterable[ScheduledAnnouncement]) -> dict[str, str]:
        """Generate multiple announcements and collect paths or error messages."""
        results: dict[str, str] = {}
        for item in items:
            try:
                results[item.key] = str(self.generate(item).public_path)
            except Exception as exc:
                results[item.key] = f"ERROR: {exc}"
                LOG.error(
                    "Manual generation failed",
                    extra={"location_id": item.location.id, "kind": item.kind.value, "error": str(exc)},
                )
        return results

    def status(self) -> dict:
        """Return a summary of cache health, configuration, and recent state."""
        now = self.now_fn()
        caches = {}
        for location in self.config.enabled_locations:
            bundle = self.weather_cache.load(location.id)
            caches[location.id] = {
                "available": bundle is not None,
                "valid": bool(
                    bundle
                    and self.weather_cache.is_fresh(
                        bundle, now, self.config.weather.max_cache_age_minutes
                    )
                ),
                "fetched_at": bundle.fetched_at.isoformat() if bundle else None,
            }
        states = self.state.entries()
        counts = Counter(entry.status.value for entry in states.values())
        return {
            "status": "ok" if all(value["valid"] for value in caches.values()) else "degraded",
            "locations": len(self.config.enabled_locations),
            "weather_providers": [
                provider.name for provider in self.config.weather.providers
            ],
            "weather_cache": caches,
            "tts_provider": self.config.tts.provider if self.config.audio.enabled else None,
            "asset_outputs": {
                "audio": self.config.audio.enabled,
                "text": self.config.text.enabled,
            },
            "languages": {
                location.id: location.language for location in self.config.enabled_locations
            },
            "announcement_states": dict(counts),
            "last_updates": {
                key: value.updated_at.isoformat()
                for key, value in sorted(states.items(), key=lambda item: item[1].updated_at)[-10:]
            },
        }
