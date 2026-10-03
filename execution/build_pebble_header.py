#!/usr/bin/env python3
"""
execution/build_pebble_header.py
Generates watchface/src/c/pangaea_data.h and watchface/src/c/pangaea_data.c
from data/deep_time.json and data/events.json.
Packs quaternions as int16_t (-32767..32767) and vertices as int16_t (deg * 100).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEEP_TIME_PATH = ROOT / "data" / "deep_time.json"
EVENTS_PATH = ROOT / "data" / "events.json"
HEADER_PATH = ROOT / "watchface" / "src" / "c" / "pangaea_data.h"
SOURCE_PATH = ROOT / "watchface" / "src" / "c" / "pangaea_data.c"


def to_vec(lat: float, lon: float) -> tuple[float, float, float]:
    la, lo = math.radians(lat), math.radians(lon)
    return (math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la))


def euler_to_quat(euler: list[float] | None) -> tuple[int, int, int, int]:
    if not euler or euler[2] == 0:
        return (0, 0, 0, 0)
    pole_lon, pole_lat, angle = euler
    k = to_vec(pole_lat, pole_lon)
    h = math.radians(angle) / 2.0
    s = math.sin(h)
    w = math.cos(h)
    x = k[0] * s
    y = k[1] * s
    z = k[2] * s
    return (
        int(round(max(-1.0, min(1.0, w)) * 32767)),
        int(round(max(-1.0, min(1.0, x)) * 32767)),
        int(round(max(-1.0, min(1.0, y)) * 32767)),
        int(round(max(-1.0, min(1.0, z)) * 32767)),
    )


def generate_c_files() -> None:
    deep_time = json.loads(DEEP_TIME_PATH.read_text(encoding="utf-8"))
    events_data = json.loads(EVENTS_PATH.read_text(encoding="utf-8"))["events"]

    raw_vertices = deep_time["vertices"]
    all_keyframes = deep_time["keyframes"]

    # Subsample Mesozoic keyframes with stride 3 (every 45 minutes),
    # but keep the 66.0 Ma boundary (minute 1439) and all fast-forward steps.
    mesozoic = all_keyframes[:96]
    ff = all_keyframes[96:]
    subsampled_mesozoic = mesozoic[::3]
    if subsampled_mesozoic[-1]["minute"] != mesozoic[-1]["minute"]:
        subsampled_mesozoic.append(mesozoic[-1])
    keyframes = subsampled_mesozoic + ff

    plate_ids_set = set()
    for v in raw_vertices:
        plate_ids_set.add(int(v[2]))
    plate_ids = sorted(plate_ids_set)
    plate_id_to_idx = {pid: i for i, pid in enumerate(plate_ids)}

    n_vertices = len(raw_vertices)
    n_plates = len(plate_ids)
    n_keyframes = len(keyframes)
    n_events = len(events_data)

    HEADER_PATH.parent.mkdir(parents=True, exist_ok=True)

    header = f"""#pragma once
#include <pebble.h>

#define PANGAEA_NUM_VERTICES {n_vertices}
#define PANGAEA_NUM_PLATES {n_plates}
#define PANGAEA_NUM_KEYFRAMES {n_keyframes}
#define PANGAEA_NUM_EVENTS {n_events}

#define PANGAEA_MAP_X 4
#define PANGAEA_MAP_Y 32
#define PANGAEA_MAP_W 192
#define PANGAEA_MAP_H 96

#define PANGAEA_START_MA 2520      // 252.0 * 10
#define PANGAEA_EXTINCTION_MA 660  // 66.0 * 10
#define PANGAEA_LAST_MINUTE 1439   // 23:59:00

typedef struct {{
  int16_t lat_x100;
  int16_t lon_x100;
  uint8_t plate_idx;
  uint8_t pen_down;
  uint16_t birth_ma_x10;
}} PangaeaVertex;

typedef struct {{
  int16_t w, x, y, z;
}} PangaeaQuat16;

typedef struct {{
  uint16_t minute_x10; // e.g. 15.0 -> 150
  uint16_t age_ma_x10; // e.g. 252.0 -> 2520
  char period[20];
}} PangaeaKeyframe;

typedef struct {{
  uint16_t age_ma_x10;
  char label[28];
}} PangaeaEvent;

extern const int32_t s_pangaea_plate_ids[PANGAEA_NUM_PLATES];
extern const PangaeaVertex s_pangaea_vertices[PANGAEA_NUM_VERTICES];
extern const PangaeaKeyframe s_pangaea_keyframes[PANGAEA_NUM_KEYFRAMES];
extern const PangaeaQuat16 s_pangaea_rotations[PANGAEA_NUM_KEYFRAMES][PANGAEA_NUM_PLATES];
extern const PangaeaEvent s_pangaea_events[PANGAEA_NUM_EVENTS];

// Find plate index from plate ID, returns -1 if not found
int pangaea_find_plate_idx(int32_t plate_id);
"""

    HEADER_PATH.write_text(header, encoding="utf-8")

    lines: list[str] = [
        '#include "pangaea_data.h"',
        "",
        f"const int32_t s_pangaea_plate_ids[PANGAEA_NUM_PLATES] = {{",
        "  " + ", ".join(str(p) for p in plate_ids),
        "};",
        "",
        "int pangaea_find_plate_idx(int32_t plate_id) {",
        "  for (int i = 0; i < PANGAEA_NUM_PLATES; i++) {",
        "    if (s_pangaea_plate_ids[i] == plate_id) return i;",
        "  }",
        "  return -1;",
        "}",
        "",
        f"const PangaeaVertex s_pangaea_vertices[PANGAEA_NUM_VERTICES] = {{",
    ]

    for v in raw_vertices:
        lat, lon, pid, pen, birth = v
        lat_x100 = int(round(lat * 100))
        lon_x100 = int(round(lon * 100))
        pidx = plate_id_to_idx[int(pid)]
        pen_down = int(pen)
        birth_x10 = int(round(birth * 10))
        lines.append(f"  {{{lat_x100}, {lon_x100}, {pidx}, {pen_down}, {birth_x10}}},")
    lines.append("};")
    lines.append("")

    lines.append(f"const PangaeaKeyframe s_pangaea_keyframes[PANGAEA_NUM_KEYFRAMES] = {{")
    for k in keyframes:
        min_x10 = int(round(k["minute"] * 10))
        age_x10 = int(round(k["age_ma"] * 10))
        period = k["period"]
        lines.append(f'  {{{min_x10}, {age_x10}, "{period}"}},')
    lines.append("};")
    lines.append("")

    lines.append(f"const PangaeaQuat16 s_pangaea_rotations[PANGAEA_NUM_KEYFRAMES][PANGAEA_NUM_PLATES] = {{")
    for k in keyframes:
        lines.append("  {")
        row = []
        for pid in plate_ids:
            euler = k["rotations"].get(str(pid))
            q = euler_to_quat(euler)
            row.append(f"{{{q[0]}, {q[1]}, {q[2]}, {q[3]}}}")
        lines.append("    " + ", ".join(row))
        lines.append("  },")
    lines.append("};")
    lines.append("")

    lines.append(f"const PangaeaEvent s_pangaea_events[PANGAEA_NUM_EVENTS] = {{")
    for ev in events_data:
        age_x10 = int(round(ev["age_ma"] * 10))
        label = ev["label"]
        lines.append(f'  {{{age_x10}, "{label}"}},')
    lines.append("};")
    lines.append("")

    SOURCE_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Generated {HEADER_PATH} and {SOURCE_PATH}")
    print(f"  {n_vertices} vertices, {n_plates} plates, {n_keyframes} keyframes, {n_events} events")


if __name__ == "__main__":
    generate_c_files()
