# AGENTS.md

## Project
`tap-usgs-earthquakes`: a Singer tap built on the Meltano Singer SDK (`singer-sdk` on PyPI,
imported as `singer_sdk`). It extracts earthquake events from the USGS FDSN Event web service.

## Stack and conventions
- Python 3.10+; dependency management with `uv` (`pyproject.toml`, `uv.lock` committed).
- Use Singer SDK primitives and keep unit tests offline.
- Lint/format: `ruff check .` and `ruff format .`. Types: `mypy tap_usgs_earthquakes`.
- Tests: `pytest`; live tests require `RUN_LIVE_TESTS=1`.

## Hard rules
- The tap must run with an EMPTY config `{}`. Every setting is optional with a sensible default.
- Never request more than 20,000 rows in one API call.
- Send a descriptive User-Agent, back off on 429/5xx, and never run more than one request at a time.
- Do not invent API behaviour; use `docs/API_NOTES.md` and fixtures.
- Before saying a task is done, run `ruff check . && ruff format --check . && mypy tap_usgs_earthquakes && pytest`.
