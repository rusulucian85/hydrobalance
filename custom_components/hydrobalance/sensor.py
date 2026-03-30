"""Sensor platform for HydroBalance."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
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
    """Set up HydroBalance sensors."""
    coordinator: HydroBalanceCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = [
        HydroBalanceDailyETSensor(coordinator, entry),
        HydroBalanceEffectiveRainSensor(coordinator, entry),
        HydroBalanceRawRainSensor(coordinator, entry),
    ]

    # Per-zone sensors
    for zone in coordinator.zones:
        entities.append(HydroBalanceZoneDeficitSensor(coordinator, entry, zone))
        entities.append(HydroBalanceZoneStatusSensor(coordinator, entry, zone))
        entities.append(HydroBalanceZoneSunCoefficientSensor(coordinator, entry, zone))

    async_add_entities(entities)


class HydroBalanceBaseSensor(CoordinatorEntity[HydroBalanceCoordinator], SensorEntity):
    """Base sensor for HydroBalance."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: HydroBalanceCoordinator, entry: ConfigEntry, key: str
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title or "HydroBalance",
            "manufacturer": "HydroBalance",
            "model": "Smart Irrigation",
            "sw_version": "0.1.0",
        }


class HydroBalanceDailyETSensor(HydroBalanceBaseSensor):
    """Daily ET sensor."""

    _attr_name = "Daily ET"
    _attr_native_unit_of_measurement = "mm"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:sun-thermometer"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "daily_et")

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data
        if data and data.get("daily"):
            return data["daily"].get("et")
        return None


class HydroBalanceEffectiveRainSensor(HydroBalanceBaseSensor):
    """Effective precipitation sensor."""

    _attr_name = "Effective Rain"
    _attr_native_unit_of_measurement = "mm"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:water-check"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "effective_rain")

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data
        if data and data.get("daily"):
            return data["daily"].get("effective_rain")
        return None


class HydroBalanceRawRainSensor(HydroBalanceBaseSensor):
    """Raw accumulated rain sensor."""

    _attr_name = "Rain Today"
    _attr_native_unit_of_measurement = "mm"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:weather-rainy"
    _attr_device_class = SensorDeviceClass.PRECIPITATION

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "rain_today")

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data
        if data and data.get("daily"):
            return data["daily"].get("rain_accumulated")
        return None


class HydroBalanceZoneDeficitSensor(HydroBalanceBaseSensor):
    """Per-zone water deficit sensor."""

    _attr_native_unit_of_measurement = "mm"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:water-minus"

    def __init__(self, coordinator, entry, zone):
        self._zone_id = zone[CONF_ZONE_ID]
        self._zone_name = zone.get(CONF_ZONE_NAME, self._zone_id)
        super().__init__(coordinator, entry, f"zone_{self._zone_id}_deficit")
        self._attr_name = f"{self._zone_name} Water Deficit"

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data
        if data and data.get("zones", {}).get(self._zone_id):
            return data["zones"][self._zone_id].get("water_deficit")
        return None

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data
        if data and data.get("zones", {}).get(self._zone_id):
            zone_data = data["zones"][self._zone_id]
            return {
                "sun_coefficient": zone_data.get("sun_coefficient"),
                "status": zone_data.get("status"),
            }
        return {}


class HydroBalanceZoneStatusSensor(HydroBalanceBaseSensor):
    """Per-zone status sensor."""

    _attr_icon = "mdi:sprinkler-variant"

    def __init__(self, coordinator, entry, zone):
        self._zone_id = zone[CONF_ZONE_ID]
        self._zone_name = zone.get(CONF_ZONE_NAME, self._zone_id)
        super().__init__(coordinator, entry, f"zone_{self._zone_id}_status")
        self._attr_name = f"{self._zone_name} Status"

    @property
    def native_value(self) -> str | None:
        data = self.coordinator.data
        if data and data.get("zones", {}).get(self._zone_id):
            return data["zones"][self._zone_id].get("status")
        return None


class HydroBalanceZoneSunCoefficientSensor(HydroBalanceBaseSensor):
    """Per-zone sun coefficient sensor."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:sun-angle"

    def __init__(self, coordinator, entry, zone):
        self._zone_id = zone[CONF_ZONE_ID]
        self._zone_name = zone.get(CONF_ZONE_NAME, self._zone_id)
        super().__init__(coordinator, entry, f"zone_{self._zone_id}_sun_coeff")
        self._attr_name = f"{self._zone_name} Sun Exposure"

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data
        if data and data.get("zones", {}).get(self._zone_id):
            return data["zones"][self._zone_id].get("sun_coefficient")
        return None
