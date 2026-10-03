"""Pebble Time 2 (Emery) build verification tests.

Verifies:
1. execution/build_pebble_header.py emits valid C headers and source.
2. pebble build compiles watchface.pbw for emery without errors.
3. Loaded app binary footprint is strictly below PebbleProcessInfo uint16 load_size limit (65535 bytes).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WATCHFACE_DIR = ROOT / "watchface"
PBW_PATH = WATCHFACE_DIR / "build" / "watchface.pbw"
APP_BIN_PATH = WATCHFACE_DIR / "build" / "emery" / "pebble-app.bin"


def test_pebble_header_generator() -> None:
    res = subprocess.run(
        [sys.executable, str(ROOT / "execution" / "build_pebble_header.py")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, f"build_pebble_header failed: {res.stderr}"
    assert (WATCHFACE_DIR / "src" / "c" / "pangaea_data.h").exists()
    assert (WATCHFACE_DIR / "src" / "c" / "pangaea_data.c").exists()


def test_pebble_build_emery() -> None:
    res = subprocess.run(
        ["pebble", "build"],
        cwd=WATCHFACE_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, f"pebble build failed: {res.stderr}\n{res.stdout}"
    assert PBW_PATH.exists(), "watchface.pbw bundle was not created"
    assert APP_BIN_PATH.exists(), "pebble-app.bin was not created"

    # Strict load size limit for Pebble OS: 65,535 bytes (uint16_t load_size)
    bin_size = APP_BIN_PATH.stat().st_size
    assert bin_size <= 65535, f"Loaded binary size {bin_size} exceeds 65535 bytes!"
