import pytest
from singer_sdk.testing import get_tap_test_class

from tap_usgs_earthquakes import TapUsgsEarthquakes


@pytest.mark.live
class TestTapStandard(
    get_tap_test_class(
        TapUsgsEarthquakes,
        config={"start_date": "2026-10-01T00:00:00Z", "min_magnitude": 4.0},
    )
):
    """Singer SDK's standard tap checks, run only against the live API."""
