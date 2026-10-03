#!/usr/bin/env python3
"""
execution/build_fossil_index.py
Builds data/fossil_index.json: every usable Mesozoic fossil occurrence worldwide, placed at its
ancient position for each keyframe it is alive in, using the same MERDITH2021 model as the
coastlines. At runtime "what's here" is then a nearest-neighbour search in ancient geography
from any home location -- so a Texas site can find its Pangaean neighbours in Africa.

PBDB's own paleocoordinates only support the gplates/scotese/seton models, so positions are
reconstructed here with GPlates instead, keeping home and fossils in one plate model.
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

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_deep_time_data import (
    EXTINCTION_MA,
    GPLATES,
    MODEL,
    PBDB,
    ROOT,
    START_MA,
    angular_distance,
    fetch_json,
    keyframe_schedule,
)

OUTPUT_PATH = ROOT / "data" / "fossil_index.json"
EXCLUSIONS_PATH = ROOT / "data" / "taxon_exclusions.json"

# Present-day locations snap to this grid before reconstruction (0.5 deg ~ 55 km),
# well under the smallest search tier.
CELL_DEG = 0.5
MAX_RANGE_MY = 25.0  # keeps two-stage formation dates (Antlers 20.9 My); drops series-level (>= 34 My)
GENUS_RANKS = ("genus", "subgenus", "species", "subspecies")
UNCERTAIN_MARKERS = ("?", " cf.", "cf. ", " aff.", "aff. ", '"')

TAXON_GROUPS = [
    ("Dinosauria", "dinosaur"),
    ("Pterosauria", "pterosaur"),
    ("Plesiosauria", "marine reptile"),
    ("Ichthyosauria", "marine reptile"),
    ("Mosasauridae", "marine reptile"),
    ("Phytosauria", "archosaur"),
    ("Aetosauria", "archosaur"),
    ("Crocodylomorpha", "croc relative"),
    ("Testudinata", "turtle"),
    ("Mammaliaformes", "early mammal"),
    ("Ammonoidea", "ammonite"),
]
MARINE_GROUPS = ("marine reptile", "ammonite")
HEADLINE_GROUPS = ("dinosaur", "bird", "pterosaur", "marine reptile", "archosaur")
TIERS = [("here", 400), ("nearby", 1200), ("region", 3000)]
MAX_TAXA = 3
POST_CHUNK = 2500


def keep(rec: dict[str, Any], exclusions: dict[str, Any]) -> bool:
    """Genus-level, certain, stage-dated, and not on the exclusion list."""
    # PBDB files e.g. "Iguanodontidae indet." under accepted name Iguanodon, so both the
    # accepted name and the original identification must be genus-level
    if rec.get("accepted_rank") not in GENUS_RANKS or rec.get("identified_rank") not in GENUS_RANKS:
        return False
    if any(m in f" {rec.get('identified_name') or ''} " for m in UNCERTAIN_MARKERS):
        return False
    try:
        max_ma, min_ma = float(rec["max_ma"]), float(rec["min_ma"])
        float(rec["lat"]), float(rec["lng"])
    except (KeyError, TypeError, ValueError):
        return False
    if max_ma - min_ma > MAX_RANGE_MY or max_ma < EXTINCTION_MA or min_ma > START_MA:
        return False
    rule = exclusions.get(rec["accepted_name"].split()[0])
    return not (rule and min_ma < rule.get("younger_than_ma", math.inf))


def fetch_group(base: str, refresh: bool) -> list[dict[str, Any]]:
    data = fetch_json(
        f"{PBDB}/occs/list.json",
        {"base_name": base, "interval": "Triassic,Cretaceous",
         "show": "coords,strat,ident", "vocab": "pbdb"},
        f"pbdb_global_v1_{base}",
        refresh,
    )
    if data.get("errors"):
        raise ValueError(f"PBDB error for {base}: {data['errors']}")
    return data.get("records", [])


def collect(refresh: bool) -> list[dict[str, Any]]:
    """Deduplicated records: one per (genus, present cell, age range, trace)."""
    exclusions = {
        k: v for k, v in json.loads(EXCLUSIONS_PATH.read_text(encoding="utf-8")).items()
        if not k.startswith("_")
    }
    # Birds are dinosaurs, but a seabird should not headline a sea scene; PBDB's class field
    # is unreliable for birds, so membership comes from the Avialae subtree
    birds = {r["accepted_name"].split()[0] for r in fetch_group("Avialae", refresh)}
    seen: dict[tuple, dict[str, Any]] = {}
    raw = 0
    for base, group in TAXON_GROUPS:
        recs = fetch_group(base, refresh)
        raw += len(recs)
        for rec in recs:
            if not keep(rec, exclusions):
                continue
            genus = rec["accepted_name"].split()[0]
            cell = (round(float(rec["lat"]) / CELL_DEG) * CELL_DEG,
                    round(float(rec["lng"]) / CELL_DEG) * CELL_DEG)
            trace = "I" in (rec.get("flags") or "")
            key = (genus, cell, float(rec["max_ma"]), float(rec["min_ma"]), trace)
            if key not in seen:
                seen[key] = {
                    "genus": genus,
                    "group": "bird" if genus in birds else group,
                    "trace": trace,
                    "cell": cell,
                    "max_ma": float(rec["max_ma"]),
                    "min_ma": float(rec["min_ma"]),
                    "formation": rec.get("formation") or "",
                }
        print(f"  {base:16s} {len(recs):6d} raw")
    print(f"  {raw} raw -> {len(seen)} kept after filters + dedupe")
    return list(seen.values())


def reconstruct_cells(
    cells: list[tuple[float, float]], age: float, refresh: bool
) -> list[tuple[float, float] | None]:
    """GPlates position of each present cell at `age`; None where that crust is not in the model."""
    out: list[tuple[float, float] | None] = []
    for i in range(0, len(cells), POST_CHUNK):
        chunk = cells[i : i + POST_CHUNK]
        flat = ",".join(f"{lon},{lat}" for lat, lon in chunk)
        data = fetch_json(
            f"{GPLATES}/reconstruct/reconstruct_points/",
            {"points": flat, "time": f"{age:g}", "model": MODEL},
            f"recon_cells_{MODEL}_{age:g}_{hashlib.sha1(flat.encode()).hexdigest()[:12]}",
            refresh,
            post=True,
        )
        coords = data["coordinates"]
        if len(coords) != len(chunk):
            raise ValueError(f"reconstruct_points returned {len(coords)} of {len(chunk)} at {age} Ma")
        out.extend((c[1], c[0]) if abs(c[1]) <= 90 else None for c in coords)
    return out


def whats_here_at(index: dict[str, Any], frame: int, lat: float, lon: float) -> dict[str, Any]:
    """Reference implementation of src/fossils.js whatsHere() -- tests check the two agree.
    Headline groups claim every tier first; other groups fill only when no headline taxon is
    within the widest tier. Non-avian dinosaurs rank first, then distance, then name."""
    best: dict[str, dict[str, Any]] = {}
    nearest: tuple[int, str] | None = None
    for ri, plat10, plon10 in index["frames"][frame]:
        d = math.radians(angular_distance(lat, lon, plat10 / 10, plon10 / 10)) * 6371.0
        if d > TIERS[-1][1]:
            continue
        ti, max_ma, min_ma, fi = index["records"][ri]
        genus, group, trace = index["taxa"][ti]
        km = math.floor(d + 0.5)  # half-up, matching JS Math.round
        if nearest is None or km < nearest[0]:
            nearest = (km, group)
        if genus not in best or km < best[genus]["distKm"]:
            best[genus] = {"genus": genus, "group": group, "trace": bool(trace), "distKm": km,
                           "formation": index["formations"][fi], "rangeMa": [max_ma, min_ma]}
    env = {"nearestKm": nearest[0] if nearest else None,
           "marine": bool(nearest) and nearest[1] in index["meta"]["marine_groups"]
           and nearest[0] <= TIERS[0][1]}
    everything = list(best.values())
    for pool in ([t for t in everything if t["group"] in HEADLINE_GROUPS], everything):
        for tier, radius in TIERS:
            in_tier = [t for t in pool if t["distKm"] <= radius]
            if in_tier:
                in_tier.sort(key=lambda t: (t["group"] != "dinosaur", t["distKm"], t["genus"]))
                return {"tier": tier, "radiusKm": radius, "taxa": in_tier[:MAX_TAXA], **env}
    return {"tier": "none", "radiusKm": TIERS[-1][1], "taxa": [], **env}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Ignore cache and re-fetch")
    parser.add_argument("--dry-run", action="store_true", help="Fetch + filter only; no reconstruction")
    args = parser.parse_args()

    print("→ PBDB occurrences (global)")
    records = collect(args.refresh)
    if args.dry_run:
        return 0

    taxa_keys = sorted({(r["genus"], r["group"], r["trace"]) for r in records})
    taxon_idx = {k: i for i, k in enumerate(taxa_keys)}
    formations = sorted({r["formation"] for r in records})
    formation_idx = {f: i for i, f in enumerate(formations)}

    schedule = [(m, a) for m, a in keyframe_schedule() if a >= EXTINCTION_MA]
    frames: list[list[list[int]]] = []
    dropped = 0
    t0 = time.time()
    print(f"→ reconstructing live fossil cells at {len(schedule)} Mesozoic keyframes")
    for ki, (_, age) in enumerate(schedule):
        live = [i for i, r in enumerate(records) if r["min_ma"] <= age <= r["max_ma"]]
        cells = sorted({records[i]["cell"] for i in live})
        positions = dict(zip(cells, reconstruct_cells(cells, age, args.refresh)))
        entries = []
        for i in live:
            pos = positions[records[i]["cell"]]
            if pos is None:
                dropped += 1
                continue
            entries.append([i, round(pos[0] * 10), round(pos[1] * 10)])
        frames.append(entries)
        if ki % 12 == 0:
            print(f"  {age:7.2f} Ma  {len(live):5d} live  {len(cells):5d} cells  ({time.time() - t0:.0f}s)")

    out = {
        "meta": {
            "model": MODEL,
            "generated": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "cell_deg": CELL_DEG,
            "max_range_my": MAX_RANGE_MY,
            "marine_groups": list(MARINE_GROUPS),
            "frame_ages": [a for _, a in schedule],
            "entry_format": "[record_index, paleo_lat*10, paleo_lon*10]",
            "record_format": "[taxon_index, max_ma, min_ma, formation_index]",
            "taxon_format": "[genus, group, is_trace]",
            "dropped_unreconstructable": dropped,
            "source": "Paleobiology Database (CC BY 4.0); positions via GPlates MERDITH2021",
        },
        "taxa": [[g, grp, int(tr)] for g, grp, tr in taxa_keys],
        "formations": formations,
        "records": [
            [taxon_idx[(r["genus"], r["group"], r["trace"])], r["max_ma"], r["min_ma"],
             formation_idx[r["formation"]]]
            for r in records
        ],
        "frames": frames,
    }
    OUTPUT_PATH.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    n_entries = sum(len(f) for f in frames)
    print(f"→ wrote {OUTPUT_PATH.relative_to(ROOT)} ({OUTPUT_PATH.stat().st_size // 1024} KB); "
          f"{len(records)} records, {n_entries} frame entries, {dropped} unreconstructable")
    return 0


if __name__ == "__main__":
    sys.exit(main())
