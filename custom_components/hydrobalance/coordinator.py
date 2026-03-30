"""DataUpdateCoordinator for HydroBalance."""

from __future__ import annotations

import asyncio
import math
from collections import deque
from datetime import datetime, timedelta, date
from typing import Any

from astral import LocationInfo
from astral.sun import azimuth, elevation

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.helpers.sun import get_astral_location
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DOMAIN,
    LOGGER,
    STORAGE_VERSION,
    STORAGE_KEY_PREFIX,
    ET_COEFF_TEMP,
    ET_COEFF_UV,
    ET_COEFF_WIND,
    ET_COEFF_HUMIDITY,
    ET_MIN,
    ET_MAX,
    DEFICIT_MIN,
    DEFICIT_MAX,
    FROST_TEMP_LIMIT,
    RAIN_FORECAST_SKIP,
    SOIL_TYPES,
    STRATEGIES,
    SUN_EXPOSURE_MANUAL,
    SUN_ORIENTATION_FALLBACK,
    SOLAR_RADIATION_WEIGHTS,
    CONF_SOIL_TYPE,
    CONF_STRATEGY,
    CONF_ZONES,
    CONF_USE_FORECAST,
    CONF_SENSOR_TEMPERATURE,
    CONF_SENSOR_TEMPERATURE_MIN,
    CONF_SENSOR_TEMPERATURE_MAX,
    CONF_SENSOR_HUMIDITY,
    CONF_SENSOR_WIND_SPEED,
    CONF_SENSOR_UV_INDEX,
    CONF_SENSOR_RAIN,
    CONF_SENSOR_RAIN_FORECAST,
    CONF_ZONE_ID,
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
    DEFAULT_SPRINKLER_RATE,
    DEFAULT_DEFICIT_THRESHOLD,
    DEFAULT_MAX_PER_CYCLE,
)


class HydroBalanceCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for HydroBalance ET-based irrigation."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=15),
        )
        self.config_entry = entry
        self._store = Store(
            hass, STORAGE_VERSION, f"{STORAGE_KEY_PREFIX}.{entry.entry_id}"
        )
        self._unsub_daily: list = []
        self._watering_queue: deque[str] = deque()
        self._watering_active = False
        self._watering_task: asyncio.Task | None = None
        self._skip_next = False

        # Running daily accumulators
        self._today: date | None = None
        self._daily_tmin: float = 99.0
        self._daily_tmax: float = -99.0
        self._daily_peak_uv: float = 0.0
        self._daily_rain: float = 0.0
        self._last_rain_value: float | None = None

        # Persistent data
        self._zone_deficits: dict[str, float] = {}
        self._last_calc_date: str | None = None

        # Panel-managed configuration (zones, soil, strategy, sensors)
        self._store_data: dict[str, Any] = {
            "zones": [],
            "soil_type": "clay",
            "strategy": "balanced",
            "sensors": {},
        }

    @property
    def config(self) -> dict[str, Any]:
        """Get config entry data."""
        return self.config_entry.data

    @property
    def zones(self) -> list[dict[str, Any]]:
        """Get zone configurations from panel storage."""
        return self._store_data.get("zones", [])

    @property
    def soil_type(self) -> str:
        """Get system soil type from panel storage."""
        return self._store_data.get("soil_type", "clay")

    @property
    def strategy(self) -> dict[str, Any]:
        """Get current strategy config from panel storage."""
        key = self._store_data.get("strategy", "balanced")
        return STRATEGIES.get(key, STRATEGIES["balanced"])

    # ─── Lifecycle ────────────────────────────────────────────────────────────

    async def async_setup(self) -> None:
        """Load persisted data and set up time-based listeners."""
        stored = await self._store.async_load()
        if stored:
            self._zone_deficits = stored.get("zone_deficits", {})
            self._last_calc_date = stored.get("last_calc_date")
            self._daily_tmin = stored.get("daily_tmin", 99.0)
            self._daily_tmax = stored.get("daily_tmax", -99.0)
            self._daily_peak_uv = stored.get("daily_peak_uv", 0.0)
            self._daily_rain = stored.get("daily_rain", 0.0)
            self._today = (
                date.fromisoformat(stored["today"])
                if stored.get("today")
                else None
            )
            # Load panel-managed config
            self._store_data["zones"] = stored.get("zones", [])
            self._store_data["soil_type"] = stored.get("soil_type", "clay")
            self._store_data["strategy"] = stored.get("strategy", "balanced")
            self._store_data["sensors"] = stored.get("sensors", {})
            LOGGER.info("Loaded persisted data: deficits=%s, zones=%d", self._zone_deficits, len(self.zones))

        # Ensure all zones have a deficit entry
        for zone in self.zones:
            zid = zone[CONF_ZONE_ID]
            if zid not in self._zone_deficits:
                self._zone_deficits[zid] = 0.0

        # Daily ET calculation at 23:00
        self._unsub_daily.append(
            async_track_time_change(
                self.hass, self._async_daily_calculation, hour=23, minute=0, second=0
            )
        )

        # Watering check at sunrise - 1h (approximated as 05:00, adjusted by sun entity)
        self._unsub_daily.append(
            async_track_time_change(
                self.hass, self._async_watering_check, hour=5, minute=0, second=0
            )
        )

        # Safety check: turn off any managed switches that are on after restart
        await self._safety_check_switches()

    async def async_shutdown(self) -> None:
        """Clean up on unload."""
        for unsub in self._unsub_daily:
            unsub()
        self._unsub_daily.clear()
        if self._watering_task and not self._watering_task.done():
            self._watering_task.cancel()
        await self._persist()

    # ─── Data Update (every 15 min) ──────────────────────────────────────────

    async def _async_update_data(self) -> dict[str, Any]:
        """Update sensor readings and track daily min/max."""
        now = datetime.now()
        today = now.date()

        # Reset daily accumulators at midnight
        if self._today != today:
            self._today = today
            self._daily_tmin = 99.0
            self._daily_tmax = -99.0
            self._daily_peak_uv = 0.0
            self._daily_rain = 0.0
            self._last_rain_value = None

        # Read current sensor values
        temp = self._read_sensor(CONF_SENSOR_TEMPERATURE)
        humidity = self._read_sensor(CONF_SENSOR_HUMIDITY)
        wind = self._read_sensor(CONF_SENSOR_WIND_SPEED)
        uv = self._read_sensor(CONF_SENSOR_UV_INDEX)
        rain = self._read_sensor(CONF_SENSOR_RAIN)

        # Track running min/max
        if temp is not None:
            self._daily_tmin = min(self._daily_tmin, temp)
            self._daily_tmax = max(self._daily_tmax, temp)
        if uv is not None:
            self._daily_peak_uv = max(self._daily_peak_uv, uv)

        # Accumulate rain
        if rain is not None:
            if self._last_rain_value is not None:
                # If sensor gives hourly rate, just add it scaled to 15min
                # If sensor gives cumulative, compute delta
                # Assume hourly rate for OWM-style sensors
                self._daily_rain += rain * 0.25  # 15min = 0.25h
            self._last_rain_value = rain

        # Persist accumulators periodically
        await self._persist()

        # Calculate sun coefficients for all zones
        sun_coefficients = {}
        for zone in self.zones:
            zid = zone[CONF_ZONE_ID]
            sun_coefficients[zid] = self._calculate_sun_coefficient(zone)

        return {
            "daily": {
                "tmin": self._daily_tmin if self._daily_tmin < 99 else None,
                "tmax": self._daily_tmax if self._daily_tmax > -99 else None,
                "peak_uv": self._daily_peak_uv,
                "rain_accumulated": round(self._daily_rain, 1),
                "et": None,  # Set after daily calculation
                "effective_rain": None,
                "last_calc_date": self._last_calc_date,
            },
            "zones": {
                zone[CONF_ZONE_ID]: {
                    "water_deficit": round(
                        self._zone_deficits.get(zone[CONF_ZONE_ID], 0.0), 1
                    ),
                    "sun_coefficient": round(sun_coefficients.get(zone[CONF_ZONE_ID], 1.0), 2),
                    "status": self._get_zone_status(zone),
                    "config": zone,
                }
                for zone in self.zones
            },
            "watering": {
                "active": self._watering_active,
                "current_zone": (
                    self._watering_queue[0] if self._watering_queue else None
                ),
                "skip_next": self._skip_next,
            },
        }

    # ─── Sensor Reading ───────────────────────────────────────────────────────

    def _read_sensor(self, config_key: str) -> float | None:
        """Read a sensor value from HA state."""
        # Check panel sensors first, then config entry
        entity_id = self._store_data.get("sensors", {}).get(config_key) or self.config.get(config_key)
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable"):
            return None
        try:
            return float(state.state)
        except (ValueError, TypeError):
            return None

    # ─── ET Calculation ───────────────────────────────────────────────────────

    @staticmethod
    def calculate_et(
        tmin: float, tmax: float, uv: float, wind: float, humidity: float
    ) -> float:
        """Calculate daily evapotranspiration in mm.

        ET = (Tmean × 0.15) + (UV × 0.25) + (wind_km_h × 0.02) - (humidity% × 0.015)
        Clamped to 0-8 mm/day.
        """
        tmean = (tmax + tmin) / 2
        et = (
            tmean * ET_COEFF_TEMP
            + uv * ET_COEFF_UV
            + wind * ET_COEFF_WIND
            - humidity * ET_COEFF_HUMIDITY
        )
        return max(ET_MIN, min(ET_MAX, round(et, 2)))

    @staticmethod
    def calculate_effective_rain(rain_mm: float, soil_type: str) -> float:
        """Calculate effective precipitation based on soil type.

        Rain bands: 0-2mm, 2-5mm, 5-15mm, >15mm
        Each soil type has different absorption coefficients per band.
        """
        coefficients = SOIL_TYPES.get(soil_type, SOIL_TYPES["clay"])["coefficients"]

        if rain_mm < 2:
            return round(rain_mm * coefficients[0], 2)
        if rain_mm < 5:
            return round(rain_mm * coefficients[1], 2)
        if rain_mm <= 15:
            return round(rain_mm * coefficients[2], 2)
        return round(rain_mm * coefficients[3], 2)

    # ─── Sun Coefficient ──────────────────────────────────────────────────────

    def _calculate_sun_coefficient(self, zone: dict[str, Any]) -> float:
        """Calculate solar exposure coefficient for a zone."""
        mode = zone.get(CONF_ZONE_SUN_EXPOSURE_MODE, "manual")

        if mode == "manual":
            exposure = zone.get(CONF_ZONE_SUN_EXPOSURE, "full_sun")
            return SUN_EXPOSURE_MANUAL.get(exposure, 1.0)

        # Auto mode
        orientation = zone.get(CONF_ZONE_ORIENTATION)
        obstacle_height = zone.get(CONF_ZONE_OBSTACLE_HEIGHT)
        obstacle_distance = zone.get(CONF_ZONE_OBSTACLE_DISTANCE)

        if not orientation:
            return 1.0

        # If no obstacle dimensions, use fallback coefficients
        if not obstacle_height or not obstacle_distance:
            return SUN_ORIENTATION_FALLBACK.get(orientation, 0.80)

        # Full shadow calculation using astral
        return self._calculate_shadow_coefficient(
            orientation, obstacle_height, obstacle_distance
        )

    def _calculate_shadow_coefficient(
        self, orientation: str, obstacle_height: float, obstacle_distance: float
    ) -> float:
        """Calculate shadow coefficient using sun position geometry."""
        lat = self.hass.config.latitude
        lon = self.hass.config.longitude
        today = datetime.now().date()

        # Convert orientation to azimuth (direction zone faces FROM obstacle)
        orientation_azimuths = {
            "N": 180,   # Zone is north of obstacle → obstacle is south → blocks sun from south
            "NE": 225,
            "E": 270,
            "SE": 315,
            "S": 0,
            "SW": 45,
            "W": 90,
            "NW": 135,
        }
        obstacle_azimuth = orientation_azimuths.get(orientation, 180)

        location = LocationInfo(latitude=lat, longitude=lon)
        shaded_weight = 0.0
        total_weight = 0.0

        for (h_start, h_end), weight in SOLAR_RADIATION_WEIGHTS.items():
            hours_shaded = 0
            hours_total = h_end - h_start

            for h in range(h_start, h_end):
                dt = datetime(today.year, today.month, today.day, h, 30)
                try:
                    sun_elev = elevation(location.observer, dt)
                    sun_az = azimuth(location.observer, dt)
                except Exception:
                    continue

                if sun_elev <= 0:
                    continue

                # Check if sun is behind the obstacle relative to zone
                az_diff = abs(sun_az - obstacle_azimuth)
                if az_diff > 180:
                    az_diff = 360 - az_diff

                # Shadow reaches zone if sun is roughly behind obstacle (within 60°)
                # and shadow length exceeds distance
                if az_diff < 60:
                    shadow_length = obstacle_height / math.tan(math.radians(sun_elev))
                    if shadow_length > obstacle_distance:
                        hours_shaded += 1

            if hours_total > 0:
                shade_fraction = hours_shaded / hours_total
                shaded_weight += shade_fraction * weight
                total_weight += weight

        if total_weight == 0:
            return 1.0

        return round(1.0 - (shaded_weight / total_weight), 2)

    # ─── Daily Calculation (23:00) ────────────────────────────────────────────

    async def _async_daily_calculation(self, _now: datetime) -> None:
        """Run daily ET calculation and update zone deficits."""
        today_str = date.today().isoformat()

        # Don't run twice on the same day
        if self._last_calc_date == today_str:
            LOGGER.debug("Daily calculation already done for %s", today_str)
            return

        tmin = self._daily_tmin if self._daily_tmin < 99 else None
        tmax = self._daily_tmax if self._daily_tmax > -99 else None
        uv = self._daily_peak_uv
        wind = self._read_sensor(CONF_SENSOR_WIND_SPEED) or 0.0
        humidity = self._read_sensor(CONF_SENSOR_HUMIDITY) or 50.0
        rain = self._daily_rain

        if tmin is None or tmax is None:
            LOGGER.warning("Missing temperature data, skipping ET calculation")
            return

        # Calculate ET
        et = self.calculate_et(tmin, tmax, uv, wind, humidity)

        # Calculate effective rain (system-level, then adjusted per zone)
        system_soil = self.soil_type
        eff_rain_system = self.calculate_effective_rain(rain, system_soil)

        LOGGER.info(
            "Daily ET=%.2fmm, Rain=%.1fmm, EffRain=%.2fmm (Tmin=%.1f Tmax=%.1f UV=%.1f Wind=%.1f Hum=%.0f)",
            et, rain, eff_rain_system, tmin, tmax, uv, wind, humidity,
        )

        # Update each zone's deficit
        for zone in self.zones:
            zid = zone[CONF_ZONE_ID]
            sun_coeff = self._calculate_sun_coefficient(zone)

            # Per-zone soil type (override or system default)
            zone_soil = zone.get(CONF_ZONE_SOIL_OVERRIDE) or system_soil
            eff_rain = self.calculate_effective_rain(rain, zone_soil)

            # Zone ET adjusted by sun exposure
            zone_et = et * sun_coeff

            # Update deficit
            current = self._zone_deficits.get(zid, 0.0)
            new_deficit = current + zone_et - eff_rain
            new_deficit = max(DEFICIT_MIN, min(DEFICIT_MAX, new_deficit))
            self._zone_deficits[zid] = round(new_deficit, 1)

            LOGGER.info(
                "Zone %s: ET=%.2f×%.2f=%.2fmm, EffRain=%.2fmm, Deficit: %.1f→%.1f",
                zid, et, sun_coeff, zone_et, eff_rain, current, new_deficit,
            )

        self._last_calc_date = today_str
        await self._persist()
        await self.async_request_refresh()

    # ─── Watering Check (sunrise - 1h) ───────────────────────────────────────

    async def _async_watering_check(self, _now: datetime) -> None:
        """Check if any zones need watering."""
        if self._skip_next:
            LOGGER.info("Watering skipped (skip_next flag)")
            self._skip_next = False
            await self._persist()
            return

        if self._watering_active:
            LOGGER.warning("Watering already in progress, skipping check")
            return

        # Frost protection
        tmin_sensor = self._read_sensor(CONF_SENSOR_TEMPERATURE_MIN)
        if tmin_sensor is not None and tmin_sensor < FROST_TEMP_LIMIT:
            LOGGER.info("Frost protection: Tmin=%.1f < %.1f, skipping", tmin_sensor, FROST_TEMP_LIMIT)
            return

        # Rain forecast skip
        if self.config.get(CONF_USE_FORECAST):
            forecast = self._read_sensor(CONF_SENSOR_RAIN_FORECAST)
            if forecast is not None and forecast > RAIN_FORECAST_SKIP:
                LOGGER.info("Rain forecast %.1fmm > %.1f, skipping", forecast, RAIN_FORECAST_SKIP)
                return

        # Build watering queue
        queue = []
        for zone in self.zones:
            zid = zone[CONF_ZONE_ID]
            deficit = self._zone_deficits.get(zid, 0.0)
            threshold = zone.get(
                CONF_ZONE_DEFICIT_THRESHOLD,
                self.strategy["deficit_threshold"],
            )
            if deficit > threshold:
                queue.append(zid)
                LOGGER.info("Zone %s deficit %.1f > threshold %.1f → queued", zid, deficit, threshold)

        if not queue:
            LOGGER.info("No zones need watering")
            return

        self._watering_queue = deque(queue)
        self._watering_task = self.hass.async_create_task(
            self._process_watering_queue()
        )

    async def _process_watering_queue(self) -> None:
        """Process the watering queue sequentially."""
        self._watering_active = True
        await self.async_request_refresh()

        while self._watering_queue:
            zone_id = self._watering_queue[0]
            zone = self._get_zone_config(zone_id)
            if zone is None:
                self._watering_queue.popleft()
                continue

            deficit = self._zone_deficits.get(zone_id, 0.0)
            max_per_cycle = zone.get(
                CONF_ZONE_MAX_PER_CYCLE,
                self.strategy.get("max_per_cycle", DEFAULT_MAX_PER_CYCLE),
            )
            mm_to_apply = min(deficit, max_per_cycle)
            sprinkler_rate = zone.get(CONF_ZONE_SPRINKLER_RATE, DEFAULT_SPRINKLER_RATE)

            duration_minutes = max(1, (mm_to_apply / sprinkler_rate) * 30)

            switch_entity = zone.get(CONF_ZONE_SWITCH)
            if not switch_entity:
                LOGGER.warning("Zone %s has no switch entity", zone_id)
                self._watering_queue.popleft()
                continue

            LOGGER.info(
                "Watering zone %s: %.1fmm for %.0f min (switch: %s)",
                zone_id, mm_to_apply, duration_minutes, switch_entity,
            )

            # Turn on
            await self.hass.services.async_call(
                "switch", "turn_on", {"entity_id": switch_entity}
            )
            await self.async_request_refresh()

            # Wait
            try:
                await asyncio.sleep(duration_minutes * 60)
            except asyncio.CancelledError:
                # Emergency stop — turn off switch
                await self.hass.services.async_call(
                    "switch", "turn_off", {"entity_id": switch_entity}
                )
                LOGGER.warning("Watering cancelled for zone %s", zone_id)
                break

            # Turn off
            await self.hass.services.async_call(
                "switch", "turn_off", {"entity_id": switch_entity}
            )

            # Update deficit
            self._zone_deficits[zone_id] = round(
                max(DEFICIT_MIN, self._zone_deficits.get(zone_id, 0.0) - mm_to_apply), 1
            )
            LOGGER.info(
                "Zone %s done. Applied %.1fmm, new deficit: %.1f",
                zone_id, mm_to_apply, self._zone_deficits[zone_id],
            )

            self._watering_queue.popleft()
            await self.async_request_refresh()

        self._watering_active = False
        await self._persist()
        await self.async_request_refresh()

    # ─── Services ─────────────────────────────────────────────────────────────

    async def async_force_water(self, zone_id: str | None = None, mm: float | None = None) -> None:
        """Force watering for a zone or all zones."""
        zones = (
            [zone_id] if zone_id else [z[CONF_ZONE_ID] for z in self.zones]
        )
        for zid in zones:
            zone = self._get_zone_config(zid)
            if zone:
                max_cycle = zone.get(CONF_ZONE_MAX_PER_CYCLE, DEFAULT_MAX_PER_CYCLE)
                self._zone_deficits[zid] = mm or max_cycle + DEFAULT_DEFICIT_THRESHOLD
        self._watering_queue = deque(zones)
        self._watering_task = self.hass.async_create_task(
            self._process_watering_queue()
        )

    async def async_skip_day(self) -> None:
        """Skip the next watering check."""
        self._skip_next = True
        await self._persist()
        await self.async_request_refresh()

    async def async_reset_deficit(self, zone_id: str | None = None) -> None:
        """Reset water deficit to 0 for a zone or all zones."""
        if zone_id:
            self._zone_deficits[zone_id] = 0.0
        else:
            for zid in self._zone_deficits:
                self._zone_deficits[zid] = 0.0
        await self._persist()
        await self.async_request_refresh()

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _get_zone_config(self, zone_id: str) -> dict[str, Any] | None:
        """Get zone configuration by ID."""
        for zone in self.zones:
            if zone[CONF_ZONE_ID] == zone_id:
                return zone
        return None

    def _get_zone_status(self, zone: dict[str, Any]) -> str:
        """Get the status string for a zone."""
        zid = zone[CONF_ZONE_ID]
        if self._watering_active and self._watering_queue and self._watering_queue[0] == zid:
            return "watering"
        deficit = self._zone_deficits.get(zid, 0.0)
        threshold = zone.get(
            CONF_ZONE_DEFICIT_THRESHOLD,
            self.strategy["deficit_threshold"],
        )
        if deficit > threshold:
            return "needs_water"
        return "ok"

    async def _safety_check_switches(self) -> None:
        """Turn off any managed switches that are on after restart."""
        for zone in self.zones:
            switch_entity = zone.get(CONF_ZONE_SWITCH)
            if not switch_entity:
                continue
            state = self.hass.states.get(switch_entity)
            if state and state.state == "on":
                LOGGER.warning(
                    "Safety: turning off %s (was on after restart)", switch_entity
                )
                await self.hass.services.async_call(
                    "switch", "turn_off", {"entity_id": switch_entity}
                )

    async def async_save_panel_config(self) -> None:
        """Save panel configuration (called from WebSocket API)."""
        await self._persist()

    async def _persist(self) -> None:
        """Save state to persistent storage."""
        await self._store.async_save({
            "zone_deficits": self._zone_deficits,
            "last_calc_date": self._last_calc_date,
            "daily_tmin": self._daily_tmin,
            "daily_tmax": self._daily_tmax,
            "daily_peak_uv": self._daily_peak_uv,
            "daily_rain": self._daily_rain,
            "today": self._today.isoformat() if self._today else None,
            # Panel-managed config
            "zones": self._store_data.get("zones", []),
            "soil_type": self._store_data.get("soil_type", "clay"),
            "strategy": self._store_data.get("strategy", "balanced"),
            "sensors": self._store_data.get("sensors", {}),
        })
