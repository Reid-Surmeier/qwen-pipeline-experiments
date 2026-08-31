#!/usr/bin/env python3
"""Warp every regional sheet onto one continuous world canvas.

Zooming the world map runs out of pixels, and opening a single sheet leaves
blank white where its neighbours should be. One surface fixes both: the world
map fills everything as a base layer, and each sheet is warped into its own
geographic window on top, at its own much higher resolution.

Sheets are drawn largest-area first so the tighter, more detailed ones land on
top, and each is feathered at its edges so a few degrees of registration error
reads as a soft join rather than a visible rectangle.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

W_X0, W_PX_DEG, W_Y_EQ, W_PX_RAD = 2294.25, 12.02, 1439.0, 687.6
REG_SX, REG_SY, REG_TX, REG_TY = 1.9000, 1.9150, 45.0, 17.0


def miller(lat):
    return 1.25 * np.log(np.tan(np.radians(45.0 + 0.4 * np.asarray(lat, float))))


def inv_miller(m):
    return (np.degrees(np.arctan(np.exp(np.asarray(m, float) / 1.25))) - 45.0) / 0.4


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--world", required=True, type=Path)
    ap.add_argument("--sheets-dir", required=True, type=Path)
    ap.add_argument("--extents", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--scale", type=float, default=2.0,
                    help="canvas size relative to the world map")
    ap.add_argument("--feather", type=int, default=40)
    args = ap.parse_args()

    world = Image.open(args.world).convert("RGB")
    CW, CH = int(world.width * args.scale), int(world.height * args.scale)
    canvas = world.resize((CW, CH), Image.LANCZOS)

    # canvas pixel -> lon/lat. The calibration was recovered in the world map's
    # 2240x1120 working space, but the finished world map is published at 2x
    # that. Missing this factor put every sheet at half its true longitude and
    # piled the whole atlas into the left half of the canvas.
    CAL_W = 2240.0
    px = args.scale * (world.width / CAL_W)          # canvas px per calibration px
    lon = ((np.arange(CW) / px) * REG_SX + REG_TX - W_X0) / W_PX_DEG
    lat = inv_miller((W_Y_EQ - ((np.arange(CH) / px) * REG_SY + REG_TY)) / W_PX_RAD)

    extents = json.loads(args.extents.read_text())
    order = sorted(extents.items(),
                   key=lambda kv: -((kv[1]["east"] - kv[1]["west"])
                                    * (kv[1]["north"] - kv[1]["south"])))
    placed = []
    for name, ext in order:
        path = args.sheets_dir / f"{name}.png"
        if not path.exists():
            continue
        sheet = Image.open(path).convert("RGB")
        S = np.asarray(sheet).astype(np.uint8)
        Hs, Ws, _ = S.shape

        cols = np.where((lon >= ext["west"]) & (lon <= ext["east"]))[0]
        rows = np.where((lat >= ext["south"]) & (lat <= ext["north"]))[0]
        if not len(cols) or not len(rows):
            continue
        LO = lon[cols][None, :]
        LA = lat[rows][:, None]
        sxi = ((LO - ext["west"]) / (ext["east"] - ext["west"]) * (Ws - 1))
        m1, m0 = miller(ext["north"]), miller(ext["south"])
        syi = ((m1 - miller(LA)) / (m1 - m0) * (Hs - 1))
        sxi = np.clip(np.broadcast_to(sxi, (len(rows), len(cols))), 0, Ws - 1).astype(int)
        syi = np.clip(np.broadcast_to(syi, (len(rows), len(cols))), 0, Hs - 1).astype(int)
        patch = S[syi, sxi]

        # feather so registration error reads as a soft join, not a rectangle
        h, w = patch.shape[:2]
        f = max(1, min(args.feather, h // 3, w // 3))
        ramp_x = np.clip(np.minimum(np.arange(w), w - 1 - np.arange(w)) / f, 0, 1)
        ramp_y = np.clip(np.minimum(np.arange(h), h - 1 - np.arange(h)) / f, 0, 1)
        alpha = (ramp_y[:, None] * ramp_x[None, :])[..., None]

        region = np.asarray(canvas).astype(float)
        y0, y1, x0, x1 = rows[0], rows[-1] + 1, cols[0], cols[-1] + 1
        region[y0:y1, x0:x1] = region[y0:y1, x0:x1] * (1 - alpha) + patch * alpha
        canvas = Image.fromarray(region.astype("uint8"))
        placed.append({"name": name, "x": int(x0), "y": int(y0),
                       "w": int(x1 - x0), "h": int(y1 - y0), **ext})
        print(f"  placed {name:15s} at {x0},{y0} {x1-x0}x{y1-y0}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(args.out)
    args.out.with_suffix(".layout.json").write_text(json.dumps(
        {"canvas": {"width": CW, "height": CH, "scale": args.scale},
         "sheets": placed}, indent=2) + "\n")
    print(f"{args.out}  {CW}x{CH}  {len(placed)} sheets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
