# tap-usgs-earthquakes

A Singer tap, built with the Meltano Singer SDK, that extracts earthquake events from the public
[USGS Earthquake Catalog API](https://earthquake.usgs.gov/fdsnws/event/1/). It requires no API key.

## Quickstart

With Meltano installed:

```sh
meltano install
meltano run tap-usgs-earthquakes target-jsonl
```

The demo defaults to earthquakes of magnitude 2.5 or greater. To run the tap directly, provide a
config file containing `{}` or any optional settings:

```sh
uv run tap-usgs-earthquakes --config tests/fixtures/empty_config.json --discover
```

The Singer SDK CLI accepts a config file path rather than an inline JSON object.

## Settings

| Setting | Default | Description |
|---|---|---|
| `start_date` | 30 days before execution | Earliest event time to scan, in UTC |
| `min_magnitude` | all magnitudes | Minimum magnitude |
| `window_days` | 7 | Size of each time window |
| `user_agent` | project identifier | User-Agent sent to USGS |

All settings are optional. The tap explicitly sends `starttime` and `endtime` so the API's own
30-day default is never relied upon.

## Stream and schema

| Stream | Method | Primary key | Replication key |
|---|---|---|---|
| `earthquakes` | GeoJSON query | `id` | `updated` |

The stream flattens event properties and geometry into a record containing ISO-8601 `time` and
`updated`, `longitude`, `latitude`, `depth_km`, magnitude metadata, and the other documented USGS
properties. See [API notes](docs/API_NOTES.md) and the checked-in [schema](tap_usgs_earthquakes/schemas/earthquakes.json).

## Incremental sync

USGS cannot order results by `updated`; it only supports time and magnitude orderings. The tap
therefore marks the stream as unsorted, uses `updated` as the replication key, and only advances
state after the complete stream finishes. On incremental runs it sends `updatedafter` together with
the explicit historical `starttime`, so an old earthquake revised recently is still found.

Time windows are sized with `/count` and recursively split before any query can exceed USGS's
20,000-event limit. Inclusive window boundaries are deduplicated by event ID.

## Limitations

- A long historical `start_date` can require many count and query requests.
- The tap uses one request at a time and backs off on transient API failures.
- Unit tests are offline; live tests should be run explicitly with `RUN_LIVE_TESTS=1`.
- Deleted or retracted events are not emitted because the tap does not request USGS's
  `includedeleted` extension.

## Built with Codex

The implementation record is in [BUILD_LOG.md](BUILD_LOG.md).
