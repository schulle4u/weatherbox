"""eSpeak NG text-to-speech provider."""

from pathlib import Path

from weatherbox.config import EspeakSettings
from weatherbox.tts.base import run_command, validate_wave_output


class EspeakProvider:
    """Generate speech with the eSpeak NG command-line application."""

    name = "espeak-ng"

    def __init__(self, settings: EspeakSettings) -> None:
        """Initialize the provider with eSpeak NG settings."""
        self.settings = settings

    def synthesize(self, text: str, output_path: Path) -> None:
        """Generate and validate a WAV file with eSpeak NG."""
        command = [
            self.settings.executable,
            "-v",
            self.settings.voice,
            "-s",
            str(self.settings.speed),
            "-w",
            str(output_path),
            text,
        ]
        run_command(command, provider=self.name)
        validate_wave_output(output_path, self.name)
