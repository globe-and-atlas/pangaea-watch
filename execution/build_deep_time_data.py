#!/usr/bin/env python3
"""
execution/build_deep_time_data.py
Builds data/deep_time.json for the Pangaea watch face.

Clock mapping: minute 0 = 252 Ma, minute 1439 = 66 Ma, and the final minute
(23:59:00 -> 23:59:59) fast-forwards 66 Ma -> 0 Ma.

Output carries coastline vertices tagged with plate IDs (once) plus one Euler
rotation per plate per keyframe -- the same shape the Pebble build will pack.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parent.parent
LAND_PATH = ROOT / "data" / "ne_110m_land.json"
OUTPUT_PATH = ROOT / "data" / "deep_time.json"
CACHE_DIR = ROOT / ".tmp" / "cache"

GPLATES = "https://gws.gplates.org"
PBDB = "https://paleobiodb.org/data1.2"
MODEL = "MERDITH2021"

# Fixed reference point for verifying the rotation convention against GPlates.
# The face itself works for any location (home is resolved at runtime in src/home.js).
HOME = {"name": "Spring, TX", "lat": 30.03, "lon": -95.53}

START_MA = 252.0
EXTINCTION_MA = 66.0
LAST_MINUTE = 1439
END_MINUTE = LAST_MINUTE + 59 / 60  # 23:59:59
KEYFRAME_STEP_MIN = 15
FAST_FORWARD_STEP_MA = 6.0
CHECK_MINUTES = (0.0, 720.0, 1200.0, 1439.0)  # verified against reconstruct_points

# Plates whose motion stays within one map pixel of a larger plate's are merged into it.
# Constellation pane 4 draws the world 192 px wide -> 360/192 deg per pixel.
MAP_WIDTH_PX = 192
MERGE_TOL_DEG = 360.0 / MAP_WIDTH_PX

# Coastline budget: polygons kept and vertex decimation
MAX_POLYGONS = 40
MIN_POLYGON_POINTS = 12
DECIMATE_STEP = 3

# ICS 2023 boundaries (Ma), youngest first
PERIODS = [
    (2.58, "Quaternary"),
    (23.03, "Neogene"),
    (66.0, "Paleogene"),
    (100.5, "Late Cretaceous"),
    (145.0, "Early Cretaceous"),
    (161.5, "Late Jurassic"),
    (174.7, "Middle Jurassic"),
    (201.4, "Early Jurassic"),
    (237.0, "Late Triassic"),
    (247.2, "Middle Triassic"),
    (252.0, "Early Triassic"),
]

HTTP_TIMEOUT = 60
HTTP_RETRIES = 3
POINT_CHUNK = 150


# ── Clock mapping ─────────────────────────────────────────────────────────────

def age_at_minute(minute: float) -> float:
    """Age in Ma for a fractional minute of the day (0 <= minute < 1440).
    The fast-forward reaches 0 Ma at 23:59:59 -- the last second the clock shows."""
    if minute <= LAST_MINUTE:
        return START_MA - minute * (START_MA - EXTINCTION_MA) / LAST_MINUTE
    return max(0.0, EXTINCTION_MA * (1 - (minute - LAST_MINUTE) / (END_MINUTE - LAST_MINUTE)))


def keyframe_schedule() -> list[tuple[float, float]]:
    """(minute, age_ma) pairs: 15-min Mesozoic steps, 66 Ma, then fast-forward to 0."""
    frames = [(float(m), age_at_minute(m)) for m in range(0, LAST_MINUTE, KEYFRAME_STEP_MIN)]
    frames.append((float(LAST_MINUTE), EXTINCTION_MA))
    age = EXTINCTION_MA - FAST_FORWARD_STEP_MA
    while age > -1e-9:
        age = max(age, 0.0)
        span = END_MINUTE - LAST_MINUTE
        frames.append((LAST_MINUTE + span * (EXTINCTION_MA - age) / EXTINCTION_MA, age))
        age -= FAST_FORWARD_STEP_MA
    return [(round(m, 6), round(a, 4)) for m, a in frames]


def period_for(age: float) -> str:
    """A boundary age belongs to the older period, so 66.0 Ma reads Late Cretaceous."""
    for boundary, name in PERIODS:
        if age < boundary - 1e-9:
            return name
    return PERIODS[-1][1]


# ── Geometry ─────────────────────────────────────────────────────────────────

def to_vec(lat: float, lon: float) -> tuple[float, float, float]:
    la, lo = math.radians(lat), math.radians(lon)
    return (math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la))


def to_latlon(v: tuple[float, float, float]) -> tuple[float, float]:
    z = max(-1.0, min(1.0, v[2]))
    return math.degrees(math.asin(z)), math.degrees(math.atan2(v[1], v[0]))


def rotate(lat: float, lon: float, euler: list[float]) -> tuple[float, float]:
    """Apply a GPlates finite rotation [pole_lon, pole_lat, angle_deg] (Rodrigues)."""
    p = to_vec(lat, lon)
    k = to_vec(euler[1], euler[0])
    a = math.radians(euler[2])
    c, s = math.cos(a), math.sin(a)
    d = sum(k[i] * p[i] for i in range(3))
    cr = (k[1] * p[2] - k[2] * p[1], k[2] * p[0] - k[0] * p[2], k[0] * p[1] - k[1] * p[0])
    return to_latlon(tuple(p[i] * c + cr[i] * s + k[i] * d * (1 - c) for i in range(3)))


def angular_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    a, b = to_vec(lat1, lon1), to_vec(lat2, lon2)
    return math.degrees(math.acos(max(-1.0, min(1.0, sum(a[i] * b[i] for i in range(3))))))


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    return math.radians(angular_distance(lat1, lon1, lat2, lon2)) * 6371.0


# ── HTTP with cache ──────────────────────────────────────────────────────────

def fetch_json(
    url: str, params: dict[str, Any], cache_key: str, refresh: bool, post: bool = False
) -> Any:
    cache_path = CACHE_DIR / f"{cache_key}.json"
    if cache_path.exists() and not refresh:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    last_error: Exception | None = None
    for attempt in range(1, HTTP_RETRIES + 1):
        try:
            if post:
                resp = requests.post(url, data=params, timeout=HTTP_TIMEOUT)
            else:
                resp = requests.get(url, params=params, timeout=HTTP_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(data), encoding="utf-8")
            return data
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            print(f"  ! {cache_key} attempt {attempt} failed: {exc}", file=sys.stderr)
            time.sleep(2 * attempt)
    raise RuntimeError(f"Fetch failed for {cache_key}: {last_error}")


# ── Coastlines ───────────────────────────────────────────────────────────────

def load_coastlines() -> list[list[tuple[float, float]]]:
    """Largest Natural Earth polygons, decimated, as [(lat, lon), ...] contours."""
    if not LAND_PATH.exists():
        raise FileNotFoundError(f"Missing land data: {LAND_PATH}")
    polys = json.loads(LAND_PATH.read_text(encoding="utf-8"))
    polys = [p for p in polys if len(p) >= MIN_POLYGON_POINTS]
    polys = sorted(polys, key=len, reverse=True)[:MAX_POLYGONS]
    contours = []
    for poly in polys:
        pts = poly[::DECIMATE_STEP]
        if pts[-1] != poly[-1]:
            pts.append(poly[-1])
        contours.append([(round(lat, 2), round(lon, 2)) for lon, lat in pts])
    return contours


def assign_plate_ids(points: list[tuple[float, float]], refresh: bool) -> list[int]:
    pids: list[int] = []
    for i in range(0, len(points), POINT_CHUNK):
        chunk = points[i : i + POINT_CHUNK]
        flat = ",".join(f"{lon},{lat}" for lat, lon in chunk)
        data = fetch_json(
            f"{GPLATES}/reconstruct/assign_points_plate_ids/",
            {"points": flat, "model": MODEL},
            f"pids_{MODEL}_{hashlib.sha1(flat.encode()).hexdigest()[:12]}",
            refresh,
        )
        if len(data) != len(chunk):
            raise ValueError(f"Plate ID count mismatch: {len(data)} != {len(chunk)}")
        pids.extend(int(p) for p in data)
    return pids


def build_vertices(
    contours: list[list[tuple[float, float]]], refresh: bool
) -> list[list[float | int]]:
    """[lat, lon, plate_id, contour_start]; vertices on no plate (ID 0) are dropped
    and the next kept vertex starts a new run."""
    flat = [pt for c in contours for pt in c]
    pids = assign_plate_ids(flat, refresh)
    vertices: list[list[float | int]] = []
    idx = 0
    for contour in contours:
        start = 1
        for lat, lon in contour:
            pid = pids[idx]
            idx += 1
            if pid == 0:
                start = 1
                continue
            vertices.append([lat, lon, pid, start])
            start = 0
    return vertices


def set_pens(
    vertices: list[list[float | int]], mapping: dict[int, int], births: list[float]
) -> list[list[float | int]]:
    """[lat, lon, rep_plate_id, pen_down, birth_ma]; pen lifts at run starts and wherever
    the representative plate changes, so no segment ever spans two moving plates.
    A vertex is drawn only while the clock's age <= birth_ma."""
    out: list[list[float | int]] = []
    prev_rep: int | None = None
    for (lat, lon, pid, start), birth in zip(vertices, births):
        rep = mapping[int(pid)]
        pen = 0 if (start or rep != prev_rep) else 1
        out.append([lat, lon, rep, pen, birth])
        prev_rep = rep
    return out


# ── Rotations ────────────────────────────────────────────────────────────────

def fetch_rotations(
    plate_ids: list[int], ages: list[float], refresh: bool
) -> dict[float, dict[int, list[float] | None]]:
    """{age: {plate_id: [pole_lon, pole_lat, angle] | None}} for every plate at every age.
    GPlates answers [0, 90, 0] for a plate that does not exist yet at that age (its
    reconstruct_points gives 999.99); that is stored as None, never as a real rotation."""
    out: dict[float, dict[int, list[float] | None]] = {a: {} for a in ages}
    age_param = ",".join(f"{a:g}" for a in ages)
    for i in range(0, len(plate_ids), 20):
        chunk = plate_ids[i : i + 20]
        data = fetch_json(
            f"{GPLATES}/rotation/get_euler_pole_and_angle",
            {"times": age_param, "pids": ",".join(map(str, chunk)), "model": MODEL},
            f"rot_{MODEL}_{'-'.join(map(str, chunk))}_{len(ages)}",
            refresh,
        )
        for age in ages:
            row = data.get(f"{float(age)}") or data.get(f"{age:g}")
            if row is None:
                raise ValueError(f"No rotations returned for {age} Ma")
            for pid in chunk:
                euler = row.get(str(pid))
                if euler is None:
                    raise ValueError(f"No rotation for plate {pid} at {age} Ma")
                undefined = age > 0 and float(euler[2]) == 0.0
                out[age][pid] = None if undefined else [round(float(x), 6) for x in euler]
    return out


Recon = dict[float, list[tuple[float, float] | None]]


def fetch_reconstructed(vertices: list[list[float | int]], ages: list[float], refresh: bool) -> Recon:
    """GPlates' own position for every vertex at every keyframe; None where GPlates answers
    999.99 (that crust is not in the model yet). This is the ground truth for existence
    and for the 1-px merge -- a plate can have a rotation before its crust exists."""
    flat = ",".join(f"{v[1]},{v[0]}" for v in vertices)
    digest = hashlib.sha1(flat.encode()).hexdigest()[:12]
    out: Recon = {}
    for age in ages:
        data = fetch_json(
            f"{GPLATES}/reconstruct/reconstruct_points/",
            {"points": flat, "time": f"{age:g}", "model": MODEL},
            f"recon_all_{MODEL}_{digest}_{age:g}",
            refresh,
            post=True,
        )
        coords = data["coordinates"]
        if len(coords) != len(vertices):
            raise ValueError(f"reconstruct_points returned {len(coords)} of {len(vertices)} at {age} Ma")
        out[age] = [(c[1], c[0]) if abs(c[1]) <= 90 else None for c in coords]
    return out


def birth_ages(recon: Recon, ages: list[float]) -> list[float]:
    """Oldest keyframe age at which each vertex exists. Asserts existence is monotonic:
    once a vertex appears it stays through to the present."""
    n = len(next(iter(recon.values())))
    births = []
    for i in range(n):
        alive = [recon[a][i] is not None for a in ages]  # ages run old -> young
        first = alive.index(True) if True in alive else None
        if first is None or not all(alive[first:]):
            raise AssertionError(f"Vertex {i} existence is not monotonic: {alive}")
        births.append(ages[first])
    return births


def merge_plates(
    vertices: list[list[float | int]],
    home_pid: int,
    rotations: dict[float, dict[int, list[float] | None]],
    recon: Recon,
) -> tuple[dict[int, int], float]:
    """Map each plate to a representative whose rotation keeps every one of the plate's
    vertices within MERGE_TOL_DEG of GPlates' position, at every keyframe where that vertex
    exists. Largest plates claim first; home's plate is always a representative."""
    idx_by_pid: dict[int, list[int]] = {}
    for i, v in enumerate(vertices):
        idx_by_pid.setdefault(int(v[2]), []).append(i)
    idx_by_pid.setdefault(home_pid, [])
    ages = list(rotations)

    def error(pid: int, rep: int) -> float:
        err = 0.0
        for a in ages:
            for i in idx_by_pid[pid]:
                truth = recon[a][i]
                if truth is None:
                    continue
                euler = rotations[a][rep]
                if euler is None:
                    return math.inf
                lat, lon = rotate(float(vertices[i][0]), float(vertices[i][1]), euler)
                err = max(err, angular_distance(lat, lon, *truth))
                if err > MERGE_TOL_DEG:
                    return err
        return err

    order = sorted(idx_by_pid, key=lambda p: (p != home_pid, -len(idx_by_pid[p])))
    reps: list[int] = []
    mapping: dict[int, int] = {}
    worst = 0.0
    for pid in order:
        chosen = None
        for rep in reps:
            err = error(pid, rep)
            if err <= MERGE_TOL_DEG:
                chosen = rep
                worst = max(worst, err)
                break
        if chosen is None:
            own = error(pid, pid)
            if own > 0.1:
                raise AssertionError(f"Plate {pid} own rotation off GPlates by {own:.3f}°")
            reps.append(pid)
            chosen = pid
        mapping[pid] = chosen
    return mapping, worst


def verify_home(
    home_pid: int,
    rotations: dict[float, dict[int, list[float] | None]],
    check_ages: list[float],
    refresh: bool,
) -> list[dict[str, float]]:
    """Popper check: stored rotations must reproduce GPlates' own reconstruction."""
    checks = []
    for age in check_ages:
        mine = rotate(HOME["lat"], HOME["lon"], rotations[age][home_pid])
        data = fetch_json(
            f"{GPLATES}/reconstruct/reconstruct_points/",
            {"points": f"{HOME['lon']},{HOME['lat']}", "time": f"{age:g}", "model": MODEL},
            f"recon_home_{MODEL}_{age:g}",
            refresh,
        )
        g_lon, g_lat = data["coordinates"][0]
        err = angular_distance(mine[0], mine[1], g_lat, g_lon)
        checks.append({"age": age, "error_deg": round(err, 5)})
        if err > 0.1:
            raise AssertionError(f"Rotation mismatch at {age} Ma: {err:.4f} deg")
    return checks


# ── Main ─────────────────────────────────────────────────────────────────────

def packed_size_estimate(n_vertices: int, n_plates: int, n_frames: int) -> dict[str, int]:
    """Watch payload: int16 lat/lon + plate index byte + birth byte per vertex;
    int16 quaternion per plate-frame."""
    vertex_bytes = n_vertices * 6
    rotation_bytes = n_plates * n_frames * 8
    return {"vertex_bytes": vertex_bytes, "rotation_bytes": rotation_bytes,
            "total_bytes": vertex_bytes + rotation_bytes}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print schedule only, no network")
    parser.add_argument("--refresh", action="store_true", help="Ignore cache and re-fetch")
    args = parser.parse_args()

    schedule = keyframe_schedule()
    if args.dry_run:
        print(f"{len(schedule)} keyframes")
        for minute, age in schedule[:3] + schedule[-13:]:
            print(f"  minute {minute:9.4f}  {age:8.3f} Ma  {period_for(age)}")
        return 0

    ages = [age for _, age in schedule]

    print("→ coastlines + plate IDs")
    contours = load_coastlines()
    vertices = build_vertices(contours, args.refresh)
    home_pid = assign_plate_ids([(HOME["lat"], HOME["lon"])], args.refresh)[0]
    if home_pid == 0:
        raise ValueError("Home location is not on any plate")
    plate_ids = sorted({int(v[2]) for v in vertices} | {home_pid})
    print(f"  {len(vertices)} vertices on {len(plate_ids)} plates; home plate {home_pid}")

    print("→ rotations")
    rotations = fetch_rotations(plate_ids, ages, args.refresh)

    if any(rotations[a][home_pid] is None for a in ages):
        raise ValueError(f"Home plate {home_pid} is undefined at some keyframe")

    print(f"→ GPlates positions for {len(vertices)} vertices x {len(ages)} keyframes")
    recon = fetch_reconstructed(vertices, ages, args.refresh)
    births = birth_ages(recon, ages)
    hidden_at_start = sum(1 for b in births if b < START_MA)
    print(f"  {hidden_at_start} vertices not yet in the model at {START_MA:g} Ma (hidden until born)")

    print(f"→ merging plates within {MERGE_TOL_DEG:.3f}° (1 px at {MAP_WIDTH_PX} px), "
          "checked against GPlates for every live vertex")
    mapping, worst_merge = merge_plates(vertices, home_pid, rotations, recon)

    print("→ verifying home against reconstruct_points")
    by_minute = dict(schedule)
    check_ages = [by_minute[m] for m in CHECK_MINUTES]
    checks = verify_home(home_pid, rotations, check_ages, args.refresh)
    for c in checks:
        print(f"  {c['age']:6.1f} Ma  error {c['error_deg']:.5f}°")

    vertices = set_pens(vertices, mapping, births)
    plate_ids = sorted(set(mapping.values()))
    pen_ups = sum(1 for v in vertices if v[3] == 0)
    print(f"  {len(mapping)} plates -> {len(plate_ids)} representatives; "
          f"worst vertex error vs GPlates {worst_merge:.3f}°; {pen_ups} pen-ups")

    keyframes = []
    for minute, age in schedule:
        rot = rotations[age]
        keyframes.append(
            {
                "minute": minute,
                "age_ma": age,
                "period": period_for(age),
                # Plates absent at this age are omitted; the renderer hides their vertices
                "rotations": {str(p): rot[p] for p in plate_ids if rot[p] is not None},
            }
        )

    size = packed_size_estimate(len(vertices), len(plate_ids), len(keyframes))
    out = {
        "meta": {
            "model": MODEL,
            "generated": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "clock": {"start_ma": START_MA, "extinction_ma": EXTINCTION_MA,
                      "last_minute": LAST_MINUTE, "end_minute": round(END_MINUTE, 6)},
            "rotation_format": "[pole_lon, pole_lat, angle_deg], present -> age, right-hand",
            "home_checks": checks,
            "plate_merge": {"tolerance_deg": round(MERGE_TOL_DEG, 4),
                            "worst_error_deg": round(worst_merge, 4),
                            "checked": "every vertex at every keyframe where it exists",
                            "hidden_at_start": hidden_at_start,
                            "source_plates": len(mapping),
                            "representatives": len(plate_ids)},
            "packed_estimate": size,
            "sources": {
                "coastlines": "Natural Earth 1:110m land (public domain)",
                "plates": "GPlates Web Service, Merdith et al. 2021",
                "fossils": "Paleobiology Database (CC BY 4.0), see data/fossil_index.json",
            },
        },
        "reference_home": {**HOME, "plate_id": home_pid},
        "vertices": vertices,
        "keyframes": keyframes,
    }
    OUTPUT_PATH.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")

    print(f"  packed watch payload estimate: {size}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
