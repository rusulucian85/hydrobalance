"""Number platform for HydroBalance."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    CONF_ZONE_ID,
    CONF_ZONE_NAME,
    CONF_ZONE_SPRINKLER_RATE,
    CONF_ZONE_DEFICIT_THRESHOLD,
    CONF_ZONE_MAX_PER_CYCLE,
    DEFAULT_SPRINKLER_RATE,
    DEFAULT_DEFICIT_THRESHOLD,
    DEFAULT_MAX_PER_CYCLE,
)
from .coordinator import HydroBalanceCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up HydroBalance number entities."""
    coordinator: HydroBalanceCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[NumberEntity] = []
    for zone in coordinator.zones:
        entities.append(HydroBalanceSprinklerRateNumber(coordinator, entry, zone))
        entities.append(HydroBalanceDeficitThresholdNumber(coordinator, entry, zone))
        entities.append(HydroBalanceMaxPerCycleNumber(coordinator, entry, zone))

    async_add_entities(entities)


class HydroBalanceBaseNumber(
    CoordinatorEntity[HydroBalanceCoordinator], NumberEntity
):
    """Base number entity for HydroBalance."""

    _attr_has_entity_name = True
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator, entry, zone, key):
        super().__init__(coordinator)
        self._zone_id = zone[CONF_ZONE_ID]
        self._zone_name = zone.get(CONF_ZONE_NAME, self._zone_id)
        self._attr_unique_id = f"{entry.entry_id}_zone_{self._zone_id}_{key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
        }


class HydroBalanceSprinklerRateNumber(HydroBalanceBaseNumber):
    """Sprinkler flow rate (mm per 30min)."""

    _attr_native_min_value = 0.5
    _attr_native_max_value = 10.0
    _attr_native_step = 0.1
    _attr_native_unit_of_measurement = "mm/30min"
    _attr_icon = "mdi:water-pump"

    def __init__(self, coordinator, entry, zone):
        super().__init__(coordinator, entry, zone, "sprinkler_rate")
        self._attr_name = f"{self._zone_name} Sprinkler Rate"
        self._value = zone.get(CONF_ZONE_SPRINKLER_RATE, DEFAULT_SPRINKLER_RATE)

    @property
    def native_value(self) -> float:
        return self._value

    async def async_set_native_value(self, value: float) -> None:
        self._value = value
        # Update zone config in coordinator
        zone = self.coordinator._get_zone_config(self._zone_id)
        if zone:
            zone[CONF_ZONE_SPRINKLER_RATE] = value
        self.async_write_ha_state()


class HydroBalanceDeficitThresholdNumber(HydroBalanceBaseNumber):
    """Watering trigger threshold (mm deficit)."""

    _attr_native_min_value = 5.0
    _attr_native_max_value = 30.0
    _attr_native_step = 1.0
    _attr_native_unit_of_measurement = "mm"
    _attr_icon = "mdi:water-alert"

    def __init__(self, coordinator, entry, zone):
        super().__init__(coordinator, entry, zone, "deficit_threshold")
        self._attr_name = f"{self._zone_name} Watering Threshold"
        self._value = zone.get(
            CONF_ZONE_DEFICIT_THRESHOLD,
            coordinator.strategy["deficit_threshold"],
        )

    @property
    def native_value(self) -> float:
        return self._value

    async def async_set_native_value(self, value: float) -> None:
        self._value = value
        zone = self.coordinator._get_zone_config(self._zone_id)
        if zone:
            zone[CONF_ZONE_DEFICIT_THRESHOLD] = value
        self.async_write_ha_state()


class HydroBalanceMaxPerCycleNumber(HydroBalanceBaseNumber):
    """Maximum water per cycle (mm)."""

    _attr_native_min_value = 1.0
    _attr_native_max_value = 15.0
    _attr_native_step = 0.5
    _attr_native_unit_of_measurement = "mm"
    _attr_icon = "mdi:water-plus"

    def __init__(self, coordinator, entry, zone):
        super().__init__(coordinator, entry, zone, "max_per_cycle")
        self._attr_name = f"{self._zone_name} Max Per Cycle"
        self._value = zone.get(
            CONF_ZONE_MAX_PER_CYCLE,
            coordinator.strategy.get("max_per_cycle", DEFAULT_MAX_PER_CYCLE),
        )

    @property
    def native_value(self) -> float:
        return self._value

    async def async_set_native_value(self, value: float) -> None:
        self._value = value
        zone = self.coordinator._get_zone_config(self._zone_id)
        if zone:
            zone[CONF_ZONE_MAX_PER_CYCLE] = value
        self.async_write_ha_state()
