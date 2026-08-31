#!/usr/bin/env python3
"""Fit each regional sheet's geographic extent by matching it to the world map.

Zooming into the world map runs out of detail, and opening a regional sheet
drops its surroundings to blank white. Both go away if the sheets are placed at
their true positions on one continuous surface, with the world map underneath
filling everything they do not cover.

That needs to know what ground each sheet covers. The publisher states it in
prose per section, but these sheets came from different pages, so the extent is
fitted instead: warp the sheet into the world map's projection under a candidate
extent and score how well its land agrees with the world map's land.

Both are the publisher's own Miller cylindrical, so the warp is four numbers --
the sheet's west, east, south and north edges.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

# world-map calibration, recovered from the source's own graticule
W_X0, W_PX_DEG, W_Y_EQ, W_PX_RAD = 2294.25, 12.02, 1439.0, 687.6
REG_SX, REG_SY, REG_TX, REG_TY = 1.9000, 1.9150, 45.0, 17.0


def miller(lat):
    return 1.25 * np.log(np.tan(np.radians(45.0 + 0.4 * np.asarray(lat, float))))


def world_xy(lon, lat, width):
    x = ((W_X0 + np.asarray(lon, float) * W_PX_DEG) - REG_TX) / REG_SX
    x = np.where(x >= width, ((W_X0 + (np.asarray(lon, float) - 360) * W_PX_DEG) - REG_TX) / REG_SX, x)
    y = ((W_Y_EQ - W_PX_RAD * miller(lat)) - REG_TY) / REG_SY
    return x, y


def land(img: Image.Image, scale: int = 1) -> np.ndarray:
    if scale != 1:
        img = img.resize((img.width // scale, img.height // scale), Image.LANCZOS)
    a = np.asarray(img.convert("RGB")).astype(int)
    return ((a.max(2) - a.min(2)) > 45) | (a.max(2) < 100)


def score(sheet_mask, world_mask, ext, world_size, step=3):
    """IoU between the sheet warped under `ext` and the world map's land."""
    lon0, lon1, lat0, lat1 = ext
    Wm, Hm = world_size
    Hs, Ws = sheet_mask.shape
    lons = np.linspace(lon0, lon1, max(8, Ws // step))
    lats = np.linspace(lat1, lat0, max(8, Hs // step))
    LO, LA = np.meshgrid(lons, lats)
    sx = ((LO - lon0) / (lon1 - lon0) * (Ws - 1)).astype(int)
    m1, m0 = miller(lat1), miller(lat0)
    sy = ((m1 - miller(LA)) / (m1 - m0) * (Hs - 1)).astype(int)
    s = sheet_mask[np.clip(sy, 0, Hs - 1), np.clip(sx, 0, Ws - 1)]
    wx, wy = world_xy(LO, LA, Wm)
    ok = (wx >= 0) & (wx < Wm) & (wy >= 0) & (wy < Hm)
    w = np.zeros_like(s)
    w[ok] = world_mask[np.clip(wy[ok].astype(int), 0, Hm - 1),
                       np.clip(wx[ok].astype(int), 0, Wm - 1)]
    inter = (s & w).sum()
    union = (s | w).sum()
    return inter / max(union, 1)


SEED = {
    "usa": (-128, -65, 24, 50), "canada": (-142, -52, 41, 75),
    "caribbean": (-95, -58, 5, 28), "south-america": (-82, -34, -56, 13),
    "europe": (-25, 45, 34, 72), "africa": (-20, 52, -36, 38),
    "middle-east": (25, 80, 12, 45), "russia": (25, 190, 40, 78),
    "asia": (60, 150, -12, 55), "australia": (110, 180, -47, -8),
}


def fit(name, sheet_path, world_mask, world_size, max_drift=22):
    """Refine the seed extent, but never far from it.

    Unconstrained, the search wanders: the Middle East sheet drifted to span
    -13 to 93 east because its inset panel and margins are land-coloured and
    score as coastline. The seed is a real reading of what the sheet shows, so
    the fit is only allowed to correct it, not replace it.
    """
    sheet = land(Image.open(sheet_path), scale=2)
    seed = SEED[name]
    best = (score(sheet, world_mask, seed, world_size), seed)
    for span in (16, 8, 4, 2, 1):
        improved = True
        while improved:
            improved = False
            for i in range(4):
                for d in (-span, span):
                    cand = list(best[1]); cand[i] += d
                    if cand[1] - cand[0] < 15 or cand[3] - cand[2] < 10:
                        continue
                    if any(abs(cand[j] - seed[j]) > max_drift for j in range(4)):
                        continue
                    if not (-190 < cand[0] < 190 and -190 < cand[1] < 195):
                        continue
                    if not (-70 < cand[2] < 80 and -60 < cand[3] < 84):
                        continue
                    s = score(sheet, world_mask, tuple(cand), world_size)
                    if s > best[0] + 1e-4:
                        best = (s, tuple(cand)); improved = True
    return best


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--world", required=True, type=Path)
    ap.add_argument("--sheets-dir", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    wimg = Image.open(args.world)
    wmask = land(wimg, scale=2)
    wsize = (wimg.width // 2, wimg.height // 2)

    result = {}
    for name in SEED:
        p = args.sheets_dir / f"{name}.png"
        if not p.exists():
            continue
        s, ext = fit(name, p, wmask, wsize)
        result[name] = {"west": ext[0], "east": ext[1], "south": ext[2], "north": ext[3],
                        "iou": round(float(s), 4)}
        print(f"{name:15s} W{ext[0]:>5} E{ext[1]:>5} S{ext[2]:>4} N{ext[3]:>3}   IoU {s:.3f}")
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
