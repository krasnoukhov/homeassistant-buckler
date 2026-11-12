"""Whether the relay is connected to the cloud."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import BucklerConfigEntry, BucklerCoordinator
from .entity import BucklerEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BucklerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        BucklerCloudConnection(coordinator, serial) for serial in coordinator.data
    )


class BucklerCloudConnection(BucklerEntity, BinarySensorEntity):
    """The relay's link to the cloud, as the cloud last saw it."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: BucklerCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial, "cloud_connection")

    @property
    def is_on(self) -> bool | None:
        value = self.relay.get("lastOnlineStatus")
        return None if value is None else bool(value)
