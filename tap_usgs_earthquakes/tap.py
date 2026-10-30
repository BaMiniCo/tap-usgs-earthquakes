from __future__ import annotations

from datetime import datetime, timedelta, timezone

from singer_sdk import Tap
from singer_sdk import typing as th

from tap_usgs_earthquakes.streams import EarthquakesStream


def default_start_date() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()


class TapUsgsEarthquakes(Tap):
    name = "tap-usgs-earthquakes"
    config_jsonschema = th.PropertiesList(
        th.Property("start_date", th.DateTimeType, required=False),
        th.Property("min_magnitude", th.NumberType, required=False),
        th.Property("window_days", th.IntegerType, required=False, default=7),
        th.Property(
            "user_agent",
            th.StringType,
            required=False,
            default="tap-usgs-earthquakes (+https://github.com/example/tap-usgs-earthquakes)",
        ),
    ).to_dict()

    def discover_streams(self) -> list[EarthquakesStream]:
        return [EarthquakesStream(self)]
