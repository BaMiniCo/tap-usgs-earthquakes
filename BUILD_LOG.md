# Build log

This log records the implementation phases, corrections, and verification results.

## Phase 0

- Investigated the live USGS FDSN Event API.
- Confirmed 1-based offsets, the 20,000 result limit, time-only ordering, and the interaction
  between `updatedafter` and the default start window.
- Captured query, empty-result, and count fixtures.

## Phase 1–4

- Scaffolded the Singer SDK tap.
- Implemented GeoJSON flattening, explicit windows, recursive count-based splitting, incremental
  filtering, deduplication at inclusive window boundaries, retries, and clear 400 errors.
- Added offline tests. All tests currently pass.

## Phase 5

- Added the Meltano demo configuration, Hub metadata, CI workflow, and quickstart documentation.

## Verification

The final verification command is:

```sh
ruff check . && ruff format --check . && mypy tap_usgs_earthquakes && pytest
```

Results in this workspace:

- `ruff check .`: passed
- `ruff format --check .`: passed
- `mypy tap_usgs_earthquakes`: passed
- `pytest`: 7 passed, 26 live tests deselected by default
- Singer SDK live standard suite: 26 passed
- Meltano quickstart: succeeded with 1,936 records and an updated incremental state
