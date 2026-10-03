# Project Context

## Identity

- Name: `pangaea-watch`
- Profile: `hybrid-geospatial`
- Target device: Pebble Time 2 (`emery`, 200×228, 64-colour)
- Sibling project: `constellation-watch` (visual source: pane 4, World Map)

## Purpose

A watch face where one day is the age of dinosaurs. Midnight = 252 Ma (start of the Mesozoic),
23:59 = 66 Ma (K-Pg extinction), and the final minute fast-forwards 66 Ma → today, landing exactly
on the present map at 23:59:59. The crosshair is the wearer's home ground (anywhere on Earth), carried
back on its tectonic plate, and "what's here" names the nearest fossil taxa of that age.

Use: an ambient, daily sense of deep time. Beauty: the Constellation pane-4 look, reused deliberately.

## Constraints

- Any home location on Earth, resolved at runtime (phone GPS on Pebble; presets/geolocation in preview)
- `MERDITH2021` plate model — the only GPlates model here that reaches 252 Ma (`MULLER2019` stops at 250)
- Coastlines are present-day Natural Earth outlines rotated back — not paleo-shorelines (no Western Interior Seaway)
- Fossil distance is measured between ancient positions (global index, same plate model)
- Watch payload must be small: per-plate rotations, not per-frame coastlines

## Out of Scope (v1)

- Paleo-shoreline / sea-level layer
- Cenozoic fauna during the fast-forward minute
