# Decisions

## Initial Decision

- Template profile: `hybrid-geospatial`
- Deploy target: `iis`
- Runtime: `hybrid`

## 2026-10-02 — Clock mapping

- Midnight = 252 Ma, 23:59 = 66 Ma (≈129,000 years per minute); final minute = 66 Ma → 0
- Alternatives: midnight = 233 Ma (first dinosaurs). Rejected: 252 lines periods up with the clock
  (Triassic ends 06:35, Jurassic ends 13:48) and noon lands in the Late Jurassic
- User chose: 252, fast-forward yes, fixed location, "what's here" when underwater

## 2026-10-02 — Per-plate rotations, not per-frame coastlines

- Store coastline vertices once with plate IDs, plus one Euler rotation per plate per keyframe;
  slerp between keyframes on device
- Alternative: 96+ pre-rotated coastline frames (~250 KB). Rejected: too large, and steps visibly
- Bonus: vertex correspondence across frames makes smooth interpolation free

## 2026-10-02 — Merge plates within 1 px

- MERDITH2021 splits coastlines across 209 plates. Plates whose every vertex stays within
  360/192° (one pane-4 pixel) of a larger plate's rotation, at every keyframe, are merged into it → 85
- Alternative: drop small plates. Rejected: top 40 plates cover only 62% of vertices
- Pen lifts wherever the representative plate changes, so no segment spans two moving plates

## 2026-10-02 — Fossils from PBDB, tiered

- Present-day box around home; tiers 400 / 1200 / 3000 km; non-avian dinosaurs ranked first
- Bird membership from an `Avialae` query, not PBDB's `class` field (Ichthyornis is filed as Reptilia)
- Ichnotaxa (PBDB flag `I`) labelled "TRACKS" — Glen Rose trackways are a feature, not noise

## 2026-10-02 — Any location (supersedes "fixed location for v1")

- User: "supposed to work for anybody anywhere on earth". Home is resolved at runtime
  (`src/home.js`): plate ID (1 call) + that plate's rotations at all keyframes (1 call) + binary
  search for when the ground first exists (~7 `reconstruct_points` calls). Cached per location.
- Build-time data is now location-free: coastlines/rotations (`deep_time.json`) and a global fossil
  index (`fossil_index.json`). Spring TX stays only as a reference point for rotation checks.
- Same calls will run in Pebble phone-side JS; both APIs send `Access-Control-Allow-Origin: *`.

## 2026-10-02 — Existence from reconstruct_points, per vertex

- Verifier: plates absent before some age were drawn at present position. Rotation `[0,90,0]` is
  not a sufficient signal — plate 104 has a rotation at 252 Ma while its crust does not exist.
- Each vertex carries a birth age (oldest keyframe where `reconstruct_points` is valid). Merge and
  verification compare against GPlates for every live vertex at every keyframe.

## 2026-10-02 — Fossils in ancient geography (idea 1)

- Global PBDB pull (dinosaurs, pterosaurs, marine reptiles, early archosaurs, croc relatives,
  turtles, early mammals, ammonites) → filter → dedupe by (genus, 0.5° cell, range) → reconstruct
  each live cell at each Mesozoic keyframe with MERDITH2021 (PBDB's own paleocoords lack Merdith)
- Search is nearest-neighbour between ancient positions, so cross-plate neighbours count
- Headline groups (dinosaur, bird, pterosaur, marine reptile, archosaur) claim every tier before
  ammonites/turtles/crocs/mammals; otherwise ammonites headline every coastal scene
- Age-range cutoff 25 My (20 My dropped Antlers Fm., 20.9 My)

## 2026-10-02 — Idea 2 layers

- Events ticker (`data/events.json`, global, sourced), drift odometer (cumulative km + cm/yr),
  climate band from paleolatitude, "SEA FINDS" when the nearest find of any kind is marine
- Hand-written "ground biography" dropped: cannot be written for every place on Earth; replaced by
  the data-derived environment line (band + marine signal + crust existence)
