from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from weatherbox.models import ForecastBundle, WeatherData


class WeatherCache:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def path_for(self, location_id: str) -> Path:
        return self.directory / f"{location_id}.json"

    def save(self, location_id: str, bundle: ForecastBundle) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        payload = {
            "fetched_at": bundle.fetched_at.isoformat(),
            "forecasts": [item.to_dict() for item in bundle.forecasts],
        }
        fd, temporary_name = tempfile.mkstemp(prefix=f".{location_id}-", suffix=".tmp", dir=self.directory)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path_for(location_id))
        finally:
            temporary.unlink(missing_ok=True)

    def load(self, location_id: str) -> ForecastBundle | None:
        try:
            payload = json.loads(self.path_for(location_id).read_text(encoding="utf-8"))
            fetched_at = datetime.fromisoformat(payload["fetched_at"])
            forecasts = tuple(WeatherData.from_dict(item) for item in payload["forecasts"])
            if fetched_at.tzinfo is None or any(item.forecast_at.tzinfo is None for item in forecasts):
                return None
            return ForecastBundle(fetched_at=fetched_at, forecasts=forecasts)
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            return None

    @staticmethod
    def is_fresh(bundle: ForecastBundle, now: datetime, max_age_minutes: int) -> bool:
        age = now - bundle.fetched_at.astimezone(now.tzinfo)
        return timedelta(0) <= age <= timedelta(minutes=max_age_minutes)

