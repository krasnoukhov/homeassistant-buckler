"""The Buckler integration."""

from __future__ import annotations

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import BucklerApi, BucklerError, InvalidAuth
from .coordinator import BucklerConfigEntry, BucklerCoordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.EVENT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: BucklerConfigEntry) -> bool:
    """Set up Buckler from a config entry."""
    api = BucklerApi(
        async_get_clientsession(hass), entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD]
    )
    try:
        await api.login()
    except InvalidAuth as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except BucklerError as err:
        raise ConfigEntryNotReady(str(err)) from err

    coordinator = BucklerCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BucklerConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
