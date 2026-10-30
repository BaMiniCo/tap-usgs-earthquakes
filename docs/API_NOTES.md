# USGS Earthquake API notes

Verified against the live USGS FDSN Event API on 2026-10-30. The requests below
were made with `curl` and a descriptive User-Agent.

## Response shape

Request:

```sh
curl -A 'tap-usgs-earthquakes (+https://github.com/example/tap-usgs-earthquakes)' \
  'https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime=2026-10-01T00:00:00Z&endtime=2026-10-02T00:00:00Z&limit=3&offset=1&orderby=time-asc'
```

The response is a GeoJSON `FeatureCollection` with top-level keys `type`,
`metadata`, `features`, and `bbox` when features are present. `metadata` in the
observed response contained `generated`, `url`, `title`, `status`, `api`,
`limit`, and `offset`.

Each feature has `type`, `properties`, `geometry`, and `id`. Observed property
fields and representative types/nullability:

| Field | Observed type | Nullable/optional |
|---|---|---|
| `mag` | number | yes; may be null or absent |
| `place` | string | yes; may be null or absent |
| `time` | integer epoch milliseconds | yes; may be null or absent |
| `updated` | integer epoch milliseconds | yes; may be null or absent |
| `tz` | integer or null | yes |
| `url`, `detail`, `status`, `net`, `code`, `ids`, `sources`, `types`, `magType`, `type`, `title` | string | generally present, but nullable/optional should be tolerated |
| `felt`, `nst`, `tsunami`, `sig` | integer | `felt` and `nst` can be null; others observed present |
| `cdi`, `mmi`, `dmin`, `rms`, `gap` | number | nullable/optional |
| `alert` | string or null | yes |

`time` and `updated` are epoch milliseconds. `geometry.coordinates` is ordered
as `[longitude, latitude, depth_km]`.

The API uses `magType` (camel case), not `mag_type`; the tap can map it to
`mag_type` in its flattened output.

## Defaults and incremental filtering

The documentation says `starttime` defaults to `NOW - 30 days` and `endtime`
defaults to the present time. A live request with only `updatedafter` returned a
current event:

```sh
curl -A 'tap-usgs-earthquakes (+https://github.com/example/tap-usgs-earthquakes)' \
  'https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&limit=1&updatedafter=2026-10-30T00:00:00Z'
```

This demonstrates that `updatedafter` does not replace the implicit `starttime`
default. The tap must pass an explicit `starttime` on incremental requests so
old events revised recently are not missed.

## Pagination and result limits

The documentation and live responses confirm:

- `offset` is 1-based; `offset=1` returns the first result.
- `limit` accepts values through 20,000.
- `offset=4` with `limit=3` returns results four through six.
- The service rejects `limit=20001` with HTTP 400.
- `/count` uses the same query parameters and returns a JSON object such as
  `{"count":418,"maxAllowed":20000}` when requested with `format=geojson`.

The tap should use a much smaller page size, such as 1,000, and split windows
when `/count` reports more than 20,000 matching events.

## Ordering

Allowed values are `time`, `time-asc`, `magnitude`, and `magnitude-asc`.
`orderby=updated` returns HTTP 400 with the message:
`Bad orderby value "updated". Valid values are: "time", "time-asc", "magnitude", "magnitude-asc".`

Therefore the stream cannot claim that records are sorted by the `updated`
replication key; it must be configured as unsorted.

## Errors

An unknown parameter returns HTTP 400 and a plain-text body beginning:
`Error 400: Bad Request` followed by `Unknown parameter "bogus".`

An over-limit request returns HTTP 400 and a body beginning:
`Error 400: Bad Request` followed by
`Bad limit value "20001". Valid values are 0 <= limit <= 20000`.

The client should include the useful USGS error text in its raised error.

## Fixture requests

The following real responses are stored in `tests/fixtures/`:

```sh
curl -A 'tap-usgs-earthquakes (+https://github.com/example/tap-usgs-earthquakes)' \
  'https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime=2026-10-01T00:00:00Z&endtime=2026-10-02T00:00:00Z&limit=3&offset=1&orderby=time-asc'

curl -A 'tap-usgs-earthquakes (+https://github.com/example/tap-usgs-earthquakes)' \
  'https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime=2026-10-01T00:00:00Z&endtime=2026-10-02T00:00:00Z&limit=3&offset=4&orderby=time-asc'

curl -A 'tap-usgs-earthquakes (+https://github.com/example/tap-usgs-earthquakes)' \
  'https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime=2026-10-01&endtime=2026-10-02&minmagnitude=9.9'

curl -A 'tap-usgs-earthquakes (+https://github.com/example/tap-usgs-earthquakes)' \
  'https://earthquake.usgs.gov/fdsnws/event/1/count?format=geojson&starttime=2026-10-01&endtime=2026-10-02'
```
