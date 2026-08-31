#!/usr/bin/env python3
"""Run one image-edit Render Pass against an OpenRouter Image API model and record it.

Storage-only harness for provider benchmarking. Writes a self-contained run
directory: sanitized request, sanitized response, decoded images, and a run
record carrying the measured cost, latency and output dimensions. Reference
image bytes and base64 payloads never enter the JSON.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import mimetypes
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

ENDPOINT = "https://openrouter.ai/api/v1/images"


class _KeepAliveHTTPSConnection(__import__("http.client", fromlist=["x"]).HTTPSConnection):
    """Idle image edits outlive NAT mappings without TCP keepalive probes."""

    def connect(self):
        super().connect()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        for name, value in (("TCP_KEEPIDLE", 30), ("TCP_KEEPINTVL", 15), ("TCP_KEEPCNT", 8)):
            option = getattr(socket, name, None)
            if option is not None:
                self.sock.setsockopt(socket.IPPROTO_TCP, option, value)


class _KeepAliveHTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, req):
        return self.do_open(_KeepAliveHTTPSConnection, req, context=self._context)


def _data_url(path: Path) -> str:
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return f"data:{media_type};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


# Read-timeout ceilings per request shape, in seconds.
#
# A timeout is a ceiling, not a duration: a 10 s call still returns in 10 s.
# But the ceiling must not be uniform. Too short converts a slow success into
# a paid nothing -- OpenRouter bills the finished image whether or not the
# client is still listening (see benchmarks/.../ledger.md, where a 180 s
# default lost billed 1K images). Too long hides a genuine hang for half an
# hour. Each ceiling below is ~3x the worst latency measured for that shape.
#
#   bare text-to-image        6-26 s measured  ->  60 s
#   referenced edit             42 s measured  -> 120 s
#   >=2K, or a slow family   214-224 s measured -> 600 s
TIMEOUT_BARE = 60.0
TIMEOUT_REFERENCED = 120.0
TIMEOUT_LARGE = 600.0
SLOW_MODEL_FAMILIES = ("qwen",)
LARGE_MIN_EDGE = 1920


def _is_large(body: dict) -> bool:
    """True if the request targets a >=2K output."""
    size = str(body.get("size") or "")
    match = re.fullmatch(r"\s*(\d+)\s*[xX]\s*(\d+)\s*", size)
    if match and max(int(match.group(1)), int(match.group(2))) >= LARGE_MIN_EDGE:
        return True
    hints = f"{body.get('resolution') or ''} {body.get('aspect_ratio') or ''}".lower()
    return "2k" in hints or "4k" in hints


def _default_timeout(body: dict, has_references: bool) -> tuple[float, str]:
    """Pick a read timeout from the request shape. Returns (seconds, why)."""
    model = str(body.get("model") or "").lower()
    if _is_large(body):
        return TIMEOUT_LARGE, "large output (>=2K)"
    if any(family in model for family in SLOW_MODEL_FAMILIES):
        return TIMEOUT_LARGE, "slow model family"
    if has_references:
        return TIMEOUT_REFERENCED, "referenced edit"
    return TIMEOUT_BARE, "bare text-to-image"


def _sanitize(body: dict) -> dict:
    clean = dict(body)
    references = clean.get("input_references")
    if isinstance(references, list):
        clean["input_references"] = [
            {"type": "image_url", "image_url": "[reference recorded separately]"} for _ in references
        ]
    return clean


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--prompt-file", required=True, type=Path)
    parser.add_argument("--reference", action="append", default=[], type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--label", default="")
    parser.add_argument("--size", help='literal "WxH"; the only sizing control meta/muse-image honors')
    parser.add_argument("--aspect-ratio")
    parser.add_argument("--resolution")
    parser.add_argument("--n", type=int, default=1)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--timeout", type=float, default=None,
                        help="read-timeout override in seconds; default is chosen from the request shape")
    args = parser.parse_args(argv)

    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        print("OPENROUTER_API_KEY is not set", file=sys.stderr)
        return 2

    prompt = args.prompt_file.read_text(encoding="utf-8").strip()
    body: dict = {"model": args.model, "prompt": prompt, "n": args.n}
    for flag, field in (("size", "size"), ("aspect_ratio", "aspect_ratio"), ("resolution", "resolution")):
        value = getattr(args, flag)
        if value:
            body[field] = value
    if args.seed is not None:
        body["seed"] = args.seed
    references = []
    for path in args.reference:
        body.setdefault("input_references", []).append(
            {"type": "image_url", "image_url": {"url": _data_url(path)}}
        )
        references.append(
            {
                "file": str(path),
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "dimensions": "x".join(str(v) for v in Image.open(path).size),
            }
        )

    if args.timeout is not None:
        timeout, timeout_reason = args.timeout, "explicit --timeout"
    else:
        timeout, timeout_reason = _default_timeout(body, bool(references))

    args.out.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "qwen-pipeline-experiments/bench",
        },
    )
    opener = urllib.request.build_opener(_KeepAliveHTTPSHandler())
    submitted = datetime.now(timezone.utc).isoformat()
    started = time.time()
    failure = None
    payload = None
    try:
        with opener.open(request, timeout=timeout) as response:
            payload = json.loads(response.read())
    except urllib.error.HTTPError as error:
        failure = {"kind": "http", "status": error.code,
                   "body": error.read(8192).decode("utf-8", "replace")[:4000]}
    except Exception as error:  # noqa: BLE001 - the record must survive any transport failure
        failure = {"kind": "transport", "error": repr(error)}
    seconds = round(time.time() - started, 1)

    outputs = []
    if payload:
        for index, item in enumerate(payload.get("data", []), start=1):
            if not isinstance(item, dict) or not isinstance(item.get("b64_json"), str):
                continue
            raw = base64.b64decode(item["b64_json"], validate=True)
            image = Image.open(io.BytesIO(raw))
            name = f"image-{index:02d}.png"
            image.convert("RGB").save(args.out / name)
            outputs.append(
                {
                    "file": name,
                    "source_media_type": item.get("media_type"),
                    "dimensions": f"{image.width}x{image.height}",
                    "aspect": round(image.width / image.height, 4),
                    "bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                }
            )

    usage = (payload or {}).get("usage", {})
    record = {
        "label": args.label or args.model,
        "model": args.model,
        "submitted_utc": submitted,
        "seconds": seconds,
        "timeout_seconds": timeout,
        "timeout_reason": timeout_reason,
        "requested": {k: v for k, v in body.items() if k not in {"prompt", "input_references"}},
        "prompt_file": str(args.prompt_file),
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "references": references,
        "cost_usd": usage.get("cost"),
        "usage": usage,
        "outputs": outputs,
        "failure": failure,
    }
    (args.out / "request.json").write_text(json.dumps(_sanitize(body) | {"prompt": prompt}, indent=2) + "\n")
    if payload is not None:
        redacted = dict(payload)
        redacted["data"] = [
            {k: (f"<{len(v)} base64 chars>" if k == "b64_json" else v) for k, v in i.items()}
            for i in payload.get("data", [])
        ]
        (args.out / "response.json").write_text(json.dumps(redacted, indent=2) + "\n")
    (args.out / "run.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({k: record[k] for k in ("label", "model", "seconds", "cost_usd", "outputs", "failure")}, indent=2))
    return 0 if outputs else 1


if __name__ == "__main__":
    raise SystemExit(main())
