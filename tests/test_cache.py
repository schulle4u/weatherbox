from datetime import timedelta

from weatherbox.models import ForecastBundle, WeatherWarning
from weatherbox.weather.cache import WeatherCache


def test_cache_round_trip_and_age(tmp_path, now, weather):
    cache = WeatherCache(tmp_path)
    bundle = ForecastBundle(fetched_at=now, forecasts=(weather,))
    cache.save("wittstock", bundle)

    loaded = cache.load("wittstock")
    assert loaded == bundle
    assert cache.is_fresh(loaded, now + timedelta(minutes=59), 60)
    assert not cache.is_fresh(loaded, now + timedelta(minutes=61), 60)


def test_corrupt_cache_is_ignored(tmp_path):
    cache = WeatherCache(tmp_path)
    tmp_path.mkdir(exist_ok=True)
    cache.path_for("broken").write_text("{not json", encoding="utf-8")
    assert cache.load("broken") is None


def test_cache_round_trip_preserves_warnings(tmp_path, now, weather):
    warning = WeatherWarning(
        level=2,
        event="WIND",
        headline="Amtliche Warnung vor Windböen",
        start=now,
        end=now + timedelta(hours=2),
        source="dwd",
    )
    cache = WeatherCache(tmp_path)
    sourced_weather = weather.with_source("open-meteo")
    bundle = ForecastBundle(
        fetched_at=now, forecasts=(sourced_weather,), warnings=(warning,)
    )

    cache.save("warned", bundle)

    assert cache.load("warned") == bundle
