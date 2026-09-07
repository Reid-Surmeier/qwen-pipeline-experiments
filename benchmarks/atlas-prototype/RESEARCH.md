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
