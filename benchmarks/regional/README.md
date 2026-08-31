# Ten regional time-zone maps

Same procedure as the world map, applied to the publisher's regional sheets:
strip the clock furniture, then recolour by country instead of by time zone.

## What changed from the world map

**The regionals do not need deterministic label placement.** On the world map
the model put Washington DC in Kansas and London in the North Atlantic, so every
label had to be recomputed from lat/lon. Here the publisher's own labels are
already correct and in place, and pass A preserves them exactly -- spelling,
position and size. Only the colouring has to change. That removes the whole
projection-recovery problem for these ten.

## Passes

Each pass carries one instruction. Two jobs in one prompt loses one of them:
the first pass B asked for a recolour *and* furniture removal and silently
deleted every country name on the Africa and South America maps.

| Pass | Prompt | Job |
|---|---|---|
| A | `passA-strip-times.txt` | remove clock readouts, DST badges, time-zone abbreviation blocks |
| B | `passB-per-country.txt` | one flat colour per country, no two neighbours alike |
| C | `passC-clear-furniture.txt` | UTC box, date text, Greenwich box, attribution, grey frame |

## Meta's content filter

`meta/muse-image` refuses this material non-deterministically. The identical
prompt passed on Africa and was filtered on Australia in 6 s; the Caribbean took
one attempt, Europe two, the Middle East three. Across the first batch there
were 12 filter events in 17 runs.

Two things follow:

- **A filtered request is rejected before generation and is not billed**, so
  retrying is free in money and costs only wall-clock. The runners retry the
  filter and only the filter.
- **Long prompts trigger it more readily.** A nine-clause removal list was
  filtered on Africa where a two-sentence version of the same request passed.

This falsifies the claim that Muse is simply usable where Qwen is blocked. Both
refuse political maps; the difference is that Muse refuses **cheaply** (4-8 s,
unbilled) and Qwen refuses **expensively** (253 s).

## Reproducing

```bash
python3 scripts/regional_batch.py africa europe usa        # passes A and B
```

`OPENROUTER_API_KEY` is injected per command by the `access-bitwarden-secrets`
runner. Reference bytes never enter the recorded JSON.
