"""Weather adapter: Open-Meteo when requested, SQLite mock on any failure."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

from config import DB_PATH
from services.database import get_demo_time, get_weather_context


def _open_meteo_forecast() -> dict[str, Any]:
    params = urlencode(
        {
            "latitude": 37.5665,
            "longitude": 126.9780,
            "hourly": "temperature_2m,precipitation_probability,rain,relative_humidity_2m",
            "timezone": "Asia/Seoul",
            "forecast_days": 1,
        }
    )
    with urlopen(f"https://api.open-meteo.com/v1/forecast?{params}", timeout=3) as response:
        payload = json.load(response)
    hourly = payload["hourly"]
    now = datetime.now().replace(minute=0, second=0, microsecond=0)
    timestamps = [datetime.fromisoformat(item) for item in hourly["time"]]
    index = min(range(len(timestamps)), key=lambda idx: abs((timestamps[idx] - now).total_seconds()))

    def item(offset: int) -> dict[str, Any]:
        idx = min(index + offset, len(timestamps) - 1)
        return {
            "timestamp": timestamps[idx].isoformat(),
            "temperature": hourly["temperature_2m"][idx],
            "precipitation_probability": hourly["precipitation_probability"][idx],
            "rainfall": hourly["rain"][idx],
            "humidity": hourly["relative_humidity_2m"][idx],
            "provider": "Open-Meteo API",
        }

    return {"current": item(0), "forecast_1h": item(1)}


def get_weather(db_path: Path | str = DB_PATH) -> dict[str, Any]:
    provider = os.getenv("WEATHER_PROVIDER", "mock").lower()
    if provider in {"open-meteo", "open_meteo", "live"}:
        try:
            return _open_meteo_forecast()
        except Exception as exc:
            result = get_weather_context(db_path)
            result["fallback_reason"] = f"Live weather unavailable: {type(exc).__name__}"
            return result
    return get_weather_context(db_path)

