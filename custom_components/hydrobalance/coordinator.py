"""DataUpdateCoordinator for HydroBalance."""

from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timedelta, date
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_sunrise, async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.helpers.sun import get_astral_location
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import calc
from .const import (
    DOMAIN,
    LOGGER,
    STORAGE_VERSION,
    STORAGE_KEY_PREFIX,
    DEFICIT_MIN,
    DEFICIT_MAX,
    SOIL_TYPES,
    FROST_TEMP_LIMIT,
    RAIN_FORECAST_SKIP,
    STRATEGIES,
    CONF_SOIL_TYPE,
    CONF_STRATEGY,
    CONF_ZONES,
    CONF_USE_FORECAST,
    CONF_USE_SOIL_MOISTURE,
    DEFAULT_USE_SOIL_MOISTURE,
    CONF_WEATHER_ENTITY,
    CONF_SENSOR_TEMPERATURE,
    CONF_SENSOR_TEMPERATURE_MIN,
    CONF_SENSOR_HUMIDITY,
    CONF_SENSOR_WIND_SPEED,
    CONF_SENSOR_UV_INDEX,
    CONF_SENSOR_RAIN,
    CONF_SENSOR_RAIN_FORECAST,
    CONF_SENSOR_SOIL_MOISTURE,
    CONF_MOISTURE_SKIP_THRESHOLD,
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
    CONF_ZONE_CROP_COEFFICIENT,
    CONF_ZONE_CYCLE_SOAK,
    CONF_ZONE_PULSE_MINUTES,
    CONF_ZONE_SOAK_MINUTES,
    DEFAULT_CROP_COEFFICIENT,
    DEFAULT_PULSE_MINUTES,
    DEFAULT_SOAK_MINUTES,
    DEFAULT_SPRINKLER_RATE,
    DEFAULT_DEFICIT_THRESHOLD,
    DEFAULT_MAX_PER_CYCLE,
    DEFAULT_MOISTURE_SKIP_THRESHOLD,
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
        # Master enable — when False, automatic watering is suspended.
        self._enabled = True
        # Rain delay / vacation: ISO timestamp until which auto watering pauses.
        self._rain_delay_until: str | None = None
        # Manual override: zone_id -> ISO start timestamp while running
        self._manual_active: dict[str, str] = {}

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
        self._zone_water_used: dict[str, float] = {}  # cumulative mm per zone
        self._zone_last_watered: dict[str, str] = {}  # zone_id -> ISO timestamp
        # Last daily ET / effective-rain result, surfaced on the dashboard.
        self._last_et: float | None = None
        self._last_effective_rain: float | None = None

        # In-memory ring of recent events for the panel (not persisted; HA's
        # logbook/recorder holds the durable record via fired bus events).
        self._recent_events: deque[dict[str, Any]] = deque(maxlen=50)
        # Trigger label for the run currently being processed.
        self._current_trigger = "auto"

        # Panel-managed configuration (zones, soil, strategy, sensors)
        self._store_data: dict[str, Any] = {
            "zones": [],
            "soil_type": "clay",
            "strategy": "balanced",
            "sensors": {},
            "sensors_fallback": {},
            CONF_MOISTURE_SKIP_THRESHOLD: DEFAULT_MOISTURE_SKIP_THRESHOLD,
            CONF_USE_SOIL_MOISTURE: DEFAULT_USE_SOIL_MOISTURE,
            CONF_WEATHER_ENTITY: None,
            CONF_USE_FORECAST: True,
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

    @property
    def moisture_skip_threshold(self) -> float:
        """Get soil-moisture skip threshold (% VWC)."""
        return self._store_data.get(
            CONF_MOISTURE_SKIP_THRESHOLD, DEFAULT_MOISTURE_SKIP_THRESHOLD
        )

    @property
    def weather_entity(self) -> str | None:
        """Get the weather entity (panel storage, falling back to config entry)."""
        return self._store_data.get(CONF_WEATHER_ENTITY) or self.config.get(
            CONF_WEATHER_ENTITY
        )

    @property
    def use_forecast(self) -> bool:
        """Get whether rain-forecast skip is enabled."""
        val = self._store_data.get(CONF_USE_FORECAST)
        if val is None:
            return bool(self.config.get(CONF_USE_FORECAST, True))
        return bool(val)

    @property
    def use_soil_moisture(self) -> bool:
        """Whether the soil-moisture sensor steers watering (vs. ET-only)."""
        val = self._store_data.get(CONF_USE_SOIL_MOISTURE)
        if val is None:
            return DEFAULT_USE_SOIL_MOISTURE
        return bool(val)

    # ─── Lifecycle ────────────────────────────────────────────────────────────

    async def async_setup(self) -> None:
        """Load persisted data and set up time-based listeners."""
        stored = await self._store.async_load()
        if stored:
            self._zone_deficits = stored.get("zone_deficits", {})
            self._zone_water_used = stored.get("zone_water_used", {})
            self._zone_last_watered = stored.get("zone_last_watered", {})
            self._last_calc_date = stored.get("last_calc_date")
            self._last_et = stored.get("last_et")
            self._last_effective_rain = stored.get("last_effective_rain")
            self._daily_tmin = stored.get("daily_tmin", 99.0)
            self._daily_tmax = stored.get("daily_tmax", -99.0)
            self._daily_peak_uv = stored.get("daily_peak_uv", 0.0)
            self._daily_rain = stored.get("daily_rain", 0.0)
            self._today = (
                date.fromisoformat(stored["today"])
                if stored.get("today")
                else None
            )
            self._manual_active = stored.get("manual_active", {})
            self._enabled = stored.get("enabled", True)
            self._rain_delay_until = stored.get("rain_delay_until")
            # Load panel-managed config
            self._store_data["zones"] = stored.get("zones", [])
            self._store_data["soil_type"] = stored.get("soil_type", "clay")
            self._store_data["strategy"] = stored.get("strategy", "balanced")
            self._store_data["sensors"] = stored.get("sensors", {})
            self._store_data["sensors_fallback"] = stored.get("sensors_fallback", {})
            self._store_data[CONF_MOISTURE_SKIP_THRESHOLD] = stored.get(
                CONF_MOISTURE_SKIP_THRESHOLD, DEFAULT_MOISTURE_SKIP_THRESHOLD
            )
            self._store_data[CONF_USE_SOIL_MOISTURE] = stored.get(
                CONF_USE_SOIL_MOISTURE, DEFAULT_USE_SOIL_MOISTURE
            )
            # Migrate weather_entity/use_forecast from config entry on first load
            self._store_data[CONF_WEATHER_ENTITY] = stored.get(
                CONF_WEATHER_ENTITY, self.config.get(CONF_WEATHER_ENTITY)
            )
            self._store_data[CONF_USE_FORECAST] = stored.get(
                CONF_USE_FORECAST, self.config.get(CONF_USE_FORECAST, True)
            )
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

        # Watering check 1h before sunrise — coolest, lowest wind, so the
        # least evaporation loss and foliage dries off during the day.
        self._unsub_daily.append(
            async_track_sunrise(
                self.hass, self._async_watering_check, offset=timedelta(hours=-1)
            )
        )

        # Finalize any manual watering interrupted by a restart: count the
        # elapsed time up to now, subtract from the deficit, and turn the
        # switch off (handled inside _finalize_manual).
        if self._manual_active:
            for zid in list(self._manual_active.keys()):
                await self._finalize_manual(zid)
            await self._persist()

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
                "et": self._last_et,
                "effective_rain": self._last_effective_rain,
                "last_calc_date": self._last_calc_date,
            },
            "zones": {
                zone[CONF_ZONE_ID]: {
                    "water_deficit": round(
                        self._zone_deficits.get(zone[CONF_ZONE_ID], 0.0), 1
                    ),
                    "sun_coefficient": round(sun_coefficients.get(zone[CONF_ZONE_ID], 1.0), 2),
                    "status": self._get_zone_status(zone),
                    "manual_active": zone[CONF_ZONE_ID] in self._manual_active,
                    "manual_started": self._manual_active.get(zone[CONF_ZONE_ID]),
                    "water_used": round(
                        self._zone_water_used.get(zone[CONF_ZONE_ID], 0.0), 1
                    ),
                    "last_watered": self._zone_last_watered.get(zone[CONF_ZONE_ID]),
                    "config": zone,
                }
                for zone in self.zones
            },
            "events": list(self._recent_events),
            "watering": {
                "active": self._watering_active,
                "current_zone": (
                    self._watering_queue[0] if self._watering_queue else None
                ),
                "skip_next": self._skip_next,
            },
            "soil": {
                "moisture": self._read_sensor(CONF_SENSOR_SOIL_MOISTURE),
                "skip_threshold": self.moisture_skip_threshold,
            },
            "system": {
                "enabled": self._enabled,
                "rain_delay_until": self._rain_delay_until,
                "rain_delay_active": self.rain_delay_active,
            },
        }

    # ─── Sensor Reading ───────────────────────────────────────────────────────

    def _read_entity(self, entity_id: str | None) -> float | None:
        """Read a single HA state as a float, or None if missing/unavailable."""
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable"):
            return None
        try:
            return float(state.state)
        except (ValueError, TypeError):
            return None

    def _read_sensor(self, config_key: str) -> float | None:
        """Read a sensor value, preferring the real local sensor over the fallback.

        Resolution order: primary (panel sensors → config entry) → fallback
        (e.g. a weather-forecast entity). The primary is meant to be a real
        local sensor that reflects reality; the fallback covers it going
        unavailable so the term isn't silently dropped from the calculation.
        """
        primary = self._store_data.get("sensors", {}).get(config_key) or self.config.get(config_key)
        value = self._read_entity(primary)
        if value is not None:
            return value

        fallback = self._store_data.get("sensors_fallback", {}).get(config_key)
        value = self._read_entity(fallback)
        if value is not None and primary:
            LOGGER.debug(
                "Sensor %s primary (%s) unavailable, using fallback %s",
                config_key, primary, fallback,
            )
        return value

    def _zone_field_capacity(self, zone: dict[str, Any]) -> float:
        """Max plant-available water (mm) for this zone's soil — caps the deficit."""
        zone_soil = zone.get(CONF_ZONE_SOIL_OVERRIDE) or self.soil_type
        soil = SOIL_TYPES.get(zone_soil) or SOIL_TYPES.get("clay", {})
        return float(soil.get("field_capacity", DEFICIT_MAX))

    # ─── ET Calculation ───────────────────────────────────────────────────────

    calculate_et = staticmethod(calc.calculate_et)
    calculate_effective_rain = staticmethod(calc.calculate_effective_rain)

    # ─── Sun Coefficient ──────────────────────────────────────────────────────

    def _calculate_sun_coefficient(self, zone: dict[str, Any]) -> float:
        """Calculate solar exposure coefficient for a zone."""
        mode = zone.get(CONF_ZONE_SUN_EXPOSURE_MODE, "manual")

        if mode == "manual":
            exposure = zone.get(CONF_ZONE_SUN_EXPOSURE, "full_sun")
            return calc.manual_sun_coefficient(exposure)

        # Auto mode
        orientation = zone.get(CONF_ZONE_ORIENTATION)
        obstacle_height = zone.get(CONF_ZONE_OBSTACLE_HEIGHT)
        obstacle_distance = zone.get(CONF_ZONE_OBSTACLE_DISTANCE)

        if not orientation:
            return 1.0

        # If no obstacle dimensions, use fallback coefficients
        if not obstacle_height or not obstacle_distance:
            return calc.orientation_fallback(orientation)

        # Full shadow calculation using astral
        return calc.shadow_coefficient(
            self.hass.config.latitude,
            self.hass.config.longitude,
            datetime.now().date(),
            orientation,
            obstacle_height,
            obstacle_distance,
        )

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

        # Persist for the dashboard — without this the panel sees None forever.
        self._last_et = round(et, 2)
        self._last_effective_rain = round(eff_rain_system, 2)

        LOGGER.info(
            "Daily ET=%.2fmm, Rain=%.1fmm, EffRain=%.2fmm (Tmin=%.1f Tmax=%.1f UV=%.1f Wind=%.1f Hum=%.0f)",
            et, rain, eff_rain_system, tmin, tmax, uv, wind, humidity,
        )

        # When the soil-moisture sensor says the ground is still wet, don't pile
        # on ET debt — the measurement overrides the estimate. Only rain is
        # applied (it can still pay down an existing deficit). This is the
        # "trust the sensor over the model" half of the flip switch; it falls
        # back to ET-only automatically when the sensor is unavailable.
        moisture = self._read_sensor(CONF_SENSOR_SOIL_MOISTURE)
        freeze_et = (
            self.use_soil_moisture
            and moisture is not None
            and moisture > self.moisture_skip_threshold
        )
        if freeze_et:
            LOGGER.info(
                "Soil moisture %.0f%% > %.0f%% — freezing ET, only rain applied today",
                moisture, self.moisture_skip_threshold,
            )

        # Update each zone's deficit
        for zone in self.zones:
            zid = zone[CONF_ZONE_ID]
            sun_coeff = self._calculate_sun_coefficient(zone)

            # Per-zone soil type (override or system default)
            zone_soil = zone.get(CONF_ZONE_SOIL_OVERRIDE) or system_soil
            eff_rain = self.calculate_effective_rain(rain, zone_soil)

            # Zone ET adjusted by sun exposure and crop coefficient
            kc = zone.get(CONF_ZONE_CROP_COEFFICIENT, DEFAULT_CROP_COEFFICIENT)
            zone_et = 0.0 if freeze_et else et * sun_coeff * kc

            # Update deficit — cap at the soil's field capacity so a long skip
            # can't accumulate more debt than the soil could physically lose.
            current = self._zone_deficits.get(zid, 0.0)
            new_deficit = current + zone_et - eff_rain
            cap = self._zone_field_capacity(zone)
            new_deficit = max(DEFICIT_MIN, min(cap, new_deficit))
            self._zone_deficits[zid] = round(new_deficit, 1)

            LOGGER.info(
                "Zone %s: ET=%.2f×%.2f×Kc%.2f=%.2fmm, EffRain=%.2fmm, Deficit: %.1f→%.1f",
                zid, et, sun_coeff, kc, zone_et, eff_rain, current, new_deficit,
            )

        self._last_calc_date = today_str
        await self._persist()
        await self.async_request_refresh()

    # ─── Watering Check (sunrise - 1h) ───────────────────────────────────────

    @property
    def rain_delay_active(self) -> bool:
        """Whether a rain-delay/vacation pause is currently in effect."""
        if not self._rain_delay_until:
            return False
        return datetime.now() < datetime.fromisoformat(self._rain_delay_until)

    async def _async_watering_check(self, _now: datetime | None = None) -> None:
        """Check if any zones need watering."""
        if not self._enabled:
            LOGGER.info("Watering skipped (system disabled)")
            self._log_event("skipped", reason="disabled")
            return

        if self.rain_delay_active:
            LOGGER.info("Watering skipped (rain delay until %s)", self._rain_delay_until)
            self._log_event("skipped", reason="rain_delay")
            return

        if self._skip_next:
            LOGGER.info("Watering skipped (skip_next flag)")
            self._skip_next = False
            self._log_event("skipped", reason="skip_next")
            await self._persist()
            return

        if self._watering_active:
            LOGGER.warning("Watering already in progress, skipping check")
            return

        # Frost protection
        tmin_sensor = self._read_sensor(CONF_SENSOR_TEMPERATURE_MIN)
        if tmin_sensor is not None and tmin_sensor < FROST_TEMP_LIMIT:
            LOGGER.info("Frost protection: Tmin=%.1f < %.1f, skipping", tmin_sensor, FROST_TEMP_LIMIT)
            self._log_event("skipped", reason="frost")
            return

        # Rain forecast skip
        if self.use_forecast:
            forecast = self._read_sensor(CONF_SENSOR_RAIN_FORECAST)
            if forecast is not None and forecast > RAIN_FORECAST_SKIP:
                LOGGER.info("Rain forecast %.1fmm > %.1f, skipping", forecast, RAIN_FORECAST_SKIP)
                self._log_event("skipped", reason="rain_forecast")
                return

        # Soil-moisture skip (real sensor feedback overrides ET estimate).
        # Only consulted when the soil-moisture mode is enabled; otherwise the
        # system runs purely on the ET deficit model.
        if self.use_soil_moisture:
            moisture = self._read_sensor(CONF_SENSOR_SOIL_MOISTURE)
            if moisture is not None and moisture > self.moisture_skip_threshold:
                LOGGER.info(
                    "Soil moisture %.1f%% > %.1f%%, skipping watering",
                    moisture, self.moisture_skip_threshold,
                )
                self._log_event("skipped", reason="soil_moisture")
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

        self._current_trigger = "auto"
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

            switch_entity = zone.get(CONF_ZONE_SWITCH)
            if not switch_entity:
                LOGGER.warning("Zone %s has no switch entity", zone_id)
                self._watering_queue.popleft()
                continue

            deficit = self._zone_deficits.get(zone_id, 0.0)
            max_per_cycle = zone.get(
                CONF_ZONE_MAX_PER_CYCLE,
                self.strategy.get("max_per_cycle", DEFAULT_MAX_PER_CYCLE),
            )
            mm_to_apply = min(deficit, max_per_cycle)
            sprinkler_rate = zone.get(CONF_ZONE_SPRINKLER_RATE, DEFAULT_SPRINKLER_RATE)

            total_minutes = max(1.0, (mm_to_apply / sprinkler_rate) * 30)

            # Cycle & soak splits the run into pulses with rest periods so
            # water soaks in instead of running off (clay, slopes). When off,
            # one pulse covers the whole run.
            if zone.get(CONF_ZONE_CYCLE_SOAK):
                pulse_minutes = max(
                    1.0, zone.get(CONF_ZONE_PULSE_MINUTES, DEFAULT_PULSE_MINUTES)
                )
                soak_minutes = max(
                    0.0, zone.get(CONF_ZONE_SOAK_MINUTES, DEFAULT_SOAK_MINUTES)
                )
            else:
                pulse_minutes = total_minutes
                soak_minutes = 0.0

            LOGGER.info(
                "Watering zone %s: %.1fmm over %.0f min (pulse=%.0f soak=%.0f, switch=%s)",
                zone_id, mm_to_apply, total_minutes, pulse_minutes, soak_minutes, switch_entity,
            )

            applied_mm = 0.0
            remaining = total_minutes
            cancelled = False

            try:
                while remaining > 0.01:
                    run = min(pulse_minutes, remaining)
                    await self.hass.services.async_call(
                        "switch", "turn_on", {"entity_id": switch_entity}
                    )
                    await self.async_request_refresh()

                    pulse_start = datetime.now()
                    try:
                        await asyncio.sleep(run * 60)
                        ran_min = run
                    except asyncio.CancelledError:
                        ran_min = (
                            datetime.now() - pulse_start
                        ).total_seconds() / 60
                        cancelled = True

                    # Turn off and credit the water actually delivered, so a
                    # cancellation mid-run only forfeits the undelivered part.
                    await self.hass.services.async_call(
                        "switch", "turn_off", {"entity_id": switch_entity}
                    )
                    delivered = (ran_min / 30) * sprinkler_rate
                    applied_mm += delivered
                    self._zone_deficits[zone_id] = round(
                        max(DEFICIT_MIN, self._zone_deficits.get(zone_id, 0.0) - delivered),
                        1,
                    )
                    remaining -= ran_min

                    if cancelled:
                        break
                    if remaining > 0.01 and soak_minutes > 0:
                        await asyncio.sleep(soak_minutes * 60)
            except asyncio.CancelledError:
                # Cancelled during a soak — make sure the switch is off.
                await self.hass.services.async_call(
                    "switch", "turn_off", {"entity_id": switch_entity}
                )
                cancelled = True

            if cancelled:
                LOGGER.warning(
                    "Watering cancelled for zone %s (applied %.1fmm)", zone_id, applied_mm
                )
                self._log_event(
                    "cancelled",
                    zone_id=zone_id,
                    mm=applied_mm,
                    trigger=self._current_trigger,
                )
                break

            LOGGER.info(
                "Zone %s done. Applied %.1fmm, new deficit: %.1f",
                zone_id, applied_mm, self._zone_deficits[zone_id],
            )
            self._log_event(
                "watered",
                zone_id=zone_id,
                mm=applied_mm,
                minutes=total_minutes,
                trigger=self._current_trigger,
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
        self._current_trigger = "forced"
        self._watering_queue = deque(zones)
        self._watering_task = self.hass.async_create_task(
            self._process_watering_queue()
        )

    async def async_manual_toggle(self, zone_id: str, turn_on: bool) -> None:
        """Manually start/stop watering a zone.

        Turning off counts the elapsed run time, converts it to mm using the
        zone's sprinkler rate, and reduces the deficit (never below 0).
        """
        zone = self._get_zone_config(zone_id)
        if zone is None:
            LOGGER.warning("Manual toggle: zone %s not found", zone_id)
            return

        switch_entity = zone.get(CONF_ZONE_SWITCH)
        if not switch_entity:
            LOGGER.warning("Manual toggle: zone %s has no switch entity", zone_id)
            return

        if turn_on:
            if zone_id in self._manual_active:
                return  # already running
            await self.hass.services.async_call(
                "switch", "turn_on", {"entity_id": switch_entity}
            )
            self._manual_active[zone_id] = datetime.now().isoformat()
            LOGGER.info("Manual watering ON for zone %s", zone_id)
        else:
            await self._finalize_manual(zone_id)

        await self._persist()
        # async_refresh (not request_refresh) so the panel's follow-up status
        # poll sees the new state instead of the still-debounced previous dict.
        await self.async_refresh()

    async def _finalize_manual(self, zone_id: str) -> None:
        """Stop a manual run, applying the watered mm to the zone deficit."""
        start_iso = self._manual_active.pop(zone_id, None)
        zone = self._get_zone_config(zone_id)
        switch_entity = zone.get(CONF_ZONE_SWITCH) if zone else None

        if switch_entity:
            await self.hass.services.async_call(
                "switch", "turn_off", {"entity_id": switch_entity}
            )

        if not start_iso or zone is None:
            return

        elapsed_min = (
            datetime.now() - datetime.fromisoformat(start_iso)
        ).total_seconds() / 60
        sprinkler_rate = zone.get(CONF_ZONE_SPRINKLER_RATE, DEFAULT_SPRINKLER_RATE)
        mm_applied = (elapsed_min / 30) * sprinkler_rate

        current = self._zone_deficits.get(zone_id, 0.0)
        new_deficit = max(0.0, current - mm_applied)
        self._zone_deficits[zone_id] = round(new_deficit, 1)

        LOGGER.info(
            "Manual watering OFF zone %s: %.1f min → %.1fmm, deficit %.1f→%.1f",
            zone_id, elapsed_min, mm_applied, current, new_deficit,
        )
        self._log_event(
            "watered",
            zone_id=zone_id,
            mm=mm_applied,
            minutes=elapsed_min,
            trigger="manual",
        )

    async def async_skip_day(self) -> None:
        """Skip the next watering check."""
        self._skip_next = True
        await self._persist()
        await self.async_refresh()

    async def async_set_enabled(self, enabled: bool) -> None:
        """Enable or disable automatic watering system-wide."""
        self._enabled = enabled
        LOGGER.info("HydroBalance %s", "enabled" if enabled else "disabled")
        await self._persist()
        await self.async_refresh()

    async def async_set_rain_delay(self, days: float) -> None:
        """Pause automatic watering for the next `days` days (vacation/rain).

        Passing 0 (or less) clears any active delay.
        """
        if days and days > 0:
            until = datetime.now() + timedelta(days=days)
            self._rain_delay_until = until.isoformat()
            LOGGER.info("Rain delay set until %s (%s days)", self._rain_delay_until, days)
        else:
            self._rain_delay_until = None
            LOGGER.info("Rain delay cleared")
        await self._persist()
        await self.async_refresh()

    async def async_reset_deficit(self, zone_id: str | None = None) -> None:
        """Reset water deficit to 0 for a zone or all zones."""
        if zone_id:
            self._zone_deficits[zone_id] = 0.0
        else:
            for zid in self._zone_deficits:
                self._zone_deficits[zid] = 0.0
        await self._persist()
        await self.async_refresh()

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _get_zone_config(self, zone_id: str) -> dict[str, Any] | None:
        """Get zone configuration by ID."""
        for zone in self.zones:
            if zone[CONF_ZONE_ID] == zone_id:
                return zone
        return None

    def _zone_label(self, zone_id: str | None) -> str | None:
        """Human-readable zone name for events/logbook."""
        if zone_id is None:
            return None
        zone = self._get_zone_config(zone_id)
        return zone.get(CONF_ZONE_NAME, zone_id) if zone else zone_id

    @callback
    def _log_event(
        self,
        kind: str,
        *,
        zone_id: str | None = None,
        mm: float | None = None,
        minutes: float | None = None,
        trigger: str | None = None,
        reason: str | None = None,
    ) -> None:
        """Record an event: update usage counters, ring buffer, and fire on the bus.

        For watered events, accumulates per-zone water usage and stamps the
        last-watered time. The fired bus event is what HA's logbook/recorder
        persists, so this method keeps no durable history of its own.
        """
        now_iso = datetime.now().isoformat()

        if kind == "watered" and zone_id is not None and mm:
            self._zone_water_used[zone_id] = round(
                self._zone_water_used.get(zone_id, 0.0) + mm, 1
            )
            self._zone_last_watered[zone_id] = now_iso

        event: dict[str, Any] = {
            "time": now_iso,
            "kind": kind,
            "zone_id": zone_id,
            "zone_name": self._zone_label(zone_id),
            "mm": round(mm, 1) if mm is not None else None,
            "minutes": round(minutes, 1) if minutes is not None else None,
            "trigger": trigger,
            "reason": reason,
        }
        self._recent_events.appendleft(event)
        self.hass.bus.async_fire(f"{DOMAIN}_event", event)

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
            "zone_water_used": self._zone_water_used,
            "zone_last_watered": self._zone_last_watered,
            "last_calc_date": self._last_calc_date,
            "last_et": self._last_et,
            "last_effective_rain": self._last_effective_rain,
            "daily_tmin": self._daily_tmin,
            "daily_tmax": self._daily_tmax,
            "daily_peak_uv": self._daily_peak_uv,
            "daily_rain": self._daily_rain,
            "today": self._today.isoformat() if self._today else None,
            "manual_active": self._manual_active,
            "enabled": self._enabled,
            "rain_delay_until": self._rain_delay_until,
            # Panel-managed config
            "zones": self._store_data.get("zones", []),
            "soil_type": self._store_data.get("soil_type", "clay"),
            "strategy": self._store_data.get("strategy", "balanced"),
            "sensors": self._store_data.get("sensors", {}),
            "sensors_fallback": self._store_data.get("sensors_fallback", {}),
            CONF_MOISTURE_SKIP_THRESHOLD: self.moisture_skip_threshold,
            CONF_USE_SOIL_MOISTURE: self.use_soil_moisture,
            CONF_WEATHER_ENTITY: self._store_data.get(CONF_WEATHER_ENTITY),
            CONF_USE_FORECAST: self._store_data.get(CONF_USE_FORECAST, True),
        })
