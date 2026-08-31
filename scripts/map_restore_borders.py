#!/usr/bin/env python3
"""Give every country a black outline, taken from the map's own geometry.

Two defects this fixes:

* **Missing borders.** The recolour passes thin or drop linework; the Asia sheet
  lost two thirds of its ink in pass A alone.
* **Bled fills.** Where a border disappears the two fills merge and Mongolia's
  colour runs into China.

Borders are copied, not redrawn -- another generation pass would invent them.
They are read as *colour boundaries* rather than as black ink, because the Asia
and Middle East sheets draw their country borders in white, so an ink filter
finds nothing there.

The reference is the pass-A output, not the raw source: A has the same geography
but has already lost the clock boxes, whose rectangular edges would otherwise be
stamped back on as spurious lines.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage


def colour_boundaries(geometry: Image.Image, target: np.ndarray,
                      size: tuple[int, int], quant: int = 28,
                      text_clearance: int = 3) -> np.ndarray:
    """Where one flat fill meets another, or meets the background.

    Every glyph is also a colour boundary, so type has to be masked out or the
    restored line traces around each letter and shreds it. Type is excluded from
    *both* maps: the recolour pass shifts letters by a pixel or two, so masking
    only the reference leaves a halo beside the target's own text.
    """
    a = np.asarray(geometry.convert("RGB").resize(size, Image.NEAREST)).astype(int)
    q = a // quant
    keyed = q[:, :, 0] * 4096 + q[:, :, 1] * 64 + q[:, :, 2]
    edge = np.zeros(keyed.shape, bool)
    edge[:, :-1] |= keyed[:, :-1] != keyed[:, 1:]
    edge[:-1, :] |= keyed[:-1, :] != keyed[1:, :]
    text = (a.max(axis=2) < 140) | (target.max(axis=2) < 140)
    return edge & ~ndimage.binary_dilation(text, iterations=text_clearance)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--geometry", required=True, type=Path,
                    help="map to read borders from, normally the pass-A output")
    ap.add_argument("--image", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--width", type=int, default=1)
    ap.add_argument("--text-clearance", type=int, default=3)
    args = ap.parse_args()

    img = Image.open(args.image).convert("RGB")
    arr = np.asarray(img).astype(int)
    net = colour_boundaries(Image.open(args.geometry), arr, img.size,
                            text_clearance=args.text_clearance)
    if args.width > 1:
        net = ndimage.binary_dilation(net, iterations=args.width - 1)
    before = float((arr.max(2) < 100).mean())
    arr[net] = (0, 0, 0)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr.astype("uint8")).save(args.out)
    print(f"{args.out.parts[-3] if len(args.out.parts)>2 else args.out.name:15s} "
          f"ink {100*before:5.2f}% -> {100*float((arr.max(2)<100).mean()):5.2f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
