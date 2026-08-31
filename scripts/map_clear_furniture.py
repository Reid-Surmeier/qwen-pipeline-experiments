#!/usr/bin/env python3
"""Erase a map's clock/attribution boxes without a generation pass.

Pass C is the wrong tool for this. On the South America sheet it removed the
country names every single time -- four of four attempts, all scoring ~77% on
the type gate -- so it is systematic, not bad luck. On Asia the content filter
blocked all six attempts, so the pass cannot run there at all.

A furniture box is a closed black rectangular frame, which is a shape a script
can find exactly. Coastlines and borders never form one: their bounding-box
perimeter is mostly empty, a frame's is nearly solid.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage


def frame_boxes(arr: np.ndarray, min_side: int = 20, min_width: int = 44,
                max_frac: float = 0.42, perimeter_fill: float = 0.55,
                min_aspect: float = 1.4) -> list[tuple[int, int, int, int]]:
    """Bounding boxes of closed rectangular frames.

    Loosening the perimeter test to catch small UTC boxes made letters qualify:
    a capital O or D is also a closed loop with a full perimeter. Furniture is
    additionally *wide* -- a readout box is at least 60 px across and wider than
    it is tall -- and no glyph on these maps is.
    """
    ink = arr.max(axis=2) < 110
    labels, _ = ndimage.label(ink, structure=np.ones((3, 3)))
    h, w = ink.shape
    found = []
    for index, (sl_y, sl_x) in enumerate(ndimage.find_objects(labels), start=1):
        bh, bw = sl_y.stop - sl_y.start, sl_x.stop - sl_x.start
        if bh < min_side or bw < min_width or bw < bh * min_aspect:
            continue
        if bh > h * max_frac or bw > w * max_frac:
            continue                                  # too big to be furniture
        comp = labels[sl_y, sl_x] == index
        edge = np.concatenate([comp[0, :], comp[-1, :], comp[:, 0], comp[:, -1]])
        if edge.mean() < perimeter_fill:              # a coastline, not a frame
            continue
        # A readout box is a frame around one flat colour plus digits. A country
        # that happens to be boxy is not: its interior carries other borders and
        # coastline, so it is never this uniform.
        inner = arr[sl_y.start + 3:sl_y.stop - 3, sl_x.start + 3:sl_x.stop - 3]
        if inner.size == 0:
            continue
        flat = inner.reshape(-1, 3)
        dominant = max(np.unique(flat // 24, axis=0, return_counts=True)[1]) / len(flat)
        # A readout's interior is part flat fill and part digits, so its
        # uniformity sits in a band. Below it is map detail; at the top end is a
        # solid block of one country, which must not be erased.
        if 0.30 <= dominant <= 0.86:
            found.append((sl_x.start, sl_y.start, sl_x.stop, sl_y.stop))
    return found


def filled_rectangles(arr: np.ndarray, min_w: int = 40, max_w: int = 300,
                      min_h: int = 16, max_h: int = 70,
                      fill_ratio: float = 0.88) -> list[tuple[int, int, int, int]]:
    """Solid rectangles of one flat colour -- a clock readout's own fill.

    Matching the readout's colour alone is unsafe: its mint (115,253,202) is
    within a hair of the palette's #75FFC8, so a colour filter would erase mint
    countries. Shape separates them. A readout fills its bounding box almost
    completely because it IS a rectangle; no country does, however small.
    """
    ink = arr.max(axis=2) < 110
    q = arr // 20
    keyed = q[:, :, 0] * 4096 + q[:, :, 1] * 64 + q[:, :, 2]
    found = []
    for value in np.unique(keyed[~ink]):
        comp, n = ndimage.label((keyed == value) & ~ink)
        if not n:
            continue
        for index, (sl_y, sl_x) in enumerate(ndimage.find_objects(comp), start=1):
            bh, bw = sl_y.stop - sl_y.start, sl_x.stop - sl_x.start
            if not (min_w <= bw <= max_w and min_h <= bh <= max_h):
                continue
            if bw < bh * 1.4:
                continue
            # The digits printed on the readout are ink, which punches holes in
            # its fill; count them as part of the box or no readout ever passes.
            solid = (comp[sl_y, sl_x] == index) | ink[sl_y, sl_x]
            if float(solid.mean()) >= fill_ratio:
                found.append((sl_x.start, sl_y.start, sl_x.stop, sl_y.stop))
    return found


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--pad", type=int, default=3)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    img = Image.open(args.image).convert("RGB")
    arr = np.asarray(img).astype(int)
    h, w, _ = arr.shape
    boxes = frame_boxes(arr) + filled_rectangles(arr)
    for x0, y0, x1, y1 in boxes:
        if args.dry_run:
            continue
        gy0, gy1 = max(0, y0 - args.pad), min(h, y1 + args.pad)
        gx0, gx1 = max(0, x0 - args.pad), min(w, x1 + args.pad)
        # Paint the box out in whatever surrounds it, not in white. A readout
        # sitting over Brazil left a white hole in Brazil when filled blind.
        ry0, ry1 = max(0, gy0 - 6), min(h, gy1 + 6)
        rx0, rx1 = max(0, gx0 - 6), min(w, gx1 + 6)
        ring = np.concatenate([
            arr[ry0:gy0, rx0:rx1].reshape(-1, 3), arr[gy1:ry1, rx0:rx1].reshape(-1, 3),
            arr[ry0:ry1, rx0:gx0].reshape(-1, 3), arr[ry0:ry1, gx1:rx1].reshape(-1, 3)])
        if len(ring):
            colours, counts = np.unique(ring, axis=0, return_counts=True)
            arr[gy0:gy1, gx0:gx1] = colours[counts.argmax()]
        else:
            arr[gy0:gy1, gx0:gx1] = (255, 255, 255)
    if not args.dry_run:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(arr.astype("uint8")).save(args.out)
    print(f"{args.image.parts[-3] if len(args.image.parts) > 2 else args.image.name:14s} "
          f"{len(boxes)} frame(s): {[(x1-x0, y1-y0) for x0, y0, x1, y1 in boxes][:6]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
