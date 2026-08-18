from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Protocol

from weatherbox.config import EspeakSettings, PiperSettings, TTSSettings
from weatherbox.errors import TTSGenerationError


LOG = logging.getLogger(__name__)


class TTSProvider(Protocol):
    name: str

    def synthesize(self, text: str, output_path: Path) -> None: ...


class PiperProvider:
    name = "piper"

    def __init__(self, settings: PiperSettings) -> None:
        self.settings = settings

    def synthesize(self, text: str, output_path: Path) -> None:
        command = [
            self.settings.executable,
            "--model", str(self.settings.model),
            "--output_file", str(output_path),
        ]
        _run(command, input_text=text, provider=self.name)
        _validate_wave_output(output_path, self.name)


class EspeakProvider:
    name = "espeak-ng"

    def __init__(self, settings: EspeakSettings) -> None:
        self.settings = settings

    def synthesize(self, text: str, output_path: Path) -> None:
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
    name = "fallback"

    def __init__(self, primary: TTSProvider, fallback: TTSProvider | None) -> None:
        self.primary = primary
        self.fallback = fallback
        self.last_provider: str | None = None

    def synthesize(self, text: str, output_path: Path) -> None:
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


def create_tts_provider(settings: TTSSettings) -> FallbackTTSProvider:
    providers: dict[str, TTSProvider] = {
        "piper": PiperProvider(settings.piper),
        "espeak-ng": EspeakProvider(settings.espeak),
    }
    return FallbackTTSProvider(
        primary=providers[settings.provider],
        fallback=providers.get(settings.fallback_provider) if settings.fallback_provider else None,
    )


def _run(command: list[str], *, provider: str, input_text: str | None = None) -> None:
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
    if not path.is_file() or path.stat().st_size < 44:
        raise TTSGenerationError(f"{provider} hat keine gültige WAV-Datei erzeugt")

