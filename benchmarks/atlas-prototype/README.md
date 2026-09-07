# Pixel Atlas — throwaway Godot prototype

Issue: https://github.com/Reid-Surmeier/qwen-pipeline-experiments/issues/5

Question: can the existing pink-and-cyan maps become one zoomable atlas without blank joins or changing their visual identity?

Run from the repository root:

```bash
benchmarks/atlas-prototype/run.sh
```

This imports and exports the Godot project and publishes its Web build through the existing Tailscale share tool. Open `godot/project.godot` in Godot 4.7.2 for the native project. No persistent state or production integration.

Drag to pan; scroll, pinch, double-click, or use +/− to zoom. A sparse set of named cities remains visible at world zoom. Major regional cities appear next, and smaller towns wait for close zoom. The original thin pixel lettering is restored. Each dot and its complete name appear and disappear together, with space between pairs. Zoom ranges from 1.0× viewport fit to 36× native scale. The minimum fills the viewport vertically, so narrow phones show a horizontal slice of the world that can be panned. Jump to a region with the selector. Full sheet displays the original regional artwork, including source insets. Europe contains 47 cities instead of 94. Home/Escape or World restores the overview.

## What the prototype established

Whole-sheet geographic warping bends text and produces mismatched coastlines. The working composition uses the existing world coastline as a shared surface and places original regional annotation groups over it. Their source pixels supply the artwork; geographic registration moves their centers without distorting the glyphs. This avoids invented rectangular geographic seams. City names stay readable, with smaller lettering at world scale. Explicit zoom tiers and pair-level collision checks control density. The original full sheets remain directly inspectable.

The world's cut-off Pacific edge needed new artwork. One Muse/OpenRouter pass completed New Zealand and cleared the seam; Assembly uses only that missing Pacific portion. New Zealand now uses that same donor at a corrected 154×193 native-pixel land extent, with the white stroke restored to eight pixels. The full regional sheets are preserved. Actual additional spend: $0.01, one output. Provider records and reference hashes are in `generation/`.

Registration is approximate because the source sheets have different projections and generated geography. This is an interaction and visual-design experiment, not a navigation dataset. No implementation decision has been promoted to production; the throwaway branch is the review artifact.

## Evidence and reproduction

`RESEARCH.md` records primary documentation and repository findings. `prepare_europe.py` captures the exact 47-city choice and edit mask; `prepare_atlas.py` produces the shared terrain and registered annotation data. These Assembly scripts reuse the original artifact paths in the experiments repository. The committed Godot assets run independently of those preparation inputs.

`node benchmarks/atlas-prototype/playtest.mjs` exercises actual desktop input through Playwright. `playtest-mobile.mjs` checks a 390×844 phone viewport using real CDP touch events. Both reuse the already installed Playwright on this host. `verify_assets.py` checks original pixels, badges, palette, generation count, successful playtest records, and hosted-file hashes. Screenshots and results are under `evidence/`.

Artifact classification: `godot/assets/` are derived prototype outputs; `generation/pacific-reference.png` and `evidence/europe-before.png` are source references; `generation/pacific-01/image-01.png` is the selected donor; JSON/prompt files are reproducibility metadata; screenshots and edit masks are comparison evidence. Exported engine binaries live in the temporary shared `web/` folder, not Git. Earlier regional/world candidates are preserved outside this prototype.

## Requested corrections

Antarctica extends the world from 2240 to 3144 pixels tall. Its land silhouette comes from [Natural Earth](https://www.naturalearthdata.com/downloads/110m-physical-vectors/), public domain, rasterized in the existing palette with an eight-pixel white coast. The clipped South American tip and missing Florida Keys were completed locally in the same style.

USA registration identifies 89 original mainland markers with [GeoNames](https://www.geonames.org/), CC BY 4.0, and excludes one duplicate Washington mark. Labels follow their markers; reviewed coast-side adjustments keep marker centers inside the illustrative land while preserving northeast-city order and Key West south of Miami. Source coordinates, GeoNames IDs, and every placement correction are recorded in `reference/usa-cities.json` and `evidence/usa-registration.json`. The world artwork remains illustrative. Large lakes now use sourced geometry, and close views switch to finer geographic coastlines.

No new paid generation was used for these corrections. All ten original full-sheet views, including the previously approved Europe reduction, are unchanged.

## Current city and camera behavior

The city/name association is based on identified names instead of the nearest generated red dot. `reference/city-catalog.json` records GeoNames matches and original label rectangles across the other nine sheets; `evidence/city-registration.json` records their placement adjustments. London uses a reviewed southeast-England anchor. Shared or adjacent source labels, including New York/Philadelphia, Detroit/Cleveland, and Belgrade/Bucharest, are separated from their neighboring city identities. All 47 European city names remain represented. Ambiguous and non-city source annotations remain listed in the catalog and visible in Full sheet rather than receiving invented geographic identities.

All camera inputs stop at a 1.0× minimum. The visible southern edge stops within Antarctica at world y=2700, before the polar projection stretches excessively. The unlimited pink fill is removed. Resizing, reset, buttons, wheel, pinch and panning use the same constraint.

Current acceptance includes sparse named overview on desktop and phone, zero orphan dots during zoom, sparse Russian regional view with towns delayed to close zoom, London on Great Britain, southern drag stop, viewport resize, all ten original thin label texture hashes, and the retained full-sheet/palette/hosting checks. No additional paid generation.

## Lakes and finer coastlines

The overview retains its original terrain artwork with the Great Lakes and major lakes in Canada and elsewhere added from Natural Earth 5.1.2. At native zoom 1.65–1.8 it transitions to 1:10m geographic coastlines and a curated set of major lakes, rasterized at four times the original pixel resolution. This adds actual bays, islands and shore geometry rather than enlarging the original pixels. The original palette, thin city-label textures, red dots, badge art and full sheets remain intact.

Only visible detail tiles are loaded. A small signed-distance shader keeps the white close-up outline approximately eight screen pixels wide as zoom increases, avoiding oversized white rings around small lakes. Detail city anchors use the same projection and land checks as the geographic layer. The source artwork and geographic coastlines differ slightly; the brief level transition moves city anchors with the terrain. This is one finite detail level, not unlimited street-level cartography.

`prepare_geography.py` builds the 48 detail tiles and geographic fields from the pinned, public-domain source extracts in `reference/`; run it before `prepare_atlas.py` to reproduce terrain assembly. Source URLs, versions and hashes are in `reference/detail-sources.json`. No additional paid generation was used.

## Small-feature cleanup and overview numbers

Small uninhabited island polygons and minor lakes are omitted from the geographic layer; small holes inside retained land and lake shapes are removed too. Major coastlines retain their finer shape, and islands needed by identified city labels remain. The overview uses the same major-lake selection. Counts and area thresholds are recorded in `evidence/geography-detail.json`.

The original 29 world badge crops now render at 22 screen pixels high, with space reserved before city labels are placed. Their fade uses the viewport minimum zoom as well as the native scale, so the colored numbers remain opaque at 1.0× even on a 4K viewport. Regional badges take over after the world badges fade. No original badge pixels, regional full sheets or label textures were edited.

## Deeper zoom and additional cities

Maximum zoom is now 36× native scale, three times the previous maximum. The minimum remains 1.0×. Beyond the original regional labels, 40,806 additional GeoNames cities and towns reveal in three close-view tiers: native zoom 7 for cities of at least 250,000 people, 14 for at least 50,000, and 24 for at least 10,000. Smaller places do not crowd the overview.

The additional catalog excludes the existing named identities, subdivisions, duplicate nearby names and points without retained land within two native-map pixels. Each additional dot and name is accepted and drawn together using the same collision space as the original labels. A geographic grid restricts layout work to nearby places. Their names use the existing regular PixelMplus font; all original label textures remain untouched. The retained coastlines, lakes, islands and badges are unchanged. At maximum zoom the white outline has a one-detail-pixel minimum so it cannot vanish.

Reproduce the added catalog with `python3 benchmarks/atlas-prototype/prepare_close_cities.py /path/to/cities5000.zip`. The selected source records, download SHA-256 and GeoNames CC BY attribution are in `reference/close-cities.json.gz`; the runnable catalog is `godot/close-cities.json`. Font permission is included in `godot/fonts/LICENSE.txt`. No paid generation.
