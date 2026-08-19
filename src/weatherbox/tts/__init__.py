"""Text-to-speech providers and fallback orchestration."""

from weatherbox.tts.base import TTSProvider
from weatherbox.tts.espeak_ng import EspeakProvider
from weatherbox.tts.factory import create_tts_provider
from weatherbox.tts.fallback import FallbackTTSProvider
from weatherbox.tts.gtts import GTTSProvider
from weatherbox.tts.piper import PiperProvider

__all__ = [
    "EspeakProvider",
    "FallbackTTSProvider",
    "GTTSProvider",
    "PiperProvider",
    "TTSProvider",
    "create_tts_provider",
]
