import json
import subprocess

import pytest

from weatherbox.audio import AudioPipeline
from weatherbox.config import AudioOutputSettings, AudioSettings, LoudnessSettings
from weatherbox.errors import AudioProcessingError


@pytest.fixture
def settings():
    return AudioSettings(
        ffmpeg="ffmpeg",
        ffprobe="ffprobe",
        loudness=LoudnessSettings(True, -16, -1.5, 11),
        output=AudioOutputSettings(48000, 2, "192k"),
    )


def test_ffprobe_validation_accepts_expected_stereo_mp3(tmp_path, settings, monkeypatch):
    path = tmp_path / "audio.mp3"
    path.write_bytes(b"mp3")
    payload = {"streams": [{"codec_name": "mp3", "channels": 2, "sample_rate": "48000"}], "format": {"duration": "2.5"}}
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, stdout=json.dumps(payload), stderr=""),
    )
    AudioPipeline(settings).validate(path)


def test_ffprobe_rejects_mono_output(tmp_path, settings, monkeypatch):
    path = tmp_path / "audio.mp3"
    path.write_bytes(b"mp3")
    payload = {"streams": [{"codec_name": "mp3", "channels": 1, "sample_rate": "48000"}], "format": {"duration": "2.5"}}
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, stdout=json.dumps(payload), stderr=""),
    )
    with pytest.raises(AudioProcessingError, match="Kanalzahl"):
        AudioPipeline(settings).validate(path)


def test_ffmpeg_failure_is_reported(tmp_path, settings, monkeypatch):
    speech = tmp_path / "speech.wav"
    speech.write_bytes(b"RIFF")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 1, stdout="", stderr="codec error"),
    )
    with pytest.raises(AudioProcessingError, match="codec error"):
        AudioPipeline(settings).process(speech, tmp_path / "out.mp3")

