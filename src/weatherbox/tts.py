"""Text-to-speech providers and fallback orchestration."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Protocol

from weatherbox.config import EspeakSettings, PiperSettings, TTSSettings
from weatherbox.errors import TTSGenerationError


LOG = logging.getLogger(__name__)


class TTSProvider(Protocol):
    """Interface implemented by text-to-speech providers."""

    name: str

    def synthesize(self, text: str, output_path: Path) -> None:
        """Synthesize ``text`` into a WAV file at ``output_path``."""
        ...


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
            "--model", str(self.settings.model),
            "--output_file", str(output_path),
        ]
        _run(command, input_text=text, provider=self.name)
        _validate_wave_output(output_path, self.name)


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
            "-v", self.settings.voice,
            "-s", str(self.settings.speed),
            "-w", str(output_path),
            text,
        ]
        _run(command, provider=self.name)
        _validate_wave_output(output_path, self.name)


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
                "TTS-Fallback wird verwendet",
                extra={"primary_provider": self.primary.name, "fallback_provider": self.fallback.name},
            )
            try:
                self.fallback.synthesize(text, output_path)
                self.last_provider = self.fallback.name
            except TTSGenerationError as fallback_error:
                raise TTSGenerationError(
                    f"Primärer TTS-Provider fehlgeschlagen ({primary_error}); "
                    f"Fallback fehlgeschlagen ({fallback_error})"
                ) from fallback_error


def create_tts_provider(settings: TTSSettings, language: str | None = None) -> FallbackTTSProvider:
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
    providers: dict[str, TTSProvider] = {
        "piper": PiperProvider(piper_settings),
        "espeak-ng": EspeakProvider(espeak_settings),
    }
    return FallbackTTSProvider(
        primary=providers[settings.provider],
        fallback=providers.get(settings.fallback_provider) if settings.fallback_provider else None,
    )


def _run(command: list[str], *, provider: str, input_text: str | None = None) -> None:
    """Run a TTS command and report execution failures consistently."""
    try:
        result = subprocess.run(
            command,
            input=input_text,
            text=True,
            capture_output=True,
            check=False,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise TTSGenerationError(f"{provider} konnte nicht ausgeführt werden: {exc}") from exc
    if result.returncode != 0:
        details = (result.stderr or result.stdout).strip()[-1000:]
        raise TTSGenerationError(f"{provider} Exit-Code {result.returncode}: {details}")


def _validate_wave_output(path: Path, provider: str) -> None:
    """Ensure a provider created a file large enough to contain a WAV header."""
    if not path.is_file() or path.stat().st_size < 44:
        raise TTSGenerationError(f"{provider} hat keine gültige WAV-Datei erzeugt")
