"""Binary sensor platform for HydroBalance."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_ZONE_ID, CONF_ZONE_NAME
from .coordinator import HydroBalanceCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up HydroBalance binary sensors."""
    coordinator: HydroBalanceCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        HydroBalanceZoneNeedsWaterSensor(coordinator, entry, zone)
        for zone in coordinator.zones
    ]
    async_add_entities(entities)


class HydroBalanceZoneNeedsWaterSensor(
    CoordinatorEntity[HydroBalanceCoordinator], BinarySensorEntity
):
    """Binary sensor indicating if a zone needs water."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:water-alert"

    def __init__(self, coordinator, entry, zone):
        super().__init__(coordinator)
        self._zone_id = zone[CONF_ZONE_ID]
        self._zone_name = zone.get(CONF_ZONE_NAME, self._zone_id)
        self._attr_unique_id = f"{entry.entry_id}_zone_{self._zone_id}_needs_water"
        self._attr_name = f"{self._zone_name} Needs Water"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
        }

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data
        if data and data.get("zones", {}).get(self._zone_id):
            return data["zones"][self._zone_id].get("status") == "needs_water"
        return None
