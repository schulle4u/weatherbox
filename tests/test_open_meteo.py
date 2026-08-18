from weatherbox.weather.open_meteo import OpenMeteoProvider


def test_open_meteo_payload_is_mapped_to_internal_model():
    hourly = {
        "time": ["2026-08-18T14:00"],
        "temperature_2m": [18.2],
        "apparent_temperature": [17.5],
        "dew_point_2m": [12.1],
        "relative_humidity_2m": [71],
        "surface_pressure": [1013.2],
        "weather_code": [2],
        "cloud_cover": [42],
        "precipitation": [0],
        "precipitation_probability": [10],
        "wind_speed_10m": [12.4],
        "wind_direction_10m": [225],
        "wind_gusts_10m": [21],
    }
    payload = {
        "hourly": hourly,
        "daily": {
            "time": ["2026-08-18"],
            "sunrise": ["2026-08-18T05:48"],
            "sunset": ["2026-08-18T20:28"],
        },
    }
    bundle = OpenMeteoProvider._parse(payload, "Europe/Berlin")
    value = bundle.forecasts[0]
    assert value.temperature == 18.2
    assert value.weather_code == 2
    assert value.forecast_at.utcoffset().total_seconds() == 7200
    assert value.sunrise.hour == 5

