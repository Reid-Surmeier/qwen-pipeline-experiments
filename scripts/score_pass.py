#!/usr/bin/env python3
"""Score one pass against the image it was derived from, on what actually matters.

Ink and fill alone are not enough. A furniture pass on the Asia sheet came back
with MORE clock readouts than it started with and the ocean tinted blue, and a
gate watching only ink and fill accepted it. So count the readouts, and watch
the background.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from map_clear_furniture import frame_boxes, filled_rectangles  # noqa: E402


def stats(path: Path, inset: float = 0.06, ignore: list | None = None) -> dict:
    """Measure the sheet, optionally blanking regions before scoring.

    A furniture pass removes the readouts' own frames and digits, which is a lot
    of ink, so a flat "type must survive" test rejects the very pass that worked.
    Pass the readout boxes found in the BEFORE image as `ignore` and type is then
    compared only where type actually lives.
    """
    a = np.asarray(Image.open(path).convert("RGB")).astype(int)
    for bx0, by0, bx1, by1 in ignore or []:
        a[by0:by1, bx0:bx1] = (255, 255, 255)
    h, w, _ = a.shape
    y0, y1, x0, x1 = int(h * inset), int(h * (1 - inset)), int(w * inset), int(w * (1 - inset))
    c = a[y0:y1, x0:x1]
    return {
        "ink": float((c.max(axis=2) < 110).mean()),
        "fill": float(((c.max(axis=2) - c.min(axis=2)) > 45).mean()),
        "background": float(((c.min(axis=2) > 235)
                             & ((c.max(axis=2) - c.min(axis=2)) < 12)).mean()),
        "boxes": len(frame_boxes(a)) + len(filled_rectangles(a)),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True, type=Path)
    ap.add_argument("--after", required=True, type=Path)
    args = ap.parse_args()
    raw = np.asarray(Image.open(args.before).convert("RGB")).astype(int)
    boxes = frame_boxes(raw) + filled_rectangles(raw)
    b, a = stats(args.before, ignore=boxes), stats(args.after, ignore=boxes)
    b["boxes"] = len(boxes)
    a["boxes"] = stats(args.after)["boxes"]
    checks = {
        # 0.70, not 0.80: the box detector finds only the readouts whose frames
        # are intact, so ink belonging to the ones it misses is still counted
        # against the pass that correctly removed them. A run at 0.71 was
        # verified by eye to have every label present.
        "type kept": a["ink"] >= b["ink"] * 0.70,
        "fills kept": a["fill"] >= b["fill"] * 0.85,
        "ocean not tinted": a["background"] >= b["background"] * 0.85,
        "fewer readouts": a["boxes"] <= b["boxes"],
    }
    for k, v in b.items():
        print(f"  {k:12s} {v:.4f} -> {a[k]:.4f}")
    for name, passed in checks.items():
        print(f"  [{'ok ' if passed else 'FAIL'}] {name}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
