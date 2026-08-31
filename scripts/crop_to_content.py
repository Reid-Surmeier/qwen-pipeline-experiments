#!/usr/bin/env python3
"""Crop a sheet to the ground it actually shows.

Warping a whole sheet into its geographic window assumes the land fills the
image. It does not: these sheets carry wide white margins and, on the US and
Middle East sheets, framed inset panels. Warped whole, a sheet's margin lands on
its neighbour's territory and nothing lines up.

The map body is the largest connected run of map content. Insets are separate
blocks, so the biggest component is the mainland panel.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage


def content_box(path: Path, pad: int = 2) -> tuple[int, int, int, int]:
    a = np.asarray(Image.open(path).convert("RGB")).astype(int)
    body = ((a.max(2) - a.min(2)) > 45) | (a.max(2) < 100)
    # close small gaps so a coastline and its labels read as one region
    solid = ndimage.binary_closing(body, np.ones((9, 9)))
    labels, n = ndimage.label(solid)
    if not n:
        return (0, 0, a.shape[1], a.shape[0])
    sizes = ndimage.sum(np.ones_like(labels), labels, range(1, n + 1))
    biggest = int(np.argmax(sizes)) + 1
    ys, xs = np.where(labels == biggest)
    h, w = body.shape
    return (max(0, xs.min() - pad), max(0, ys.min() - pad),
            min(w, xs.max() + 1 + pad), min(h, ys.max() + 1 + pad))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-dir", required=True, type=Path)
    ap.add_argument("--out-dir", required=True, type=Path)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    boxes = {}
    for p in sorted(args.in_dir.glob("*.png")):
        box = content_box(p)
        im = Image.open(p).convert("RGB").crop(box)
        im.save(args.out_dir / p.name)
        boxes[p.stem] = {"box": [int(v) for v in box], "size": [im.width, im.height]}
        print(f"  {p.stem:15s} {Image.open(p).size} -> {im.size}")
    (args.out_dir / "crops.json").write_text(json.dumps(boxes, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
