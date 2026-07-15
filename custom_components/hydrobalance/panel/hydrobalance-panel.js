// HydroBalance panel — registered as panel_custom in HA, runs inside the HA
// frontend context so we get an authenticated `hass` object directly (no
// WebSocket auth dance, works inside the iOS app's WKWebView).

// ─── i18n catalog ──────────────────────────────────────────────────────────
// Keys are namespaced "section.key". English is the source of truth and the
// fallback for any missing translation. Add a new language by copying the
// `en` block, translating the values, and the panel picks it up automatically
// based on the user's HA locale (`hass.locale.language`).
const I18N = {
  en: {
    common: { close: 'Close', cancel: 'Cancel', save: 'Save', delete: 'Delete', loading: 'Loading…' },
    tabs: { dashboard: 'Dashboard', zones: 'Zones', settings: 'Settings' },
    header: { tagline: 'Smart Irrigation', support_btn: '♥ Support' },
    badges: {
      ok: 'OK', needs_water: 'Needs Water', saturated: 'Saturated',
      building: 'Building', watering: 'Watering', manual: 'Manual',
      pending_recalc: 'Pending recalc', soil_wet: 'Soil wet',
    },
    dashboard: {
      todays_data: "Today's Data",
      et: 'ET (mm)', rain: 'Rain (mm)', eff_rain: 'Eff. Rain (mm)',
      tmin: 'T min (°C)', tmax: 'T max (°C)', peak_uv: 'Peak UV',
      soil_moisture: 'Soil Moisture',
      zone_status: 'Zone Status',
      no_zones: 'No zones configured yet.',
      go_to_zones: 'Go to Zones tab to add watering zones.',
      recent_activity: 'Recent Activity',
      load_more: 'Load more',
      system: 'System',
      manual_water: 'Manual Water', stop_manual: 'Stop Manual',
      skip_next: 'Skip Next Watering', force_all: 'Force Water All',
      reset_all: 'Reset All Deficits',
    },
    settings: {
      weather_channels: 'Weather Channels',
      weather_intro: 'ET is calculated from the Primary weather channel. If it goes unavailable, values are read from the Secondary.',
      primary: 'Primary Weather Channel',
      secondary: 'Secondary Weather Channel',
      secondary_hint: '(optional fallback)',
      skip_rain: 'Skip watering when rain is forecast',
      save_weather: 'Save Weather Channels',
      soil_moisture_title: 'Soil Moisture Sensor',
      soil_moisture_intro: 'System-wide fallback. Used for zones without a local soil-moisture sensor. When measured moisture is above the threshold, ET is frozen and watering is skipped.',
      use_soil_moisture: 'Use soil-moisture sensor (off = pure ET model)',
      sensor_entity: 'Sensor Entity',
      threshold: 'Skip Threshold (% VWC)',
      save_soil: 'Save Soil Moisture',
      history_title: 'Activity History',
      history_intro: 'How long to keep the Recent Activity log. Older entries are pruned automatically.',
      history_retention: 'Keep history for (days)',
      save_history: 'Save History Settings',
      soil_strategy: 'Soil & Strategy',
      soil_type: 'Soil Type', strategy: 'Strategy',
    },
    support: {
      title: '♥ Thanks for considering!',
      body: 'HydroBalance is free & open source. A small tip keeps the late-night commits coming.',
      qr_hint: 'Scan with your phone — opens any banking app that supports payment links.',
    },
    health: { offline: 'sensor offline', stale_warn: 'values may be stale' },
  },
  ro: {
    common: { close: 'Închide', cancel: 'Anulează', save: 'Salvează', delete: 'Șterge', loading: 'Se încarcă…' },
    tabs: { dashboard: 'Tablou', zones: 'Zone', settings: 'Setări' },
    header: { tagline: 'Irigare Inteligentă', support_btn: '♥ Susține' },
    badges: {
      ok: 'OK', needs_water: 'Necesită apă', saturated: 'Saturat',
      building: 'Crește', watering: 'Udare în curs', manual: 'Manual',
      pending_recalc: 'Recalc. în așteptare', soil_wet: 'Sol ud',
    },
    dashboard: {
      todays_data: 'Date azi',
      et: 'ET (mm)', rain: 'Ploaie (mm)', eff_rain: 'Ploaie ef. (mm)',
      tmin: 'T min (°C)', tmax: 'T max (°C)', peak_uv: 'UV maxim',
      soil_moisture: 'Umiditate sol',
      zone_status: 'Stare zone',
      no_zones: 'Nicio zonă configurată.',
      go_to_zones: 'Adaugă o zonă din tab-ul Zone.',
      recent_activity: 'Activitate recentă',
      load_more: 'Încarcă mai mult',
      system: 'Sistem',
      manual_water: 'Udare manuală', stop_manual: 'Oprește manual',
      skip_next: 'Sări peste următoarea udare', force_all: 'Forțează udarea tuturor',
      reset_all: 'Resetează toate deficitele',
    },
    settings: {
      weather_channels: 'Canale meteo',
      weather_intro: 'ET-ul se calculează din canalul Primar. Dacă pică, se citește din Secundar.',
      primary: 'Canal meteo primar',
      secondary: 'Canal meteo secundar',
      secondary_hint: '(rezervă opțională)',
      skip_rain: 'Sări peste udare când e prognozată ploaie',
      save_weather: 'Salvează canalele meteo',
      soil_moisture_title: 'Senzor umiditate sol',
      soil_moisture_intro: 'Rezervă la nivel de sistem. Folosit pentru zonele fără senzor local. Când umiditatea măsurată depășește pragul, ET-ul îngheață și udarea se sare.',
      use_soil_moisture: 'Folosește senzor de sol (off = model ET pur)',
      sensor_entity: 'Entitate senzor',
      threshold: 'Prag (% VWC)',
      save_soil: 'Salvează umiditatea solului',
      history_title: 'Istoric activitate',
      history_intro: 'Cât timp se păstrează jurnalul de activitate recentă. Intrările mai vechi sunt șterse automat.',
      history_retention: 'Păstrează istoricul (zile)',
      save_history: 'Salvează setările istoricului',
      soil_strategy: 'Sol & Strategie',
      soil_type: 'Tip sol', strategy: 'Strategie',
    },
    support: {
      title: '♥ Mulțumesc pentru gândul bun!',
      body: 'HydroBalance e gratuit și open-source. Un mic tip ajută la commits de noapte.',
      qr_hint: 'Scanează cu telefonul — deschide orice aplicație bancară cu plăți rapide.',
    },
    health: { offline: 'senzor offline', stale_warn: 'valorile pot fi vechi' },
  },
  de: {
    common: { close: 'Schließen', cancel: 'Abbrechen', save: 'Speichern', delete: 'Löschen', loading: 'Lädt…' },
    tabs: { dashboard: 'Übersicht', zones: 'Zonen', settings: 'Einstellungen' },
    header: { tagline: 'Smarte Bewässerung', support_btn: '♥ Unterstützen' },
    badges: {
      ok: 'OK', needs_water: 'Wasser nötig', saturated: 'Gesättigt',
      building: 'Steigt', watering: 'Bewässert', manual: 'Manuell',
      pending_recalc: 'Neuberechnung steht aus', soil_wet: 'Boden nass',
    },
    dashboard: {
      todays_data: 'Heutige Daten',
      et: 'ET (mm)', rain: 'Regen (mm)', eff_rain: 'Eff. Regen (mm)',
      tmin: 'T min (°C)', tmax: 'T max (°C)', peak_uv: 'UV max',
      soil_moisture: 'Bodenfeuchte',
      zone_status: 'Zonenstatus',
      no_zones: 'Noch keine Zonen konfiguriert.',
      go_to_zones: 'Im Tab Zonen eine Bewässerungszone hinzufügen.',
      recent_activity: 'Letzte Aktivität',
      load_more: 'Mehr laden',
      system: 'System',
      manual_water: 'Manuell bewässern', stop_manual: 'Manuell stoppen',
      skip_next: 'Nächste Bewässerung überspringen', force_all: 'Alle Zonen jetzt bewässern',
      reset_all: 'Alle Defizite zurücksetzen',
    },
    settings: {
      weather_channels: 'Wetterkanäle',
      weather_intro: 'Die ET wird aus dem Primärkanal berechnet. Wenn er nicht verfügbar ist, werden Werte aus dem Sekundärkanal gelesen.',
      primary: 'Primärer Wetterkanal',
      secondary: 'Sekundärer Wetterkanal',
      secondary_hint: '(optionaler Fallback)',
      skip_rain: 'Bewässerung überspringen, wenn Regen erwartet wird',
      save_weather: 'Wetterkanäle speichern',
      soil_moisture_title: 'Bodenfeuchtesensor',
      soil_moisture_intro: 'Systemweiter Fallback. Wird für Zonen ohne lokalen Bodenfeuchtesensor verwendet. Übersteigt die gemessene Feuchte den Schwellwert, wird die ET eingefroren und die Bewässerung übersprungen.',
      use_soil_moisture: 'Bodenfeuchtesensor verwenden (aus = reines ET-Modell)',
      sensor_entity: 'Sensor-Entität',
      threshold: 'Schwellwert (% VWC)',
      save_soil: 'Bodenfeuchte speichern',
      history_title: 'Aktivitätsverlauf',
      history_intro: 'Wie lange das Aktivitätsprotokoll aufbewahrt wird. Ältere Einträge werden automatisch entfernt.',
      history_retention: 'Verlauf aufbewahren (Tage)',
      save_history: 'Verlaufseinstellungen speichern',
      soil_strategy: 'Boden & Strategie',
      soil_type: 'Bodentyp', strategy: 'Strategie',
    },
    support: {
      title: '♥ Danke für die Überlegung!',
      body: 'HydroBalance ist kostenlos & Open Source. Ein kleiner Tipp hält die nächtlichen Commits am Laufen.',
      qr_hint: 'Mit dem Handy scannen — öffnet jede Banking-App, die Zahlungs-Links unterstützt.',
    },
    health: { offline: 'Sensor offline', stale_warn: 'Werte sind möglicherweise veraltet' },
  },
};

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
        <div class="version">v0.16.4 &mdash; <span data-i18n="header.tagline">Smart Irrigation</span></div>
      </div>
      <button class="btn btn-sm btn-outline" style="align-self:flex-start;" onclick="window.__hb.openSupportModal()" title="Support development" data-i18n="header.support_btn">&#9829; Support</button>
    </div>

    <div id="support-modal" class="modal-overlay hidden" onclick="window.__hb._supportBackdrop(event)">
      <div class="modal" style="max-width:340px;text-align:center;">
        <h2 style="margin:0 0 8px;" data-i18n="support.title">&#9829; Thanks for considering!</h2>
        <p style="font-size:0.9em;color:var(--text-secondary);margin:0 0 14px;" data-i18n="support.body">HydroBalance is free &amp; open source. A small tip keeps the late-night commits coming.</p>
        <a class="btn btn-primary" href="https://revolut.me/lucian448" target="_blank" rel="noopener" style="display:block;margin-bottom:12px;">Revolut &mdash; lucian448</a>
        <div style="background:white;padding:10px;border-radius:8px;display:inline-block;">
          <img src="https://api.qrserver.com/v1/create-qr-code/?size=200x200&amp;data=https%3A%2F%2Frevolut.me%2Flucian448" alt="Revolut QR" width="180" height="180" style="display:block;" />
        </div>
        <p style="font-size:0.75em;color:var(--text-secondary);margin:8px 0 0;" data-i18n="support.qr_hint">Scan with your phone &mdash; opens any banking app that supports payment links.</p>
        <div style="margin-top:14px;">
          <button class="btn btn-outline btn-sm" onclick="window.__hb.closeSupportModal()" data-i18n="common.close">Close</button>
        </div>
      </div>
    </div>

    <datalist id="dl-switches"></datalist>
    <datalist id="dl-sensors"></datalist>
    <datalist id="dl-weather"></datalist>

    <div class="tabs">
      <button class="tab active" data-tab="dashboard" onclick="window.__hb.showTab('dashboard')" data-i18n="tabs.dashboard">Dashboard</button>
      <button class="tab" data-tab="zones" onclick="window.__hb.showTab('zones')" data-i18n="tabs.zones">Zones</button>
      <button class="tab" data-tab="settings" onclick="window.__hb.showTab('settings')" data-i18n="tabs.settings">Settings</button>
    </div>

    <div id="tab-dashboard">
      <div class="card hidden" id="sensor-health-card" style="border-left:4px solid var(--danger);">
        <h2 id="sensor-health-title" style="margin:0 0 4px;font-size:1.05em;">&#9888; Sensors offline</h2>
        <div id="sensor-health-body" style="font-size:0.85em;color:var(--text-secondary);"></div>
      </div>

      <div class="card">
        <h2 data-i18n="dashboard.todays_data">Today's Data</h2>
        <div class="status-grid">
          <div class="stat-box"><div class="value" id="stat-et">--</div><div class="label" data-i18n="dashboard.et">ET (mm)</div></div>
          <div class="stat-box"><div class="value" id="stat-rain">--</div><div class="label" data-i18n="dashboard.rain">Rain (mm)</div></div>
          <div class="stat-box"><div class="value" id="stat-effrain">--</div><div class="label" data-i18n="dashboard.eff_rain">Eff. Rain (mm)</div></div>
          <div class="stat-box"><div class="value" id="stat-tmin">--</div><div class="label" data-i18n="dashboard.tmin">T min (&deg;C)</div></div>
          <div class="stat-box"><div class="value" id="stat-tmax">--</div><div class="label" data-i18n="dashboard.tmax">T max (&deg;C)</div></div>
          <div class="stat-box"><div class="value" id="stat-uv">--</div><div class="label" data-i18n="dashboard.peak_uv">Peak UV</div></div>
        </div>
      </div>

      <div class="card hidden" id="soil-moisture-card">
        <h2 data-i18n="dashboard.soil_moisture">Soil Moisture</h2>
        <div style="display:flex;justify-content:space-between;align-items:baseline;">
          <span id="soil-moisture-value" style="font-size:1.6em;font-weight:700;">--</span>
          <span id="soil-moisture-meta" style="font-size:0.85em;color:var(--text-secondary);"></span>
        </div>
      </div>

      <div class="card">
        <h2 data-i18n="dashboard.zone_status">Zone Status</h2>
        <div id="zone-status-list"><div class="loading" data-i18n="common.loading">Loading...</div></div>
      </div>

      <div class="card">
        <h2 data-i18n="dashboard.recent_activity">Recent Activity</h2>
        <div id="activity-list"><div class="empty-state"><p>No activity yet.</p></div></div>
        <div class="actions" style="margin-top:8px;">
          <button id="activity-load-more" class="btn btn-outline btn-sm hidden" onclick="window.__hb.loadMoreActivity()" data-i18n="dashboard.load_more">Load more</button>
        </div>
      </div>

      <div class="card">
        <h2 data-i18n="dashboard.system">System</h2>
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
          <button class="btn btn-warning" onclick="window.__hb.skipDay()" data-i18n="dashboard.skip_next">Skip Next Watering</button>
          <button class="btn btn-primary" onclick="window.__hb.forceWater()" data-i18n="dashboard.force_all">Force Water All</button>
          <button class="btn btn-outline" onclick="window.__hb.resetDeficit()" data-i18n="dashboard.reset_all">Reset All Deficits</button>
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
        <h2 data-i18n="settings.weather_channels">Weather Channels</h2>
        <p style="font-size:0.85em;color:var(--text-secondary);margin-bottom:12px;" data-i18n="settings.weather_intro">
          ET is calculated from the Primary weather channel. If it goes unavailable,
          values are read from the Secondary.
        </p>
        <div class="form-group">
          <label data-i18n="settings.primary">Primary Weather Channel</label>
          <select id="weather-primary-picker" onchange="window.__hb._onWeatherPickerChange('primary')" style="margin-bottom:6px;"></select>
          <input type="text" id="weather-primary" list="dl-weather" placeholder="weather.openweathermap" autocapitalize="off" autocomplete="off" oninput="window.__hb._refreshWeatherPreview('primary')">
          <div id="weather-primary-setup" class="hidden" style="margin-top:6px;padding:10px 12px;border-radius:8px;background:rgba(255,165,0,0.08);border-left:3px solid var(--warning, #e65100);font-size:0.85em;"></div>
          <div id="weather-primary-preview" style="margin-top:6px;padding:8px 10px;border-radius:8px;background:rgba(0,0,0,0.04);"></div>
        </div>
        <div class="form-group">
          <label><span data-i18n="settings.secondary">Secondary Weather Channel</span> <span style="opacity:0.6;font-weight:normal;" data-i18n="settings.secondary_hint">(optional fallback)</span></label>
          <select id="weather-secondary-picker" onchange="window.__hb._onWeatherPickerChange('secondary')" style="margin-bottom:6px;"></select>
          <input type="text" id="weather-secondary" list="dl-weather" placeholder="weather.pirateweather" autocapitalize="off" autocomplete="off" oninput="window.__hb._refreshWeatherPreview('secondary')">
          <div id="weather-secondary-setup" class="hidden" style="margin-top:6px;padding:10px 12px;border-radius:8px;background:rgba(255,165,0,0.08);border-left:3px solid var(--warning, #e65100);font-size:0.85em;"></div>
          <div id="weather-secondary-preview" style="margin-top:6px;padding:8px 10px;border-radius:8px;background:rgba(0,0,0,0.04);"></div>
        </div>
        <div class="form-group" style="display:flex;align-items:center;gap:8px;">
          <input type="checkbox" id="use-forecast" style="width:auto;">
          <label for="use-forecast" style="margin:0;" data-i18n="settings.skip_rain">Skip watering when rain is forecast</label>
        </div>
        <div class="actions">
          <button class="btn btn-primary" onclick="window.__hb.saveWeatherChannels()" data-i18n="settings.save_weather">Save Weather Channels</button>
        </div>
      </div>

      <div class="card">
        <h2 data-i18n="settings.soil_moisture_title">Soil Moisture Sensor</h2>
        <p style="font-size:0.85em;color:var(--text-secondary);margin-bottom:12px;" data-i18n="settings.soil_moisture_intro">
          System-wide fallback. Used for zones that don't have their own local soil-moisture
          sensor (configured in the zone editor). When measured moisture is above the threshold,
          ET is frozen and watering is skipped.
        </p>
        <div class="form-group" style="display:flex;align-items:center;gap:8px;">
          <input type="checkbox" id="use-soil-moisture" style="width:auto;">
          <label for="use-soil-moisture" style="margin:0;" data-i18n="settings.use_soil_moisture">Use soil-moisture sensor (off = pure ET model)</label>
        </div>
        <div class="form-group">
          <label data-i18n="settings.sensor_entity">Sensor Entity</label>
          <input type="text" id="soil-moisture-sensor" list="dl-sensors" placeholder="sensor.garden_sensor_soil_moisture" autocapitalize="off" autocomplete="off">
        </div>
        <div class="form-group">
          <label data-i18n="settings.threshold">Skip Threshold (% VWC)</label>
          <input type="number" id="moisture-threshold" value="40" step="1" min="0" max="100">
        </div>
        <div class="actions">
          <button class="btn btn-primary" onclick="window.__hb.saveMoistureConfig()" data-i18n="settings.save_soil">Save Soil Moisture</button>
        </div>
      </div>

      <div class="card">
        <h2 data-i18n="settings.soil_strategy">Soil &amp; Strategy</h2>
        <div class="form-row">
          <div class="form-group">
            <label data-i18n="settings.soil_type">Soil Type</label>
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

      <div class="card">
        <h2 data-i18n="settings.history_title">Activity History</h2>
        <p style="font-size:0.85em;color:var(--text-secondary);margin-bottom:12px;" data-i18n="settings.history_intro">
          How long to keep the Recent Activity log. Older entries are pruned automatically.
        </p>
        <div class="form-group">
          <label data-i18n="settings.history_retention">Keep history for (days)</label>
          <input type="number" id="history-retention" value="30" step="1" min="1" max="3650">
        </div>
        <div class="actions">
          <button class="btn btn-primary" onclick="window.__hb.saveHistoryConfig()" data-i18n="settings.save_history">Save History Settings</button>
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

        <fieldset style="border:1px solid var(--border);border-radius:8px;padding:12px;margin-top:8px;">
          <legend style="font-size:0.9em;padding:0 6px;">Local Sensors <span style="opacity:0.6;font-weight:normal;">(optional)</span></legend>
          <p style="margin:0 0 10px;font-size:0.8em;opacity:0.75;">Per-zone overrides. When set, the zone uses these instead of the weather channels for ET. Live values shown after the field updates.</p>
          <div class="form-group">
            <label>Local Temperature</label>
            <input type="text" id="zone-local-temp" list="dl-sensors" placeholder="e.g. sensor.front_garden_temp" autocapitalize="off" autocomplete="off" oninput="window.__hb._refreshLocalPreview('temp')">
            <div id="zone-local-temp-preview" style="margin-top:4px;font-size:0.8em;"></div>
          </div>
          <div class="form-group">
            <label>Local Humidity</label>
            <input type="text" id="zone-local-humidity" list="dl-sensors" placeholder="e.g. sensor.front_garden_humidity" autocapitalize="off" autocomplete="off" oninput="window.__hb._refreshLocalPreview('humidity')">
            <div id="zone-local-humidity-preview" style="margin-top:4px;font-size:0.8em;"></div>
          </div>
          <div class="form-group">
            <label>Local Soil Moisture</label>
            <input type="text" id="zone-local-soil" list="dl-sensors" placeholder="e.g. sensor.front_garden_soil_moisture" autocapitalize="off" autocomplete="off" oninput="window.__hb._refreshLocalPreview('soil')">
            <div id="zone-local-soil-preview" style="margin-top:4px;font-size:0.8em;"></div>
          </div>
        </fieldset>

        <div class="actions">
          <button class="btn btn-outline" onclick="window.__hb.closeZoneModal()">Cancel</button>
          <button class="btn btn-danger hidden" id="zone-delete-btn" onclick="window.__hb.deleteZone()">Delete</button>
          <button class="btn btn-primary" onclick="window.__hb.saveZone()">Save Zone</button>
        </div>
      </div>
    </div>

    <div id="manual-modal" class="modal-overlay hidden" onclick="window.__hb._manualBackdrop(event)">
      <div class="modal" style="max-width:420px;">
        <h2 id="manual-modal-title">Manual water</h2>
        <p id="manual-modal-info" style="margin:0 0 12px;font-size:0.85em;color:var(--text-secondary);"></p>
        <input type="hidden" id="manual-modal-zone">
        <label style="font-size:0.85em;color:var(--text-secondary);">Quick pick</label>
        <div id="manual-chips" style="display:flex;flex-wrap:wrap;gap:8px;margin:6px 0 16px;"></div>
        <div class="form-group">
          <label>Custom duration (min)</label>
          <input type="number" id="manual-custom-min" min="1" step="1" placeholder="e.g. 12">
        </div>
        <div class="actions" style="flex-wrap:wrap;gap:8px;">
          <button class="btn btn-outline" onclick="window.__hb.closeManualModal()">Cancel</button>
          <button class="btn btn-outline" onclick="window.__hb.startManualOpen()">Until I stop</button>
          <button class="btn btn-primary" onclick="window.__hb.startManualCustom()">Start</button>
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
      this._applyI18n();
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

  // ─── i18n ───────────────────────────────────────────────────────────────
  _lang() {
    const code = (this._hass && this._hass.locale && this._hass.locale.language) || 'en';
    const base = String(code).toLowerCase().split('-')[0];
    return I18N[base] ? base : 'en';
  }

  t(key, vars = {}) {
    const lookup = (lang) => {
      let v = I18N[lang];
      for (const p of key.split('.')) {
        if (v && typeof v === 'object') v = v[p];
        else return undefined;
      }
      return v;
    };
    let val = lookup(this._lang());
    if (val === undefined) val = lookup('en');
    if (typeof val !== 'string') return key;  // missing → show key for debugging
    return val.replace(/\{(\w+)\}/g, (_, n) => (vars[n] != null ? String(vars[n]) : `{${n}}`));
  }

  _applyI18n() {
    // Walk the shadow DOM and replace text content of any element with a
    // data-i18n="namespace.key" attribute. Re-runnable; called after the
    // template is mounted and whenever the locale changes.
    const nodes = this.shadowRoot.querySelectorAll('[data-i18n]');
    nodes.forEach(el => {
      const key = el.getAttribute('data-i18n');
      if (!key) return;
      el.textContent = this.t(key);
    });
  }

  _fmtMinutes(min) {
    if (min == null || isNaN(min)) return '—';
    if (min < 60) return `${Math.round(min)} min`;
    const h = Math.floor(min / 60);
    const m = Math.round(min - h * 60);
    return `${h}h${String(m).padStart(2, '0')}`;
  }

  _renderLiveDeficit(live, committed) {
    if (live == null || live === committed) return '';
    const tip = 'Live estimate — hybrid of running Tmin/Tmax (primary) and forecast Tmax (fill-in early morning), scaled by an ET diurnal curve. Replaced by the real value at 23:00.';
    return ` <span title="${this._esc(tip)}" style="font-size:0.85em;opacity:0.65;font-weight:normal;">~ ${live} live</span>`;
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
  _renderSensorHealth(health) {
    const card = this.$('sensor-health-card');
    const title = this.$('sensor-health-title');
    const body = this.$('sensor-health-body');
    const issues = (health && health.issues) || [];

    if (issues.length === 0) {
      card.classList.add('hidden');
      return;
    }
    card.classList.remove('hidden');

    const sev = (i) => i.severity || 'info';
    const order = { critical: 0, warning: 1, info: 2 };
    const sorted = [...issues].sort((a, b) => (order[sev(a)] ?? 9) - (order[sev(b)] ?? 9));
    const top = sev(sorted[0]);
    const color = top === 'critical' ? 'var(--danger)' : top === 'warning' ? 'var(--warning, #e65100)' : 'var(--primary)';
    card.style.borderLeftColor = color;

    const icon = top === 'critical' ? '&#9888;' : top === 'warning' ? '&#9888;' : '&#9432;';
    const count = issues.length;
    title.innerHTML = `${icon} Sensor health &mdash; ${count} issue${count > 1 ? 's' : ''}`;

    body.innerHTML = sorted.map(i => {
      const dot = sev(i) === 'critical' ? 'var(--danger)' : sev(i) === 'warning' ? 'var(--warning, #e65100)' : 'var(--primary)';
      return `<div style="display:flex;gap:8px;align-items:flex-start;margin-top:2px;">
        <span style="color:${dot};">&#9679;</span>
        <span>${this._esc(i.message)}</span>
      </div>`;
    }).join('');
  }

  _renderDashboard() {
    if (!this._currentEntryId || !this._status[this._currentEntryId]) return;
    const s = this._status[this._currentEntryId];
    const daily = s.daily || {};

    this._renderSensorHealth(s.sensor_health || {});

    this.$('stat-et').textContent = daily.et != null ? daily.et : '--';
    this.$('stat-rain').textContent = daily.rain_accumulated != null ? daily.rain_accumulated : '--';
    // Eff. Rain shows the live projection (what would be applied to deficits
    // if 23:00 ran right now) so heavy rain is reflected immediately. The
    // committed value goes back to being shown after the rain accumulator
    // resets at midnight.
    const effLive = daily.effective_rain_live;
    const effCommitted = daily.effective_rain;
    const effDisplay = (effLive != null && effLive > 0) ? effLive : (effCommitted != null ? effCommitted : '--');
    this.$('stat-effrain').textContent = effDisplay;
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

    const cfg = this._config[this._currentEntryId] || {};
    const moistureThreshold = soil.skip_threshold ?? 40;
    const wetSoil = (cfg.use_soil_moisture !== false)
      && soil.moisture != null
      && soil.moisture > moistureThreshold;

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

      // Projected run time at the current deficit (matches coordinator's
      // mm_to_apply = min(deficit, max_per_cycle); minutes = mm/rate × 30, min 1).
      const cfg = zdata.config || {};
      const rate = Number(cfg.sprinkler_rate) || 2.0;
      const maxPer = Number(cfg.max_per_cycle) || 5;
      const pulseMin = Number(cfg.pulse_minutes) || 0;
      const soakMin = Number(cfg.soak_minutes) || 0;
      const mmToApply = deficit > 0 ? Math.min(deficit, maxPer) : 0;
      let runFmt = '—';
      let runTitle = 'No water needed';
      if (mmToApply > 0) {
        const runMin = Math.max(1, (mmToApply / rate) * 30);
        runFmt = this._fmtMinutes(runMin);
        runTitle = `${mmToApply.toFixed(1)} mm @ ${rate} mm/30min`;
        if (pulseMin > 0 && soakMin > 0 && runMin > pulseMin) {
          const pulses = Math.ceil(runMin / pulseMin);
          const wallMin = runMin + (pulses - 1) * soakMin;
          runTitle += ` — ${pulses}× cycle&soak ≈ ${this._fmtMinutes(wallMin)} wall-clock`;
        }
      }

      // Badge prefers the live deficit when it disagrees with the committed
      // one — e.g. heavy rain pours after 23:00's calc, committed still shows
      // "Needs Water" but live drops to saturated. Show "Saturated" instead of
      // a misleading red badge.
      const liveDef = zdata.water_deficit_live;
      let badgeClass = 'badge-ok', badgeText = this.t('badges.ok');
      if (manualActive) { badgeClass = 'badge-active'; badgeText = this.t('badges.manual'); }
      else if (zoneStatus === 'watering') { badgeClass = 'badge-active'; badgeText = this.t('badges.watering'); }
      else if (liveDef != null && liveDef < 0) { badgeClass = 'badge-ok'; badgeText = this.t('badges.saturated'); }
      else if (zoneStatus === 'needs_water') {
        if (liveDef != null && liveDef <= threshold) {
          badgeClass = 'badge-warning'; badgeText = this.t('badges.pending_recalc');
        } else {
          badgeClass = 'badge-danger'; badgeText = this.t('badges.needs_water');
        }
      }
      else if (deficit > threshold * 0.7) { badgeClass = 'badge-warning'; badgeText = this.t('badges.building'); }

      const pct = Math.min(100, Math.max(0, (deficit / threshold) * 100));
      const barColor = pct > 80 ? 'var(--danger)' : pct > 50 ? 'var(--warning)' : 'var(--success)';

      const manualEnds = zdata.manual_ends || '';
      const cron = manualActive
        ? `<span class="hb-cron" data-start="${this._esc(manualStarted)}" data-end="${this._esc(manualEnds)}" style="font-variant-numeric:tabular-nums;color:var(--danger);font-weight:600;">00:00</span>${manualEnds ? '<span style="font-size:0.75em;color:var(--text-secondary);margin-left:6px;">left</span>' : ''}`
        : '';

      html += `
        <div class="zone-card">
          <div class="zone-header">
            <span class="zone-name">${this._esc(zoneName)}</span>
            <span>
              ${wetSoil ? `<span class="badge badge-ok" title="Soil moisture above threshold — ET frozen, only rain adjusts the deficit">${this.t('badges.soil_wet')}</span> ` : ''}
              <span class="badge ${badgeClass}">${badgeText}</span>
            </span>
          </div>
          <div class="zone-stats">
            <span title="Committed deficit — set by the 23:00 daily calc, drives watering decisions.">Deficit: <strong>${deficit} mm</strong>${this._renderLiveDeficit(zdata.water_deficit_live, deficit)}</span>
            <span>Sun: <strong>${sunCoeff}</strong></span>
            <span>Threshold: ${threshold} mm</span>
            <span title="${this._esc(runTitle)}">Run: <strong>${runFmt}</strong></span>
            <span>Used: <strong>${waterUsed} mm</strong></span>
            <span>Last: ${this._esc(lastWatered)}</span>
          </div>
          <div class="progress-bar">
            <div class="fill" style="width:${pct}%;background:${barColor}"></div>
          </div>
          <div style="margin-top:12px;display:flex;gap:8px;align-items:center;">
            <button class="btn btn-sm ${manualActive ? 'btn-danger' : 'btn-outline'}"
              onclick="window.__hb.${manualActive ? `manualWater('${this._esc(zid)}', false)` : `openManualModal('${this._esc(zid)}')`}">
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

    // When active, show the dynamically-computed next start (and estimated
    // finish). The start is back-solved at the 23:00 calc so watering ends by
    // the target time; sunrise−1h caps it, an early floor guards the bottom.
    let nextTxt = '';
    if (enabled && !delayActive && sys.next_watering) {
      const start = new Date(sys.next_watering);
      const mins = Number(sys.next_watering_minutes) || 0;
      const hhmm = (d) => d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      const finishTxt = mins > 0
        ? ` → done ~${hhmm(new Date(start.getTime() + mins * 60000))}`
        : '';
      nextTxt = `<div style="margin-top:4px;font-size:0.85em;color:var(--text-secondary);">Next start: <strong>${this._esc(hhmm(start))}</strong>${finishTxt}</div>`;
    }
    statusEl.innerHTML = `<span style="font-weight:600;color:${color};">${this._esc(msg)}</span>${nextTxt}`;

    toggleBtn.textContent = enabled ? 'Disable Watering' : 'Enable Watering';
    toggleBtn.classList.toggle('btn-danger', enabled);
    toggleBtn.classList.toggle('btn-primary', !enabled);
    toggleBtn.classList.toggle('btn-outline', false);

    this.$('clear-delay-btn').classList.toggle('hidden', !delayActive);
  }

  _renderActivity(events) {
    this._statusEvents = events || [];
    if (this._actShown == null) this._actShown = 20;
    // Once the full on-disk log has been pulled, keep showing it but splice in
    // any newer events the status poll has picked up since, so a live watering
    // still appears at the top.
    if (this._historyLoaded && this._historyEvents && this._historyEvents.length) {
      const newest = this._historyEvents[0].time || '';
      const fresh = this._statusEvents.filter(e => (e.time || '') > newest);
      if (fresh.length) this._historyEvents = fresh.concat(this._historyEvents);
    }
    this._renderActivityList();
  }

  _activitySource() {
    return (this._historyLoaded && this._historyEvents)
      ? this._historyEvents
      : (this._statusEvents || []);
  }

  _renderActivityList() {
    const container = this.$('activity-list');
    if (!container) return;
    const source = this._activitySource();
    if (!source.length) {
      container.innerHTML = '<div class="empty-state"><p>No activity yet.</p></div>';
      this._updateLoadMore();
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
    for (const ev of source.slice(0, this._actShown)) {
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
    this._updateLoadMore();
  }

  _updateLoadMore() {
    const btn = this.$('activity-load-more');
    if (!btn) return;
    const source = this._activitySource();
    const moreInSource = this._actShown < source.length;
    // The status payload is capped at 100; if we've hit that and haven't yet
    // pulled the full log, there may be older entries on disk.
    const maybeMoreOnDisk = !this._historyLoaded && (this._statusEvents || []).length >= 100;
    btn.classList.toggle('hidden', !(moreInSource || maybeMoreOnDisk));
  }

  async loadMoreActivity() {
    // If we're about to run past the capped status payload, pull the full log.
    const needDisk = !this._historyLoaded
      && (this._actShown + 20) >= (this._statusEvents || []).length
      && (this._statusEvents || []).length >= 100;
    if (needDisk) {
      try {
        const res = await this._ws('hydrobalance/history', {});
        const all = (res && res[this._currentEntryId]) || [];
        this._historyEvents = all;
        this._historyLoaded = true;
      } catch (e) {
        this._toast('Error: ' + (e.message || e));
      }
    }
    this._actShown += 20;
    this._renderActivityList();
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
      const end = sp.dataset.end ? Date.parse(sp.dataset.end) : NaN;
      let sec;
      if (!isNaN(end)) {
        sec = Math.max(0, Math.floor((end - now) / 1000));
        // Countdown hit zero — HA finalises around the same instant, but the
        // panel keeps the stale "Stop Manual" red button until something polls.
        // Trigger a one-shot refresh (debounced via _fired) with a small grace
        // so the server-side auto-stop has definitely landed.
        if (sec === 0 && !sp._fired) {
          sp._fired = true;
          setTimeout(() => this._loadAll(), 1500);
        }
      } else {
        const start = Date.parse(sp.dataset.start);
        if (isNaN(start)) return;
        sec = Math.max(0, Math.floor((now - start) / 1000));
      }
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

    this.$('weather-primary').value = (entry && entry.weather_primary) || (entry && entry.weather_entity) || '';
    this.$('weather-secondary').value = (entry && entry.weather_secondary) || '';
    this.$('use-forecast').checked = !(entry && entry.use_forecast === false);
    this._populatePicker('dl-weather', 'weather');
    this._populateProviderPicker('primary');
    this._populateProviderPicker('secondary');
    this._refreshWeatherPreview('primary');
    this._refreshWeatherPreview('secondary');

    this.$('soil-type').value = (entry && entry.soil_type) || 'clay';
    this.$('strategy').value = (entry && entry.strategy) || 'balanced';

    const sensors = (entry && entry.sensors) || {};
    this.$('use-soil-moisture').checked = !(entry && entry.use_soil_moisture === false);
    this.$('soil-moisture-sensor').value = sensors.sensor_soil_moisture || '';
    this.$('moisture-threshold').value = (entry && entry.moisture_skip_threshold != null) ? entry.moisture_skip_threshold : 40;
    const retentionEl = this.$('history-retention');
    if (retentionEl) retentionEl.value = (entry && entry.history_retention_days != null) ? entry.history_retention_days : 30;
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
      const ls = zone.local_sensors || {};
      this.$('zone-local-temp').value = ls.temperature || '';
      this.$('zone-local-humidity').value = ls.humidity || '';
      this.$('zone-local-soil').value = ls.soil_moisture || '';
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
      this.$('zone-local-temp').value = '';
      this.$('zone-local-humidity').value = '';
      this.$('zone-local-soil').value = '';
    }
    this.toggleSunFields();
    this.toggleCycleSoakFields();
    this._populatePicker('dl-switches', 'switch');
    this._populatePicker('dl-sensors', 'sensor');
    this._refreshLocalPreview('temp');
    this._refreshLocalPreview('humidity');
    this._refreshLocalPreview('soil');
    this.$('zone-modal').classList.remove('hidden');
  }

  _refreshLocalPreview(which) {
    const map = {
      temp: { input: 'zone-local-temp', preview: 'zone-local-temp-preview', unit: '°C' },
      humidity: { input: 'zone-local-humidity', preview: 'zone-local-humidity-preview', unit: '%' },
      soil: { input: 'zone-local-soil', preview: 'zone-local-soil-preview', unit: '%' },
    };
    const cfg = map[which];
    if (!cfg) return;
    const el = this.$(cfg.preview);
    if (!el) return;
    const entityId = this.$(cfg.input).value.trim();
    if (!entityId) {
      el.innerHTML = '<span style="opacity:0.6;font-style:italic;">No local sensor — uses weather channels.</span>';
      return;
    }
    const state = this._hass && this._hass.states[entityId];
    if (!state) {
      el.innerHTML = `<span style="color:var(--danger);">&#9888; ${this._esc(entityId)} not found</span>`;
      return;
    }
    if (state.state === 'unavailable' || state.state === 'unknown') {
      el.innerHTML = `<span style="color:var(--danger);">&#9888; unavailable</span>`;
      return;
    }
    el.innerHTML = `<span style="color:var(--success);">&#10003; <strong>${this._esc(state.state)} ${cfg.unit}</strong></span>`;
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

    const localSensors = {};
    const lt = this.$('zone-local-temp').value.trim();
    const lh = this.$('zone-local-humidity').value.trim();
    const ls = this.$('zone-local-soil').value.trim();
    if (lt) localSensors.temperature = lt;
    if (lh) localSensors.humidity = lh;
    if (ls) localSensors.soil_moisture = ls;
    if (Object.keys(localSensors).length > 0) zone.local_sensors = localSensors;

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
        use_soil_moisture: this.$('use-soil-moisture').checked,
      });
      this._toast('Soil moisture settings saved!');
      await this._loadAll();
    } catch (e) {
      this._toast('Error: ' + (e.message || e));
    }
  }

  async saveHistoryConfig() {
    let days = parseInt(this.$('history-retention').value, 10);
    if (isNaN(days) || days < 1) days = 30;
    try {
      await this._ws('hydrobalance/config/save', {
        entry_id: this._currentEntryId,
        history_retention_days: days,
      });
      this._toast('History settings saved!');
      await this._loadAll();
    } catch (e) {
      this._toast('Error: ' + (e.message || e));
    }
  }

  async saveWeatherChannels() {
    const primary = this.$('weather-primary').value.trim();
    const secondary = this.$('weather-secondary').value.trim();
    try {
      await this._ws('hydrobalance/config/save', {
        entry_id: this._currentEntryId,
        weather_primary: primary || null,
        weather_secondary: secondary || null,
        use_forecast: this.$('use-forecast').checked,
      });
      this._toast('Weather channels saved!');
      await this._loadAll();
    } catch (e) {
      this._toast('Error: ' + (e.message || e));
    }
  }

  _refreshWeatherPreview(which) {
    const inputId = which === 'primary' ? 'weather-primary' : 'weather-secondary';
    const previewId = which === 'primary' ? 'weather-primary-preview' : 'weather-secondary-preview';
    const el = this.$(previewId);
    if (!el) return;
    const entityId = this.$(inputId).value.trim();
    if (!entityId) {
      el.innerHTML = '<span style="opacity:0.6;font-style:italic;font-size:0.85em;">No channel set.</span>';
      return;
    }
    const state = this._hass && this._hass.states[entityId];
    if (!state || state.state === 'unavailable' || state.state === 'unknown') {
      el.innerHTML = `<span style="color:var(--danger);font-size:0.85em;">&#9888; ${this._esc(entityId)} unavailable</span>`;
      return;
    }
    const a = state.attributes || {};
    const fmt = (v, unit) => (v == null || v === '') ? '—' : `${v}${unit ? ' ' + unit : ''}`;
    // UV is rarely on the weather entity itself — try attribute aliases, then
    // fall back to a sibling sensor named after the weather entity (works for
    // OpenWeatherMap, Met.no and similar integrations).
    let uv = a.uv_index ?? a.uvi ?? a.uv;
    if (uv == null && entityId.includes('.')) {
      const stem = entityId.split('.', 2)[1];
      const sibling = this._hass.states[`sensor.${stem}_uv_index`];
      if (sibling && sibling.state !== 'unavailable' && sibling.state !== 'unknown') {
        uv = sibling.state;
      }
    }
    const rainNowId = `${previewId}-rain-now`;
    const rain24hId = `${previewId}-rain-24h`;
    el.innerHTML = `
      <div style="font-size:0.85em;">
        <div style="margin-bottom:4px;"><strong>${this._esc(state.state)}</strong>
          <span style="opacity:0.7;margin-left:6px;">${this._esc(a.friendly_name || entityId)}</span></div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:2px 12px;">
          <span>Temp: <strong>${fmt(a.temperature, '°C')}</strong></span>
          <span>Humidity: <strong>${fmt(a.humidity, '%')}</strong></span>
          <span>Wind: <strong>${fmt(a.wind_speed, 'km/h')}</strong></span>
          <span>UV: <strong>${fmt(uv)}</strong></span>
          <span>Pressure: <strong>${fmt(a.pressure, 'hPa')}</strong></span>
          <span>Cloud: <strong>${fmt(a.cloud_coverage, '%')}</strong></span>
          <span title="Current precipitation reported on the weather entity (when supported by the integration).">Rain now: <strong id="${rainNowId}">${fmt(a.precipitation, 'mm/h')}</strong></span>
          <span title="Sum of next 24h precipitation from the daily forecast — what the rain-forecast skip checks against.">Rain 24h: <strong id="${rain24hId}">…</strong></span>
        </div>
      </div>`;
    // Fetch forecast asynchronously and patch the rain-24h cell when it arrives.
    this._fillForecastRain(entityId, rain24hId);
  }

  async _fillForecastRain(entityId, targetElId) {
    let mm = null;
    try {
      const r = await this._hass.callService(
        'weather', 'get_forecasts',
        { entity_id: entityId, type: 'daily' },
        undefined, true, true,
      );
      const fc = ((r && r.response) || {})[entityId];
      const list = (fc && fc.forecast) || [];
      if (list.length > 0) {
        const p = list[0].precipitation;
        if (p != null) mm = Number(p);
      }
    } catch (_) { /* leave as — */ }
    const el = this.$(targetElId);
    if (!el) return;
    el.textContent = mm == null || isNaN(mm) ? '—' : `${mm.toFixed(1)} mm`;
  }

  // ─── Weather provider picker ─────────────────────────────────────────────
  // Top 5 most-used weather integrations in HA. Detected first from the
  // entity registry (most reliable — uses the integration's domain), then by
  // attribution as fallback for HA versions where hass.entities isn't exposed
  // to custom panels.
  get _PROVIDERS() {
    return {
      openweathermap: {
        name: 'OpenWeatherMap',
        attribution: 'openweathermap',
        platform: 'openweathermap',
        free: 'Free 1000 calls/day',
        // UV lives on a sibling sensor.openweathermap_uv_index, which we auto-pick.
        limitation: null,
        steps: [
          'Sign up at <a href="https://home.openweathermap.org/users/sign_up" target="_blank" rel="noopener">openweathermap.org</a> (free)',
          'Get your API key from <em>API keys</em> tab (takes ~2h to activate)',
          'HA: Settings → Devices & Services → Add Integration → <strong>OpenWeatherMap</strong>',
          'Paste the API key and save',
        ],
      },
      pirateweather: {
        name: 'Pirate Weather',
        attribution: 'pirate weather',
        platform: 'pirateweather',
        free: 'Free 10,000 calls/month',
        limitation: 'No UV index exposed (neither as attribute nor sibling sensor) — ET falls back to peak UV from primary, or 0.',
        steps: [
          'Sign up at <a href="https://pirateweather.net" target="_blank" rel="noopener">pirateweather.net</a> (Dark Sky successor)',
          'Get API key from your account dashboard',
          'HA: Settings → Devices & Services → Add → <strong>Pirate Weather</strong>',
          'Paste API key, save',
        ],
      },
      met: {
        name: 'Met.no (Norway)',
        attribution: 'met.no',
        platform: 'met',
        free: 'Completely free, no API key needed',
        // Best attribute coverage of all — has UV index directly.
        limitation: null,
        steps: [
          'No account required',
          'HA: Settings → Devices & Services → Add Integration → <strong>Met.no</strong>',
          'Save (uses your HA location automatically)',
        ],
      },
      openmeteo: {
        name: 'Open-Meteo',
        attribution: 'open-meteo',
        platform: 'openmeteo',
        free: 'Completely free, no API key, no signup',
        limitation: 'Limited integration — only temperature + wind on the weather entity. No humidity / UV / pressure / cloud. Best as fallback, not primary.',
        steps: [
          'No account required',
          'HA: Settings → Devices & Services → Add Integration → <strong>Open-Meteo</strong>',
          'Save (uses your HA location)',
        ],
      },
      accuweather: {
        name: 'AccuWeather',
        attribution: 'accuweather',
        platform: 'accuweather',
        free: 'Free 50 calls/day',
        limitation: 'Free tier is only 50 calls/day — HydroBalance polls every 15 min (~96/day), so you may exhaust it. Use as secondary fallback only.',
        steps: [
          'Sign up at <a href="https://developer.accuweather.com" target="_blank" rel="noopener">developer.accuweather.com</a>',
          'Create an app, get API key',
          'HA: Settings → Devices & Services → Add Integration → <strong>AccuWeather</strong>',
          'Paste API key, save',
        ],
      },
    };
  }

  _norm(s) { return String(s || '').toLowerCase().replace(/[_\-\s.]/g, ''); }

  _detectProviders() {
    // Returns { providerKey: entityId } for every recognised weather entity.
    // First pass: entity registry by integration platform (catches providers
    // that don't expose an `attribution` attribute, like Open-Meteo).
    // Second pass: attribution attribute, as a fallback / cross-check.
    const found = {};
    if (!this._hass) return found;
    const providers = this._PROVIDERS;

    const entities = this._hass.entities || {};
    for (const [id, ent] of Object.entries(entities)) {
      if (!id.startsWith('weather.')) continue;
      const plat = this._norm(ent && ent.platform);
      if (!plat) continue;
      for (const [key, p] of Object.entries(providers)) {
        if (!(key in found) && plat.includes(this._norm(p.platform))) {
          found[key] = id;
          break;
        }
      }
    }

    if (this._hass.states) {
      for (const [id, st] of Object.entries(this._hass.states)) {
        if (!id.startsWith('weather.')) continue;
        const attr = ((st.attributes || {}).attribution || '').toLowerCase();
        if (!attr) continue;
        for (const [key, p] of Object.entries(providers)) {
          if (!(key in found) && attr.includes(p.attribution)) {
            found[key] = id;
            break;
          }
        }
      }
    }
    return found;
  }

  _populateProviderPicker(which) {
    const picker = this.$(`weather-${which}-picker`);
    if (!picker) return;
    const detected = this._detectProviders();
    const currentValue = this.$(`weather-${which}`).value.trim();
    const providers = this._PROVIDERS;

    let html = '<option value="">— pick a provider —</option>';

    const configured = Object.keys(detected);
    if (configured.length > 0) {
      html += '<optgroup label="Configured on this HA">';
      for (const key of configured) {
        const eid = detected[key];
        const selected = currentValue === eid ? ' selected' : '';
        // ⚠ glyph in option label when the provider has known limitations
        const flag = providers[key].limitation ? ' ⚠' : '';
        html += `<option value="entity:${this._esc(eid)}"${selected}>${this._esc(providers[key].name)}${flag} — ${this._esc(eid)}</option>`;
      }
      html += '</optgroup>';
    }

    const notConfigured = Object.keys(providers).filter(k => !(k in detected));
    if (notConfigured.length > 0) {
      html += '<optgroup label="Available providers (need setup)">';
      for (const key of notConfigured) {
        const flag = providers[key].limitation ? ' ⚠' : '';
        html += `<option value="setup:${key}">${this._esc(providers[key].name)}${flag} — ${this._esc(providers[key].free)}</option>`;
      }
      html += '</optgroup>';
    }

    // If current value doesn't match any detected provider, mark it as custom
    const matchesDetected = configured.some(k => detected[k] === currentValue);
    const selectedCustom = currentValue && !matchesDetected ? ' selected' : '';
    html += `<option value="custom"${selectedCustom}>Custom entity ID${currentValue && !matchesDetected ? ` (${this._esc(currentValue)})` : ''}…</option>`;

    picker.innerHTML = html;
    // Render any disclaimer for the pre-selected option on initial load.
    this._onWeatherPickerChange(which);
  }

  _onWeatherPickerChange(which) {
    const picker = this.$(`weather-${which}-picker`);
    const input = this.$(`weather-${which}`);
    const setupEl = this.$(`weather-${which}-setup`);
    const val = picker.value;

    if (!val) {
      setupEl.classList.add('hidden');
      return;
    }
    if (val === 'custom') {
      setupEl.classList.add('hidden');
      input.focus();
      return;
    }
    if (val.startsWith('entity:')) {
      const entityId = val.slice(7);
      input.value = entityId;
      // Identify which provider was picked, surface any known limitation.
      const detected = this._detectProviders();
      const providerKey = Object.keys(detected).find(k => detected[k] === entityId);
      const p = providerKey ? this._PROVIDERS[providerKey] : null;
      if (p && p.limitation) {
        setupEl.classList.remove('hidden');
        setupEl.innerHTML = `
          <div style="font-weight:600;margin-bottom:4px;">&#9888; Heads up about ${this._esc(p.name)}</div>
          <div style="opacity:0.9;">${this._esc(p.limitation)}</div>`;
      } else {
        setupEl.classList.add('hidden');
      }
      this._refreshWeatherPreview(which);
      return;
    }
    if (val.startsWith('setup:')) {
      const key = val.slice(6);
      const p = this._PROVIDERS[key];
      if (!p) return;
      setupEl.classList.remove('hidden');
      const limitationHtml = p.limitation
        ? `<p style="margin:8px 0 0;color:var(--danger);">&#9888; ${this._esc(p.limitation)}</p>`
        : '';
      setupEl.innerHTML = `
        <div style="font-weight:600;margin-bottom:6px;">Set up ${this._esc(p.name)}</div>
        <div style="opacity:0.85;margin-bottom:8px;">${this._esc(p.free)}</div>
        <ol style="margin:0;padding-left:20px;">
          ${p.steps.map(s => `<li style="margin-bottom:4px;">${s}</li>`).join('')}
        </ol>
        ${limitationHtml}
        <p style="margin-top:8px;opacity:0.7;">After adding it in HA, return here — the provider will appear under "Configured" in the dropdown.</p>`;
      // Don't change the input value when picking a setup-only option
      this._refreshWeatherPreview(which);
    }
  }

  async forceWater(zoneId) {
    try {
      await this._ws('hydrobalance/force_water', zoneId ? { zone_id: zoneId } : {});
      this._toast('Force watering initiated');
      setTimeout(() => this._loadAll(), 2000);
    } catch (e) { this._toast('Error: ' + (e.message || e)); }
  }

  async manualWater(zoneId, on, durationMinutes) {
    try {
      const payload = { zone_id: zoneId, on };
      if (on && durationMinutes && durationMinutes > 0) {
        payload.duration_minutes = durationMinutes;
      }
      await this._ws('hydrobalance/manual_water', payload);
      this._toast(
        on
          ? (durationMinutes ? `Manual watering — ${durationMinutes} min` : 'Manual watering started')
          : 'Manual watering stopped'
      );
      await this._loadAll();
    } catch (e) { this._toast('Error: ' + (e.message || e)); }
  }

  // ─── Manual-watering timer modal ─────────────────────────────────────────
  openManualModal(zoneId) {
    const entry = this._config[this._currentEntryId];
    const zones = (entry && entry.zones) || [];
    const zone = zones.find(z => z.id === zoneId) || {};
    const rate = Number(zone.sprinkler_rate) || 2.0;
    const name = zone.name || zoneId;

    this.$('manual-modal-zone').value = zoneId;
    this.$('manual-modal-title').textContent = `Manual water — ${name}`;
    this.$('manual-modal-info').textContent =
      `Sprinkler rate: ${rate} mm/30min. The run auto-stops at the end of the timer.`;
    this.$('manual-custom-min').value = '';

    const presets = [5, 10, 15, 30, 45, 60];
    const chips = this.$('manual-chips');
    chips.innerHTML = presets.map(min => {
      const mm = ((min / 30) * rate).toFixed(1);
      return `<button class="btn btn-sm btn-outline"
        style="flex:1 1 30%;min-width:90px;"
        onclick="window.__hb.startManualPreset(${min})">
        ${min} min<br><span style="font-size:0.75em;opacity:0.7;">≈ ${mm} mm</span>
      </button>`;
    }).join('');

    this.$('manual-modal').classList.remove('hidden');
  }

  closeManualModal() { this.$('manual-modal').classList.add('hidden'); }
  _manualBackdrop(event) {
    if (event.target === this.$('manual-modal')) this.closeManualModal();
  }

  openSupportModal() { this.$('support-modal').classList.remove('hidden'); }
  closeSupportModal() { this.$('support-modal').classList.add('hidden'); }
  _supportBackdrop(event) {
    if (event.target === this.$('support-modal')) this.closeSupportModal();
  }

  async startManualPreset(minutes) {
    const zoneId = this.$('manual-modal-zone').value;
    this.closeManualModal();
    if (zoneId) await this.manualWater(zoneId, true, minutes);
  }

  async startManualCustom() {
    const zoneId = this.$('manual-modal-zone').value;
    const minutes = parseFloat(this.$('manual-custom-min').value);
    if (!minutes || minutes <= 0) {
      this._toast('Enter a duration in minutes');
      return;
    }
    this.closeManualModal();
    if (zoneId) await this.manualWater(zoneId, true, minutes);
  }

  async startManualOpen() {
    const zoneId = this.$('manual-modal-zone').value;
    this.closeManualModal();
    if (zoneId) await this.manualWater(zoneId, true);
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
