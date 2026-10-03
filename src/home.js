// Resolve any home location against the plate model at runtime -- the same calls the Pebble
// phone-side JS will make. Three steps, ~9 requests, cached per location:
//   1. which plate the point is on
//   2. that plate's rotation at every keyframe (one batched call)
//   3. when that ground first exists in the model (binary search on reconstruct_points;
//      young seafloor and accreted terranes do not exist at 252 Ma)

const GPLATES = "https://gws.gplates.org";
const MODEL = "MERDITH2021";
const CACHE_VERSION = 2;
const TIMEOUT_MS = 15000;
const RETRIES = 3;

async function getJSON(url) {
  // GPlates occasionally stalls; time out each attempt and retry with backoff
  let lastErr;
  for (let attempt = 1; attempt <= RETRIES; attempt++) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
    try {
      const resp = await fetch(url, { signal: ctrl.signal });
      if (resp.status >= 400 && resp.status < 500) {
        throw Object.assign(new Error(`GPlates HTTP ${resp.status}`), { fatal: true }); // won't succeed on retry
      }
      if (!resp.ok) throw new Error(`GPlates HTTP ${resp.status}`);
      return await resp.json();
    } catch (err) {
      if (err.fatal) throw err;
      lastErr = err.name === "AbortError" ? new Error("GPlates timed out") : err;
      if (attempt < RETRIES) await new Promise((r) => setTimeout(r, 1000 * attempt));
    } finally {
      clearTimeout(timer);
    }
  }
  throw lastErr;
}

function cacheKey(lat, lon) {
  return `pangaea:home:v${CACHE_VERSION}:${MODEL}:${lat.toFixed(3)},${lon.toFixed(3)}`;
}

function readCache(key) {
  try { return JSON.parse(localStorage.getItem(key)); } catch { return null; }
}

function writeCache(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* private mode etc. */ }
}

async function aliveAt(lat, lon, age) {
  const d = await getJSON(`${GPLATES}/reconstruct/reconstruct_points/?points=${lon},${lat}&time=${age}&model=${MODEL}`);
  return Math.abs(d.coordinates[0][1]) <= 90; // 999.99 = not in the model at this age
}

/**
 * @param {number} lat
 * @param {number} lon
 * @param {number[]} ages keyframe ages, oldest first
 * @returns {Promise<{lat:number, lon:number, plateId:number, rotations:(number[]|null)[], birthIndex:number}>}
 */
export async function resolveHome(lat, lon, ages) {
  const key = cacheKey(lat, lon);
  const cached = readCache(key);
  const agesKey = ages.join(",");
  if (cached && cached.agesKey === agesKey) return cached; // keyed by the exact keyframe ages

  const [plateId] = await getJSON(`${GPLATES}/reconstruct/assign_points_plate_ids/?points=${lon},${lat}&model=${MODEL}`);
  if (!plateId) throw new Error("This location is not on any plate in the model");

  const rot = await getJSON(
    `${GPLATES}/rotation/get_euler_pole_and_angle?times=${ages.join(",")}&pids=${plateId}&model=${MODEL}`);
  const rotations = ages.map((a) => {
    // Keys are Python float strings: "252.0", "250.0611"
    const row = rot[Number.isInteger(a) ? `${a}.0` : String(a)];
    const e = row?.[String(plateId)];
    if (!e) throw new Error(`No rotation for plate ${plateId} at ${a} Ma`);
    return a > 0 && e[2] === 0 ? null : e; // [0, 90, 0] = plate not in model yet
  });

  // Oldest keyframe at which the ground exists; existence is monotonic (old -> young)
  let birthIndex;
  if (rotations[0] && (await aliveAt(lat, lon, ages[0]))) {
    birthIndex = 0;
  } else {
    let dead = 0, live = ages.length - 1;
    while (live - dead > 1) {
      const mid = (dead + live) >> 1;
      if (rotations[mid] && (await aliveAt(lat, lon, ages[mid]))) live = mid; else dead = mid;
    }
    birthIndex = live;
  }

  const home = { lat, lon, plateId, rotations, birthIndex, agesKey };
  writeCache(key, home);
  return home;
}
