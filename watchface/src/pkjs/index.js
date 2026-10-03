// PebbleKit JS companion for Pangaea Watch
// Resolves GPS location against GPlates Web Service (MERDITH2021)
// and handles configuration (12/24h time, customizable font colors).

var GPLATES = "https://gws.gplates.org";
var MODEL = "MERDITH2021";

var DEFAULT_HOME = {
  lat: 30.03,
  lon: -95.53,
  label: "SPRING, TX",
  plateId: 101,
  birthAge: 252.0
};

var defaultConfig = {
  hour_mode: 0,           // 0 = Watch system default, 1 = 12-hour, 2 = 24-hour
  color_time: "#FFAA00",   // Chrome Yellow
  color_taxon: "#FFAA00",  // Chrome Yellow
  color_coords: "#FFFFFF", // White
  color_age: "#55FFFF",    // Electric Blue
  color_ticker: "#AAFFAA", // Mint Green
  color_header: "#FFFFFF", // White
  color_footer: "#AAAAAA"  // Light Gray
};

function hexToInt(hex) {
  if (typeof hex !== "string") return 0xFFFFFF;
  var clean = hex.replace("#", "");
  return parseInt(clean, 16);
}

function loadConfig() {
  try {
    var raw = localStorage.getItem("pangaea:config");
    if (!raw) return defaultConfig;
    var parsed = JSON.parse(raw);
    for (var k in defaultConfig) {
      if (parsed[k] === undefined) parsed[k] = defaultConfig[k];
    }
    return parsed;
  } catch (e) {
    return defaultConfig;
  }
}

function saveConfig(cfg) {
  try {
    localStorage.setItem("pangaea:config", JSON.stringify(cfg));
  } catch (e) {
    console.log("Error saving config: " + e);
  }
}

function sendConfigToWatch(cfg) {
  var dict = {
    HOUR_MODE: cfg.hour_mode,
    COLOR_TIME: hexToInt(cfg.color_time),
    COLOR_TAXON: hexToInt(cfg.color_taxon),
    COLOR_COORDS: hexToInt(cfg.color_coords),
    COLOR_AGE: hexToInt(cfg.color_age),
    COLOR_TICKER: hexToInt(cfg.color_ticker),
    COLOR_HEADER: hexToInt(cfg.color_header),
    COLOR_FOOTER: hexToInt(cfg.color_footer)
  };
  Pebble.sendAppMessage(dict, function () {
    console.log("Sent configuration to watch");
  }, function (err) {
    console.log("Failed to send configuration: " + JSON.stringify(err));
  });
}

function getJSON(url, timeoutMs, cb) {
  var req = new XMLHttpRequest();
  req.open("GET", url, true);
  req.timeout = timeoutMs || 15000;
  req.onload = function () {
    if (req.status >= 200 && req.status < 300) {
      try {
        cb(null, JSON.parse(req.responseText));
      } catch (err) {
        cb(err);
      }
    } else {
      cb(new Error("HTTP " + req.status));
    }
  };
  req.onerror = function () { cb(new Error("Network error")); };
  req.ontimeout = function () { cb(new Error("Request timed out")); };
  req.send();
}

function resolveGPlatesPlate(lat, lon, cb) {
  var url = GPLATES + "/reconstruct/assign_points_plate_ids/?points=" + lon + "," + lat + "&model=" + MODEL;
  getJSON(url, 12000, function (err, data) {
    if (err || !data || !data.length || data[0] === 0) {
      cb(err || new Error("No plate found"));
      return;
    }
    cb(null, data[0]);
  });
}

function sendHomeToWatch(home) {
  var dict = {
    HOME_LAT: Math.round(home.lat * 100),
    HOME_LON: Math.round(home.lon * 100),
    HOME_LABEL: home.label || "MY GROUND",
    HOME_PLATE_ID: home.plateId,
    HOME_BIRTH_AGE: Math.round(home.birthAge * 10)
  };
  Pebble.sendAppMessage(dict, function () {
    console.log("Sent home position to watch: " + JSON.stringify(dict));
  }, function (err) {
    console.log("Failed to send home position: " + JSON.stringify(err));
  });
}

function updateLocationAndSync() {
  if (!navigator.geolocation) {
    console.log("Geolocation unavailable, using default home");
    sendHomeToWatch(DEFAULT_HOME);
    return;
  }

  navigator.geolocation.getCurrentPosition(function (pos) {
    var lat = pos.coords.latitude;
    var lon = pos.coords.longitude;
    console.log("Detected GPS: " + lat + ", " + lon);

    resolveGPlatesPlate(lat, lon, function (err, plateId) {
      if (err) {
        console.log("Could not resolve plate from GPlates: " + err + ", using cached/default");
        sendHomeToWatch(DEFAULT_HOME);
        return;
      }
      var home = {
        lat: lat,
        lon: lon,
        label: "MY LOCATION",
        plateId: plateId,
        birthAge: 252.0
      };
      sendHomeToWatch(home);
    });
  }, function (err) {
    console.log("Geolocation error: " + err.message + ", using default home");
    sendHomeToWatch(DEFAULT_HOME);
  }, { timeout: 10000 });
}

Pebble.addEventListener("ready", function () {
  console.log("Pangaea Watch PKJS ready");
  var cfg = loadConfig();
  sendConfigToWatch(cfg);
  updateLocationAndSync();
});

Pebble.addEventListener("appmessage", function (e) {
  console.log("Received appmessage from watch: " + JSON.stringify(e.payload));
  if (e.payload.CMD === 1) {
    var cfg = loadConfig();
    sendConfigToWatch(cfg);
    updateLocationAndSync();
  }
});

Pebble.addEventListener("showConfiguration", function () {
  var cfg = loadConfig();
  var html = '<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
    '<title>Pangaea Settings</title><style>' +
    ':root{--bg:#0e1117;--card:#161b22;--border:#30363d;--text:#e6e8ee;--muted:#8b949e;--accent:#ffaa00;}' +
    'body{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,sans-serif;padding:16px;margin:0;line-height:1.5;}' +
    'h1{font-size:1.25rem;margin:0 0 4px;color:#fff;text-align:center;}' +
    'p.sub{font-size:0.8rem;color:var(--muted);margin:0 0 16px;text-align:center;}' +
    '.card{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:14px;margin-bottom:14px;}' +
    '.sec-title{font-size:0.85rem;font-weight:600;color:var(--accent);text-transform:uppercase;letter-spacing:0.05em;margin-bottom:10px;}' +
    '.row{display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.06);}' +
    '.row:last-child{border-bottom:none;}' +
    'label{font-size:0.9rem;}' +
    'select{background:#0d1117;border:1px solid var(--border);color:#fff;padding:6px 10px;border-radius:6px;font-size:0.9rem;}' +
    'input[type=color]{border:none;width:36px;height:28px;border-radius:4px;background:none;cursor:pointer;}' +
    '.btn{display:block;width:100%;background:#238636;color:#fff;font-weight:600;border:none;border-radius:6px;padding:12px;font-size:1rem;margin-top:18px;cursor:pointer;}' +
    '</style></head><body>' +
    '<h1>PANGAEA WATCH</h1><p class="sub">Pebble Time 2 Settings</p>' +
    '<div class="card">' +
    '<div class="sec-title">Clock Format</div>' +
    '<div class="row"><label>Time Display</label>' +
    '<select id="hour_mode">' +
    '<option value="0"' + (cfg.hour_mode === 0 ? ' selected' : '') + '>Follow Watch (System)</option>' +
    '<option value="1"' + (cfg.hour_mode === 1 ? ' selected' : '') + '>12-Hour (e.g. 5:00)</option>' +
    '<option value="2"' + (cfg.hour_mode === 2 ? ' selected' : '') + '>24-Hour (e.g. 17:00)</option>' +
    '</select></div></div>' +
    '<div class="card">' +
    '<div class="sec-title">Font Colors</div>' +
    '<div class="row"><label>Digital Clock Time</label><input type="color" id="col_time" value="' + cfg.color_time + '"></div>' +
    '<div class="row"><label>Location Header</label><input type="color" id="col_hdr" value="' + cfg.color_header + '"></div>' +
    '<div class="row"><label>Fossil Taxon (Line 1)</label><input type="color" id="col_taxon" value="' + cfg.color_taxon + '"></div>' +
    '<div class="row"><label>Paleo Coordinates (Line 2)</label><input type="color" id="col_coords" value="' + cfg.color_coords + '"></div>' +
    '<div class="row"><label>Period & Age (Line 3)</label><input type="color" id="col_age" value="' + cfg.color_age + '"></div>' +
    '<div class="row"><label>Event / Drift (Line 4)</label><input type="color" id="col_ticker" value="' + cfg.color_ticker + '"></div>' +
    '<div class="row"><label>Climate Footer</label><input type="color" id="col_foot" value="' + cfg.color_footer + '"></div>' +
    '</div>' +
    '<button class="btn" id="save_btn">Save & Sync with Watch</button>' +
    '<script>' +
    'document.getElementById("save_btn").addEventListener("click", function(){' +
    'var res = {' +
    'hour_mode: +document.getElementById("hour_mode").value,' +
    'color_time: document.getElementById("col_time").value,' +
    'color_header: document.getElementById("col_hdr").value,' +
    'color_taxon: document.getElementById("col_taxon").value,' +
    'color_coords: document.getElementById("col_coords").value,' +
    'color_age: document.getElementById("col_age").value,' +
    'color_ticker: document.getElementById("col_ticker").value,' +
    'color_footer: document.getElementById("col_foot").value' +
    '};' +
    'window.location.href = "pebblejs://close#" + encodeURIComponent(JSON.stringify(res));' +
    '});' +
    '</script></body></html>';

  Pebble.openURL("data:text/html;base64," + btoa(unescape(encodeURIComponent(html))));
});

Pebble.addEventListener("webviewclosed", function (e) {
  if (e && e.response) {
    try {
      var decoded = JSON.parse(decodeURIComponent(e.response));
      saveConfig(decoded);
      sendConfigToWatch(decoded);
    } catch (err) {
      console.log("Error parsing settings response: " + err);
    }
  }
});
