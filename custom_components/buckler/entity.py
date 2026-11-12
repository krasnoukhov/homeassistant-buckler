"""Base entity for the Buckler integration."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import BASE_URL
from .const import DOMAIN
from .coordinator import BucklerCoordinator


class BucklerEntity(CoordinatorEntity[BucklerCoordinator]):
    """An entity of one relay."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: BucklerCoordinator, serial: str, key: str) -> None:
        super().__init__(coordinator)
        self._serial = serial
        self._attr_unique_id = f"{serial}_{key}"
        self._attr_translation_key = key
        relay = coordinator.data[serial].relay
        model = relay.get("typeRelay")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            name=relay.get("name") or serial,
            manufacturer="Buckler",
            model=model.replace("_", "-") if model else None,
            serial_number=serial,
            sw_version=relay.get("firmware"),
            configuration_url=f"{BASE_URL}/relay/{serial}/settings",
        )

    @property
    def available(self) -> bool:
        return super().available and self._serial in self.coordinator.data

    @property
    def relay(self) -> dict[str, Any]:
        return self.coordinator.data[self._serial].relay

    @property
    def settings(self) -> dict[str, Any]:
        return self.relay.get("settings") or {}
