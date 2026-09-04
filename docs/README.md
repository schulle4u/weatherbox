# Documentation

Start with the [project README](../README.md) for a quick setup.
These guides cover configuring and operating Weatherbox in more detail.

| Topic | Contents |
| --- | --- |
| [Installation and Linux service](installation.md) | Native installation, Windows, systemd, and HTTP delivery |
| [Docker](docker.md) | Compose, persistent data, updates, custom files, and Piper |
| [Configuration](configuration.md) | YAML structure, locations, weather sources, voices, and audio |
| [Templates and languages](templates.md) | Announcement text, all placeholders, and custom language files |
| [Operation and command line](operations.md) | Manual generation, continuous operation, status, and retention |
| [Development](development.md) | Development setup, tests, and architecture |

Configuration examples to copy:

- [Quick start](config.quickstart.yaml): Open-Meteo and gTTS, without models or jingles.
- [Full example](config.example.yaml): multiple weather sources, Piper fallback, and audio elements; customize before use.
- [Docker example](../deploy/docker/config.example.yaml): container paths and a local eSpeak fallback.

The full `config.example.yaml` is located in `docs/`.
Deployment files remain under `deploy/` or in the project directory:
[systemd service](../deploy/systemd/weatherbox.service),
[systemd timer](../deploy/systemd/weatherbox.timer),
[Caddy example](../deploy/Caddyfile.example), [Compose](../compose.yaml), and
[Dockerfile](../Dockerfile).
