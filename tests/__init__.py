"""Tests for the Buckler integration."""

import copy
from typing import Any

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from custom_components.buckler.const import DOMAIN

SERIAL = "4365_sxy15l"
RELAY_ID = "6a957b02f77f1e42d2194e5c"
USER = {
    "_id": "user-1",
    "username": "Dmytro",
    "email": "user@example.com",
    "relays": [
        {"index": 9999, "name": "IFLH", "serialNumber": SERIAL, "_id": RELAY_ID}
    ],
}

# /api/relay/<serial>'s relay, trimmed
_RELAY = {
    "_id": RELAY_ID,
    "serialNumber": SERIAL,
    "name": "IFLH",
    "typeRelay": "KMP_121_40",
    "firmware": "kmp_121_40_v3_260729d",
    "lastOnlineStatus": True,
    "settings": {
        "common": {"timeToOn": 10, "autoTurn": True},
        "voltage": {"min": 190, "max": 253, "diff": 5, "enable": True},
        "current": {"max": 32000, "category": 7, "enable": False},
        "frequency": {"min": 49.5, "max": 50.5, "diff": 0.1, "enable": False},
        "power": {"max": 12000, "enable": False},
        "temperature": {"max": 70, "enable": True},
        "difCurrent": {"max": None, "enable": None},
        "confirm": True,
    },
}


def relay() -> dict[str, Any]:
    """A fresh copy of the relay."""
    return copy.deepcopy(_RELAY)


def log(log_id: str, code: int, ts: str, log_type: str = "", message: str = "") -> dict:
    """A log entry as the cloud returns it."""
    return {
        "_id": log_id,
        "code": code,
        "type": log_type,
        "message": message,
        "timestamp": ts,
        "cp_time": 0,
        "info": "",
        "relay": RELAY_ID,
    }


def add_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Add a config entry for USER."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=USER["email"],
        unique_id=USER["_id"],
        data={CONF_EMAIL: USER["email"], CONF_PASSWORD: "secret"},
    )
    entry.add_to_hass(hass)
    return entry
