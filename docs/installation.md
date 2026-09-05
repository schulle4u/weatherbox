# Installation and Linux service

[Project overview and quick start](../README.md) · [Documentation index](README.md)

## Native installation requirements

Python 3.11 or later, `ffmpeg`, and `ffprobe` must be available on your PATH.
gTTS is installed with Weatherbox. The quick-start configuration uses
Open-Meteo and gTTS and requires outbound internet access.
Piper or eSpeak NG is only required if configured as the primary or fallback
speech provider.

Example for Debian/Ubuntu or Raspberry Pi OS with Python 3.11 or later:

```bash
sudo apt update
sudo apt install python3 python3-venv ffmpeg
```

For the optional local eSpeak provider, also install `espeak-ng`.
On macOS, install Python and FFmpeg using your preferred package manager.
On Windows, the directories containing `ffmpeg.exe` and `ffprobe.exe` must be
on your `PATH`. Alternatively, set their paths using `audio.ffmpeg` and
`audio.ffprobe` in the [configuration](configuration.md).

## Linux and macOS

From the downloaded or cloned project directory:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
cp docs/config.quickstart.yaml config.yaml
```

Open `config.yaml` and update the name, coordinates, and time zone under
`locations`. Then generate your first announcements:

```bash
wb-announcer --config config.yaml generate-all
```

Files are saved under `var/public/<location-id>/`. For continuous operation,
run `wb-announcer --config config.yaml serve`; stop the process with `Ctrl+C`.

## Windows with PowerShell

From the project directory, without activating the virtual environment:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
Copy-Item docs/config.quickstart.yaml config.yaml
```

Update the location in `config.yaml` first, then run:

```powershell
.\.venv\Scripts\wb-announcer.exe --config config.yaml generate-all
.\.venv\Scripts\wb-announcer.exe --config config.yaml serve
```

The second command starts continuous operation in the terminal. For Docker
on Windows, follow the [Docker guide](docker.md).

## Linux service with systemd

The included units expect the project under `/opt/weatherbox`, a Python virtual
environment under `/opt/weatherbox/.venv`, configuration at
`/etc/weatherbox/config.yaml`, and writable data under `/var/lib/weatherbox`.
The following steps describe a new installation. For existing installations,
reuse the user and directories and keep the existing configuration.

### 1. Set up the application and service user

After installing the system dependencies listed above and Git:

```bash
sudo git clone https://github.com/schulle4u/weatherbox.git /opt/weatherbox
cd /opt/weatherbox
sudo python3 -m venv .venv
sudo .venv/bin/python -m pip install .
sudo useradd --system --user-group --home-dir /var/lib/weatherbox --no-create-home weatherbox
sudo install -d -m 0755 /etc/weatherbox
sudo install -d -o weatherbox -g weatherbox -m 0755 /var/lib/weatherbox
sudo install -m 0644 docs/config.quickstart.yaml /etc/weatherbox/config.yaml
```

### 2. Customize the configuration and try it out

Edit `/etc/weatherbox/config.yaml` with administrator privileges: update the
location and replace the entire `output` section with the following. Relative
paths would otherwise point into the read-only configuration directory.

```yaml
output:
  cache_dir: /var/lib/weatherbox/cache
  generated_dir: /var/lib/weatherbox/generated
  generated_retention_days: 30
  public_dir: /var/lib/weatherbox/public
  state_dir: /var/lib/weatherbox/state
```

Then run a test as the service user:

```bash
sudo -u weatherbox /opt/weatherbox/.venv/bin/wb-announcer --config /etc/weatherbox/config.yaml generate-all
```

Audio and optional HTML files are saved under
`/var/lib/weatherbox/public/<location-id>/`.
Custom models, language files, and jingles must be readable by the `weatherbox`
user. The service unit blocks access to home directories; use subdirectories
of `/etc/weatherbox`, for example, for these files.

### 3. Enable the timer

```bash
sudo install -m 0644 deploy/systemd/weatherbox.service deploy/systemd/weatherbox.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now weatherbox.timer
systemctl list-timers weatherbox.timer
sudo journalctl -u weatherbox.service -n 50
```

The timer starts a short `run` pass every minute. Weatherbox uses its
configuration to determine which announcements are due and which need retries.
Do not run an additional `serve` process or Docker scheduler against the same
data. Before running manual commands that write data, stop the timer and wait
for any active service run to finish; restart the timer afterwards.

## Serving files over HTTP

Weatherbox does not include a public web server. Caddy or nginx can deliver
audio files to players. Use only `public_dir` as the document root —
`/var/lib/weatherbox/public` for the Linux service.
The cache and scheduler state do not belong in this directory.

The [Caddy example](../deploy/Caddyfile.example) includes the document root
and cache headers for the supported audio formats. Replace `audio.example.org`
with your domain and incorporate the settings into your Caddy setup.
Announcements will then be available at addresses such as
`https://audio.example.org/wittstock/full-hour.mp3`.
For Docker, the [Docker guide](docker.md#configuration-files-and-persistent-data)
explains how to access the data volume.

Files are replaced before their scheduled playback time. Players must download
them in time and manage playback scheduling themselves.
