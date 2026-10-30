import os

import pytest


def pytest_collection_modifyitems(config, items):
    if os.environ.get("RUN_LIVE_TESTS") == "1":
        return
    skip_live = pytest.mark.skip(reason="set RUN_LIVE_TESTS=1 to run live tests")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)
