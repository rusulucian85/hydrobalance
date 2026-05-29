// HydroBalance panel — registered as panel_custom in HA, runs inside the HA
// frontend context so we get an authenticated `hass` object directly (no
// WebSocket auth dance, works inside the iOS app's WKWebView).

const STYLES = `
  :host {
    display: block;
    --primary: #2196F3;
    --primary-dark: #1565C0;
    --success: #4CAF50;
    --warning: #FF9800;
    --danger: #f44336;
    --bg: #f5f5f5;
    --card: #ffffff;
    --text: #212121;
    --text-secondary: #757575;
    --border: #e0e0e0;
    --radius: 12px;
    --shadow: 0 2px 8px rgba(0,0,0,0.08);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    padding: 16px;
    box-sizing: border-box;
    min-height: 100%;
  }
  @media (prefers-color-scheme: dark) {
    :host {
      --bg: #1a1a2e;
      --card: #16213e;
      --text: #e0e0e0;
      --text-secondary: #9e9e9e;
      --border: #2a2a4a;
      --shadow: 0 2px 8px rgba(0,0,0,0.3);
    }
  }
  .wrap { max-width: 960px; margin: 0 auto; }
  * { box-sizing: border-box; }
  .header {
    display: flex; align-items: center; gap: 12px;
    margin-bottom: 24px; padding: 16px 20px;
    background: var(--card); border-radius: var(--radius); box-shadow: var(--shadow);
  }
  .header h1 { font-size: 1.5em; flex: 1; margin: 0; }
  .header .version { color: var(--text-secondary); font-size: 0.85em; }
  .tabs {
    display: flex; gap: 4px; margin-bottom: 20px;
    background: var(--card); border-radius: var(--radius); padding: 4px; box-shadow: var(--shadow);
  }
  .tab {
    flex: 1; padding: 10px 16px; border: none; background: transparent;
    color: var(--text-secondary); cursor: pointer; border-radius: 8px;
    font-size: 0.9em; font-weight: 500; transition: all 0.2s;
  }
  .tab.active { background: var(--primary); color: white; }
  .tab:hover:not(.active) { background: var(--border); }
  .card {
    background: var(--card); border-radius: var(--radius); padding: 20px;
    margin-bottom: 16px; box-shadow: var(--shadow);
  }
  .card h2 { font-size: 1.1em; margin: 0 0 16px; display: flex; align-items: center; gap: 8px; }
  .form-group { margin-bottom: 14px; }
  .form-group label {
    display: block; font-size: 0.85em; color: var(--text-secondary);
    margin-bottom: 4px; font-weight: 500;
  }
  .form-group input, .form-group select {
    width: 100%; padding: 10px 12px; border: 1px solid var(--border);
    border-radius: 8px; background: var(--bg); color: var(--text); font-size: 0.95em;
  }
  .form-group input:focus, .form-group select:focus {
    outline: none; border-color: var(--primary);
    box-shadow: 0 0 0 2px rgba(33,150,243,0.2);
  }
  .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .form-row-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; }
  .btn {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 10px 20px; border: none; border-radius: 8px; cursor: pointer;
    font-size: 0.9em; font-weight: 500; transition: all 0.2s;
  }
  .btn-primary { background: var(--primary); color: white; }
  .btn-primary:hover { background: var(--primary-dark); }
  .btn-warning { background: var(--warning); color: white; }
  .btn-danger { background: var(--danger); color: white; }
  .btn-outline { background: transparent; border: 1px solid var(--border); color: var(--text); }
  .btn-outline:hover { background: var(--border); }
  .btn-sm { padding: 6px 12px; font-size: 0.8em; }
  .actions { display: flex; gap: 8px; margin-top: 16px; flex-wrap: wrap; }
  .status-grid {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px;
  }
  .stat-box { text-align: center; padding: 16px 12px; background: var(--bg); border-radius: 8px; }
  .stat-box .value { font-size: 1.6em; font-weight: 700; color: var(--primary); }
  .stat-box .label { font-size: 0.75em; color: var(--text-secondary); margin-top: 4px; }
  .zone-card { border: 1px solid var(--border); border-radius: 8px; padding: 16px; margin-bottom: 12px; }
  .zone-card .zone-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
  .zone-card .zone-name { font-weight: 600; font-size: 1em; }
  .badge { display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 0.75em; font-weight: 600; }
  .badge-ok { background: #e8f5e9; color: #2e7d32; }
  .badge-warning { background: #fff3e0; color: #e65100; }
  .badge-danger { background: #ffebee; color: #c62828; }
  .badge-active { background: #e3f2fd; color: #1565c0; }
  .zone-stats { display: flex; gap: 16px; font-size: 0.85em; color: var(--text-secondary); flex-wrap: wrap; }
  .hidden { display: none !important; }
  .loading { text-align: center; padding: 40px; color: var(--text-secondary); }
  .empty-state { text-align: center; padding: 40px 20px; color: var(--text-secondary); }
  .empty-state p { margin-top: 8px; font-size: 0.9em; }
  .sensor-item {
    display: flex; justify-content: space-between; align-items: center;
    padding: 8px 0; border-bottom: 1px solid var(--border); font-size: 0.9em;
  }
  .sensor-item:last-child { border-bottom: none; }
  .sensor-item .sensor-name { color: var(--text-secondary); }
  .sensor-item .sensor-value { font-weight: 500; }
  .sensor-item .sensor-value.found { color: var(--success); }
  .sensor-item .sensor-value.missing { color: var(--danger); }
  .modal-overlay {
    position: fixed; top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.5); display: flex; align-items: center;
    justify-content: center; z-index: 100;
  }
  .modal {
    background: var(--card); border-radius: var(--radius); padding: 24px;
    width: 90%; max-width: 500px; max-height: 80vh; overflow-y: auto;
    box-shadow: 0 8px 32px rgba(0,0,0,0.2);
  }
  .modal h2 { margin: 0 0 20px; }
  .modal .actions { justify-content: flex-end; }
  .progress-bar { height: 6px; background: var(--border); border-radius: 3px; overflow: hidden; margin-top: 8px; }
  .progress-bar .fill { height: 100%; border-radius: 3px; transition: width 0.3s; }
  .toast {
    position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%);
    background: #333; color: white; padding: 12px 24px; border-radius: 8px;
    font-size: 0.9em; z-index: 1000;
  }
  .toast.err { background: var(--danger); }
`;

const TEMPLATE = `
  <div class="wrap">
    <div class="header">
      <div style="flex:1;">
        <h1>HydroBalance</h1>
        <div class="version">v0.9.1 &mdash; Smart Irrigation</div>
      </div>
    </div>

    <datalist id="dl-switches"></datalist>
    <datalist id="dl-sensors"></datalist>
    <datalist id="dl-weather"></datalist>

    <div class="tabs">
      <button class="tab active" data-tab="dashboard" onclick="window.__hb.showTab('dashboard')">Dashboard</button>
      <button class="tab" data-tab="zones" onclick="window.__hb.showTab('zones')">Zones</button>
      <button class="tab" data-tab="settings" onclick="window.__hb.showTab('settings')">Settings</button>
    </div>

    <div id="tab-dashboard">
      <div class="card">
        <h2>Today's Data</h2>
        <div class="status-grid">
          <div class="stat-box"><div class="value" id="stat-et">--</div><div class="label">ET (mm)</div></div>
          <div class="stat-box"><div class="value" id="stat-rain">--</div><div class="label">Rain (mm)</div></div>
          <div class="stat-box"><div class="value" id="stat-effrain">--</div><div class="label">Eff. Rain (mm)</div></div>
          <div class="stat-box"><div class="value" id="stat-tmin">--</div><div class="label">T min (&deg;C)</div></div>
          <div class="stat-box"><div class="value" id="stat-tmax">--</div><div class="label">T max (&deg;C)</div></div>
          <div class="stat-box"><div class="value" id="stat-uv">--</div><div class="label">Peak UV</div></div>
        </div>
      </div>

      <div class="card hidden" id="soil-moisture-card">
        <h2>Soil Moisture</h2>
        <div style="display:flex;justify-content:space-between;align-items:baseline;">
          <span id="soil-moisture-value" style="font-size:1.6em;font-weight:700;">--</span>
          <span id="soil-moisture-meta" style="font-size:0.85em;color:var(--text-secondary);"></span>
        </div>
      </div>

      <div class="card">
        <h2>Zone Status</h2>
        <div id="zone-status-list"><div class="loading">Loading...</div></div>
      </div>

      <div class="card">
        <h2>Recent Activity</h2>
        <div id="activity-list"><div class="empty-state"><p>No activity yet.</p></div></div>
      </div>

      <div class="card">
        <h2>System</h2>
        <div id="system-status" style="margin-bottom:12px;"></div>
        <div class="actions">
          <button class="btn btn-outline" id="enable-toggle-btn" onclick="window.__hb.toggleEnabled()">Disable Watering</button>
          <button class="btn btn-warning" onclick="window.__hb.setRainDelay(3)">Rain Delay 3d</button>
          <button class="btn btn-warning" onclick="window.__hb.setRainDelay(7)">Vacation 7d</button>
          <button class="btn btn-outline" id="clear-delay-btn" onclick="window.__hb.setRainDelay(0)">Clear Delay</button>
        </div>
      </div>

      <div class="card">
        <h2>Actions</h2>
        <div class="actions">
          <button class="btn btn-warning" onclick="window.__hb.skipDay()">Skip Next Watering</button>
          <button class="btn btn-primary" onclick="window.__hb.forceWater()">Force Water All</button>
          <button class="btn btn-outline" onclick="window.__hb.resetDeficit()">Reset All Deficits</button>
        </div>
      </div>
    </div>

    <div id="tab-zones" class="hidden">
      <div class="card">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
          <h2 style="margin-bottom:0;">Watering Zones</h2>
          <button class="btn btn-primary btn-sm" onclick="window.__hb.openZoneModal()">+ Add Zone</button>
        </div>
        <div id="zone-config-list">
          <div class="empty-state"><p><strong>No zones configured</strong></p><p>Add your first watering zone to get started.</p></div>
        </div>
      </div>
    </div>

    <div id="tab-settings" class="hidden">
      <div class="card">
        <h2>Weather Source</h2>
        <p style="font-size:0.85em;color:var(--text-secondary);margin-bottom:12px;">
          The weather integration that ET is calculated from. After changing it,
          re-discover sensors below.
        </p>
        <div class="form-group">
          <label>Weather Entity</label>
          <input type="text" id="weather-entity" list="dl-weather" placeholder="weather.home" autocapitalize="off" autocomplete="off">
        </div>
        <div class="form-group" style="display:flex;align-items:center;gap:8px;">
          <input type="checkbox" id="use-forecast" style="width:auto;">
          <label for="use-forecast" style="margin:0;">Skip watering when rain is forecast</label>
        </div>
        <div class="actions">
          <button class="btn btn-primary" onclick="window.__hb.saveWeatherConfig()">Save Weather Source</button>
        </div>
      </div>

      <div class="card">
        <h2>Weather Sensors</h2>
        <p style="font-size:0.85em;color:var(--text-secondary);margin-bottom:12px;">
          Auto-discovered from your weather integration. Adjust if needed.
        </p>
        <div id="sensor-list"><div class="loading">Loading...</div></div>
        <div class="actions">
          <button class="btn btn-primary" onclick="window.__hb.saveWeatherSensors()">Save Sensors</button>
          <button class="btn btn-outline" onclick="window.__hb.discoverSensors()">Re-discover Sensors</button>
        </div>
      </div>

      <div class="card">
        <h2>Soil Moisture Sensor</h2>
        <p style="font-size:0.85em;color:var(--text-secondary);margin-bottom:12px;">
          Optional. When set, watering is skipped if measured soil moisture is above the threshold &mdash;
          real-sensor feedback overrides the ET estimate.
        </p>
        <div class="form-group">
          <label>Sensor Entity</label>
          <input type="text" id="soil-moisture-sensor" list="dl-sensors" placeholder="sensor.garden_sensor_soil_moisture" autocapitalize="off" autocomplete="off">
        </div>
        <div class="form-group">
          <label>Skip Threshold (% VWC)</label>
          <input type="number" id="moisture-threshold" value="40" step="1" min="0" max="100">
        </div>
        <div class="actions">
          <button class="btn btn-primary" onclick="window.__hb.saveMoistureConfig()">Save Soil Moisture</button>
        </div>
      </div>

      <div class="card">
        <h2>Soil &amp; Strategy</h2>
        <div class="form-row">
          <div class="form-group">
            <label>Soil Type</label>
            <select id="soil-type">
              <option value="clay">Clay / Heavy Soil</option>
              <option value="loam">Loam</option>
              <option value="sandy">Sandy</option>
            </select>
          </div>
          <div class="form-group">
            <label>Watering Strategy</label>
            <select id="strategy">
              <option value="balanced">Balanced (12mm / 5mm)</option>
              <option value="water_saving">Water Saving (16mm / 4mm)</option>
              <option value="lush_green">Lush Green (8mm / 6mm)</option>
              <option value="clay_safe">Clay-Safe (14mm / 3mm)</option>
            </select>
          </div>
        </div>
        <div class="actions">
          <button class="btn btn-primary" onclick="window.__hb.saveSettings()">Save Settings</button>
        </div>
      </div>
    </div>

    <div id="zone-modal" class="modal-overlay hidden" onclick="window.__hb._modalBackdrop(event)">
      <div class="modal">
        <h2 id="zone-modal-title">Add Zone</h2>
        <input type="hidden" id="zone-edit-id">
        <div class="form-group">
          <label>Zone Name</label>
          <input type="text" id="zone-name" placeholder="e.g. Back Garden">
        </div>
        <div class="form-group">
          <label>Sprinkler Switch Entity</label>
          <input type="text" id="zone-switch" list="dl-switches" placeholder="switch.sprinkler_back" autocapitalize="off" autocomplete="off">
        </div>
        <div class="form-row-3">
          <div class="form-group">
            <label>Sprinkler Rate (mm/30min)</label>
            <input type="number" id="zone-rate" value="2.0" step="0.1" min="0.1">
          </div>
          <div class="form-group">
            <label>Deficit Threshold (mm)</label>
            <input type="number" id="zone-threshold" value="12" step="0.5" min="1">
          </div>
          <div class="form-group">
            <label>Max Per Cycle (mm)</label>
            <input type="number" id="zone-maxcycle" value="5" step="0.5" min="0.5">
          </div>
        </div>
        <div class="form-group">
          <label>Sun Exposure Mode</label>
          <select id="zone-sun-mode" onchange="window.__hb.toggleSunFields()">
            <option value="manual">Manual</option>
            <option value="auto">Auto (Orientation + Shadow)</option>
          </select>
        </div>
        <div id="sun-manual-fields">
          <div class="form-group">
            <label>Sun Exposure</label>
            <select id="zone-sun-exposure">
              <option value="full_sun">Full Sun (1.0)</option>
              <option value="partial_shade">Partial Shade (0.7)</option>
              <option value="heavy_shade">Heavy Shade (0.45)</option>
            </select>
          </div>
        </div>
        <div id="sun-auto-fields" class="hidden">
          <div class="form-group">
            <label>Zone Orientation (relative to building)</label>
            <select id="zone-orientation">
              <option value="N">North</option>
              <option value="NE">North-East</option>
              <option value="E">East</option>
              <option value="SE">South-East</option>
              <option value="S">South</option>
              <option value="SW">South-West</option>
              <option value="W">West</option>
              <option value="NW">North-West</option>
            </select>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>Obstacle Height (m)</label>
              <input type="number" id="zone-obs-height" step="0.5" min="0" placeholder="e.g. 8">
            </div>
            <div class="form-group">
              <label>Distance to Obstacle (m)</label>
              <input type="number" id="zone-obs-distance" step="0.5" min="0" placeholder="e.g. 5">
            </div>
          </div>
        </div>
        <div class="form-group">
          <label>Crop Coefficient (Kc) — plant water demand vs. reference</label>
          <select id="zone-kc">
            <option value="0.4">0.4 — Drought-tolerant / native</option>
            <option value="0.6">0.6 — Shrubs / mixed beds</option>
            <option value="0.8">0.8 — Cool-season turf (low)</option>
            <option value="1">1.0 — Reference / standard lawn</option>
            <option value="1.1">1.1 — Vegetable garden</option>
            <option value="1.2">1.2 — High-demand / dense crop</option>
          </select>
        </div>
        <div class="form-group" style="display:flex;align-items:center;gap:8px;">
          <input type="checkbox" id="zone-cycle-soak" style="width:auto;" onchange="window.__hb.toggleCycleSoakFields()">
          <label for="zone-cycle-soak" style="margin:0;">Cycle &amp; Soak (pulse watering to prevent runoff)</label>
        </div>
        <div id="cycle-soak-fields" class="form-row hidden">
          <div class="form-group">
            <label>Pulse (min)</label>
            <input type="number" id="zone-pulse" value="10" step="1" min="1">
          </div>
          <div class="form-group">
            <label>Soak (min)</label>
            <input type="number" id="zone-soak" value="20" step="1" min="0">
          </div>
        </div>
        <div class="form-group">
          <label>Soil Override (leave empty for system default)</label>
          <select id="zone-soil-override">
            <option value="">Use System Default</option>
            <option value="clay">Clay / Heavy Soil</option>
            <option value="loam">Loam</option>
            <option value="sandy">Sandy</option>
          </select>
        </div>
        <div class="actions">
          <button class="btn btn-outline" onclick="window.__hb.closeZoneModal()">Cancel</button>
          <button class="btn btn-danger hidden" id="zone-delete-btn" onclick="window.__hb.deleteZone()">Delete</button>
          <button class="btn btn-primary" onclick="window.__hb.saveZone()">Save Zone</button>
        </div>
      </div>
    </div>
  </div>
`;

class HydroBalancePanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._config = {};
    this._status = {};
    this._currentEntryId = null;
    this._entitiesCache = null;
    this._rendered = false;
    this._cronTimer = null;
    // Inline event handlers in the template reference this global. There's
    // only ever one panel instance, so a single window-scoped pointer is fine.
    window.__hb = this;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._rendered) {
      this._rendered = true;
      this.shadowRoot.innerHTML = `<style>${STYLES}</style>${TEMPLATE}`;
      this._loadAll();
    }
  }

  $(id) { return this.shadowRoot.getElementById(id); }

  async _ws(type, data = {}) {
    return this._hass.callWS({ type, ...data });
  }

  _esc(s) {
    const d = document.createElement('div');
    d.textContent = s || '';
    return d.innerHTML;
  }

  _toast(msg) {
    const el = document.createElement('div');
    el.className = 'toast';
    const isErr = /^Error/i.test(msg);
    if (isErr) el.classList.add('err');
    el.textContent = msg;
    el.onclick = () => el.remove();
    this.shadowRoot.appendChild(el);
    setTimeout(() => el.remove(), isErr ? 8000 : 3000);
  }

  // ─── Data loading ───────────────────────────────────────────────────────
  async _loadAll() {
    try {
      const [cfg, status] = await Promise.all([
        this._ws('hydrobalance/config'),
        this._ws('hydrobalance/status'),
      ]);
      this._config = cfg;
      this._status = status;
      const entries = Object.keys(cfg);
      if (entries.length > 0) this._currentEntryId = entries[0];
      this._renderDashboard();
      this._renderZones();
      this._renderSettings();
    } catch (e) {
      console.error('HydroBalance load failed:', e);
      this._toast('Error loading: ' + (e.message || e));
    }
  }

  async _getEntities() {
    if (this._entitiesCache) return this._entitiesCache;
    try {
      const states = await this._ws('get_states');
      this._entitiesCache = states || [];
    } catch (e) {
      console.error('get_states failed:', e);
      this._entitiesCache = [];
    }
    return this._entitiesCache;
  }

  async _populatePicker(datalistId, domainPrefix) {
    const dl = this.$(datalistId);
    if (!dl) return;
    const states = await this._getEntities();
    const prefix = domainPrefix + '.';
    const filtered = states.filter(s => s.entity_id && s.entity_id.startsWith(prefix));
    dl.innerHTML = filtered
      .map(s => {
        const name = s.attributes && s.attributes.friendly_name;
        return `<option value="${this._esc(s.entity_id)}">${this._esc(name || s.entity_id)}</option>`;
      })
      .join('');
  }

  // ─── Rendering ──────────────────────────────────────────────────────────
  _renderDashboard() {
    if (!this._currentEntryId || !this._status[this._currentEntryId]) return;
    const s = this._status[this._currentEntryId];
    const daily = s.daily || {};

    this.$('stat-et').textContent = daily.et != null ? daily.et : '--';
    this.$('stat-rain').textContent = daily.rain_accumulated != null ? daily.rain_accumulated : '--';
    this.$('stat-effrain').textContent = daily.effective_rain != null ? daily.effective_rain : '--';
    this.$('stat-tmin').textContent = daily.tmin != null ? daily.tmin.toFixed(1) : '--';
    this.$('stat-tmax').textContent = daily.tmax != null ? daily.tmax.toFixed(1) : '--';
    this.$('stat-uv').textContent = daily.peak_uv != null ? daily.peak_uv.toFixed(1) : '--';

    const soil = s.soil || {};
    const moistureCard = this.$('soil-moisture-card');
    if (soil.moisture != null) {
      moistureCard.classList.remove('hidden');
      const threshold = soil.skip_threshold ?? 40;
      const valueEl = this.$('soil-moisture-value');
      valueEl.textContent = soil.moisture.toFixed(1) + ' %';
      valueEl.style.color = soil.moisture > threshold ? 'var(--success)' : 'var(--primary)';
      this.$('soil-moisture-meta').textContent =
        `skip when ≥ ${threshold}%` + (soil.moisture > threshold ? ' — watering skipped' : '');
    } else {
      moistureCard.classList.add('hidden');
    }

    const zones = s.zones || {};
    const container = this.$('zone-status-list');
    if (Object.keys(zones).length === 0) {
      container.innerHTML = '<div class="empty-state"><p>No zones configured yet.</p><p>Go to Zones tab to add watering zones.</p></div>';
      return;
    }

    let html = '';
    for (const [zid, zdata] of Object.entries(zones)) {
      const zoneName = (zdata.config && zdata.config.name) || zid;
      const deficit = zdata.water_deficit || 0;
      const sunCoeff = zdata.sun_coefficient || 1;
      const zoneStatus = zdata.status || 'ok';
      const threshold = (zdata.config && zdata.config.deficit_threshold) || 12;
      const manualActive = !!zdata.manual_active;
      const manualStarted = zdata.manual_started || '';
      const waterUsed = zdata.water_used || 0;
      const lastWatered = zdata.last_watered
        ? this._relTime(zdata.last_watered)
        : 'never';

      let badgeClass = 'badge-ok', badgeText = 'OK';
      if (manualActive) { badgeClass = 'badge-active'; badgeText = 'Manual'; }
      else if (zoneStatus === 'watering') { badgeClass = 'badge-active'; badgeText = 'Watering'; }
      else if (zoneStatus === 'needs_water') { badgeClass = 'badge-danger'; badgeText = 'Needs Water'; }
      else if (deficit > threshold * 0.7) { badgeClass = 'badge-warning'; badgeText = 'Building'; }

      const pct = Math.min(100, Math.max(0, (deficit / threshold) * 100));
      const barColor = pct > 80 ? 'var(--danger)' : pct > 50 ? 'var(--warning)' : 'var(--success)';

      const cron = manualActive
        ? `<span class="hb-cron" data-start="${this._esc(manualStarted)}" style="font-variant-numeric:tabular-nums;color:var(--danger);font-weight:600;">00:00</span>`
        : '';

      html += `
        <div class="zone-card">
          <div class="zone-header">
            <span class="zone-name">${this._esc(zoneName)}</span>
            <span class="badge ${badgeClass}">${badgeText}</span>
          </div>
          <div class="zone-stats">
            <span>Deficit: <strong>${deficit} mm</strong></span>
            <span>Sun: <strong>${sunCoeff}</strong></span>
            <span>Threshold: ${threshold} mm</span>
            <span>Used: <strong>${waterUsed} mm</strong></span>
            <span>Last: ${this._esc(lastWatered)}</span>
          </div>
          <div class="progress-bar">
            <div class="fill" style="width:${pct}%;background:${barColor}"></div>
          </div>
          <div style="margin-top:12px;display:flex;gap:8px;align-items:center;">
            <button class="btn btn-sm ${manualActive ? 'btn-danger' : 'btn-outline'}"
              onclick="window.__hb.manualWater('${this._esc(zid)}', ${manualActive ? 'false' : 'true'})">
              ${manualActive ? 'Stop Manual' : 'Manual Water'}
            </button>
            ${cron}
          </div>
        </div>`;
    }
    container.innerHTML = html;
    this._ensureCronTicker();
    this._renderActivity(s.events || []);
    this._renderSystem(s.system || {});
  }

  _renderSystem(sys) {
    const statusEl = this.$('system-status');
    const toggleBtn = this.$('enable-toggle-btn');
    if (!statusEl || !toggleBtn) return;

    const enabled = sys.enabled !== false;
    const delayActive = !!sys.rain_delay_active;
    this._enabled = enabled;

    let msg, color;
    if (!enabled) {
      msg = 'Automatic watering is DISABLED'; color = 'var(--danger)';
    } else if (delayActive) {
      const until = sys.rain_delay_until ? new Date(sys.rain_delay_until) : null;
      const untilTxt = until ? until.toLocaleString() : '';
      msg = `Paused (rain delay) until ${untilTxt}`; color = 'var(--warning)';
    } else {
      msg = 'Automatic watering is active'; color = 'var(--success)';
    }
    statusEl.innerHTML = `<span style="font-weight:600;color:${color};">${this._esc(msg)}</span>`;

    toggleBtn.textContent = enabled ? 'Disable Watering' : 'Enable Watering';
    toggleBtn.classList.toggle('btn-danger', enabled);
    toggleBtn.classList.toggle('btn-primary', !enabled);
    toggleBtn.classList.toggle('btn-outline', false);

    this.$('clear-delay-btn').classList.toggle('hidden', !delayActive);
  }

  _renderActivity(events) {
    const container = this.$('activity-list');
    if (!container) return;
    if (!events.length) {
      container.innerHTML = '<div class="empty-state"><p>No activity yet.</p></div>';
      return;
    }
    const labels = {
      watered: ['mdi water', 'Watered'],
      skipped: ['skip', 'Skipped'],
      cancelled: ['stop', 'Cancelled'],
    };
    const triggerText = { auto: 'auto', forced: 'forced', manual: 'manual' };
    const reasonText = {
      frost: 'frost protection',
      rain_forecast: 'rain forecast',
      soil_moisture: 'soil moisture',
      skip_next: 'skip requested',
      disabled: 'system disabled',
      rain_delay: 'rain delay / vacation',
    };
    let html = '';
    for (const ev of events.slice(0, 20)) {
      const [, label] = labels[ev.kind] || ['', ev.kind];
      let detail = '';
      if (ev.kind === 'watered') {
        const parts = [];
        if (ev.zone_name) parts.push(this._esc(ev.zone_name));
        if (ev.mm != null) parts.push(`${ev.mm} mm`);
        if (ev.minutes != null) parts.push(`${ev.minutes} min`);
        if (ev.trigger) parts.push(`(${triggerText[ev.trigger] || ev.trigger})`);
        detail = parts.join(' · ');
      } else if (ev.kind === 'skipped') {
        detail = reasonText[ev.reason] || ev.reason || '';
      } else if (ev.kind === 'cancelled') {
        detail = ev.zone_name ? this._esc(ev.zone_name) : '';
      }
      html += `
        <div class="sensor-item">
          <span class="sensor-name">${this._esc(label)} ${detail ? '· ' + detail : ''}</span>
          <span class="sensor-value">${this._esc(this._relTime(ev.time))}</span>
        </div>`;
    }
    container.innerHTML = html;
  }

  _relTime(iso) {
    const t = Date.parse(iso);
    if (isNaN(t)) return '';
    const diff = Math.floor((Date.now() - t) / 1000);
    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
  }

  // Live elapsed-time ticker for any zone currently in manual watering.
  _updateCrons() {
    const spans = this.shadowRoot.querySelectorAll('.hb-cron');
    if (spans.length === 0) {
      if (this._cronTimer) { clearInterval(this._cronTimer); this._cronTimer = null; }
      return;
    }
    const now = Date.now();
    spans.forEach(sp => {
      const start = Date.parse(sp.dataset.start);
      if (isNaN(start)) return;
      const sec = Math.max(0, Math.floor((now - start) / 1000));
      const m = String(Math.floor(sec / 60)).padStart(2, '0');
      const s = String(sec % 60).padStart(2, '0');
      sp.textContent = `${m}:${s}`;
    });
  }

  _ensureCronTicker() {
    this._updateCrons();
    if (this._cronTimer) return;
    if (this.shadowRoot.querySelectorAll('.hb-cron').length === 0) return;
    this._cronTimer = setInterval(() => this._updateCrons(), 1000);
  }

  _renderZones() {
    if (!this._currentEntryId) return;
    const entry = this._config[this._currentEntryId];
    const zones = (entry && entry.zones) || [];
    const container = this.$('zone-config-list');

    if (zones.length === 0) {
      container.innerHTML = '<div class="empty-state"><p><strong>No zones configured</strong></p><p>Add your first watering zone to get started.</p></div>';
      return;
    }

    let html = '';
    for (const zone of zones) {
      const sunMode = zone.sun_exposure_mode || 'manual';
      const sunText = sunMode === 'manual'
        ? (zone.sun_exposure || 'full_sun').replace('_', ' ')
        : `${zone.orientation || '?'} auto`;

      html += `
        <div class="zone-card">
          <div class="zone-header">
            <span class="zone-name">${this._esc(zone.name || zone.id)}</span>
            <button class="btn btn-outline btn-sm" onclick="window.__hb.editZone('${this._esc(zone.id)}')">Edit</button>
          </div>
          <div class="zone-stats">
            <span>Switch: ${this._esc(zone.switch_entity || 'none')}</span>
            <span>Rate: ${zone.sprinkler_rate || 2.0} mm/30min</span>
            <span>Sun: ${this._esc(sunText)}</span>
            <span>Kc: ${zone.crop_coefficient != null ? zone.crop_coefficient : 1.0}</span>
            ${zone.cycle_soak ? `<span>Cycle&amp;Soak: ${zone.pulse_minutes || 10}/${zone.soak_minutes || 0}m</span>` : ''}
          </div>
        </div>`;
    }
    container.innerHTML = html;
  }

  _renderSettings() {
    if (!this._currentEntryId) return;
    const entry = this._config[this._currentEntryId];

    this.$('weather-entity').value = (entry && entry.weather_entity) || '';
    this.$('use-forecast').checked = !(entry && entry.use_forecast === false);
    this._populatePicker('dl-weather', 'weather');

    this.$('soil-type').value = (entry && entry.soil_type) || 'clay';
    this.$('strategy').value = (entry && entry.strategy) || 'balanced';

    const sensors = (entry && entry.sensors) || {};
    const sensorKeys = [
      ['sensor_temperature', 'Temperature'],
      ['sensor_temperature_min', 'Forecast Min (frost check)'],
      ['sensor_humidity', 'Humidity'],
      ['sensor_wind_speed', 'Wind Speed'],
      ['sensor_uv_index', 'UV Index'],
      ['sensor_rain', 'Rain'],
      ['sensor_rain_forecast', 'Rain Forecast'],
    ];
    let html = '';
    for (const [key, label] of sensorKeys) {
      const val = sensors[key] || '';
      html += `
        <div class="form-group">
          <label>${label}</label>
          <input type="text" id="ws-${key}" list="dl-sensors" value="${this._esc(val)}" placeholder="Not configured" autocapitalize="off" autocomplete="off">
        </div>`;
    }
    this.$('sensor-list').innerHTML = html;

    this.$('soil-moisture-sensor').value = sensors.sensor_soil_moisture || '';
    this.$('moisture-threshold').value = (entry && entry.moisture_skip_threshold != null) ? entry.moisture_skip_threshold : 40;
    this._populatePicker('dl-sensors', 'sensor');
  }

  // ─── Tabs & modal ───────────────────────────────────────────────────────
  showTab(tab) {
    this.shadowRoot.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
    this.$('tab-dashboard').classList.toggle('hidden', tab !== 'dashboard');
    this.$('tab-zones').classList.toggle('hidden', tab !== 'zones');
    this.$('tab-settings').classList.toggle('hidden', tab !== 'settings');
  }

  openZoneModal(zone = null) {
    const title = this.$('zone-modal-title');
    const deleteBtn = this.$('zone-delete-btn');

    if (zone) {
      title.textContent = 'Edit Zone';
      deleteBtn.classList.remove('hidden');
      this.$('zone-edit-id').value = zone.id;
      this.$('zone-name').value = zone.name || '';
      this.$('zone-switch').value = zone.switch_entity || '';
      this.$('zone-rate').value = zone.sprinkler_rate || 2.0;
      this.$('zone-threshold').value = zone.deficit_threshold || 12;
      this.$('zone-maxcycle').value = zone.max_per_cycle || 5;
      this.$('zone-sun-mode').value = zone.sun_exposure_mode || 'manual';
      this.$('zone-sun-exposure').value = zone.sun_exposure || 'full_sun';
      this.$('zone-orientation').value = zone.orientation || 'S';
      this.$('zone-obs-height').value = zone.obstacle_height || '';
      this.$('zone-obs-distance').value = zone.obstacle_distance || '';
      this.$('zone-soil-override').value = zone.soil_override || '';
      this.$('zone-kc').value = zone.crop_coefficient != null ? String(zone.crop_coefficient) : '1';
      this.$('zone-cycle-soak').checked = !!zone.cycle_soak;
      this.$('zone-pulse').value = zone.pulse_minutes != null ? zone.pulse_minutes : 10;
      this.$('zone-soak').value = zone.soak_minutes != null ? zone.soak_minutes : 20;
    } else {
      title.textContent = 'Add Zone';
      deleteBtn.classList.add('hidden');
      this.$('zone-edit-id').value = '';
      this.$('zone-name').value = '';
      this.$('zone-switch').value = '';
      this.$('zone-rate').value = '2.0';
      this.$('zone-threshold').value = '12';
      this.$('zone-maxcycle').value = '5';
      this.$('zone-sun-mode').value = 'manual';
      this.$('zone-sun-exposure').value = 'full_sun';
      this.$('zone-orientation').value = 'S';
      this.$('zone-obs-height').value = '';
      this.$('zone-obs-distance').value = '';
      this.$('zone-soil-override').value = '';
      this.$('zone-kc').value = '1';
      this.$('zone-cycle-soak').checked = false;
      this.$('zone-pulse').value = '10';
      this.$('zone-soak').value = '20';
    }
    this.toggleSunFields();
    this.toggleCycleSoakFields();
    this._populatePicker('dl-switches', 'switch');
    this.$('zone-modal').classList.remove('hidden');
  }

  closeZoneModal() { this.$('zone-modal').classList.add('hidden'); }

  _modalBackdrop(event) {
    if (event.target === this.$('zone-modal')) this.closeZoneModal();
  }

  editZone(zoneId) {
    const entry = this._config[this._currentEntryId];
    const zone = ((entry && entry.zones) || []).find(z => z.id === zoneId);
    if (zone) this.openZoneModal(zone);
  }

  toggleSunFields() {
    const mode = this.$('zone-sun-mode').value;
    this.$('sun-manual-fields').classList.toggle('hidden', mode !== 'manual');
    this.$('sun-auto-fields').classList.toggle('hidden', mode !== 'auto');
  }

  toggleCycleSoakFields() {
    const on = this.$('zone-cycle-soak').checked;
    this.$('cycle-soak-fields').classList.toggle('hidden', !on);
  }

  // ─── Mutations ──────────────────────────────────────────────────────────
  async saveZone() {
    const editId = this.$('zone-edit-id').value;
    const zone = {
      id: editId || 'zone_' + Date.now(),
      name: this.$('zone-name').value.trim(),
      switch_entity: this.$('zone-switch').value.trim(),
      sprinkler_rate: parseFloat(this.$('zone-rate').value) || 2.0,
      deficit_threshold: parseFloat(this.$('zone-threshold').value) || 12,
      max_per_cycle: parseFloat(this.$('zone-maxcycle').value) || 5,
      sun_exposure_mode: this.$('zone-sun-mode').value,
      sun_exposure: this.$('zone-sun-exposure').value,
      orientation: this.$('zone-orientation').value,
      obstacle_height: parseFloat(this.$('zone-obs-height').value) || null,
      obstacle_distance: parseFloat(this.$('zone-obs-distance').value) || null,
      soil_override: this.$('zone-soil-override').value || null,
      crop_coefficient: parseFloat(this.$('zone-kc').value) || 1.0,
      cycle_soak: this.$('zone-cycle-soak').checked,
      pulse_minutes: parseFloat(this.$('zone-pulse').value) || 10,
      soak_minutes: parseFloat(this.$('zone-soak').value) || 0,
    };

    if (!zone.name) { this._toast('Zone name is required'); return; }

    const entry = this._config[this._currentEntryId];
    let zones = [...((entry && entry.zones) || [])];

    if (editId) {
      const idx = zones.findIndex(z => z.id === editId);
      if (idx >= 0) zones[idx] = zone; else zones.push(zone);
    } else {
      zones.push(zone);
    }

    try {
      await this._ws('hydrobalance/config/save', {
        entry_id: this._currentEntryId,
        zones: zones,
      });
      this.closeZoneModal();
      this._toast('Zone saved!');
      await this._loadAll();
    } catch (e) {
      this._toast('Error saving zone: ' + (e.message || e));
    }
  }

  async deleteZone() {
    const editId = this.$('zone-edit-id').value;
    if (!editId || !confirm('Delete this zone?')) return;

    const entry = this._config[this._currentEntryId];
    const zones = ((entry && entry.zones) || []).filter(z => z.id !== editId);

    try {
      await this._ws('hydrobalance/config/save', {
        entry_id: this._currentEntryId,
        zones: zones,
      });
      this.closeZoneModal();
      this._toast('Zone deleted');
      await this._loadAll();
    } catch (e) {
      this._toast('Error: ' + (e.message || e));
    }
  }

  async saveSettings() {
    try {
      await this._ws('hydrobalance/config/save', {
        entry_id: this._currentEntryId,
        soil_type: this.$('soil-type').value,
        strategy: this.$('strategy').value,
      });
      this._toast('Settings saved!');
      await this._loadAll();
    } catch (e) {
      this._toast('Error: ' + (e.message || e));
    }
  }

  async saveMoistureConfig() {
    const entry = this._config[this._currentEntryId];
    const sensors = { ...((entry && entry.sensors) || {}) };
    const moistureEntity = this.$('soil-moisture-sensor').value.trim();
    if (moistureEntity) sensors.sensor_soil_moisture = moistureEntity;
    else delete sensors.sensor_soil_moisture;
    const threshold = parseFloat(this.$('moisture-threshold').value);
    try {
      await this._ws('hydrobalance/config/save', {
        entry_id: this._currentEntryId,
        sensors: sensors,
        moisture_skip_threshold: isNaN(threshold) ? 40 : threshold,
      });
      this._toast('Soil moisture settings saved!');
      await this._loadAll();
    } catch (e) {
      this._toast('Error: ' + (e.message || e));
    }
  }

  async saveWeatherConfig() {
    const weatherEntity = this.$('weather-entity').value.trim();
    try {
      await this._ws('hydrobalance/config/save', {
        entry_id: this._currentEntryId,
        weather_entity: weatherEntity || null,
        use_forecast: this.$('use-forecast').checked,
      });
      this._toast('Weather source saved!');
      await this._loadAll();
    } catch (e) {
      this._toast('Error: ' + (e.message || e));
    }
  }

  async saveWeatherSensors() {
    const entry = this._config[this._currentEntryId];
    const sensors = { ...((entry && entry.sensors) || {}) };
    const keys = [
      'sensor_temperature', 'sensor_temperature_min',
      'sensor_humidity', 'sensor_wind_speed', 'sensor_uv_index',
      'sensor_rain', 'sensor_rain_forecast',
    ];
    for (const k of keys) {
      const v = this.$('ws-' + k).value.trim();
      if (v) sensors[k] = v; else delete sensors[k];
    }
    delete sensors.sensor_temperature_max;  // retired field
    try {
      await this._ws('hydrobalance/config/save', { entry_id: this._currentEntryId, sensors });
      this._toast('Sensors saved!');
      await this._loadAll();
    } catch (e) {
      this._toast('Error: ' + (e.message || e));
    }
  }

  async discoverSensors() {
    const entry = this._config[this._currentEntryId];
    const weatherEntity = this.$('weather-entity').value.trim() || (entry && entry.weather_entity);
    if (!weatherEntity) { this._toast('Set a weather entity first'); return; }
    try {
      const discovered = await this._ws('hydrobalance/discover_sensors', { weather_entity: weatherEntity });
      // Merge over existing so we don't wipe the soil-moisture sensor (which
      // discovery doesn't return) or any manual overrides for unfound keys.
      const merged = { ...((entry && entry.sensors) || {}) };
      for (const [k, v] of Object.entries(discovered)) {
        if (v) merged[k] = v;
      }
      await this._ws('hydrobalance/config/save', { entry_id: this._currentEntryId, sensors: merged });
      this._toast('Sensors re-discovered!');
      await this._loadAll();
    } catch (e) {
      this._toast('Error: ' + (e.message || e));
    }
  }

  async forceWater(zoneId) {
    try {
      await this._ws('hydrobalance/force_water', zoneId ? { zone_id: zoneId } : {});
      this._toast('Force watering initiated');
      setTimeout(() => this._loadAll(), 2000);
    } catch (e) { this._toast('Error: ' + (e.message || e)); }
  }

  async manualWater(zoneId, on) {
    try {
      await this._ws('hydrobalance/manual_water', { zone_id: zoneId, on });
      this._toast(on ? 'Manual watering started' : 'Manual watering stopped');
      await this._loadAll();
    } catch (e) { this._toast('Error: ' + (e.message || e)); }
  }

  async skipDay() {
    try {
      await this._ws('hydrobalance/skip_day');
      this._toast('Next watering will be skipped');
    } catch (e) { this._toast('Error: ' + (e.message || e)); }
  }

  async toggleEnabled() {
    const next = !this._enabled;
    try {
      await this._ws('hydrobalance/set_enabled', { enabled: next });
      this._toast(next ? 'Automatic watering enabled' : 'Automatic watering disabled');
      await this._loadAll();
    } catch (e) { this._toast('Error: ' + (e.message || e)); }
  }

  async setRainDelay(days) {
    try {
      await this._ws('hydrobalance/set_rain_delay', { days });
      this._toast(days > 0 ? `Watering paused for ${days} day(s)` : 'Rain delay cleared');
      await this._loadAll();
    } catch (e) { this._toast('Error: ' + (e.message || e)); }
  }

  async resetDeficit(zoneId) {
    try {
      await this._ws('hydrobalance/reset_deficit', zoneId ? { zone_id: zoneId } : {});
      this._toast('Deficit reset');
      await this._loadAll();
    } catch (e) { this._toast('Error: ' + (e.message || e)); }
  }
}

customElements.define('hydrobalance-panel', HydroBalancePanel);
