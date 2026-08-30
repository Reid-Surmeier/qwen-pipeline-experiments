#!/usr/bin/env python3.12
"""Run one non-retryable Seedance video-reference MIME probe.

The failed study-001 used a public URL whose response was
application/octet-stream. This additive probe keeps every generation variable
fixed and embeds the same hash-locked bytes as data:video/mp4. The full data
URL is never persisted.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx

RUN_ID = "seedance-video-study-002-20260830T201500Z"
RUN = Path("artifacts/qwen-pipeline/runs") / RUN_ID
REFERENCE = Path("references/seedance-motion-reference.mp4")
MODEL = "bytedance/seedance-2.0-mini"
EXPECTED_REFERENCE_SHA256 = (
    "0f4ecfc3771d5e3e43709d7aaec7be7fac08b29f13c95e91eebe9b77b57f9ba2"
)
EXPECTED_ESTIMATE = Decimal("0.0454")
EXPECTED_APPLICATION_COMMIT = "9ed4e006ad5d285b91abe79d0569bc1dfdb5b0b8"
TOOL = Path("/home/reidsurmeier/qwen-image-pipeline-worktrees/fix-seedance-http-error")
EXPECTED_TOOL_COMMIT = "3fcf67c2599953f5685b8c4b221f8e6fefdfc766"
PROMPT = (
    "Create one clean 4-second square motion study using the supplied video as the "
    "authoritative motion reference. Preserve the same centered dark rounded tile and "
    "cyan diamond identity on a fixed uniform green matte. Follow the reference's single "
    "clockwise turn, steady pace, locked camera, centered position, and return to the "
    "original pose. Keep the icon fully inside frame. Do not invent text, objects, "
    "particles, shadows, scenery, camera motion, or extra cycles."
)


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_sha256(value: object) -> str:
    return sha256_bytes(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    )


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def event(name: str, **fields: object) -> None:
    with (RUN / "events.jsonl").open("a") as stream:
        stream.write(json.dumps({"timestamp": now(), "event": name, **fields}) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def git_head(path: Path) -> str:
    return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()


def provider_status(value: dict[str, Any]) -> str:
    nested = value.get("data")
    return str(value.get("status") or (nested.get("status") if isinstance(nested, dict) else ""))


def job_id(value: dict[str, Any]) -> str | None:
    nested = value.get("data")
    candidate = value.get("id") or (nested.get("id") if isinstance(nested, dict) else None)
    return candidate if isinstance(candidate, str) and candidate else None


def actual_cost(value: dict[str, Any]) -> object | None:
    nested = value.get("data")
    usage = value.get("usage") or (nested.get("usage") if isinstance(nested, dict) else None)
    return usage.get("cost") if isinstance(usage, dict) else None


def sanitize(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return {
            name: sanitize(item, key)
            for name, item in value.items()
            if name.lower() not in {"authorization", "api_key", "token"}
        }
    if isinstance(value, list):
        return [sanitize(item, key) for item in value]
    if isinstance(value, str):
        return value.replace(key, "<REDACTED>") if key else value
    return value


def finish_failure(
    *,
    started_at: str,
    request_sha256: str,
    reference_sha256: str,
    error: dict[str, Any],
) -> int:
    completed_at = now()
    failure = {
        **error,
        "recorded_at": completed_at,
        "safe_to_retry": False,
        "billing_status": "possibly_spent",
    }
    write_json(RUN / "provider-error.json", failure)
    write_json(
        RUN / "provider-response.json",
        {
            "submitted_at": started_at,
            "received_at": completed_at,
            "submission_response": None,
            "terminal_response": None,
            "error": failure,
        },
    )
    write_json(
        RUN / "run-record.json",
        {
            "run_id": RUN_ID,
            "status": "failed-submission",
            "provider": "openrouter",
            "model": MODEL,
            "requested_count": 1,
            "completed_count": 0,
            "provider_request_sha256": request_sha256,
            "reference_sha256": reference_sha256,
            "estimated_cost_usd": str(EXPECTED_ESTIMATE),
            "actual_cost_usd": None,
            "billing_status": "possibly_spent",
            "safe_to_retry": False,
            "submission_started_at": started_at,
            "completed_at": completed_at,
        },
    )
    event("submission_failed", error_class=failure.get("error_class"), safe_to_retry=False)
    return 1


def main() -> int:
    os.umask(0o077)
    if RUN.exists():
        raise RuntimeError(f"refusing a second attempt: {RUN} already exists")
    if git_head(Path.cwd()) != EXPECTED_APPLICATION_COMMIT:
        raise RuntimeError("application commit changed before the one-shot probe")
    if git_head(TOOL) != EXPECTED_TOOL_COMMIT:
        raise RuntimeError("structured-error client is not at the reviewed commit")

    reference_bytes = REFERENCE.read_bytes()
    reference_sha256 = sha256_bytes(reference_bytes)
    if reference_sha256 != EXPECTED_REFERENCE_SHA256:
        raise RuntimeError("video reference changed")
    data_url = "data:video/mp4;base64," + base64.b64encode(reference_bytes).decode()
    data_url_sha256 = sha256_bytes(data_url.encode())

    models_response = httpx.get("https://openrouter.ai/api/v1/videos/models", timeout=30)
    models_response.raise_for_status()
    profile = next(row for row in models_response.json()["data"] if row["id"] == MODEL)
    if profile["canonical_slug"] != "bytedance/seedance-2.0-mini-20260811":
        raise RuntimeError("canonical Mini model changed")
    if 4 not in profile["supported_durations"] or "480x480" not in profile["supported_sizes"]:
        raise RuntimeError("live Mini capabilities no longer support the probe")
    video_tokens = Decimal(480 * 480 * 4 * 24) / Decimal(1024)
    estimate = (video_tokens * Decimal(profile["pricing_skus"]["video_tokens_with_video_input"])).quantize(
        Decimal("0.0001")
    )
    if estimate != EXPECTED_ESTIMATE:
        raise RuntimeError(f"live estimate changed to {estimate}")

    request = {
        "model": MODEL,
        "prompt": PROMPT,
        "duration": 4,
        "size": "480x480",
        "generate_audio": False,
        "seed": 1301,
        "input_references": [{"type": "video_url", "video_url": {"url": data_url}}],
    }
    request_sha256 = canonical_sha256(request)
    sanitized_request = {
        **request,
        "input_references": [
            {
                "type": "video_url",
                "video_url": {
                    "url": (
                        f"<data:video/mp4 sha256={data_url_sha256} "
                        f"source_sha256={reference_sha256} bytes={len(reference_bytes)}>"
                    )
                },
            }
        ],
    }

    RUN.mkdir(parents=True)
    write_json(RUN / "request.json", sanitized_request)
    write_json(RUN / "capabilities.json", {"fetched_at": now(), "model": profile})
    write_json(
        RUN / "plan.json",
        {
            "question": (
                "Did study-001 fail because its public reference declared "
                "application/octet-stream rather than video/mp4?"
            ),
            "single_changed_variable": "reference transport: HTTPS URL to data:video/mp4",
            "source_run": "seedance-video-study-001-20260830T195347Z",
            "model": MODEL,
            "canonical_slug": profile["canonical_slug"],
            "provider_request_sha256": request_sha256,
            "reference_sha256": reference_sha256,
            "estimated_cost_usd": str(estimate),
            "acknowledged_cost_usd": str(EXPECTED_ESTIMATE),
            "requested_count": 1,
            "paid_submission_performed": False,
            "safe_to_retry": False,
        },
    )
    write_json(
        RUN / "provenance.json",
        {
            "issue": "https://github.com/Reid-Surmeier/qwen-image-pipeline/issues/15",
            "application_repository": "https://github.com/Reid-Surmeier/qwen-pipeline-experiments",
            "application_commit": EXPECTED_APPLICATION_COMMIT,
            "tool_repository": "https://github.com/Reid-Surmeier/qwen-image-pipeline",
            "tool_commit": EXPECTED_TOOL_COMMIT,
            "reference_path": str(REFERENCE),
            "reference_sha256": reference_sha256,
            "reference_mime": "video/mp4",
            "provider_request_sha256": request_sha256,
            "full_data_url_persisted": False,
        },
    )
    event(
        "paid_action_reserved",
        provider="openrouter",
        model=MODEL,
        requested_count=1,
        estimated_cost_usd=str(estimate),
        provider_request_sha256=request_sha256,
        safe_to_retry=False,
    )

    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY was not injected")
    sys.path.insert(0, str(TOOL / "seedance" / "src"))
    from seedance_icons.openrouter import OpenRouterHTTPError, OpenRouterVideoClient

    plan = json.loads((RUN / "plan.json").read_text())
    plan.update(
        paid_submission_performed=True,
        submission_status="submitting",
        billing_status="possibly_spent",
    )
    write_json(RUN / "plan.json", plan)
    started_at = now()
    event("submission_started", provider_request_sha256=request_sha256, safe_to_retry=False)
    client = OpenRouterVideoClient(key)
    try:
        try:
            submitted = client.submit(request)
        except OpenRouterHTTPError as caught:
            return finish_failure(
                started_at=started_at,
                request_sha256=request_sha256,
                reference_sha256=reference_sha256,
                error=caught.to_record(),
            )
        except Exception as caught:  # noqa: BLE001 - preserve an ambiguous POST outcome
            return finish_failure(
                started_at=started_at,
                request_sha256=request_sha256,
                reference_sha256=reference_sha256,
                error={
                    "error_class": type(caught).__name__,
                    "message": sanitize(str(caught), key),
                },
            )

        submitted = sanitize(submitted, key)
        if not isinstance(submitted, dict) or not job_id(submitted):
            raise RuntimeError("accepted response did not contain a job ID")
        identifier = job_id(submitted)
        write_json(RUN / "job.json", submitted)
        event("submission_accepted", job_id=identifier, safe_to_retry=False)

        deadline = time.monotonic() + 1800
        terminal: dict[str, Any] | None = None
        while time.monotonic() < deadline:
            polled = sanitize(client.status(identifier), key)
            if not isinstance(polled, dict):
                raise TypeError("poll response was not an object")
            status = provider_status(polled)
            event("job_status", job_id=identifier, provider_status=status, safe_to_retry=False)
            if status in {"completed", "failed", "cancelled", "expired"}:
                terminal = polled
                break
            time.sleep(10)
        if terminal is None:
            raise TimeoutError(f"poll timeout for existing job {identifier}")
        write_json(RUN / "completed-job.json", terminal)
        write_json(
            RUN / "provider-response.json",
            {
                "submitted_at": started_at,
                "received_at": now(),
                "submission_response": submitted,
                "terminal_response": terminal,
            },
        )
        cost = actual_cost(terminal)
        if provider_status(terminal) != "completed":
            return finish_failure(
                started_at=started_at,
                request_sha256=request_sha256,
                reference_sha256=reference_sha256,
                error={
                    "error_class": "OpenRouterTerminalJobError",
                    "provider_status": provider_status(terminal),
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
        write_json(RUN / "checks.json", {"ffprobe": media, "output_sha256": output_sha256})
        write_json(
            RUN / "run-record.json",
            {
                "run_id": RUN_ID,
                "status": "generated-machine-checked",
                "provider": "openrouter",
                "model": MODEL,
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
                "completed_at": now(),
            },
        )
        plan.update(submission_status="accepted", actual_cost_usd=cost)
        write_json(RUN / "plan.json", plan)
        event(
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
