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

## Recommended assembly order — maximal batching (≤1 call per widget TYPE)

Each MCP call is a serialized round-trip through the browser bridge, so **wall-clock is
dominated by call count.** Collect every widget of a type across the whole board into one list
and issue **one `create_*` call per type**, in this fixed order:

1. `create_areas` — section frames/containers (children parented via `parent_id`)
2. `create_titles` — headline/section headings
3. `create_shapes` — cards, chips, badges, tints, chart geometry (**never `create_table`** — it's
   broken here; build matrices as area-nested chips + textboxes, see `table-fidelity.md`)
4. `create_icons`
5. `create_textboxes` — body, labels, bullets
6. `create_connectors` — **last**, after all endpoint ids exist (`connect_widgets`, never `→` glyphs)

**Order each list backgrounds-first** (area fills / chart scaffolds / tints / chip fills before
their labels; chart segments before markers). Within a single `create_*` call, **list position =
paint order — the last item in the list renders on top** (validated: three overlapping rects
created `[red, green, blue]` in one call landed with `stackingOrder` red<green<blue, blue on top).
So one batched call with backgrounds first correctly reproduces z-order — no need to split
background vs foreground into separate calls.

**Size cap ~80 widgets per call.** Above that, split by section (a size concession, not a z-order
one — still backgrounds-first within each split) and re-run the Layer-6 dedup check (the bridge
double-apply bug scales with batch size).

**Mapping returned ids back to widgets:** the create response's array order is **not guaranteed to
match input order** (observed reversed in the z-order test). Match each returned id to its logical
widget by the returned `position_x`/`position_y`, not by array index — this matters when wiring
`create_connectors` to specific endpoints.

Do secondary detail/alignment cleanup afterward with a batched, idempotent `update_widgets`.

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
5. **Transcribe** text (Pass A), then **replicate** repeated widgets — one batched call per
   widget type (see "maximal batching" above), not per section/family.
6. **Connect** the conceptual flow with real connectors and grouping.
7. **Verify** with a screenshot diff against the source (required — see below).
8. **Refine** spacing, alignment, and contrast only after structure is right.

## Decision rule for active board detection

- If a writable Mural board is already open, execute directly.
- If no board is open, build from the image and be ready to create or target a new board.
- If both are possible, choose the fastest path that preserves fidelity.

## Verification checklist

**Verification budget:** 0 full-board screenshots mid-build; verify geometry by `list_widgets`
diffs; take **exactly one `get_canvas_image` at the very end** for the source/HTML compare.

- **Geometry — by diff, not pixels (default).** After each create batch, diff `list_widgets`
  (`view="full"`, scoped by `aabb`/parent) bounding boxes against the intended coords. No
  screenshot needed for placement.
- **Content — by data model.** Confirm text via `list_widgets` `text_content` (lag-free);
  reserve `get_widgets_screenshot` (small id set, `max_output_dimension` ~1024) for the rare case
  a value must be eyeballed.
- **Dedup — by count.** `get_canvas_overview` `total_widgets` vs intended after each large batch
  (cheap, count-only); run `scripts/dedupe_widgets.py` if higher.
- **Final compare — one `get_canvas_image`.** Then check against the source:

Then check:

- Does the board read in the same order as the image?
- Did every major section survive the translation?
- Are repeated widgets repeated the same number of times?
- Do matrices use area-nested chips + textboxes (**never `create_table`**) and flows use real
  connectors (no `→` glyphs)?
- Does placed text match the Pass-A manifest?
- Did any widget get nudged (`requested_x/y` ≠ final position)? Usually a misused sticky.
- Are relationships between blocks clear without relying on exact decorative assets?

Fix with a batched, idempotent `update_widgets` / `move_widget_to_area`, then re-verify (geometry
diff first; re-screenshot only the touched region if needed) until it matches.
