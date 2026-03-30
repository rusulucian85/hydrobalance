"""Constants for HydroBalance integration."""

from __future__ import annotations

import logging

DOMAIN = "hydrobalance"
LOGGER = logging.getLogger(__package__)

PLATFORMS = ["sensor", "binary_sensor", "switch", "number"]

# ─── Storage ──────────────────────────────────────────────────────────────────

STORAGE_VERSION = 1
STORAGE_KEY_PREFIX = "hydrobalance"

# ─── ET Formula Constants ─────────────────────────────────────────────────────

ET_COEFF_TEMP = 0.15
ET_COEFF_UV = 0.25
ET_COEFF_WIND = 0.02
ET_COEFF_HUMIDITY = 0.015
ET_MIN = 0.0
ET_MAX = 8.0

# ─── Defaults ─────────────────────────────────────────────────────────────────

DEFAULT_SPRINKLER_RATE = 2.0  # mm per 30 min
DEFAULT_DEFICIT_THRESHOLD = 12.0  # mm
DEFAULT_MAX_PER_CYCLE = 5.0  # mm
FROST_TEMP_LIMIT = 5.0  # °C
RAIN_FORECAST_SKIP = 5.0  # mm
DEFICIT_MIN = -20.0
DEFICIT_MAX = 60.0

# ─── Soil Types ───────────────────────────────────────────────────────────────
# Effective precipitation coefficients per rain band: (0-2mm, 2-5mm, 5-15mm, >15mm)

SOIL_TYPES = {
    "clay": {
        "name": "Clay / Heavy Soil",
        "coefficients": (0.00, 0.60, 0.70, 0.55),
    },
    "loam": {
        "name": "Loam",
        "coefficients": (0.15, 0.65, 0.75, 0.60),
    },
    "sandy": {
        "name": "Sandy",
        "coefficients": (0.30, 0.75, 0.85, 0.65),
    },
}

# ─── Watering Strategies ──────────────────────────────────────────────────────

STRATEGIES = {
    "balanced": {
        "name": "Balanced",
        "deficit_threshold": 12.0,
        "max_per_cycle": 5.0,
    },
    "water_saving": {
        "name": "Water Saving",
        "deficit_threshold": 16.0,
        "max_per_cycle": 4.0,
    },
    "lush_green": {
        "name": "Lush Green",
        "deficit_threshold": 8.0,
        "max_per_cycle": 6.0,
    },
    "clay_safe": {
        "name": "Clay-Safe",
        "deficit_threshold": 14.0,
        "max_per_cycle": 3.0,
    },
}

# ─── Sun Exposure ─────────────────────────────────────────────────────────────

SUN_EXPOSURE_MANUAL = {
    "full_sun": 1.0,
    "partial_shade": 0.7,
    "heavy_shade": 0.45,
}

# Fallback coefficients when orientation is set but no obstacle dimensions
SUN_ORIENTATION_FALLBACK = {
    "N": 0.60,
    "NE": 0.70,
    "E": 0.80,
    "SE": 0.90,
    "S": 0.95,
    "SW": 0.90,
    "W": 0.80,
    "NW": 0.70,
}

# Solar radiation distribution by hour range (fraction of daily total)
SOLAR_RADIATION_WEIGHTS = {
    (6, 9): 0.15,
    (9, 12): 0.30,
    (12, 15): 0.35,
    (15, 18): 0.20,
}

# ─── Config Keys ──────────────────────────────────────────────────────────────

CONF_SYSTEM_NAME = "system_name"
CONF_WEATHER_ENTITY = "weather_entity"

CONF_SENSOR_TEMPERATURE = "sensor_temperature"
CONF_SENSOR_TEMPERATURE_MIN = "sensor_temperature_min"
CONF_SENSOR_TEMPERATURE_MAX = "sensor_temperature_max"
CONF_SENSOR_HUMIDITY = "sensor_humidity"
CONF_SENSOR_WIND_SPEED = "sensor_wind_speed"
CONF_SENSOR_UV_INDEX = "sensor_uv_index"
CONF_SENSOR_RAIN = "sensor_rain"
CONF_SENSOR_RAIN_FORECAST = "sensor_rain_forecast"
CONF_SOIL_TYPE = "soil_type"
CONF_STRATEGY = "strategy"
CONF_USE_FORECAST = "use_forecast"
CONF_ZONES = "zones"

# Zone config keys
CONF_ZONE_ID = "id"
CONF_ZONE_NAME = "name"
CONF_ZONE_SWITCH = "switch_entity"
CONF_ZONE_SPRINKLER_RATE = "sprinkler_rate"
CONF_ZONE_MAX_PER_CYCLE = "max_per_cycle"
CONF_ZONE_DEFICIT_THRESHOLD = "deficit_threshold"
CONF_ZONE_SUN_EXPOSURE_MODE = "sun_exposure_mode"
CONF_ZONE_SUN_EXPOSURE = "sun_exposure"
CONF_ZONE_ORIENTATION = "orientation"
CONF_ZONE_OBSTACLE_HEIGHT = "obstacle_height"
CONF_ZONE_OBSTACLE_DISTANCE = "obstacle_distance"
CONF_ZONE_SOIL_OVERRIDE = "soil_override"
