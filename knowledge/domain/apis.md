---
generated_by: "Claude Code CLI (claude-opus-5-5)"
timestamp: "2026-10-02T15:40:00-05:00"
---

# API Notes

## GPlates Web Service (`https://gws.gplates.org`)

- `reconstruct/reconstruct_points/?points=LON,LAT[,LON,LAT...]&time=MA&model=M` → GeoJSON MultiPoint
- `reconstruct/assign_points_plate_ids/?points=...&model=M` → `[pid, ...]`; 0 = no plate
- `rotation/get_euler_pole_and_angle?times=A,B&pids=P,Q&model=M` →
  `{"A.0": {"P": [pole_lon, pole_lat, angle_deg]}}` — keys are floats as strings
- Rotation convention verified: right-hand rotation about (pole_lat, pole_lon), present → age.
  Reproduces `reconstruct_points` to ~0.00005°
- `MULLER2019` covers 0–250 Ma only (error text names `big_time: 250`); `MERDITH2021` covers 252
- `return_plate_ids` on reconstruct_points is silently ignored
- Plate 101 = North America (Spring, TX)
- `reconstruct_points` accepts POST (form field `points`) — 1,465+ points per call works
- Existence: `reconstruct_points` → 999.99 when the crust is not in the model at that age. A plate can
  have a non-placeholder rotation before its crust exists (plate 104 at 252 Ma), so use this, not the rotation
- Rotation placeholder for an absent plate: `[0.0, 90.0, 0.0]`
- Both GPlates and PBDB send `Access-Control-Allow-Origin: *` (browser/phone JS can call directly)

## Paleobiology Database (`https://paleobiodb.org/data1.2`)

- `occs/list.json?base_name=X&interval=Triassic,Cretaceous&lngmin..&latmax..&vocab=pbdb&show=coords,strat,ident,class`
- `flags` contains `I` for ichnotaxa (footprint genera) — needs `show=ident`
- `class` is unreliable for birds; use `base_name=Avialae` membership
- `max_ma` / `min_ma` are stage-level ranges (often several My), so one genus spans many keyframes
- Licence: CC BY 4.0
- `pgm` (paleocoordinate model) only accepts `gplates`, `scotese`, `seton` — no Merdith 2021
- `accepted_name` can be a genus while the identification was family-level ("Iguanodontidae indet."
  → Iguanodon); check `identified_rank` too
- Global Triassic–Cretaceous counts (2026-10): Dinosauria 22k, Ammonoidea 80k occurrences
