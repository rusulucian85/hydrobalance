"""Config flow for HydroBalance."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    LOGGER,
    SOIL_TYPES,
    STRATEGIES,
    SUN_EXPOSURE_MANUAL,
    SUN_ORIENTATION_FALLBACK,
    DEFAULT_SPRINKLER_RATE,
    DEFAULT_MAX_PER_CYCLE,
    CONF_SYSTEM_NAME,
    CONF_SENSOR_TEMPERATURE,
    CONF_SENSOR_TEMPERATURE_MIN,
    CONF_SENSOR_TEMPERATURE_MAX,
    CONF_SENSOR_HUMIDITY,
    CONF_SENSOR_WIND_SPEED,
    CONF_SENSOR_UV_INDEX,
    CONF_SENSOR_RAIN,
    CONF_SENSOR_RAIN_FORECAST,
    CONF_SOIL_TYPE,
    CONF_STRATEGY,
    CONF_USE_FORECAST,
    CONF_ZONES,
    CONF_ZONE_ID,
    CONF_ZONE_NAME,
    CONF_ZONE_SWITCH,
    CONF_ZONE_SPRINKLER_RATE,
    CONF_ZONE_MAX_PER_CYCLE,
    CONF_ZONE_DEFICIT_THRESHOLD,
    CONF_ZONE_SUN_EXPOSURE_MODE,
    CONF_ZONE_SUN_EXPOSURE,
    CONF_ZONE_ORIENTATION,
    CONF_ZONE_OBSTACLE_HEIGHT,
    CONF_ZONE_OBSTACLE_DISTANCE,
    CONF_ZONE_SOIL_OVERRIDE,
)


class HydroBalanceConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HydroBalance."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._data: dict[str, Any] = {}
        self._zones: list[dict[str, Any]] = []
        self._current_zone_index: int = 0

    # ─── Step 1: System Setup ─────────────────────────────────────────────────

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle system setup step."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_soil()

        schema = vol.Schema({
            vol.Required(CONF_SYSTEM_NAME, default="My Garden"): str,
            vol.Required(CONF_SENSOR_TEMPERATURE): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor", device_class="temperature"
                )
            ),
            vol.Optional(CONF_SENSOR_TEMPERATURE_MIN): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor", device_class="temperature"
                )
            ),
            vol.Optional(CONF_SENSOR_TEMPERATURE_MAX): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor", device_class="temperature"
                )
            ),
            vol.Required(CONF_SENSOR_HUMIDITY): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor", device_class="humidity"
                )
            ),
            vol.Required(CONF_SENSOR_WIND_SPEED): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Required(CONF_SENSOR_UV_INDEX): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Required(CONF_SENSOR_RAIN): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor", device_class="precipitation"
                )
            ),
            vol.Optional(CONF_SENSOR_RAIN_FORECAST): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional(CONF_USE_FORECAST, default=True): bool,
        })

        return self.async_show_form(step_id="user", data_schema=schema)

    # ─── Step 2: Soil & Strategy ──────────────────────────────────────────────

    async def async_step_soil(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle soil and strategy selection."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_zones_menu()

        schema = vol.Schema({
            vol.Required(CONF_SOIL_TYPE, default="clay"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=k, label=v["name"])
                        for k, v in SOIL_TYPES.items()
                    ],
                    mode=selector.SelectSelectorMode.LIST,
                )
            ),
            vol.Required(CONF_STRATEGY, default="balanced"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=k, label=v["name"])
                        for k, v in STRATEGIES.items()
                    ],
                    mode=selector.SelectSelectorMode.LIST,
                )
            ),
        })

        return self.async_show_form(step_id="soil", data_schema=schema)

    # ─── Step 3: Zone Menu ────────────────────────────────────────────────────

    async def async_step_zones_menu(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Zone management menu."""
        if user_input is not None:
            action = user_input.get("action")
            if action == "add":
                self._current_zone_index = len(self._zones)
                return await self.async_step_zone_config()
            if action == "done":
                if not self._zones:
                    return self.async_show_form(
                        step_id="zones_menu",
                        data_schema=self._zones_menu_schema(),
                        errors={"base": "no_zones"},
                    )
                return await self.async_step_summary()

        return self.async_show_form(
            step_id="zones_menu",
            data_schema=self._zones_menu_schema(),
            description_placeholders={
                "zone_count": str(len(self._zones)),
                "zone_list": ", ".join(z.get(CONF_ZONE_NAME, "?") for z in self._zones) or "None",
            },
        )

    def _zones_menu_schema(self) -> vol.Schema:
        return vol.Schema({
            vol.Required("action", default="add"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value="add", label="Add Zone"),
                        selector.SelectOptionDict(value="done", label="Done — Continue to Summary"),
                    ],
                    mode=selector.SelectSelectorMode.LIST,
                )
            ),
        })

    # ─── Step 4: Zone Configuration ───────────────────────────────────────────

    async def async_step_zone_config(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure a single zone."""
        if user_input is not None:
            zone_id = user_input.get(CONF_ZONE_NAME, "zone").lower().replace(" ", "_")
            # Ensure unique ID
            existing_ids = {z[CONF_ZONE_ID] for z in self._zones}
            base_id = zone_id
            counter = 1
            while zone_id in existing_ids:
                zone_id = f"{base_id}_{counter}"
                counter += 1

            zone = {
                CONF_ZONE_ID: zone_id,
                CONF_ZONE_NAME: user_input.get(CONF_ZONE_NAME, "Zone"),
                CONF_ZONE_SWITCH: user_input.get(CONF_ZONE_SWITCH),
                CONF_ZONE_SPRINKLER_RATE: user_input.get(
                    CONF_ZONE_SPRINKLER_RATE, DEFAULT_SPRINKLER_RATE
                ),
                CONF_ZONE_MAX_PER_CYCLE: user_input.get(
                    CONF_ZONE_MAX_PER_CYCLE, DEFAULT_MAX_PER_CYCLE
                ),
                CONF_ZONE_SUN_EXPOSURE_MODE: user_input.get(
                    CONF_ZONE_SUN_EXPOSURE_MODE, "manual"
                ),
                CONF_ZONE_SUN_EXPOSURE: user_input.get(CONF_ZONE_SUN_EXPOSURE),
                CONF_ZONE_ORIENTATION: user_input.get(CONF_ZONE_ORIENTATION),
                CONF_ZONE_OBSTACLE_HEIGHT: user_input.get(CONF_ZONE_OBSTACLE_HEIGHT),
                CONF_ZONE_OBSTACLE_DISTANCE: user_input.get(CONF_ZONE_OBSTACLE_DISTANCE),
                CONF_ZONE_SOIL_OVERRIDE: user_input.get(CONF_ZONE_SOIL_OVERRIDE),
            }

            if self._current_zone_index < len(self._zones):
                self._zones[self._current_zone_index] = zone
            else:
                self._zones.append(zone)

            return await self.async_step_zones_menu()

        schema = vol.Schema({
            vol.Required(CONF_ZONE_NAME): str,
            vol.Required(CONF_ZONE_SWITCH): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="switch")
            ),
            vol.Required(
                CONF_ZONE_SPRINKLER_RATE, default=DEFAULT_SPRINKLER_RATE
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0.5, max=10.0, step=0.1, unit_of_measurement="mm/30min"
                )
            ),
            vol.Required(
                CONF_ZONE_MAX_PER_CYCLE, default=DEFAULT_MAX_PER_CYCLE
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1.0, max=15.0, step=0.5, unit_of_measurement="mm"
                )
            ),
            vol.Required(
                CONF_ZONE_SUN_EXPOSURE_MODE, default="manual"
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value="manual", label="Manual"),
                        selector.SelectOptionDict(value="auto", label="Auto (orientation-based)"),
                    ]
                )
            ),
            vol.Optional(CONF_ZONE_SUN_EXPOSURE): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value="full_sun", label="Full Sun"),
                        selector.SelectOptionDict(value="partial_shade", label="Partial Shade"),
                        selector.SelectOptionDict(value="heavy_shade", label="Heavy Shade"),
                    ],
                    mode=selector.SelectSelectorMode.LIST,
                )
            ),
            vol.Optional(CONF_ZONE_ORIENTATION): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=d, label=d)
                        for d in ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
                    ]
                )
            ),
            vol.Optional(CONF_ZONE_OBSTACLE_HEIGHT): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=30, step=0.5, unit_of_measurement="m"
                )
            ),
            vol.Optional(CONF_ZONE_OBSTACLE_DISTANCE): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=50, step=0.5, unit_of_measurement="m"
                )
            ),
            vol.Optional(CONF_ZONE_SOIL_OVERRIDE): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value="", label="Use System Default"),
                    ] + [
                        selector.SelectOptionDict(value=k, label=v["name"])
                        for k, v in SOIL_TYPES.items()
                    ]
                )
            ),
        })

        return self.async_show_form(step_id="zone_config", data_schema=schema)

    # ─── Step 5: Summary ──────────────────────────────────────────────────────

    async def async_step_summary(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show summary and create entry."""
        if user_input is not None:
            self._data[CONF_ZONES] = self._zones
            return self.async_create_entry(
                title=self._data.get(CONF_SYSTEM_NAME, "HydroBalance"),
                data=self._data,
            )

        return self.async_show_form(
            step_id="summary",
            data_schema=vol.Schema({}),
            description_placeholders={
                "system_name": self._data.get(CONF_SYSTEM_NAME, ""),
                "soil_type": SOIL_TYPES.get(
                    self._data.get(CONF_SOIL_TYPE, "clay"), {}
                ).get("name", ""),
                "strategy": STRATEGIES.get(
                    self._data.get(CONF_STRATEGY, "balanced"), {}
                ).get("name", ""),
                "zone_count": str(len(self._zones)),
                "zone_names": ", ".join(
                    z.get(CONF_ZONE_NAME, "?") for z in self._zones
                ),
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Get the options flow handler."""
        return HydroBalanceOptionsFlow(config_entry)


class HydroBalanceOptionsFlow(config_entries.OptionsFlow):
    """Options flow for HydroBalance."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema({
            vol.Required(
                CONF_SOIL_TYPE,
                default=self._config_entry.data.get(CONF_SOIL_TYPE, "clay"),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=k, label=v["name"])
                        for k, v in SOIL_TYPES.items()
                    ],
                    mode=selector.SelectSelectorMode.LIST,
                )
            ),
            vol.Required(
                CONF_STRATEGY,
                default=self._config_entry.data.get(CONF_STRATEGY, "balanced"),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=k, label=v["name"])
                        for k, v in STRATEGIES.items()
                    ],
                    mode=selector.SelectSelectorMode.LIST,
                )
            ),
        })

        return self.async_show_form(step_id="init", data_schema=schema)
