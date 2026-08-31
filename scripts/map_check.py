#!/usr/bin/env python3
"""Check a recoloured map against its source for lost borders and bled fills.

Two defects the eye catches late and a script catches immediately:

* **Missing linework.** The Asia sheet came back with its black borders gone
  entirely, which is invisible in a thumbnail and obvious in a coverage ratio.
* **Bled fills.** A country's colour crossing into its neighbour -- Mongolia
  into China -- happens exactly where a source border pixel has no generated
  linework near it, so source borders are the reference.

The source is scaled to the generated frame; both maps hold the same crop and
aspect, so a plain resize registers them closely enough to compare linework.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage


def linework(rgb: np.ndarray, threshold: int = 100) -> np.ndarray:
    """Near-black across all channels: borders and type, never a saturated fill."""
    return rgb.max(axis=2) < threshold


def check(source: Path, generated: Path, radius: int = 6) -> dict:
    """radius tolerates the pixel or two a recolour shifts a line by; at 3 the
    screen flagged maps that are visually correct."""
    gen = Image.open(generated).convert("RGB")
    src = Image.open(source).convert("RGB").resize(gen.size, Image.LANCZOS)
    g = np.asarray(gen).astype(int)
    s = np.asarray(src).astype(int)

    gl, sl = linework(g), linework(s)
    # a source border pixel is "kept" if any generated linework sits within radius
    near = ndimage.binary_dilation(gl, np.ones((radius * 2 + 1, radius * 2 + 1)))
    retained = float((sl & near).sum() / max(sl.sum(), 1))

    fills = (g.max(2) - g.min(2)) > 55
    regions, count = ndimage.label(fills & ~gl)

    return {
        "generated": str(generated),
        "size": f"{gen.width}x{gen.height}",
        "source_linework_pct": round(100 * sl.mean(), 2),
        "generated_linework_pct": round(100 * gl.mean(), 2),
        "border_retention_pct": round(100 * retained, 1),
        "fill_regions": int(count),
        "verdict": (
            "NO LINEWORK" if gl.mean() < sl.mean() * 0.35 else
            "BORDERS LOST" if retained < 0.70 else
            "ok"
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pairs", nargs="+", help="source.png=generated.png")
    ap.add_argument("--json", type=Path)
    ap.add_argument("--radius", type=int, default=6)
    args = ap.parse_args()
    rows = []
    for pair in args.pairs:
        src, gen = pair.split("=")
        row = check(Path(src), Path(gen), radius=args.radius)
        rows.append(row)
        print(f"{Path(gen).stem:15s} src_ink {row['source_linework_pct']:5.2f}%  "
              f"gen_ink {row['generated_linework_pct']:5.2f}%  "
              f"retained {row['border_retention_pct']:5.1f}%  "
              f"regions {row['fill_regions']:5d}   {row['verdict']}")
    if args.json:
        args.json.write_text(json.dumps(rows, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
