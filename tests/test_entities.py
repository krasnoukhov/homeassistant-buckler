"""Tests for the Buckler entities."""

from datetime import timedelta

from pytest_homeassistant_custom_component.common import async_fire_time_changed

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.buckler.const import UPDATE_INTERVAL

from . import RELAY_ID, add_entry, log

EVENT = "event.iflh_log"


async def _setup(hass: HomeAssistant) -> None:
    entry = add_entry(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def _poll(hass: HomeAssistant) -> None:
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=UPDATE_INTERVAL + 1)
    )
    await hass.async_block_till_done()


async def test_settings_in_ha_units(hass: HomeAssistant, mock_api) -> None:
    """mA shows as A, W as kW, category 7 as curve D."""
    await _setup(hass)

    assert hass.states.get("number.iflh_turn_on_delay").state == "10.0"
    assert hass.states.get("number.iflh_voltage_minimum").state == "190.0"
    assert hass.states.get("number.iflh_voltage_maximum").state == "253.0"
    assert hass.states.get("number.iflh_current_maximum").state == "32.0"
    assert hass.states.get("number.iflh_power_maximum").state == "12.0"
    assert hass.states.get("number.iflh_frequency_minimum").state == "49.5"
    assert hass.states.get("select.iflh_current_trip_curve").state == "d"
    assert hass.states.get("switch.iflh_voltage_protection").state == "on"
    assert hass.states.get("switch.iflh_current_protection").state == "off"
    assert hass.states.get("switch.iflh_auto_turn_on").state == "on"
    assert hass.states.get("binary_sensor.iflh_cloud_connection").state == "on"


async def test_new_log_entries_fire_events(hass: HomeAssistant, mock_api) -> None:
    """Entries already there at startup don't fire; new ones fire oldest first."""
    await _setup(hass)
    assert hass.states.get(EVENT).state == "unknown"

    fired = []
    hass.bus.async_listen(
        "state_changed",
        lambda event: event.data["entity_id"] == EVENT
        and fired.append(event.data["new_state"].attributes),
    )
    mock_api.logs = [
        log("b", 122, "2026-11-12T14:13:55.000Z", "DOWN_VRMS", "📉 Зменшення напруги"),
        log("a", 122, "2026-11-12T14:10:38.000Z", "DOWN_VRMS", "📉 Зменшення напруги"),
        *mock_api.logs,
    ]
    await _poll(hass)

    assert [(x["event_type"], x["time"]) for x in fired] == [
        ("undervoltage", "2026-11-12T14:10:38.000Z"),
        ("undervoltage", "2026-11-12T14:13:55.000Z"),
    ]
    assert fired[-1]["code"] == 122
    assert fired[-1]["type"] == "DOWN_VRMS"

    # Nothing new, nothing fired
    await _poll(hass)
    assert len(fired) == 2


async def test_unknown_code_is_other(hass: HomeAssistant, mock_api) -> None:
    await _setup(hass)
    mock_api.logs = [log("x", 9999, "2026-11-12T15:00:00.000Z"), *mock_api.logs]
    await _poll(hass)
    assert hass.states.get(EVENT).attributes["event_type"] == "other"


async def test_number_saves_whole_section_in_cloud_units(
    hass: HomeAssistant, mock_api
) -> None:
    await _setup(hass)

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.iflh_current_maximum", "value": 25.5},
        blocking=True,
    )
    mock_api.save.assert_awaited_once_with(
        RELAY_ID, "current", {"max": 25500, "category": 7, "enable": False}
    )

    mock_api.save.reset_mock()
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.iflh_frequency_minimum", "value": 49},
        blocking=True,
    )
    mock_api.save.assert_awaited_once_with(
        RELAY_ID, "frequency", {"min": 49.0, "max": 50.5, "diff": 0.1, "enable": False}
    )


async def test_switch_and_select_save(hass: HomeAssistant, mock_api) -> None:
    await _setup(hass)

    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.iflh_current_protection"},
        blocking=True,
    )
    mock_api.save.assert_awaited_once_with(
        RELAY_ID, "current", {"max": 32000, "category": 7, "enable": True}
    )

    mock_api.save.reset_mock()
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.iflh_current_trip_curve", "option": "c"},
        blocking=True,
    )
    mock_api.save.assert_awaited_once_with(
        RELAY_ID, "current", {"max": 32000, "category": 5, "enable": False}
    )


async def test_save_reads_back_from_cloud(hass: HomeAssistant, mock_api) -> None:
    """After a save the entity shows what the cloud now has."""
    await _setup(hass)

    async def cloud_takes_it(relay_id, section, values):
        mock_api.relay["settings"][section] = values
        return True

    mock_api.save.side_effect = cloud_takes_it
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.iflh_voltage_minimum", "value": 180},
        blocking=True,
    )
    assert hass.states.get("number.iflh_voltage_minimum").state == "180.0"
