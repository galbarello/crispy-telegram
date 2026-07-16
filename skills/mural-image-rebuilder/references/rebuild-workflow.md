# Rebuild workflow reference

Use this reference when turning a screenshot into a Mural board.

## What to preserve first

- Section boundaries
- Relative ordering of blocks
- Widget count per section
- Connector direction and graph structure
- Visual hierarchy: headline, subhead, body, callout, metadata

## What can be approximated

- Exact icon artwork
- Decorative illustrations
- Fine-grained color matches
- Font-perfect rendering when the image is low resolution

## Recommended assembly order

1. Background and overall canvas shape
2. Major containers and section frames — as `areas` (`create_areas`), children parented via `parent_id`
3. Large text headers and labels (`create_titles`)
4. Cards, tables, and repeated widgets — tables via `create_table`, not loose textboxes
5. Connectors, arrows, badges, and markers — real connectors (`connect_widgets`), never `→` glyphs
6. Secondary details and alignment cleanup

## Text protocol (two passes)

- **Pass A — Transcribe** every legible string into a manifest (`section → element →
  verbatim text`) before placing anything. Mark illegible text `[illegible: ~N chars]`;
  never invent wording.
- **Pass B — Place** from the manifest, not from memory.

## Layered execution checklist

Use this checklist during real sessions:

1. **Scan** the image and identify the biggest structural divisions.
2. **Map** each division to a Mural container or widget family (see `widget-selection.md`).
3. **Layout map**: write each section's bounding box on a grid; confirm no overlaps.
4. **Block in** the macro layout as `areas` before writing or polishing text.
5. **Transcribe** text (Pass A), then **replicate** repeated widgets in batches.
6. **Connect** the conceptual flow with real connectors and grouping.
7. **Verify** with a screenshot diff against the source (required — see below).
8. **Refine** spacing, alignment, and contrast only after structure is right.

## Decision rule for active board detection

- If a writable Mural board is already open, execute directly.
- If no board is open, build from the image and be ready to create or target a new board.
- If both are possible, choose the fastest path that preserves fidelity.

## Verification checklist (requires an actual screenshot)

Read the canvas back with `get_viewport_screenshot` / `get_canvas_image` /
`get_widgets_screenshot` and diff against the source. Then check:

- Does the board read in the same order as the image?
- Did every major section survive the translation?
- Are repeated widgets repeated the same number of times?
- Do tables use `create_table` and flows use real connectors (no `→` glyphs)?
- Does placed text match the Pass-A manifest?
- Did any widget get nudged (`requested_x/y` ≠ final position)? Usually a misused sticky.
- Are relationships between blocks clear without relying on exact decorative assets?

Fix with `update_widgets` / `move_widget_to_area`, re-screenshot, and repeat until it matches.
