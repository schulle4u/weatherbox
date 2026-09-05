# Development and architecture

[Project overview and quick start](../README.md) · [Documentation index](README.md)

## Development setup

Python 3.11 or later, FFmpeg, and FFprobe are required. From the project
directory, activate a virtual environment and install the extra test dependencies:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
```

See [installation](installation.md) for PowerShell commands and system
dependencies. To try Weatherbox locally, copy
[config.quickstart.yaml](config.quickstart.yaml) to the project directory
as `config.yaml`.

## Tests

```bash
pytest
```

## Architecture rule

Weatherbox does not produce live audio output. All configured audio formats are
generated and validated with FFprobe first, and an optional HTML representation
is rendered before publication. Only then is each file moved atomically to its
stable public location. If synthesis, processing, or validation fails, all
previously published assets remain unchanged.

The weather implementation is in the `src/weatherbox/weather/` package:

- `open_meteo.py` and `dwd.py` contain the providers and their API mappings.
- `merged.py` aligns multiple sources in time and merges them field by field.
- `factory.py` builds a single or merged provider from YAML.
- `base.py` contains the shared interface.
- `cache.py` stores forecasts and warnings independently of their provider.

The TTS implementation is in the `src/weatherbox/tts/` package:

- `piper.py`, `espeak_ng.py`, and `gtts.py` each contain one provider.
- `fallback.py` manages primary and fallback speech generation.
- `factory.py` translates configuration into a provider chain.
- `base.py` contains only the shared interface and validation helpers.
- `__init__.py` exposes the existing public import interface.
