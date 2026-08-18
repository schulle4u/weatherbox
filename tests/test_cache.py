from datetime import timedelta

from weatherbox.models import ForecastBundle
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

