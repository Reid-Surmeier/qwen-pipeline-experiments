#!/usr/bin/env python3
"""Accept a pass only if it kept the type it was told to keep.

Pass C removed South America's country names while clearing its furniture, and
nothing caught it until the contact sheet. The filter is stochastic, so the same
prompt run again often succeeds -- but only if a failed attempt is detected and
rejected rather than saved over a good result.

Furniture removal legitimately lowers the ink ratio, so the test is not "ink
must not drop"; it is that ink inside the *map body* must survive. The furniture
sits in the margins, so the centre is measured and the outer frame ignored.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image


def body_ink(path: Path, inset: float = 0.14) -> float:
    a = np.asarray(Image.open(path).convert("RGB")).astype(int)
    h, w, _ = a.shape
    y0, y1 = int(h * inset), int(h * (1 - inset))
    x0, x1 = int(w * inset), int(w * (1 - inset))
    return float((a[y0:y1, x0:x1].max(axis=2) < 110).mean())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True, type=Path)
    ap.add_argument("--after", required=True, type=Path)
    ap.add_argument("--min-keep", type=float, default=0.80)
    args = ap.parse_args()
    b, a = body_ink(args.before), body_ink(args.after)
    kept = a / b if b else 0.0
    ok = kept >= args.min_keep
    print(f"body ink {100*b:.2f}% -> {100*a:.2f}%  kept {100*kept:.0f}%  "
          f"{'ACCEPT' if ok else 'REJECT (type lost)'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
