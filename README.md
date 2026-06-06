# HydroBalance

**ET-based smart irrigation for Home Assistant.**

HydroBalance waters your garden the way a careful gardener would: it estimates how much
water the soil *loses* each day to evaporation and plant transpiration, subtracts
whatever rain actually soaked in, and tops up only the zones that have run dry — at the
time of day when the least water is wasted. No fixed schedules, no overwatering after a
storm, no parched beds during a heatwave.

Every zone is modelled independently. A south-facing bed in full sun on sandy soil dries
far faster than a shaded north corner on clay, and HydroBalance tracks each one with its
own running water balance.

Everything is configured from a **custom sidebar panel** — no YAML required.

---

## Table of contents

1. [The core idea: the water deficit](#1-the-core-idea-the-water-deficit)
2. [Evapotranspiration (ET) — the loss model](#2-evapotranspiration-et--the-loss-model)
3. [Sensors — what HydroBalance reads and why](#3-sensors--what-hydrobalance-reads-and-why)
4. [Weather source & sensor discovery](#4-weather-source--sensor-discovery)
5. [Soil types & effective rainfall](#5-soil-types--effective-rainfall)
6. [Sun exposure & crop coefficient — the per-zone multipliers](#6-sun-exposure--crop-coefficient--the-per-zone-multipliers)
7. [The daily cycle — putting it together](#7-the-daily-cycle--putting-it-together)
8. [Watering: schedule, skips, duration](#8-watering-schedule-skips-duration)
9. [Manual watering](#9-manual-watering)
10. [Watering strategies](#10-watering-strategies)
11. [Sprinkler rate — how to measure yours](#11-sprinkler-rate--how-to-measure-yours)
12. [Worked example](#12-worked-example)
13. [Installation & setup](#13-installation--setup)
14. [The panel](#14-the-panel)
15. [Entities](#15-entities)
16. [Services & WebSocket API](#16-services--websocket-api)
17. [Constants reference](#17-constants-reference)
18. [Troubleshooting](#18-troubleshooting)
19. [Changelog](#19-changelog)

---

## 1. The core idea: the water deficit

Each zone holds a single number: its **water deficit**, in millimetres. Think of it as
"how many mm of water the soil is short of ideal right now."

- Every night the deficit **grows** by the day's water loss (ET, adjusted for how sunny
  the zone is).
- Rain and watering **shrink** it.
- When the deficit climbs above a **threshold** (default 12 mm), the zone is watered.
- Watering applies up to `max_per_cycle` mm and subtracts that from the deficit.

```
            +ET·sun                         −effective_rain
deficit ───────────────►  grows each night  ◄─────────────── rain that soaked in
            −watering (auto or manual)       ◄────────────── sprinkler output
```

The deficit is clamped on the dry side at the soil's **field capacity** — the most
plant-available water that soil can actually hold (clay 30 mm, loam 20 mm, sandy 12 mm;
see §5). A long dry spell or a multi-day skip therefore can't invent more "debt" than the
soil could physically have lost, which prevents a giant catch-up overwater when watering
resumes. The wet side is floored at **−20 mm**. (Manual watering uses a tighter floor of
**0** — see §9.)

**1 mm of water = 1 litre per square metre.** All quantities in HydroBalance — ET, rain,
deficit, sprinkler output — are in mm, which keeps the maths consistent regardless of
zone size.

---

## 2. Evapotranspiration (ET) — the loss model

**Evapotranspiration** is the sum of two losses: water evaporating from the soil surface,
and water transpired by plants through their leaves. It's the "demand" side of the water
balance. Hot, sunny, windy, dry days have high ET; cool, cloudy, calm, humid days have
low ET.

A full reference model (FAO-56 Penman-Monteith) needs solar radiation sensors most home
setups don't have. HydroBalance uses a lightweight linear approximation driven by the
sensors a typical weather integration already exposes:

```
Tmean = (Tmax + Tmin) / 2

ET = Tmean × 0.15        ← warmth drives evaporation
   + UV    × 0.25        ← sunlight is the energy source for evaporation
   + Wind  × 0.02        ← wind carries moisture away from leaves/soil
   − Hum%  × 0.015       ← humid air slows evaporation

ET is then clamped to 0 … 8 mm/day and rounded to 2 decimals.
```

| Term | Coefficient | Unit of input | Why it's in the model |
|---|---|---|---|
| Mean temperature | `0.15` (`ET_COEFF_TEMP`) | °C | Warmer air holds and pulls more moisture |
| Peak UV index | `0.25` (`ET_COEFF_UV`) | UV index | Proxy for solar energy — the dominant ET driver |
| Wind speed | `0.02` (`ET_COEFF_WIND`) | km/h | Moving air removes the saturated boundary layer |
| Relative humidity | `−0.015` (`ET_COEFF_HUMIDITY`) | % | High humidity suppresses evaporation (negative) |

`Tmean` uses the day's **min and max** temperature (accumulated across the day from the
temperature sensor), so a day that swings from 12 °C to 30 °C is treated differently from
a flat 21 °C day even though the average is the same.

**Clamp (`ET_MIN`=0, `ET_MAX`=8):** ET can never be negative (the model can't "add" water
through the ET term), and is capped at 8 mm/day — a realistic ceiling for a hot summer day
in a temperate climate, which guards against a spurious sensor spike blowing out the
deficit.

> These coefficients are deliberately simple and tunable in `const.py`. They are an
> *estimate*; the soil-moisture sensor override (§3) is the recommended way to keep the
> system honest against reality.

---

## 3. Sensors — what HydroBalance reads and why

HydroBalance reads plain Home Assistant sensor entities. You map them in the panel
(Settings → Weather Sensors). Each is read either continuously (every 15 min) or at a
specific moment.

| Sensor | Config key | Unit | When read | Used for | If missing |
|---|---|---|---|---|---|
| **Temperature** | `sensor_temperature` | °C | Every 15 min | Builds the day's Tmin/Tmax for ET | ET can't run that day |
| **Forecast Min** | `sensor_temperature_min` | °C | At watering check | **Frost protection** | No frost skip |
| **Humidity** | `sensor_humidity` | % | At 23:00 calc | ET humidity term | Defaults to 50% |
| **Wind Speed** | `sensor_wind_speed` | km/h | At 23:00 calc | ET wind term | Defaults to 0 |
| **UV Index** | `sensor_uv_index` | index | Every 15 min (peak) | ET UV term | Treated as 0 |
| **Rain** | `sensor_rain` | mm/h (rate) | Every 15 min | Accumulated to daily rainfall | No rain credit |
| **Rain Forecast** | `sensor_rain_forecast` | mm (next 24 h) | At watering check | **Skip if rain coming** | No forecast skip |
| **Soil Moisture** *(optional)* | `sensor_soil_moisture` | % VWC | At watering check | **Override skip** | ET estimate used alone |

### How each is processed

- **Temperature** is sampled every 15 minutes; HydroBalance keeps the running **minimum**
  and **maximum** for the day. Those become `Tmin`/`Tmax` in the ET formula. At local
  midnight the accumulators reset.
- **UV index** is sampled every 15 minutes and the **peak** value of the day is kept —
  the midday maximum best represents the solar energy available for evaporation.
- **Rain** is read as an **hourly rate** (mm/h, OpenWeatherMap-style). Each 15-minute
  tick adds `rain × 0.25` mm to the day's running total (¼ hour). At midnight it resets.
- **Forecast Min** is the *forecast* overnight low. If it's below `FROST_TEMP_LIMIT`
  (5 °C) the whole watering check is skipped — watering in freezing conditions can damage
  plants and pipes.
- **Rain Forecast** is expected to be a "precipitation next 24 h" sensor (mm). If it's
  above `RAIN_FORECAST_SKIP` (5 mm) and the forecast skip is enabled, watering is skipped
  — no point watering when meaningful rain is coming.
- **Soil Moisture** (% volumetric water content) is the reality check. When the
  soil-moisture mode is on (default) and the measured moisture is above your skip threshold
  (default 40%), two things happen: the nightly calc **freezes ET** so a wet soil stops
  accruing fake debt (only rain adjusts the deficit), and the pre-dawn watering run is
  skipped. **A real sensor beats the model.**

> **Why two temperature sensors?** The plain *Temperature* sensor is the live reading used
> to build today's actual Tmin/Tmax for ET. The *Forecast Min* is a forward-looking
> overnight low used purely for the frost decision before the pre-dawn watering run.

### Two "flip switches": real sensors vs. forecast, and sensor vs. model

HydroBalance is built to run **with or without** local sensors, and it degrades gracefully
when one drops out. Two independent switches control this:

1. **Per-sensor fallback (real → forecast).** Each weather term has a **Primary** field
   (your real local sensor) and an optional **Fallback** field (e.g. a weather-forecast
   entity). The primary is used whenever it's available; the fallback fills in *only* when
   the primary is `unknown`/`unavailable`, so a sensor going offline never silently drops a
   term from the ET calculation. Point Primary at your own temperature/humidity sensor to
   make ET reflect *your* garden instead of a regional forecast.
2. **Soil-moisture mode (sensor ⇄ model).** The *Use soil-moisture sensor* toggle decides
   whether the measured moisture steers things at all. **On:** the sensor overrides the
   model (freeze ET when wet, skip when wet) — the reality check above. **Off:** the system
   runs purely on the ET deficit model and ignores moisture entirely. Either way, if the
   sensor is unavailable it automatically falls back to ET-only for that run.

---

## 4. Weather source & sensor discovery

You pick a single **weather entity** (e.g. `weather.openweathermap`) as the source. The
panel's **Re-discover Sensors** button then inspects every `sensor.*` entity that belongs
to the *same integration* as that weather entity and auto-maps them by device class and
name heuristics:

- **Temperature** → first `temperature` device-class sensor, *excluding* names containing
  `forecast`, `min`, `max`, `dew`, `feels`, or `apparent` (so it doesn't grab the dew
  point or "feels like").
- **Forecast Min** → a `temperature` sensor whose name contains `min`.
- **Humidity** → first `humidity` device-class sensor.
- **Wind Speed** → name contains `wind` and (`speed` or a km/h or m/s unit).
- **UV Index** → name contains `uv`.
- **Rain** → name contains `rain` or device class `precipitation`, *not* `forecast`.
- **Rain Forecast** → name contains `precipitation`/`rain` *and* `forecast` or `24`.

Discovery **merges** over your existing mapping — it only fills fields it finds and never
wipes a manually set sensor (e.g. your soil-moisture sensor, which discovery doesn't
touch). Anything it gets wrong, you fix by typing the entity directly into the field.

ET is always calculated from the mapped **sensors**, not from the weather entity's own
attributes — sensors are more reliable and update more predictably.

---

## 5. Soil types & effective rainfall

Not all rain reaches the root zone. Light rain on baked clay mostly runs off or
evaporates; the same rain on sand soaks straight in. **Effective rainfall** is the
fraction of raw rainfall that actually counts against the deficit.

HydroBalance splits rainfall into four **intensity bands** and applies a per-soil
absorption coefficient to each:

| Rain band | Clay / Heavy | Loam | Sandy |
|---|---|---|---|
| **0–2 mm** (light) | `0.00` | `0.15` | `0.30` |
| **2–5 mm** (moderate) | `0.60` | `0.65` | `0.75` |
| **5–15 mm** (steady) | `0.70` | `0.75` | `0.85` |
| **> 15 mm** (heavy) | `0.55` | `0.60` | `0.65` |

```
effective_rain = raw_rain × coefficient[band(raw_rain)]
```

**Reading the table:**

- **Clay rejects light rain entirely** (`0.00` for 0–2 mm): a 1 mm drizzle beads up and
  evaporates before it penetrates heavy soil.
- **Sand always absorbs the most** in every band — it has large pores and drains fast.
- **The > 15 mm coefficients drop** for every soil because in a heavy downpour a chunk of
  the water runs off or drains past the root zone instead of being stored where roots can
  use it.
- **The 5–15 mm "steady soak" band is the most efficient** for all soils — long enough to
  penetrate, gentle enough to avoid runoff.

### Soil type explained

| Soil | Character | Water behaviour | Field capacity | Best HydroBalance fit |
|---|---|---|---|---|
| **Clay / Heavy** | Fine particles, sticky when wet, cracks when dry | Holds a lot of water but absorbs slowly; prone to runoff and waterlogging | **30 mm** | Low max-per-cycle, longer intervals (Clay-Safe strategy) |
| **Loam** | Balanced sand/silt/clay mix — the "ideal" garden soil | Good absorption *and* retention | **20 mm** | Balanced strategy |
| **Sandy** | Coarse particles, gritty | Absorbs fast, drains fast, dries out quickly | **12 mm** | Smaller, more frequent watering |

The **field capacity** is the most plant-available water each soil can hold, and it caps
how large a zone's deficit can grow (§1). Sandy soil holds little, so it tops out at 12 mm
of debt; clay can bank up to 30 mm. This is why a long skip on sandy soil won't trigger the
same multi-day catch-up that the old flat 60 mm cap allowed.

The system has one default soil type, but **each zone can override it** (zone editor →
Soil Override) if part of your garden differs — the override changes both its rain
absorption *and* its deficit cap.

---

## 6. Sun exposure & crop coefficient — the per-zone multipliers

Two beds with identical soil dry at different rates if one is shaded, or if one is planted
with thirsty vegetables and the other with drought-tolerant natives. HydroBalance scales
each zone's ET by two independent multipliers:

```
zone_ET = ET × sun_coefficient × crop_coefficient (Kc)
```

### Sun coefficient

A coefficient of `1.0` means full sun (full ET); `0.45` means a heavily shaded spot loses
less than half as much water. There are two modes.

### Manual mode

Pick one of three presets:

| Setting | Coefficient | Use for |
|---|---|---|
| Full Sun | `1.00` | Open lawn, unshaded beds |
| Partial Shade | `0.70` | Dappled light, half-day sun |
| Heavy Shade | `0.45` | North side of a wall, under dense trees |

### Auto mode (orientation + shadow geometry)

You describe the obstacle that shades the zone — its **orientation** relative to the zone,
its **height**, and its **distance** — and HydroBalance computes the coefficient from the
real path of the sun using `astral`.

**If you give only an orientation** (no height/distance), it uses a fallback table:

| Orientation | N | NE | E | SE | S | SW | W | NW |
|---|---|---|---|---|---|---|---|---|
| Coefficient | 0.60 | 0.70 | 0.80 | 0.90 | 0.95 | 0.90 | 0.80 | 0.70 |

(North-facing zones get the least sun in the northern hemisphere; south-facing the most.)

**If you give height and distance**, it runs a full shadow calculation:

1. The day is divided into four solar windows, each weighted by how much of the day's
   radiation it carries:

   | Window | 06–09 | 09–12 | 12–15 | 15–18 |
   |---|---|---|---|---|
   | Weight | 0.15 | 0.30 | 0.35 | 0.20 |

2. For each hour, the sun's **elevation** and **azimuth** are computed for your latitude/
   longitude. Hours when the sun is below the horizon are ignored.
3. The obstacle shades the zone in a given hour when **both**:
   - the sun is roughly *behind* the obstacle (azimuth within 60° of the obstacle's
     direction), and
   - the cast shadow is long enough to reach the zone:
     `shadow_length = height / tan(elevation) > distance`.
4. The shaded fraction of each window is weighted and summed:
   `sun_coefficient = 1 − (shaded_weighted / total_weighted)`.

This means a low winter sun (long shadows) shades a zone more than the same obstacle does
under a high summer sun — the coefficient is recomputed against the current date.

### Crop coefficient (Kc)

Where the sun coefficient captures *how much sun* a zone gets, the **crop coefficient**
captures *how thirsty its planting is* relative to a reference lawn. It's the standard
agronomic Kc factor, applied as a straight multiplier on the zone's ET.

| Kc | Planting |
|---|---|
| `0.4` | Drought-tolerant / native / xeriscape |
| `0.6` | Shrubs, mixed ornamental beds |
| `0.8` | Cool-season turf (lower demand) |
| `1.0` | Reference / standard lawn (default) |
| `1.1` | Vegetable garden |
| `1.2` | High-demand or dense crop |

Set it per zone in the zone editor. The default `1.0` leaves ET unchanged, so existing
zones behave exactly as before unless you tune it.

---

## 7. The daily cycle — putting it together

```
┌─ every 15 min ──────────────────────────────────────────────┐
│ read sensors → update day's Tmin/Tmax, peak UV, rain total   │
│ reset accumulators at local midnight                         │
└──────────────────────────────────────────────────────────────┘

┌─ 23:00 nightly — daily calculation ─────────────────────────┐
│ ET            = f(Tmin, Tmax, peakUV, wind, humidity)        │
│ for each zone:                                               │
│   zone_ET     = ET × sun_coefficient(zone) × Kc(zone)        │
│                 (zone_ET = 0 when soil-moisture mode says wet)│
│   eff_rain    = effective_rain(day_rain, zone_soil)          │
│   deficit    += zone_ET − eff_rain  (clamp −20…field_cap)    │
└──────────────────────────────────────────────────────────────┘

┌─ sunrise − 1h — watering check ─────────────────────────────┐
│ skip if: skip-next flag / already watering / frost /         │
│          rain forecast / soil moisture high                  │
│ queue zones where deficit > threshold, water them in turn    │
└──────────────────────────────────────────────────────────────┘
```

Per-zone deficit update at 23:00:

```
zone_ET     = ET × sun_coefficient × crop_coefficient   (0 if soil is wet & sensor mode on)
eff_rain    = effective_rain(daily_rain, zone_soil_override or system_soil)
new_deficit = clamp(current_deficit + zone_ET − eff_rain,  −20 … field_capacity(zone_soil))
```

---

## 8. Watering: schedule, skips, duration

### When

The watering check runs **1 hour before sunrise** (computed from your HA location). This
is the coldest, calmest part of the day, so evaporation loss is minimal and foliage dries
as the sun comes up — which discourages fungal disease.

### Skip conditions (checked in order, any one aborts the run)

1. **System disabled:** the master *Automatic Watering* switch is off.
2. **Rain delay / vacation:** an active multi-day pause (see below).
3. **Skip-next flag** set (via the panel or `skip_day` service) — consumed once.
4. **Watering already in progress.**
5. **Frost:** forecast Tmin < `FROST_TEMP_LIMIT` (5 °C).
6. **Rain forecast:** forecast > `RAIN_FORECAST_SKIP` (5 mm) *and* forecast-skip enabled.
7. **Soil moisture:** *(only when soil-moisture mode is on)* measured moisture > skip
   threshold (default 40% VWC).

Each weather/system skip (everything except the re-entrancy guard #4) fires a
`hydrobalance_event` with its reason (see §16) so you can surface it in the logbook or a
notification. Manual and forced watering deliberately **bypass** the master switch and
rain delay — they're explicit overrides.

### System control: enable & rain delay

- **Automatic Watering switch** (`switch.*_automatic_watering`) — turn it off to suspend
  the whole schedule indefinitely. Deficits keep accruing; nothing waters automatically.
- **Rain delay / vacation** — pause automatic watering for a set number of days. The
  panel offers *Rain Delay 3d*, *Vacation 7d*, and *Clear Delay*; the `set_rain_delay`
  WebSocket command takes any day count (0 clears). When the window elapses the schedule
  resumes on its own.

### Which zones, and for how long

A zone is queued when `deficit > threshold`. Zones water **sequentially** (one switch at a
time). For each:

```
mm_to_apply      = min(deficit, max_per_cycle)
duration_minutes = max(1, (mm_to_apply / sprinkler_rate) × 30)
```

`sprinkler_rate` is in **mm per 30 min**, so dividing the target mm by it and multiplying
by 30 gives minutes. After the run, `deficit −= mm_to_apply` (floored at −20).

The `max_per_cycle` cap prevents dumping a huge deficit all at once — especially important
on clay, where applying more than the soil can absorb just runs off.

### Cycle & soak

Optional per zone. Instead of one continuous run, the target is split into **pulses** of
`pulse_minutes` separated by `soak_minutes` rests with the switch off, letting water
absorb instead of running off — ideal for clay and slopes.

```
pulse → soak → pulse → soak → … until the full duration is delivered
```

The deficit is credited **per pulse**, so if a run is cancelled (e.g. HA restart, manual
stop) only the undelivered remainder is forfeited — water already applied still counts.
Off by default (a single pulse equals the old behaviour).

---

## 9. Manual watering

Each zone on the dashboard has a **Manual Water** toggle for on-demand watering:

- **Press it** → a small modal asks for the run length: pick a preset
  (5 / 10 / 15 / 30 / 45 / 60 min), type a custom number of minutes, or choose
  *Until I stop* for an open-ended run. The zone's switch turns on and a live
  countdown (mm:ss) starts — counting **down** to the auto-stop for a timed run,
  or **up** for an open-ended one.
- **Auto-stop** — when the timer expires, HydroBalance turns the switch off and
  credits the elapsed time to the deficit just like a manual stop.
- **Press Stop Manual** before the timer ends to stop early — the run is
  accounted for:

```
mm_applied  = (elapsed_minutes / 30) × sprinkler_rate
new_deficit = max(0, current_deficit − mm_applied)
```

The deficit floor here is **0** (not −20): manual watering credits the soil but never
drives the balance negative, so a long manual session doesn't suppress automatic watering
for days afterwards.

**Restart-safe:** if Home Assistant restarts mid-run, on startup HydroBalance finalises
the interrupted run — it counts the elapsed time up to that point, credits the deficit,
and turns the switch off (the safety check also force-closes any zone switch left on).

---

## 10. Watering strategies

A strategy is a preset pair of *threshold* (how dry before watering) and *max-per-cycle*
(how much per run). It sets system defaults; any zone can override both.

| Strategy | Threshold | Max/cycle | Character |
|---|---|---|---|
| **Balanced** | 12 mm | 5 mm | Sensible default for most gardens |
| **Water Saving** | 16 mm | 4 mm | Waters later and lighter — drought-tolerant lawns |
| **Lush Green** | 8 mm | 6 mm | Waters early and generously — keeps grass vivid |
| **Clay-Safe** | 14 mm | 3 mm | Small doses so heavy soil absorbs without runoff |

---

## 11. Sprinkler rate — how to measure yours

`sprinkler_rate` is the single most important number for correct run times. It is the
**depth of water (mm) your sprinkler lays down in 30 minutes** over the area it covers.

### From flow and area (quick estimate)

```
rate_mm_per_30min = (flow_L_per_hour / area_m²) × 0.5
```

Example — Gardena OS 140 oscillating sprinkler at ~600 L/h covering ~7 m × ~13 m (≈ 91 m²):

```
(600 / 91) × 0.5 ≈ 3.3 mm/30min
```

### By measurement (most accurate — "catch-cup test")

Place several straight-sided containers across the zone, run the sprinkler for 30 minutes,
measure the average water depth in mm. That depth **is** your `sprinkler_rate`. This
captures real coverage and uniformity better than the flow estimate.

Set the value per zone in the zone editor, or with the `number.<zone>_sprinkler_rate`
entity.

---

## 12. Worked example

A south-facing **loam** lawn zone, full sun (`sun_coefficient = 1.0`), Balanced strategy
(threshold 12 mm), sprinkler rate 3.3 mm/30min, max-per-cycle 5 mm.

**A hot dry day:** Tmin 16 °C, Tmax 31 °C, peak UV 8, wind 10 km/h, humidity 45%, no rain.

```
Tmean = (31 + 16) / 2 = 23.5
ET    = 23.5×0.15 + 8×0.25 + 10×0.02 − 45×0.015
      = 3.525 + 2.0 + 0.2 − 0.675
      = 5.05 mm
zone_ET = 5.05 × 1.0 = 5.05 mm
deficit: 0 → 5.05 mm   (below threshold, no watering)
```

**A second similar day:** deficit `5.05 → ~10.1 mm` (still below 12).

**A third day, plus 3 mm of rain overnight:**

```
eff_rain (loam, 2–5 mm band) = 3 × 0.65 = 1.95 mm
deficit: 10.1 + 5.05 − 1.95 = 13.2 mm   → above 12 mm threshold
```

At the next sunrise−1h check the zone is queued:

```
mm_to_apply = min(13.2, 5) = 5 mm
duration    = (5 / 3.3) × 30 ≈ 45 min
deficit after watering: 13.2 − 5 = 8.2 mm
```

The remaining 8.2 mm carries over and will be topped up on subsequent nights as the
deficit climbs again.

---

## 13. Installation & setup

### Install via HACS (recommended)

1. HACS → **Integrations** → ⋮ → **Custom repositories**.
2. Add `https://github.com/rusulucian85/hydrobalance` as an **Integration**.
3. Search **HydroBalance**, download, and **restart Home Assistant**.

### Manual install

Copy `custom_components/hydrobalance/` into your HA `config/custom_components/` and
restart.

### First-time setup

1. **Settings → Devices & Services → Add Integration → HydroBalance.** The config flow
   only asks for a system name; everything else is in the panel.
2. Open the **HydroBalance** panel from the sidebar.
3. **Settings tab:**
   - Choose your **Weather Entity**, then **Re-discover Sensors**; correct any mapping.
   - Optionally set a **Soil Moisture** sensor and skip threshold.
   - Pick **Soil Type** and **Watering Strategy**.
4. **Zones tab:** add one zone per sprinkler — switch entity, sprinkler rate, thresholds,
   and sun exposure.

---

## 14. The panel

The custom panel is served as a `panel_custom` element (it runs inside the authenticated
HA frontend, so it works in the iOS/Android app too). The JS is cache-busted by version.

- **Dashboard** — today's ET / rain / effective rain / Tmin / Tmax / peak UV; an optional
  soil-moisture card; a status card per zone (deficit bar, sun coefficient, threshold,
  water used, last watered) with a **Manual Water** toggle and live timer; a **Recent
  Activity** feed of watered/skipped/cancelled events; a **System** card (enable toggle,
  rain-delay / vacation buttons); and global actions: **Skip Next Watering**, **Force
  Water All**, **Reset All Deficits**.
- **Zones** — add / edit / delete zones, including sun-exposure mode, crop coefficient,
  cycle & soak, and soil override.
- **Settings** — weather source, sensor mapping (each with a Primary and optional Fallback
  field), soil moisture (with the *Use soil-moisture sensor* mode toggle), soil type &
  strategy.

---

## 15. Entities

**System sensors:**

| Entity | Unit | Description |
|---|---|---|
| `sensor.*_daily_et` | mm | Daily evapotranspiration |
| `sensor.*_effective_rain` | mm | Soil-adjusted effective rainfall |
| `sensor.*_rain_today` | mm | Raw accumulated rainfall |
| `switch.*_automatic_watering` | — | Master enable for the automatic schedule |

**Per zone:**

| Entity | Unit | Description |
|---|---|---|
| `sensor.<zone>_water_deficit` | mm | Current deficit (attrs: sun coefficient, status) |
| `sensor.<zone>_status` | — | `ok` / `needs_water` / `watering` |
| `sensor.<zone>_sun_exposure` | — | Sun coefficient (0–1) |
| `sensor.<zone>_water_used` | mm | Cumulative water applied (total_increasing) |
| `sensor.<zone>_last_watered` | timestamp | When the zone was last watered |
| `binary_sensor.<zone>_needs_water` | — | Problem class; on when deficit > threshold |
| `switch.<zone>_sprinkler` | — | The zone's sprinkler switch |
| `number.<zone>_sprinkler_rate` | mm/30min | Sprinkler rate (0.5–10, step 0.1) |
| `number.<zone>_watering_threshold` | mm | Deficit threshold (5–30, step 1) |
| `number.<zone>_max_per_cycle` | mm | Max water per cycle (1–15, step 0.5) |

---

## 16. Services & WebSocket API

**Services** (Developer Tools → Services, or automations):

| Service | Fields | Description |
|---|---|---|
| `hydrobalance.force_water` | `zone_id?`, `mm_to_apply?` | Water now (one zone or all) |
| `hydrobalance.skip_day` | — | Skip the next watering check |
| `hydrobalance.reset_deficit` | `zone_id?` | Reset deficit to 0 (one zone or all) |

**WebSocket API** (used by the panel):

| Command | Payload | Purpose |
|---|---|---|
| `hydrobalance/config` | — | Read full configuration |
| `hydrobalance/config/save` | zones, soil, strategy, sensors, sensors_fallback, use_soil_moisture, … | Persist configuration |
| `hydrobalance/status` | — | Read live deficits / ET / status |
| `hydrobalance/discover_sensors` | `weather_entity` | Auto-map sensors |
| `hydrobalance/force_water` | `zone_id?`, `mm?` | Force watering |
| `hydrobalance/manual_water` | `zone_id`, `on`, `duration_minutes?` | Manual on/off toggle (optional auto-stop timer) |
| `hydrobalance/skip_day` | — | Skip next check |
| `hydrobalance/reset_deficit` | `zone_id?` | Reset deficit |
| `hydrobalance/set_enabled` | `enabled` | Master enable/disable |
| `hydrobalance/set_rain_delay` | `days` | Pause N days (0 clears) |

### Events & notifications

Every watering action fires a `hydrobalance_event` on the Home Assistant event bus, which
the logbook and recorder pick up automatically. The payload:

| Field | Values | Notes |
|---|---|---|
| `kind` | `watered` / `skipped` / `cancelled` | What happened |
| `zone_id` / `zone_name` | zone identifier / friendly name | `null` for system-wide skips |
| `mm` | float | Water applied (watered/cancelled) |
| `minutes` | float | Planned run length |
| `trigger` | `auto` / `forced` / `manual` | What initiated the run |
| `reason` | `disabled` / `rain_delay` / `skip_next` / `frost` / `rain_forecast` / `soil_moisture` | Why a run was skipped |
| `time` | ISO timestamp | When the event fired |

Wire these into a notification with a simple automation. **Notify when a zone is
watered:**

```yaml
automation:
  - alias: HydroBalance watered notification
    trigger:
      - platform: event
        event_type: hydrobalance_event
        event_data:
          kind: watered
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "HydroBalance"
          message: >
            Watered {{ trigger.event.data.zone_name }} —
            {{ trigger.event.data.mm }} mm ({{ trigger.event.data.trigger }})
```

**Notify when watering is skipped because of rain or frost:**

```yaml
automation:
  - alias: HydroBalance skip notification
    trigger:
      - platform: event
        event_type: hydrobalance_event
        event_data:
          kind: skipped
    condition:
      - "{{ trigger.event.data.reason in ['rain_forecast', 'frost'] }}"
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "HydroBalance"
          message: "Watering skipped: {{ trigger.event.data.reason }}"
```

You can equally trigger on `kind: cancelled`, branch on `trigger`/`reason`, or feed the
`sensor.<zone>_last_watered` and `sensor.<zone>_water_used` entities into dashboards and
history graphs.

---

## 17. Constants reference

All in `custom_components/hydrobalance/const.py`.

| Constant | Default | Meaning |
|---|---|---|
| `ET_COEFF_TEMP` | 0.15 | ET weight on mean temperature (°C) |
| `ET_COEFF_UV` | 0.25 | ET weight on peak UV index |
| `ET_COEFF_WIND` | 0.02 | ET weight on wind speed (km/h) |
| `ET_COEFF_HUMIDITY` | 0.015 | ET reduction per % relative humidity |
| `ET_MIN` / `ET_MAX` | 0 / 8 | ET clamp (mm/day) |
| `FROST_TEMP_LIMIT` | 5 °C | Skip watering below this forecast Tmin |
| `RAIN_FORECAST_SKIP` | 5 mm | Skip watering above this forecast rain |
| `DEFICIT_MIN` / `DEFICIT_MAX` | −20 / 60 | Deficit floor; 60 is now only a fallback cap when a soil has no `field_capacity` |
| `DEFAULT_SPRINKLER_RATE` | 2.0 | mm per 30 min |
| `DEFAULT_DEFICIT_THRESHOLD` | 12 | mm |
| `DEFAULT_MAX_PER_CYCLE` | 5 | mm |
| `DEFAULT_MOISTURE_SKIP_THRESHOLD` | 40 | % VWC |
| `DEFAULT_USE_SOIL_MOISTURE` | True | Soil-moisture mode on by default (off = pure ET model) |
| `DEFAULT_CROP_COEFFICIENT` | 1.0 | Kc multiplier on zone ET |
| `DEFAULT_PULSE_MINUTES` | 10 | Cycle & soak: max run before soaking |
| `DEFAULT_SOAK_MINUTES` | 20 | Cycle & soak: rest between pulses |
| `SOIL_TYPES` | clay / loam / sandy | Per-band rain absorption coefficients + field capacity (30 / 20 / 12 mm) |
| `STRATEGIES` | balanced / water_saving / lush_green / clay_safe | Threshold + max-per-cycle presets |
| `SUN_EXPOSURE_MANUAL` | 1.0 / 0.7 / 0.45 | Full / partial / heavy shade |
| `SUN_ORIENTATION_FALLBACK` | N…NW | Coefficients when only orientation is set |
| `SOLAR_RADIATION_WEIGHTS` | 0.15 / 0.30 / 0.35 / 0.20 | Daily radiation share per time window |

---

## 18. Troubleshooting

- **Nothing waters** — expected when every deficit is 0. Deficits build nightly at 23:00;
  watering begins automatically once a zone crosses its threshold. Use **Force Water** or
  **Manual Water** to test immediately.
- **ET / Tmin / Tmax stay blank** — temperature data is missing for the day. Check the
  Temperature sensor mapping and that the weather integration is delivering values.
- **Discovery mapped the wrong temperature sensor** — it excludes dew-point/feels-like by
  name, but you can always type the correct entity into the field and Save Sensors.
- **Rain never registers** — the Rain sensor is read as an **hourly rate** (mm/h). A
  cumulative-total sensor will be misread; map a rate sensor or a "precipitation
  intensity" sensor.
- **Panel shows an old version after updating** — restart Home Assistant, then fully close
  and reopen the app (the WebView caches the panel JS; the integration appends
  `?v=<version>` to bust it).
- **A zone watered far too long/short** — your `sprinkler_rate` is off. Run the catch-cup
  test (§11) and set the measured value.

---

## 19. Changelog

- **0.11.0** — **Manual watering timer:** the Manual Water button now opens a
  modal with preset durations (5–60 min), custom minutes, or *Until I stop*. A
  timed run auto-stops at the end and the live counter on the zone card counts
  down to it.
- **0.10.1** — Zone status shows the projected sprinkler **Run** time at the
  current deficit.
- **0.10.0** — **Sensor-aware reliability:** per-sensor **Primary → Fallback** resolver
  (real local sensor with a forecast fallback); **field-capacity deficit cap** (clay 30 /
  loam 20 / sandy 12 mm) replacing the flat 60 mm ceiling so a long skip can't bank
  impossible debt; **soil-moisture mode toggle** that freezes ET on wet soil (sensor
  overrides model) and can be turned off for a pure-ET system. Panel gains a fallback
  column, a soil-moisture mode switch, and a "Soil wet" zone badge.
- **0.9.x** — Panel button reactivity fix; ET / effective-rain surfaced on the dashboard.
- **0.8.0** — Per-zone **cycle & soak** pulse watering with per-pulse deficit crediting
  (cancellation-safe).
- **0.7.0** — Master **Automatic Watering** enable switch and **rain delay / vacation**
  multi-day pause.
- **0.6.0** — Per-zone **crop coefficient (Kc)**: `zone_ET = ET × sun × Kc`.
- **0.5.0** — Watering **history & per-zone usage**: `hydrobalance_event` bus events
  (watered/skipped/cancelled), `water_used` and `last_watered` sensors, Recent Activity
  panel card.
- **0.4.0** — Per-zone manual watering toggle with live timer; elapsed run time is
  credited to the deficit (clamped at 0) and survives restarts. Full technical README.
- **0.3.x** — Weather source & sensor mapping moved into the panel; sunrise−1h watering
  schedule; panel served as a `panel_custom` element; version cache-busting; editable
  sensor mappings with smarter discovery.
- **0.1.0** — Initial release: ET model, per-zone deficits, soil types, sun modelling,
  custom panel.
