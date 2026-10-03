# Pangaea Watch

A Pebble Time 2 watch face concept where one day is the age of dinosaurs, for wherever you are.

- **00:00**: 252 million years ago, start of the Mesozoic. Your ground sits inside Pangaea, or
  doesn't exist yet if it's young seafloor.
- **06:31**: end-Triassic extinction; Pangaea starts to break up.
- **13:48**: Cretaceous begins.
- **23:59**: 66 million years ago, the asteroid.
- **23:59:00 to 23:59:59**: the last 66 million years in under a minute, landing exactly on today's map.

The yellow crosshair is your location carried back on its tectonic plate. "What's here" names the
nearest fossil finds of that age, measured in ancient geography, so in the Triassic a Texan can
find neighbours that are now in Africa. A global events ticker, a drift odometer and a climate band
fill the quiet stretches.

The look is borrowed from pane 4 (World Map) of [Constellation](../constellation-watch).

## Run

```bash
source .venv/bin/activate
python3 execution/build_deep_time_data.py   # coastlines + plate rotations -> data/deep_time.json
python3 execution/build_fossil_index.py     # global fossils at ancient positions -> data/fossil_index.json
python3 -m pytest tests -q                  # ~90 s; preview tests use headless Chrome + network
python3 -m http.server 8765                 # http://localhost:8765
```

URL parameters: `?t=17:00:00` pins the clock; `&lat=51.51&lon=-0.13&place=London` sets the location.

## How it works

- **Coastlines:** vertices are stored once with a plate ID and a birth age. Each keyframe stores one
  rotation per plate; the renderer slerps between keyframes. This is the format the watch will carry.
- **Home (any location):** resolved at runtime in `src/home.js`: plate ID, that plate's rotations, and
  when the ground first exists, which takes about 9 requests to the GPlates Web Service and is cached.
- **Fossils:** `data/fossil_index.json` holds about 32k PBDB records, each reconstructed to its ancient
  position at every keyframe it lived through. `src/fossils.js` searches it around your ancient position.

## Sources

- Coastlines: [Natural Earth](https://www.naturalearthdata.com/) 1:110m land (public domain)
- Plate model: [GPlates Web Service](https://gws.gplates.org/), Merdith et al. 2021
- Fossils: [Paleobiology Database](https://paleobiodb.org/) (CC BY 4.0)
- Events: `data/events.json`, each with a reference (spot-check before publishing)

## Known limits

- Coastlines are today's outlines moved back, not ancient shorelines
- "SEA" means the nearest find is marine, not a sea-level reconstruction
- The packed watch payload is about 70 KB for coastlines and 2.5 MB for the fossil index, both too
  large for the watch. The phone must compute "what's here" and send only the results
