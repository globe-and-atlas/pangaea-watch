# Task: pangaea-watch

## Objective

Prove the Pangaea watch face in a browser before writing Pebble C: a data pipeline that rotates
present-day coastlines and a fixed home point back through 252–0 Ma on a one-day clock, plus a
pane-4-styled preview that applies the same per-plate rotations the watch will.

## Context

- Directive: `directives/build_deep_time_data.md` (Validation Contract lives there)
- Visual source: `constellation-watch` pane 4 (`watchface/src/c/ground_track.c`)

## Acceptance Criteria

- [x] Objective is rewritten from template language into project language
- [x] Relevant directive exists in `directives/`
- [x] `execution/build_deep_time_data.py` exits 0
- [x] `python3 -m pytest tests -q` passes
- [x] Preview renders at 00:00, 06:35, 13:00, 17:00, 21:00, 23:59:30 (headless screenshots)
- [x] Independent verifier approves (round 1 REJECT, round 2 REJECT, round 3 APPROVE)
- [x] Works for any location (Spring, London, Sydney, Honolulu, Buenos Aires, Beijing, Reykjavik)
- [x] Fossils searched in ancient geography (global index)
- [x] Events ticker, drift odometer, climate band, marine signal
- [x] No screen text truncated (tested across 8 scenes)
- [x] `watchface/` builds cleanly with `pebble build` targeting `emery`
- [x] Static coastline vertices and keyframes compiled into ROM header (`pangaea_data.h`)
- [x] Watchface renders 200×228 layout (ocean, grid, coastlines, crosshair, text stack)
- [x] Dynamic tick timer: 1-minute cadence during Mesozoic, 1-second cadence during 23:59 fast-forward
- [x] PKJS transmits GPS/configured location and fossil find via AppMessage
- [x] Watch caches home state to persistent storage (`persist_write_data`)
- [x] 12-hour and 24-hour clock formatting options supported on both Pebble watchface and browser preview
- [x] Customizable font colors (time, taxon, coords, age, ticker, header, footer) supported across watch and preview
- [x] Ergonomic watchface redesign: hero 24px bold time + stacked period/age in header
- [x] Deep-Time "Day Arc" ribbon (Triassic amber, Jurassic cyan, Cretaceous mint, asteroid impact tick, white time needle)
- [x] Hero taxon typography (18px bold on Pebble, 14-15px adaptive on web preview) with contextual subline stack

## Steps

- [x] Scaffold project
- [x] Directive + Validation Contract
- [x] Data pipeline (GPlates + PBDB, cached)
- [x] Browser preview in pane-4 palette
- [x] Verifier pass (round 3 APPROVE)
- [x] Hosting/architecture plan: phone-side PKJS computes what's-here, watch carries coastlines in ROM
- [x] Generate `pangaea_data.h` from `data/deep_time.json` and `data/events.json`
- [x] Scaffold `watchface/` (wscript, package.json, src/c/, src/pkjs/)
- [x] Implement C rendering (`pangaea_map.c`, `main.c`) with dynamic tick timer
- [x] Implement PKJS companion (`src/pkjs/index.js`) for GPS resolution and AppMessage sync
- [x] Build and verify with `pebble build`
- [x] Ergonomic redesign: Hero time, Day Arc ribbon, and Hero Taxon

## Progress Log

### 2026-10-02 15:45 — Browser slice
- Changed: execution/build_deep_time_data.py, data/deep_time.json, index.html, src/app.js, style.css, tests/
- Test: `python3 -m pytest tests -q` ✅ 21 passed
- Next: verifier pass, then payload budget for emery

### 2026-10-02 19:30 — Any location + ideas 1 & 2
- Changed: execution/build_fossil_index.py (new), src/home.js (new), src/fossils.js (new), data/events.json (new), src/app.js, index.html, tests/
- Test: `python3 -m pytest tests -q` ✅ 59 passed
- Next: verifier round 2

### 2026-10-02 22:05 — Pebble Time 2 build kickoff
- Changed: knowledge/SESSION.md, task.md
- Plan: generate ROM header `pangaea_data.h`, implement watchface C renderer and PKJS bridge
- Next: write C code generator script

### 2026-10-02 22:20 — Pebble Time 2 (Emery) watchface operational
- Changed: execution/build_pebble_header.py (new), watchface/ (package.json, wscript, src/c/pangaea_data.[ch], src/c/math_geo.[ch], src/c/pangaea_map.[ch], src/c/main.c, src/pkjs/index.js), tests/test_pebble_build.py (new)
- Test: `pytest tests/test_pebble_build.py -v` ✅ 2 passed; `pebble build` in watchface/ creates `build/watchface.pbw` (57.2 KB RAM footprint, 73.8 KB free heap, 0 warnings)
- Next: 12/24 hour options and font color configuration

### 2026-10-02 22:30 — 12/24h time options and customizable font colors
- Changed: watchface/package.json, watchface/src/c/pangaea_map.[ch], watchface/src/c/main.c, watchface/src/pkjs/index.js, index.html, style.css, src/app.js
- Implemented: 12-hour vs 24-hour time formatting, customizable font colors (time, header, taxon, coords, age, ticker, footer) persisted across reloads on both watch and browser preview
- Test: `pebble clean && pebble build` ✅ creates watchface.pbw (72.9 KB free heap, 0 errors); `pytest tests/test_pebble_build.py -v` ✅ 2 passed

### 2026-10-03 11:10 — Ergonomic watchface redesign implemented
- Changed: `watchface/src/c/pangaea_map.c`, `src/app.js`, `task.md`, `knowledge/SESSION.md`
- Implemented:
  1. Top Bar: Hero Digital Time (24px Bold / 22px web) in top left, stacked Geological Period + Age in top right.
  2. Day Arc Ribbon: 4px multi-colored deep-time progress bar under map (Triassic Amber, Jurassic Cyan, Cretaceous Mint, Asteroid extinction tick, and white cursor needle).
  3. Telemetry Stack: 18px Hero Taxon line with adaptive scaling, context subline (formation & distance), event ticker / drift odometer, and paleo coordinates.
  4. Bottom Bar: Anchor with Home location label + Climate band.
- Test: `pebble build` in `watchface/` ✅ (58.5 KB RAM footprint, 72.6 KB free heap); full test suite `pytest -q` ✅ 70 passed in 92s.
