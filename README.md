# HydroBalance

**ET-based smart irrigation for Home Assistant.** HydroBalance decides *when* and *how
long* to water each zone of your garden by tracking a per-zone **water deficit** that
grows with evapotranspiration (ET) and shrinks with rain and watering — instead of a
dumb fixed schedule.

It models each zone independently: a south-facing bed in full sun dries faster than a
shaded north corner, and sandy soil drains faster than clay. HydroBalance accounts for
all of it and only waters the zones that actually need it.

Everything is configured from a **custom sidebar panel** — no YAML required.

---

## Features

- **ET-based scheduling** — daily evapotranspiration computed from your weather sensors
  (temperature, UV, wind, humidity), clamped to a sane 0–8 mm/day range.
- **Per-zone water deficit** — each zone keeps its own running balance; only zones that
  cross their threshold get watered.
- **Per-zone sun exposure** — manual (full sun / partial / heavy shade) or automatic
  shadow modelling from an obstacle's height, distance and orientation using real solar
  geometry (`astral`).
- **Soil-aware rain absorption** — effective rainfall is computed per soil type (clay /
  loam / sandy) across four intensity bands, so a 1 mm drizzle on clay counts for almost
  nothing while 10 mm on sand soaks in.
- **Smart skips** — frost protection, rain-forecast skip, and a soil-moisture sensor
  override that beats the ET estimate when you have real ground-truth.
- **Sunrise-aware watering** — the daily watering check runs **1 hour before sunrise**,
  the coolest and least windy time, so almost all the water reaches the roots and
  foliage dries off during the day.
- **Manual watering with auto-accounting** — a per-zone toggle starts/stops a sprinkler
  on demand; HydroBalance times the run and subtracts the watered millimetres from that
  zone's deficit (never below 0).
- **Watering strategies** — Balanced, Water Saving, Lush Green, Clay-Safe presets.
- **Full custom panel** — dashboard, zone editor, and settings, all in the HA sidebar.

---

## How it works

### 1. Daily ET (23:00 every night)

```
Tmean = (Tmax + Tmin) / 2
ET = Tmean·0.15 + UV·0.25 + wind_kmh·0.02 − humidity%·0.015      (clamped 0–8 mm)
```

`Tmin`/`Tmax`/peak `UV` are accumulated across the day from your sensors; wind and
humidity are read at calculation time.

### 2. Effective rain (soil-dependent)

Raw rainfall is multiplied by a coefficient that depends on soil type and rain band
(0–2, 2–5, 5–15, >15 mm). Heavy clay rejects light rain as runoff; sand absorbs more.

### 3. Per-zone deficit update

```
zone_ET      = ET × sun_coefficient
new_deficit  = clamp(current_deficit + zone_ET − effective_rain,  −20 … 60 mm)
```

### 4. Watering check (sunrise − 1h)

For each zone, if `deficit > threshold`, the zone is queued. Before watering, the whole
check is skipped if **any** of these is true:

- forecast Tmin < 5 °C (frost protection)
- rain forecast > 5 mm (and "skip on forecast" is enabled)
- measured soil moisture > skip threshold

Then queued zones water sequentially:

```
mm_to_apply      = min(deficit, max_per_cycle)
duration_minutes = max(1, (mm_to_apply / sprinkler_rate) × 30)
```

After a successful run the applied millimetres are subtracted from the deficit.

### 5. Manual watering

Pressing **Manual Water** on a zone turns its switch on and starts a timer. Pressing
**Stop Manual** turns it off and credits the deficit:

```
mm_applied   = (elapsed_minutes / 30) × sprinkler_rate
new_deficit  = max(0, current_deficit − mm_applied)
```

The deficit is clamped at **0** — manual watering never drives it negative. Manual runs
survive a Home Assistant restart: on startup any interrupted run is finalised (elapsed
time counted, switch turned off).

---

## Installation

### HACS (recommended)

1. HACS → **Integrations** → ⋮ → **Custom repositories**.
2. Add `https://github.com/rusulucian85/hydrobalance` as an **Integration**.
3. Search for **HydroBalance**, download, and **restart Home Assistant**.

### Manual

Copy `custom_components/hydrobalance/` into your HA `config/custom_components/`
directory and restart.

---

## Setup

1. **Settings → Devices & Services → Add Integration → HydroBalance.** The config flow
   only asks for a system name — everything else lives in the panel.
2. Open the **HydroBalance** panel from the sidebar.
3. **Settings tab:**
   - Pick your **Weather Entity**, then **Re-discover Sensors** to auto-map temperature,
     humidity, wind, UV, rain and rain-forecast sensors. Adjust any mapping by hand.
   - Optionally set a **Soil Moisture** sensor + skip threshold.
   - Choose **Soil Type** and **Watering Strategy**.
4. **Zones tab:** add a zone per sprinkler — switch entity, sprinkler rate, thresholds,
   and sun exposure.

### Calculating your sprinkler rate

`sprinkler_rate` is in **mm per 30 minutes**. Compute it from your sprinkler's flow and
the area it covers:

```
rate_mm_per_30min = (flow_L_per_hour / area_m2) × 0.5
```

Example: a Gardena OS 140 at ~600 L/h covering ~7 m × ~13 m (≈ 91 m²) → ≈ **3.3 mm/30min**.

---

## The panel

- **Dashboard** — today's ET / rain / temperature / UV, optional soil-moisture card, a
  status card per zone (deficit bar, sun coefficient, threshold), per-zone **Manual
  Water** toggle with live timer, and global actions (Skip Next, Force Water All, Reset
  All Deficits).
- **Zones** — add / edit / delete zones.
- **Settings** — weather source, sensor mapping, soil moisture, soil type & strategy.

---

## Entities

Per system:

| Entity | Description |
|---|---|
| `sensor.*_daily_et` | Daily evapotranspiration (mm) |
| `sensor.*_effective_rain` | Soil-adjusted effective rainfall (mm) |
| `sensor.*_rain_today` | Raw accumulated rainfall (mm) |

Per zone:

| Entity | Description |
|---|---|
| `sensor.<zone>_water_deficit` | Current water deficit (mm) |
| `sensor.<zone>_status` | `ok` / `needs_water` / `watering` |
| `sensor.<zone>_sun_exposure` | Sun coefficient (0–1) |
| `binary_sensor.<zone>_needs_water` | Problem class — on when deficit > threshold |
| `switch.<zone>_sprinkler` | The zone's sprinkler switch |
| `number.<zone>_sprinkler_rate` | Sprinkler rate (mm/30min) |
| `number.<zone>_watering_threshold` | Deficit threshold (mm) |
| `number.<zone>_max_per_cycle` | Max water per cycle (mm) |

---

## Services

| Service | Fields | Description |
|---|---|---|
| `hydrobalance.force_water` | `zone_id?`, `mm_to_apply?` | Water now (a zone, or all) |
| `hydrobalance.skip_day` | — | Skip the next scheduled watering check |
| `hydrobalance.reset_deficit` | `zone_id?` | Reset deficit to 0 (a zone, or all) |

Manual watering is also exposed to the panel over the WebSocket API
(`hydrobalance/manual_water`).

---

## Tuning (`const.py`)

| Constant | Default | Meaning |
|---|---|---|
| `ET_COEFF_TEMP / UV / WIND / HUMIDITY` | 0.15 / 0.25 / 0.02 / 0.015 | ET formula weights |
| `ET_MIN / ET_MAX` | 0 / 8 mm | ET clamp |
| `FROST_TEMP_LIMIT` | 5 °C | Skip watering below this forecast Tmin |
| `RAIN_FORECAST_SKIP` | 5 mm | Skip watering above this forecast rain |
| `DEFICIT_MIN / DEFICIT_MAX` | −20 / 60 mm | Deficit clamp |
| `SOIL_TYPES` | clay / loam / sandy | Per-band rain absorption coefficients |
| `STRATEGIES` | balanced / water_saving / lush_green / clay_safe | Threshold + max-per-cycle presets |

---

## Troubleshooting

- **No watering happens** — expected when every deficit is 0. Deficits build nightly at
  23:00; watering starts automatically once a zone crosses its threshold. Use **Force
  Water** or **Manual Water** to test immediately.
- **ET stays blank** — temperature data is missing. Check the sensor mapping in Settings
  and that the weather integration is providing values.
- **Panel shows an old version after updating** — restart Home Assistant, then fully
  close and reopen the app (the WebView caches the panel JS; the integration appends
  `?v=<version>` to bust it).

---

## Changelog

- **0.4.0** — Per-zone manual watering toggle with live timer; elapsed run-time is
  credited back to the deficit (clamped at 0) and survives restarts.
- **0.3.x** — Weather source & sensor mapping moved into the panel; sunrise−1h watering
  schedule; panel served as a `panel_custom` element; version cache-busting.
- **0.1.0** — Initial release: ET model, per-zone deficits, soil types, sun modelling,
  custom panel.
