"""Convert synthesized speech to validated, normalized MP3 assets."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from weatherbox.config import AudioSettings
from weatherbox.errors import AudioProcessingError


class AudioPipeline:
    """Process speech and optional jingles with FFmpeg and FFprobe."""

    def __init__(self, settings: AudioSettings) -> None:
        """Initialize the pipeline with audio processing settings."""
        self.settings = settings

    def process(self, speech_path: Path, output_path: Path, jingle_path: Path | None = None) -> None:
        """Create and validate an MP3 from speech and an optional leading jingle."""
        if jingle_path is not None and not jingle_path.is_file():
            raise AudioProcessingError(f"Jingle fehlt: {jingle_path}")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        command = [self.settings.ffmpeg, "-hide_banner", "-loglevel", "error", "-y"]
        if jingle_path:
            command += ["-i", str(jingle_path), "-i", str(speech_path)]
            filters = (
                f"[0:a]aformat=sample_rates={self.settings.output.sample_rate}:channel_layouts=stereo[j];"
                f"[1:a]aformat=sample_rates={self.settings.output.sample_rate}:channel_layouts=stereo[s];"
                "[j][s]concat=n=2:v=0:a=1"
            )
            filters += self._loudness_suffix()
            filters += "[out]"
            command += ["-filter_complex", filters, "-map", "[out]"]
        else:
            command += ["-i", str(speech_path)]
            filters = f"aformat=sample_rates={self.settings.output.sample_rate}:channel_layouts=stereo"
            filters += self._loudness_suffix()
            command += ["-af", filters]
        command += [
            "-ar", str(self.settings.output.sample_rate),
            "-ac", str(self.settings.output.channels),
            "-b:a", self.settings.output.bitrate,
            "-f", "mp3",
            str(output_path),
        ]
        self._run(command, "FFmpeg-Verarbeitung")
        self.validate(output_path)

    def _loudness_suffix(self) -> str:
        """Return the configured FFmpeg loudness-normalization filter suffix."""
        if not self.settings.loudness.enabled:
            return ""
        value = self.settings.loudness
        return f",loudnorm=I={value.target_lufs}:LRA={value.loudness_range}:TP={value.true_peak_db}"

    def validate(self, path: Path) -> None:
        """Verify that a file is a non-empty MP3 with the configured format."""
        if not path.is_file() or path.stat().st_size == 0:
            raise AudioProcessingError("MP3-Datei fehlt oder ist leer")
        command = [
            self.settings.ffprobe,
            "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=codec_name,channels,sample_rate:format=duration",
            "-of", "json",
            str(path),
        ]
        result = self._run(command, "FFprobe-Validierung", return_output=True)
        try:
            payload = json.loads(result)
            stream = payload["streams"][0]
            duration = float(payload["format"]["duration"])
            if stream["codec_name"] != "mp3":
                raise ValueError("Codec ist nicht MP3")
            if int(stream["channels"]) != self.settings.output.channels:
                raise ValueError("unerwartete Kanalzahl")
            if int(stream["sample_rate"]) != self.settings.output.sample_rate:
                raise ValueError("unerwartete Samplerate")
            if duration <= 0:
                raise ValueError("ungültige Dauer")
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise AudioProcessingError(f"Ungültige MP3-Ausgabe: {exc}") from exc

    @staticmethod
    def _run(command: list[str], label: str, *, return_output: bool = False) -> str:
        """Run an audio command and translate process failures to domain errors."""
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=180)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AudioProcessingError(f"{label} konnte nicht ausgeführt werden: {exc}") from exc
        if result.returncode != 0:
            details = (result.stderr or result.stdout).strip()[-2000:]
            raise AudioProcessingError(f"{label} fehlgeschlagen: {details}")
        return result.stdout if return_output else ""
