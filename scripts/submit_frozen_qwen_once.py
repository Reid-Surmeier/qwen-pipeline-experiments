#!/usr/bin/env python3.12
"""Submit one already-reserved Qwen Image request, with no retry path."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


EXPECTED_TOOL_COMMIT = "b2e4f594f6fb23e0dcc4e2a3395d492585a35c9b"
EXPECTED_SOURCE_SHA256 = "1115739048230bb6f1f8679af204fee87591595de7f5efb9a92f29f1849afaee"
EXPECTED_PROVIDER_SHA256 = "58af7d8dc096e0bb2b37ada4e49b35ffbbd98788a7292720b2c89f130de88f83"
TOOL_REPOSITORY = Path("/home/reidsurmeier/qwen-image-pipeline")
RUN_DIRECTORY = Path(
    "artifacts/qwen-pipeline/runs/qwen-image-study-001-20260830T193454Z"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def canonical_sha256(value: object) -> str:
    payload = json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def write_exclusive(path: Path, payload: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)


def append_event(event: dict[str, object]) -> None:
    with (RUN_DIRECTORY / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, separators=(",", ":")) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def sanitized_response(response: dict[str, object]) -> dict[str, object]:
    clean = dict(response)
    images = []
    for item in response.get("data", []):
        if not isinstance(item, dict) or not isinstance(item.get("b64_json"), str):
            images.append({"status": "unusable-image-record"})
            continue
        image_bytes = base64.b64decode(item["b64_json"], validate=True)
        images.append(
            {
                "media_type": item.get("media_type", "application/octet-stream"),
                "bytes": len(image_bytes),
                "sha256": hashlib.sha256(image_bytes).hexdigest(),
            }
        )
    clean["data"] = images
    return clean


def main() -> int:
    tool_head = subprocess.check_output(
        ["git", "-C", str(TOOL_REPOSITORY), "rev-parse", "HEAD"], text=True
    ).strip()
    if tool_head != EXPECTED_TOOL_COMMIT:
        raise RuntimeError(f"tool checkout is not pinned: {tool_head}")

    sys.path.insert(0, str(TOOL_REPOSITORY))
    from qwen_ui_pipeline.providers.openrouter import OpenRouterImageClient

    source_request = json.loads((RUN_DIRECTORY / "source-request.json").read_text())
    provider_request = json.loads((RUN_DIRECTORY / "request.json").read_text())
    if canonical_sha256(source_request) != EXPECTED_SOURCE_SHA256:
        raise RuntimeError("source request changed after preflight")
    if canonical_sha256(provider_request) != EXPECTED_PROVIDER_SHA256:
        raise RuntimeError("provider request changed after reservation")

    events = [json.loads(line) for line in (RUN_DIRECTORY / "events.jsonl").read_text().splitlines()]
    reservation = events[0]
    if (
        reservation.get("event") != "paid_action_reserved"
        or reservation.get("billing_state") != "possibly_spent"
        or reservation.get("safe_to_retry") is not False
        or reservation.get("provider_request_sha256") != EXPECTED_PROVIDER_SHA256
    ):
        raise RuntimeError("paid-action reservation is absent or contradictory")

    attempt = {
        "attempt_id": "qwen-image-study-001-20260830T193454Z",
        "created_at": utc_now(),
        "provider": "openrouter",
        "model": "qwen/qwen-image-3-pro",
        "provider_request_sha256": EXPECTED_PROVIDER_SHA256,
        "status": "submitting",
        "billing_state": "possibly_spent",
        "safe_to_retry": False,
    }
    write_exclusive(
        RUN_DIRECTORY / "submission-attempt.json",
        (json.dumps(attempt, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    append_event(
        {
            "timestamp": utc_now(),
            "event": "submission_started",
            "provider_request_sha256": EXPECTED_PROVIDER_SHA256,
            "billing_state": "possibly_spent",
            "safe_to_retry": False,
        }
    )

    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY was not injected")
    client = OpenRouterImageClient(key, timeout=900)
    try:
        response = client.generate(provider_request)
    except BaseException as error:
        error_record = {
            "timestamp": utc_now(),
            "error_type": type(error).__name__,
            "message": str(error),
            "billing_state": "possibly_spent",
            "safe_to_retry": False,
        }
        write_exclusive(
            RUN_DIRECTORY / "provider-error.json",
            (json.dumps(error_record, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        )
        append_event({"event": "submission_ambiguous", **error_record})
        print(json.dumps({"status": "ambiguous", "safe_to_retry": False}))
        return 1

    response_record = sanitized_response(response)
    write_exclusive(
        RUN_DIRECTORY / "provider-response.json",
        (json.dumps(response_record, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    data = response.get("data")
    if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict):
        raise RuntimeError("provider response did not contain exactly one image record")
    encoded = data[0].get("b64_json")
    if not isinstance(encoded, str):
        raise RuntimeError("provider image record did not contain b64_json")
    donor_bytes = base64.b64decode(encoded, validate=True)
    media_type = str(data[0].get("media_type", "image/png"))
    extension = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}.get(
        media_type, ".bin"
    )
    donor_path = RUN_DIRECTORY / f"donor-raw{extension}"
    write_exclusive(donor_path, donor_bytes)
    donor_sha256 = hashlib.sha256(donor_bytes).hexdigest()
    request_id = response.get("id") or response.get("request_id")
    usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
    append_event(
        {
            "timestamp": utc_now(),
            "event": "submission_succeeded",
            "request_id": request_id,
            "completed_count": 1,
            "donor_path": donor_path.as_posix(),
            "donor_sha256": donor_sha256,
            "actual_cost_usd": usage.get("cost"),
            "billing_state": "spent",
            "safe_to_retry": False,
        }
    )
    print(
        json.dumps(
            {
                "status": "succeeded",
                "request_id": request_id,
                "completed_count": 1,
                "donor_path": donor_path.as_posix(),
                "donor_sha256": donor_sha256,
                "actual_cost_usd": usage.get("cost"),
                "safe_to_retry": False,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
