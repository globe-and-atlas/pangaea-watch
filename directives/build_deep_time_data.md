---
generated_by: "Claude Code CLI (claude-opus-5-5)"
timestamp: "2026-10-02T15:05:00-05:00"
---

# Directive: Build Deep-Time Data

## Goal

Produce the data file behind the Pangaea watch face: one clock day maps 252 Ma (midnight) to
66 Ma (23:59), and the final minute fast-forwards 66 Ma → today. The face shows present-day
coastlines rotated back to each age, with a crosshair on the fixed home location (Spring, TX)
traced back through its plate, plus "what's here": the nearest fossil taxa of that age.

The data format mirrors what the Pebble build will carry: coastline vertices tagged with plate IDs
(stored once) plus one Euler rotation per plate per keyframe. The browser preview applies those
rotations itself, so it proves the watch algorithm, not just the data.

## Validation Contract

> [!IMPORTANT]
> Binary assertions. Each one passes or fails on its own.

- [ ] `python3 execution/build_deep_time_data.py` exits 0
- [ ] `data/deep_time.json` exists after the run
- [ ] Keyframe at minute 0 has age 252.0 Ma
- [ ] Keyframe at minute 1439 has age 66.0 Ma
- [ ] Final keyframe has age 0.0 Ma
- [ ] Keyframe count is 108 (96 at 15-min spacing + 66 Ma + 11 fast-forward steps)
- [ ] Every coastline vertex carries a plate ID
- [ ] A pen-up is inserted wherever two consecutive vertices have different plate IDs
- [ ] Home position computed from stored rotations matches GPlates `reconstruct_points` within 0.1° at keyframe minutes 0, 720, 1200 and 1439 (252, ~158.9, ~97.0, 66 Ma)
- [ ] Home position at age 0 matches the present home coordinates within 0.01°
- [ ] Every keyframe has a `here` entry
- [ ] Every `here` entry states its distance tier (`here` / `nearby` / `region` / `none`)
- [ ] Every taxon listed in a `here` entry has a fossil age range containing that keyframe's age
- [ ] Estimated packed watch payload (int16 quaternions + int16 vertices) is printed by the script
- [ ] `index.html` renders the map in the Constellation pane-4 palette at 200×228 native resolution
- [ ] The preview crosshair sits at home's reconstructed position for the selected time
- [ ] The preview slider covers 00:00:00 through 23:59:59

## Inputs

- `data/ne_110m_land.json` — Natural Earth 1:110m land polygons (public domain), `[[lon, lat], ...]` per polygon; copied from overpass-watch so this repo has no cross-repo dependency
- GPlates Web Service (`gws.gplates.org`), model `MERDITH2021` (0–1000 Ma; MULLER2019 stops at 250 Ma)
- Paleobiology Database API (`paleobiodb.org/data1.2`)
- No `.env` keys required

## Tools/Scripts

- `execution/build_deep_time_data.py` — fetches plate IDs, rotations, fossils; verifies; writes JSON
- `execution/build_deep_time_data.py --dry-run` — prints the keyframe schedule only, no network
- `execution/build_deep_time_data.py --refresh` — ignore `.tmp/cache/` and re-fetch

## Outputs

| Artifact | Location | Format | Notes |
|----------|----------|--------|-------|
| Deep-time data | `data/deep_time.json` | JSON | Committed; consumed by `index.html` |
| API cache | `.tmp/cache/` | JSON | Gitignored |

## Edge Cases

- Points that fall on no plate get plate ID 0 and are dropped from coastlines
- Polylines crossing the antimeridian after rotation: renderer breaks the pen when |Δlon| > 180
- Fossil distance is measured in present-day coordinates. That equals paleo-distance only for
  fossils on the same rigid plate as home; cross-plate neighbours (e.g. Africa in Pangaea) are not considered
- Sparse intervals (Texas Jurassic) fall through to wider tiers or `none` — never invent a taxon

## Rollback Plan

Delete `data/deep_time.json`; nothing else is modified.

## Last Validated

<!-- YYYY-MM-DD — result -->

## Learnings

### 2026-10-02 — Verifier round 1 (REJECT) and scope change: any location

Verifier found (a) plates/crust absent from MERDITH2021 before some age were drawn at their
present position — GPlates returns rotation `[0, 90, 0]` and `reconstruct_points` 999.99 for them,
and a plate can have a rotation before its crust exists (plate 104); (b) the fast-forward ended at
24:00, so 23:59:59 showed 1.1 Ma; (c) four contract lines had no test; (d) legacy PBDB IDs
(family-level "Iguanodontidae indet." filed under accepted name *Iguanodon*; Cretaceous
"Plesiosaurus sp."). User then widened scope: **the face must work for anyone, anywhere**, and
asked for fossils in ancient geography + wider taxa (idea 1) and the events ticker, drift
odometer, environment and climate lines (idea 2).

Assertions in the original contract that referenced a fixed home (`home_paleo`, per-keyframe
`here`) are superseded by the revision below; home is now resolved at runtime (`src/home.js`).

## Validation Contract — Revision 2 (any location)

Data (`execution/build_deep_time_data.py`, `execution/build_fossil_index.py`):

- [ ] Final keyframe sits at minute 1439 + 59/60 (23:59:59) with age 0.0 Ma
- [ ] No stored rotation is the GPlates placeholder (angle 0 at age > 0)
- [ ] Every coastline vertex carries a birth age (oldest keyframe at which GPlates says it exists)
- [ ] Every vertex alive at a keyframe has a rotation for its plate at that keyframe
- [ ] Every alive vertex at every keyframe is within 1 px (1.875°) of GPlates `reconstruct_points`
- [ ] Every fossil index entry belongs to a record whose age range contains that frame's age
- [ ] Every fossil record's age range spans ≤ 25 My
- [ ] Excluded legacy records (Plesiosaurus younger than 174.7 Ma) are absent from the index
- [ ] Fossil paleo positions match GPlates `reconstruct_points` for a sample of entries within 0.1°
- [ ] Every event in `data/events.json` has an age, a label ≤ 26 characters, and a source

Preview (`index.html`, `src/*.js`), checked in headless Chrome:

- [ ] Canvas is 200×228; ocean is #000055; coastlines #AAFFAA; crosshair #FFAA00
- [ ] For Spring TX and London, the crosshair sits at GPlates' reconstructed position (±0.05°)
- [ ] At 23:59:59 the age is 0 and the crosshair is the present location (±0.01°)
- [ ] Honolulu at 03:00 shows no crosshair and "YOUR GROUND: NOT FORMED YET"
- [ ] JS `whatsHere` and Python `whats_here_at` return the same genera for the same input
- [ ] An event label shows on screen during its window (e.g. 08:00 → "ATLANTIC STARTS OPENING")
- [ ] The slider covers 00:00:00 through 23:59:59

### 2026-10-02 — Verifier round 2 (REJECT) fixes

- 66.0 Ma impact event used the 20-min Mesozoic window and stayed on through the fast-forward;
  Mesozoic windows now end at 23:59:00 and the impact gets 4 s like Cenozoic events
- Circular tests (reading the build's self-reported meta) replaced by recomputation against cached
  GPlates answers for every vertex × keyframe; fossil position sample widened to 4 frames
- Location lookup: per-request timeout + 3 retries; cache keyed by exact keyframe ages
- "SEA" footer only when the nearest find is marine and ≤ 400 km
- Contract wording: the not-yet-formed line reads "GROUND NOT FORMED YET" (shortened to fit 192 px)
