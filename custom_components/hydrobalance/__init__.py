"""HydroBalance - Smart irrigation based on real water deficit."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components import frontend
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .api import async_register_api
from .const import DOMAIN, LOGGER, PLATFORMS
from .coordinator import HydroBalanceCoordinator

type HydroBalanceConfigEntry = ConfigEntry

PANEL_URL = "/hydrobalance-panel"
PANEL_TITLE = "HydroBalance"
PANEL_ICON = "mdi:water-pump"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the HydroBalance component."""
    # Register WebSocket API commands
    async_register_api(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HydroBalance from a config entry."""
    coordinator = HydroBalanceCoordinator(hass, entry)

    # Load persisted state and set up time listeners
    await coordinator.async_setup()

    # Initial data fetch
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Forward platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services
    _register_services(hass, coordinator)

    # Register panel (only once)
    if len(hass.data[DOMAIN]) == 1:
        hass.http.register_static_path(
            PANEL_URL,
            hass.config.path(f"custom_components/{DOMAIN}/panel"),
            cache_headers=False,
        )
        frontend.async_register_built_in_panel(
            hass,
            component_name="iframe",
            sidebar_title=PANEL_TITLE,
            sidebar_icon=PANEL_ICON,
            frontend_url_path=DOMAIN,
            config={"url": f"{PANEL_URL}/index.html"},
            require_admin=False,
        )

    LOGGER.info("HydroBalance setup complete for: %s", entry.title)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator: HydroBalanceCoordinator = hass.data[DOMAIN].get(entry.entry_id)

    if coordinator:
        await coordinator.async_shutdown()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    # Remove services and panel if no more entries
    if not hass.data[DOMAIN]:
        for service in ("force_water", "skip_day", "reset_deficit"):
            hass.services.async_remove(DOMAIN, service)
        frontend.async_remove_panel(hass, DOMAIN)

    return unload_ok


def _register_services(hass: HomeAssistant, coordinator: HydroBalanceCoordinator) -> None:
    """Register HydroBalance services."""

    if hass.services.has_service(DOMAIN, "force_water"):
        return  # Already registered

    async def handle_force_water(call: ServiceCall) -> None:
        zone_id = call.data.get("zone_id")
        mm = call.data.get("mm_to_apply")
        await coordinator.async_force_water(zone_id, mm)

    async def handle_skip_day(call: ServiceCall) -> None:
        await coordinator.async_skip_day()

    async def handle_reset_deficit(call: ServiceCall) -> None:
        zone_id = call.data.get("zone_id")
        await coordinator.async_reset_deficit(zone_id)

    hass.services.async_register(
        DOMAIN,
        "force_water",
        handle_force_water,
        schema=vol.Schema({
            vol.Optional("zone_id"): cv.string,
            vol.Optional("mm_to_apply"): vol.Coerce(float),
        }),
    )

    hass.services.async_register(
        DOMAIN,
        "skip_day",
        handle_skip_day,
    )

    hass.services.async_register(
        DOMAIN,
        "reset_deficit",
        handle_reset_deficit,
        schema=vol.Schema({
            vol.Optional("zone_id"): cv.string,
        }),
    )
