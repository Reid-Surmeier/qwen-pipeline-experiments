#!/usr/bin/env python3
"""Paste a source map's inset panels back onto a recoloured map.

The US sheet carries Alaska, Guam, American Samoa and Hawaii in framed panels
down its left margin. The recolour pass kept Alaska's landmass but dropped its
frame and lost the other three panels outright, which silently removes two
states and two territories from the map.

They are copied from the source rather than regenerated: the panels are exact
rectangles at known coordinates, so there is nothing for a model to add and a
great deal for it to get wrong.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

# panel rectangles in source pixels, read off the grey frame lines
PANELS = {
    "usa": [
        ("alaska", 3, 26, 549, 333),
        ("guam", 2, 730, 373, 915),
        ("american-samoa", 2, 920, 373, 1105),
        ("hawaii", 2, 1110, 373, 1295),
    ],
}


# The pastel fills the publisher uses behind a clock readout or a DST badge.
# Land is more saturated -- Alaska (28,234,165), Guam (53,184,250), Hawaii
# (248,87,87) -- so matching the pastel exactly never touches a landmass.
CLOCK_FILLS = [(255, 153, 153), (255, 255, 0), (102, 255, 204), (102, 204, 255),
               (153, 255, 204), (255, 204, 204)]


def clear_clock_boxes(panel: Image.Image, pad: int = 5) -> Image.Image:
    """White out the clock readouts inside a pasted panel.

    A panel copied from the source brings its clock furniture with it, which is
    the very thing this whole procedure removes. The readouts sit in black-framed
    rectangles over a pastel fill, so each fill's bounding box, grown to swallow
    the frame and the DST tab above it, is painted out.
    """
    arr = np.asarray(panel.convert("RGB")).astype(int)
    h, w, _ = arr.shape
    hit = np.zeros((h, w), bool)
    for rgb in CLOCK_FILLS:
        hit |= np.abs(arr - np.array(rgb)).sum(axis=2) < 40
    if not hit.any():
        return panel
    labels, count = ndimage.label(ndimage.binary_dilation(hit, iterations=3))
    for sl_y, sl_x in ndimage.find_objects(labels):
        y0, y1 = max(0, sl_y.start - pad), min(h, sl_y.stop + pad)
        x0, x1 = max(0, sl_x.start - pad), min(w, sl_x.stop + pad)
        if (y1 - y0) * (x1 - x0) < 12:
            continue
        arr[y0:y1, x0:x1] = (255, 255, 255)
    return Image.fromarray(arr.astype("uint8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", required=True)
    ap.add_argument("--source", required=True, type=Path)
    ap.add_argument("--image", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    panels = PANELS.get(args.region, [])
    src = Image.open(args.source).convert("RGB")
    img = Image.open(args.image).convert("RGB")
    if not panels:
        # most sheets have no insets; pass the image through so the caller can
        # treat this as one uniform step rather than a special case
        args.out.parent.mkdir(parents=True, exist_ok=True)
        img.save(args.out)
        print(f"{args.region}: no inset panels")
        return 0
    sx, sy = img.width / src.width, img.height / src.height

    pasted = []
    for name, x0, y0, x1, y1 in panels:
        crop = clear_clock_boxes(src.crop((x0, y0, x1, y1)))
        target = (max(1, round((x1 - x0) * sx)), max(1, round((y1 - y0) * sy)))
        img.paste(crop.resize(target, Image.LANCZOS), (round(x0 * sx), round(y0 * sy)))
        pasted.append({"panel": name, "at": [round(x0 * sx), round(y0 * sy)],
                       "size": list(target)})

    args.out.parent.mkdir(parents=True, exist_ok=True)
    img.save(args.out)
    args.out.with_suffix(".insets.json").write_text(json.dumps(pasted, indent=2) + "\n")
    print(f"{args.region}: pasted {', '.join(p['panel'] for p in pasted)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
