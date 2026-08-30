#!/usr/bin/env python3.12
"""Run one non-retryable Seedance HTTPS video/mp4 reference probe."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import run_seedance_video_study_002_once as base

RUN_ID = "seedance-video-study-003-20260830T201900Z"
RUN = Path("artifacts/qwen-pipeline/runs") / RUN_ID
REFERENCE_URL = (
    "https://reid-surmeier.github.io/qwen-pipeline-experiments/"
    "references/seedance-motion-reference.mp4"
)
EXPECTED_APPLICATION_COMMIT = "162c0ab830e32a071faba9374ccda32047491dd5"


def fail(
    *, started_at: str, request_sha256: str, reference_sha256: str, error: dict[str, Any]
) -> int:
    base.RUN_ID = RUN_ID
    base.RUN = RUN
    return base.finish_failure(
        started_at=started_at,
        request_sha256=request_sha256,
        reference_sha256=reference_sha256,
        error=error,
    )


def main() -> int:
    os.umask(0o077)
    base.RUN_ID = RUN_ID
    base.RUN = RUN
    if RUN.exists():
        raise RuntimeError(f"refusing a second attempt: {RUN} already exists")
    if base.git_head(Path.cwd()) != EXPECTED_APPLICATION_COMMIT:
        raise RuntimeError("application commit changed before the one-shot probe")
    if base.git_head(base.TOOL) != base.EXPECTED_TOOL_COMMIT:
        raise RuntimeError("structured-error client is not at the reviewed commit")

    reference_bytes = base.REFERENCE.read_bytes()
    reference_sha256 = base.sha256_bytes(reference_bytes)
    if reference_sha256 != base.EXPECTED_REFERENCE_SHA256:
        raise RuntimeError("local video reference changed")
    remote = httpx.get(REFERENCE_URL, follow_redirects=True, timeout=60)
    remote.raise_for_status()
    remote_content_type = remote.headers.get("content-type", "").split(";", 1)[0].lower()
    if remote_content_type != "video/mp4":
        raise RuntimeError(f"public reference MIME is {remote_content_type!r}, not video/mp4")
    if base.sha256_bytes(remote.content) != reference_sha256:
        raise RuntimeError("public reference bytes differ from the local authority")

    models_response = httpx.get("https://openrouter.ai/api/v1/videos/models", timeout=30)
    models_response.raise_for_status()
    profile = next(row for row in models_response.json()["data"] if row["id"] == base.MODEL)
    if profile["canonical_slug"] != "bytedance/seedance-2.0-mini-20260811":
        raise RuntimeError("canonical Mini model changed")
    if 4 not in profile["supported_durations"] or "480x480" not in profile["supported_sizes"]:
        raise RuntimeError("live Mini capabilities no longer support the probe")
    video_tokens = Decimal(480 * 480 * 4 * 24) / Decimal(1024)
    estimate = (video_tokens * Decimal(profile["pricing_skus"]["video_tokens_with_video_input"])).quantize(
        Decimal("0.0001")
    )
    if estimate != base.EXPECTED_ESTIMATE:
        raise RuntimeError(f"live estimate changed to {estimate}")

    request = {
        "model": base.MODEL,
        "prompt": base.PROMPT,
        "duration": 4,
        "size": "480x480",
        "generate_audio": False,
        "seed": 1301,
        "input_references": [
            {"type": "video_url", "video_url": {"url": REFERENCE_URL}}
        ],
    }
    request_sha256 = base.canonical_sha256(request)
    RUN.mkdir(parents=True)
    base.write_json(RUN / "request.json", request)
    base.write_json(RUN / "capabilities.json", {"fetched_at": base.now(), "model": profile})
    base.write_json(
        RUN / "reference-proof.json",
        {
            "checked_at": base.now(),
            "local_path": str(base.REFERENCE),
            "declared_url": REFERENCE_URL,
            "provider_payload_url": REFERENCE_URL,
            "http_status": remote.status_code,
            "content_type": remote_content_type,
            "content_length": len(remote.content),
            "local_sha256": reference_sha256,
            "remote_sha256": base.sha256_bytes(remote.content),
            "remote_matches_local": True,
        },
    )
    base.write_json(
        RUN / "plan.json",
        {
            "question": (
                "Does the same HTTPS reference succeed when served as video/mp4 instead of "
                "application/octet-stream?"
            ),
            "single_changed_variable": (
                "HTTPS reference host and response MIME: raw GitHub octet-stream to "
                "GitHub Pages video/mp4"
            ),
            "source_runs": [
                "seedance-video-study-001-20260830T195347Z",
                "seedance-video-study-002-20260830T201500Z",
            ],
            "model": base.MODEL,
            "canonical_slug": profile["canonical_slug"],
            "provider_request_sha256": request_sha256,
            "reference_sha256": reference_sha256,
            "estimated_cost_usd": str(estimate),
            "acknowledged_cost_usd": str(base.EXPECTED_ESTIMATE),
            "requested_count": 1,
            "paid_submission_performed": False,
            "safe_to_retry": False,
        },
    )
    base.write_json(
        RUN / "provenance.json",
        {
            "issue": "https://github.com/Reid-Surmeier/qwen-image-pipeline/issues/15",
            "application_repository": "https://github.com/Reid-Surmeier/qwen-pipeline-experiments",
            "application_commit": EXPECTED_APPLICATION_COMMIT,
            "tool_repository": "https://github.com/Reid-Surmeier/qwen-image-pipeline",
            "tool_commit": base.EXPECTED_TOOL_COMMIT,
            "reference_path": str(base.REFERENCE),
            "reference_url": REFERENCE_URL,
            "reference_sha256": reference_sha256,
            "reference_mime": remote_content_type,
            "provider_request_sha256": request_sha256,
        },
    )
    base.event(
        "paid_action_reserved",
        provider="openrouter",
        model=base.MODEL,
        requested_count=1,
        estimated_cost_usd=str(estimate),
        provider_request_sha256=request_sha256,
        safe_to_retry=False,
    )

    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY was not injected")
    sys.path.insert(0, str(base.TOOL / "seedance" / "src"))
    from seedance_icons.openrouter import OpenRouterHTTPError, OpenRouterVideoClient

    plan = json.loads((RUN / "plan.json").read_text())
    plan.update(
        paid_submission_performed=True,
        submission_status="submitting",
        billing_status="possibly_spent",
    )
    base.write_json(RUN / "plan.json", plan)
    started_at = base.now()
    base.event("submission_started", provider_request_sha256=request_sha256, safe_to_retry=False)
    client = OpenRouterVideoClient(key)
    try:
        try:
            submitted = client.submit(request)
        except OpenRouterHTTPError as caught:
            return fail(
                started_at=started_at,
                request_sha256=request_sha256,
                reference_sha256=reference_sha256,
                error=caught.to_record(),
            )
        except Exception as caught:  # noqa: BLE001 - preserve an ambiguous POST outcome
            return fail(
                started_at=started_at,
                request_sha256=request_sha256,
                reference_sha256=reference_sha256,
                error={
                    "error_class": type(caught).__name__,
                    "message": base.sanitize(str(caught), key),
                },
            )

        submitted = base.sanitize(submitted, key)
        if not isinstance(submitted, dict) or not base.job_id(submitted):
            raise RuntimeError("accepted response did not contain a job ID")
        identifier = base.job_id(submitted)
        base.write_json(RUN / "job.json", submitted)
        base.event("submission_accepted", job_id=identifier, safe_to_retry=False)

        deadline = time.monotonic() + 1800
        terminal: dict[str, Any] | None = None
        last_status = ""
        while time.monotonic() < deadline:
            polled = base.sanitize(client.status(identifier), key)
            if not isinstance(polled, dict):
                raise TypeError("poll response was not an object")
            status = base.provider_status(polled)
            if status != last_status:
                base.event(
                    "job_status", job_id=identifier, provider_status=status, safe_to_retry=False
                )
                print(json.dumps({"job_id": identifier, "status": status}), flush=True)
                last_status = status
            if status in {"completed", "failed", "cancelled", "expired"}:
                terminal = polled
                break
            time.sleep(10)
        if terminal is None:
            raise TimeoutError(f"poll timeout for existing job {identifier}")
        base.write_json(RUN / "completed-job.json", terminal)
        base.write_json(
            RUN / "provider-response.json",
            {
                "submitted_at": started_at,
                "received_at": base.now(),
                "submission_response": submitted,
                "terminal_response": terminal,
            },
        )
        cost = base.actual_cost(terminal)
        if base.provider_status(terminal) != "completed":
            return fail(
                started_at=started_at,
                request_sha256=request_sha256,
                reference_sha256=reference_sha256,
                error={
                    "error_class": "OpenRouterTerminalJobError",
                    "provider_status": base.provider_status(terminal),
                    "provider_error": terminal.get("error"),
                    "actual_cost_usd": cost,
                },
            )

        output = RUN / "outputs" / "output.mp4"
        output_sha256 = client.download(identifier, output)
        media = json.loads(
            subprocess.check_output(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration,size,format_name:stream=codec_name,codec_type,width,height,r_frame_rate",
                    "-of",
                    "json",
                    str(output),
                ],
                text=True,
            )
        )
        base.write_json(RUN / "checks.json", {"ffprobe": media, "output_sha256": output_sha256})
        base.write_json(
            RUN / "run-record.json",
            {
                "run_id": RUN_ID,
                "status": "generated-machine-checked",
                "provider": "openrouter",
                "model": base.MODEL,
                "job_id": identifier,
                "requested_count": 1,
                "completed_count": 1,
                "provider_request_sha256": request_sha256,
                "reference_sha256": reference_sha256,
                "output_path": str(output),
                "output_sha256": output_sha256,
                "estimated_cost_usd": str(estimate),
                "actual_cost_usd": cost,
                "safe_to_retry": False,
                "completed_at": base.now(),
            },
        )
        plan.update(submission_status="accepted", actual_cost_usd=cost)
        base.write_json(RUN / "plan.json", plan)
        base.event(
            "run_completed",
            job_id=identifier,
            completed_count=1,
            output_sha256=output_sha256,
            actual_cost_usd=cost,
            safe_to_retry=False,
        )
        print(json.dumps({"run": str(RUN), "job_id": identifier, "actual_cost_usd": cost}))
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
