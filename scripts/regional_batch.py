#!/usr/bin/env python3
"""Run the two-pass regional recolour: strip the clock furniture, then recolour.

One prompt carrying both instructions loses one of them (measured on the world
map), so each pass is single-purpose and chains onto the previous output.
"""
from __future__ import annotations

import argparse
import math
import json
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image

BENCH = Path("scripts/bench_image_model.py")
ROOT = Path("benchmarks/regional")


def size_for(path: Path, target_pixels: float = 2.45e6) -> str:
    """A size string matching the source's aspect ratio as closely as possible.

    meta/muse-image keeps the ratio it is given and picks its own pixels, but
    only `size` carries the ratio -- `aspect_ratio` collapses to three buckets.

    Insisting on the source's exact reduced ratio is a trap: 1993x1528 reduces
    to 1993:1528, whose smallest 32-aligned multiple is 63776x48896. Search the
    32-px grid for the closest ratio near the target area instead.
    """
    w, h = Image.open(path).size
    ratio = w / h
    best = None
    for ch in range(32, 4097, 32):
        cw = max(32, round(ch * ratio / 32) * 32)
        err = abs((cw / ch) - ratio) / ratio + abs(cw * ch - target_pixels) / target_pixels * 0.25
        if best is None or err < best[0]:
            best = (err, cw, ch)
    return f"{best[1]}x{best[2]}"


def run(model: str, prompt: Path, reference: Path, out: Path, size: str,
        attempts: int = 3) -> bool:
    """Submit one pass, retrying a moderation filter.

    Meta's filter on this content is not deterministic: the identical prompt
    passed on the Africa map and was filtered on Australia in 6 s. A filtered
    request is rejected before generation and is not billed, so retrying is
    free; a real failure is not worth repeating, so only the filter is retried.
    """
    cmd = [sys.executable, str(BENCH), "--timeout", "600", "--model", model,
           "--label", out.name, "--prompt-file", str(prompt),
           "--reference", str(reference), "--size", size, "--out", str(out)]
    for attempt in range(1, attempts + 1):
        if subprocess.run(cmd).returncode == 0:
            return True
        record = out / "run.json"
        body = ""
        if record.exists():
            body = json.loads(record.read_text()).get("failure", {}).get("body", "") or ""
        if "content management policy" not in body:
            return False
        print(f"   moderation filter on {out.name}, attempt {attempt}/{attempts}")
        time.sleep(4)
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("regions", nargs="+")
    ap.add_argument("--model", default="meta/muse-image")
    ap.add_argument("--pass", dest="which", choices=["A", "B", "both"], default="both")
    args = ap.parse_args()

    for region in args.regions:
        src = ROOT / "reference" / f"{region}.png"
        if not src.exists():
            print(f"!! no reference for {region}")
            continue
        size = size_for(src)
        print(f"\n=== {region}  source {Image.open(src).size}  requesting {size}")
        a_out = ROOT / "runs" / region / "A-stripped"
        b_out = ROOT / "runs" / region / "B-recoloured"
        if args.which in {"A", "both"}:
            if not run(args.model, ROOT / "prompts" / "passA-strip-times.txt", src, a_out, size):
                print(f"!! {region} pass A failed")
                continue
        if args.which in {"B", "both"}:
            base = a_out / "image-01.png"
            if not base.exists():
                print(f"!! {region} has no pass A output")
                continue
            run(args.model, ROOT / "prompts" / "passB-per-country.txt", base, b_out, size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
