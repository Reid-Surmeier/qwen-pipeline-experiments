# Prototype question

Can the existing world and regional art behave as one continuous zoomable Godot atlas, without blank gaps or losing the established pixel design?

## Findings and implementation choice

Godot's Camera2D supplies the canvas transform for pan and zoom. CanvasItem nearest filtering preserves raster pixel steps. A single-threaded Compatibility Web export runs through ordinary HTTPS hosting without SharedArrayBuffer isolation headers. Sources checked 2026-09-07:

- https://docs.godotengine.org/en/stable/classes/class_camera2d.html
- https://docs.godotengine.org/en/stable/classes/class_canvasitem.html
- https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_web.html

The repository already contains `scripts/georeference.py`, `scripts/build_composite.py` and `benchmarks/regional/EXTENTS.json`. They establish a Miller-coordinate placement method, but old fit scores range from 0.42 to 0.87: rectangular placement alone is not exact registration. USA includes unrelated inset panels; Middle East includes an enlarged Arabian inset. These cannot be pasted as rectangular geography. Extract geographic panels, calibrate useful city anchors, retain a complete world underlay, and use edge blending plus a zoom-dependent detail layer. Keep the original full sheets separately available for direct inspection.

An inference from those assets: generating every sheet again would move its labels and coastlines without solving registration. Apply Muse only to a visible missing Pacific wrap segment, then preserve the existing ten regional sheets through deterministic Assembly. Source geography is illustrative, not a certified geographic dataset. Prototype decisions remain on the throwaway branch until user evaluation.

## Playtest findings

The first geographic warp bent glyphs and badges, most severely on the conic-looking Russia sheet. Moving intact annotation groups solves that observed defect. Fixed screen-size lettering and a small occupancy grid prevent overlaps as regions come together; cities retain red markers. Multiword labels are grouped before placement so decluttering does not hide half a name.

The first phone test also found that disabling Godot touch-to-mouse emulation prevented native controls from accepting taps. Keeping UI emulation enabled while ignoring synthesized mouse input in the map gesture handler gives both working native buttons and single, non-duplicated pan/pinch gestures.

Desktop playtest covers all ten region selections, automatic detail, pointer-anchored zoom, pan, sheet view, reset, and crossing the Pacific wrap. A separate 390×844 phone run checks controls fit, region taps, two-finger pinch, one-finger pan, touch release, and reset. Source/badge preservation and served-file hashes are checked separately from visual inspection.

## Revision findings

The first overview displayed cities baked into `world.png`, so fading regional annotations could not hide them. The runtime now draws clean terrain and extracted original overview badges, then reveals separate city and label sprites at zoom ≥0.65. A 55-screen-pixel spacing rule progressively admits more cities; labels are tied to accepted markers. The original bitmap strokes are dilated one pixel and drawn opaque black rather than fading with terrain.

Six US control points were insufficient for differing source projections. The revised registration identifies 89 mainland markers against GeoNames' downloadable city data, then records bounded coast-side placements on the existing illustrative silhouette. One duplicate Washington dot is omitted from the assembled atlas. Original full sheets remain untouched. Data source and attribution: https://www.geonames.org/export/ (CC BY); selected records are committed for reproduction.

The original world stopped at 2240 native pixels, before Antarctica. Natural Earth's public-domain land polygons supply the missing silhouette through the South Pole at 3144 pixels, using the existing Miller mapping, pink fill and white coast. Source: https://www.naturalearthdata.com/downloads/110m-physical-vectors/ ; downloaded source URL and SHA are recorded in `reference/sources.json`. This is deterministic Assembly, not another paid Render Pass.

The Muse Pacific donor's New Zealand silhouette was 413×464 pixels, visibly oversized relative to Australia. Assembly retains its shape and places it at a mainland extent of 154×193 pixels, then reconstructs the eight-pixel white coast instead of shrinking the stroke. The Pacific wrap includes both land and stroke. These corrections require no new generation spend.

## Owner's density, placement and pan correction

The owner preferred the earlier thin text and clarified that overview should retain a few city names. The original ten label textures are restored byte-for-byte from commit `99840fb`. World labels use a smaller screen size; identified major cities have early reveal tiers, smaller places wait until native zoom 3.5 or 5.5. Dot and all associated label pieces are accepted as one rectangle group, so clipping or collision hides the whole pair.

The placement audit found names that were nearer the wrong generated source dot: London was on the continental side of the channel, Rome followed Ljubljana, Vancouver followed Calgary, and several US city names were grouped together. Name identity is now explicit in the catalog using the GeoNames cities500 data extract and reviewed source readings. The assembly records geographic targets and coast-side adjustments. London, Edinburgh, Dublin and Reykjavík have reviewed anchors on their intended island silhouettes. The existing world geography remains illustrative; ambiguous/non-city source annotations are recorded separately and retained in Full sheet.

A camera-center clamp still allowed the viewport below Antarctica. The shared constraint now subtracts half the visible world-space viewport height. At overview scales where the map is shorter than the viewport, vertical motion locks to the centered world and a fixed pink polar cap fills below the artwork. This keeps the map centered on phones and removes the false sea and bottom coastline. Tests attempt repeated southward drags, zoom through both density directions, and resize the viewport; original gestures continue through the same handler.

## Geographic detail and zoom-floor revision

The owner requested a 1.0× zoom floor, smaller visible Antarctic extent, major lakes, and genuine land detail at close zoom. Natural Earth's [1:10m physical vectors](https://www.naturalearthdata.com/downloads/10m-physical-vectors/) and [lakes documentation](https://www.naturalearthdata.com/downloads/10m-physical-vectors/10m-lakes/) provide detailed land and lake geometry in the public domain. This run pins the vector repository to v5.1.2 and records original download hashes and reduced-property extract hashes in `reference/detail-sources.json`. No generated geography is presented as an authoritative geographic source.

Implementation: keep the approved overview, add major lakes there, and rasterize the real geographic detail at four times its resolution into 560×524-world-pixel tiles. Godot loads visible tiles at close zoom. Detail city positions share that projection. The original full-sheet art is retained. Inference from the existing assets: complete exact registration of generated coastlines to geographic coastlines is impossible without changing their shape, so a short scale transition replaces the terrain and moves city anchors together.

The first visual trial applied the original eight-world-pixel stroke to every small island and lake. This produced excessive white rings. Signed-distance tiles now retain the detailed silhouettes while the shader keeps close-up strokes at eight screen pixels. Padding exceeds the maximum stroke radius, preventing tile-edge seams. Nearest filtering preserves hard pixel steps; no blur or invented fractal detail is added.

The prior unlimited pink polar fill caused the excessive Antarctic area. The shared camera constraint now requires a viewport-filling minimum scale and stops at y=2700 within the Antarctic land, keeping the full high-latitude source terrain available as an asset while preventing travel to its stretched pole. The displayed minimum is 1.0× on desktop and phone. Narrow screens pan across the world horizontally instead of exposing unused canvas.

## Small-feature cleanup and badge visibility

The owner found the new small lakes and islands too numerous. Geographic assembly now drops lake polygons below 100 square native-map pixels or scale rank above 2, and land polygons below 60 square native-map pixels except those near identified city coordinates. Small interior rings receive the same treatment. Filtering full polygons before tiled rasterization avoids fragments or seams at tile edges; the original source geometry remains preserved in `reference/`.

Overview badges previously faded at a fixed native camera scale of 0.5–0.65. On a sufficiently large viewport the 1.0× minimum itself exceeded that threshold, making the world numbers disappear. Their reveal now follows the viewport minimum, and individual original badge crops maintain a 22-pixel screen height. Desktop, phone and 3840×2160 screenshots test the actual minimum zoom and visible badge count.

## Deeper zoom and additional city catalog

The original 396 names were already all eligible by native zoom 5.5, so increasing the old 12× maximum alone could only relieve collisions. To reveal genuinely additional places, the prototype reuses the previously downloaded [GeoNames cities5000 extract](https://www.geonames.org/export/), retaining populated places and administrative seats with population at least 10,000 and excluding subdivisions and duplicate source identities. Source rows and attribution are preserved.

No new terrain is generated: extra markers must find existing retained land within two native-map pixels. New names remain hidden below close zoom 7; population tiers at 7, 14 and 24 admit progressively smaller places. Original bitmap labels keep priority. Dot/name pairs share one clipping/collision rectangle and draw together. A 64-world-pixel grid limits candidate work to the visible neighborhood rather than creating tens of thousands of nodes.

The existing regular PixelMplus font is reused under the [upstream M+ permission](https://github.com/itouhiro/PixelMplus/blob/master/misc/mplus_bitmap_fonts/LICENSE_E). Godot's [CanvasItem drawing API](https://docs.godotengine.org/en/stable/classes/class_canvasitem.html) supplies drawing at fixed screen size. A shared maximum constant raises wheel, button, keyboard and pinch zoom to 36; the coastline shader retains a one-texel stroke minimum at that scale.

## Slower reveal pacing

The owner wanted less density earlier in zoom. The previous three thresholds admitted large population bands simultaneously. Original secondary-city thresholds move from 2/3.5/5.5 to 3.5/6.5/11, while original world and major regional labels remain unchanged. Additional cities now reveal across population-based thresholds spanning 12.17–34: large cities spread over approximately 12–18, medium places over 18–26, and smaller towns over 26–34. All 40,806 additional identities remain and each has a later threshold than before.

Verification compares old and new reveal eligibility for every added city and captures five real wheel-zoom checkpoints around London. This changes pacing only: city positions, glyphs, palette, map textures, badge artwork and camera limits are preserved.

## Further zoom and simultaneous label density

The Tokyo screenshot demonstrated that later eligibility alone still fills the screen once many places qualify. Increase the shared maximum to 120, stretch additional thresholds to 24.67–112, and increase existing pair-rectangle padding from 8 to 60 screen pixels. Reusing the population-sorted collision pass preserves larger places and leaves room around each accepted name; closer zoom separates competing towns spatially. Original labels retain priority and their exact typography. No new terrain or generated artwork. Real-input checks compare the same Tokyo scale to the previous build, check close-pair spacing, and reach 120 on desktop and phone.

## City names and dots grow at close zoom

Both city rendering paths previously divided by camera zoom to hold a fixed screen size. A shared scale now grows from one to two between native zoom 2 and 80; original world lettering keeps its prior 0.65 scale. Apply this factor to the original texture sprites, the additional text/dot drawing transform, and every corresponding layout rectangle/offset. Pixel filtering and original glyph assets remain intact. Verification compares rendered red pixels against saved before screenshots for original and additional cities at the same camera, checks intermediate growth, and playtests the enlarged labels on desktop and phone.
