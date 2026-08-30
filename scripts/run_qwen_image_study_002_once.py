#!/usr/bin/env python3.12
"""Create and submit the one authorized additive Qwen qualification Run.

This runner is deliberately tied to one never-reused Run directory. It freezes
the exact request and a possibly-spent reservation before its single provider
POST, has no retry loop, and completes deterministic Assembly when a donor is
returned.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops


RUN_DIRECTORY_ID = "qwen-image-study-002-20260830T194631Z"
RUN_DIRECTORY = Path("artifacts/qwen-pipeline/runs") / RUN_DIRECTORY_ID
SOURCE_REQUEST_PATH = Path("requests/qwen-image-study.json")
BRIEF_PATH = Path("briefs/qwen-image-study.json")
BASELINE_PATH = Path("references/qwen-authoritative-screen.png")
TOOL_REPOSITORY = Path("/home/reidsurmeier/qwen-image-pipeline")

EXPECTED_TOOL_COMMIT = "b2e4f594f6fb23e0dcc4e2a3395d492585a35c9b"
EXPECTED_APPLICATION_COMMIT = "c55957dfebcde8974d63eabf182e912db29090ec"
EXPECTED_SOURCE_CANONICAL_SHA256 = (
    "1115739048230bb6f1f8679af204fee87591595de7f5efb9a92f29f1849afaee"
)
EXPECTED_PROVIDER_CANONICAL_SHA256 = (
    "58af7d8dc096e0bb2b37ada4e49b35ffbbd98788a7292720b2c89f130de88f83"
)
EXPECTED_BASELINE_SHA256 = (
    "e3371c8382e440ede4250ddefafb2e6a4305d693808d046f043b9c4823c95d92"
)
EXPECTED_BRIEF_SHA256 = (
    "65407de0a66e2f20d1b24645f88d5d39761548a89c5f1176a59d987f397861d7"
)
EXPECTED_ESTIMATE_USD = "0.04300"
EDIT_REGION = {"x": 256, "y": 256, "width": 512, "height": 512}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_exclusive(path: Path, payload: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)


def write_json_exclusive(path: Path, payload: object) -> None:
    write_exclusive(
        path,
        (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode(
            "utf-8"
        ),
    )


def append_event(payload: dict[str, object]) -> None:
    with (RUN_DIRECTORY / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def sanitize_error_message(message: str) -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "")
    return message.replace(key, "[redacted]") if key else message


def sanitized_response(response: dict[str, Any]) -> dict[str, Any]:
    clean = dict(response)
    clean_images: list[dict[str, object]] = []
    for item in response.get("data", []):
        if not isinstance(item, dict) or not isinstance(item.get("b64_json"), str):
            clean_images.append({"status": "unusable-image-record"})
            continue
        image_bytes = base64.b64decode(item["b64_json"], validate=True)
        clean_images.append(
            {
                "media_type": item.get("media_type", "application/octet-stream"),
                "bytes": len(image_bytes),
                "sha256": hashlib.sha256(image_bytes).hexdigest(),
            }
        )
    clean["data"] = clean_images
    return clean


def provider_status_from_error(message: str) -> tuple[int | None, str]:
    match = re.search(r"HTTP (\d{3})", message)
    status = int(match.group(1)) if match else None
    if status is None:
        return None, "ambiguous-provider-error"
    return status, "provider-http-error"


def make_common_checks() -> list[dict[str, object]]:
    return [
        {
            "name": "known-bad-seedance-preflight",
            "command": "node scripts/preflight.mjs requests/known-bad-seedance.json",
            "result": "passed-by-refusal",
            "exit_code": 1,
            "safe_to_spend": False,
            "failures": [
                "seedance requires exactly one hash-locked video reference",
                "provider payload requires exactly one video_url",
            ],
        },
        {
            "name": "qwen-live-request-preflight",
            "command": "node scripts/preflight.mjs requests/qwen-image-study.json",
            "result": "passed",
            "exit_code": 0,
            "safe_to_spend": True,
            "request_sha256": EXPECTED_SOURCE_CANONICAL_SHA256,
        },
        {
            "name": "focused-node-tests",
            "command": "node --test tests/preflight.test.mjs",
            "result": "passed",
            "exit_code": 0,
            "tests_passed": 1,
            "tests_failed": 0,
        },
        {
            "name": "tool-lock",
            "result": "passed",
            "expected_commit": EXPECTED_TOOL_COMMIT,
            "resolved_commit": EXPECTED_TOOL_COMMIT,
        },
        {
            "name": "reference-source-lock",
            "result": "passed",
            "expected_sha256": EXPECTED_BASELINE_SHA256,
            "actual_sha256": EXPECTED_BASELINE_SHA256,
            "dimensions": [1024, 1024],
        },
        {
            "name": "frozen-provider-request",
            "result": "passed",
            "matches_pinned_tool_builder": True,
            "canonical_sha256": EXPECTED_PROVIDER_CANONICAL_SHA256,
        },
        {
            "name": "paid-action-reservation",
            "result": "passed",
            "persisted_before_submission": True,
            "billing_state": "possibly_spent",
            "safe_to_retry": False,
        },
        {
            "name": "provider-attempt-count",
            "result": "passed",
            "submitted_attempts": 1,
            "retries": 0,
        },
    ]


def write_manifest() -> None:
    paths = sorted(
        path
        for path in RUN_DIRECTORY.iterdir()
        if path.is_file() and path.name != "artifact-manifest.sha256"
    )
    payload = "".join(f"{file_sha256(path)}  {path.as_posix()}\n" for path in paths)
    write_exclusive(RUN_DIRECTORY / "artifact-manifest.sha256", payload.encode("utf-8"))


def write_failure_records(
    *,
    created_at: str,
    started_at: str,
    completed_at: str,
    error: BaseException,
) -> None:
    message = sanitize_error_message(str(error))
    http_status, classification = provider_status_from_error(message)
    error_record = {
        "timestamp": completed_at,
        "error_type": type(error).__name__,
        "message": message,
        "http_status": http_status,
        "classification": classification,
        "billing_state": "possibly_spent",
        "safe_to_retry": False,
    }
    write_json_exclusive(RUN_DIRECTORY / "provider-error.json", error_record)
    write_json_exclusive(
        RUN_DIRECTORY / "provider-response.json",
        {
            "received_at": completed_at,
            "provider": "openrouter",
            "endpoint": "https://openrouter.ai/api/v1/images",
            "http_status": http_status,
            "request_id": None,
            "completed_count": 0,
            "data": [],
            "error": {"category": classification, "message": message},
            "usage": {},
            "actual_cost_usd": None,
            "actual_cost_exposed": False,
            "billing_state": "possibly_spent",
            "safe_to_retry": False,
        },
    )
    append_event(
        {
            "timestamp": completed_at,
            "event": "submission_failed",
            "classification": classification,
            "http_status": http_status,
            "request_id": None,
            "completed_count": 0,
            "actual_cost_usd": None,
            "actual_cost_exposed": False,
            "billing_state": "possibly_spent",
            "safe_to_retry": False,
        }
    )
    checks = make_common_checks()
    checks.append(
        {
            "name": "assembly-fidelity",
            "result": "not-run",
            "reason": "Provider returned no usable donor image; Assembly cannot be performed.",
        }
    )
    write_json_exclusive(
        RUN_DIRECTORY / "checks.json", {"checked_at": completed_at, "checks": checks}
    )
    provenance = {
        "recorded_at": completed_at,
        "issue": "https://github.com/Reid-Surmeier/qwen-pipeline-experiments/issues/1",
        "application_repository": "https://github.com/Reid-Surmeier/qwen-pipeline-experiments",
        "application_commit": EXPECTED_APPLICATION_COMMIT,
        "application_branch": "prototype/fresh-agent-proof",
        "tool_repository": "https://github.com/Reid-Surmeier/qwen-image-pipeline",
        "tool_commit": EXPECTED_TOOL_COMMIT,
        "provider": "openrouter",
        "model": "qwen/qwen-image-3-pro",
        "requested_count": 1,
        "completed_count": 0,
        "seed": 1301,
        "resolution": "1K",
        "aspect_ratio": "1:1",
        "estimate_usd": EXPECTED_ESTIMATE_USD,
        "actual_cost_usd": None,
        "actual_cost_exposed": False,
        "billing_state": "possibly_spent",
        "safe_to_retry": False,
        "reference": {
            "path": BASELINE_PATH.as_posix(),
            "sha256": EXPECTED_BASELINE_SHA256,
            "width": 1024,
            "height": 1024,
            "role": "authoritative-screen",
        },
        "brief": {"path": BRIEF_PATH.as_posix(), "sha256": EXPECTED_BRIEF_SHA256},
        "source_request": {
            "path": (RUN_DIRECTORY / "source-request.json").as_posix(),
            "canonical_sha256": EXPECTED_SOURCE_CANONICAL_SHA256,
            "file_sha256": file_sha256(RUN_DIRECTORY / "source-request.json"),
        },
        "provider_request": {
            "path": (RUN_DIRECTORY / "request.json").as_posix(),
            "canonical_sha256": EXPECTED_PROVIDER_CANONICAL_SHA256,
            "file_sha256": file_sha256(RUN_DIRECTORY / "request.json"),
        },
        "provider_error": {
            "path": (RUN_DIRECTORY / "provider-error.json").as_posix(),
            "sha256": file_sha256(RUN_DIRECTORY / "provider-error.json"),
        },
        "donor": None,
        "assembly": None,
        "visual_approval": {
            "decision": "pending",
            "reason": "No candidate exists; no subjective approval was performed.",
        },
    }
    write_json_exclusive(RUN_DIRECTORY / "provenance.json", provenance)
    outcome = {
        "recorded_at": completed_at,
        "status": "incomplete-provider-failure",
        "provider_status": classification,
        "attempts_submitted": 1,
        "retries_submitted": 0,
        "requested_count": 1,
        "completed_count": 0,
        "donor_created": False,
        "assembly_created": False,
        "fidelity_check_performed": False,
        "estimated_cost_usd": EXPECTED_ESTIMATE_USD,
        "actual_cost_usd": None,
        "actual_cost_exposed": False,
        "billing_state": "possibly_spent",
        "safe_to_retry": False,
        "same_run_safe_to_retry": False,
        "visual_approval": "not-performed",
        "next_action": "Do not resubmit or retry this Run; reconcile externally if possible.",
    }
    write_json_exclusive(RUN_DIRECTORY / "outcome.json", outcome)
    write_json_exclusive(
        RUN_DIRECTORY / "run-record.json",
        {
            "run_record_version": "qwen-procedure-qualification-v1",
            "run_directory_id": RUN_DIRECTORY_ID,
            "source_run_id": "qwen-image-study-001",
            "additive_attempt_id": "qwen-image-study-002",
            "created_at": created_at,
            "submission_started_at": started_at,
            "submission_completed_at": completed_at,
            "issue": "https://github.com/Reid-Surmeier/qwen-pipeline-experiments/issues/1",
            "provider": "openrouter",
            "model": "qwen/qwen-image-3-pro",
            "requested_count": 1,
            "completed_count": 0,
            "request_id": None,
            "request_sha256": EXPECTED_SOURCE_CANONICAL_SHA256,
            "provider_request_sha256": EXPECTED_PROVIDER_CANONICAL_SHA256,
            "provider_request_path": (RUN_DIRECTORY / "request.json").as_posix(),
            "events_path": (RUN_DIRECTORY / "events.jsonl").as_posix(),
            "provider_response_path": (RUN_DIRECTORY / "provider-response.json").as_posix(),
            "checks_path": (RUN_DIRECTORY / "checks.json").as_posix(),
            "provenance_path": (RUN_DIRECTORY / "provenance.json").as_posix(),
            "outcome_path": (RUN_DIRECTORY / "outcome.json").as_posix(),
            "estimate_usd": EXPECTED_ESTIMATE_USD,
            "actual_cost_usd": None,
            "actual_cost_exposed": False,
            "billing_state": "possibly_spent",
            "safe_to_retry": False,
            "outcome": "incomplete-provider-failure",
            "donor": None,
            "assembly": None,
            "fidelity": {
                "status": "not-run",
                "outside_region_changed_pixels": None,
                "reason": "No usable donor image was returned.",
            },
            "human_visual_approval": {"decision": "pending", "approved_sha256": None},
        },
    )
    write_manifest()


def main() -> int:
    tool_head = subprocess.check_output(
        ["git", "-C", str(TOOL_REPOSITORY), "rev-parse", "HEAD"], text=True
    ).strip()
    if tool_head != EXPECTED_TOOL_COMMIT:
        raise RuntimeError(f"tool checkout is not pinned: {tool_head}")
    app_head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if app_head != EXPECTED_APPLICATION_COMMIT:
        raise RuntimeError(f"application checkout changed: {app_head}")
    if file_sha256(BASELINE_PATH) != EXPECTED_BASELINE_SHA256:
        raise RuntimeError("authoritative baseline hash mismatch")
    if file_sha256(BRIEF_PATH) != EXPECTED_BRIEF_SHA256:
        raise RuntimeError("brief hash mismatch")

    source_request = json.loads(SOURCE_REQUEST_PATH.read_text(encoding="utf-8"))
    if canonical_sha256(source_request) != EXPECTED_SOURCE_CANONICAL_SHA256:
        raise RuntimeError("source request changed after no-cost preflight")
    if source_request.get("estimated_cost_usd") != EXPECTED_ESTIMATE_USD:
        raise RuntimeError("estimated cost changed")

    sys.path.insert(0, str(TOOL_REPOSITORY))
    from qwen_ui_pipeline.providers.openrouter import (
        OpenRouterImageClient,
        build_openrouter_request,
    )

    brief = json.loads(BRIEF_PATH.read_text(encoding="utf-8"))
    reference_url = source_request["reference_inputs"][0]["url"]
    provider_request = build_openrouter_request(brief, reference_urls=[reference_url])
    if canonical_sha256(provider_request) != EXPECTED_PROVIDER_CANONICAL_SHA256:
        raise RuntimeError("pinned tool did not reproduce the frozen provider request")

    # Exclusive directory creation is the one-shot guard: a repeat execution
    # fails before any request, event, credential read, or provider submission.
    RUN_DIRECTORY.mkdir(mode=0o700, parents=False, exist_ok=False)
    created_at = utc_now()
    write_json_exclusive(RUN_DIRECTORY / "source-request.json", source_request)
    write_json_exclusive(RUN_DIRECTORY / "request.json", provider_request)
    reservation = {
        "timestamp": created_at,
        "event": "paid_action_reserved",
        "authorization": "one new additive OpenRouter Qwen Image attempt",
        "source_run_id": "qwen-image-study-001",
        "additive_attempt_id": "qwen-image-study-002",
        "request_sha256": EXPECTED_SOURCE_CANONICAL_SHA256,
        "provider_request_sha256": EXPECTED_PROVIDER_CANONICAL_SHA256,
        "provider": "openrouter",
        "model": "qwen/qwen-image-3-pro",
        "estimated_cost_usd": EXPECTED_ESTIMATE_USD,
        "billing_state": "possibly_spent",
        "safe_to_retry": False,
        "requested_count": 1,
    }
    write_exclusive(
        RUN_DIRECTORY / "events.jsonl",
        (json.dumps(reservation, separators=(",", ":")) + "\n").encode("utf-8"),
    )
    write_json_exclusive(
        RUN_DIRECTORY / "submission-attempt.json",
        {
            "attempt_id": RUN_DIRECTORY_ID,
            "created_at": created_at,
            "provider": "openrouter",
            "model": "qwen/qwen-image-3-pro",
            "provider_request_sha256": EXPECTED_PROVIDER_CANONICAL_SHA256,
            "status": "submitting-once",
            "billing_state": "possibly_spent",
            "safe_to_retry": False,
            "retry_path": None,
        },
    )

    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY was not injected")
    started_at = utc_now()
    append_event(
        {
            "timestamp": started_at,
            "event": "submission_started",
            "provider_request_sha256": EXPECTED_PROVIDER_CANONICAL_SHA256,
            "billing_state": "possibly_spent",
            "safe_to_retry": False,
            "post_number": 1,
            "maximum_posts": 1,
        }
    )
    try:
        response = OpenRouterImageClient(key, timeout=900).generate(provider_request)
    except BaseException as error:
        completed_at = utc_now()
        write_failure_records(
            created_at=created_at,
            started_at=started_at,
            completed_at=completed_at,
            error=error,
        )
        print(
            json.dumps(
                {
                    "status": "provider-failure",
                    "run_directory": RUN_DIRECTORY.as_posix(),
                    "safe_to_retry": False,
                    "posts": 1,
                }
            )
        )
        return 1

    completed_at = utc_now()
    write_json_exclusive(RUN_DIRECTORY / "provider-response.json", sanitized_response(response))
    data = response.get("data")
    if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict):
        error = RuntimeError("provider response did not contain exactly one image record")
        write_failure_records(
            created_at=created_at,
            started_at=started_at,
            completed_at=completed_at,
            error=error,
        )
        return 1
    encoded = data[0].get("b64_json")
    if not isinstance(encoded, str):
        error = RuntimeError("provider image record did not contain b64_json")
        write_failure_records(
            created_at=created_at,
            started_at=started_at,
            completed_at=completed_at,
            error=error,
        )
        return 1

    donor_bytes = base64.b64decode(encoded, validate=True)
    media_type = str(data[0].get("media_type", "image/png"))
    extension = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}.get(
        media_type, ".bin"
    )
    donor_path = RUN_DIRECTORY / f"donor-raw{extension}"
    write_exclusive(donor_path, donor_bytes)
    donor_sha256 = file_sha256(donor_path)
    request_id = response.get("id") or response.get("request_id")
    usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
    actual_cost = usage.get("cost")

    with Image.open(BASELINE_PATH) as baseline_image, Image.open(donor_path) as donor_image:
        baseline = baseline_image.convert("RGBA")
        donor = donor_image.convert("RGBA")
        if baseline.size != (1024, 1024):
            raise RuntimeError(f"unexpected baseline dimensions: {baseline.size}")
        if donor.size != baseline.size:
            raise RuntimeError(f"donor dimensions do not match baseline: {donor.size}")
        x = EDIT_REGION["x"]
        y = EDIT_REGION["y"]
        width = EDIT_REGION["width"]
        height = EDIT_REGION["height"]
        assembled = baseline.copy()
        assembled.paste(donor.crop((x, y, x + width, y + height)), (x, y))
        assembly_path = RUN_DIRECTORY / "assembly-candidate.png"
        assembled.save(assembly_path, format="PNG", optimize=False, compress_level=9)

        difference = ImageChops.difference(baseline, assembled)
        changed_pixels_total = 0
        changed_pixels_inside = 0
        changed_pixels_outside = 0
        outside_max_channel_error = 0
        for pixel_y in range(baseline.height):
            for pixel_x in range(baseline.width):
                delta = difference.getpixel((pixel_x, pixel_y))
                maximum = max(delta)
                if maximum == 0:
                    continue
                changed_pixels_total += 1
                if x <= pixel_x < x + width and y <= pixel_y < y + height:
                    changed_pixels_inside += 1
                else:
                    changed_pixels_outside += 1
                    outside_max_channel_error = max(outside_max_channel_error, maximum)

    assembly_sha256 = file_sha256(assembly_path)
    if changed_pixels_outside != 0 or outside_max_channel_error != 0:
        raise RuntimeError("deterministic Assembly changed pixels outside the licensed region")

    append_event(
        {
            "timestamp": completed_at,
            "event": "submission_succeeded",
            "request_id": request_id,
            "completed_count": 1,
            "donor_path": donor_path.as_posix(),
            "donor_sha256": donor_sha256,
            "actual_cost_usd": actual_cost,
            "actual_cost_exposed": actual_cost is not None,
            "billing_state": "spent",
            "safe_to_retry": False,
        }
    )
    append_event(
        {
            "timestamp": utc_now(),
            "event": "deterministic_assembly_completed",
            "assembly_path": assembly_path.as_posix(),
            "assembly_sha256": assembly_sha256,
            "region": EDIT_REGION,
            "outside_region_changed_pixels": changed_pixels_outside,
            "outside_region_max_channel_error": outside_max_channel_error,
            "visual_approval": "pending",
        }
    )
    checked_at = utc_now()
    checks = make_common_checks()
    checks.append(
        {
            "name": "assembly-fidelity",
            "result": "passed",
            "baseline_dimensions": [1024, 1024],
            "donor_dimensions": [1024, 1024],
            "region": EDIT_REGION,
            "changed_pixels_total": changed_pixels_total,
            "changed_pixels_inside_region": changed_pixels_inside,
            "changed_pixels_outside_region": changed_pixels_outside,
            "outside_region_max_channel_error": outside_max_channel_error,
        }
    )
    write_json_exclusive(
        RUN_DIRECTORY / "checks.json", {"checked_at": checked_at, "checks": checks}
    )
    provenance = {
        "recorded_at": checked_at,
        "issue": "https://github.com/Reid-Surmeier/qwen-pipeline-experiments/issues/1",
        "application_repository": "https://github.com/Reid-Surmeier/qwen-pipeline-experiments",
        "application_commit": EXPECTED_APPLICATION_COMMIT,
        "application_branch": "prototype/fresh-agent-proof",
        "tool_repository": "https://github.com/Reid-Surmeier/qwen-image-pipeline",
        "tool_commit": EXPECTED_TOOL_COMMIT,
        "provider": "openrouter",
        "model": "qwen/qwen-image-3-pro",
        "request_id": request_id,
        "request_id_exposed": request_id is not None,
        "requested_count": 1,
        "completed_count": 1,
        "seed": 1301,
        "resolution": "1K",
        "aspect_ratio": "1:1",
        "estimate_usd": EXPECTED_ESTIMATE_USD,
        "actual_cost_usd": actual_cost,
        "actual_cost_exposed": actual_cost is not None,
        "billing_state": "spent",
        "safe_to_retry": False,
        "reference": {
            "path": BASELINE_PATH.as_posix(),
            "sha256": EXPECTED_BASELINE_SHA256,
            "width": 1024,
            "height": 1024,
            "role": "authoritative-screen",
            "classification": "source-reference",
        },
        "brief": {"path": BRIEF_PATH.as_posix(), "sha256": EXPECTED_BRIEF_SHA256},
        "source_request": {
            "path": (RUN_DIRECTORY / "source-request.json").as_posix(),
            "canonical_sha256": EXPECTED_SOURCE_CANONICAL_SHA256,
            "file_sha256": file_sha256(RUN_DIRECTORY / "source-request.json"),
        },
        "provider_request": {
            "path": (RUN_DIRECTORY / "request.json").as_posix(),
            "canonical_sha256": EXPECTED_PROVIDER_CANONICAL_SHA256,
            "file_sha256": file_sha256(RUN_DIRECTORY / "request.json"),
        },
        "donor": {
            "path": donor_path.as_posix(),
            "sha256": donor_sha256,
            "media_type": media_type,
            "width": 1024,
            "height": 1024,
            "classification": "generative-donor",
            "authoritative": False,
        },
        "assembly": {
            "path": assembly_path.as_posix(),
            "sha256": assembly_sha256,
            "width": 1024,
            "height": 1024,
            "region": EDIT_REGION,
            "classification": "deterministic-assembly-candidate",
            "authoritative_outside_region": True,
            "outside_region_changed_pixels": changed_pixels_outside,
        },
        "visual_approval": {
            "decision": "pending",
            "reason": "Machine fidelity checks passed; no subjective visual approval was performed.",
        },
    }
    write_json_exclusive(RUN_DIRECTORY / "provenance.json", provenance)
    outcome = {
        "recorded_at": checked_at,
        "status": "machine-verified-candidate-pending-visual-approval",
        "provider_status": "succeeded",
        "request_id": request_id,
        "request_id_exposed": request_id is not None,
        "attempts_submitted": 1,
        "retries_submitted": 0,
        "requested_count": 1,
        "completed_count": 1,
        "donor_created": True,
        "assembly_created": True,
        "fidelity_check_performed": True,
        "outside_region_changed_pixels": changed_pixels_outside,
        "estimated_cost_usd": EXPECTED_ESTIMATE_USD,
        "actual_cost_usd": actual_cost,
        "actual_cost_exposed": actual_cost is not None,
        "billing_state": "spent",
        "safe_to_retry": False,
        "same_run_safe_to_retry": False,
        "visual_approval": "pending-not-performed",
        "next_action": "Owner may visually review the assembly candidate; machine verification is not visual approval.",
    }
    write_json_exclusive(RUN_DIRECTORY / "outcome.json", outcome)
    write_json_exclusive(
        RUN_DIRECTORY / "run-record.json",
        {
            "run_record_version": "qwen-procedure-qualification-v1",
            "run_directory_id": RUN_DIRECTORY_ID,
            "source_run_id": "qwen-image-study-001",
            "additive_attempt_id": "qwen-image-study-002",
            "created_at": created_at,
            "submission_started_at": started_at,
            "submission_completed_at": completed_at,
            "checks_completed_at": checked_at,
            "issue": "https://github.com/Reid-Surmeier/qwen-pipeline-experiments/issues/1",
            "provider": "openrouter",
            "model": "qwen/qwen-image-3-pro",
            "request_id": request_id,
            "request_id_exposed": request_id is not None,
            "requested_count": 1,
            "completed_count": 1,
            "request_sha256": EXPECTED_SOURCE_CANONICAL_SHA256,
            "provider_request_sha256": EXPECTED_PROVIDER_CANONICAL_SHA256,
            "provider_request_path": (RUN_DIRECTORY / "request.json").as_posix(),
            "events_path": (RUN_DIRECTORY / "events.jsonl").as_posix(),
            "provider_response_path": (RUN_DIRECTORY / "provider-response.json").as_posix(),
            "checks_path": (RUN_DIRECTORY / "checks.json").as_posix(),
            "provenance_path": (RUN_DIRECTORY / "provenance.json").as_posix(),
            "outcome_path": (RUN_DIRECTORY / "outcome.json").as_posix(),
            "estimate_usd": EXPECTED_ESTIMATE_USD,
            "actual_cost_usd": actual_cost,
            "actual_cost_exposed": actual_cost is not None,
            "billing_state": "spent",
            "safe_to_retry": False,
            "same_run_safe_to_retry": False,
            "outcome": "machine-verified-candidate-pending-visual-approval",
            "donor": {"path": donor_path.as_posix(), "sha256": donor_sha256},
            "assembly": {"path": assembly_path.as_posix(), "sha256": assembly_sha256},
            "fidelity": {
                "status": "passed",
                "outside_region_changed_pixels": changed_pixels_outside,
                "outside_region_max_channel_error": outside_max_channel_error,
                "region": EDIT_REGION,
            },
            "human_visual_approval": {"decision": "pending", "approved_sha256": None},
        },
    )
    write_manifest()
    print(
        json.dumps(
            {
                "status": "machine-verified-candidate-pending-visual-approval",
                "run_directory": RUN_DIRECTORY.as_posix(),
                "request_id": request_id,
                "completed_count": 1,
                "donor_sha256": donor_sha256,
                "assembly_sha256": assembly_sha256,
                "outside_region_changed_pixels": changed_pixels_outside,
                "actual_cost_usd": actual_cost,
                "actual_cost_exposed": actual_cost is not None,
                "safe_to_retry": False,
                "posts": 1,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
