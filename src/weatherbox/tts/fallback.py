"""Fallback orchestration for text-to-speech providers."""

import logging
from pathlib import Path

from weatherbox.errors import TTSGenerationError
from weatherbox.tts.base import TTSProvider


LOG = logging.getLogger(__name__)


class FallbackTTSProvider:
    """Use a secondary TTS provider if the primary provider fails."""

    name = "fallback"

    def __init__(self, primary: TTSProvider, fallback: TTSProvider | None) -> None:
        """Initialize the provider chain with a primary and optional fallback."""
        self.primary = primary
        self.fallback = fallback
        self.last_provider: str | None = None

    def synthesize(self, text: str, output_path: Path) -> None:
        """Synthesize speech with the primary provider and optional fallback."""
        try:
            self.primary.synthesize(text, output_path)
            self.last_provider = self.primary.name
        except TTSGenerationError as primary_error:
            output_path.unlink(missing_ok=True)
            if self.fallback is None:
                raise
            LOG.warning(
                "Using TTS fallback",
                extra={
                    "primary_provider": self.primary.name,
                    "fallback_provider": self.fallback.name,
                },
            )
            try:
                self.fallback.synthesize(text, output_path)
                self.last_provider = self.fallback.name
            except TTSGenerationError as fallback_error:
                raise TTSGenerationError(
                    f"Primary TTS provider failed ({primary_error}); "
                    f"Fallback failed ({fallback_error})"
                ) from fallback_error
