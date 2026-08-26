"""Convert synthesized speech to validated, normalized MP3 assets."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from weatherbox.config import AudioSettings
from weatherbox.errors import AudioProcessingError
from weatherbox.models import JingleAssets


class AudioPipeline:
    """Process speech and optional jingles with FFmpeg and FFprobe."""

    def __init__(self, settings: AudioSettings) -> None:
        """Initialize the pipeline with audio processing settings."""
        self.settings = settings

    def process(
        self,
        speech_path: Path,
        output_path: Path,
        jingles: JingleAssets | None = None,
    ) -> None:
        """Create an MP3 from speech, optional intro/outro, and an optional music bed."""
        jingles = jingles or JingleAssets()
        for label, path in (
            ("Intro", jingles.intro),
            ("Outro", jingles.outro),
            ("Music bed", jingles.music),
        ):
            if path is not None and not path.is_file():
                raise AudioProcessingError(f"{label} missing: {path}")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        command = [self.settings.ffmpeg, "-hide_banner", "-loglevel", "error", "-y"]
        command += ["-i", str(speech_path)]

        input_indexes: dict[str, int] = {}
        for name, path in (
            ("intro", jingles.intro),
            ("music", jingles.music),
            ("outro", jingles.outro),
        ):
            if path is None:
                continue
            if name == "music":
                command += ["-stream_loop", "-1"]
            input_indexes[name] = len(input_indexes) + 1
            command += ["-i", str(path)]

        sample_rate = self.settings.output.sample_rate
        audio_format = f"aformat=sample_rates={sample_rate}:channel_layouts=stereo"
        filters: list[str] = [f"[0:a]{audio_format}[speech]"]
        body_label = "speech"

        if jingles.music is not None:
            speech_duration = self._duration(speech_path)
            fade_duration = self.settings.music_fade_out_seconds
            music_duration = speech_duration + fade_duration
            fade = ""
            if fade_duration > 0:
                fade = (
                    f",afade=t=out:st={self._format_number(speech_duration)}"
                    f":d={self._format_number(fade_duration)}"
                )
            filters.extend(
                (
                    f"[speech]apad=pad_dur={self._format_number(fade_duration)}[speech_padded]",
                    f"[{input_indexes['music']}:a]{audio_format},"
                    f"volume={self._format_number(self.settings.music_attenuation_db)}dB,"
                    f"atrim=duration={self._format_number(music_duration)}{fade}[music]",
                    "[speech_padded][music]amix=inputs=2:duration=first:dropout_transition=0[body]",
                )
            )
            body_label = "body"

        sequence: list[str] = []
        if jingles.intro is not None:
            filters.append(f"[{input_indexes['intro']}:a]{audio_format}[intro]")
            sequence.append("intro")
        sequence.append(body_label)
        if jingles.outro is not None:
            filters.append(f"[{input_indexes['outro']}:a]{audio_format}[outro]")
            sequence.append("outro")

        if len(sequence) > 1:
            inputs = "".join(f"[{label}]" for label in sequence)
            filters.append(f"{inputs}concat=n={len(sequence)}:v=0:a=1[assembled]")
            final_label = "assembled"
        else:
            final_label = sequence[0]

        final_filter = f"[{final_label}]anull{self._loudness_suffix()}[out]"
        filters.append(final_filter)
        command += ["-filter_complex", ";".join(filters), "-map", "[out]"]
        command += [
            "-ar", str(self.settings.output.sample_rate),
            "-ac", str(self.settings.output.channels),
            "-b:a", self.settings.output.bitrate,
            "-f", "mp3",
            str(output_path),
        ]
        self._run(command, "FFmpeg processing")
        self.validate(output_path)

    def _duration(self, path: Path) -> float:
        """Return an input file's positive duration in seconds using FFprobe."""
        command = [
            self.settings.ffprobe,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json",
            str(path),
        ]
        result = self._run(command, "FFprobe duration inspection", return_output=True)
        try:
            duration = float(json.loads(result)["format"]["duration"])
            if duration <= 0:
                raise ValueError("invalid duration")
            return duration
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise AudioProcessingError(f"Invalid speech duration: {exc}") from exc

    @staticmethod
    def _format_number(value: float) -> str:
        """Format numeric FFmpeg arguments without locale-dependent separators."""
        return format(value, ".12g")

    def _loudness_suffix(self) -> str:
        """Return the configured FFmpeg loudness-normalization filter suffix."""
        if not self.settings.loudness.enabled:
            return ""
        value = self.settings.loudness
        return f",loudnorm=I={value.target_lufs}:LRA={value.loudness_range}:TP={value.true_peak_db}"

    def validate(self, path: Path) -> None:
        """Verify that a file is a non-empty MP3 with the configured format."""
        if not path.is_file() or path.stat().st_size == 0:
            raise AudioProcessingError("MP3 file missing or empty")
        command = [
            self.settings.ffprobe,
            "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=codec_name,channels,sample_rate:format=duration",
            "-of", "json",
            str(path),
        ]
        result = self._run(command, "FFprobe validation", return_output=True)
        try:
            payload = json.loads(result)
            stream = payload["streams"][0]
            duration = float(payload["format"]["duration"])
            if stream["codec_name"] != "mp3":
                raise ValueError("Codec is not MP3")
            if int(stream["channels"]) != self.settings.output.channels:
                raise ValueError("unexpected channel count")
            if int(stream["sample_rate"]) != self.settings.output.sample_rate:
                raise ValueError("unexpected sampling rate")
            if duration <= 0:
                raise ValueError("invalid duration")
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise AudioProcessingError(f"Invalid MP3 output: {exc}") from exc

    @staticmethod
    def _run(command: list[str], label: str, *, return_output: bool = False) -> str:
        """Run an audio command and translate process failures to domain errors."""
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=180)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AudioProcessingError(f"{label} could not be run: {exc}") from exc
        if result.returncode != 0:
            details = (result.stderr or result.stdout).strip()[-2000:]
            raise AudioProcessingError(f"{label} failed: {details}")
        return result.stdout if return_output else ""
