# Operation and command line

[Project overview and quick start](../README.md) · [Documentation index](README.md)

For native installations, run the commands below from the project directory
with the Python environment activated. For containers, see
[Docker commands](docker.md#status-manual-commands-and-updates).
Only one scheduler instance may use the same runtime data. Stop it before
running manual commands that write data, then start it again afterwards.

## CLI

```text
wb-announcer --config config.yaml weather-update
wb-announcer --config config.yaml run
wb-announcer --config config.yaml serve --interval-seconds 60
wb-announcer --config config.yaml generate-half-hour
wb-announcer --config config.yaml generate-full-hour
wb-announcer --config config.yaml generate-location wittstock
wb-announcer --config config.yaml generate-all
wb-announcer --config config.yaml generate-time wittstock full_hour --at 2026-08-18T14:00:00+02:00
wb-announcer --config config.yaml cleanup-generated
wb-announcer --config config.yaml cleanup-generated --older-than-days 30
wb-announcer --config config.yaml status
```

`run` is intended for regular invocation by systemd. The application determines
which announcements fall within the configured preparation window.
`serve` runs one pass immediately, then waits the specified number of seconds
between passes (default: 60). Passes run sequentially; the scheduler continues
to retry individual announcements that fail.
SIGTERM and SIGINT stop continuous operation after the current pass completes;
during the wait period, shutdown is immediate. Configuration changes require
restarting `serve`.
Manual generation commands process each location independently and return
success or failure for each announcement. On success, all configured output
formats are published.

`status` reports the current state as JSON. A `degraded` status is normal on a
fresh start with an empty weather cache. `generate-all` immediately generates
both announcement types for their respective next playback times, fetching
weather data as needed. `serve` only generates announcements that are due
within the preparation window.

## Output

An announcement for Wittstock might produce:

```text
var/generated/wittstock/2026-08-18/14-00-full.mp3
var/generated/wittstock/2026-08-18/14-00-full.flac
var/generated/wittstock/2026-08-18/14-00-full.opus
var/public/wittstock/full-hour.mp3
var/public/wittstock/full-hour.flac
var/public/wittstock/full-hour.opus
```

Only the files with stable names under `public_dir` are served by Caddy or
nginx. The Python application does not provide a public web server.

Set `output.generated_retention_days` to define a retention period for files
under `generated_dir`. Before each `run`, Weatherbox deletes files whose last
modification time is older than the retention period, then removes empty
subdirectories. A value of `30` means 30 days. If the setting is omitted or
`null`, automatic cleanup is disabled.
`cleanup-generated` triggers cleanup manually; `--older-than-days` overrides
the configured period for that invocation. Files under `public_dir` are not
modified by cleanup.
