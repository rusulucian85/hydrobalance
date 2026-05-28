"""Pure calculation helpers for HydroBalance.

This module deliberately has **no Home Assistant imports** so the irrigation
maths (ET, effective rainfall, sun exposure) can be unit-tested in isolation.
"""

from __future__ import annotations

import math
from datetime import date, datetime

from .const import (
    ET_COEFF_TEMP,
    ET_COEFF_UV,
    ET_COEFF_WIND,
    ET_COEFF_HUMIDITY,
    ET_MIN,
    ET_MAX,
    SOIL_TYPES,
    SUN_EXPOSURE_MANUAL,
    SUN_ORIENTATION_FALLBACK,
    SOLAR_RADIATION_WEIGHTS,
)

# Direction the shading obstacle sits in, as a compass azimuth, given the
# orientation the zone faces relative to the obstacle.
ORIENTATION_AZIMUTHS = {
    "N": 180,
    "NE": 225,
    "E": 270,
    "SE": 315,
    "S": 0,
    "SW": 45,
    "W": 90,
    "NW": 135,
}


def calculate_et(
    tmin: float, tmax: float, uv: float, wind: float, humidity: float
) -> float:
    """Calculate daily evapotranspiration in mm.

    ET = (Tmean × 0.15) + (UV × 0.25) + (wind_km_h × 0.02) − (humidity% × 0.015)
    Clamped to 0–8 mm/day.
    """
    tmean = (tmax + tmin) / 2
    et = (
        tmean * ET_COEFF_TEMP
        + uv * ET_COEFF_UV
        + wind * ET_COEFF_WIND
        - humidity * ET_COEFF_HUMIDITY
    )
    return max(ET_MIN, min(ET_MAX, round(et, 2)))


def calculate_effective_rain(rain_mm: float, soil_type: str) -> float:
    """Calculate effective precipitation based on soil type.

    Rain bands: 0–2mm, 2–5mm, 5–15mm, >15mm. Each soil type has different
    absorption coefficients per band.
    """
    coefficients = SOIL_TYPES.get(soil_type, SOIL_TYPES["clay"])["coefficients"]

    if rain_mm < 2:
        return round(rain_mm * coefficients[0], 2)
    if rain_mm < 5:
        return round(rain_mm * coefficients[1], 2)
    if rain_mm <= 15:
        return round(rain_mm * coefficients[2], 2)
    return round(rain_mm * coefficients[3], 2)


def manual_sun_coefficient(exposure: str) -> float:
    """Return the sun coefficient for a manual exposure setting."""
    return SUN_EXPOSURE_MANUAL.get(exposure, 1.0)


def orientation_fallback(orientation: str) -> float:
    """Return the fallback sun coefficient when only orientation is known."""
    return SUN_ORIENTATION_FALLBACK.get(orientation, 0.80)


def shadow_coefficient(
    lat: float,
    lon: float,
    day: date,
    orientation: str,
    obstacle_height: float,
    obstacle_distance: float,
) -> float:
    """Sun coefficient from shadow geometry for a given location and date.

    Returns a value in 0–1: the fraction of weighted daily solar radiation that
    reaches the zone (1.0 = never shaded).
    """
    # astral is imported lazily so this module stays importable (and the rest of
    # it testable) in environments where astral is not installed.
    from astral import LocationInfo
    from astral.sun import azimuth, elevation

    obstacle_azimuth = ORIENTATION_AZIMUTHS.get(orientation, 180)
    location = LocationInfo(latitude=lat, longitude=lon)
    shaded_weight = 0.0
    total_weight = 0.0

    for (h_start, h_end), weight in SOLAR_RADIATION_WEIGHTS.items():
        hours_shaded = 0
        hours_total = h_end - h_start

        for h in range(h_start, h_end):
            dt = datetime(day.year, day.month, day.day, h, 30)
            try:
                sun_elev = elevation(location.observer, dt)
                sun_az = azimuth(location.observer, dt)
            except Exception:
                continue

            if sun_elev <= 0:
                continue

            az_diff = abs(sun_az - obstacle_azimuth)
            if az_diff > 180:
                az_diff = 360 - az_diff

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
