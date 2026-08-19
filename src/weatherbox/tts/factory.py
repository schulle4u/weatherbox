"""Factory for configured text-to-speech provider chains."""

from weatherbox.config import EspeakSettings, GTTSSettings, PiperSettings, TTSSettings
from weatherbox.tts.base import TTSProvider
from weatherbox.tts.espeak_ng import EspeakProvider
from weatherbox.tts.fallback import FallbackTTSProvider
from weatherbox.tts.gtts import GTTSProvider
from weatherbox.tts.piper import PiperProvider


def create_tts_provider(
    settings: TTSSettings, language: str | None = None
) -> FallbackTTSProvider:
    """Create the configured provider chain for an optional language."""
    override = settings.languages.get(language) if language else None
    piper_settings = PiperSettings(
        executable=settings.piper.executable,
        model=override.piper_model if override and override.piper_model else settings.piper.model,
    )
    espeak_settings = EspeakSettings(
        executable=settings.espeak.executable,
        voice=override.espeak_voice if override and override.espeak_voice else settings.espeak.voice,
        speed=settings.espeak.speed,
    )
    gtts_settings = GTTSSettings(
        language=(
            override.gtts_language
            if override and override.gtts_language
            else language or settings.gtts.language
        ),
        tld=override.gtts_tld if override and override.gtts_tld else settings.gtts.tld,
        slow=settings.gtts.slow,
        timeout_seconds=settings.gtts.timeout_seconds,
    )
    providers: dict[str, TTSProvider] = {
        "piper": PiperProvider(piper_settings),
        "espeak-ng": EspeakProvider(espeak_settings),
        "gtts": GTTSProvider(gtts_settings),
    }
    return FallbackTTSProvider(
        primary=providers[settings.provider],
        fallback=(
            providers.get(settings.fallback_provider) if settings.fallback_provider else None
        ),
    )
