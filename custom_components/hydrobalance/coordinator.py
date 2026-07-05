"""DataUpdateCoordinator for HydroBalance."""

from __future__ import annotations

import asyncio
import math
from collections import deque
from datetime import datetime, timedelta, date
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SUN_EVENT_SUNRISE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import (
    async_call_later,
    async_track_point_in_time,
    async_track_time_change,
)
from homeassistant.helpers.storage import Store
from homeassistant.helpers.sun import get_location_astral_event_next
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
import homeassistant.util.dt as dt_util

from . import calc
from .const import (
    DOMAIN,
    LOGGER,
    STORAGE_VERSION,
    STORAGE_KEY_PREFIX,
    STORAGE_KEY_EVENTS,
    DEFAULT_HISTORY_RETENTION_DAYS,
    HISTORY_MAX_EVENTS,
    CONF_HISTORY_RETENTION_DAYS,
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
    CONF_WEATHER_PRIMARY,
    CONF_WEATHER_SECONDARY,
    CONF_ZONE_LOCAL_SENSORS,
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
    WATERING_TARGET_FINISH,
    WATERING_EARLIEST_START,
    WATERING_SUNRISE_OFFSET_H,
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
        # Dedicated store for the activity log (persisted across restarts,
        # pruned by retention). Kept apart from the main state file so it can
        # grow to weeks of history without bloating every state save.
        self._events_store = Store(
            hass, STORAGE_VERSION, f"{STORAGE_KEY_EVENTS}.{entry.entry_id}"
        )
        self._unsub_daily: list = []
        # One-shot cancel handle for the dynamically-scheduled watering start,
        # plus the planned start (ISO) surfaced on the dashboard.
        self._unsub_watering: Any = None
        self._planned_start: str | None = None
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
        # Planned end (ISO) when manual run has a timer; same key as _manual_active
        self._manual_ends: dict[str, str] = {}
        # Per-zone async_call_later cancel handles for the auto-stop timer
        self._manual_timers: dict[str, Any] = {}

        # Running daily accumulators
        self._today: date | None = None
        self._daily_tmin: float = 99.0
        self._daily_tmax: float = -99.0
        self._daily_peak_uv: float = 0.0
        self._daily_rain: float = 0.0
        self._last_rain_value: float | None = None
        # Today's forecast Tmax, refreshed each 15-min poll from the weather
        # entity. Used in the live-deficit hybrid so morning estimates aren't
        # anchored to the still-cool Tmax_so_far.
        self._today_forecast_tmax: float | None = None

        # Persistent data
        self._zone_deficits: dict[str, float] = {}
        self._last_calc_date: str | None = None
        self._zone_water_used: dict[str, float] = {}  # cumulative mm per zone
        self._zone_last_watered: dict[str, str] = {}  # zone_id -> ISO timestamp
        # Last daily ET / effective-rain result, surfaced on the dashboard.
        self._last_et: float | None = None
        self._last_effective_rain: float | None = None

        # Recent events for the panel — persisted to _events_store and pruned by
        # retention. Newest is appendleft (index 0); oldest at the right end.
        # maxlen is a hard safety cap; age-based pruning is the primary bound.
        self._recent_events: deque[dict[str, Any]] = deque(maxlen=HISTORY_MAX_EVENTS)
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
            CONF_HISTORY_RETENTION_DAYS: DEFAULT_HISTORY_RETENTION_DAYS,
            CONF_USE_SOIL_MOISTURE: DEFAULT_USE_SOIL_MOISTURE,
            CONF_WEATHER_ENTITY: None,
            CONF_WEATHER_PRIMARY: None,
            CONF_WEATHER_SECONDARY: None,
            CONF_USE_FORECAST: True,
        }
        # Per-zone running Tmin/Tmax accumulators (populated when a zone has a
        # local temperature sensor; otherwise it uses the system-wide values).
        self._zone_daily_temps: dict[str, dict[str, float]] = {}

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
    def history_retention_days(self) -> int:
        """How many days of Recent Activity to keep."""
        try:
            val = int(self._store_data.get(
                CONF_HISTORY_RETENTION_DAYS, DEFAULT_HISTORY_RETENTION_DAYS
            ))
        except (TypeError, ValueError):
            return DEFAULT_HISTORY_RETENTION_DAYS
        return max(1, val)

    @property
    def weather_entity(self) -> str | None:
        """Legacy: the single weather entity (used for sensor discovery).

        Returns the primary weather channel if set, otherwise the old config.
        """
        return (
            self._store_data.get(CONF_WEATHER_PRIMARY)
            or self._store_data.get(CONF_WEATHER_ENTITY)
            or self.config.get(CONF_WEATHER_ENTITY)
        )

    @property
    def weather_primary(self) -> str | None:
        """Primary weather channel (e.g. weather.openweathermap)."""
        return (
            self._store_data.get(CONF_WEATHER_PRIMARY)
            or self._store_data.get(CONF_WEATHER_ENTITY)
            or self.config.get(CONF_WEATHER_ENTITY)
        )

    @property
    def weather_secondary(self) -> str | None:
        """Secondary weather channel, used when the primary is unavailable."""
        return self._store_data.get(CONF_WEATHER_SECONDARY)

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
            self._store_data[CONF_HISTORY_RETENTION_DAYS] = stored.get(
                CONF_HISTORY_RETENTION_DAYS, DEFAULT_HISTORY_RETENTION_DAYS
            )
            self._store_data[CONF_USE_SOIL_MOISTURE] = stored.get(
                CONF_USE_SOIL_MOISTURE, DEFAULT_USE_SOIL_MOISTURE
            )
            # Migrate weather_entity/use_forecast from config entry on first load
            self._store_data[CONF_WEATHER_ENTITY] = stored.get(
                CONF_WEATHER_ENTITY, self.config.get(CONF_WEATHER_ENTITY)
            )
            # Weather channels: primary defaults to the legacy single weather
            # entity so existing installs keep working unchanged.
            self._store_data[CONF_WEATHER_PRIMARY] = stored.get(
                CONF_WEATHER_PRIMARY,
                stored.get(CONF_WEATHER_ENTITY) or self.config.get(CONF_WEATHER_ENTITY),
            )
            self._store_data[CONF_WEATHER_SECONDARY] = stored.get(CONF_WEATHER_SECONDARY)
            self._store_data[CONF_USE_FORECAST] = stored.get(
                CONF_USE_FORECAST, self.config.get(CONF_USE_FORECAST, True)
            )
            LOGGER.info("Loaded persisted data: deficits=%s, zones=%d", self._zone_deficits, len(self.zones))

        # Load the persisted activity log (separate store), pruning anything
        # already past the retention window on the way in.
        events_stored = await self._events_store.async_load()
        if events_stored and events_stored.get("events"):
            self._recent_events = deque(
                events_stored["events"], maxlen=HISTORY_MAX_EVENTS
            )
            self._prune_events()

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

        # Watering start is scheduled dynamically (see _schedule_next_watering):
        # the 23:00 calc computes how long all zones need and back-solves a
        # start time so watering finishes by the target, capped at sunrise−1h
        # and floored at the earliest allowed start. Schedule once now so a
        # restart between 23:00 and the morning run doesn't drop the watering.
        self._schedule_next_watering()

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
        if self._unsub_watering is not None:
            self._unsub_watering()
            self._unsub_watering = None
        if self._watering_task and not self._watering_task.done():
            self._watering_task.cancel()
        # Flush any debounced event save immediately so a restart keeps the log.
        await self._events_store.async_save(self._events_snapshot())
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
            self._zone_daily_temps = {}

        # Read current values via the new resolver chain (zone-local → primary
        # weather attr → secondary weather attr → legacy sensor mapping).
        temp = self._resolve_term("temperature")
        uv = self._resolve_term("uv_index")
        rain = self._resolve_term("rain")

        # Track running min/max — system-wide (used for zones without a local
        # temperature sensor).
        if temp is not None:
            self._daily_tmin = min(self._daily_tmin, temp)
            self._daily_tmax = max(self._daily_tmax, temp)
        if uv is not None:
            self._daily_peak_uv = max(self._daily_peak_uv, uv)

        # Per-zone temperature accumulators for zones with a local temp sensor.
        # Zones without one fall back to the system Tmin/Tmax above.
        for zone in self.zones:
            local_temp_id = (zone.get(CONF_ZONE_LOCAL_SENSORS) or {}).get("temperature")
            if not local_temp_id:
                continue
            zone_temp = self._read_entity(local_temp_id)
            if zone_temp is None:
                continue
            zid = zone[CONF_ZONE_ID]
            zd = self._zone_daily_temps.setdefault(zid, {"tmin": 99.0, "tmax": -99.0})
            zd["tmin"] = min(zd["tmin"], zone_temp)
            zd["tmax"] = max(zd["tmax"], zone_temp)

        # Accumulate rain
        if rain is not None:
            if self._last_rain_value is not None:
                # If sensor gives hourly rate, just add it scaled to 15min
                # If sensor gives cumulative, compute delta
                # Assume hourly rate for OWM-style sensors
                self._daily_rain += rain * 0.25  # 15min = 0.25h
            self._last_rain_value = rain

        # Refresh today's forecast Tmax (used in the live-deficit hybrid).
        await self._refresh_forecast_tmax()

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
                "effective_rain_live": round(
                    self.calculate_effective_rain(self._daily_rain, self.soil_type), 2
                ),
                "last_calc_date": self._last_calc_date,
            },
            "zones": {
                zone[CONF_ZONE_ID]: {
                    "water_deficit": round(
                        self._zone_deficits.get(zone[CONF_ZONE_ID], 0.0), 1
                    ),
                    "water_deficit_live": self._zone_live_deficit(zone),
                    "sun_coefficient": round(sun_coefficients.get(zone[CONF_ZONE_ID], 1.0), 2),
                    "status": self._get_zone_status(zone),
                    "manual_active": zone[CONF_ZONE_ID] in self._manual_active,
                    "manual_started": self._manual_active.get(zone[CONF_ZONE_ID]),
                    "manual_ends": self._manual_ends.get(zone[CONF_ZONE_ID]),
                    "water_used": round(
                        self._zone_water_used.get(zone[CONF_ZONE_ID], 0.0), 1
                    ),
                    "last_watered": self._zone_last_watered.get(zone[CONF_ZONE_ID]),
                    "config": zone,
                }
                for zone in self.zones
            },
            # Cap what the status poll carries — the panel shows a short list;
            # the full retained log lives in the events store on disk.
            "events": list(self._recent_events)[:100],
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
                "next_watering": self._planned_start,
                "next_watering_minutes": round(self._estimate_total_runtime()),
            },
            "sensor_health": self._sensor_health(),
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

    def _read_weather_attr(self, weather_entity: str | None, attr: str) -> float | None:
        """Read a numeric attribute from a weather entity's state.

        For ``uv_index`` (which most weather integrations expose as a sibling
        sensor rather than an entity attribute) we also try the common alias
        names and, as a last resort, a derived ``sensor.{stem}_uv_index``
        following the OWM/Met.no naming convention.
        """
        if not weather_entity:
            return None
        state = self.hass.states.get(weather_entity)
        if state is None or state.state in ("unknown", "unavailable"):
            return None
        val = state.attributes.get(attr)
        if val is None and attr == "uv_index":
            # Some integrations use uvi/uv as the attribute name
            for alias in ("uvi", "uv"):
                val = state.attributes.get(alias)
                if val is not None:
                    break
            if val is None:
                # Last resort: a sibling sensor named after the weather entity
                stem = weather_entity.split(".", 1)[1] if "." in weather_entity else weather_entity
                sibling = self.hass.states.get(f"sensor.{stem}_uv_index")
                if sibling is not None and sibling.state not in ("unknown", "unavailable"):
                    val = sibling.state
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    # Maps our term keys to weather-entity attribute names.
    _WEATHER_ATTR = {
        "temperature": "temperature",
        "humidity": "humidity",
        "wind_speed": "wind_speed",
        "uv_index": "uv_index",
        "pressure": "pressure",
    }
    # Maps term keys to the legacy CONF_SENSOR_* fields, for the bottom of the
    # resolution chain (rain rate, soil moisture, forecast bits without an attr).
    _LEGACY_SENSOR = {
        "temperature": CONF_SENSOR_TEMPERATURE,
        "temperature_min": CONF_SENSOR_TEMPERATURE_MIN,
        "humidity": CONF_SENSOR_HUMIDITY,
        "wind_speed": CONF_SENSOR_WIND_SPEED,
        "uv_index": CONF_SENSOR_UV_INDEX,
        "rain": CONF_SENSOR_RAIN,
        "rain_forecast": CONF_SENSOR_RAIN_FORECAST,
        "soil_moisture": CONF_SENSOR_SOIL_MOISTURE,
    }

    def _resolve_term(
        self,
        term: str,
        zone: dict[str, Any] | None = None,
    ) -> float | None:
        """Resolve a measurement term in priority order.

        1. Zone-local sensor (if a zone is given and has one mapped for ``term``).
        2. Primary weather channel attribute.
        3. Secondary weather channel attribute.
        4. Legacy per-sensor mapping (``sensors`` / ``sensors_fallback``).
        """
        if zone is not None:
            local = (zone.get(CONF_ZONE_LOCAL_SENSORS) or {}).get(term)
            v = self._read_entity(local)
            if v is not None:
                return v
        attr = self._WEATHER_ATTR.get(term)
        if attr:
            v = self._read_weather_attr(self.weather_primary, attr)
            if v is not None:
                return v
            v = self._read_weather_attr(self.weather_secondary, attr)
            if v is not None:
                return v
        legacy = self._LEGACY_SENSOR.get(term)
        if legacy:
            return self._read_sensor(legacy)
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

    # Configured sensor keys + human labels, in the order we want them surfaced.
    _SENSOR_LABELS = (
        (CONF_SENSOR_TEMPERATURE, "Temperature"),
        (CONF_SENSOR_TEMPERATURE_MIN, "Forecast Min (frost)"),
        (CONF_SENSOR_HUMIDITY, "Humidity"),
        (CONF_SENSOR_WIND_SPEED, "Wind speed"),
        (CONF_SENSOR_UV_INDEX, "UV index"),
        (CONF_SENSOR_RAIN, "Rain"),
        (CONF_SENSOR_RAIN_FORECAST, "Rain forecast"),
        (CONF_SENSOR_SOIL_MOISTURE, "Soil moisture"),
    )

    _LOCAL_SENSOR_LABELS = (
        ("temperature", "Temperature"),
        ("humidity", "Humidity"),
        ("soil_moisture", "Soil moisture"),
    )

    def _weather_available(self, weather_entity: str | None) -> bool:
        """True iff the given weather entity exists and is reporting a state."""
        if not weather_entity:
            return False
        state = self.hass.states.get(weather_entity)
        return state is not None and state.state not in ("unknown", "unavailable")

    def _sensor_health(self) -> dict[str, Any]:
        """Snapshot of where each data source stands right now.

        Layout (consumed by the panel banner):

        - ``weather_primary`` / ``weather_secondary``: entity id + availability
        - ``zones``: per-zone local-sensor entity + reading
        - ``legacy``: any sensor still mapped via the old per-key flow that
          isn't currently reporting (for installs not yet migrated)
        - ``issues``: ordered list of {severity, message} for the dashboard
        """
        primary = self.weather_primary
        secondary = self.weather_secondary
        primary_ok = self._weather_available(primary)
        secondary_ok = self._weather_available(secondary)

        zones_health: list[dict[str, Any]] = []
        for zone in self.zones:
            local = zone.get(CONF_ZONE_LOCAL_SENSORS) or {}
            entries = []
            for term, label in self._LOCAL_SENSOR_LABELS:
                entity = local.get(term)
                if not entity:
                    continue
                value = self._read_entity(entity)
                entries.append({
                    "term": term,
                    "label": label,
                    "entity": entity,
                    "value": value,
                    "available": value is not None,
                })
            if entries:
                zones_health.append({
                    "id": zone[CONF_ZONE_ID],
                    "name": zone.get(CONF_ZONE_NAME, zone[CONF_ZONE_ID]),
                    "local": entries,
                })

        # Legacy sensors that still have a mapping but aren't currently fresh.
        legacy_offline: list[dict[str, Any]] = []
        sensors = self._store_data.get("sensors", {})
        sensors_fallback = self._store_data.get("sensors_fallback", {})
        for key, label in self._SENSOR_LABELS:
            p = sensors.get(key) or self.config.get(key)
            f = sensors_fallback.get(key)
            if not p and not f:
                continue
            if self._read_entity(p) is None and self._read_entity(f) is None:
                legacy_offline.append({"key": key, "label": label, "primary": p, "fallback": f})

        issues: list[dict[str, str]] = []
        if primary and secondary and not primary_ok and not secondary_ok:
            issues.append({"severity": "critical", "message": (
                f"Both weather channels offline ({primary} & {secondary}) — values may be stale"
            )})
        elif primary and not primary_ok and secondary_ok:
            issues.append({"severity": "warning", "message": (
                f"Primary weather {primary} offline — using secondary {secondary}"
            )})
        elif primary and not primary_ok and not secondary:
            issues.append({"severity": "critical", "message": (
                f"Weather channel {primary} offline and no secondary configured"
            )})
        elif not primary and not secondary and not legacy_offline:
            issues.append({"severity": "warning", "message": (
                "No weather channel configured — set one in Settings"
            )})
        for zh in zones_health:
            for e in zh["local"]:
                if not e["available"]:
                    issues.append({"severity": "info", "message": (
                        f"Zone {zh['name']}: local {e['label']} ({e['entity']}) offline"
                    )})
        for lo in legacy_offline:
            issues.append({"severity": "info", "message": (
                f"Legacy sensor {lo['label']} offline (consider migrating to a weather channel)"
            )})

        return {
            "weather_primary": {"entity": primary, "available": primary_ok} if primary else None,
            "weather_secondary": {"entity": secondary, "available": secondary_ok} if secondary else None,
            "zones": zones_health,
            "legacy_offline": legacy_offline,
            "issues": issues,
        }

    def _zone_field_capacity(self, zone: dict[str, Any]) -> float:
        """Max plant-available water (mm) for this zone's soil — caps the deficit."""
        zone_soil = zone.get(CONF_ZONE_SOIL_OVERRIDE) or self.soil_type
        soil = SOIL_TYPES.get(zone_soil) or SOIL_TYPES.get("clay", {})
        return float(soil.get("field_capacity", DEFICIT_MAX))

    # ─── Live Deficit Estimate ────────────────────────────────────────────────

    async def _refresh_forecast_tmax(self) -> None:
        """Fetch today's forecast high from the primary (or secondary) weather entity.

        Used in the hybrid live-deficit estimate so morning estimates aren't
        anchored to the still-cool Tmax-so-far.
        """
        for w_entity in (self.weather_primary, self.weather_secondary):
            if not w_entity:
                continue
            try:
                result = await self.hass.services.async_call(
                    "weather", "get_forecasts",
                    {"entity_id": w_entity, "type": "daily"},
                    blocking=True, return_response=True,
                )
            except Exception:  # noqa: BLE001
                continue
            forecasts = ((result or {}).get(w_entity, {}) or {}).get("forecast", [])
            if not forecasts:
                continue
            today_fc = forecasts[0]
            tmax = today_fc.get("temperature") or today_fc.get("native_temperature")
            try:
                self._today_forecast_tmax = float(tmax) if tmax is not None else None
            except (TypeError, ValueError):
                self._today_forecast_tmax = None
            return  # got it from this entity, stop
        # No weather entity worked → keep whatever value we last had

    @staticmethod
    def _et_fraction_of_day() -> float:
        """How much of the day's ET should have happened by now (0..1).

        Sinusoidal half-wave peaking at 13:00 over the active ET window 06:00-20:00.
        Closely matches real ET diurnal profile better than a linear ramp.
        """
        now = datetime.now()
        h = now.hour + now.minute / 60
        if h <= 6:
            return 0.0
        if h >= 20:
            return 1.0
        return (1 - math.cos(math.pi * (h - 6) / 14)) / 2

    def _zone_live_deficit(self, zone: dict[str, Any]) -> float | None:
        """Hybrid live deficit estimate — A primary, B fills in early morning.

        A = ET from running Tmin/Tmax × fraction-of-day elapsed.
        B = ET from running Tmin and forecast Tmax × fraction-of-day elapsed.
        Hybrid: A·f + B·(1−f). At dawn B dominates; by dusk A is everything.
        Once today's 23:00 calc runs, the committed deficit is returned as-is.
        """
        zid = zone[CONF_ZONE_ID]
        committed = self._zone_deficits.get(zid, 0.0)
        # If today's daily calc already ran, the live estimate is just the
        # committed number (no further ET accumulates until tomorrow).
        if self._last_calc_date == date.today().isoformat():
            return committed

        # Per-zone Tmin/Tmax — local accumulator if present, else system.
        zd = self._zone_daily_temps.get(zid)
        if zd and zd["tmin"] < 99 and zd["tmax"] > -99:
            tmin, tmax_a = zd["tmin"], zd["tmax"]
        elif self._daily_tmin < 99 and self._daily_tmax > -99:
            tmin, tmax_a = self._daily_tmin, self._daily_tmax
        else:
            return None  # no temperature data yet → don't show a live number

        f = self._et_fraction_of_day()
        uv = self._daily_peak_uv
        wind = self._resolve_term("wind_speed", zone) or 0.0
        hum = self._resolve_term("humidity", zone) or 50.0
        sun_coeff = self._calculate_sun_coefficient(zone)
        kc = zone.get(CONF_ZONE_CROP_COEFFICIENT, DEFAULT_CROP_COEFFICIENT)

        # A: from what actually happened.
        base_a = self.calculate_et(tmin, tmax_a, uv, wind, hum)
        et_a = base_a * sun_coeff * kc * f

        # B: from forecast Tmax, only if it's hotter than what we've seen.
        tmax_fc = self._today_forecast_tmax
        if tmax_fc is not None and tmax_fc > tmax_a:
            base_b = self.calculate_et(tmin, tmax_fc, uv, wind, hum)
            et_b = base_b * sun_coeff * kc * f
        else:
            et_b = et_a

        # Hybrid: A weight ramps up with f (A primary at dusk, B fills morning).
        live_et = et_a * f + et_b * (1 - f)

        # Wet-soil ET freeze (same rule as the 23:00 calc).
        zmoisture = self._resolve_term("soil_moisture", zone)
        if (
            self.use_soil_moisture
            and zmoisture is not None
            and zmoisture > self.moisture_skip_threshold
        ):
            live_et = 0.0

        zone_soil = zone.get(CONF_ZONE_SOIL_OVERRIDE) or self.soil_type
        eff_rain = self.calculate_effective_rain(self._daily_rain, zone_soil)

        live = committed + live_et - eff_rain
        cap = self._zone_field_capacity(zone)
        return round(max(DEFICIT_MIN, min(cap, live)), 1)

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
        wind = self._resolve_term("wind_speed") or 0.0
        humidity = self._resolve_term("humidity") or 50.0
        rain = self._daily_rain

        if tmin is None or tmax is None:
            LOGGER.warning("Missing temperature data, skipping ET calculation")
            return

        # System-level ET — what the dashboard shows. Per-zone ET below uses
        # the zone's own local-sensor accumulators when configured.
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

        # Update each zone's deficit. Each zone may carry its own local
        # temperature/humidity/soil-moisture sensors; when present the zone's
        # own ET and freeze decision use those instead of the system-wide ones.
        for zone in self.zones:
            zid = zone[CONF_ZONE_ID]
            sun_coeff = self._calculate_sun_coefficient(zone)

            # Per-zone Tmin/Tmax — use the local-sensor accumulator when set,
            # otherwise fall back to the system-wide values.
            zd = self._zone_daily_temps.get(zid)
            if zd and zd["tmin"] < 99 and zd["tmax"] > -99:
                ztmin, ztmax = zd["tmin"], zd["tmax"]
            else:
                ztmin, ztmax = tmin, tmax
            zhumidity = self._resolve_term("humidity", zone) or humidity
            zwind = self._resolve_term("wind_speed", zone) or wind
            zone_base_et = self.calculate_et(ztmin, ztmax, uv, zwind, zhumidity)

            # Per-zone wet-soil ET freeze — uses the zone's own moisture if it
            # has a local sensor; otherwise the system-wide soil sensor.
            zmoisture = self._resolve_term("soil_moisture", zone)
            freeze_et = (
                self.use_soil_moisture
                and zmoisture is not None
                and zmoisture > self.moisture_skip_threshold
            )

            # Per-zone soil type (override or system default)
            zone_soil = zone.get(CONF_ZONE_SOIL_OVERRIDE) or system_soil
            eff_rain = self.calculate_effective_rain(rain, zone_soil)

            kc = zone.get(CONF_ZONE_CROP_COEFFICIENT, DEFAULT_CROP_COEFFICIENT)
            zone_et = 0.0 if freeze_et else zone_base_et * sun_coeff * kc

            # Update deficit — cap at the soil's field capacity so a long skip
            # can't accumulate more debt than the soil could physically lose.
            current = self._zone_deficits.get(zid, 0.0)
            new_deficit = current + zone_et - eff_rain
            cap = self._zone_field_capacity(zone)
            new_deficit = max(DEFICIT_MIN, min(cap, new_deficit))
            self._zone_deficits[zid] = round(new_deficit, 1)

            LOGGER.info(
                "Zone %s: ET=%.2f×%.2f×Kc%.2f=%.2fmm (Tmin=%.1f Tmax=%.1f Hum=%.0f Wind=%.1f%s), EffRain=%.2fmm, Deficit: %.1f→%.1f",
                zid, zone_base_et, sun_coeff, kc, zone_et,
                ztmin, ztmax, zhumidity, zwind,
                " FROZEN(wet)" if freeze_et else "",
                eff_rain, current, new_deficit,
            )

        self._last_calc_date = today_str
        # Now that deficits are current, back-solve tomorrow morning's start so
        # watering finishes by the target time.
        self._schedule_next_watering()
        await self._persist()
        await self.async_request_refresh()

    # ─── Dynamic Start Scheduling ─────────────────────────────────────────────

    def _estimate_zone_runtime(self, zone: dict[str, Any]) -> float:
        """Minutes this zone would run at the next check, or 0 if it wouldn't.

        Mirrors the queue-building + per-zone timing in the watering path so the
        schedule can back-solve a start time. Soil-moisture skips aren't known
        until check time, so this is an upper bound (worst case: start earlier).
        """
        zid = zone[CONF_ZONE_ID]
        deficit = self._zone_deficits.get(zid, 0.0)
        threshold = zone.get(
            CONF_ZONE_DEFICIT_THRESHOLD, self.strategy["deficit_threshold"]
        )
        if deficit <= threshold:
            return 0.0
        max_per_cycle = zone.get(
            CONF_ZONE_MAX_PER_CYCLE,
            self.strategy.get("max_per_cycle", DEFAULT_MAX_PER_CYCLE),
        )
        mm_to_apply = min(deficit, max_per_cycle)
        rate = zone.get(CONF_ZONE_SPRINKLER_RATE, DEFAULT_SPRINKLER_RATE)
        total_minutes = max(1.0, (mm_to_apply / rate) * 30)

        # Cycle & soak adds rest periods between pulses to the wall-clock time.
        if zone.get(CONF_ZONE_CYCLE_SOAK):
            pulse = max(1.0, zone.get(CONF_ZONE_PULSE_MINUTES, DEFAULT_PULSE_MINUTES))
            soak = max(0.0, zone.get(CONF_ZONE_SOAK_MINUTES, DEFAULT_SOAK_MINUTES))
            pulses = math.ceil(total_minutes / pulse)
            total_minutes += max(0, pulses - 1) * soak
        return total_minutes

    def _estimate_total_runtime(self) -> float:
        """Total wall-clock minutes to water every zone that's currently due."""
        return sum(self._estimate_zone_runtime(z) for z in self.zones)

    def _compute_planned_start(self) -> datetime | None:
        """Aware datetime to start the morning run, or None if nothing is due.

        start = max( min(target_finish − total_runtime, sunrise − 1h), earliest )
        """
        total_min = self._estimate_total_runtime()
        if total_min <= 0:
            return None

        now = dt_util.now()
        sunrise = dt_util.as_local(
            get_location_astral_event_next(
                self.hass, SUN_EVENT_SUNRISE, dt_util.utcnow()
            )
        )
        # 07:00, 04:30 and sunrise all belong to the same morning — anchor the
        # window to sunrise's local date so DST/tz stays consistent.
        target_finish = sunrise.replace(
            hour=WATERING_TARGET_FINISH.hour,
            minute=WATERING_TARGET_FINISH.minute,
            second=0,
            microsecond=0,
        )
        earliest = sunrise.replace(
            hour=WATERING_EARLIEST_START.hour,
            minute=WATERING_EARLIEST_START.minute,
            second=0,
            microsecond=0,
        )
        latest = sunrise - timedelta(hours=WATERING_SUNRISE_OFFSET_H)

        target_start = target_finish - timedelta(minutes=total_min)
        planned = max(min(target_start, latest), earliest)

        # If we're computing after the planned moment already passed (e.g. a
        # restart mid-window), don't schedule in the past — run shortly from now.
        if planned <= now:
            planned = now + timedelta(seconds=30)
        return planned

    @callback
    def _schedule_next_watering(self) -> None:
        """(Re)schedule the one-shot morning watering start."""
        if self._unsub_watering is not None:
            self._unsub_watering()
            self._unsub_watering = None

        planned = self._compute_planned_start()
        self._planned_start = planned.isoformat() if planned else None
        if planned is None:
            LOGGER.info("No watering scheduled — no zones above threshold")
            return

        self._unsub_watering = async_track_point_in_time(
            self.hass, self._async_watering_check, planned
        )
        LOGGER.info(
            "Next watering start scheduled for %s (est %.0f min, finish ~%s)",
            planned.strftime("%Y-%m-%d %H:%M"),
            self._estimate_total_runtime(),
            (planned + timedelta(minutes=self._estimate_total_runtime())).strftime("%H:%M"),
        )

    # ─── Watering Check (dynamic start) ───────────────────────────────────────

    @property
    def rain_delay_active(self) -> bool:
        """Whether a rain-delay/vacation pause is currently in effect."""
        if not self._rain_delay_until:
            return False
        return datetime.now() < datetime.fromisoformat(self._rain_delay_until)

    async def _async_watering_check(self, _now: datetime | None = None) -> None:
        """Check if any zones need watering."""
        # The one-shot schedule has now fired; clear its stale state so the
        # dashboard doesn't keep showing a past start time. The next start is
        # recomputed at the 23:00 daily calc.
        self._unsub_watering = None
        self._planned_start = None

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

        # Build watering queue — each candidate zone is skipped individually
        # when its own (or the system fallback) soil moisture is above the
        # threshold, so zones with different local sensors decide independently.
        queue = []
        for zone in self.zones:
            zid = zone[CONF_ZONE_ID]
            deficit = self._zone_deficits.get(zid, 0.0)
            threshold = zone.get(
                CONF_ZONE_DEFICIT_THRESHOLD,
                self.strategy["deficit_threshold"],
            )
            if deficit <= threshold:
                continue
            if self.use_soil_moisture:
                zmoisture = self._resolve_term("soil_moisture", zone)
                if zmoisture is not None and zmoisture > self.moisture_skip_threshold:
                    LOGGER.info(
                        "Zone %s skipped — moisture %.1f%% > %.1f%%",
                        zid, zmoisture, self.moisture_skip_threshold,
                    )
                    self._log_event("skipped", zone_id=zid, reason="soil_moisture")
                    continue
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

    async def async_manual_toggle(
        self,
        zone_id: str,
        turn_on: bool,
        duration_minutes: float | None = None,
    ) -> None:
        """Manually start/stop watering a zone.

        When ``duration_minutes`` is given on turn-on, the run auto-stops after
        that long. Without it, the run is open-ended until the user stops it.
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
            now = datetime.now()
            self._manual_active[zone_id] = now.isoformat()
            if duration_minutes and duration_minutes > 0:
                end = now + timedelta(minutes=duration_minutes)
                self._manual_ends[zone_id] = end.isoformat()
                self._manual_timers[zone_id] = async_call_later(
                    self.hass,
                    duration_minutes * 60,
                    self._manual_timer_done(zone_id),
                )
                LOGGER.info(
                    "Manual watering ON for zone %s (auto-stop in %.1f min)",
                    zone_id, duration_minutes,
                )
            else:
                LOGGER.info("Manual watering ON for zone %s (open-ended)", zone_id)
        else:
            await self._finalize_manual(zone_id)

        await self._persist()
        # async_refresh (not request_refresh) so the panel's follow-up status
        # poll sees the new state instead of the still-debounced previous dict.
        await self.async_refresh()

    def _manual_timer_done(self, zone_id: str):
        """Build the auto-stop callback for async_call_later."""
        async def _fire(_now):
            self._manual_timers.pop(zone_id, None)
            if zone_id not in self._manual_active:
                return  # already stopped by user
            LOGGER.info("Manual watering timer expired for zone %s", zone_id)
            await self._finalize_manual(zone_id)
            await self._persist()
            await self.async_refresh()
        return _fire

    async def _finalize_manual(self, zone_id: str) -> None:
        """Stop a manual run, applying the watered mm to the zone deficit."""
        start_iso = self._manual_active.pop(zone_id, None)
        self._manual_ends.pop(zone_id, None)
        cancel = self._manual_timers.pop(zone_id, None)
        if cancel is not None:
            try:
                cancel()
            except Exception:  # noqa: BLE001
                pass
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
        # Same floor as the auto path: clamp at DEFICIT_MIN, not 0. A flat-zero
        # floor would erase a negative (saturated) deficit on any manual run,
        # even a 0.1 mm sprinkler test — surprising the user. Real saturation
        # from rain stays saturated.
        new_deficit = max(DEFICIT_MIN, current - mm_applied)
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

    def _prune_events(self) -> None:
        """Drop events older than the retention window (oldest are at the right)."""
        cutoff = (
            datetime.now() - timedelta(days=self.history_retention_days)
        ).isoformat()
        while self._recent_events and self._recent_events[-1].get("time", "") < cutoff:
            self._recent_events.pop()

    def _events_snapshot(self) -> dict[str, Any]:
        """Data for the events store (called by async_delay_save)."""
        return {"events": list(self._recent_events)}

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
        last-watered time. Events are persisted to a dedicated store (pruned by
        retention) and also fired on the bus for HA's logbook/recorder.
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
        self._prune_events()
        # Debounced write — several events in one watering run coalesce into a
        # single disk save a few seconds later.
        self._events_store.async_delay_save(self._events_snapshot, 10)
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
        # Retention may have been lowered — apply it to the log right away.
        self._prune_events()
        self._events_store.async_delay_save(self._events_snapshot, 10)
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
            CONF_HISTORY_RETENTION_DAYS: self.history_retention_days,
            CONF_USE_SOIL_MOISTURE: self.use_soil_moisture,
            CONF_WEATHER_ENTITY: self._store_data.get(CONF_WEATHER_ENTITY),
            CONF_WEATHER_PRIMARY: self._store_data.get(CONF_WEATHER_PRIMARY),
            CONF_WEATHER_SECONDARY: self._store_data.get(CONF_WEATHER_SECONDARY),
            CONF_USE_FORECAST: self._store_data.get(CONF_USE_FORECAST, True),
        })
