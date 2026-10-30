from __future__ import annotations

import json
import time
from collections.abc import Iterable, Iterator, Mapping
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, cast

import requests
from singer_sdk.streams import RESTStream

BASE_URL = "https://earthquake.usgs.gov/fdsnws/event/1"
PAGE_SIZE = 1000
MAX_RESULTS = 20_000


class EarthquakesStream(RESTStream):
    name = "earthquakes"
    path = "/query"
    url_base = BASE_URL
    primary_keys = ["id"]
    replication_key = "updated"
    is_sorted = False
    records_jsonpath = "$.features[*]"
    rest_method = "GET"

    schema = json.loads((Path(__file__).parent / "schemas" / "earthquakes.json").read_text())

    @property
    def http_headers(self) -> dict[str, str]:
        return {"User-Agent": self.config.get("user_agent", "tap-usgs-earthquakes")}

    def get_url_params(
        self, context: Mapping[str, Any] | None, next_page_token: Any
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "format": "geojson",
            "orderby": "time-asc",
            "limit": PAGE_SIZE,
        }
        if next_page_token:
            params["offset"] = next_page_token
        if self.config.get("min_magnitude") is not None:
            params["minmagnitude"] = self.config["min_magnitude"]
        return params

    def prepare_request_payload(self, *args: Any, **kwargs: Any) -> None:
        return None

    def _start_date(self) -> datetime:
        configured = self.config.get("start_date")
        if configured:
            value = str(configured).replace("Z", "+00:00")
            return datetime.fromisoformat(value).astimezone(timezone.utc)
        return datetime.now(timezone.utc) - timedelta(days=30)

    def _end_date(self) -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _iso(value: int | float | None) -> str | None:
        if value is None:
            return None
        return (
            datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z")
        )

    @classmethod
    def flatten_record(cls, feature: dict[str, Any]) -> dict[str, Any]:
        properties = dict(feature.get("properties") or {})
        coordinates = feature.get("geometry", {}).get("coordinates", [None, None, None])
        record: dict[str, Any] = {
            "id": feature.get("id"),
            "time": cls._iso(properties.pop("time", None)),
            "updated": cls._iso(properties.pop("updated", None)),
            "longitude": coordinates[0],
            "latitude": coordinates[1],
            "depth_km": coordinates[2],
        }
        record.update(properties)
        if "magType" in record:
            record["mag_type"] = record.pop("magType")
        return record

    def _request_json(self, params: dict[str, Any], path: str = "/query") -> dict[str, Any]:
        for attempt in range(5):
            try:
                response = requests.get(
                    f"{self.url_base}{path}",
                    params=params,
                    headers=self.http_headers,
                    timeout=60,
                )
            except requests.RequestException:
                if attempt == 4:
                    raise
                time.sleep(2**attempt)
                continue
            if response.status_code in {429, 500, 502, 503, 504}:
                if attempt == 4:
                    response.raise_for_status()
                retry_after = response.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    delay = float(retry_after)
                elif retry_after:
                    retry_at = parsedate_to_datetime(retry_after)
                    delay = max(0, retry_at.timestamp() - time.time())
                else:
                    delay = 2**attempt
                time.sleep(delay)
                continue
            if response.status_code == 400:
                raise RuntimeError(f"USGS API request failed (400): {response.text.strip()}")
            response.raise_for_status()
            return cast(dict[str, Any], response.json())
        raise RuntimeError("USGS API request failed after retries")

    def _count(self, start: datetime, end: datetime) -> int:
        params: dict[str, Any] = {
            "format": "geojson",
            "starttime": start.isoformat().replace("+00:00", "Z"),
            "endtime": end.isoformat().replace("+00:00", "Z"),
        }
        if self.config.get("min_magnitude") is not None:
            params["minmagnitude"] = self.config["min_magnitude"]
        return int(self._request_json(params, path="/count")["count"])

    def _windows(self, start: datetime, end: datetime) -> Iterator[tuple[datetime, datetime]]:
        window_days = max(1, int(self.config.get("window_days", 7)))
        cursor = start
        while cursor < end:
            chunk_end = min(cursor + timedelta(days=window_days), end)
            yield from self._split_if_needed(cursor, chunk_end)
            cursor = chunk_end

    def _split_if_needed(
        self, start: datetime, end: datetime
    ) -> Iterator[tuple[datetime, datetime]]:
        count = self._count(start, end)
        if count <= MAX_RESULTS:
            yield start, end
            return
        midpoint = start + (end - start) / 2
        yield from self._windows(start, midpoint)
        yield from self._windows(midpoint, end)

    def _window_params(self, start: datetime, end: datetime) -> dict[str, Any]:
        params = self.get_url_params({}, None)
        params.update(
            starttime=start.isoformat().replace("+00:00", "Z"),
            endtime=end.isoformat().replace("+00:00", "Z"),
        )
        bookmark = self.get_starting_replication_key_value({})
        if bookmark:
            params["updatedafter"] = str(bookmark)
        return params

    def get_records(self, context: Mapping[str, Any] | None) -> Iterable[dict[str, Any]]:
        start = self._start_date()
        end = self._end_date()
        seen_ids: set[str] = set()
        for window_start, window_end in self._windows(start, end):
            params = self._window_params(window_start, window_end)
            offset = 1
            while True:
                page_params = dict(params, offset=offset)
                payload = self._request_json(page_params)
                features = payload.get("features", [])
                for feature in features:
                    record = self.flatten_record(feature)
                    record_id = str(record.get("id"))
                    if record_id in seen_ids:
                        continue
                    seen_ids.add(record_id)
                    yield record
                if len(features) < PAGE_SIZE:
                    break
                offset += PAGE_SIZE
