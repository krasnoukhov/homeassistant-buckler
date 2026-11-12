"""Protection on/off switches."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import BucklerConfigEntry, BucklerCoordinator
from .entity import BucklerEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class BucklerSwitchDescription(SwitchEntityDescription):
    """A boolean field of a settings section."""

    section: str
    field: str = "enable"
    entity_category: EntityCategory | None = EntityCategory.CONFIG


SWITCHES = (
    # Turn back on by itself once the fault clears
    BucklerSwitchDescription(key="auto_turn_on", section="common", field="autoTurn"),
    BucklerSwitchDescription(key="voltage_protection", section="voltage"),
    BucklerSwitchDescription(key="current_protection", section="current"),
    BucklerSwitchDescription(key="power_protection", section="power"),
    BucklerSwitchDescription(key="frequency_protection", section="frequency"),
    BucklerSwitchDescription(key="temperature_protection", section="temperature"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BucklerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        BucklerSwitch(coordinator, serial, description)
        for serial, data in coordinator.data.items()
        for description in SWITCHES
        if (data.relay.get("settings") or {})
        .get(description.section, {})
        .get(description.field)
        is not None
    )


class BucklerSwitch(BucklerEntity, SwitchEntity):
    """Turns one protection on or off."""

    entity_description: BucklerSwitchDescription

    def __init__(
        self,
        coordinator: BucklerCoordinator,
        serial: str,
        description: BucklerSwitchDescription,
    ) -> None:
        super().__init__(coordinator, serial, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        d = self.entity_description
        value = self.settings.get(d.section, {}).get(d.field)
        return None if value is None else bool(value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._save(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._save(False)

    async def _save(self, value: bool) -> None:
        d = self.entity_description
        await self.coordinator.async_save(self._serial, d.section, {d.field: value})
