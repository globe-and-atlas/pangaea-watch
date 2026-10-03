"""Preview assertions (contract revision 2), checked in headless Chrome.

index.html publishes what it drew on <canvas data-state> when the clock is pinned with ?t=.
Home is resolved live against the GPlates Web Service, so these tests need network access.
"""

from __future__ import annotations

import html
import json
import re
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from functools import cache
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "execution"))

import build_deep_time_data as b
import build_fossil_index as f

CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
MAP = {"x": 4, "y": 32, "w": 192, "h": 96}
OXFORD, MINT, CHROME_YELLOW = "#000055", "#AAFFAA", "#FFAA00"
SPRING = (30.03, -95.53)
LONDON = (51.51, -0.13)
HONOLULU = (21.31, -157.86)


@pytest.fixture(scope="module")
def server() -> Iterator[str]:
    if not CHROME.exists():
        pytest.skip("Google Chrome not installed")
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(0.8)
    yield f"http://127.0.0.1:{port}"
    proc.terminate()


@cache
def _state(server: str, t: str, lat: float, lon: float) -> str:
    dom = subprocess.run(
        [str(CHROME), "--headless=new", "--disable-gpu", "--virtual-time-budget=30000",
         "--dump-dom", f"{server}/?t={t}&lat={lat}&lon={lon}&place=Buenos%20Aires"],
        capture_output=True, text=True, timeout=120, check=False,
    ).stdout
    m = re.search(r'data-state="([^"]*)"', dom)
    assert m, f"no data-state rendered at {t}"
    return html.unescape(m.group(1))


def state_at(server: str, t: str, where: tuple[float, float] = SPRING) -> dict:
    s = json.loads(_state(server, t, *where))
    assert s["ready"], f"home did not resolve at {t} {where}"
    return s


def minute_of(t: str) -> float:
    h, m, sec = map(int, t.split(":"))
    return h * 60 + m + sec / 60


def keyframe_at(t: str) -> tuple[int, float]:
    sched = b.keyframe_schedule()
    k = next(i for i, (m, _) in enumerate(sched) if m == minute_of(t))
    return k, sched[k][1]


def gplates_position(lat: float, lon: float, age: float) -> tuple[float, float]:
    data = b.fetch_json(
        f"{b.GPLATES}/reconstruct/reconstruct_points/",
        {"points": f"{lon},{lat}", "time": f"{age:g}", "model": b.MODEL},
        f"test_recon_{lat}_{lon}_{age:g}", refresh=False,
    )
    g_lon, g_lat = data["coordinates"][0]
    return g_lat, g_lon


def expected_cross(lat: float, lon: float) -> list[int]:
    # coord_to_screen() in constellation-watch ground_track.c (JS rounds to whole degrees first)
    lo, la = round(lon), max(-90, min(90, round(lat)))
    return [MAP["x"] + (lo + 180) * MAP["w"] // 360, MAP["y"] + (90 - la) * MAP["h"] // 180]


# ── Look ────────────────────────────────────────────────────────────────────

def test_canvas_is_emery_native(server: str) -> None:
    s = state_at(server, "12:00:00")
    assert (s["w"], s["h"]) == (200, 228)


def test_ocean_is_oxford_blue(server: str) -> None:
    colors = state_at(server, "12:00:00")["mapColors"]
    assert max(colors, key=colors.get) == OXFORD


def test_coastlines_are_mint(server: str) -> None:
    assert state_at(server, "12:00:00")["mapColors"].get(MINT, 0) > 200


def test_crosshair_is_chrome_yellow(server: str) -> None:
    assert state_at(server, "12:00:00")["crossColor"] == CHROME_YELLOW


def test_slider_spans_whole_day(server: str) -> None:
    assert state_at(server, "00:00:00")["slider"] == [0, 86399]


# ── Any location ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("where", [SPRING, LONDON], ids=["spring", "london"])
@pytest.mark.parametrize("t", ["00:00:00", "13:00:00", "23:59:00"])
def test_crosshair_at_gplates_position(server: str, t: str, where: tuple[float, float]) -> None:
    _, age = keyframe_at(t)
    expected = gplates_position(*where, age)
    s = state_at(server, t, where)
    assert b.angular_distance(*s["home"], *expected) < 0.05
    assert s["cross"] == expected_cross(*s["home"])


@pytest.mark.parametrize("where", [SPRING, LONDON], ids=["spring", "london"])
def test_235959_is_present_location(server: str, where: tuple[float, float]) -> None:
    s = state_at(server, "23:59:59", where)
    assert s["age"] == 0
    assert b.angular_distance(*s["home"], *where) < 0.01


def test_young_seafloor_has_no_crosshair(server: str) -> None:
    s = state_at(server, "03:00:00", HONOLULU)
    assert s["cross"] is None
    assert s["line1"] == "GROUND NOT FORMED YET"


@pytest.mark.parametrize("where", [SPRING, LONDON], ids=["spring", "london"])
@pytest.mark.parametrize("t", ["02:00:00", "13:00:00", "21:00:00"])
def test_js_and_python_whats_here_agree(server: str, t: str, where: tuple[float, float]) -> None:
    index = json.loads((ROOT / "data" / "fossil_index.json").read_text(encoding="utf-8"))
    k, _ = keyframe_at(t)
    s = state_at(server, t, where)
    py = f.whats_here_at(index, k, *s["home"])
    assert s["here"]["genera"] == [x["genus"] for x in py["taxa"]]
    assert s["here"]["tier"] == py["tier"]
    assert s["here"]["nearestKm"] == py["nearestKm"]
    assert s["here"]["marine"] == py["marine"]


def test_event_label_shows_in_window(server: str) -> None:
    # "Atlantic starts opening" is 190 Ma -> 07:59; it shows for 20 clock-minutes
    assert state_at(server, "08:00:00")["line4"] == "ATLANTIC STARTS OPENING"


def test_drift_odometer_outside_events(server: str) -> None:
    assert state_at(server, "17:00:00")["line4"].startswith("DRIFT ")


def test_impact_shows_at_2359(server: str) -> None:
    assert state_at(server, "23:59:02")["line4"] == "ASTEROID IMPACT"


@pytest.mark.parametrize("t", ["23:59:20", "23:59:40", "23:59:52"])
def test_fast_forward_not_stuck_on_impact(server: str, t: str) -> None:
    # Verifier round 2: the 66.0 Ma event used the 20-minute Mesozoic window
    line4 = state_at(server, t)["line4"]
    assert line4 != "ASTEROID IMPACT"
    assert line4.startswith("DRIFT ") or line4 in FF_LABELS


def test_mesozoic_events_end_at_2359(server: str) -> None:
    # T. rex (68 Ma) and Deccan (66.3 Ma) must not spill into the fast-forward
    assert state_at(server, "23:59:10")["line4"] not in {"TYRANNOSAURUS REX", "DECCAN TRAPS ERUPT"}


FF_LABELS = {e["label"] for e in json.loads((ROOT / "data" / "events.json").read_text(encoding="utf-8"))["events"]
             if e["age_ma"] <= 66.0}


SCENES = [("08:00:00", LONDON), ("03:00:00", HONOLULU), ("02:30:00", (-33.87, 151.21)),
          ("21:00:00", SPRING), ("17:00:00", SPRING), ("23:59:30", (-34.6, -58.38)),
          ("10:00:00", (39.9, 116.4)), ("13:00:00", (64.15, -21.94))]


@pytest.mark.parametrize(("t", "where"), SCENES)
def test_no_screen_text_truncated(server: str, t: str, where: tuple[float, float]) -> None:
    assert state_at(server, t, where)["truncated"] == []
