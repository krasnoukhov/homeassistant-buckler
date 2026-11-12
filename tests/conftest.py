"""Fixtures for Buckler tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, PropertyMock, patch

import pytest

from . import USER, log, relay

API = "custom_components.buckler.api.BucklerApi"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Load the integration from custom_components."""
    yield


@pytest.fixture
def mock_api():
    """Stub the cloud: one relay with one old log entry."""
    cloud = SimpleNamespace(
        relay=relay(),
        logs=[log("old", 129, "2026-11-11T19:44:24.000Z", "CONDITION_SET")],
    )
    with (
        patch(f"{API}.login", return_value=USER) as cloud.login,
        patch(f"{API}.relays", new_callable=PropertyMock, return_value=USER["relays"]),
        patch(f"{API}.relay", side_effect=lambda serial: cloud.relay),
        patch(f"{API}.logs", side_effect=lambda serial, limit: cloud.logs),
        patch(
            f"{API}.save_settings", new_callable=AsyncMock, return_value=True
        ) as cloud.save,
    ):
        yield cloud
