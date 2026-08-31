#!/usr/bin/env python3
"""Deterministic Assembly for the world map: graticule + capital labels.

Generation supplies the pixels (country fills); this supplies the placement.
The model's own attempt at capitals put Washington DC in Kansas and London in
the North Atlantic, so nothing positional is left to it.

The source map is Miller cylindrical. Calibration was recovered from the
source image's own graticule (15 deg of longitude every 180.3 px, 10 deg of
latitude on Miller spacing) and verified against Tokyo and Cape Town.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"

# --- style measured from the publisher's own native GIF ---------------------
# worldtimezone.com serves its map at 1001x485 with a 256-colour palette; every
# reference we were handed is an upscale of that. Read off the native file:
#
#   * the graticule is 1 px of #CCCEFC, drawn ONLY over the white background.
#     Of its 16936 grid pixels, exactly 0 fall on a saturated country fill --
#     the lattice sits behind the land, it does not cross it. Drawing it over
#     everything is what made our version read as an overlay pasted on top.
#   * place names are #040234, a very dark navy, not black.
#   * "Seattle" measures 7 px tall and 33 px wide against a 960 px-wide world,
#     so type is far chunkier relative to the map than ours was.
#
# 15 deg of longitude is 40 px there and 94.9 px here, so this map is 2.373x
# native and native metrics scale by that.
GRID_RGB = (204, 206, 252)
LABEL_RGB = (4, 2, 52)
NATIVE_SCALE = 2.373
NATIVE_TEXT_H = 7.0

# --- source-image geo calibration (Miller cylindrical) ----------------------
SRC_X0 = 2294.25       # pixel x of the Greenwich meridian
SRC_PX_PER_DEG = 12.02 # longitude
SRC_Y_EQUATOR = 1439.0
SRC_PX_PER_RAD = 687.6 # Miller vertical scale

# --- source -> generated-image registration (land-mask fit, IoU 0.76) -------
REG_SX, REG_SY, REG_TX, REG_TY = 1.9000, 1.9150, 45.0, 17.0


def miller(lat_deg: float) -> float:
    """Miller cylindrical northing, in radians of the sphere."""
    return 1.25 * math.log(math.tan(math.radians(45.0 + 0.4 * lat_deg)))


def project(lon: float, lat: float, width: int | None = None) -> tuple[float, float]:
    """Longitude/latitude -> pixel in the generated image.

    The map is cut at the International Date Line rather than centred on it,
    so the far east of the sphere reappears at the left edge. New Zealand at
    175E lands past the right border unless it is wrapped back by 360 deg.
    """
    sx = SRC_X0 + lon * SRC_PX_PER_DEG
    x = (sx - REG_TX) / REG_SX
    if width is not None and x >= width:
        x = (SRC_X0 + (lon - 360.0) * SRC_PX_PER_DEG - REG_TX) / REG_SX
    sy = SRC_Y_EQUATOR - SRC_PX_PER_RAD * miller(lat)
    return x, (sy - REG_TY) / REG_SY


# Alaska is United States territory but the generation pass filled it with
# Canada's colour. Recolour it deterministically from a seed point inside it.
ALASKA_SEED = (64.2, -149.5)
USA_SEED = (39.0, -98.0)


# name, lat, lon, priority (1 = place first / never drop), optional side hint.
# The hint is tried before the default order and exists for the handful of
# tight pairs the original map also had to solve by hand -- Santiago's label
# goes out over the Pacific so Buenos Aires can keep the space to its right.
CAPITALS = [
    ("Washington DC", 38.90, -77.04, 1), ("Ottawa", 45.42, -75.70, 1),
    ("Mexico City", 19.43, -99.13, 1),   ("Havana", 23.11, -82.37, 3),
    ("Guatemala City", 14.63, -90.51, 4),("Panama City", 8.98, -79.52, 4),
    ("Bogota", 4.71, -74.07, 2),         ("Caracas", 10.48, -66.90, 3),
    ("Quito", -0.18, -78.47, 3, "L"),         ("Lima", -12.05, -77.04, 1, "L"),
    ("La Paz", -16.50, -68.15, 3, "L"),       ("Brasilia", -15.79, -47.88, 1),
    ("Asuncion", -25.26, -57.58, 4),     ("Santiago", -33.45, -70.67, 1, "L"),
    ("Buenos Aires", -34.60, -58.38, 1), ("Montevideo", -34.90, -56.16, 4, "D"),
    ("Reykjavik", 64.15, -21.94, 3),     ("Dublin", 53.35, -6.26, 4, "L"),
    ("London", 51.51, -0.13, 1, "L"),         ("Paris", 48.86, 2.35, 1, "D"),
    ("Madrid", 40.42, -3.70, 1),         ("Lisbon", 38.72, -9.14, 3),
    ("Rome", 41.90, 12.50, 1),           ("Berlin", 52.52, 13.40, 1),
    ("Oslo", 59.91, 10.75, 3),           ("Stockholm", 59.33, 18.07, 3, "U"),
    ("Helsinki", 60.17, 24.94, 3),       ("Warsaw", 52.23, 21.01, 2, "R"),
    ("Kyiv", 50.45, 30.52, 2),           ("Moscow", 55.76, 37.62, 1),
    ("Ankara", 39.93, 32.86, 2),         ("Athens", 37.98, 23.73, 4),
    ("Cairo", 30.04, 31.24, 1),          ("Algiers", 36.75, 3.06, 2),
    ("Rabat", 34.02, -6.84, 4, "L"),          ("Tripoli", 32.89, 13.19, 4),
    ("Khartoum", 15.50, 32.56, 3),       ("Addis Ababa", 9.03, 38.74, 2),
    ("Nairobi", -1.29, 36.82, 2),        ("Dar es Salaam", -6.79, 39.21, 4),
    ("Kinshasa", -4.44, 15.27, 3),       ("Luanda", -8.84, 13.23, 4),
    ("Abuja", 9.06, 7.49, 2),            ("Accra", 5.60, -0.19, 4, "D"),
    ("Dakar", 14.72, -17.47, 3),         ("Bamako", 12.64, -8.00, 4, "L"),
    ("Pretoria", -25.75, 28.19, 1),      ("Windhoek", -22.56, 17.08, 4, "L"),
    ("Antananarivo", -18.88, 47.51, 4),  ("Riyadh", 24.71, 46.68, 1),
    ("Baghdad", 33.32, 44.36, 3, "D"),        ("Tehran", 35.69, 51.39, 1),
    ("Kabul", 34.53, 69.17, 3, "U"),          ("Islamabad", 33.68, 73.05, 2),
    ("New Delhi", 28.61, 77.21, 1),      ("Kathmandu", 27.72, 85.32, 4, "U"),
    ("Dhaka", 23.81, 90.41, 4),          ("Astana", 51.17, 71.43, 2),
    ("Tashkent", 41.30, 69.24, 4),       ("Beijing", 39.90, 116.41, 1),
    ("Ulaanbaatar", 47.89, 106.91, 3),   ("Seoul", 37.57, 126.98, 2),
    ("Tokyo", 35.68, 139.77, 1),         ("Hanoi", 21.03, 105.85, 3),
    ("Bangkok", 13.76, 100.50, 1),       ("Kuala Lumpur", 3.14, 101.69, 4),
    ("Jakarta", -6.21, 106.85, 1),       ("Manila", 14.60, 120.98, 2),
    ("Canberra", -35.28, 149.13, 1),     ("Wellington", -41.29, 174.78, 1),
    ("Port Moresby", -9.44, 147.18, 4),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--font-size", type=int, default=0,
                    help="0 derives it from the native map's own type size")
    ap.add_argument("--pad", type=int, default=6, help="label clearance in px")
    ap.add_argument("--max-priority", type=int, default=3)
    ap.add_argument("--max-clutter", type=float, default=0.30)
    ap.add_argument("--fix-alaska", action="store_true")
    ap.add_argument("--thicken", type=int, default=1,
                    help="dilate the black linework by this many px. The "
                         "publisher's coastlines are heavier relative to its "
                         "type than the generated ones are, which is what makes "
                         "our labels read as pasted on rather than drawn in.")
    ap.add_argument("--no-labels", action="store_true")
    ap.add_argument("--no-grid", action="store_true")
    ap.add_argument("--scale", type=int, default=2,
                    help="final NEAREST upscale, matching how the publisher's "
                         "own map is presented above native size")
    args = ap.parse_args()

    base = Image.open(args.base).convert("RGB")
    W, H = base.size

    if args.fix_alaska:
        ax, ay = project(ALASKA_SEED[1], ALASKA_SEED[0], W)
        ux, uy = project(USA_SEED[1], USA_SEED[0], W)
        usa = base.getpixel((int(ux), int(uy)))
        before = base.getpixel((int(ax), int(ay)))
        if before != usa:
            ImageDraw.floodfill(base, (int(ax), int(ay)), usa, thresh=30)
            print(f"  Alaska {before} -> {usa}")

    arr = np.asarray(base).astype(int)
    saturated = (arr.max(2) - arr.min(2)) > 55      # a country fill
    inked = arr.max(2) < 90                          # black linework

    if args.thicken:
        from scipy import ndimage
        grown = ndimage.binary_dilation(inked, iterations=args.thicken)
        arr[grown] = (0, 0, 0)
        inked = grown
        saturated = (arr.max(2) - arr.min(2)) > 55
        base = Image.fromarray(arr.astype("uint8"))
    background = ~(saturated | inked)                # ocean and interior white

    # --- graticule: behind the land, never across it ------------------------
    if not args.no_grid:
        grid = np.zeros((H, W), bool)
        gw = max(1, round(NATIVE_SCALE / 2))         # native is 1 px
        for lon in range(-180, 181, 15):
            x, _ = project(lon, 0.0)
            if 0 <= x < W:
                grid[:, int(x):int(x) + gw] = True
        for lat in range(-50, 81, 10):
            _, y = project(0.0, lat)
            if 0 <= y < H:
                grid[int(y):int(y) + gw, :] = True
        arr[grid & background] = GRID_RGB
        base = Image.fromarray(arr.astype("uint8"))

    placed, skipped_tight = [], []
    if not args.no_labels:
        # Type is rendered at half resolution with smoothing off and then
        # doubled with NEAREST, so every letter is built from square 2x2 blocks
        # on the same grid as the linework instead of floating above it as
        # smooth vector shapes.
        ss = 2
        size = args.font_size or max(6, round(NATIVE_TEXT_H * NATIVE_SCALE / ss / 0.72))
        font = ImageFont.truetype(FONT, size)
        layer = Image.new("RGBA", (W // ss, H // ss), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        ld.fontmode = "1"
        dot = 2

        clutter = inked.astype(np.float32)
        taken: list[tuple[float, float, float, float]] = []

        def free(box):
            x0, y0, x1, y1 = box
            if x0 < 1 or y0 < 1 or x1 > W // ss - 1 or y1 > H // ss - 1:
                return False
            return not any(x0 < b[2] and b[0] < x1 and y0 < b[3] and b[1] < y1 for b in taken)

        def busy(box):
            x0, y0, x1, y1 = (int(v) * ss for v in box)
            patch = clutter[max(y0, 0):max(y1, 1), max(x0, 0):max(x1, 1)]
            return float(patch.mean()) if patch.size else 1.0

        def mark_busy(box):
            x0, y0, x1, y1 = (int(v) * ss for v in box)
            clutter[max(y0, 0):max(y1, 1), max(x0, 0):max(x1, 1)] = 1.0

        for entry in sorted(CAPITALS, key=lambda c: c[3]):
            name, lat, lon, prio = entry[:4]
            hint = entry[4] if len(entry) > 4 else None
            if prio > args.max_priority:
                continue
            fx, fy = project(lon, lat, W)
            if not (0 <= fx < W and 0 <= fy < H):
                continue
            x, y = fx / ss, fy / ss
            tw = ld.textlength(name, font=font)
            th = size
            g = dot + 3
            pad = args.pad
            slots = {"R": (g, -th / 2), "L": (-tw - g, -th / 2),
                     "D": (-tw / 2, g), "U": (-tw / 2, -th - g)}
            order = ["R", "L", "D", "U"]
            if hint:
                order.remove(hint)
                order.insert(0, hint)
            candidates = [slots[k] for k in order] + [
                (g, g), (-tw - g, g), (g, -th - g), (-tw - g, -th - g)]

            def boxfor(dx, dy):
                return (x + dx - pad, y + dy - pad, x + dx + tw + pad, y + dy + th + pad)

            chosen = None
            if hint:                      # a hint is a decision, not a tiebreak
                hb = boxfor(*slots[hint])
                if free(hb) and busy(hb) <= args.max_clutter:
                    chosen = (busy(hb), *slots[hint], hb)
            if chosen is None:
                scored = [(busy(boxfor(dx, dy)) + rank * 0.02, dx, dy, boxfor(dx, dy))
                          for rank, (dx, dy) in enumerate(candidates)
                          if free(boxfor(dx, dy))]
                chosen = min(scored) if scored else None
            if not chosen or chosen[0] > args.max_clutter:
                skipped_tight.append(name)
                continue
            score, dx, dy, box = chosen
            taken.append(box)
            taken.append((x - dot - 1, y - dot - 1, x + dot + 1, y + dot + 1))
            mark_busy(box)
            ld.ellipse([x - dot, y - dot, x + dot, y + dot], fill=(204, 51, 51, 255))
            ld.text((x + dx, y + dy), name, font=font, fill=(*LABEL_RGB, 255))
            placed.append({"name": name, "lat": lat, "lon": lon,
                           "x": round(fx, 1), "y": round(fy, 1),
                           "clutter": round(score, 4)})

        base = Image.alpha_composite(
            base.convert("RGBA"),
            layer.resize((W, H), Image.NEAREST)).convert("RGB")

    if args.scale > 1:
        base = base.resize((W * args.scale, H * args.scale), Image.NEAREST)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    base.save(args.out)
    report = {"output": str(args.out), "size": f"{base.width}x{base.height}",
              "scale": args.scale, "font_size": args.font_size or "derived",
              "placed": len(placed), "skipped_no_room": skipped_tight, "labels": placed}
    args.out.with_suffix(".labels.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"{args.out}  {base.width}x{base.height}  placed {len(placed)}  "
          f"skipped {len(skipped_tight)}: {', '.join(skipped_tight) or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
