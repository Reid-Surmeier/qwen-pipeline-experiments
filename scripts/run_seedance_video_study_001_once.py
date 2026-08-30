#!/usr/bin/env python3.12
"""Create, submit, reconcile, and verify one authorized Seedance study Run.

This runner is intentionally bound to one additive Run directory. It has one
provider POST and no submission retry path. Polling and downloading use only
the job ID returned by that POST.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

RUN_DIRECTORY_ID = "seedance-video-study-001-20260830T195347Z"
RUN_DIRECTORY = Path("artifacts/qwen-pipeline/runs") / RUN_DIRECTORY_ID
SOURCE_REQUEST_PATH = Path("requests/seedance-video-study.json")
REFERENCE_PATH = Path("references/seedance-motion-reference.mp4")
TOOL_REPOSITORY = Path("/home/reidsurmeier/qwen-image-pipeline")
TOOL_SEEDANCE_SOURCE = TOOL_REPOSITORY / "seedance" / "src"

EXPECTED_TOOL_COMMIT = "b2e4f594f6fb23e0dcc4e2a3395d492585a35c9b"
EXPECTED_APPLICATION_COMMIT = "34175a20aa72252d87265fa9435c76ce323b821b"
EXPECTED_SOURCE_CANONICAL_SHA256 = (
    "48fc30a62ceb881c767355e7b965812aab810e002c6abb8c6d7a0140721f2547"
)
EXPECTED_PROVIDER_CANONICAL_SHA256 = (
    "7c9373e8f671c9c3b83770fc6fe16b31079878c93618345f77663f248a3fd69e"
)
EXPECTED_REFERENCE_SHA256 = (
    "0f4ecfc3771d5e3e43709d7aaec7be7fac08b29f13c95e91eebe9b77b57f9ba2"
)
EXPECTED_ESTIMATE_USD = "0.0454"
EXPECTED_MODEL = "bytedance/seedance-2.0-mini"
POLL_INTERVAL_SECONDS = 10
POLL_TIMEOUT_SECONDS = 1800


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


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_exclusive(path: Path, payload: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)
    fsync_directory(path.parent)


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
    fsync_directory(RUN_DIRECTORY)


def sanitize_error_message(message: str) -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "")
    return message.replace(key, "[redacted]") if key else message


def sanitize_provider_record(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: sanitize_provider_record(item)
            for key, item in value.items()
            if key.lower() not in {"authorization", "api_key", "token"}
        }
    if isinstance(value, list):
        return [sanitize_provider_record(item) for item in value]
    if isinstance(value, str):
        return sanitize_error_message(value)
    return value


def extract_status(job: dict[str, Any]) -> str:
    nested = job.get("data")
    return str(job.get("status") or (nested.get("status") if isinstance(nested, dict) else ""))


def extract_cost(job: dict[str, Any]) -> object | None:
    usage = job.get("usage")
    if isinstance(usage, dict):
        return usage.get("cost")
    nested = job.get("data")
    if isinstance(nested, dict) and isinstance(nested.get("usage"), dict):
        return nested["usage"].get("cost")
    return None


def job_id_from_response(job: dict[str, Any]) -> str | None:
    value = job.get("id")
    if isinstance(value, str) and value:
        return value
    nested = job.get("data")
    if isinstance(nested, dict) and isinstance(nested.get("id"), str):
        return nested["id"]
    return None


def reference_proof(source_request: dict[str, Any]) -> dict[str, object]:
    references = source_request.get("reference_inputs")
    provider_references = source_request.get("provider_payload", {}).get("input_references")
    if not isinstance(references, list) or len(references) != 1:
        raise RuntimeError("source request does not declare exactly one reference")
    if not isinstance(provider_references, list) or len(provider_references) != 1:
        raise RuntimeError("provider payload does not contain exactly one input reference")
    declared = references[0]
    provider_reference = provider_references[0]
    if declared.get("kind") != "video" or provider_reference.get("type") != "video_url":
        raise RuntimeError("declared and provider references are not both video references")
    if declared.get("path") != REFERENCE_PATH.as_posix():
        raise RuntimeError("declared reference path changed")
    declared_url = declared.get("url")
    provider_url = provider_reference.get("video_url", {}).get("url")
    local_hash = file_sha256(REFERENCE_PATH)
    if local_hash != declared.get("sha256") or local_hash != EXPECTED_REFERENCE_SHA256:
        raise RuntimeError("local reference hash does not match the declaration")
    if not isinstance(declared_url, str) or declared_url != provider_url:
        raise RuntimeError("declared reference URL does not exactly match provider payload")
    remote_response = httpx.get(declared_url, follow_redirects=True, timeout=60)
    remote_response.raise_for_status()
    remote_hash = hashlib.sha256(remote_response.content).hexdigest()
    if remote_hash != local_hash:
        raise RuntimeError("remote provider reference bytes do not match local authority")
    return {
        "checked_at": utc_now(),
        "declared_path": declared["path"],
        "declared_sha256": declared["sha256"],
        "local_sha256": local_hash,
        "path_hash_match": True,
        "declared_url": declared_url,
        "provider_payload_url": provider_url,
        "exact_url_match": True,
        "remote_http_status": remote_response.status_code,
        "remote_sha256": remote_hash,
        "remote_matches_local": True,
        "provider_reference_type": provider_reference["type"],
    }


def ffprobe_report(path: Path) -> dict[str, Any]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration,size,format_name:stream=index,codec_name,codec_type,width,height,r_frame_rate,avg_frame_rate",
        "-of",
        "json",
        str(path),
    ]
    return json.loads(subprocess.check_output(command, text=True))


def create_contact_sheet(video: Path, destination: Path) -> None:
    command = [
        "ffmpeg",
        "-v",
        "error",
        "-i",
        str(video),
        "-vf",
        "fps=1,scale=240:240:force_original_aspect_ratio=decrease,pad=240:240:(ow-iw)/2:(oh-ih)/2,tile=4x1",
        "-frames:v",
        "1",
        str(destination),
    ]
    subprocess.run(command, check=True)
    with destination.open("rb") as stream:
        os.fsync(stream.fileno())
    fsync_directory(destination.parent)


def make_base_checks(proof: dict[str, object]) -> list[dict[str, object]]:
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
            "name": "seedance-live-request-preflight",
            "command": "node scripts/preflight.mjs requests/seedance-video-study.json",
            "result": "passed",
            "exit_code": 0,
            "safe_to_spend": True,
            "request_sha256": EXPECTED_SOURCE_CANONICAL_SHA256,
        },
        {
            "name": "focused-node-tests",
            "command": "node --test tests/preflight.test.mjs",
            "result": "passed",
            "tests_passed": 1,
            "tests_failed": 0,
        },
        {
            "name": "pinned-openrouter-client-tests",
            "command": "PYTHONPATH=/home/reidsurmeier/qwen-image-pipeline/seedance/src python3.12 -m pytest /home/reidsurmeier/qwen-image-pipeline/seedance/tests/test_openrouter.py -q",
            "result": "passed",
            "tests_passed": 3,
            "tests_failed": 0,
        },
        {
            "name": "tool-lock",
            "result": "passed",
            "expected_commit": EXPECTED_TOOL_COMMIT,
            "resolved_commit": EXPECTED_TOOL_COMMIT,
        },
        {
            "name": "reference-and-payload-proof",
            "result": "passed",
            **proof,
        },
        {
            "name": "frozen-provider-request",
            "result": "passed",
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
        for path in RUN_DIRECTORY.rglob("*")
        if path.is_file() and path.name != "artifact-manifest.sha256"
    )
    payload = "".join(f"{file_sha256(path)}  {path.as_posix()}\n" for path in paths)
    write_exclusive(RUN_DIRECTORY / "artifact-manifest.sha256", payload.encode("utf-8"))


def write_terminal_records(
    *,
    source_request: dict[str, Any],
    proof: dict[str, object],
    created_at: str,
    started_at: str,
    completed_at: str,
    status: str,
    job_id: str | None,
    completed_count: int,
    actual_cost_usd: object | None,
    provider_status: str,
    media: dict[str, Any] | None,
    output_sha256: str | None,
    failure: dict[str, object] | None,
) -> None:
    checks = make_base_checks(proof)
    if media is None:
        checks.append(
            {
                "name": "output-media",
                "result": "not-run",
                "reason": "No completed output was available for ffprobe.",
            }
        )
    else:
        streams = media.get("streams", [])
        video_streams = [stream for stream in streams if stream.get("codec_type") == "video"]
        audio_streams = [stream for stream in streams if stream.get("codec_type") == "audio"]
        video_stream = video_streams[0] if len(video_streams) == 1 else {}
        duration = float(media.get("format", {}).get("duration", "0"))
        dimensions = [video_stream.get("width"), video_stream.get("height")]
        checks.extend(
            [
                {
                    "name": "output-media-readable",
                    "result": "passed" if len(video_streams) == 1 else "failed",
                    "video_stream_count": len(video_streams),
                    "codec": video_stream.get("codec_name"),
                },
                {
                    "name": "output-duration",
                    "result": "passed" if abs(duration - 4.0) <= 0.35 else "failed",
                    "requested_seconds": 4,
                    "actual_seconds": duration,
                    "tolerance_seconds": 0.35,
                },
                {
                    "name": "output-dimensions",
                    "result": "passed" if dimensions == [480, 480] else "failed",
                    "requested": [480, 480],
                    "actual": dimensions,
                    "square": dimensions[0] == dimensions[1],
                },
                {
                    "name": "output-audio",
                    "result": "passed" if not audio_streams else "failed",
                    "requested_audio": False,
                    "audio_stream_count": len(audio_streams),
                },
                {
                    "name": "contact-sheet",
                    "result": "passed",
                    "path": (RUN_DIRECTORY / "contact-sheet.png").as_posix(),
                    "sha256": file_sha256(RUN_DIRECTORY / "contact-sheet.png"),
                    "visual_approval_performed": False,
                },
            ]
        )
    write_json_exclusive(
        RUN_DIRECTORY / "checks.json", {"checked_at": completed_at, "checks": checks}
    )
    output_record = None
    if output_sha256 is not None:
        output_record = {
            "path": (RUN_DIRECTORY / "output.mp4").as_posix(),
            "sha256": output_sha256,
            "ffprobe_path": (RUN_DIRECTORY / "ffprobe.json").as_posix(),
            "contact_sheet_path": (RUN_DIRECTORY / "contact-sheet.png").as_posix(),
        }
    provenance = {
        "recorded_at": completed_at,
        "issue": "https://github.com/Reid-Surmeier/qwen-pipeline-experiments/issues/1",
        "application_repository": "https://github.com/Reid-Surmeier/qwen-pipeline-experiments",
        "application_commit": EXPECTED_APPLICATION_COMMIT,
        "application_branch": "prototype/fresh-agent-proof",
        "tool_repository": "https://github.com/Reid-Surmeier/qwen-image-pipeline",
        "tool_commit": EXPECTED_TOOL_COMMIT,
        "tool_client": "seedance/src/seedance_icons/openrouter.py:OpenRouterVideoClient",
        "provider": "openrouter",
        "endpoint": "https://openrouter.ai/api/v1/videos",
        "model": EXPECTED_MODEL,
        "requested_count": 1,
        "completed_count": completed_count,
        "duration_seconds": source_request["duration"],
        "size": source_request["size"],
        "generate_audio": source_request["provider_payload"]["generate_audio"],
        "seed": source_request["provider_payload"]["seed"],
        "estimate_usd": EXPECTED_ESTIMATE_USD,
        "actual_cost_usd": actual_cost_usd,
        "actual_cost_exposed": actual_cost_usd is not None,
        "billing_state": "spent" if completed_count else "possibly_spent",
        "safe_to_retry": False,
        "job_id": job_id,
        "reference_proof": proof,
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
        "output": output_record,
        "failure": failure,
        "visual_approval": {
            "decision": "pending",
            "performed": False,
            "reason": "Machine evidence and a preview were produced; subjective approval is owner-only.",
        },
    }
    write_json_exclusive(RUN_DIRECTORY / "provenance.json", provenance)
    write_json_exclusive(
        RUN_DIRECTORY / "outcome.json",
        {
            "recorded_at": completed_at,
            "status": status,
            "provider_status": provider_status,
            "attempts_submitted": 1,
            "retries": 0,
            "requested_count": 1,
            "completed_count": completed_count,
            "job_id": job_id,
            "estimate_usd": EXPECTED_ESTIMATE_USD,
            "actual_cost_usd": actual_cost_usd,
            "actual_cost_exposed": actual_cost_usd is not None,
            "billing_state": "spent" if completed_count else "possibly_spent",
            "safe_to_retry": False,
            "machine_verification_complete": media is not None,
            "visual_approval": "pending-owner-review",
        },
    )
    write_json_exclusive(
        RUN_DIRECTORY / "run-record.json",
        {
            "run_id": RUN_DIRECTORY_ID,
            "created_at": created_at,
            "submission_started_at": started_at,
            "completed_at": completed_at,
            "provider": "openrouter",
            "model": EXPECTED_MODEL,
            "provider_request_sha256": EXPECTED_PROVIDER_CANONICAL_SHA256,
            "attempts_submitted": 1,
            "completed_count": completed_count,
            "job_id": job_id,
            "estimated_cost_usd": EXPECTED_ESTIMATE_USD,
            "actual_cost_usd": actual_cost_usd,
            "billing_state": "spent" if completed_count else "possibly_spent",
            "safe_to_retry": False,
            "status": status,
        },
    )
    write_manifest()


def main() -> int:
    os.umask(0o077)
    application_head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if application_head != EXPECTED_APPLICATION_COMMIT:
        raise RuntimeError(f"application checkout changed: {application_head}")
    tool_head = subprocess.check_output(
        ["git", "-C", str(TOOL_REPOSITORY), "rev-parse", "HEAD"], text=True
    ).strip()
    if tool_head != EXPECTED_TOOL_COMMIT:
        raise RuntimeError(f"tool checkout is not pinned: {tool_head}")

    source_request = json.loads(SOURCE_REQUEST_PATH.read_text())
    provider_request = source_request.get("provider_payload")
    if canonical_sha256(source_request) != EXPECTED_SOURCE_CANONICAL_SHA256:
        raise RuntimeError("source request changed after preflight")
    if canonical_sha256(provider_request) != EXPECTED_PROVIDER_CANONICAL_SHA256:
        raise RuntimeError("provider payload changed after preflight")
    if source_request.get("provider") != "openrouter":
        raise RuntimeError("paid provider is not OpenRouter")
    if source_request.get("model") != EXPECTED_MODEL or provider_request.get("model") != EXPECTED_MODEL:
        raise RuntimeError("model differs from the pinned Seedance route")
    if source_request.get("requested_count") != 1:
        raise RuntimeError("request count is not exactly one")
    if source_request.get("estimated_cost_usd") != EXPECTED_ESTIMATE_USD:
        raise RuntimeError("estimated cost differs from the authorized decimal")

    proof = reference_proof(source_request)
    created_at = utc_now()
    RUN_DIRECTORY.mkdir(parents=True, exist_ok=False)
    fsync_directory(RUN_DIRECTORY.parent)
    write_json_exclusive(RUN_DIRECTORY / "source-request.json", source_request)
    write_json_exclusive(RUN_DIRECTORY / "request.json", provider_request)
    write_json_exclusive(RUN_DIRECTORY / "reference-payload-proof.json", proof)

    reservation = {
        "timestamp": utc_now(),
        "event": "paid_action_reserved",
        "authorization": "exactly one OpenRouter Seedance submission at USD 0.0454 estimate",
        "provider": "openrouter",
        "model": EXPECTED_MODEL,
        "requested_count": 1,
        "estimated_cost_usd": EXPECTED_ESTIMATE_USD,
        "source_request_sha256": EXPECTED_SOURCE_CANONICAL_SHA256,
        "provider_request_sha256": EXPECTED_PROVIDER_CANONICAL_SHA256,
        "billing_state": "possibly_spent",
        "safe_to_retry": False,
    }
    write_exclusive(
        RUN_DIRECTORY / "events.jsonl",
        (json.dumps(reservation, separators=(",", ":")) + "\n").encode("utf-8"),
    )

    started_at = utc_now()
    write_json_exclusive(
        RUN_DIRECTORY / "submission-attempt.json",
        {
            "attempt_id": RUN_DIRECTORY_ID,
            "created_at": started_at,
            "provider": "openrouter",
            "endpoint": "https://openrouter.ai/api/v1/videos",
            "model": EXPECTED_MODEL,
            "provider_request_sha256": EXPECTED_PROVIDER_CANONICAL_SHA256,
            "status": "submitting",
            "billing_state": "possibly_spent",
            "safe_to_retry": False,
        },
    )
    append_event(
        {
            "timestamp": started_at,
            "event": "submission_started",
            "provider_request_sha256": EXPECTED_PROVIDER_CANONICAL_SHA256,
            "billing_state": "possibly_spent",
            "safe_to_retry": False,
        }
    )

    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY was not injected")
    sys.path.insert(0, str(TOOL_SEEDANCE_SOURCE))
    from seedance_icons.openrouter import OpenRouterVideoClient

    client = OpenRouterVideoClient(key)
    job_id: str | None = None
    try:
        try:
            submitted_job = client.submit(provider_request)
        except Exception as error:  # noqa: BLE001 - persist any ambiguous POST outcome
            completed_at = utc_now()
            error_record = {
                "timestamp": completed_at,
                "error_type": type(error).__name__,
                "message": sanitize_error_message(str(error)),
                "classification": "ambiguous-submission-failure",
                "billing_state": "possibly_spent",
                "safe_to_retry": False,
            }
            write_json_exclusive(RUN_DIRECTORY / "provider-error.json", error_record)
            write_json_exclusive(
                RUN_DIRECTORY / "provider-response.json",
                {
                    "submitted_at": started_at,
                    "received_at": completed_at,
                    "submission_response": None,
                    "terminal_response": None,
                    "error": error_record,
                },
            )
            append_event({"event": "submission_ambiguous", **error_record})
            write_terminal_records(
                source_request=source_request,
                proof=proof,
                created_at=created_at,
                started_at=started_at,
                completed_at=completed_at,
                status="incomplete-ambiguous-submission",
                job_id=None,
                completed_count=0,
                actual_cost_usd=None,
                provider_status="ambiguous-submission-failure",
                media=None,
                output_sha256=None,
                failure=error_record,
            )
            print(json.dumps({"status": "ambiguous", "safe_to_retry": False}), flush=True)
            return 1

        submitted_job = sanitize_provider_record(submitted_job)
        if not isinstance(submitted_job, dict):
            raise TypeError("provider submission response was not a JSON object")
        job_id = job_id_from_response(submitted_job)
        if job_id is None:
            raise RuntimeError("provider submission response did not include a job ID")
        write_json_exclusive(RUN_DIRECTORY / "job.json", submitted_job)
        append_event(
            {
                "timestamp": utc_now(),
                "event": "submission_accepted",
                "job_id": job_id,
                "provider_status": extract_status(submitted_job),
                "billing_state": "possibly_spent",
                "safe_to_retry": False,
            }
        )
        print(json.dumps({"event": "submission_accepted", "job_id": job_id}), flush=True)

        deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
        terminal_job: dict[str, Any] | None = None
        last_status = ""
        while time.monotonic() < deadline:
            try:
                polled_job = sanitize_provider_record(client.status(job_id))
            except Exception as error:  # noqa: BLE001 - persist reconciliation errors
                append_event(
                    {
                        "timestamp": utc_now(),
                        "event": "poll_error",
                        "job_id": job_id,
                        "error_type": type(error).__name__,
                        "message": sanitize_error_message(str(error)),
                        "billing_state": "possibly_spent",
                        "safe_to_retry": False,
                    }
                )
                time.sleep(POLL_INTERVAL_SECONDS)
                continue
            if not isinstance(polled_job, dict):
                raise TypeError("provider poll response was not a JSON object")
            status = extract_status(polled_job)
            if status != last_status:
                append_event(
                    {
                        "timestamp": utc_now(),
                        "event": "job_status",
                        "job_id": job_id,
                        "provider_status": status,
                        "billing_state": "possibly_spent",
                        "safe_to_retry": False,
                    }
                )
                print(json.dumps({"event": "job_status", "job_id": job_id, "status": status}), flush=True)
                last_status = status
            if status == "completed":
                terminal_job = polled_job
                break
            if status in {"failed", "cancelled", "expired"}:
                terminal_job = polled_job
                break
            time.sleep(POLL_INTERVAL_SECONDS)
        if terminal_job is None:
            raise TimeoutError(f"poll timeout for existing OpenRouter job {job_id}")
        write_json_exclusive(RUN_DIRECTORY / "completed-job.json", terminal_job)
        terminal_status = extract_status(terminal_job)
        actual_cost = extract_cost(terminal_job)
        write_json_exclusive(
            RUN_DIRECTORY / "provider-response.json",
            {
                "submitted_at": started_at,
                "received_at": utc_now(),
                "submission_response": submitted_job,
                "terminal_response": terminal_job,
                "job_id": job_id,
                "actual_cost_usd": actual_cost,
                "actual_cost_exposed": actual_cost is not None,
                "safe_to_retry": False,
            },
        )
        if terminal_status != "completed":
            completed_at = utc_now()
            append_event(
                {
                    "timestamp": completed_at,
                    "event": "job_failed",
                    "job_id": job_id,
                    "provider_status": terminal_status,
                    "actual_cost_usd": actual_cost,
                    "billing_state": "possibly_spent",
                    "safe_to_retry": False,
                }
            )
            write_terminal_records(
                source_request=source_request,
                proof=proof,
                created_at=created_at,
                started_at=started_at,
                completed_at=completed_at,
                status="incomplete-provider-job-failure",
                job_id=job_id,
                completed_count=0,
                actual_cost_usd=actual_cost,
                provider_status=terminal_status,
                media=None,
                output_sha256=None,
                failure={"provider_status": terminal_status},
            )
            return 1

        output_path = RUN_DIRECTORY / "output.mp4"
        output_sha256 = client.download(job_id, output_path)
        with output_path.open("rb") as stream:
            os.fsync(stream.fileno())
        fsync_directory(RUN_DIRECTORY)
        if output_sha256 != file_sha256(output_path):
            raise RuntimeError("downloaded output hash changed after client write")
        media = ffprobe_report(output_path)
        write_json_exclusive(RUN_DIRECTORY / "ffprobe.json", media)
        create_contact_sheet(output_path, RUN_DIRECTORY / "contact-sheet.png")
        completed_at = utc_now()
        append_event(
            {
                "timestamp": completed_at,
                "event": "reconciliation_completed",
                "job_id": job_id,
                "provider_status": terminal_status,
                "completed_count": 1,
                "output_path": output_path.as_posix(),
                "output_sha256": output_sha256,
                "actual_cost_usd": actual_cost,
                "actual_cost_exposed": actual_cost is not None,
                "billing_state": "spent",
                "safe_to_retry": False,
            }
        )
        write_terminal_records(
            source_request=source_request,
            proof=proof,
            created_at=created_at,
            started_at=started_at,
            completed_at=completed_at,
            status="generated-machine-checked",
            job_id=job_id,
            completed_count=1,
            actual_cost_usd=actual_cost,
            provider_status=terminal_status,
            media=media,
            output_sha256=output_sha256,
            failure=None,
        )
        print(
            json.dumps(
                {
                    "status": "generated-machine-checked",
                    "job_id": job_id,
                    "completed_count": 1,
                    "output_sha256": output_sha256,
                    "actual_cost_usd": actual_cost,
                    "safe_to_retry": False,
                    "visual_approval": "pending-owner-review",
                }
            ),
            flush=True,
        )
        return 0
    except Exception as error:  # noqa: BLE001 - persist any post-submission failure
        completed_at = utc_now()
        error_record = {
            "timestamp": completed_at,
            "error_type": type(error).__name__,
            "message": sanitize_error_message(str(error)),
            "classification": "reconciliation-incomplete" if job_id else "ambiguous-submission-response",
            "job_id": job_id,
            "billing_state": "possibly_spent",
            "safe_to_retry": False,
        }
        write_json_exclusive(RUN_DIRECTORY / "provider-error.json", error_record)
        if not (RUN_DIRECTORY / "provider-response.json").exists():
            write_json_exclusive(
                RUN_DIRECTORY / "provider-response.json",
                {
                    "submitted_at": started_at,
                    "received_at": completed_at,
                    "job_id": job_id,
                    "error": error_record,
                    "safe_to_retry": False,
                },
            )
        append_event({"event": "reconciliation_incomplete", **error_record})
        write_terminal_records(
            source_request=source_request,
            proof=proof,
            created_at=created_at,
            started_at=started_at,
            completed_at=completed_at,
            status="incomplete-reconciliation",
            job_id=job_id,
            completed_count=0,
            actual_cost_usd=None,
            provider_status=error_record["classification"],
            media=None,
            output_sha256=None,
            failure=error_record,
        )
        print(json.dumps({"status": "incomplete", "job_id": job_id, "safe_to_retry": False}), flush=True)
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
