"""Pure calculation helpers for HydroBalance.

This module deliberately has **no Home Assistant imports** so the irrigation
maths (ET, effective rainfall, sun exposure) can be unit-tested in isolation.
"""

from __future__ import annotations

import math
from datetime import date, datetime

from .const import (
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


def calculate_et0_hargreaves(
    tmin: float, tmax: float, latitude: float, day_of_year: int
) -> float:
    """Reference evapotranspiration ET0 (mm/day) via Hargreaves–Samani.

    ET0 = 0.0023 × (Tmean + 17.8) × √(Tmax − Tmin) × Ra

    where Ra is extraterrestrial radiation (mm/day equivalent), derived purely
    from latitude and day-of-year. This is the FAO-56 recommended method when
    reliable humidity / wind / solar-radiation data isn't available — it needs
    only temperature (which weather sources report dependably), so it doesn't
    inherit the noise of flaky UV / humidity sensors. Clamped to 0..ET_MAX.

    The temperature range (Tmax − Tmin) acts as a built-in proxy for cloud /
    humidity: overcast, humid days have a small range and therefore lower ET0.
    """
    phi = math.radians(latitude)
    # Inverse relative Earth–Sun distance and solar declination (FAO-56 eq.).
    dr = 1 + 0.033 * math.cos(2 * math.pi / 365 * day_of_year)
    dec = 0.409 * math.sin(2 * math.pi / 365 * day_of_year - 1.39)
    # Sunset hour angle — clamp the acos domain for high latitudes / solstices.
    cos_ws = max(-1.0, min(1.0, -math.tan(phi) * math.tan(dec)))
    ws = math.acos(cos_ws)
    ra = (24 * 60 / math.pi) * 0.0820 * dr * (
        ws * math.sin(phi) * math.sin(dec)
        + math.cos(phi) * math.cos(dec) * math.sin(ws)
    )  # MJ/m²/day
    ra_mm = ra * 0.408  # convert to mm/day equivalent
    trange = max(0.0, tmax - tmin)
    tmean = (tmax + tmin) / 2
    et0 = 0.0023 * (tmean + 17.8) * math.sqrt(trange) * ra_mm
    return max(ET_MIN, min(ET_MAX, round(et0, 2)))


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
