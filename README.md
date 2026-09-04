# Weatherbox

English | [Deutsch](README-de.md)

Weatherbox automatically creates spoken weather reports for your locations —
for example, for an internet radio station or a Raspberry Pi used as a player.
Announcements are prepared for the hour and half-hour and made available as
finished audio files. Play them using your own radio automation software or
audio player. Once downloaded, announcements can be played even without an
internet connection.

You can set up multiple locations, use German or English announcement text,
and add your own intros, outros, and background music.
Weather data comes from Open-Meteo and/or the German Weather Service (DWD);
speech is generated using gTTS, Piper, or eSpeak NG.
The default output is MP3, with other audio formats available.

## Choose an installation method

| Option | Best suited for |
| --- | --- |
| [Docker Compose](#quick-start-with-docker-compose) | Quick setup and continuous operation with just a few commands |
| [Python](#quick-start-with-python) | Trying Weatherbox locally or running it on your own computer |
| [Linux service with systemd](#running-as-a-linux-service) | Automatic operation on a server or Raspberry Pi |

Download the repository or clone it with Git. Run the following commands
from the project directory:

```bash
git clone https://github.com/schulle4u/weatherbox.git
cd weatherbox
```

## Quick start with Docker Compose

Requirements: Docker with Linux containers and Docker Compose.
Python and audio tools are already included in the image.

1. **Copy the configuration.**

   ```bash
   mkdir docker-config
   cp deploy/docker/config.example.yaml docker-config/config.yaml
   ```

2. **Set your location.** Open `docker-config/config.yaml` and enter the place
   name, latitude, longitude, and time zone under `locations`.
   You can keep the example location, Wittstock, for a first try.

3. **Generate your first announcements and start continuous operation.**

   ```bash
   docker compose build --pull
   docker compose run --rm weatherbox generate-all
   docker compose up -d
   ```

MP3 files are stored in the data volume under
`/var/lib/weatherbox/public/wittstock/`. Copy them to your computer to listen:

```bash
docker compose cp weatherbox:/var/lib/weatherbox/public ./weatherbox-audio
```

Replace `wittstock` with your own location ID if you changed it.
View progress and errors with `docker compose logs -f weatherbox`.
The example configuration requires internet access for weather data and gTTS.
See the [Docker guide](docs/docker.md) for updates, custom voices, and file access.

## Quick start with Python

Requirements: Python 3.11 or later and FFmpeg, including FFprobe, on your PATH.
The commands below are for Linux/macOS; setup details and PowerShell commands
are in the [installation guide](docs/installation.md).

1. **Install Weatherbox.**

   ```bash
   python3 -m venv .venv
   . .venv/bin/activate
   python -m pip install .
   ```

2. **Copy the configuration and set your location.**

   ```bash
   cp docs/config.quickstart.yaml config.yaml
   ```

   Open `config.yaml` and update the place name, coordinates, and time zone
   under `locations`. You can keep Wittstock for a first try.
   This example requires internet access but no additional voices or audio files.

3. **Generate announcements and listen.**

   ```bash
   wb-announcer --config config.yaml generate-all
   ```

   Open `var/public/wittstock/full-hour.mp3` or `half-hour.mp3` in your audio
   player. If you chose a different location ID, the subdirectory uses that name.

For continuous generation, run `wb-announcer --config config.yaml serve`.
The process runs until you stop it with `Ctrl+C`. Use Docker Compose or systemd
to start Weatherbox automatically after a reboot.

## Running as a Linux service

1. **Install:** Set up Weatherbox with Python under `/opt/weatherbox`.
2. **Configure:** Create the service user, configuration, and data directory.
3. **Enable:** Install the included systemd files and start the timer.

Commands you can copy are in the
[Linux service guide](docs/installation.md#linux-service-with-systemd).

## Using and customizing announcements

Weatherbox generates audio files; your player or radio automation software
handles scheduled playback. To retrieve files over the network, you can
[serve them through a web server](docs/installation.md#serving-files-over-http).

The supplied quick-start examples use German announcement text. For English
announcements, set the location language to `en` and provide English templates;
see [templates and languages](docs/templates.md).

Explore the [documentation index](docs/README.md) for more settings:
[configuration and voices](docs/configuration.md),
[announcement text and languages](docs/templates.md),
[operation and commands](docs/operations.md), and
[development](docs/development.md).
