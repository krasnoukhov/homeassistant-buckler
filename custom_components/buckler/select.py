"""Current trip curve."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CURVES
from .coordinator import BucklerConfigEntry, BucklerCoordinator
from .entity import BucklerEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BucklerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        BucklerCurveSelect(coordinator, serial)
        for serial, data in coordinator.data.items()
        if (data.relay.get("settings") or {}).get("current", {}).get("category")
        is not None
    )


class BucklerCurveSelect(BucklerEntity, SelectEntity):
    """The current protection's trip curve, B/C/D as on breakers."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = list(CURVES.values())

    def __init__(self, coordinator: BucklerCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial, "current_curve")

    @property
    def current_option(self) -> str | None:
        try:
            return CURVES.get(int(self.settings["current"]["category"]))
        except (KeyError, TypeError, ValueError):
            return None

    async def async_select_option(self, option: str) -> None:
        category = next(k for k, v in CURVES.items() if v == option)
        await self.coordinator.async_save(
            self._serial, "current", {"category": category}
        )
