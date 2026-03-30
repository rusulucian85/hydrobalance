"""Switch platform for HydroBalance."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_ZONE_ID, CONF_ZONE_NAME, CONF_ZONE_SWITCH
from .coordinator import HydroBalanceCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up HydroBalance zone switches."""
    coordinator: HydroBalanceCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        HydroBalanceZoneSwitch(coordinator, entry, zone)
        for zone in coordinator.zones
        if zone.get(CONF_ZONE_SWITCH)
    ]
    async_add_entities(entities)


class HydroBalanceZoneSwitch(
    CoordinatorEntity[HydroBalanceCoordinator], SwitchEntity
):
    """Zone proxy switch that wraps the real sprinkler switch."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:sprinkler"

    def __init__(self, coordinator, entry, zone):
        super().__init__(coordinator)
        self._zone_id = zone[CONF_ZONE_ID]
        self._zone_name = zone.get(CONF_ZONE_NAME, self._zone_id)
        self._switch_entity = zone[CONF_ZONE_SWITCH]
        self._attr_unique_id = f"{entry.entry_id}_zone_{self._zone_id}_switch"
        self._attr_name = f"{self._zone_name} Sprinkler"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
        }

    @property
    def is_on(self) -> bool | None:
        """Mirror the state of the underlying switch."""
        state = self.hass.states.get(self._switch_entity)
        if state is None:
            return None
        return state.state == "on"

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on the sprinkler."""
        await self.hass.services.async_call(
            "switch", "turn_on", {"entity_id": self._switch_entity}
        )

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the sprinkler."""
        await self.hass.services.async_call(
            "switch", "turn_off", {"entity_id": self._switch_entity}
        )
