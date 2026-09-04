# Docker deployment

[Project overview and quick start](../README.md) · [Documentation index](README.md)

Docker is an alternative deployment option to the
[systemd timer](installation.md#linux-service-with-systemd).
It requires Docker with Linux containers and the
[Compose plugin](https://docs.docker.com/compose/). Run all commands below from
the repository directory. The image includes Python 3.14, FFmpeg, FFprobe,
eSpeak NG, CA certificates, and time zone data; gTTS is installed with Weatherbox.
No Python or audio tools need to be installed on the host.

## Starting with Compose

```bash
mkdir docker-config
cp deploy/docker/config.example.yaml docker-config/config.yaml
# Customize docker-config/config.yaml, especially locations and templates.
docker compose config
docker compose build --pull
docker compose run --rm weatherbox status
docker compose up -d
docker compose logs -f weatherbox
```

In PowerShell, you can use `Copy-Item` instead of `cp`.
The [Docker example configuration](../deploy/docker/config.example.yaml) uses
Open-Meteo and gTTS with a local eSpeak fallback, requiring no extra models or
jingles. An initial `degraded` status is normal with an empty weather cache.
Weather data and gTTS require outbound internet access. For local speech
generation, set `tts.provider: espeak-ng` and `tts.fallback_provider: null`.

The container starts `serve`: one scheduler pass immediately, then a 60-second
pause between passes. The preparation window, retries, and cleanup are controlled
through YAML. Change the polling interval in `compose.override.yaml`:

```yaml
services:
  weatherbox:
    command: ["serve", "--interval-seconds", "30"]
```

Only one scheduler instance may use the same runtime data; stop and disable
any existing systemd timer before switching.
`docker compose stop` waits up to two minutes for the current pass to finish.
With many locations or slow synthesis, increase `stop_grace_period` so Docker
does not terminate the process prematurely. Compose restarts the service after
a failure or Docker restart unless it was stopped manually. See the
[Compose service reference](https://docs.docker.com/reference/compose-file/services/)
for details.

## Configuration, files, and persistent data

`docker-config/` is mounted read-only at `/etc/weatherbox` and excluded from Git
and the image build. `docker-config/config.yaml` must exist before startup.
Relative paths in this file refer to `/etc/weatherbox`, for example:

| File on the host | Path in the YAML configuration |
| --- | --- |
| `docker-config/assets/intro.wav` | `assets/intro.wav` |
| `docker-config/models/stimme.onnx` | `models/stimme.onnx` |
| `docker-config/lang/de.yaml` | `localization.directory: lang` |

Custom language files must still follow the complete language schema.
After configuration changes, run `docker compose restart weatherbox`.
You can reuse an existing native configuration: update the four output paths
to the absolute container paths from the Docker example and place required
audio and model files under `docker-config/`.

The cache, scheduler state, versioned audio, and public files are stored under
`/var/lib/weatherbox` in the named volume `weatherbox-data` (Compose adds the
project name). They survive container recreation and `docker compose down`.
**`docker compose down -v` deletes this volume, including all runtime data.**
Back up the configuration and volume together.
The image runs as an unprivileged user with UID/GID `10001:10001`; Docker sets
up write permissions when it first creates the empty volume.

For direct host access, for example from an existing Caddy or nginx instance,
replace the `/var/lib/weatherbox` volume entry in `compose.yaml` with a bind mount:

```yaml
      - type: bind
        source: ./var/docker
        target: /var/lib/weatherbox
        bind:
          create_host_path: false
```

Create the directory first and, on Linux, make it writable by UID/GID
`10001:10001`, for example with
`sudo install -d -o 10001 -g 10001 -m 0755 var/docker`.
Configuration and assets must be readable by this user. Changing the mount does
not automatically transfer existing data; when migrating, stop the scheduler
and transfer the cache, state, and audio directories.

Weatherbox does not open a network port. For HTTP delivery, point a separate
web server exclusively at the `public` subdirectory — `var/docker/public` on
the host with the bind mount above. A web server container can mount the data
volume read-only and use `/var/lib/weatherbox/public` as its document root.
The cache and state must stay outside the public document root. The headers in
[deploy/Caddyfile.example](../deploy/Caddyfile.example) also apply to this setup.

## Status, manual commands, and updates

```bash
docker compose exec weatherbox wb-announcer --config /etc/weatherbox/config.yaml status

# Stop the scheduler before running manual commands that write data.
docker compose stop weatherbox
docker compose run --rm weatherbox weather-update
docker compose run --rm weatherbox generate-all
docker compose up -d

# After updating the source code, rebuild the image and replace the service.
docker compose build --pull
docker compose up -d

# Remove containers while keeping runtime data.
docker compose down
```

Other CLI commands work the same way, for example
`docker compose run --rm weatherbox cleanup-generated --older-than-days 30`.
Compose limits container logs to three files of 10 MB each.

## Optional: Piper in the image

Enable the optional [Piper installation](https://github.com/OHF-Voice/piper1-gpl)
at build time by creating or updating a `.env` file in the repository with:

```dotenv
INSTALL_PIPER=true
```

Then run `docker compose build --pull`. The Dockerfile installs
`piper-tts==1.7.0`; compatible packages must be available for your Linux
architecture. Place the desired `.onnx` model and its accompanying `.onnx.json`
file under `docker-config/models/` and update the YAML configuration:

```yaml
tts:
  provider: piper
  fallback_provider: espeak-ng
  piper:
    executable: piper
    model: models/de_DE-thorsten-medium.onnx
```

Piper can also serve as a fallback for gTTS. Models are not downloaded
automatically. Afterwards, run `docker compose up -d --force-recreate` to
activate both the new image and the configuration.
