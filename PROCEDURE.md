# Procedure qualification

Issue: [#1](https://github.com/Reid-Surmeier/qwen-pipeline-experiments/issues/1)

## Purpose

Prove the normal path with one Qwen Image study and one Seedance study. This is application evidence, not a second reusable tool.

## Rules that decide the path

- OpenRouter is the only paid provider.
- A declared reference is not evidence until its file and SHA-256 match and the exact reference appears in the provider payload.
- Qwen may redraw pixels. When authoritative pixels already exist, its output is a donor; deterministic Assembly produces the candidate.
- A paid submission is attempted once. A timeout or unclear response means `possibly_spent`; reconcile that exact request or job, never resubmit it.
- Machine checks may declare a verified candidate. Only the owner can approve its visual quality.

## Fresh-agent task

1. Confirm the tool lock resolves to the pinned commit.
2. Run `node scripts/preflight.mjs requests/known-bad-seedance.json`. It must fail before any paid request because no video reaches the payload.
3. Run the same preflight for each live request. Do not submit if it fails.
4. For Qwen, request exactly one 1K image from `qwen/qwen-image-3-pro`. Save the raw result as a donor, then copy only the declared 512 by 512 edit region over the authoritative 1024 by 1024 reference. Verify that every pixel outside the region is unchanged.
5. For Seedance, request exactly one 4-second, 480p, silent video from `bytedance/seedance-2.0-mini`. The provider payload must contain the hash-locked motion-reference URL from the request.
6. Keep the additive files listed by the Project Contract. Never overwrite or reuse a paid Run directory.
7. Stop for the owner only after machine evidence is complete, or when a genuine subjective choice is required.

## Paid-action reservation

Immediately before the one submission, append an event with:

- UTC timestamp;
- request SHA-256;
- provider and exact model;
- estimated cost;
- `billing_state: possibly_spent`;
- `safe_to_retry: false`.

The request returning an error does not undo that reservation. If Seedance returns a job ID, polling that ID is reconciliation and is allowed; submitting another job is not.
