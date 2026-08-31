#!/usr/bin/env python3
"""Outline every flat fill in a recoloured map, in black, 1 px.

The Asia and Middle East sheets draw their country borders in white, so the
recolour leaves them with no dark outlines at all and neighbouring fills read as
one country.

An earlier attempt copied borders from the pass-A output by finding colour
boundaries there. That was wrong: pass A still carries the source's dithering,
anti-aliased type and stray speckle, and every one of those is a colour
boundary, so it stamped black noise across the whole sheet.

The recoloured image is the better reference for its own borders. Its fills are
already flat, so a boundary between two of them is exactly a border and nothing
else -- no texture to mistake for one.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage


def outline(image: Image.Image, quant: int = 26, min_region: int = 40,
            text_clearance: int = 2) -> Image.Image:
    arr = np.asarray(image.convert("RGB")).astype(int)
    h, w, _ = arr.shape
    ink = arr.max(axis=2) < 120

    q = arr // quant
    keyed = q[:, :, 0] * 4096 + q[:, :, 1] * 64 + q[:, :, 2]

    # Speckle is its own tiny region and would be outlined like a country, so
    # only regions with real area are allowed to own a border.
    labels, count = ndimage.label(keyed[None] * 0 + 1)  # placeholder
    big = np.zeros((h, w), bool)
    for value in np.unique(keyed[~ink]):
        comp, n = ndimage.label((keyed == value) & ~ink)
        if not n:
            continue
        sizes = ndimage.sum(np.ones_like(comp), comp, range(1, n + 1))
        keep = {i + 1 for i, s in enumerate(sizes) if s >= min_region}
        if keep:
            big |= np.isin(comp, list(keep))

    edge = np.zeros((h, w), bool)
    edge[:, :-1] |= (keyed[:, :-1] != keyed[:, 1:]) & big[:, :-1] & big[:, 1:]
    edge[:-1, :] |= (keyed[:-1, :] != keyed[1:, :]) & big[:-1, :] & big[1:, :]

    # These sheets separate countries with a WHITE line, so two fills are rarely
    # adjacent and a plain boundary test finds almost nothing. The separator
    # itself is the border: a pale pixel with two or more different fills close
    # by sits between countries, while one on the coast has only one fill near
    # it and stays ocean.
    pale = (arr.min(axis=2) > 170) & ~ink
    if pale.any():
        reach = 3
        near_counts = np.zeros((h, w), np.int16)
        seen_first = np.full((h, w), -1, np.int64)
        for value in np.unique(keyed[big]):
            present = ndimage.binary_dilation((keyed == value) & big, iterations=reach)
            near_counts += present.astype(np.int16)
            seen_first = np.where((seen_first < 0) & present, value, seen_first)
        edge |= pale & (near_counts >= 2)

    edge &= ~ndimage.binary_dilation(ink, iterations=text_clearance)

    out = arr.copy()
    out[edge] = (0, 0, 0)
    return Image.fromarray(out.astype("uint8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--min-region", type=int, default=40)
    args = ap.parse_args()
    img = Image.open(args.image)
    before = float((np.asarray(img.convert("RGB")).max(axis=2) < 110).mean())
    res = outline(img, min_region=args.min_region)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    res.save(args.out)
    after = float((np.asarray(res).max(axis=2) < 110).mean())
    print(f"{args.out.stem:14s} ink {100*before:5.2f}% -> {100*after:5.2f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
