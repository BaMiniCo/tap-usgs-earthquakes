from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import requests_mock

from tap_usgs_earthquakes import TapUsgsEarthquakes
from tap_usgs_earthquakes.streams import EarthquakesStream

FIXTURES = Path(__file__).parent / "fixtures"


def test_flatten_record_converts_time_and_coordinates() -> None:
    payload = json.loads((FIXTURES / "query_page1.json").read_text())
    record = EarthquakesStream.flatten_record(payload["features"][0])
    assert record["id"] == "aka2026tkfzmc"
    assert record["time"] == "2026-10-01T00:00:21.945000Z"
    assert record["updated"] == "2026-10-13T17:35:40.905000Z"
    assert record["longitude"] == -143.571
    assert record["latitude"] == 69.45
    assert record["depth_km"] == 10
    assert record["mag_type"] == "ml"


def test_empty_fixture_has_no_features() -> None:
    payload = json.loads((FIXTURES / "query_empty.json").read_text())
    assert payload["features"] == []


def test_windows_split_when_count_exceeds_limit(monkeypatch) -> None:
    stream = object.__new__(EarthquakesStream)
    stream._config = {}
    calls = []

    def count(start, end):
        calls.append((start, end))
        return 20_001 if (end - start).days >= 2 else 1

    monkeypatch.setattr(stream, "_count", count)
    start = datetime(2026, 10, 1, tzinfo=timezone.utc)
    end = datetime(2026, 10, 5, tzinfo=timezone.utc)
    windows = list(stream._windows(start, end))
    assert len(windows) == 4
    assert len(calls) > 1


def test_pagination_stops_and_deduplicates(monkeypatch) -> None:
    stream = TapUsgsEarthquakes(config={}).streams["earthquakes"]
    payload = json.loads((FIXTURES / "query_page1.json").read_text())
    pages = [payload, {"features": [payload["features"][0]]}]
    monkeypatch.setattr(stream, "_windows", lambda start, end: iter([(start, end)]))
    monkeypatch.setattr(stream, "_start_date", lambda: __import__("datetime").datetime(2026, 10, 1))
    monkeypatch.setattr(stream, "_end_date", lambda: __import__("datetime").datetime(2026, 10, 2))
    monkeypatch.setattr(stream, "_count", lambda start, end: 1)
    monkeypatch.setattr(stream, "_request_json", lambda params: pages.pop(0))
    records = list(stream.get_records(None))
    assert len(records) == 3


def test_retry_then_success(monkeypatch) -> None:
    stream = TapUsgsEarthquakes(config={}).streams["earthquakes"]

    def zero_wait():
        while True:
            yield 0

    monkeypatch.setattr(stream, "backoff_wait_generator", zero_wait)
    with requests_mock.Mocker() as mock:
        mock.get(
            "https://earthquake.usgs.gov/fdsnws/event/1/query",
            response_list=[{"status_code": 503}, {"json": {"features": []}}],
        )
        assert stream._request_json({"limit": 1}) == {"features": []}
        assert mock.call_count == 2


def test_bad_request_contains_usgs_error(monkeypatch) -> None:
    stream = TapUsgsEarthquakes(config={}).streams["earthquakes"]
    with requests_mock.Mocker() as mock:
        mock.get(
            "https://earthquake.usgs.gov/fdsnws/event/1/query",
            status_code=400,
            text='Error 400: Bad Request\nUnknown parameter "bogus".',
        )
        try:
            stream._request_json({"bogus": 1})
        except Exception as exc:
            assert "Unknown parameter" in str(exc)
        else:
            raise AssertionError("expected RuntimeError")


def test_incremental_window_has_explicit_start_and_updatedafter(monkeypatch) -> None:
    stream = TapUsgsEarthquakes(config={}).streams["earthquakes"]
    bookmark = "2026-10-30T00:00:00Z"
    monkeypatch.setattr(stream, "get_starting_replication_key_value", lambda _: bookmark)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 1, 8, tzinfo=timezone.utc)
    params = stream._window_params(start, end)
    assert params["starttime"] == "2026-01-01T00:00:00Z"
    assert params["endtime"] == "2026-01-08T00:00:00Z"
    assert params["updatedafter"] == bookmark


def test_incremental_sync_advances_state_and_skips_unchanged_window(monkeypatch, capsys) -> None:
    from datetime import datetime, timezone

    query_payload = json.loads((FIXTURES / "query_page1.json").read_text())
    start = datetime(2026, 10, 1, tzinfo=timezone.utc)
    end = datetime(2026, 10, 2, tzinfo=timezone.utc)
    config = {"start_date": start.isoformat(), "window_days": 7}

    with requests_mock.Mocker() as mock:
        mock.get(
            "https://earthquake.usgs.gov/fdsnws/event/1/count",
            response_list=[{"json": {"count": 3}}, {"json": {"count": 0}}],
        )
        mock.get(
            "https://earthquake.usgs.gov/fdsnws/event/1/query",
            json=query_payload,
        )

        first_tap = TapUsgsEarthquakes(config=config)
        monkeypatch.setattr(first_tap.streams["earthquakes"], "_end_date", lambda: end)
        first_tap.sync_all()
        first_output = capsys.readouterr().out.splitlines()
        state_line = next(line for line in first_output if '"type":"STATE"' in line)
        first_state = json.loads(state_line)["value"]
        expected_max = max(
            record["updated"]
            for record in (
                EarthquakesStream.flatten_record(feature) for feature in query_payload["features"]
            )
        )
        assert first_state["bookmarks"]["earthquakes"]["replication_key_value"] == expected_max

        second_tap = TapUsgsEarthquakes(config=config, state=first_state)
        monkeypatch.setattr(second_tap.streams["earthquakes"], "_end_date", lambda: end)
        second_tap.sync_all()
        second_output = capsys.readouterr().out

        query_calls = [
            request for request in mock.request_history if request.path.endswith("/query")
        ]
        count_calls = [
            request for request in mock.request_history if request.path.endswith("/count")
        ]
        assert len(query_calls) == 1
        assert len(count_calls) == 2
        assert count_calls[1].qs["updatedafter"] == [expected_max.lower()]
        assert '"type":"RECORD"' not in second_output
