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
# The publisher's own graticule is #CCCEFC, a pale blue. The owner wants a
# lighter, greyer, more open lattice than that: a neutral grey blended into the
# background rather than painted over it, so it reads as ruling under the map
# instead of a second layer on top.
GRID_RGB = (128, 132, 138)
GRID_OPACITY = 0.28
LABEL_RGB = (4, 2, 52)
DATELINE_RGB = (252, 102, 4)
NATIVE_SCALE = 2.373
NATIVE_TEXT_H = 7.0

# The graticule is every 7.5 deg of longitude (20 px native), not 15. Reading
# only the strongest columns had missed every other line and left the lattice
# half as dense as the publisher's.
GRID_LON_STEP = 15.0
GRID_LAT_STEP = 20

# Graticule and date line are both 1 px in the native file, so they must stay
# the same weight here. Stamping the reprojected date line and dilating it had
# made it 6 px against the grid's 2.
LINE_W = max(1, round(NATIVE_SCALE))

# native-file calibration, for reprojecting artwork out of it
NAT_X0, NAT_PX_PER_DEG = 500.0, 40.0 / 15.0
NAT_Y_EQUATOR, NAT_PX_PER_RAD = 313.0, 152.8


def miller_inverse(y_m: float) -> float:
    """Miller northing in sphere-radians -> latitude in degrees."""
    return (math.degrees(math.atan(math.exp(y_m / 1.25))) - 45.0) / 0.4


def dateline_segments(native: "Image.Image", width: int) -> list[tuple[tuple, tuple]]:
    """The publisher's own date line, as projected segments ready to stroke.

    The line zigzags around the Aleutians, Kiribati and Samoa, and authoring
    those jogs by hand would be guesswork, so its orange pixels are lifted from
    the native GIF and reprojected. Its label letters are separate small blobs,
    so a size filter keeps the line and drops the type.

    Neighbouring native pixels become segments rather than dots: at 2.37x a
    stamped point set is dotted, and dilating it to close the gaps is what made
    the line three times the graticule's weight.
    """
    from scipy import ndimage

    a = np.asarray(native.convert("RGB")).astype(int)
    orange = (a[:, :, 0] > 200) & (a[:, :, 1] > 60) & (a[:, :, 1] < 160) & (a[:, :, 2] < 80)
    labels, count = ndimage.label(orange, structure=np.ones((3, 3)))
    line = np.zeros_like(orange)
    for index in range(1, count + 1):
        ys, xs = np.where(labels == index)
        if (ys.max() - ys.min() + 1) > 40 and len(ys) > 60:
            line[ys, xs] = True                # a line branch, not a letter

    def to_map(px, py):
        lon = (px - NAT_X0) / NAT_PX_PER_DEG
        lat = miller_inverse((NAT_Y_EQUATOR - py) / NAT_PX_PER_RAD)
        return project(lon, lat, width)

    segments = []
    ys, xs = np.where(line)
    points = set(zip(ys.tolist(), xs.tolist()))
    for py, px in points:
        here = to_map(px, py)
        for dy, dx in ((0, 1), (1, 0), (1, 1), (1, -1)):   # each pair once
            if (py + dy, px + dx) in points:
                segments.append((here, to_map(px + dx, py + dy)))
    return segments


# Country names, as the publisher sets them: the same face in capitals, placed
# over the territory. Only large territories -- the publisher's own world map
# names CHINA, INDIA, ALASKA, GREENLAND and KAMCHATKA but never France or Spain,
# because at this scale a small country's name would sit on top of its capital.
# These are placed after the capitals, into whatever ground is left.
COUNTRIES = [
    ("GREENLAND", 72.0, -42.0), ("ALASKA", 64.5, -152.0), ("CANADA", 58.0, -100.0),
    ("MEXICO", 23.5, -102.0), ("BRAZIL", -10.0, -52.0), ("ARGENTINA", -35.0, -65.0),
    ("PERU", -9.0, -74.0),
    ("RUSSIA", 62.0, 95.0), ("CHINA", 33.0, 103.0), ("INDIA", 22.0, 79.0),
    ("KAZAKHSTAN", 48.0, 64.0), ("MONGOLIA", 46.5, 100.0), ("IRAN", 31.0, 56.0),
    ("SAUDI ARABIA", 21.0, 45.0), ("LIBYA", 26.0, 17.0), ("ALGERIA", 27.0, 2.0),
    ("SUDAN", 14.0, 28.0), ("SOUTH AFRICA", -30.5, 23.0),
    ("AUSTRALIA", -24.0, 133.0), ("NEW ZEALAND", -44.0, 171.0),
    ("INDONESIA", -1.5, 114.0),
]

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
    ap.add_argument("--grid-opacity", type=float, default=GRID_OPACITY)
    ap.add_argument("--grid-lon-step", type=float, default=GRID_LON_STEP)
    ap.add_argument("--grid-lat-step", type=int, default=GRID_LAT_STEP)
    ap.add_argument("--dateline", type=Path,
                    default=Path("benchmarks/world-map/reference/"
                                 "worldtimezone-native-1001x485.gif"),
                    help="native GIF to lift the date line out of")
    ap.add_argument("--no-countries", action="store_true")
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
        gw = LINE_W                                   # native is 1 px, as is the date line
        steps = int(round(360 / args.grid_lon_step))
        for i in range(steps + 1):
            lon = -180 + i * args.grid_lon_step
            x, _ = project(lon, 0.0)
            if 0 <= x < W:
                grid[:, int(x):int(x) + gw] = True
        for lat in range(-80, 81, args.grid_lat_step):
            _, y = project(0.0, lat)
            if 0 <= y < H:
                grid[int(y):int(y) + gw, :] = True
        # Blended, not painted: at full strength even a light grey reads as a
        # layer sitting on the map rather than ruling beneath it.
        mask = grid & background
        alpha = max(0.0, min(1.0, args.grid_opacity))
        arr[mask] = np.round(
            arr[mask] * (1.0 - alpha) + np.array(GRID_RGB) * alpha).astype(int)
        base = Image.fromarray(arr.astype("uint8"))

    if args.dateline and args.dateline.exists():
        # Consecutive native pixels land 2.37 apart here, so plotting them as
        # points draws a dotted line. Dilating to close the gaps was the first
        # fix and it made the line 6 px against the graticule's 2. Instead join
        # each native pixel to its neighbours and stroke those segments at the
        # graticule's own width, which is what the native file does.
        dl = ImageDraw.Draw(base)
        for (x0, y0), (x1, y1) in dateline_segments(Image.open(args.dateline), W):
            dl.line([(x0, y0), (x1, y1)], fill=DATELINE_RGB, width=LINE_W)

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

        from scipy import ndimage

        # Split the map into contiguous areas of one fill colour, so a label can
        # be tested against the country it belongs to. Quantising to a coarse
        # palette first keeps a country whole despite stray generated pixels;
        # the black linework separates neighbours.
        quant = np.asarray(base).astype(int) // 24
        keyed = quant[:, :, 0] * 4096 + quant[:, :, 1] * 64 + quant[:, :, 2]
        regions = np.zeros((H, W), np.int32)
        next_id = 1
        for value in np.unique(keyed[~inked]):
            comp, count = ndimage.label((keyed == value) & ~inked)
            comp[comp > 0] += next_id - 1
            regions = np.where(comp > 0, comp, regions)
            next_id += count
        _region_cache: dict[int, np.ndarray] = {}

        def country_region(fx, fy):
            xi, yi = int(round(fx)), int(round(fy))
            if not (0 <= xi < W and 0 <= yi < H):
                return None
            rid = int(regions[yi, xi])
            if rid <= 0:
                return None
            if rid not in _region_cache:
                _region_cache[rid] = regions == rid
            return _region_cache[rid]

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

        def interior_spots(region, need_w, need_h, ss_, limit=14):
            """Places inside the region where the whole word fits, best first.

            Returning only the single deepest point was not enough: Brazil's
            pole of inaccessibility happens to sit against Brasilia's label, so
            the name was dropped even though the Amazon had room a little to the
            west. Candidates are spread out so the caller can fall back.
            """
            dist = ndimage.distance_transform_edt(region)
            ys, xs = np.where(dist >= max(need_h / 2.0, 3.0))
            if not len(ys):
                return []
            order = np.argsort(-dist[ys, xs])
            out, chosen = [], []
            for i in order[:6000]:
                cy, cx = float(ys[i]), float(xs[i])
                if any(abs(cx - px) < need_w * 0.6 and abs(cy - py) < need_h * 1.5
                       for px, py in chosen):
                    continue
                x0, x1 = int(cx - need_w / 2), int(cx + need_w / 2)
                y0, y1 = int(cy - need_h / 2), int(cy + need_h / 2)
                if x0 < 0 or y0 < 0 or x1 >= W or y1 >= H:
                    continue
                patch = region[y0:y1, x0:x1]
                if patch.size and patch.mean() >= 0.85:
                    chosen.append((cx, cy))
                    out.append((cx / ss_, cy / ss_))
                    if len(out) >= limit:
                        break
            return out

        countries = ([] if args.no_countries
                     else [(n.upper(), la, lo, 0, None) for n, la, lo in COUNTRIES])
        # Capitals claim their ground first; country names take what is left,
        # otherwise FRANCE evicts Paris and JAPAN evicts Tokyo.
        for entry in sorted(CAPITALS, key=lambda c: c[3]) + countries:
            name, lat, lon, prio = entry[:4]
            hint = entry[4] if len(entry) > 4 else None
            is_country = prio == 0
            if prio and prio > args.max_priority:
                continue
            fx, fy = project(lon, lat, W)
            if not (0 <= fx < W and 0 <= fy < H):
                continue
            x, y = fx / ss, fy / ss
            tw = ld.textlength(name, font=font)
            th = size
            g = dot + 3
            pad = args.pad
            if is_country:
                # A centroid is not a good anchor: Greenland's lands near the
                # coast and the name hangs off the island. Instead find the
                # point furthest from that country's own edges -- its pole of
                # inaccessibility -- and require the whole word to sit on that
                # one fill, so a name can never spill into a neighbour or the
                # sea.
                region = country_region(fx, fy)
                if region is None:
                    skipped_tight.append(name)
                    continue
                # Containment is measured on the glyphs alone. The padding is
                # clearance from other labels, and counting it here demanded a
                # country be 46 px thick at its narrowest, which dropped Peru,
                # Iran and Mongolia despite each having ample room for the word.
                need_w, need_h = tw * ss, th * ss
                spots = interior_spots(region, need_w, need_h, ss)
                chosen = None
                for cx, cy in spots:
                    cbox = (cx - tw / 2 - pad, cy - th / 2 - pad,
                            cx + tw / 2 + pad, cy + th / 2 + pad)
                    # A country name has already been proved to sit on its own
                    # fill, so linework beneath it matters less than it does for
                    # a city label; what must hold is that it clears every label
                    # already placed.
                    if free(cbox) and busy(cbox) <= args.max_clutter * 1.6:
                        chosen = (cx, cy, cbox)
                        break
                if chosen is None:
                    skipped_tight.append(name)
                    continue
                cx, cy, cbox = chosen
                taken.append(cbox)
                mark_busy(cbox)
                ld.text((cx - tw / 2, cy - th / 2), name, font=font,
                        fill=(*LABEL_RGB, 255))
                placed.append({"name": name, "kind": "country",
                               "lat": lat, "lon": lon})
                continue
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
            placed.append({"name": name, "kind": "capital",
                           "lat": lat, "lon": lon,
                           "x": round(fx, 1), "y": round(fy, 1),
                           "clutter": round(score, 4)})

        if args.dateline and args.dateline.exists():
            # Set sideways in the publisher's orange, in the strip of ocean west
            # of the line itself. The box is cut to the glyphs: any slack in it
            # pushes the caption across the line, and there are only ~22 px of
            # margin between the map edge and the 180th meridian.
            text = "International Date Line"
            tb = font.getbbox(text)
            caption = Image.new("RGBA", (tb[2] + 2, tb[3] + 2), (0, 0, 0, 0))
            cd = ImageDraw.Draw(caption)
            cd.fontmode = "1"
            cd.text((0, 0), text, font=font, fill=(*DATELINE_RGB, 255))
            caption = caption.rotate(90, expand=True)
            layer.alpha_composite(caption, (3, int(H / ss * 0.36)))

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
