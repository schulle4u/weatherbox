"""Shared interface and utilities for text-to-speech providers."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Protocol

from weatherbox.errors import TTSGenerationError


class TTSProvider(Protocol):
    """Interface implemented by text-to-speech providers."""

    name: str

    def synthesize(self, text: str, output_path: Path) -> None:
        """Synthesize ``text`` into an audio file at ``output_path``."""
        ...


def run_command(command: list[str], *, provider: str, input_text: str | None = None) -> None:
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
        raise TTSGenerationError(f"{provider} could not be executed: {exc}") from exc
    if result.returncode != 0:
        details = (result.stderr or result.stdout).strip()[-1000:]
        raise TTSGenerationError(f"{provider} exit code {result.returncode}: {details}")


def validate_wave_output(path: Path, provider: str) -> None:
    """Ensure a provider created a file large enough to contain a WAV header."""
    if not path.is_file() or path.stat().st_size < 44:
        raise TTSGenerationError(f"{provider} has not generated a valid WAV file")


def validate_mp3_output(path: Path, provider: str) -> None:
    """Ensure a provider created a non-empty file with an MP3 header."""
    try:
        header = path.read_bytes()[:3]
    except OSError as exc:
        raise TTSGenerationError(f"{provider} has not generated a valid MP3 file") from exc
    has_id3_header = header == b"ID3"
    has_mpeg_frame = len(header) >= 2 and header[0] == 0xFF and header[1] & 0xE0 == 0xE0
    if path.stat().st_size <= 3 or not (has_id3_header or has_mpeg_frame):
        raise TTSGenerationError(f"{provider} has not generated a valid MP3 file")
