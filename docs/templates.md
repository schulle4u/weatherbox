# Templates and languages

[Project overview and quick start](../README.md) · [Documentation index](README.md)

## Setting announcement text

Global text is configured under `announcements.half_hour.template` and
`announcements.full_hour.template`. A location can override it under
`locations.<id>.announcements`. Set `enabled: false` to disable either
announcement type. The examples below are snippets for your existing
[configuration](configuration.md).

## Template variables

Templates use placeholders in braces, for example:
`Es ist {time} in {location}. Die Temperatur beträgt {temperature} Grad.`
The following variables are currently supported:

| Variable | Content and output format |
| --- | --- |
| `{greeting}` | Greeting based on local time at the location: morning until 11:59, daytime from 12:00, and evening from 18:00; text is configured under `greetings` in the language file |
| `{time}` | Scheduled playback time in words in the location language, for example `vierzehn Uhr dreißig` |
| `{hour}` | Hour of scheduled playback in words in the location language, for example `vierzehn` |
| `{minute}` | Minute of scheduled playback as a number, for example `30` |
| `{date}` | Localized date of scheduled playback, for example `18. August 2026` |
| `{location}` | Configured display name of the location |
| `{latitude}` | Latitude of the location |
| `{longitude}` | Longitude of the location |
| `{temperature}` | Forecast temperature in the location's configured unit |
| `{apparent_temperature}` | Forecast feels-like temperature in the location's configured unit |
| `{dew_point}` | Forecast dew point in the location's configured unit |
| `{humidity}` | Relative humidity as a percentage |
| `{pressure}` | Surface air pressure in hectopascals |
| `{weather_description}` | Localized description of the provider-independent WMO weather code, for example `teilweise bewölkt` |
| `{weather_code}` | Numeric WMO weather code normalized internally |
| `{cloud_cover}` | Cloud cover as a percentage |
| `{wind_speed}` | Wind speed in kilometers per hour |
| `{wind_direction}` | Wind direction as a localized compass direction, for example `Südwesten` |
| `{wind_direction_degrees}` | Wind direction in degrees |
| `{wind_gusts}` | Wind gust speed in kilometers per hour |
| `{precipitation}` | Forecast precipitation amount in millimeters |
| `{precipitation_probability}` | Probability of precipitation as a percentage |
| `{day_temperature_min}` | Lowest temperature of the local calendar day in the configured temperature unit |
| `{day_temperature_max}` | Highest temperature of the local calendar day in the configured temperature unit |
| `{day_precipitation_sum}` | Expected total precipitation for the local calendar day in millimeters |
| `{day_precipitation_probability_max}` | Highest hourly precipitation probability for the local calendar day as a percentage |
| `{day_precipitation_hours}` | Number of hours with expected precipitation during the local calendar day |
| `{day_cloud_cover_mean}` | Mean cloud cover over the entire local calendar day as a percentage |
| `{day_weather_description}` | Localized description of the most significant weather conditions of the local calendar day |
| `{day_wind_speed_max}` | Highest wind speed of the local calendar day in kilometers per hour |
| `{day_wind_gusts_max}` | Highest gust speed of the local calendar day in kilometers per hour |
| `{day_weather_summary}` | Localized summary of daily weather conditions and minimum and maximum temperatures |
| `{day_cloud_summary}` | Localized daily summary derived from mean cloud cover |
| `{day_precipitation_summary}` | Localized summary of maximum precipitation probability and expected total precipitation |
| `{sunrise}` | Sunrise time in words in the location language, for example `fünf Uhr achtundvierzig` |
| `{sunset}` | Sunset time in words in the location language |
| `{forecast_time}` | Timestamp of the weather data used, in words in the location language |
| `{warning_count}` | Number of DWD warnings active at playback time |
| `{warning_level}` | DWD warning level of the highest-priority active warning |
| `{warning_event}` | Event name of the highest-priority warning |
| `{warning_headline}` | Headline of the highest-priority warning |
| `{warning_description}` | Detailed description of the highest-priority warning |
| `{warning_instruction}` | Recommended action from the highest-priority warning |
| `{warning_start}` | Start time of the highest-priority warning in localized time words |
| `{warning_end}` | End time of the highest-priority warning in localized time words |
| `{warning_text}` | Headlines of all active warnings, or a localized message that no warning is active |
| `{temperature_source}` | Provider of the temperature value used, for example `dwd` |
| `{weather_source}` | Provider of the weather code and description used |
| `{warning_source}` | Provider of the highest-priority active warning |

Numeric values are rounded to one decimal place, unnecessary decimal places
are removed, and the decimal separator is localized.
An unknown variable, a format specifier such as `{temperature:.1f}`, or a
referenced value that is unavailable in the current forecast causes generation
to stop with a controlled error. The previously published audio asset is preserved.
`{warning_count}` and `{warning_text}` are always populated. Other warning
fields can only be used when a corresponding warning is active at playback time.
With multiple warnings, individual fields refer to the warning with the highest
severity level; `{warning_text}` combines all headlines.
The `day_` variables refer to the local calendar date of scheduled playback.
Daily summaries are complete sentences and can be placed directly after one
another, for example:

```yaml
template: >
  Es ist {time} in {location}. {day_weather_summary}
  {day_cloud_summary} {day_precipitation_summary}
```

## Languages and pronunciation dictionaries

Weatherbox includes German (`de`) and English (`en`). Their YAML dictionaries
are in [src/weatherbox/lang/](../src/weatherbox/lang/). They contain:

- Numbers from zero to nineteen and multiples of ten up to fifty.
- Rules and exceptions for compound numbers.
- Context-dependent forms such as `ein Uhr` versus `eins`.
- Time and date patterns and month names.
- Decimal separators.
- Descriptions of provider-independent WMO weather codes.
- Sentence patterns for weather, cloud cover, and precipitation summaries.
- Sixteen compass directions.

The built-in summaries map mean daily cloud cover to fixed cloud-cover bands
and maximum precipitation probability to fixed probability bands. All output
sentences are stored under `summaries` in the corresponding language file and
can be replaced there. Older custom language files may omit this section;
the rest of the language remains usable, but the three summary variables will
be unset.

Choose the language separately for each location:

```yaml
localization:
  default_language: de
  # Optional: load complete custom YAML language files from this directory.
  directory: lang

locations:
  wittstock:
    name: Wittstock
    latitude: 53.16
    longitude: 12.48
    timezone: Europe/Berlin
    temperature_unit: c
    language: de

  london:
    name: London
    latitude: 51.51
    longitude: -0.13
    timezone: Europe/London
    temperature_unit: f
    language: en
    announcements:
      full_hour:
        template: >
          It is {time} in {location}. The temperature is {temperature} degrees.
          Conditions are {weather_description}.
```

Custom language files must follow the complete schema of a built-in file.
A file in the configured `localization.directory` overrides a built-in language
with the same `code`; new codes extend the catalog. Use `numbers.overrides` to
fully override irregular numbers. `time.hour_mode` supports 12-hour or 24-hour
output. Invalid or incomplete language files are rejected at startup.

Templates are not translated automatically. Each location using a different
language therefore needs suitable templates for its enabled announcement types.
