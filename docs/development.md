# Entwicklung und Architektur

[Projektübersicht und Schnellstart](../README.md) · [Dokumentationsübersicht](README.md)

## Entwicklungsinstallation

Python ab 3.11 sowie FFmpeg und FFprobe werden vorausgesetzt. Im
Projektverzeichnis eine virtuelle Umgebung aktivieren und die zusätzlichen
Testabhängigkeiten installieren:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
```

Für PowerShell und Systemabhängigkeiten siehe [Installation](installation.md).
Zum lokalen Ausprobieren [config.quickstart.yaml](config.quickstart.yaml)
als `config.yaml` ins Projektverzeichnis kopieren.

## Tests

```bash
pytest
```

## Architekturregel

Weatherbox erzeugt keine Live-Audioausgabe. Alle konfigurierten Formate werden
zuerst erzeugt und mit FFprobe validiert. Erst danach wird jede Datei atomar an
ihre stabile öffentliche Stelle verschoben. Schlägt Synthese, Verarbeitung oder
Validierung fehl, bleiben sämtliche bisherigen öffentlichen Assets unverändert.

Die Wetter-Implementierung liegt im Paket `src/weatherbox/weather/`:

- `open_meteo.py` und `dwd.py` enthalten die Provider und ihre API-Abbildungen
- `merged.py` richtet mehrere Quellen zeitlich aus und führt sie feldweise zusammen
- `factory.py` baut den einzelnen oder zusammengeführten Provider aus YAML
- `base.py` enthält die gemeinsame Schnittstelle
- `cache.py` speichert Forecasts und Warnungen providerunabhängig

Die TTS-Implementierung liegt im Paket `src/weatherbox/tts/`:

- `piper.py`, `espeak_ng.py` und `gtts.py` enthalten jeweils genau einen Provider
- `fallback.py` steuert die primäre und sekundäre Ausgabe
- `factory.py` übersetzt die Konfiguration in eine Provider-Kette
- `base.py` enthält nur die gemeinsame Schnittstelle und Validierungshelfer
- `__init__.py` stellt die bisherige öffentliche Importoberfläche bereit
