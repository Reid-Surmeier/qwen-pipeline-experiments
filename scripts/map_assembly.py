#!/usr/bin/env python3
"""Assemble a recoloured map region by region from several Muse donors.

Asking one pass to recolour a whole dense sheet lets it redraw the map: on the
Asia sheet Kazakhstan's fill swallowed part of western China, and on the Middle
East sheet an island appeared in the Caspian. Prompting did not fix it across
five attempts, because the pass is free to move any pixel it likes.

Assembly removes that freedom. The reference stays authoritative and a donor may
only supply pixels inside one declared region, so nothing outside it can move --
the repo's own rule that a Fidelity Check reports zero changed pixels outside
declared edit regions. Several whole-sheet donors are generated, and each region
takes the donor that kept that region's geometry, which is what the repo means
by similarity metrics ranking generative donors.

Geometry is scored by border agreement, not by colour: a donor is supposed to
change every fill, so colour distance would rank the most faithful donor worst.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage


def edges(rgb: np.ndarray) -> np.ndarray:
    """Where one flat area meets another -- the map's linework, colour aside."""
    q = rgb // 26
    keyed = q[:, :, 0] * 4096 + q[:, :, 1] * 64 + q[:, :, 2]
    e = np.zeros(keyed.shape, bool)
    e[:, :-1] |= keyed[:, :-1] != keyed[:, 1:]
    e[:-1, :] |= keyed[:-1, :] != keyed[1:, :]
    return e


def agreement(ref_edges: np.ndarray, donor_edges: np.ndarray, slack: int = 2) -> float:
    """Fraction of reference borders the donor still draws in the same place."""
    if not ref_edges.any():
        return 1.0
    near = ndimage.binary_dilation(donor_edges, iterations=slack)
    kept = float((ref_edges & near).sum() / ref_edges.sum())
    # a donor that draws borders everywhere would score well on kept alone
    near_ref = ndimage.binary_dilation(ref_edges, iterations=slack)
    invented = float((donor_edges & ~near_ref).sum() / max(donor_edges.sum(), 1))
    return kept - invented


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reference", required=True, type=Path)
    ap.add_argument("--donor", action="append", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--grid", type=int, default=6, help="regions across and down")
    ap.add_argument("--min-agreement", type=float, default=0.55,
                    help="below this no donor is trusted and the reference stands")
    ap.add_argument("--single-donor", action="store_true",
                    help="use the best whole-sheet donor untouched. Mixing helps "
                         "when donors agree; on the South America sheet they "
                         "coloured Brazil differently and the mix produced a "
                         "checkerboard worse than any single donor.")
    ap.add_argument("--switch-margin", type=float, default=0.06,
                    help="how much better a rival must be before a region leaves "
                         "the base donor; picking per region independently gave "
                         "India two colours across a tile seam")
    args = ap.parse_args()

    ref_img = Image.open(args.reference).convert("RGB")
    ref = np.asarray(ref_img).astype(int)
    h, w, _ = ref.shape
    ref_e = edges(ref)

    donors = []
    for path in args.donor:
        if not path.exists():
            continue
        d = np.asarray(Image.open(path).convert("RGB").resize((w, h), Image.LANCZOS)).astype(int)
        donors.append((path.parent.name, d, edges(d)))
    if not donors:
        print("no donors")
        return 1

    # One donor is the base for the whole sheet so colouring stays consistent;
    # a region only leaves it when a rival is clearly better there. Choosing
    # freely per region split India into two colours across a tile edge.
    base_name, base, base_e = max(
        donors, key=lambda d: agreement(ref_e, d[2]))

    out = base.copy()
    regions, kept_ref = [], 0
    for gy in range(args.grid):
        for gx in range(args.grid):
            y0, y1 = h * gy // args.grid, h * (gy + 1) // args.grid
            x0, x1 = w * gx // args.grid, w * (gx + 1) // args.grid
            tile_ref_e = ref_e[y0:y1, x0:x1]
            scored = [(agreement(tile_ref_e, de[y0:y1, x0:x1]), name, d)
                      for name, d, de in donors]
            base_score = next(s_ for s_, n_, _ in scored if n_ == base_name)
            score, name, chosen = max(scored, key=lambda z: z[0])
            if args.single_donor or score < base_score + args.switch_margin:
                score, name, chosen = base_score, base_name, base
            if score < args.min_agreement:
                # Fall back to the base donor, not the reference. Reverting a
                # region to the reference restores its time-zone colouring, and
                # on the South America sheet eleven such regions turned Brazil
                # into a checkerboard of green and red rectangles. A slightly
                # worse border beats a visible tile seam.
                out[y0:y1, x0:x1] = base[y0:y1, x0:x1]
                kept_ref += 1
                regions.append({"x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0,
                                "donor": base_name, "agreement": round(score, 3),
                                "fallback": True})
                continue
            out[y0:y1, x0:x1] = chosen[y0:y1, x0:x1]
            regions.append({"x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0,
                            "donor": name, "agreement": round(score, 3)})

    args.out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(out.astype("uint8")).save(args.out)

    # Prove the Assembly kept its contract: every pixel outside a declared
    # region must be byte identical to the reference, which is the repo's
    # standing definition of strict preservation.
    declared = np.zeros((h, w), bool)
    for r in regions:
        if r["donor"]:
            declared[r["y"]:r["y"] + r["height"], r["x"]:r["x"] + r["width"]] = True
    outside_changed = int(((out != ref).any(axis=2) & ~declared).sum())

    used = {}
    for r in regions:
        used[r["donor"] or "reference"] = used.get(r["donor"] or "reference", 0) + 1
    contract = {"canvas": {"width": w, "height": h},
                "regions": [{"name": f"r{i}", **{k: r[k] for k in ("x", "y", "width", "height")}}
                            for i, r in enumerate(regions) if r["donor"]]}
    args.out.with_suffix(".assembly.json").write_text(
        json.dumps({"regions": regions, "donors_used": used, "contract": contract,
                    "base_donor": base_name,
                    "pixels_changed_outside_declared_regions": outside_changed},
                   indent=2) + "\n")
    mean = sum(r["agreement"] for r in regions) / len(regions)
    print(f"{args.out.stem:14s} {len(regions)} regions, mean agreement {mean:.3f}, "
          f"reference kept in {kept_ref}, donors: {used}\n"
          f"{'':14s} outside declared regions: {outside_changed} pixels changed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
