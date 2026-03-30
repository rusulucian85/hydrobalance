"""Config flow for HydroBalance — minimal setup, detailed config via panel."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers import entity_registry as er, selector

from .const import (
    DOMAIN,
    CONF_SYSTEM_NAME,
    CONF_WEATHER_ENTITY,
    CONF_USE_FORECAST,
)


class HydroBalanceConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HydroBalance."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle initial setup — just name and weather source."""
        if user_input is not None:
            # Prevent duplicate entries
            await self.async_set_unique_id(user_input[CONF_SYSTEM_NAME])
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=user_input[CONF_SYSTEM_NAME],
                data=user_input,
            )

        schema = vol.Schema({
            vol.Required(CONF_SYSTEM_NAME, default="My Garden"): str,
            vol.Required(CONF_WEATHER_ENTITY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="weather")
            ),
            vol.Optional(CONF_USE_FORECAST, default=True): bool,
        })

        return self.async_show_form(step_id="user", data_schema=schema)
