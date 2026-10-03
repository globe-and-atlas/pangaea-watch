// Pangaea Watch preview: renders the Constellation pane-4 layout at Emery native resolution
// and applies per-plate rotations with slerp between keyframes -- the watch algorithm.
// Home can be anywhere on Earth: it is resolved against the plate model at runtime.

import { resolveHome } from "./home.js";
import { whatsHere } from "./fossils.js";

const W = 200;
const H = 228;
const MAP = { x: 4, y: 32, w: 192, h: 96 }; // ground_track.c: content y=20, +12; 2:1 frame

// Pebble 64-colour palette entries used by Constellation pane 4
const C = {
  black: "#000000",
  white: "#FFFFFF",
  oxford: "#000055",
  darkGray: "#555555",
  mint: "#AAFFAA",
  chrome: "#FFAA00",
  electric: "#55FFFF",
};

const canvas = document.getElementById("screen");
const ctx = canvas.getContext("2d");
const scrub = document.getElementById("scrub");
const clockOut = document.getElementById("clock-out");
const playBtn = document.getElementById("play");
const nowBtn = document.getElementById("now");
const speedSel = document.getElementById("speed");

let data = null;
let quats = null; // per keyframe: { pid: [w, x, y, z] }
let fossilIndex = null;
let events = [];
let home = null; // resolved + derived per-keyframe state, see prepareHome()
let homeStatus = "LOCATING…";
let live = true;
let playing = false;
let seconds = 0;
let pinnedMode = false;

let timeFormat = 24;
const customColors = {
  time: C.chrome,
  header: C.white,
  taxon: C.chrome,
  coords: C.white,
  age: C.electric,
  ticker: C.mint,
  footer: "#AAAAAA",
};
const CONFIG_KEY = "pangaea:preview_config";

// ── Rotation math ───────────────────────────────────────────────────────────

const rad = (d) => (d * Math.PI) / 180;
const deg = (r) => (r * 180) / Math.PI;

function toVec(lat, lon) {
  const la = rad(lat), lo = rad(lon);
  return [Math.cos(la) * Math.cos(lo), Math.cos(la) * Math.sin(lo), Math.sin(la)];
}

function toLatLon(v) {
  return [deg(Math.asin(Math.max(-1, Math.min(1, v[2])))), deg(Math.atan2(v[1], v[0]))];
}

function eulerToQuat([poleLon, poleLat, angle]) {
  const k = toVec(poleLat, poleLon);
  const h = rad(angle) / 2;
  const s = Math.sin(h);
  return [Math.cos(h), k[0] * s, k[1] * s, k[2] * s];
}

function slerp(a, b, t) {
  let dot = a[0] * b[0] + a[1] * b[1] + a[2] * b[2] + a[3] * b[3];
  let bb = b;
  if (dot < 0) { dot = -dot; bb = b.map((x) => -x); } // shortest arc
  if (dot > 0.9995) {
    const q = a.map((x, i) => x + t * (bb[i] - x));
    const n = Math.hypot(...q);
    return q.map((x) => x / n);
  }
  const th = Math.acos(dot);
  const sa = Math.sin((1 - t) * th) / Math.sin(th);
  const sb = Math.sin(t * th) / Math.sin(th);
  return a.map((x, i) => sa * x + sb * bb[i]);
}

function rotateVec(q, v) {
  const [w, x, y, z] = q;
  // v' = v + 2w(u × v) + 2u × (u × v), u = (x, y, z)
  const cx = y * v[2] - z * v[1], cy = z * v[0] - x * v[2], cz = x * v[1] - y * v[0];
  const ccx = y * cz - z * cy, ccy = z * cx - x * cz, ccz = x * cy - y * cx;
  return [v[0] + 2 * (w * cx + ccx), v[1] + 2 * (w * cy + ccy), v[2] + 2 * (w * cz + ccz)];
}

// ── Time ────────────────────────────────────────────────────────────────────

function ageAt(minute) {
  // Mirrors age_at_minute(): the fast-forward lands on 0 Ma at 23:59:59
  const { start_ma, extinction_ma, last_minute, end_minute } = data.meta.clock;
  if (minute <= last_minute) return start_ma - (minute * (start_ma - extinction_ma)) / last_minute;
  return Math.max(0, extinction_ma * (1 - (minute - last_minute) / (end_minute - last_minute)));
}

function bracket(minute) {
  const ks = data.keyframes;
  let i = 0;
  while (i < ks.length - 2 && ks[i + 1].minute <= minute) i++;
  const span = ks[i + 1].minute - ks[i].minute;
  return { i, t: Math.min(1, Math.max(0, (minute - ks[i].minute) / span)) };
}

function fmtClock(s) {
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = Math.floor(s % 60);
  return [h, m, sec].map((n) => String(n).padStart(2, "0")).join(":");
}

function fmtClockBar(s, mode = 24) {
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
  if (mode === 12) {
    const h12 = h % 12 || 12;
    return `${h12}:${String(m).padStart(2, "0")}`;
  }
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

function fmtAge(age) {
  if (age >= 10) return `${age.toFixed(1)} MA`;
  if (age >= 1) return `${age.toFixed(2)} MA`;
  return age < 0.0005 ? "TODAY" : `${Math.round(age * 1000)} KA`;
}

function fmtCoord(v) {
  const sign = v < 0 ? "-" : "+";
  return `${sign}${Math.abs(v).toFixed(2)}°`;
}

// ── Rendering ───────────────────────────────────────────────────────────────

function toScreen(lat, lon) {
  // Integer mapping identical to coord_to_screen() in ground_track.c
  let lo = Math.round(lon), la = Math.round(lat);
  if (lo < -180) lo += 360;
  if (lo > 180) lo -= 360;
  la = Math.max(-90, Math.min(90, la));
  return [MAP.x + Math.floor(((lo + 180) * MAP.w) / 360), MAP.y + Math.floor(((90 - la) * MAP.h) / 180)];
}

function line(x0, y0, x1, y1, color) {
  // Bresenham so lines stay 1px and unantialiased, like graphics_draw_line
  ctx.fillStyle = color;
  let dx = Math.abs(x1 - x0), dy = -Math.abs(y1 - y0);
  const sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1;
  let err = dx + dy;
  for (;;) {
    ctx.fillRect(x0, y0, 1, 1);
    if (x0 === x1 && y0 === y1) break;
    const e2 = 2 * err;
    if (e2 >= dy) { err += dy; x0 += sx; }
    if (e2 <= dx) { err += dx; y0 += sy; }
  }
}

let truncated = []; // lines that did not fit this frame (tests assert none)

function text(str, x, y, color, bold = false, align = "left", maxW = 192, fontSize = 12) {
  ctx.fillStyle = color;
  ctx.font = `${bold ? "bold " : ""}${fontSize}px "Helvetica Neue", Arial, sans-serif`;
  ctx.textAlign = align;
  ctx.textBaseline = "top";
  let s = str;
  if (ctx.measureText(s).width > maxW) truncated.push(str);
  while (ctx.measureText(s).width > maxW && s.length > 1) s = s.slice(0, -2) + "…";
  ctx.fillText(s, x, y);
}

function fitLabel(str, maxW) {
  // Deliberate shortening for user-supplied place names (not counted as truncation)
  ctx.font = 'bold 11px "Helvetica Neue", Arial, sans-serif';
  let s = str;
  while (ctx.measureText(s).width > maxW && s.length > 1) s = s.slice(0, -1);
  return s.trimEnd();
}

function bar(y, label, right, rightColor, labelColor = C.white) {
  ctx.fillStyle = C.black;
  ctx.fillRect(0, y, W, 20);
  line(0, y === 0 ? 19 : y, W - 1, y === 0 ? 19 : y, C.darkGray);
  text(label, 4, y + 3, labelColor, true, "left", right ? 140 : 192);
  if (right) text(right, W - 4, y + 3, rightColor, true, "right", 60);
}


const PRESETS = [
  ["Spring, TX", 30.03, -95.53],
  ["London", 51.51, -0.13],
  ["Beijing", 39.9, 116.4],
  ["Sydney", -33.87, 151.21],
  ["Cape Town", -33.92, 18.42],
  ["Buenos Aires", -34.6, -58.38],
  ["Reykjavik", 64.15, -21.94],
  ["Honolulu", 21.31, -157.86],
];
const LOCATION_KEY = "pangaea:location";

// ── Derived home state ─────────────────────────────────────────────────────

function climateBand(lat) {
  const a = Math.abs(lat);
  if (a < 23.5) return "TROPICS";
  if (a < 35) return "SUBTROPICS";
  if (a < 60) return "MID-LAT";
  return "HIGH-LAT";
}

function gcKm(a, b) {
  const va = toVec(a[0], a[1]), vb = toVec(b[0], b[1]);
  return Math.acos(Math.max(-1, Math.min(1, va[0] * vb[0] + va[1] * vb[1] + va[2] * vb[2]))) * 6371;
}

function prepareHome(raw, label) {
  const q = raw.rotations.map((e) => (e ? eulerToQuat(e) : null));
  const paleo = q.map((qq, k) =>
    qq && k >= raw.birthIndex ? toLatLon(rotateVec(qq, toVec(raw.lat, raw.lon))) : null);
  const cumKm = [];
  let total = 0;
  paleo.forEach((p, k) => {
    if (k > 0 && p && paleo[k - 1]) total += gcKm(paleo[k - 1], p);
    cumKm.push(total);
  });
  const nFossil = fossilIndex ? fossilIndex.frames.length : 0;
  const here = paleo.map((p, k) => (k < nFossil && p ? whatsHere(fossilIndex, k, p[0], p[1]) : null));
  return { ...raw, label, q, paleo, cumKm, here, birthAge: data.keyframes[raw.birthIndex].age_ma };
}

function minuteForAge(age) {
  const { start_ma, extinction_ma, last_minute, end_minute } = data.meta.clock;
  if (age >= extinction_ma) return ((start_ma - age) * last_minute) / (start_ma - extinction_ma);
  return last_minute + ((extinction_ma - age) / extinction_ma) * (end_minute - last_minute);
}

function activeEvent(s) {
  // Mesozoic events show for 20 clock-minutes (~2.6 My) but never past 23:59:00; the impact
  // (66.0 Ma) and Cenozoic events get 4 s each inside the fast-forward minute.
  const ffStart = data.meta.clock.last_minute * 60;
  let hit = null;
  for (const ev of events) {
    const start = minuteForAge(ev.age_ma) * 60;
    const end = ev.age_ma > data.meta.clock.extinction_ma ? Math.min(start + 1200, ffStart) : start + 4;
    if (s >= start && s < end && (!hit || start > hit.start)) hit = { ...ev, start };
  }
  return hit;
}

// ── Rendering ──────────────────────────────────────────────────────────────

// Short on-screen group labels; the readout panel shows the full group name
const SCREEN_GROUP = {
  "marine reptile": "MARINE", pterosaur: "PTEROSAUR", archosaur: "ARCHOSAUR", bird: "BIRD",
  "croc relative": "CROC KIN", turtle: "TURTLE", "early mammal": "MAMMAL", ammonite: "AMMONITE",
};

function taxonLine(here, s) {
  if (!here.taxa.length) return "NOTHING FOUND NEARBY";
  const t = here.taxa[Math.floor(s / 10) % here.taxa.length]; // rotate every 10 s
  const genus = t.genus.toUpperCase();
  const kind = t.trace ? " (TRACKS)" : t.group === "dinosaur" ? "" : ` · ${SCREEN_GROUP[t.group] ?? ""}`;
  ctx.font = 'bold 15px "Helvetica Neue", Arial, sans-serif';
  return ctx.measureText(genus + kind).width <= MAP.w ? genus + kind : genus; // long genus wins
}

function homeAt(i, t, age) {
  if (!home || age > home.birthAge) return null;
  const a = home.q[i], b = home.q[i + 1];
  const q = a && b ? slerp(a, b, t) : a || b; // at the birth boundary use the frame that exists
  return q ? toLatLon(rotateVec(q, toVec(home.lat, home.lon))) : null;
}

function render(s) {
  const minute = s / 60;
  const { i, t } = bracket(minute);
  const qa = quats[i], qb = quats[i + 1];
  const age = ageAt(minute);
  const k = t < 0.5 ? i : i + 1;
  const frame = data.keyframes[k];
  const fastForward = age < data.meta.clock.extinction_ma;

  truncated = [];
  ctx.fillStyle = C.black;
  ctx.fillRect(0, 0, W, H);

  // 1. Header Bar (y: 0..27, divider line at y: 28)
  // Left: Hero Digital Time (22px Bold)
  const timeStr = fmtClockBar(s, timeFormat);
  ctx.fillStyle = customColors.time;
  ctx.font = 'bold 22px "Helvetica Neue", Arial, sans-serif';
  ctx.textAlign = "left";
  ctx.textBaseline = "top";
  ctx.fillText(timeStr, 4, 1);

  // Right: Stacked Period and Age
  ctx.fillStyle = customColors.header;
  ctx.font = 'bold 11px "Helvetica Neue", Arial, sans-serif';
  ctx.textAlign = "right";
  ctx.fillText(frame.period.toUpperCase(), W - 4, 2);

  ctx.fillStyle = customColors.age;
  ctx.font = 'bold 11px "Helvetica Neue", Arial, sans-serif';
  ctx.fillText(fmtAge(age), W - 4, 14);

  line(0, 28, W - 1, 28, C.darkGray);

  // 2. Map frame, grid, border (y: 32..127)
  ctx.fillStyle = C.oxford;
  ctx.fillRect(MAP.x, MAP.y, MAP.w, MAP.h);
  const eqY = MAP.y + MAP.h / 2, pmX = MAP.x + MAP.w / 2;
  line(MAP.x, eqY, MAP.x + MAP.w - 1, eqY, C.darkGray);
  line(pmX, MAP.y, pmX, MAP.y + MAP.h - 1, C.darkGray);
  ctx.strokeStyle = C.white;
  ctx.lineWidth = 1;
  ctx.strokeRect(MAP.x + 0.5, MAP.y + 0.5, MAP.w - 1, MAP.h - 1);

  // Coastlines: rotate each vertex by its plate's interpolated rotation
  const cache = {};
  const qFor = (pid) => (cache[pid] ??= qa[pid] && qb[pid] ? slerp(qa[pid], qb[pid], t) : null);
  let prev = null, prevLon = 0;
  for (const [lat, lon, pid, pen, birth] of data.vertices) {
    const q = age <= birth ? qFor(pid) : null;
    if (!q) { prev = null; continue; }
    const [plat, plon] = toLatLon(rotateVec(q, toVec(lat, lon)));
    const p = toScreen(plat, plon);
    const wrap = prev && Math.abs(plon - prevLon) > 180;
    if (pen && prev && !wrap) line(prev[0], prev[1], p[0], p[1], C.mint);
    prev = p;
    prevLon = plon;
  }

  // Home crosshair
  const hp = homeAt(i, t, age);
  let cross = null;
  if (hp) {
    cross = toScreen(hp[0], hp[1]);
    line(cross[0] - 3, cross[1], cross[0] + 3, cross[1], C.chrome);
    line(cross[0], cross[1] - 3, cross[0], cross[1] + 3, C.chrome);
  }

  // 3. Deep-Time "Day Arc" Ribbon (y: 130..133)
  ctx.fillStyle = "#FF8800"; // Triassic
  ctx.fillRect(4, 130, 53, 4);
  ctx.fillStyle = "#00AAAA"; // Jurassic
  ctx.fillRect(57, 130, 57, 4);
  ctx.fillStyle = C.mint; // Cretaceous
  ctx.fillRect(114, 130, 81, 4);
  ctx.fillStyle = "#FF0000"; // Asteroid Impact at 66 Ma
  ctx.fillRect(195, 130, 1, 4);

  // Day Arc Cursor Needle (y: 129..134)
  const curX = Math.min(195, 4 + Math.floor((minute * 191) / 1440));
  ctx.fillStyle = C.white;
  ctx.fillRect(curX - 1, 129, 2, 6);

  // 4. Telemetry Text Stack (y: 136..206)
  const here = home?.here[k] ?? null;
  const ev = activeEvent(s);

  // Line 1: Hero Taxon / Status (Large Bold with adaptive scaling)
  let line1;
  if (!home) {
    line1 = homeStatus;
  } else if (!hp) {
    line1 = "GROUND NOT FORMED YET";
  } else {
    line1 = fastForward ? "AFTER THE DINOSAURS" : here ? taxonLine(here, s) : "NOTHING FOUND NEARBY";
  }
  let fontSz = 14;
  ctx.font = `bold ${fontSz}px "Helvetica Neue", Arial, sans-serif`;
  while (ctx.measureText(line1).width > MAP.w && fontSz > 11) {
    fontSz--;
    ctx.font = `bold ${fontSz}px "Helvetica Neue", Arial, sans-serif`;
  }
  text(line1, MAP.x, 136, customColors.taxon, true, "left", MAP.w, fontSz);

  // Line 2: Context Subline (11px regular)
  let line2;
  if (!home) {
    line2 = "MERDITH 2021 PLATE MODEL";
  } else if (!hp) {
    line2 = `APPEARS AT ${fmtClock(minuteForAge(home.birthAge) * 60).slice(0, 5)}`;
  } else if (fastForward) {
    line2 = "CENOZOIC FAST-FORWARD";
  } else if (here?.nearestKm != null) {
    line2 = `${here.marine ? "MARINE" : "TERRESTRIAL"} FIND • ${here.nearestKm} KM`;
  } else {
    line2 = "NO FOSSILS WITHIN 1000 KM";
  }
  text(line2, MAP.x, 155, C.white, false, "left", MAP.w, 11);

  // Line 3: Event Ticker or Drift Odometer (11px regular)
  let line4 = "";
  if (ev) {
    line4 = ev.label;
    text(line4, MAP.x, 171, C.white, false, "left", MAP.w, 11);
  } else if (home && hp) {
    const drift = drifted(i, t);
    line4 = `DRIFT ${Math.round(drift.km).toLocaleString("en-US")} KM • ${drift.cmyr.toFixed(1)} CM/YR`;
    text(line4, MAP.x, 171, customColors.ticker, false, "left", MAP.w, 11);
  }

  // Line 4: Paleo Coordinates (11px regular)
  let coordsLine = "";
  if (hp) {
    coordsLine = `PALEO: ${fmtCoord(hp[0])}, ${fmtCoord(hp[1])} (YOU)`;
  } else {
    coordsLine = "GLOBAL RECONSTRUCTION";
  }
  text(coordsLine, MAP.x, 187, customColors.coords, false, "left", MAP.w, 11);

  // 5. Bottom Bar (y: 207..227)
  line(0, H - 21, W - 1, H - 21, C.darkGray);
  const homeLbl = fitLabel((home?.label ?? "PANGAEA").toUpperCase(), 120);
  const band = hp ? climateBand(hp[0]) : "GLOBAL";
  const foot = `${homeLbl} • ${band}`;
  text(homeLbl, MAP.x, H - 18, customColors.footer, true, "left", 120, 11);
  text(band, W - 4, H - 18, customColors.footer, false, "right", 70, 11);

  updateReadout(s, age, frame, hp, here, ev);
  if (pinnedMode) publishState({ age, hp, cross, line1, line4, foot, here });
}

function drifted(i, t) {
  const c = home.cumKm;
  const km = c[i] + t * (c[i + 1] - c[i]);
  const ka = data.keyframes[i].age_ma, kb = data.keyframes[i + 1].age_ma;
  const seg = home.paleo[i] && home.paleo[i + 1] ? gcKm(home.paleo[i], home.paleo[i + 1]) : 0;
  const cmyr = ka > kb ? seg / (ka - kb) / 10 : 0; // km per My = mm per year
  return { km, cmyr };
}

// Test hook: with ?t= pinned, expose what was drawn so tests/test_preview.py can check it
function publishState(st) {
  const hexAt = (x, y) => {
    const [r, g, b] = ctx.getImageData(x, y, 1, 1).data;
    return "#" + [r, g, b].map((n) => n.toString(16).padStart(2, "0")).join("").toUpperCase();
  };
  const px = ctx.getImageData(MAP.x + 1, MAP.y + 1, MAP.w - 2, MAP.h - 2).data;
  const counts = {};
  for (let i = 0; i < px.length; i += 4) {
    const k = "#" + [px[i], px[i + 1], px[i + 2]].map((n) => n.toString(16).padStart(2, "0")).join("").toUpperCase();
    counts[k] = (counts[k] || 0) + 1;
  }
  canvas.dataset.state = JSON.stringify({
    w: canvas.width, h: canvas.height, age: st.age, ready: !!home,
    home: st.hp, cross: st.cross, crossColor: st.cross ? hexAt(st.cross[0] + 2, st.cross[1]) : null,
    mapColors: counts, slider: [Number(scrub.min), Number(scrub.max)],
    plateId: home?.plateId ?? null, birthAge: home?.birthAge ?? null,
    line1: st.line1, line4: st.line4, foot: st.foot, truncated,
    here: st.here ? { tier: st.here.tier, genera: st.here.taxa.map((x) => x.genus),
      nearestKm: st.here.nearestKm, marine: st.here.marine } : null,
  });
  try {
    const hiCanvas = document.createElement("canvas");
    hiCanvas.width = 600;
    hiCanvas.height = 684;
    const hiCtx = hiCanvas.getContext("2d");
    hiCtx.imageSmoothingEnabled = false;
    hiCtx.drawImage(canvas, 0, 0, 600, 684);
    canvas.dataset.png = hiCanvas.toDataURL("image/png");
  } catch {
    /* ignore */
  }
}

function updateReadout(s, age, frame, hp, here, ev) {
  clockOut.textContent = fmtClock(s);
  scrub.value = Math.floor(s);
  document.getElementById("r-age").textContent = age < 0.0005 ? "today" : `${age.toFixed(2)} million years ago`;
  document.getElementById("r-period").textContent = frame.period;
  document.getElementById("r-pos").textContent = hp ? `${hp[0].toFixed(2)}°, ${hp[1].toFixed(2)}°` : "not in the model yet";
  document.getElementById("r-tier").textContent = !here ? "–"
    : here.tier === "none" ? `nothing within ${here.radiusKm} km of your ancient position`
    : `${here.tier} (≤ ${here.radiusKm} km, measured in ancient geography)`;
  document.getElementById("r-event").textContent = ev ? `${ev.label.toLowerCase()} — ${ev.note}` : "–";
  const ul = document.getElementById("r-taxa");
  ul.replaceChildren(...(here?.taxa ?? []).map((t) => {
    const li = document.createElement("li");
    li.textContent = `${t.genus}${t.trace ? " (tracks)" : ""} `;
    const span = document.createElement("span");
    span.textContent = `${t.group} · ${t.distKm} km · ${t.formation || "unnamed formation"} · ${t.rangeMa[0]}–${t.rangeMa[1]} Ma`;
    li.append(span);
    return li;
  }));
}

// ── Location ───────────────────────────────────────────────────────────────

const locStatus = document.getElementById("loc-status");

let locationRequest = 0; // newest request wins; slower, older lookups are discarded

async function setLocation(lat, lon, label) {
  const request = ++locationRequest;
  home = null;
  homeStatus = "LOCATING…";
  locStatus.textContent = `Resolving ${label} against the plate model…`;
  try {
    const raw = await resolveHome(lat, lon, data.keyframes.map((k) => k.age_ma));
    if (request !== locationRequest) return;
    home = prepareHome(raw, label);
    try { localStorage.setItem(LOCATION_KEY, JSON.stringify({ lat, lon, label })); } catch { /* ignore */ }
    const born = home.birthIndex === 0 ? "exists at 252 Ma" : `first appears ${home.birthAge.toFixed(1)} Ma`;
    locStatus.textContent = `${label}: plate ${home.plateId}, ground ${born}.`;
  } catch (err) {
    if (request !== locationRequest) return;
    homeStatus = "LOCATION FAILED";
    locStatus.textContent = `Could not resolve ${label}: ${err.message}`;
  }
  if (pinnedMode) render(seconds);
}

function loadCustomization() {
  try {
    const saved = JSON.parse(localStorage.getItem(CONFIG_KEY));
    if (saved) {
      if (saved.timeFormat) timeFormat = Number(saved.timeFormat);
      if (saved.colors) Object.assign(customColors, saved.colors);
    }
  } catch { /* ignore */ }
}

function saveCustomization() {
  try {
    localStorage.setItem(CONFIG_KEY, JSON.stringify({ timeFormat, colors: customColors }));
  } catch { /* ignore */ }
}

function initCustomizationUI() {
  loadCustomization();
  const tf = document.getElementById("time-format");
  if (tf) {
    tf.value = String(timeFormat);
    tf.addEventListener("change", () => {
      timeFormat = Number(tf.value);
      saveCustomization();
      render(seconds);
    });
  }
  const colorInputs = {
    time: "col-time",
    header: "col-header",
    taxon: "col-taxon",
    coords: "col-coords",
    age: "col-age",
    ticker: "col-ticker",
    footer: "col-footer",
  };
  for (const [key, id] of Object.entries(colorInputs)) {
    const input = document.getElementById(id);
    if (!input) continue;
    input.value = customColors[key];
    input.addEventListener("input", () => {
      customColors[key] = input.value;
      saveCustomization();
      render(seconds);
    });
  }
}

function initLocationUI() {
  const sel = document.getElementById("loc-preset");
  sel.replaceChildren(...PRESETS.map(([name], i) => new Option(name, String(i))));
  sel.addEventListener("change", () => {
    const [name, lat, lon] = PRESETS[Number(sel.value)];
    setLocation(lat, lon, name);
  });
  document.getElementById("loc-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const lat = Number(document.getElementById("loc-lat").value);
    const lon = Number(document.getElementById("loc-lon").value);
    if (!(Math.abs(lat) <= 90 && Math.abs(lon) <= 180)) {
      locStatus.textContent = "Latitude must be −90…90 and longitude −180…180.";
      return;
    }
    setLocation(lat, lon, `${lat.toFixed(1)}, ${lon.toFixed(1)}`);
  });
  document.getElementById("loc-gps").addEventListener("click", () => {
    if (!navigator.geolocation) { locStatus.textContent = "Geolocation is not available here."; return; }
    locStatus.textContent = "Asking for your location…";
    navigator.geolocation.getCurrentPosition(
      (pos) => setLocation(pos.coords.latitude, pos.coords.longitude, "My location"),
      (err) => { locStatus.textContent = `Location unavailable: ${err.message}`; },
      { timeout: 15000 });
  });
}

function initialLocation() {
  const q = new URLSearchParams(location.search);
  if (q.has("lat") && q.has("lon")) {
    return { lat: Number(q.get("lat")), lon: Number(q.get("lon")), label: q.get("place") || "Custom" };
  }
  try {
    const saved = JSON.parse(localStorage.getItem(LOCATION_KEY));
    if (saved && Number.isFinite(saved.lat)) return saved;
  } catch { /* ignore */ }
  const [label, lat, lon] = PRESETS[0];
  return { lat, lon, label };
}

// ── Loop & controls ────────────────────────────────────────────────────────

function nowSeconds() {
  const d = new Date();
  return d.getHours() * 3600 + d.getMinutes() * 60 + d.getSeconds() + d.getMilliseconds() / 1000;
}

function setMode(mode) {
  live = mode === "live";
  playing = mode === "play";
  nowBtn.classList.toggle("active", live);
  playBtn.classList.toggle("active", playing);
  playBtn.textContent = playing ? "Pause" : "Play";
}

let last = performance.now();
function tick(ts) {
  const dt = (ts - last) / 1000;
  last = ts;
  if (live) seconds = nowSeconds();
  else if (playing) seconds = (seconds + dt * Number(speedSel.value)) % 86400;
  render(seconds);
  requestAnimationFrame(tick);
}

scrub.addEventListener("input", () => { setMode("scrub"); seconds = Number(scrub.value); });
nowBtn.addEventListener("click", () => setMode("live"));
playBtn.addEventListener("click", () => setMode(playing ? "scrub" : "play"));
document.querySelectorAll(".jumps button").forEach((b) => b.addEventListener("click", () => {
  const [h, m, s] = b.dataset.t.split(":").map(Number);
  setMode("scrub");
  seconds = h * 3600 + m * 60 + s;
}));

async function loadJSON(path) {
  const resp = await fetch(path);
  if (!resp.ok) throw new Error(`${path}: HTTP ${resp.status}`);
  return resp.json();
}

async function main() {
  [data, fossilIndex, { events }] = await Promise.all([
    loadJSON("data/deep_time.json"), loadJSON("data/fossil_index.json"), loadJSON("data/events.json")]);
  quats = data.keyframes.map((k) =>
    Object.fromEntries(Object.entries(k.rotations).map(([pid, e]) => [pid, eulerToQuat(e)])));
  const src = data.meta.sources;
  document.getElementById("sources").textContent =
    `Coastlines: ${src.coastlines}. Plates: ${src.plates}. Fossils: ${fossilIndex.meta.source}. ` +
    `Fossil distances are measured between ancient positions at each moment.`;
  initLocationUI();
  initCustomizationUI();
  const loc = initialLocation();
  const pinned = new URLSearchParams(location.search).get("t"); // ?t=HH:MM:SS pins the clock
  if (pinned) {
    pinnedMode = true;
    const [h, m, s = 0] = pinned.split(":").map(Number);
    seconds = h * 3600 + m * 60 + s;
    setMode("scrub");
    render(seconds);
    await setLocation(loc.lat, loc.lon, loc.label); // re-renders synchronously when resolved
  } else {
    setMode("live");
    setLocation(loc.lat, loc.lon, loc.label);
  }
  requestAnimationFrame(tick);
}

main().catch((err) => {
  ctx.fillStyle = C.black;
  ctx.fillRect(0, 0, W, H);
  text("DATA LOAD FAILED", 4, 100, C.chrome, true);
  text(String(err.message), 4, 116, C.white);
  console.error(err);
});
