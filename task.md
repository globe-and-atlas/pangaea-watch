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

## Steps

- [x] Scaffold project
- [x] Directive + Validation Contract
- [x] Data pipeline (GPlates + PBDB, cached)
- [x] Browser preview in pane-4 palette
- [x] Verifier pass (round 3 APPROVE)
- [ ] Hosting plan for fossil index (2.5 MB) for phone-side JS
- [ ] Pebble build: shrink payload (≈80 KB now) — hourly keyframes or coarser merge tolerance
- [ ] Pebble build: fixed-point quaternion slerp on device

## Progress Log

### 2026-10-02 15:45 — Browser slice
- Changed: execution/build_deep_time_data.py, data/deep_time.json, index.html, src/app.js, style.css, tests/
- Test: `python3 -m pytest tests -q` ✅ 21 passed
- Next: verifier pass, then payload budget for emery

### 2026-10-02 19:30 — Any location + ideas 1 & 2
- Changed: execution/build_fossil_index.py (new), src/home.js (new), src/fossils.js (new), data/events.json (new), src/app.js, index.html, tests/
- Test: `python3 -m pytest tests -q` ✅ 59 passed
- Next: verifier round 2
