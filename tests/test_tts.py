from pathlib import Path

import pytest

from weatherbox.errors import TTSGenerationError
from weatherbox.tts import FallbackTTSProvider


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
    assert "Fallback" in caplog.text


def test_both_providers_fail(tmp_path):
    provider = FallbackTTSProvider(FakeTTS("piper", True), FakeTTS("espeak-ng", True))
    with pytest.raises(TTSGenerationError, match="Fallback fehlgeschlagen"):
        provider.synthesize("Hallo", tmp_path / "out.wav")

