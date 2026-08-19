"""Piper text-to-speech provider."""

from pathlib import Path

from weatherbox.config import PiperSettings
from weatherbox.tts.base import run_command, validate_wave_output


class PiperProvider:
    """Generate speech with the Piper command-line application."""

    name = "piper"

    def __init__(self, settings: PiperSettings) -> None:
        """Initialize the provider with Piper settings."""
        self.settings = settings

    def synthesize(self, text: str, output_path: Path) -> None:
        """Generate and validate a WAV file with Piper."""
        command = [
            self.settings.executable,
            "--model",
            str(self.settings.model),
            "--output_file",
            str(output_path),
        ]
        run_command(command, input_text=text, provider=self.name)
        validate_wave_output(output_path, self.name)
