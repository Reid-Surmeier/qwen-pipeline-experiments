#!/usr/bin/env python3.12
"""Run the one-shot Seedance probe with the corrected 720x720 reference."""

from pathlib import Path

import run_seedance_video_study_003_once as probe

probe.RUN_ID = "seedance-video-study-004-20260830T202300Z"
probe.RUN = Path("artifacts/qwen-pipeline/runs") / probe.RUN_ID
probe.REFERENCE_PATH = Path("references/seedance-motion-reference-720.mp4")
probe.REFERENCE_URL = (
    "https://reid-surmeier.github.io/qwen-pipeline-experiments/"
    "references/seedance-motion-reference-720.mp4"
)
probe.EXPECTED_REFERENCE_SHA256 = (
    "8a0931d2876579dbb17e2ab3680d379516a59d9ec116a99f6a476964770f97a7"
)
probe.EXPECTED_APPLICATION_COMMIT = "60471d089a3e4d94b876a367d6ec0b4f5a662e84"
probe.QUESTION = (
    "Does Mini reference-to-video accept the same motion authority after deterministic "
    "upscaling from 480x480 to 720x720, above the provider's 407696-pixel minimum?"
)
probe.SINGLE_CHANGED_VARIABLE = (
    "reference video dimensions: 480x480 (230400 pixels) to 720x720 (518400 pixels)"
)
probe.SOURCE_RUNS = ["seedance-video-study-003-20260830T201900Z"]


if __name__ == "__main__":
    raise SystemExit(probe.main())
