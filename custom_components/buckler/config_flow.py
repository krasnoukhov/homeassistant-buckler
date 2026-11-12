"""Config flow for the Buckler integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import BucklerApi, BucklerError, InvalidAuth
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

_PASSWORD = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="username")
        ),
        vol.Required(CONF_PASSWORD): _PASSWORD,
    }
)
REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): _PASSWORD})


class BucklerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Log in to the Buckler cloud."""

    VERSION = 1

    async def _login(
        self, email: str, password: str, errors: dict[str, str]
    ) -> dict[str, Any] | None:
        api = BucklerApi(async_get_clientsession(self.hass), email, password)
        try:
            return await api.login()
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except BucklerError:
            _LOGGER.exception("Can't reach the Buckler cloud")
            errors["base"] = "cannot_connect"
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            user = await self._login(
                user_input[CONF_EMAIL], user_input[CONF_PASSWORD], errors
            )
            if user is not None:
                await self.async_set_unique_id(
                    user.get("_id") or user_input[CONF_EMAIL]
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user.get("email") or user_input[CONF_EMAIL], data=user_input
                )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                USER_SCHEMA, {CONF_EMAIL: (user_input or {}).get(CONF_EMAIL)}
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            user = await self._login(
                entry.data[CONF_EMAIL], user_input[CONF_PASSWORD], errors
            )
            if user is not None:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            description_placeholders={"email": entry.data[CONF_EMAIL]},
            errors=errors,
        )
