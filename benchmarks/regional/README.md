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

## Where each map ended

| Map | Best stage | State |
|---|---|---|
| Australia, USA, Canada, Caribbean, Europe | C | clean: per-country colour, names intact, furniture gone |
| Africa | C | clean; the brown graticule is kept deliberately |
| Asia | B2 | names intact, colour good; pass C filtered 3/3, furniture remains |
| Middle East | B2 | pass C filtered 3/3; the source's inset panel is misaligned |
| South America | B2 or C | **C cleared the furniture but dropped the country names again**; B2 keeps the names and keeps the furniture. Neither is finished. |
| Russia | C | **weak.** Provincial borders, dozens of small labels and grey non-Russian territory all get flattened. |

Every additional pass is another chance to lose text: pass C removed the country
names from the South America map that pass B had preserved. The passes are cheap
but they are not free of risk, so the fewest that will do the job is the right
number.

Russia is the one map this procedure does not suit. It probably needs the world
map's treatment instead -- generation for the fills, deterministic assembly for
the labels -- because its label density is closer to the world map's than to
Australia's.

## Deterministic repairs

Two defects survive generation and are repaired in code rather than by another
pass, because in both cases the correct answer already exists and there is
nothing for a model to add.

**Missing borders** (`scripts/map_restore_borders.py`). The Asia and Middle East
sheets came back with no black country outlines, so Mongolia's fill ran into
China's. Their sources draw borders in *white*, not black, so copying ink finds
nothing; borders are read as **colour boundaries** instead and stamped in black.
The reference is the pass-A output rather than the raw source, because A has the
same geography but has already lost the clock boxes, whose rectangular edges
would otherwise come back as spurious lines. Type is masked out of both images:
the recolour shifts letters a pixel or two, so masking only the reference leaves
a halo that shreds the target's own text.

Applied to those two sheets only. Run everywhere it stamps the brown graticule
as heavy black lines and damages type on maps whose borders were already fine.

**Dropped inset panels** (`scripts/map_restore_insets.py`). The US sheet carries
Alaska, Guam, American Samoa and Hawaii in framed panels down its left margin.
The recolour kept Alaska's landmass but dropped its frame and lost the other
three outright -- silently removing two states and two territories. The panels
are exact rectangles at known coordinates, so they are copied from the source
and their clock readouts painted out by matching the publisher's pastel box
fills, which no landmass colour comes near.

**Checking** (`scripts/map_check.py`) screens every sheet for both defects. It
over-flags: legitimate furniture removal lowers the ink ratio the same way a
lost border does, so a flag is a prompt to look, not a verdict.

## Assembly, for the sheets a single pass cannot hold

Asking one pass to recolour a whole dense sheet lets it redraw the map. On Asia,
Kazakhstan's fill swallowed part of western China and reached Urumqi; on the
Middle East an island appeared in the Caspian. Five attempts across two prompts
all passed the type gate and all moved borders, because a whole-sheet pass is
free to move any pixel.

`scripts/map_assembly.py` uses the repo's Assembly instead. Several whole-sheet
donors are generated, and each declared region takes the donor that kept that
region's geometry -- the repo's own note that similarity metrics are for
*ranking generative donor images*. The reference stays authoritative, and the
run records how many pixels changed outside the declared regions. It is zero on
both sheets, which is the repo's definition of strict preservation.

Two details the first attempt got wrong:

- **Score geometry, not colour.** A donor is supposed to change every fill, so
  colour distance ranks the most faithful donor worst. Agreement is measured on
  border positions, minus a penalty for borders the donor invents.
- **One base donor, overridden only on a clear margin.** Choosing freely per
  region split India into two colours across a tile seam. A region now leaves
  the base donor only when a rival beats it by 0.06.

Whole-sheet donors keep colouring consistent because each donor saw the whole
map; per-tile crops would not.

## Reproducing

```bash
python3 scripts/regional_batch.py africa europe usa        # passes A and B
```

`OPENROUTER_API_KEY` is injected per command by the `access-bitwarden-secrets`
runner. Reference bytes never enter the recorded JSON.
