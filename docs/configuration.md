# Configuration

[Project overview and quick start](../README.md) · [Documentation index](README.md)

## Configuration file and examples

Weatherbox reads a YAML file selected with `wb-announcer --config config.yaml`.
All command examples assume you are in the project directory.
Copy an example there before using it:

| Example | Purpose |
| --- | --- |
| [config.quickstart.yaml](config.quickstart.yaml) | Simple setup with Open-Meteo and gTTS, without models or audio files |
| [config.example.yaml](config.example.yaml) | Full example with DWD, Piper fallback, and jingles |
| [Docker configuration](../deploy/docker/config.example.yaml) | Compose operation with absolute container paths and eSpeak fallback |

```bash
cp docs/config.example.yaml config.yaml
```

Customize the full example before starting: it references a Piper model and
audio files that are not included. Install and configure those files, or choose
a different TTS provider/fallback and remove the optional jingle entries.
`fallback_provider: null` disables the fallback. A jingle can be omitted or
disabled with `null`.

Relative file and directory paths are always resolved against the directory
containing the configuration file, not the working directory.
Restart continuous operation (`serve` or Docker) after making changes.

## Structure and locations

| Section | Purpose |
| --- | --- |
| `application` | Log level and JSON logs |
| `localization` | Default language and custom language files |
| `weather` | Weather sources, cache age, and merging |
| `scheduler` | Preparation window and retries |
| `tts` | Speech generation, fallback, and voices per language |
| `audio` | FFmpeg/FFprobe, loudness, formats, and jingles |
| `text` | Optional static HTML assets and their page template |
| `output` | Data directories and retention period |
| `announcements` | Shared text for hourly and half-hourly announcements |
| `locations` | Locations and their individual settings |

Each location requires `name`, `latitude`, `longitude`, and `timezone`.
The location ID determines the output subdirectory. It starts with a letter
or digit and contains only ASCII letters, digits, hyphens, and underscores,
for example `wittstock_nord`.

```yaml
locations:
  wittstock:
    name: Wittstock
    latitude: 53.16
    longitude: 12.48
    timezone: Europe/Berlin
    language: de
    temperature_unit: c
    enabled: true
```

Add more locations as additional entries under `locations`.
`enabled: false` excludes a location from regular processing.
`temperature_unit` accepts `c` (the default) or `f`.
When DWD is enabled, each active location also requires `weather.dwd_station_id`.
Custom announcements under
`locations.<id>.announcements.<half_hour|full_hour>` override the global settings.
See the [template reference](templates.md) for text and language settings.

## Scheduling and data directories

`scheduler.preparation_minutes` specifies how many minutes before playback
generation starts (default: 10).
`scheduler.retry.interval_seconds` and `max_attempts` control retries for failed
announcements (defaults: 60 seconds and 5 attempts).
Weatherbox must be invoked regularly with `run` or continuously with `serve`;
the [operations guide](operations.md) explains these commands.

`output.cache_dir` stores weather data, `state_dir` stores scheduler state,
`generated_dir` stores versioned assets, and `public_dir` stores files
with stable names. All four directories must be writable. See
[output](operations.md#output) for cleanup details.

## Static HTML text assets

Weatherbox can publish a readable HTML page beside each audio announcement:

```yaml
text:
  enabled: true
  template: docs/template.example.html
```

The template path is optional and, like other configured paths, is resolved
relative to the configuration file. Without it, Weatherbox uses the built-in
page wrapper. The supplied [example template](template.example.html) supports
`{language}`, `{location}`, `{location_id}`, `{message}`, `{kind}`, `{date}`,
`{time}`, and `{year}`. Inserted values are HTML-escaped. Literal braces in
custom CSS or JavaScript must be doubled (`{{` and `}}`).

Text assets use the configured announcement sentence but format times, dates,
hours, and minutes for reading instead of spelling them with the pronunciation
rules. For example, German `{time}` is `14:00` in HTML while the corresponding
TTS text remains `vierzehn Uhr`. Weather descriptions and summaries remain
localized.

For a text-only setup, disable audio. Neither a TTS provider nor FFmpeg is
invoked during generation:

```yaml
audio:
  enabled: false
text:
  enabled: true
```

At least one of `audio.enabled` or `text.enabled` must be true. HTML files use
the same stable naming convention and directories as audio, for example
`var/public/wittstock/full-hour.html`.

## Intros, outros, and music beds

Hourly and half-hourly announcements can each have their own intro, outro,
and music bed:

```yaml
audio:
  jingles:
    half_hour:
      intro: assets/intro.wav
      outro: assets/outro.wav
      music: assets/music.wav
    full_hour:
      intro: assets/full-hour-intro.wav
    music_attenuation: -10
    music_fade_out: 2.5
```

Relative file paths are resolved against the configuration file. The music bed
is looped as needed, adjusted by `music_attenuation` decibels, and mixed into the
announcement. `music_fade_out` specifies how many seconds it continues and
fades out after the speech ends; the outro then begins.
`music_attenuation` must be less than or equal to zero, and `music_fade_out`
must be greater than or equal to zero. Locations can override individual files
under `locations.<id>.audio.jingles.<half_hour|full_hour>` or explicitly disable
them with an empty value.

## Audio output formats

Without a format setting, Weatherbox generates MP3 only. Enable multiple
formats using the compact syntax:

```yaml
audio:
  output:
    format: mp3, flac, opus
    sample_rate: 48000
    channels: 2
    bitrate: 192k
```

Alternatively, `formats` supports a separate bitrate for each lossy format:

```yaml
audio:
  output:
    sample_rate: 48000
    channels: 2
    formats:
      mp3:
        bitrate: 192k
      wav: {}
      flac: {}
      ogg:
        bitrate: 160k
      opus:
        bitrate: 96k
      m4a:
        bitrate: 192k
```

Supported formats are `mp3`, `wav` (16-bit PCM), `flac`, `ogg` (Vorbis), `opus`,
and `m4a` (AAC). `vorbis` and `aac` are accepted as aliases for `ogg` and `m4a`,
respectively. In addition to comma-separated values, `format` accepts a YAML
list. Do not set `format` and `formats` at the same time.
WAV and FLAC are lossless and have no bitrate setting. Opus supports sample
rates of 8000, 12000, 16000, 24000, or 48000 Hz. Publication begins only after
all configured formats have been generated successfully and validated with
FFprobe.

## Weather providers

Weatherbox retrieves data from the sources configured under `weather.providers`.
Open-Meteo uses location coordinates directly, while the DWD provider uses the
station-based WarnWetter API. Sources are merged field by field. When DWD is
configured, each active location requires a DWD station identifier:

```yaml
weather:
  providers:
    open-meteo:
      endpoint: https://api.open-meteo.com/v1/forecast
    dwd:
      endpoint: https://app-prod-ws.warnwetter.de/v30/stationOverviewExtended
  update_interval_minutes: 30
  max_cache_age_minutes: 60
  request_timeout_seconds: 15
  merge:
    tolerance_minutes: 30
    default_priority: [open-meteo, dwd]
    field_priority:
      temperature: [dwd, open-meteo]
      humidity: [dwd, open-meteo]
      pressure: [dwd, open-meteo]
      warnings: [dwd, open-meteo]

locations:
  wittstock:
    name: Wittstock
    latitude: 53.16
    longitude: 12.48
    timezone: Europe/Berlin
    temperature_unit: c
    weather:
      # WarnWetter/MOS identifier for Wittstock-Rote Mühle
      dwd_station_id: F143
    announcements:
      full_hour:
        template: >
          Es ist {time} in {location}. {weather_description}.
          {warning_text}.
```

Providers are queried in parallel. The time grid comes from the first available
provider in `default_priority`; values from other sources are matched to the
nearest timestamp within `tolerance_minutes`.
For each field, the first available value in its `field_priority` is used.
Providers not explicitly listed are automatically appended as fallbacks.
Values are not averaged. Warnings are combined and duplicates removed according
to warning priority. If only one provider is reachable, its results are still
used; retrieval fails only when all providers fail.

Temperatures are always stored in degrees Celsius internally and in the cache,
regardless of provider. When building an announcement, Weatherbox converts
`temperature`, `apparent_temperature`, `dew_point`, `day_temperature_min`, and
`day_temperature_max` to Celsius (`c`, the default) or Fahrenheit (`f`) according
to `locations.<id>.temperature_unit`. Multiple locations can therefore use
different units with the same weather providers. Templates should name the
unit appropriately as “degrees Celsius” or “degrees Fahrenheit”.

The station identifier is not necessarily the numeric `Stations_id` from CDC
open-data files. `stationOverviewExtended` only provides WarnWetter/MOS stations;
phenological identifiers such as `12471` for Wittstock/Dosse do not work there.
For the example location Wittstock, `F143` (`Wittstock-Rote Mühle`) is a suitable
identifier. The public
[Tiny Weather Forecast Germany station catalog](https://tinyweatherforecastgermanygroup.gitlab.io/index/stations.html)
can be used to find MOS identifiers if the DWD list linked from the
[DWD API documentation](https://dwd.api.bund.dev/) is unavailable.
Temperature, humidity, pressure, precipitation, and wind values from DWD are
converted from tenths into the same units used by Open-Meteo.
The DWD provider also reads daily minimum and maximum temperatures,
precipitation totals, weather conditions, and maximum wind and gust speeds
from the `days` section, and derives precipitation hours from the hourly series.
Because the DWD response does not contain every Open-Meteo field,
`{apparent_temperature}`, `{cloud_cover}`, `{precipitation_probability}`,
`{day_cloud_cover_mean}`, and `{day_precipitation_probability_max}` in particular
remain unset for DWD. When both providers are used, Open-Meteo supplies these
values according to the merge priority.

## Cloud speech generation with gTTS

For simple cloud speech generation, Weatherbox uses the gTTS Python API
directly; it does not start `gtts-cli` as a subprocess. gTTS accesses the
Google Translate text-to-speech service and returns MP3 data. This is separate
from the paid Google Cloud Text-to-Speech API and requires no API key.
Because gTTS cannot guarantee the underlying service, a local fallback is
recommended:

```yaml
tts:
  provider: gtts
  fallback_provider: piper
  gtts:
    language: de
    tld: de
    slow: false
    timeout_seconds: 15
  piper:
    executable: piper
    model: models/de_DE-kerstin-low.onnx
```

`language` is the gTTS language code. `tld` selects the Google domain and can
affect regional pronunciation. Network errors, timeouts, or service failures
automatically trigger the configured fallback.

To select the appropriate voice for gTTS, Piper, or eSpeak NG, TTS settings
can also be overridden per language:

```yaml
tts:
  provider: gtts
  fallback_provider: piper
  gtts:
    language: de
    tld: de
  piper:
    model: models/de_DE-kerstin-low.onnx
  espeak-ng:
    voice: de
  languages:
    en:
      piper:
        model: models/en_GB-alba-medium.onnx
      espeak-ng:
        voice: en-gb
      gtts:
        language: en
        tld: co.uk
```

If a language-specific TTS setting is missing, the global value is used.
Only gTTS automatically derives `language` from the location language; an
explicit language-specific setting can override that mapping.
