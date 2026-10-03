"""Validation contract for directives/build_deep_time_data.md (coastlines + rotations)."""

from __future__ import annotations

import itertools
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "execution"))

import build_deep_time_data as b

DATA_PATH = ROOT / "data" / "deep_time.json"


@pytest.fixture(scope="module")
def data() -> dict:
    if not DATA_PATH.exists():
        pytest.skip("run execution/build_deep_time_data.py first")
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def frame_at(data: dict, minute: float) -> dict:
    return next(k for k in data["keyframes"] if k["minute"] == minute)


# ── Clock mapping (pure functions) ───────────────────────────────────────────

def test_age_at_midnight_is_252() -> None:
    assert b.age_at_minute(0) == 252.0


def test_age_at_2359_is_66() -> None:
    assert b.age_at_minute(1439) == pytest.approx(66.0)


def test_fast_forward_reaches_present_at_235959() -> None:
    assert b.age_at_minute(1439 + 59 / 60) == 0.0


def test_period_boundary_belongs_to_older_period() -> None:
    assert b.period_for(66.0) == "Late Cretaceous"


def test_rotation_reproduces_known_gplates_point() -> None:
    # GPlates reconstruct_points: (-95.4, 30.0) at 100 Ma, MERDITH2021 -> (-50.5785, 32.6604)
    lat, lon = b.rotate(30.0, -95.4, [119.56199818, 71.67125211, 39.41180963])
    assert b.angular_distance(lat, lon, 32.6604, -50.5785) < 0.001


# ── Keyframes ────────────────────────────────────────────────────────────────

def test_keyframe_minute_0_is_252(data: dict) -> None:
    assert frame_at(data, 0.0)["age_ma"] == 252.0


def test_keyframe_minute_1439_is_66(data: dict) -> None:
    assert frame_at(data, 1439.0)["age_ma"] == 66.0


def test_final_keyframe_is_present(data: dict) -> None:
    assert data["keyframes"][-1]["age_ma"] == 0.0


def test_final_keyframe_is_at_235959(data: dict) -> None:
    assert data["keyframes"][-1]["minute"] == pytest.approx(1439 + 59 / 60, abs=1e-5)


def test_keyframe_count_is_108(data: dict) -> None:
    assert len(data["keyframes"]) == 108


# ── Plates and coastlines ────────────────────────────────────────────────────

def test_every_vertex_has_plate_id(data: dict) -> None:
    assert all(isinstance(v[2], int) and v[2] > 0 for v in data["vertices"])


def test_no_placeholder_rotation_stored(data: dict) -> None:
    # GPlates' [0, 90, 0] means "plate not in model yet"; it must never be drawn as real
    for k in data["keyframes"]:
        if k["age_ma"] > 0:
            assert all(e[2] != 0.0 for e in k["rotations"].values()), k["minute"]


def test_every_vertex_has_birth_age(data: dict) -> None:
    assert all(0 <= v[4] <= 252.0 for v in data["vertices"])


def test_born_vertex_plate_has_rotation(data: dict) -> None:
    for k in data["keyframes"]:
        live = {str(v[2]) for v in data["vertices"] if k["age_ma"] <= v[4]}
        assert live <= set(k["rotations"]), k["minute"]


def test_some_vertices_hidden_at_midnight(data: dict) -> None:
    # Baja, Central America, the Caribbean etc. are not in MERDITH2021 at 252 Ma
    assert data["meta"]["plate_merge"]["hidden_at_start"] > 0


def test_pen_lifts_on_plate_change(data: dict) -> None:
    vs = data["vertices"]
    assert all(cur[3] == 0 for prev, cur in itertools.pairwise(vs) if prev[2] != cur[2])


@pytest.fixture(scope="module")
def recon(data: dict) -> dict:
    # GPlates' own answer for every stored vertex at every keyframe (cached API responses)
    if not (ROOT / ".tmp" / "cache").exists():
        pytest.skip("needs cached API responses")
    ages = [k["age_ma"] for k in data["keyframes"]]
    return b.fetch_reconstructed(data["vertices"], ages, refresh=False)


def test_birth_is_oldest_keyframe_gplates_has_vertex(data: dict, recon: dict) -> None:
    ages = [k["age_ma"] for k in data["keyframes"]]
    for i, v in enumerate(data["vertices"]):
        oldest = next(a for a in ages if recon[a][i] is not None)
        assert v[4] == oldest, (i, v[4], oldest)


def test_every_live_vertex_within_one_pixel_of_gplates(data: dict, recon: dict) -> None:
    # Recomputed independently of the build's self-reported meta
    worst = 0.0
    for k in data["keyframes"]:
        for i, v in enumerate(data["vertices"]):
            truth = recon[k["age_ma"]][i]
            if truth is None:
                continue
            lat, lon = b.rotate(v[0], v[1], k["rotations"][str(v[2])])
            worst = max(worst, b.angular_distance(lat, lon, *truth))
    assert worst <= b.MERGE_TOL_DEG


def test_hidden_vertices_absent_in_gplates(data: dict, recon: dict) -> None:
    for k in data["keyframes"]:
        for i, v in enumerate(data["vertices"]):
            if k["age_ma"] > v[4]:
                assert recon[k["age_ma"]][i] is None, (k["minute"], i)


def test_script_prints_payload_estimate() -> None:
    if not (ROOT / ".tmp" / "cache").exists():
        pytest.skip("needs cached API responses")
    out = subprocess.run(
        [sys.executable, str(ROOT / "execution" / "build_deep_time_data.py")],
        capture_output=True, text=True, timeout=600, check=True,
    ).stdout
    assert "packed watch payload estimate" in out
