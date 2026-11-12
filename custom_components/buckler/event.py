"""The relay's event log as an event entity."""

from __future__ import annotations

from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import EVENT_TYPE_OTHER, EVENT_TYPES, EVENT_TYPES_BY_CODE
from .coordinator import BucklerConfigEntry, BucklerCoordinator
from .entity import BucklerEntity

PARALLEL_UPDATES = 0


def event_type(entry: dict[str, Any]) -> str:
    """The event type for a log entry."""
    try:
        return EVENT_TYPES_BY_CODE.get(int(entry.get("code")), EVENT_TYPE_OTHER)
    except (TypeError, ValueError):
        return EVENT_TYPE_OTHER


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BucklerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        BucklerLogEvent(coordinator, serial) for serial in coordinator.data
    )


class BucklerLogEvent(BucklerEntity, EventEntity):
    """Fires once for each new entry in the relay's log."""

    _attr_event_types = EVENT_TYPES

    def __init__(self, coordinator: BucklerCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial, "log")

    @callback
    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data.get(self._serial)
        for entry in data.new_logs if data else []:
            self._trigger_event(
                event_type(entry),
                {
                    "code": entry.get("code"),
                    "type": entry.get("type"),
                    "message": entry.get("message"),
                    "time": entry.get("timestamp"),
                },
            )
            # One state per entry, so each reaches the logbook and automations
            self.async_write_ha_state()
        super()._handle_coordinator_update()
