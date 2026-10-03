#!/usr/bin/env python3
"""Render high-resolution watchface screenshots using headless Chrome."""

from __future__ import annotations

import base64
import html
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

import urllib.parse

ROOT = Path(__file__).resolve().parent.parent
CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
OUT_DIR = ROOT / "store"

SHOTS = [
    {
        "id": "emery_triassic",
        "t": "00:00:00",
        "lat": 30.03,
        "lon": -95.53,
        "place": "Spring, TX",
        "title": "00:00 — 252.0 Ma (Triassic Dawn)",
        "desc": "Supercontinent Pangaea intact. Amber Day Arc ribbon, initial ground formation.",
    },
    {
        "id": "emery_jurassic",
        "t": "06:35:00",
        "lat": 51.51,
        "lon": -0.13,
        "place": "London, UK",
        "title": "06:35 — 201.3 Ma (Triassic-Jurassic Rift)",
        "desc": "Atlantic rifting begins. Transition to Cyan Day Arc ribbon.",
    },
    {
        "id": "emery_cretaceous",
        "t": "17:00:00",
        "lat": 30.03,
        "lon": -95.53,
        "place": "Spring, TX",
        "title": "17:00 — 93.0 Ma (Mid Cretaceous Tracks)",
        "desc": "Glen Rose dinosaur tracks near ancient Texas coast. Mint Day Arc ribbon.",
    },
    {
        "id": "emery_impact",
        "t": "23:59:02",
        "lat": 30.03,
        "lon": -95.53,
        "place": "Spring, TX",
        "title": "23:59:02 — 66.0 Ma (Asteroid Impact)",
        "desc": "Chicxulub extinction event ticker. Red extinction boundary tick.",
    },
    {
        "id": "emery_present",
        "t": "23:59:59",
        "lat": 30.03,
        "lon": -95.53,
        "place": "Spring, TX",
        "title": "23:59:59 — Today (Present Earth)",
        "desc": "Landing exactly at present-day geography and coordinates.",
    },
]


def main() -> None:
    if not CHROME.exists():
        print("Chrome not found!", file=sys.stderr)
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Start ephemeral web server
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(1.0)

    try:
        for shot in SHOTS:
            out_path = OUT_DIR / f"{shot['id']}.png"
            if out_path.exists() and out_path.stat().st_size > 0:
                print(f"Skipping already rendered {shot['id']}")
                continue
            if shot['lat'] == 30.03 and shot['lon'] == -95.53:
                url = f"http://127.0.0.1:{port}/?t={shot['t']}"
            else:
                place_enc = urllib.parse.quote(shot['place'])
                url = f"http://127.0.0.1:{port}/?t={shot['t']}&lat={shot['lat']}&lon={shot['lon']}&place={place_enc}"
            print(f"Rendering {shot['title']}...")
            res = subprocess.run(
                [
                    str(CHROME),
                    "--headless=new",
                    "--disable-gpu",
                    "--virtual-time-budget=30000",
                    "--dump-dom",
                    url,
                ],
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            dom = res.stdout
            m = re.search(r'data-png="([^"]*)"', dom)
            if not m:
                print(f"  Warning: no data-png found for {shot['id']}")
                continue

            data_url = html.unescape(m.group(1))
            prefix = "data:image/png;base64,"
            if data_url.startswith(prefix):
                raw = base64.b64decode(data_url[len(prefix):])
                out_path = OUT_DIR / f"{shot['id']}.png"
                out_path.write_bytes(raw)
                print(f"  Saved {out_path.name} ({len(raw):,} bytes)")
            else:
                print(f"  Invalid data url for {shot['id']}")

    finally:
        proc.terminate()

    print("\nAll renders complete!")


if __name__ == "__main__":
    main()
