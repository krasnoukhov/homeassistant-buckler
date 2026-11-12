"""Polls the Buckler cloud for each relay's settings and event log."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import BucklerApi, BucklerError, InvalidAuth
from .const import DOMAIN, LOG_PAGE, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

type BucklerConfigEntry = ConfigEntry[BucklerCoordinator]


@dataclass
class RelayData:
    """One relay as the cloud has it."""

    relay: dict[str, Any]
    # Newest first
    logs: list[dict[str, Any]]
    # Entries that appeared since the previous poll, oldest first
    new_logs: list[dict[str, Any]] = field(default_factory=list)


class BucklerCoordinator(DataUpdateCoordinator[dict[str, RelayData]]):
    """Reads every relay on the account."""

    config_entry: BucklerConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: BucklerConfigEntry, api: BucklerApi
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )
        self.api = api
        # serial -> log ids from the previous poll; absent until the first poll
        self._seen: dict[str, set[str]] = {}

    async def _async_update_data(self) -> dict[str, RelayData]:
        data: dict[str, RelayData] = {}
        try:
            for item in self.api.relays:
                serial = item["serialNumber"]
                relay = await self.api.relay(serial)
                logs = await self.api.logs(serial, LOG_PAGE)
                data[serial] = RelayData(relay, logs, self._new_logs(serial, logs))
        except InvalidAuth as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except BucklerError as err:
            raise UpdateFailed(str(err)) from err
        # Only after every relay is read, so a failed poll reports its entries next time
        for serial, relay_data in data.items():
            self._seen[serial] = {entry.get("_id") for entry in relay_data.logs}
        return data

    def _new_logs(
        self, serial: str, logs: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        seen = self._seen.get(serial)
        # The first poll only remembers what's there, so a restart doesn't replay it
        if seen is None:
            return []
        return [entry for entry in reversed(logs) if entry.get("_id") not in seen]

    async def async_save(
        self, serial: str, section: str, changes: dict[str, Any]
    ) -> None:
        """Change fields of one settings section, in the cloud's units."""
        relay = self.data[serial].relay
        values = {**relay["settings"][section], **changes}
        try:
            confirmed = await self.api.save_settings(relay["_id"], section, values)
        except BucklerError as err:
            raise HomeAssistantError(f"Buckler didn't take the change: {err}") from err
        if not confirmed:
            _LOGGER.warning(
                "%s: the cloud took the %s change, but the relay hasn't confirmed it",
                serial,
                section,
            )
        await self.async_refresh()
