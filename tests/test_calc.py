"""Unit tests for the pure irrigation maths in ``calc.py``."""

import pytest

from hb import calc


# ─── ET ────────────────────────────────────────────────────────────────────

def test_calculate_et_known_value():
    # Tmean=23.5 → 3.525 + 2.0 + 0.2 − 0.675 = 5.05
    assert calc.calculate_et(16, 31, 8, 10, 45) == 5.05


def test_calculate_et_clamped_to_max():
    assert calc.calculate_et(30, 40, 12, 30, 10) == 8.0


def test_calculate_et_never_negative():
    assert calc.calculate_et(0, 0, 0, 0, 100) == 0.0


def test_calculate_et_humidity_reduces():
    dry = calc.calculate_et(15, 25, 5, 5, 20)
    humid = calc.calculate_et(15, 25, 5, 5, 90)
    assert humid < dry


# ─── Effective rain ──────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "rain, soil, expected",
    [
        (1.0, "clay", 0.0),    # light rain on clay is fully rejected
        (3.0, "clay", 1.8),    # 3 × 0.60
        (10.0, "clay", 7.0),   # 10 × 0.70
        (20.0, "clay", 11.0),  # 20 × 0.55
        (3.0, "loam", 1.95),   # 3 × 0.65
        (1.0, "sandy", 0.3),   # sand absorbs light rain
    ],
)
def test_effective_rain(rain, soil, expected):
    assert calc.calculate_effective_rain(rain, soil) == expected


def test_effective_rain_unknown_soil_falls_back_to_clay():
    assert calc.calculate_effective_rain(3.0, "nonexistent") == calc.calculate_effective_rain(3.0, "clay")


@pytest.mark.parametrize(
    "rain, band_index",
    [(1.99, 0), (2.0, 1), (4.99, 1), (5.0, 2), (15.0, 2), (15.01, 3)],
)
def test_effective_rain_band_boundaries(rain, band_index):
    coeff = calc.SOIL_TYPES["loam"]["coefficients"][band_index]
    assert calc.calculate_effective_rain(rain, "loam") == round(rain * coeff, 2)


def test_sandy_absorbs_more_than_clay_every_band():
    for rain in (1.0, 3.0, 10.0, 20.0):
        assert calc.calculate_effective_rain(rain, "sandy") >= calc.calculate_effective_rain(rain, "clay")


# ─── Sun coefficient ─────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "exposure, expected",
    [("full_sun", 1.0), ("partial_shade", 0.7), ("heavy_shade", 0.45), ("???", 1.0)],
)
def test_manual_sun_coefficient(exposure, expected):
    assert calc.manual_sun_coefficient(exposure) == expected


@pytest.mark.parametrize(
    "orientation, expected",
    [("N", 0.60), ("S", 0.95), ("E", 0.80), ("???", 0.80)],
)
def test_orientation_fallback(orientation, expected):
    assert calc.orientation_fallback(orientation) == expected


def test_shadow_coefficient_in_range():
    pytest.importorskip("astral")
    from datetime import date

    val = calc.shadow_coefficient(45.0, 25.0, date(2026, 6, 21), "N", 8.0, 2.0)
    assert 0.0 <= val <= 1.0


def test_shadow_coefficient_taller_obstacle_shades_more():
    pytest.importorskip("astral")
    from datetime import date

    day = date(2026, 12, 21)  # low winter sun → long shadows
    short = calc.shadow_coefficient(45.0, 25.0, day, "S", 1.0, 5.0)
    tall = calc.shadow_coefficient(45.0, 25.0, day, "S", 20.0, 5.0)
    assert tall <= short
