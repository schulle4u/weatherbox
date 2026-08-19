"""Google Translate text-to-speech provider using gTTS."""

from pathlib import Path

from weatherbox.config import GTTSSettings
from weatherbox.errors import TTSGenerationError
from weatherbox.tts.base import validate_mp3_output


class GTTSProvider:
    """Generate MP3 speech through Google Translate using the gTTS library."""

    name = "gtts"

    def __init__(self, settings: GTTSSettings) -> None:
        """Initialize the provider with language and request settings."""
        self.settings = settings

    def synthesize(self, text: str, output_path: Path) -> None:
        """Generate and validate an MP3 file using the gTTS Python API."""
        try:
            from gtts import gTTS

            speech = gTTS(
                text=text,
                lang=self.settings.language,
                tld=self.settings.tld,
                slow=self.settings.slow,
                timeout=self.settings.timeout_seconds,
            )
            speech.save(str(output_path))
        except Exception as exc:
            raise TTSGenerationError(f"{self.name} request failed: {exc}") from exc
        validate_mp3_output(output_path, self.name)
