# World-map benchmark: `meta/muse-image` vs `qwen/qwen-image-3-pro`

Storage-only evidence. The reusable pipeline code lives in `qwen-image-pipeline`;
nothing in this directory is imported by it.

Measured 2026-08-31 against the OpenRouter Image API (`POST /api/v1/images`).

## The task

Take a WorldTimeZone.com time-zone map (`reference/worldtimezone-source.png`,
4272x2175) and: strip every time label and chrome, give each **country** one flat
colour from the source palette, and place capital cities accurately — without
losing geographic accuracy or the flat 1-pixel pixel-art rendering.

## Verdict

| | `meta/muse-image` | `qwen/qwen-image-3-pro` |
|---|---|---|
| Completed the edit | yes | **no** |
| Failure | — | `HTTP 400 Alibaba blocked this request through content moderation` |
| Time to that outcome | 42 s | 253 s |
| Cost | $0.01 / image | $0 (rejected) |

Qwen Image 3 Pro is **disqualified for political-map content**. Its only
OpenRouter endpoint is Alibaba, whose moderation rejects world maps with
national borders. This confirms the standing finding from 2026-08-30 and is not
a prompt problem — the request never reached generation.

`meta/muse-image` produced an accurate result in three short targeted passes.

## Per-country palette

Sampled from the source image (`#RRGGBB`, share of source pixels):

`#FF0024` red 5.41% · `#009DFF` blue 6.14% · `#00D200` green 1.59% ·
`#FFCC00` amber 0.31% · `#BEFF8F` pale green 0.16% · `#75FFC8` mint 0.08% ·
`#51B8FF` sky 0.08% · `#D9DAFF` lavender 0.95% · `#FF8548` orange 0.06%

## What each pass achieved

| Run | Prompt | s | $ | Result |
|---|---|---|---|---|
| `01-muse-size` | `recolour-v1` (all three asks at once) | 42.1 | 0.01 | Labels, DST badges, graticule, date box and attribution all removed. Geography and pixel style preserved exactly. **But** kept time-zone banding (Canada, Brazil, Australia still striped) and placed **no** capitals. |
| `02-qwen-2k` | same | 253.3 | — | Moderation block. |
| `05-muse-pass2` | `pass2-per-country` | 18.1 | 0.01 | One flat colour per country, banding gone, all nine palette colours used, adjacent countries differ, grey chrome removed. |
| `06-muse-pass3` | `pass3-capitals` | 40.8 | 0.01 | ~36 capitals placed at true positions with dots and white-haloed labels; crowded ones correctly skipped. |

**A single prompt carrying three instructions loses two of them.** Short,
single-purpose passes chained over the previous output is what works — the same
lesson recorded for `openai/gpt-image-2` on 2026-08-30.

## Known faults in the final image

- Alaska carries Canada's pale green instead of the United States' orange
  (introduced in pass 2, not corrected in pass 3).
- India and Pakistan both pale green — one adjacency violation.
- Hanoi omitted; Antarctica absent (also absent from the source).
- Capital labels are anti-aliased sans-serif, not pixel-crisp, so they read
  slightly softer than the 1-pixel map linework.

## Measured `meta/muse-image` request contract

Its `/api/v1/images/models/meta/muse-image/endpoints` returns an empty
`endpoints` array, so the supported parameters below were established by probe,
not documentation. **OpenRouter validates these fields against a shared Zod
schema and accepts them; Muse then ignores most of them.** Silent, not an error.

| Field | Behaviour | Evidence |
|---|---|---|
| `prompt` | honored | — |
| `n` | **honored** | `n=2` returned 2 images, cost doubled to $0.02 |
| `size: "WxH"` | **honored**, snapped to a grid | `1920x1080` → `2048x1152` (exact 16:9); `2048x1024` → `2240x1120` (exact 2:1) |
| `aspect_ratio` | **accepted but collapsed to 3 buckets** | `1:1` → 1600x1600; `16:9`, `4:3`, `2:1`, `21:9` → **all** 1920x1280 (3:2); `9:16`, `3:4` → 1280x1920 |
| `resolution` | **ignored** | `1K` and `2K` both returned 1920x1280 |
| `seed` | **accepted but ignored** | same seed twice → different sha256 |
| `width` / `height` | **ignored** | returned 1600x1600 |
| `input_references` | honored | data-URL reference drove every pass |

Two consequences for the pipeline:

1. `aspect_ratio` is the wrong control for Muse. Asking for `16:9` silently
   yields 3:2. **`size` is the only accurate framing control**, and it must be
   sent instead of, not alongside, `aspect_ratio`.
2. Muse is **not reproducible**. Seeded reruns differ, so a Muse run can be
   recorded but never replayed. Qwen's `seed` is real; Muse's is decoration.

An invalid `aspect_ratio` returns a `ZodError` listing the shared enum
(`1:1 1:2 1:4 1:8 2:1 2:3 3:2 3:4 4:1 4:3 4:5 …`) — that enum is OpenRouter's,
and passing it says nothing about whether the model honors the value.

## Timeouts

The pipeline's 180 s default is too short and the failure mode costs money: the
client gives up, the provider finishes and bills anyway ($3.36 lost on
2026-08-30, recorded in `qwen_ui_pipeline/providers/openrouter.py`). Qwen took
253 s here just to return a *rejection*. Muse's slowest edit was 42 s.
**600 s is the right ceiling** — well clear of the worst observed case, without
the 30-minute hang that motivated TCP keepalive.

## Reproducing

```bash
python3 scripts/bench_image_model.py --timeout 600 \
  --model meta/muse-image --prompt-file benchmarks/world-map/prompts/pass2-per-country.txt \
  --reference benchmarks/world-map/runs/01-muse-size/image-01.png \
  --size 2048x1024 --out benchmarks/world-map/runs/NN-label
```

`OPENROUTER_API_KEY` is injected per command by the `access-bitwarden-secrets`
runner. Reference bytes and base64 payloads never enter the recorded JSON.

## Spend

$0.19 total: $0.16 of contract probes, $0.03 of map passes. Within the standing
under-$5 OpenRouter allowance.
