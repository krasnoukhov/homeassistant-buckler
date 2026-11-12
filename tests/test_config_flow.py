"""Tests for the Buckler config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.buckler.api import BucklerError, InvalidAuth
from custom_components.buckler.const import DOMAIN

from . import USER, add_entry

LOGIN = "custom_components.buckler.api.BucklerApi.login"
INPUT = {CONF_EMAIL: USER["email"], CONF_PASSWORD: "secret"}


async def _start(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"
    return result


async def test_user_creates_entry(hass: HomeAssistant, mock_api) -> None:
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], INPUT)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == USER["email"]
    assert result["data"] == INPUT
    assert result["result"].unique_id == USER["_id"]


async def test_user_errors(hass: HomeAssistant) -> None:
    result = await _start(hass)

    with patch(LOGIN, side_effect=InvalidAuth("Incorrect email or password")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], INPUT
        )
    assert result["errors"] == {"base": "invalid_auth"}

    with patch(LOGIN, side_effect=BucklerError("timeout")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], INPUT
        )
    assert result["errors"] == {"base": "cannot_connect"}


async def test_same_account_aborts(hass: HomeAssistant, mock_api) -> None:
    add_entry(hass)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], INPUT)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_updates_password(hass: HomeAssistant, mock_api) -> None:
    entry = add_entry(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    with patch(LOGIN, side_effect=InvalidAuth("Incorrect email or password")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "wrong"}
        )
    assert result["errors"] == {"base": "invalid_auth"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "new"


async def test_bad_password_at_setup_starts_reauth(hass: HomeAssistant) -> None:
    entry = add_entry(hass)
    with patch(LOGIN, side_effect=InvalidAuth("Incorrect email or password")):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is config_entries.ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert [f["context"]["source"] for f in flows] == ["reauth"]
