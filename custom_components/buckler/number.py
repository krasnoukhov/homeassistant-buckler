"""Protection limits as number entities."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import BucklerConfigEntry, BucklerCoordinator
from .entity import BucklerEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class BucklerNumberDescription(NumberEntityDescription):
    """A field of a settings section."""

    section: str
    field: str
    # Cloud value / scale = value here (the cloud keeps mA and W)
    scale: int = 1
    mode: NumberMode = NumberMode.BOX
    entity_category: EntityCategory | None = EntityCategory.CONFIG


_VOLT = {
    "native_unit_of_measurement": UnitOfElectricPotential.VOLT,
    "device_class": NumberDeviceClass.VOLTAGE,
    "native_step": 1,
}
_HERTZ = {
    "native_unit_of_measurement": UnitOfFrequency.HERTZ,
    "device_class": NumberDeviceClass.FREQUENCY,
    "native_step": 0.1,
}

# Ranges as the web app allows them
NUMBERS = (
    BucklerNumberDescription(
        key="turn_on_delay",
        section="common",
        field="timeToOn",
        native_min_value=10,
        native_max_value=1800,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=NumberDeviceClass.DURATION,
    ),
    BucklerNumberDescription(
        key="voltage_max",
        section="voltage",
        field="max",
        native_min_value=220,
        native_max_value=280,
        **_VOLT,
    ),
    BucklerNumberDescription(
        key="voltage_min",
        section="voltage",
        field="min",
        native_min_value=120,
        native_max_value=210,
        **_VOLT,
    ),
    BucklerNumberDescription(
        key="voltage_hysteresis",
        section="voltage",
        field="diff",
        native_min_value=1,
        native_max_value=9,
        **_VOLT,
    ),
    BucklerNumberDescription(
        key="current_max",
        section="current",
        field="max",
        scale=1000,
        native_min_value=0.1,
        native_max_value=60,
        native_step=0.1,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=NumberDeviceClass.CURRENT,
    ),
    BucklerNumberDescription(
        key="power_max",
        section="power",
        field="max",
        scale=1000,
        native_min_value=0.02,
        native_max_value=13.8,
        native_step=0.01,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=NumberDeviceClass.POWER,
    ),
    BucklerNumberDescription(
        key="frequency_min",
        section="frequency",
        field="min",
        native_min_value=45,
        native_max_value=49.9,
        **_HERTZ,
    ),
    BucklerNumberDescription(
        key="frequency_max",
        section="frequency",
        field="max",
        native_min_value=50.1,
        native_max_value=65,
        **_HERTZ,
    ),
    BucklerNumberDescription(
        key="temperature_max",
        section="temperature",
        field="max",
        native_min_value=40,
        native_max_value=75,
        native_step=1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BucklerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        BucklerNumber(coordinator, serial, description)
        for serial, data in coordinator.data.items()
        for description in NUMBERS
        if (data.relay.get("settings") or {})
        .get(description.section, {})
        .get(description.field)
        is not None
    )


class BucklerNumber(BucklerEntity, NumberEntity):
    """A protection limit."""

    entity_description: BucklerNumberDescription

    def __init__(
        self,
        coordinator: BucklerCoordinator,
        serial: str,
        description: BucklerNumberDescription,
    ) -> None:
        super().__init__(coordinator, serial, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        d = self.entity_description
        value = self.settings.get(d.section, {}).get(d.field)
        if value is None:
            return None
        return round(float(value) / d.scale, 3)

    async def async_set_native_value(self, value: float) -> None:
        d = self.entity_description
        if d.scale != 1 or d.native_step >= 1:
            cloud: float = int(round(value * d.scale))
        else:
            cloud = round(value, 1)
        await self.coordinator.async_save(self._serial, d.section, {d.field: cloud})
