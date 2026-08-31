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
# Landmasses the recolour drew loose on the map that a restored panel now
# carries properly, as a fraction of the map area. Left in place they appear
# twice: the US sheet showed Alaska both in its panel and adrift beside it.
# region of the map area (x0, y0, x1, y1 as fractions) to blank
SUPERSEDED = {"usa": [("alaska", 0.03, 0.0, 0.215, 0.25)]}

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
               (153, 255, 204), (255, 204, 204), (255, 255, 102), (255, 240, 0)]


def flood_region(arr: np.ndarray, seed: tuple[int, int]) -> np.ndarray:
    """The contiguous non-background blob containing `seed`."""
    body = (arr.max(axis=2) - arr.min(axis=2) > 40) | (arr.max(axis=2) < 110)
    labels, _ = ndimage.label(body, structure=np.ones((3, 3)))
    target = labels[seed[1], seed[0]]
    return labels == target if target else np.zeros(body.shape, bool)


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

    # The recolour fills more of the frame than the source did, so a panel
    # pasted at the source's scaled position lands on the map -- Alaska's box
    # covered Washington. Give the panels their own column beside the map
    # instead: covering a state to save the frame size is the wrong trade.
    prepared = [(name, clear_clock_boxes(src.crop((x0, y0, x1, y1))),
                 max(1, round((x1 - x0) * sx)), max(1, round((y1 - y0) * sy)))
                for name, x0, y0, x1, y1 in panels]
    gap = max(6, round(img.height * 0.012))
    col_w = max(pw for _, _, pw, _ in prepared)
    stack_h = sum(ph for *_, ph in prepared) + gap * (len(prepared) + 1)

    canvas = Image.new("RGB",
                       (img.width + col_w + gap * 2, max(img.height, stack_h)),
                       (255, 255, 255))
    canvas.paste(img, (col_w + gap * 2, 0))
    img = canvas

    for _name, fx0, fy0, fx1, fy1 in SUPERSEDED.get(args.region, []):
        mx0 = col_w + gap * 2
        mw, mh = img.width - mx0, img.height
        arr = np.asarray(img.convert("RGB")).astype(int)
        arr[int(mh * fy0):int(mh * fy1),
            mx0 + int(mw * fx0):mx0 + int(mw * fx1)] = (255, 255, 255)
        img = Image.fromarray(arr.astype("uint8"))

    pasted = []
    cursor = gap
    for name, crop, pw, ph in prepared:
        img.paste(crop.resize((pw, ph), Image.LANCZOS), (gap, cursor))
        pasted.append({"panel": name, "at": [gap, cursor], "size": [pw, ph]})
        cursor += ph + gap

    args.out.parent.mkdir(parents=True, exist_ok=True)
    img.save(args.out)
    args.out.with_suffix(".insets.json").write_text(json.dumps(pasted, indent=2) + "\n")
    print(f"{args.region}: pasted {', '.join(p['panel'] for p in pasted)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
