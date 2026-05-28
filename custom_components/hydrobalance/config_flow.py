"""Config flow for HydroBalance — minimal setup, detailed config via panel."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult

from .const import (
    DOMAIN,
    CONF_SYSTEM_NAME,
)


class HydroBalanceConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HydroBalance."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle initial setup — just the system name. Weather source,
        sensors and zones are all configured later from the panel UI."""
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
        })

        return self.async_show_form(step_id="user", data_schema=schema)
