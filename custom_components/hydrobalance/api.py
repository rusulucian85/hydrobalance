"""WebSocket API for HydroBalance panel."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, LOGGER


def async_register_api(hass: HomeAssistant) -> None:
    """Register WebSocket API commands for HydroBalance panel."""
    websocket_api.async_register_command(hass, ws_get_config)
    websocket_api.async_register_command(hass, ws_save_config)
    websocket_api.async_register_command(hass, ws_get_status)
    websocket_api.async_register_command(hass, ws_discover_sensors)
    websocket_api.async_register_command(hass, ws_force_water)
    websocket_api.async_register_command(hass, ws_skip_day)
    websocket_api.async_register_command(hass, ws_reset_deficit)


@websocket_api.websocket_command({
    vol.Required("type"): "hydrobalance/config",
})
@callback
def ws_get_config(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Return the full HydroBalance configuration."""
    data = {}
    for entry_id, coordinator in hass.data.get(DOMAIN, {}).items():
        store_data = {
            "entry_id": entry_id,
            "config": dict(coordinator.config_entry.data),
            "zones": coordinator._store_data.get("zones", []),
            "soil_type": coordinator._store_data.get("soil_type", "clay"),
            "strategy": coordinator._store_data.get("strategy", "balanced"),
            "sensors": coordinator._store_data.get("sensors", {}),
            "moisture_skip_threshold": coordinator.moisture_skip_threshold,
            "weather_entity": coordinator.weather_entity,
            "use_forecast": coordinator.use_forecast,
        }
        data[entry_id] = store_data
    connection.send_result(msg["id"], data)


@websocket_api.websocket_command({
    vol.Required("type"): "hydrobalance/config/save",
    vol.Required("entry_id"): str,
    vol.Optional("zones"): list,
    vol.Optional("soil_type"): str,
    vol.Optional("strategy"): str,
    vol.Optional("sensors"): dict,
    vol.Optional("moisture_skip_threshold"): vol.Coerce(float),
    vol.Optional("weather_entity"): vol.Any(str, None),
    vol.Optional("use_forecast"): bool,
})
@websocket_api.async_response
async def ws_save_config(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Save HydroBalance configuration from panel."""
    entry_id = msg["entry_id"]
    coordinator = hass.data.get(DOMAIN, {}).get(entry_id)
    if not coordinator:
        connection.send_error(msg["id"], "not_found", "Entry not found")
        return

    # Update stored configuration
    if "zones" in msg:
        coordinator._store_data["zones"] = msg["zones"]
    if "soil_type" in msg:
        coordinator._store_data["soil_type"] = msg["soil_type"]
    if "strategy" in msg:
        coordinator._store_data["strategy"] = msg["strategy"]
    if "sensors" in msg:
        coordinator._store_data["sensors"] = msg["sensors"]
    if "moisture_skip_threshold" in msg:
        coordinator._store_data["moisture_skip_threshold"] = msg["moisture_skip_threshold"]
    if "weather_entity" in msg:
        coordinator._store_data["weather_entity"] = msg["weather_entity"]
    if "use_forecast" in msg:
        coordinator._store_data["use_forecast"] = msg["use_forecast"]

    await coordinator.async_save_panel_config()
    await coordinator.async_request_refresh()

    LOGGER.info("Configuration saved from panel for entry %s", entry_id)
    connection.send_result(msg["id"], {"success": True})


@websocket_api.websocket_command({
    vol.Required("type"): "hydrobalance/status",
})
@callback
def ws_get_status(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Return current HydroBalance status (deficits, ET, etc.)."""
    result = {}
    for entry_id, coordinator in hass.data.get(DOMAIN, {}).items():
        result[entry_id] = coordinator.data if coordinator.data else {}
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command({
    vol.Required("type"): "hydrobalance/discover_sensors",
    vol.Required("weather_entity"): str,
})
@callback
def ws_discover_sensors(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Auto-discover sensors from a weather integration."""
    weather_entity_id = msg["weather_entity"]
    entity_registry = er.async_get(hass)
    weather_entry = entity_registry.async_get(weather_entity_id)

    sensors = {
        "sensor_temperature": None,
        "sensor_temperature_min": None,
        "sensor_temperature_max": None,
        "sensor_humidity": None,
        "sensor_wind_speed": None,
        "sensor_uv_index": None,
        "sensor_rain": None,
        "sensor_rain_forecast": None,
    }

    if not weather_entry or not weather_entry.config_entry_id:
        connection.send_result(msg["id"], sensors)
        return

    config_entry_id = weather_entry.config_entry_id

    for entry in entity_registry.entities.values():
        if entry.config_entry_id != config_entry_id or entry.domain != "sensor":
            continue

        state = hass.states.get(entry.entity_id)
        if not state:
            continue

        eid = entry.entity_id.lower()
        device_class = state.attributes.get("device_class", "")
        unit = state.attributes.get("unit_of_measurement", "")

        if device_class == "temperature" and not sensors["sensor_temperature"]:
            excluded = ("forecast", "min", "max", "dew", "feels", "apparent")
            if not any(token in eid for token in excluded):
                sensors["sensor_temperature"] = entry.entity_id

        if device_class == "temperature" and not sensors["sensor_temperature_min"]:
            if "min" in eid:
                sensors["sensor_temperature_min"] = entry.entity_id

        if device_class == "temperature" and not sensors["sensor_temperature_max"]:
            if "max" in eid:
                sensors["sensor_temperature_max"] = entry.entity_id

        if device_class == "humidity" and not sensors["sensor_humidity"]:
            sensors["sensor_humidity"] = entry.entity_id

        if not sensors["sensor_wind_speed"] and "wind" in eid and ("speed" in eid or "km" in unit or "m/s" in unit):
            sensors["sensor_wind_speed"] = entry.entity_id

        if not sensors["sensor_uv_index"] and "uv" in eid:
            sensors["sensor_uv_index"] = entry.entity_id

        if not sensors["sensor_rain"] and ("rain" in eid or device_class == "precipitation") and "forecast" not in eid:
            sensors["sensor_rain"] = entry.entity_id

        if not sensors["sensor_rain_forecast"] and ("precipitation" in eid or "rain" in eid) and ("forecast" in eid or "24" in eid):
            sensors["sensor_rain_forecast"] = entry.entity_id

    connection.send_result(msg["id"], sensors)


@websocket_api.websocket_command({
    vol.Required("type"): "hydrobalance/force_water",
    vol.Optional("zone_id"): str,
    vol.Optional("mm"): float,
})
@websocket_api.async_response
async def ws_force_water(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Force watering."""
    for coordinator in hass.data.get(DOMAIN, {}).values():
        await coordinator.async_force_water(msg.get("zone_id"), msg.get("mm"))
        break
    connection.send_result(msg["id"], {"success": True})


@websocket_api.websocket_command({
    vol.Required("type"): "hydrobalance/skip_day",
})
@websocket_api.async_response
async def ws_skip_day(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Skip next watering."""
    for coordinator in hass.data.get(DOMAIN, {}).values():
        await coordinator.async_skip_day()
        break
    connection.send_result(msg["id"], {"success": True})


@websocket_api.websocket_command({
    vol.Required("type"): "hydrobalance/reset_deficit",
    vol.Optional("zone_id"): str,
})
@websocket_api.async_response
async def ws_reset_deficit(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Reset deficit."""
    for coordinator in hass.data.get(DOMAIN, {}).values():
        await coordinator.async_reset_deficit(msg.get("zone_id"))
        break
    connection.send_result(msg["id"], {"success": True})
