import sys
import types
from pathlib import Path

import pytest

from weatherbox.errors import TTSGenerationError
from weatherbox.config import GTTSSettings
from weatherbox.tts import FallbackTTSProvider, GTTSProvider


class FakeTTS:
    def __init__(self, name: str, fails: bool = False):
        self.name = name
        self.fails = fails

    def synthesize(self, text: str, output_path: Path) -> None:
        if self.fails:
            raise TTSGenerationError(f"{self.name} failed")
        output_path.write_bytes(b"RIFF" + b"0" * 44)


def test_primary_provider_success(tmp_path):
    provider = FallbackTTSProvider(FakeTTS("piper"), FakeTTS("espeak-ng"))
    provider.synthesize("Hallo", tmp_path / "out.wav")
    assert provider.last_provider == "piper"


def test_fallback_provider_is_used(tmp_path, caplog):
    provider = FallbackTTSProvider(FakeTTS("piper", fails=True), FakeTTS("espeak-ng"))
    provider.synthesize("Hallo", tmp_path / "out.wav")
    assert provider.last_provider == "espeak-ng"
    assert "Using TTS fallback" in caplog.text


def test_both_providers_fail(tmp_path):
    provider = FallbackTTSProvider(FakeTTS("piper", True), FakeTTS("espeak-ng", True))
    with pytest.raises(TTSGenerationError, match="Fallback failed"):
        provider.synthesize("Hallo", tmp_path / "out.wav")


def test_gtts_provider_uses_python_api_and_writes_mp3(tmp_path, monkeypatch):
    calls = {}

    class FakeGoogleSpeech:
        def __init__(self, **kwargs):
            calls.update(kwargs)

        def save(self, path):
            Path(path).write_bytes(b"ID3" + b"0" * 20)

    fake_module = types.ModuleType("gtts")
    fake_module.gTTS = FakeGoogleSpeech
    monkeypatch.setitem(sys.modules, "gtts", fake_module)

    output = tmp_path / "speech.audio"
    provider = GTTSProvider(GTTSSettings("de", "de", False, 12.5))
    provider.synthesize("Guten Morgen", output)

    assert output.read_bytes().startswith(b"ID3")
    assert calls == {
        "text": "Guten Morgen",
        "lang": "de",
        "tld": "de",
        "slow": False,
        "timeout": 12.5,
    }


def test_gtts_provider_translates_client_errors(tmp_path, monkeypatch):
    class FailingGoogleSpeech:
        def __init__(self, **kwargs):
            raise RuntimeError("offline")

    fake_module = types.ModuleType("gtts")
    fake_module.gTTS = FailingGoogleSpeech
    monkeypatch.setitem(sys.modules, "gtts", fake_module)

    provider = GTTSProvider(GTTSSettings("de", "com", False, 15))
    with pytest.raises(TTSGenerationError, match="offline"):
        provider.synthesize("Hallo", tmp_path / "speech.audio")
