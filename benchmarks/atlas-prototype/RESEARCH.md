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
