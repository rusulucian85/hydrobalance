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
    CONF_WEATHER_ENTITY,
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
        """Handle system setup step — select weather integration."""
        errors = {}

        if user_input is not None:
            weather_entity = user_input.get(CONF_WEATHER_ENTITY)
            self._data[CONF_SYSTEM_NAME] = user_input.get(CONF_SYSTEM_NAME, "My Garden")
            self._data[CONF_WEATHER_ENTITY] = weather_entity
            self._data[CONF_USE_FORECAST] = user_input.get(CONF_USE_FORECAST, True)

            # Auto-discover sensors from the same integration
            sensors = await self._discover_weather_sensors(weather_entity)
            if not sensors.get(CONF_SENSOR_TEMPERATURE):
                errors["base"] = "no_sensors"
            else:
                self._data.update(sensors)
                LOGGER.info("Auto-discovered sensors: %s", sensors)
                return await self.async_step_soil()

        schema = vol.Schema({
            vol.Required(CONF_SYSTEM_NAME, default="My Garden"): str,
            vol.Required(CONF_WEATHER_ENTITY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="weather")
            ),
            vol.Optional(CONF_USE_FORECAST, default=True): bool,
        })

        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )

    async def _discover_weather_sensors(self, weather_entity_id: str) -> dict[str, str | None]:
        """Auto-discover sensors from the same integration as the weather entity."""
        entity_registry = self.hass.helpers.entity_registry.async_get(self.hass)
        weather_entry = entity_registry.async_get(weather_entity_id)

        sensors: dict[str, str | None] = {
            CONF_SENSOR_TEMPERATURE: None,
            CONF_SENSOR_TEMPERATURE_MIN: None,
            CONF_SENSOR_TEMPERATURE_MAX: None,
            CONF_SENSOR_HUMIDITY: None,
            CONF_SENSOR_WIND_SPEED: None,
            CONF_SENSOR_UV_INDEX: None,
            CONF_SENSOR_RAIN: None,
            CONF_SENSOR_RAIN_FORECAST: None,
        }

        if not weather_entry or not weather_entry.config_entry_id:
            # Fallback: try to match by entity_id prefix
            prefix = weather_entity_id.replace("weather.", "sensor.").split("_")[0]
            return self._discover_by_prefix(prefix, sensors)

        # Find all sensor entities from the same config entry
        config_entry_id = weather_entry.config_entry_id
        all_entities = entity_registry.entities

        candidates = []
        for entity_id, entry in all_entities.items():
            if (
                entry.config_entry_id == config_entry_id
                and entry.domain == "sensor"
            ):
                state = self.hass.states.get(entity_id)
                candidates.append((entity_id, entry, state))

        return self._match_sensors(candidates, sensors)

    def _discover_by_prefix(
        self, prefix: str, sensors: dict[str, str | None]
    ) -> dict[str, str | None]:
        """Discover sensors by entity_id prefix matching."""
        all_states = self.hass.states.async_all("sensor")

        candidates = []
        for state in all_states:
            if prefix in state.entity_id:
                candidates.append((state.entity_id, None, state))

        return self._match_sensors(candidates, sensors)

    def _match_sensors(
        self,
        candidates: list,
        sensors: dict[str, str | None],
    ) -> dict[str, str | None]:
        """Match candidate entities to sensor roles by device_class and name patterns."""
        for entity_id, entry, state in candidates:
            if state is None:
                continue

            device_class = state.attributes.get("device_class", "")
            eid_lower = entity_id.lower()
            name_lower = (state.attributes.get("friendly_name") or "").lower()
            unit = state.attributes.get("unit_of_measurement", "")

            # Temperature (current)
            if device_class == "temperature" and not sensors[CONF_SENSOR_TEMPERATURE]:
                if "forecast" not in eid_lower and "min" not in eid_lower and "max" not in eid_lower:
                    sensors[CONF_SENSOR_TEMPERATURE] = entity_id

            # Temperature min forecast
            if device_class == "temperature" and not sensors[CONF_SENSOR_TEMPERATURE_MIN]:
                if "min" in eid_lower or "min" in name_lower:
                    sensors[CONF_SENSOR_TEMPERATURE_MIN] = entity_id

            # Temperature max forecast
            if device_class == "temperature" and not sensors[CONF_SENSOR_TEMPERATURE_MAX]:
                if "max" in eid_lower or "max" in name_lower:
                    sensors[CONF_SENSOR_TEMPERATURE_MAX] = entity_id

            # Humidity
            if device_class == "humidity" and not sensors[CONF_SENSOR_HUMIDITY]:
                sensors[CONF_SENSOR_HUMIDITY] = entity_id

            # Wind speed
            if not sensors[CONF_SENSOR_WIND_SPEED]:
                if "wind" in eid_lower and "speed" in eid_lower:
                    sensors[CONF_SENSOR_WIND_SPEED] = entity_id
                elif "wind" in eid_lower and ("km" in unit or "m/s" in unit):
                    sensors[CONF_SENSOR_WIND_SPEED] = entity_id

            # UV index
            if not sensors[CONF_SENSOR_UV_INDEX]:
                if "uv" in eid_lower:
                    sensors[CONF_SENSOR_UV_INDEX] = entity_id

            # Rain
            if not sensors[CONF_SENSOR_RAIN]:
                if ("rain" in eid_lower or device_class == "precipitation") and "forecast" not in eid_lower:
                    sensors[CONF_SENSOR_RAIN] = entity_id

            # Rain forecast
            if not sensors[CONF_SENSOR_RAIN_FORECAST]:
                if "rain" in eid_lower and "forecast" in eid_lower:
                    sensors[CONF_SENSOR_RAIN_FORECAST] = entity_id
                elif "precipitation" in eid_lower and ("forecast" in eid_lower or "24" in eid_lower):
                    sensors[CONF_SENSOR_RAIN_FORECAST] = entity_id

        return sensors

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
