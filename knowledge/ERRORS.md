# Errors

Record deterministic errors, root causes, and fixes here.

## 2026-10-02 — Verify step returned 252 Ma rotations for every age

- Error: `ValueError: No rotations returned for 159.0 Ma`
- Cause: cache key for single-plate rotation lookups omitted the age → every call hit the 252 Ma cache file
- Fix: verification uses the stored keyframe rotations directly (what the contract asks for anyway)
- Graduated-to: cache keys must encode every request parameter (`knowledge/procedural/build_data.md`)

## 2026-10-02 — Python `hash()` in cache keys

- Cause: `hash()` is salted per process → cache never hit across runs
- Fix: `hashlib.sha1(...)` prefix

## 2026-10-02 — Seabird headlined a marine scene as "dinosaur"

- Cause: PBDB `class` is inconsistent for birds (Ichthyornis → Reptilia)
- Fix: tag birds by membership in a separate `base_name=Avialae` query

## 2026-10-02 — Verifier REJECT round 1

- Absent plates drawn at present position → per-vertex birth from `reconstruct_points` (see DECISIONS)
- 23:59:59 showed 1.1 Ma: fast-forward mapped to 24:00 → now ends at minute 1439 + 59/60
- Contract lines without tests → `tests/test_preview.py` drives headless Chrome via a `data-state` hook
- Headless `--dump-dom` raced the rAF loop (flaky) → pinned mode renders synchronously
- PBDB files "Iguanodontidae indet." under accepted name *Iguanodon* → require genus-level
  `identified_rank` too; "cf."/"?" IDs dropped; Cretaceous "Plesiosaurus sp." excluded with reason
- Records dated only to a period (e.g. Liodon "Cretaceous", 77 My) put a Late Cretaceous mosasaur
  at 135 Ma → age-range cutoff
