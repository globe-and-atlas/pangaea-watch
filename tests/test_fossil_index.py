"""Validation contract (revision 2) for data/fossil_index.json and data/events.json."""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "execution"))

import build_deep_time_data as b
import build_fossil_index as f

INDEX_PATH = ROOT / "data" / "fossil_index.json"
EVENTS_PATH = ROOT / "data" / "events.json"


@pytest.fixture(scope="module")
def index() -> dict:
    if not INDEX_PATH.exists():
        pytest.skip("run execution/build_fossil_index.py first")
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


def test_frames_cover_mesozoic_keyframes(index: dict) -> None:
    mesozoic = [a for _, a in b.keyframe_schedule() if a >= b.EXTINCTION_MA]
    assert index["meta"]["frame_ages"] == mesozoic


def test_every_entry_record_alive_at_frame_age(index: dict) -> None:
    for age, entries in zip(index["meta"]["frame_ages"], index["frames"]):
        for ri, _, _ in entries:
            _, max_ma, min_ma, _ = index["records"][ri]
            assert min_ma <= age <= max_ma, (age, ri)


def test_every_record_range_within_limit(index: dict) -> None:
    assert all(r[1] - r[2] <= f.MAX_RANGE_MY for r in index["records"])


def test_every_entry_has_valid_paleo_position(index: dict) -> None:
    for entries in index["frames"]:
        for _, lat10, lon10 in entries:
            assert -900 <= lat10 <= 900 and -1800 <= lon10 <= 1800


def test_excluded_plesiosaurus_absent(index: dict) -> None:
    for ti, max_ma, min_ma, _ in index["records"]:
        assert not (index["taxa"][ti][0] == "Plesiosaurus" and min_ma < 174.7)


def test_family_level_iguanodon_records_absent(index: dict) -> None:
    # Only Cedar Mountain's named species may remain; legacy family-level IDs must not
    names = {index["formations"][fi] for ti, _, _, fi in index["records"] if index["taxa"][ti][0] == "Iguanodon"}
    assert "Bissett Conglomerate" not in names


@pytest.mark.parametrize("frame", [0, 30, 60, 96])
def test_paleo_positions_match_gplates_sample(index: dict, frame: int) -> None:
    # Re-derive a sample of positions from GPlates (cached) using each record's present cell
    rng = random.Random(frame)
    age = index["meta"]["frame_ages"][frame]
    cells_by_record = {}
    for rec in f.collect(refresh=False):
        key = (rec["genus"], rec["group"], rec["trace"])
        cells_by_record.setdefault((key, rec["max_ma"], rec["min_ma"]), []).append(rec["cell"])
    sample = rng.sample(index["frames"][frame], min(25, len(index["frames"][frame])))
    worst = 0.0
    for ri, lat10, lon10 in sample:
        ti, max_ma, min_ma, _ = index["records"][ri]
        genus, group, trace = index["taxa"][ti]
        cells = cells_by_record[((genus, group, bool(trace)), max_ma, min_ma)]
        recon = [p for p in f.reconstruct_cells(cells, age, refresh=False) if p]
        best = min(b.angular_distance(lat10 / 10, lon10 / 10, *p) for p in recon)
        worst = max(worst, best)
    assert worst < 0.1


def test_whats_here_prefers_headline_taxa(index: dict) -> None:
    # Spring TX at 17:00 (keyframe 68): Acrocanthosaurus outranks nearer ammonites
    frame = 68
    lat, lon = 30.726289652772284, -39.17286299826463
    here = f.whats_here_at(index, frame, lat, lon)
    assert here["taxa"] and all(t["group"] in f.HEADLINE_GROUPS for t in here["taxa"])


def test_every_event_is_complete() -> None:
    events = json.loads(EVENTS_PATH.read_text(encoding="utf-8"))["events"]
    for ev in events:
        assert isinstance(ev["age_ma"], (int, float)) and 0 <= ev["age_ma"] <= 252
        assert 0 < len(ev["label"]) <= 26, ev["label"]
        assert ev["source"].strip(), ev["label"]
