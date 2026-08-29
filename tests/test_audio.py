import json
import shutil
import subprocess
from dataclasses import replace

import pytest

from weatherbox.audio import AudioPipeline
from weatherbox.config import (
    AudioFormatSettings,
    AudioOutputSettings,
    AudioSettings,
    LoudnessSettings,
)
from weatherbox.errors import AudioProcessingError
from weatherbox.models import JingleAssets


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
    with pytest.raises(AudioProcessingError, match="unexpected channel count"):
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


@pytest.mark.parametrize(
    ("audio_format", "probe_codec", "has_bitrate"),
    (
        (AudioFormatSettings("mp3", "mp3", "libmp3lame", "mp3", "192k"), "mp3", True),
        (AudioFormatSettings("wav", "wav", "pcm_s16le", "wav", None), "pcm_s16le", False),
        (AudioFormatSettings("flac", "flac", "flac", "flac", None), "flac", False),
        (AudioFormatSettings("ogg", "ogg", "libvorbis", "ogg", "160k"), "vorbis", True),
        (AudioFormatSettings("opus", "opus", "libopus", "opus", "96k"), "opus", True),
        (AudioFormatSettings("m4a", "m4a", "aac", "ipod", "192k"), "aac", True),
    ),
)
def test_each_audio_format_uses_expected_encoder_and_is_validated(
    tmp_path, settings, monkeypatch, audio_format, probe_codec, has_bitrate
):
    speech = tmp_path / "speech.wav"
    speech.write_bytes(b"RIFF")
    output = tmp_path / f"out.{audio_format.extension}"
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        if command[0] == "ffmpeg":
            output.write_bytes(b"audio")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        payload = {
            "streams": [
                {"codec_name": probe_codec, "channels": 2, "sample_rate": "48000"}
            ],
            "format": {"duration": "2.5"},
        }
        return subprocess.CompletedProcess(
            command, 0, stdout=json.dumps(payload), stderr=""
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    configured = replace(
        settings,
        output=replace(settings.output, formats=(audio_format,)),
    )

    AudioPipeline(configured).process(speech, output)

    ffmpeg_command = commands[0]
    assert ffmpeg_command[ffmpeg_command.index("-c:a") + 1] == audio_format.codec
    assert ffmpeg_command[ffmpeg_command.index("-f") + 1] == audio_format.container
    assert ("-b:a" in ffmpeg_command) is has_bitrate


def test_music_bed_is_looped_mixed_faded_and_surrounded_by_jingles(
    tmp_path, settings, monkeypatch
):
    speech = tmp_path / "speech.wav"
    intro = tmp_path / "intro.wav"
    music = tmp_path / "music.wav"
    outro = tmp_path / "outro.wav"
    output = tmp_path / "out.mp3"
    for path in (speech, intro, music, outro):
        path.write_bytes(b"RIFF")

    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        if command[0] == "ffmpeg":
            output.write_bytes(b"mp3")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        if any(value.startswith("stream=codec_name") for value in command):
            payload = {
                "streams": [
                    {"codec_name": "mp3", "channels": 2, "sample_rate": "48000"}
                ],
                "format": {"duration": "8.0"},
            }
        else:
            payload = {"format": {"duration": "4.25"}}
        return subprocess.CompletedProcess(
            command, 0, stdout=json.dumps(payload), stderr=""
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    AudioPipeline(settings).process(
        speech,
        output,
        JingleAssets(intro=intro, music=music, outro=outro),
    )

    ffmpeg_command = next(command for command in commands if command[0] == "ffmpeg")
    filter_graph = ffmpeg_command[ffmpeg_command.index("-filter_complex") + 1]
    assert ffmpeg_command[ffmpeg_command.index("-stream_loop") + 1] == "-1"
    assert "volume=-10dB" in filter_graph
    assert "atrim=duration=6.75" in filter_graph
    assert "afade=t=out:st=4.25:d=2.5" in filter_graph
    assert "[intro][body][outro]concat=n=3" in filter_graph


def test_missing_optional_asset_is_reported_before_ffmpeg(
    tmp_path, settings, monkeypatch
):
    speech = tmp_path / "speech.wav"
    speech.write_bytes(b"RIFF")
    missing = tmp_path / "missing.wav"
    called = False

    def fake_run(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(AudioProcessingError, match="Outro missing"):
        AudioPipeline(settings).process(
            speech, tmp_path / "out.mp3", JingleAssets(outro=missing)
        )
    assert not called


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="FFmpeg and FFprobe are required for the integration test",
)
@pytest.mark.parametrize(
    "audio_format",
    (
        AudioFormatSettings("mp3", "mp3", "libmp3lame", "mp3", "192k"),
        AudioFormatSettings("wav", "wav", "pcm_s16le", "wav", None),
        AudioFormatSettings("flac", "flac", "flac", "flac", None),
        AudioFormatSettings("ogg", "ogg", "libvorbis", "ogg", "160k"),
        AudioFormatSettings("opus", "opus", "libopus", "opus", "96k"),
        AudioFormatSettings("m4a", "m4a", "aac", "ipod", "192k"),
    ),
    ids=lambda audio_format: audio_format.name,
)
def test_real_ffmpeg_encodes_each_supported_format(tmp_path, settings, audio_format):
    speech = tmp_path / "speech.wav"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=0.2",
            str(speech),
        ],
        check=True,
    )
    configured = replace(
        settings,
        loudness=replace(settings.loudness, enabled=False),
        output=replace(settings.output, formats=(audio_format,)),
    )
    output = tmp_path / f"announcement.{audio_format.extension}"

    AudioPipeline(configured).process(speech, output)

    assert output.is_file()


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="FFmpeg and FFprobe are required for the integration test",
)
def test_real_ffmpeg_pipeline_combines_all_audio_elements(tmp_path, settings):
    paths = {
        "speech": (tmp_path / "speech.wav", 1.0, 440),
        "intro": (tmp_path / "intro.wav", 0.25, 660),
        "music": (tmp_path / "music.wav", 0.3, 220),
        "outro": (tmp_path / "outro.wav", 0.25, 880),
    }
    for path, duration, frequency in paths.values():
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency={frequency}:duration={duration}",
                str(path),
            ],
            check=True,
        )

    integration_settings = replace(
        settings,
        loudness=replace(settings.loudness, enabled=False),
        music_attenuation_db=-12,
        music_fade_out_seconds=0.5,
    )
    output = tmp_path / "combined.mp3"
    pipeline = AudioPipeline(integration_settings)

    pipeline.process(
        paths["speech"][0],
        output,
        JingleAssets(
            intro=paths["intro"][0],
            music=paths["music"][0],
            outro=paths["outro"][0],
        ),
    )

    assert output.is_file()
    assert pipeline._duration(output) == pytest.approx(2.0, abs=0.1)
