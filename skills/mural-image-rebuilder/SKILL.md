---
name: mural-image-rebuilder
description: reconstruct a mural from screenshots or reference images by extracting widget-level structure, layout hierarchy, text content, and visual patterns such as timelines, matrices, dashboards, and strategy frameworks. use when recreating a board from an image, preserving fidelity at the widget level, or deciding whether to execute directly in an active mural tab versus build from a standalone image.
---

# Mural Image Rebuilder

## Overview

Recreate a Mural board from one or more images by preserving structure, hierarchy, widget families, and readable text. Optimize for a faithful board-level reconstruction, not a pixel-perfect clone. Prefer Mural-native primitives: frames, shapes, text, connectors, tables, cards, badges, and grouped blocks.

## Token discipline

Builds run through image + MCP calls that are individually expensive; keep them cheap by default.

- **Prefer the board-spec path** (below) — it skips vision entirely and is the cheapest route to a
  faithful board.
- **Reads:** use `get_canvas_overview` for counts/types; default `list_widgets` /
  `list_widgets_near` to `view="compact"`. Use `view="full"` only when you need geometry, and
  **scope it** (an `aabb` region, or an anchor + small radius) — never a whole-board `full` dump.
- **Screenshots are heavy — verify at layer checkpoints, not after every create.** Pass a
  **targeted set of widget ids**, not the whole canvas; cap `max_output_dimension` (~1024 for
  layout scans, up to 1400 only to read dense text). Reserve `get_canvas_image` (whole board) for
  the final compare. For pure position/geometry checks, **diff `list_widgets` (`view="full"`)
  bounding boxes instead of screenshotting** — no pixels needed.
- **Icons:** `search_icons` returns heavy base64 previews — call it with `limit=3`, **once per
  distinct pictogram**, and reuse ids for repeats; don't re-search a weak match without a new
  term. (`references/icon-matching.md` has the full cost note + a vetted-id shortlist.)
- **Scripts over round-trips:** compute chart geometry with `scripts/line_chart.py` /
  `scripts/pie_chart.py` and dedup with `scripts/dedupe_widgets.py` rather than probing the board.
- **Reuse data you already fetched** — don't re-read state between steps.

## Consuming a board-spec (from muralize) — the lossless path

If you're handed a **`board-spec`** (JSON, produced by the `muralize` skill —
schema in `../muralize/references/board-spec.md`) instead of (or alongside) an image,
**build from the spec and skip vision entirely.** The spec carries verbatim text, exact
counts, palette roles, and primitive-aligned blocks, so there is no OCR/vision loss.

Mapping spec → this skill's primitives:
- `meta.palette` roles → resolve to hex once; every block's `color`/`fill` references a role.
- `meta` header/hero → build the whole header, top to bottom, so it matches the infographic:
  `meta.eyebrow` → a small textbox in the accent role (~13px, letter-spaced) placed **above**
  the title; `meta.title` → a `title` widget **in the spec's exact casing** (never force
  upper/lower case — if the spec is title-case, the board is title-case); `meta.subtitle` → a
  muted textbox under the title; `meta.tags` → **one small chip shape per tag** (`rounded_square`,
  subtle fill, short label) in a row beneath the subtitle. Reproduce **every** header element
  the spec carries — dropping the eyebrow or the chips makes the board diverge from the HTML
  (a real bug seen in practice: the eyebrow "first line" and chip row went missing on the board
  because they weren't rebuilt from `meta`).
- each `section` → an `area` (with `showTitle:false`) + a heading widget from `section.title`,
  placed per `section.grid` on your layout map (reserve the top band).

**Block → primitive (build recipe).** The common blocks are summarized here; the detailed recipes
for charts and metaphor blocks live in references — **load them only when you build that block**:

| block | primitive recipe |
|-------|------------------|
| `flow` | step shapes (`shape`) + icons (icon-matching loop) + **real connectors** (`loop:true` closes the cycle). |
| `table` | area-nested chips + textboxes on a grid, per-column colored headers + column tints, **NOT `create_table`**; cell variants text/bullets/chips/coloredText, leading-label badge→icon→name. Full recipe: `references/table-fidelity.md`. |
| `cards` / `metrics` | titled entries (bold colored title + desc + optional `meta`/icon) in `columns`. |
| `banner` / `callout` | filled rectangle + centered/emphasis text. |
| `gauge` | a gauge tile per item — linear meter (default, renders precisely) or radial dial; the numeric `value` label is the fidelity, not the arc. Recipe: `references/chart-fidelity.md`. |
| `chart` (`bar`/`line`/`pie`) | build from primitives in a plot area (axis first, data, labels on top); the value labels are the fidelity, the shapes are the approximation. Recipe: `references/chart-fidelity.md` (+ `scripts/line_chart.py`, `scripts/pie_chart.py`). |
| `comparison` `cycle` `chips` `pyramid` `funnel` `quadrant` `pillars` `hub` `timeline` `swimlane` `gantt` `tree` `mindmap` `venn` `spectrum` `decision` `rings` | metaphor blocks — one build recipe each in `references/block-catalog.md` (real connectors, area-nested cells, never `create_table`). |
| `icon` concept names | resolve via the icon-matching loop (or use a supplied `noun_project_id`) — `references/icon-matching.md`. |

Then run Layer 6 verification exactly as for an image build. Trust the spec's text and counts
literally; do not "improve" wording. Fall back to the image/vision path below only when no
spec is available.

## Operating modes

1. **Image-only build**: Use when the user provides screenshots or reference images and no board is open.
2. **Direct execution**: Use when a writable Mural board is already open.
3. **Bridge mode**: If no board is open, prepare the reconstruction from the image first, then hand off the fastest executable build plan.
4. **Local browser execution**: Use when a writable board is open in Chrome but the Mural MCP is unavailable. Plan exactly as normal, then execute the build through the local browser via the `mural-local-driver` skill (it maps every primitive below to a local click/drag/type operation and verifies via screenshots). See `../mural-local-driver/references/rebuilder-backend.md`.

Decision rule:
- If a writable Mural board is available via the Mural MCP, execute directly.
- Else, if a writable board is open in Chrome (extension enabled, domain permissioned, not bypass mode), execute locally via `mural-local-driver`.
- If neither, continue without blocking on board setup.
- Never require the user to open Mural before starting analysis.

## Pattern recognition first

Before rebuilding, identify the dominant board pattern. Treat this as the primary routing step because it determines the widget families and assembly order.

### Common patterns

- **Timeline**: Look for horizontal or vertical progression, milestones, dates, phases, arrows, and recurring checkpoint markers. Rebuild the axis first, then place milestones, then add labels and detail cards.
- **Matrix / quadrant**: Look for 2x2 or grid-based layouts with axis labels, intersecting themes, scorecards, or category comparisons. Rebuild the grid frame first, then fill each cell with its widget family.
- **Dashboard**: Look for KPI tiles, charts, side panels, summary blocks, legends, and dense metric-heavy composition. Rebuild the metric hierarchy first, then the chart containers, then supporting annotations.
- **Strategy framework**: Look for pillars, layers, flywheels, ladders, loops, or stacked conceptual blocks. Rebuild the conceptual scaffolding first, then add the supporting labels and connectors.

If the image contains mixed patterns, choose the dominant one and treat the others as embedded substructures.

## Primitives-first routing (do this before placing anything)

The most common failure mode is faking a structure out of loose textboxes and glyphs
when a native widget exists. Before building each element, route it to the right tool.
These MCP tools exist and are preferred — use them:

| If the source shows… | Use | Do NOT |
|----------------------|-----|--------|
| A grid / matrix / comparison table | an `area` of positioned cells — column-tint backgrounds, **per-column colored header cells** (one colored cell per column, not one banner), chips + textboxes — per `references/table-fidelity.md` | rely on `create_table` (cells render **empty** here); flatten the header into a single band when the source colors each column |
| A matrix cell holding **several chips/stickies** (e.g. an "experiments" column with 3 tags) | one chip widget **per chip** (small `shape`), laid out in the **same arrangement as the source** (a row of N across if it shows a row) and **sized to hug its text**, not stretched full-width | collapse the chips into one `"a · b · c"` string, or stretch one chip across the whole cell — both lose the count/arrangement the source shows |
| A matrix cell holding a bulleted list | a single textbox with `\n•` lines | separate widgets per bullet |
| Sequential steps, loops, dependencies, "→" arrows | create the nodes, then `connect_widgets` / `connect_widget_to_point` | type `→`/`->` glyphs in a textbox as fake arrows |
| A titled region or section | `create_areas` first (with `showTitle: false`), a dedicated `title` widget for the heading, then children with `parent_id` (or `move_widget_to_area`) | leave section contents as loose widgets, or rely on the built-in area title (it overlaps content — see caveat) |
| Icons, logos, pictograms | `search_icons` → inspect previews → `create_icons`, tinted to match; one strategy per board (see `references/icon-matching.md`) | substitute mismatched emoji for the source's custom icons, or mix real icons and emoji across the board |
| KPI tiles / cards | a shape (created first, as background) with text on top, or a titled area | a sticky note |
| Literal sticky notes in the source | `create_stickies` | anything else |

Fall back to shapes + textboxes only when the native primitive genuinely can't express
what the source needs — and say so when you do.

**`create_table` is broken here — do not use it for content.** Observed on multiple
builds: `create_table` returns `cells_populated: 0` and does not fill cells; and the
follow-up `update_widgets` with `textContent` returns `success: true` / `updated: N` but
the cells still render **empty** (`text_content: ""`). Both the tool's success envelope
and structural `list_widgets` counts lie about content. Net: a `create_table` matrix ends
up an empty grid. **Build matrices as an `area` with positioned chips + textboxes instead**
(this renders reliably and is what worked before the table tool existed).

**Content validation is visual, not API.** Never conclude text is present from a tool's
`success`/`updated` count or from a zoomed-out board screenshot. To confirm a
matrix/table actually shows its content, call `get_widgets_screenshot` on the **child
widgets** (pass the cell/chip/textbox ids, not just the container — the container renders
as an empty frame) and read the text off the image. If it's blank, the build failed
regardless of what the API returned.

**Do NOT recreate widgets to "fix" them — you will create duplicates.** Two failure modes
seen in real builds both end in duplicate widgets stacked at the same spot. Guard against both:

- **Render lag ≠ missing content.** A widget's text renders a beat *after* `create_*`
  returns, so a `get_widgets_screenshot` taken immediately can show a blank widget that is
  actually populated. Before deciding a widget is empty and recreating it, read its real
  stored content with `list_widgets` (`view="compact"`, check `text_content`) — that's the
  data model, lag-free and authoritative. Non-empty `text_content` + blank image = a render
  delay, not a failure: **do not recreate.** Empty `text_content` = a genuine miss (e.g. the
  `create_table` bug). To fix genuinely wrong/missing text, **edit in place** with
  `update_widgets` / `set_sticky_text` on the existing widget — never a second `create_*`.
- **A failed write may still have applied.** A `create_*`/`update_widgets` call can return an
  error (e.g. "no active mural", a transient bridge error) yet still have executed on the
  board. Before retrying, re-check state with `get_canvas_overview` / `list_widgets`; if the
  widgets are already there, don't re-issue the call. After a `partial` batch, retry **only
  the `failed` ids**, never the whole batch.

If duplicates do slip in, remove the extras with `delete_widget` (confirm ids via
`list_widgets` first) — don't just `hidden:true` them, which leaves dead widgets on the board.

**`update_widgets` uses PARENT-RELATIVE coordinates for children — `create_*` uses
absolute.** This asymmetry silently flings widgets off-screen. `create_*` places a widget
(even a child of an area) at absolute canvas coords. But `update_widgets` interprets a
parented widget's `x`/`y` as RELATIVE to its parent area's origin. Observed: Product
Foundation labels parented to an area at x=1320 were "shifted" to x=1357 via
`update_widgets` and actually jumped to absolute 2677, vanishing from the section (the
API still reported `success`). To move a child to absolute `(X, Y)`, set
`x = X − area_x`, `y = Y − area_y` (or detach `parentId` first, or delete + recreate).
The bug scales with the parent's offset, so a far-right section is hit hardest.

**Re-verify the WHOLE section after any edit/move, not just the widgets you touched.**
A screenshot of only the new pieces (e.g. freshly placed icons) will miss that a
reposition flung existing text off-screen. After `update_widgets`/`move_widget_to_area`,
screenshot the entire affected section and read it back.

**Area built-in titles overlap content — don't use them as the visible heading.** Mural
renders an area's own title INSIDE the top of the frame, on top of any content placed
there, which reads badly (shrinking `titleFontSize` is not enough). Instead:
- Set `showTitle: false` on the area (hides the built-in title; the area stays a container).
- Render the section heading as a dedicated `title` widget parented to the area, placed in
  a reserved top band (≈ `area_y + 6`, font ~13, bold). It's a normal widget you position
  precisely, so it sits above content instead of over it — and still moves with the area.
- Reserve the top ~30px of every area for this heading and start content below it
  (plan this in the Layer 1 layout map). Skip the heading widget for a section whose
  content already self-labels (e.g. a callout that begins "Key Difference — …").

Two hard rules learned from real builds:

- **Never use sticky notes for grids, table cells, chips, or anything needing precise
  placement.** Stickies are large (~168px) and auto-nudge on collision — they will
  relocate, sometimes to negative coordinates. Use textboxes, shapes, or `create_table`.
- **Areas are the only real containers, and only via `parent_id`.** Dropping a widget
  inside an area's bounds does not parent it. Create the area first, then parent its
  children, so the section moves and groups as a unit. Newer widgets render on top, so
  create backgrounds/areas before their contents.

## Layer-by-layer reconstruction checklist

Rebuild the source in layers. Do not jump ahead until the current layer is stable.

### Layer 0 — Source scan
- Identify canvas bounds, orientation, and dominant reading direction.
- Detect the board title, branding, and any footer or header bars.
- Count major sections and repeated modules.
- Classify the dominant pattern: timeline, matrix, dashboard, strategy framework, or mixed.
- Note where text is clear, partially legible, or unreadable.

### Layer 1 — Macro layout
- Before placing anything, write a **layout map**: each section's bounding box
  `(x, y, w, h)` on a consistent grid with fixed gutters, and confirm boxes don't
  overlap. This prevents drift and the sticky-spill seen in past builds. Reserve the
  top ~30px of each area as a heading band and start content below it (see the area-title
  note below).
- Recreate the outer canvas structure first.
- Place the largest containers, sections, and columns (as `areas`; see routing above).
- Match relative size ratios and whitespace between major blocks.
- Keep the top-to-bottom and left-to-right reading order intact.

### Layer 2 — Widget families
- Recreate repeated widget patterns as reusable families: cards, tiles, tables, timelines, legends, callouts, metric boxes, chips, and panels.
- Match the number of widgets in each family.
- **Match each family's SHAPE to the source, don't guess from memory.** Look up the
  source's visual signature in `references/shape-catalog.md` (e.g. an interlocking
  chevron banner is `step`, not `pentagon_smart`). For any non-trivial repeated shape,
  run the **probe-then-replicate loop**: create one probe (and rival candidates if
  unsure), `get_widgets_screenshot` it, compare to the source, then commit. If you guessed
  wrong, `update_widgets` with `{shapeType: ...}` fixes it in place — no rebuild needed.
- **Match icons the same way** (see `references/icon-matching.md`): decide one icon
  strategy for the board, name each distinct source pictogram as a search term,
  `search_icons`, pick by inspecting the previews, `create_icons` tinted to match, then
  screenshot-verify. Real icons beat mismatched emoji; search once per distinct pictogram
  and reuse ids for repeats.
- Preserve the family’s internal rhythm: spacing, alignment, and label placement.
- Use generic shapes or placeholders for icons and imagery only as an explicit,
  stated fallback when no suitable icon exists.

### Layer 3 — Connectors and relationships
- Use real connectors (`connect_widgets`, or `connect_widget_to_point` for a free point),
  never `→`/`->` text glyphs standing in for arrows.
- Create the endpoint widgets first, then connect them so the connector anchors correctly.
- Preserve directionality, sequence, and adjacency; for loops, close the cycle back to
  the first node.
- Ensure connectors explain the same conceptual relationship as in the source.

### Layer 4 — Text fidelity (two passes)
Placing text from memory in one pass produces garbled content (e.g. "outperform" became
"superform", invented KPI names). Split it:

- **Pass A — Transcribe.** Before placing text, read the image and write a structured
  manifest of every legible string: `section → element → verbatim text`. Where text is
  illegible, write `[illegible: ~N chars]` — never invent wording to fill the gap.
- **Pass B — Place.** Create widgets by copying from the manifest, not from memory.
- Preserve headings, labels, and numeric values exactly; keep repeated fragments as
  separate widgets if the source shows them separately.

### Layer 5 — Visual polish
- Align edges and baselines.
- Tighten spacing inside cards and between groups.
- Rebalance contrast so hierarchy is obvious at zoomed-out scale.
- Approximate colors, icons, and decorative assets only after structure is correct.

### Editing an existing build — reflow in place, don't rebuild
When a build is **content-faithful but visually off** (too sparse, misaligned columns, a few
wrong icons), fix it in place — never delete dozens of correct widgets to recreate identical
text, and never rebuild on a board someone else is editing.

- **`update_widgets` is idempotent** — setting x/y/width/height/color/text-style to the same
  value twice is a no-op, so it is **safe from the create double-apply bug**. Reflow an entire
  region in one batched `update_widgets` call without fear of twins (only `create_*` doubles).
- **Reflow recipe (dense item lists / panels):** keep item 0 anchored to the header, give every
  item a fixed **pitch**, and preserve each item's intra-item offsets. Values that read well for
  a sprint-highlights row: 46px icon; offsets icon/title `+0`, ticket `+26`, description `+54`;
  and a **~140–150px item pitch** (a ~220px pitch reads as unfinished whitespace). Collapse
  panel-background heights and pull footers/callouts up by the same amount so the card refits.
- **Icons can't be reflowed** (stickers aren't `update_widgets`-able) — delete + recreate at the
  new coords, recovering `noun_project_id` from `get_widget_by_id.name` (see
  `references/icon-matching.md`).
- **Scope reads to the region.** On a busy or live-edited board, enumerate just your section with
  `list_widgets_near` anchored on that section's **backing shape** (small radius) rather than
  reading the whole canvas, and operate **only on those known ids**. Never run a board-wide dedup
  on a shared board being actively edited — it can delete other people's widgets. Confirm scope
  before large moves, and verify the region visually with `get_widgets_screenshot`.

### Layer 6 — Verify against the source (required, not optional)
A reconstruction you never looked at is not finished. This step is mandatory. Keep verification
cheap per the **Token discipline** policy above (checkpoint screenshots, targeted id sets,
geometry diffs over pixels).

- Read the canvas back with `get_viewport_screenshot` (or `get_canvas_image` /
  `get_widgets_screenshot`) — once after the macro layout, and again at the end.
- **Screenshot reliability:** right after a `create_*`, `get_widgets_screenshot` often fails
  with "none of the requested widget IDs were found" (render lag) — retry once or twice, and
  if it keeps failing fall back to `get_canvas_image`, which renders the whole board reliably
  and is the best tool for a final old-vs-new or multi-section comparison. For precise
  geometry checks you don't need pixels at all: `list_widgets` (`view="full"`) returns each
  widget's rendered axis-aligned bounding box (`position_x/y`, `width`, `height`) — diff those
  against the intended coordinates (this is how the segment-rotation bug was pinned down).
- Diff against the source top-left → bottom-right: section count, per-family widget
  count, text vs the Pass-A manifest, reading order, and any overlaps.
- Scan create-tool responses for `requested_x/y` that differ from the final position —
  that means a widget was nudged (usually a misused sticky); fix it.
- **Dedup check (required after any large batch build — charts especially).** Compare
  `get_canvas_overview`'s `total_widgets` (and per-type counts) against what you intended to
  build; if it's higher, you have duplicates. Two causes: (a) you recreated on a render-lag
  blank or retried after an errored write, or (b) **the Mural bridge silently double-applied
  a `create_*` call** — the tool returns one id per widget but a second identical "twin"
  also lands on the board with an id you never saw. Twins overlap their originals exactly,
  so the board *looks* right while carrying ~2× the widgets (seen for real: a chart went
  from 349 → 678 widgets). To clean deterministically: dump the built area with
  `list_widgets` (`view="full"`; large results auto-save to a file), then run
  `scripts/dedupe_widgets.py <file> --parent <area_id>` and feed its output (the ids to
  delete) to `delete_widget` in batches; re-run `get_canvas_overview` to confirm. The script
  keeps one widget per group of **pixel-identical** widgets (same type, position, size,
  rotation, color, and visible text), so it is visually lossless — never dedup on position
  alone, which can delete a differently-colored overlapping widget.
- Fix discrepancies with `update_widgets` / `move_widget_to_area`, then re-screenshot.
  Loop until it matches. Only claim it is "verified against the source" once you have
  actually done this.

## Build sequence

1. Read the image once end to end.
2. Classify the pattern and sketch the board as a structure map: sections, widget families, connectors, and text blocks.
3. Build the macro layout.
4. Fill in repeated widgets.
5. Add connectors and secondary details.
6. Fix spacing, alignment, and hierarchy.
7. Compare against the source from top-left to bottom-right.
8. Adjust anything that changes the board’s meaning or visual rhythm.

## Fidelity rules

- Preserve section count, widget count, hierarchy, and visual density.
- Preserve the source’s macro-layout even when exact styling cannot be matched.
- Approximate icons, illustrations, and logos when exact matching is not feasible.
- Prefer fidelity to structure over fidelity to decoration.
- Do not overfit on typography or color when the source is low resolution.
- For dashboards, preserve metric grouping and visual priority before chart styling.
- For timelines, preserve sequence and milestone spacing before decorative markers.
- For matrices, preserve axis labels and cell boundaries before decorative borders.
- For strategy frameworks, preserve the conceptual progression before polish.

## Direct execution behavior

When a writable board is available:
- Move from analysis to execution as soon as the structure map is stable.
- Build the broad shape first, then refine in place.
- Use the image as the authoritative source for layout and content.
- Prefer the fastest path that keeps the structure faithful.

When no board is available:
- Produce the same structure map and reconstruction sequence.
- Be ready to execute immediately once a target board becomes available.
- Keep the handoff short and actionable.

## Quality checks

Before finishing, confirm each of these — they are pass/fail:
- A screenshot of the actual **child widgets** was taken and diffed against the source
  (Layer 6 ran — and content was confirmed on the image, not from API success counts).
- No duplicates: `get_canvas_overview`'s widget count matches what was intended, and no
  widget was recreated to "fix" a render-lag blank or re-issued after an errored write.
- Matrices were built as an `area` of positioned chips + textboxes (NOT `create_table`),
  and every cell that shows multiple chips in the source has multiple chip widgets — laid out
  in the source's arrangement and sized to hug their text (not stretched full-width).
- Matrix headers are colored **per column** to match the source (not a single flat band unless
  the source shows one), and column tints match the source. See `references/table-fidelity.md`.
- No table/cell is empty: text was visually confirmed to render.
- Every flow/loop uses real connectors; zero `→` glyphs used as arrows.
- Each section is an `area` with its widgets parented to it; area `titleFontSize` is small
  enough not to overlap content.
- Placed text matches the Pass-A manifest; illegible spots were flagged, not invented.
- No widget was silently nudged (no unexplained `requested_x/y` mismatches).
- The board reads in the same order as the source and stays recognizable when zoomed out.

If any item fails, the reconstruction is not done.

## References

- `references/rebuild-workflow.md`: detailed assembly order and verification checklist.
- `references/pattern-catalog.md`: visual signatures and reconstruction hints for common board patterns.
- `references/widget-selection.md`: which Mural widget/tool to use for each source element, and the sticky-note / stacking-order gotchas.
- `references/table-fidelity.md`: the concrete recipe for reconstructing a matrix/table so it reads like the source — column tints, per-column colored headers, chip arrangement/sizing, row rhythm, and cell-type routing.
- `references/chart-fidelity.md`: building `gauge` and `chart` (bar/line/pie) blocks from primitives — the meter/dial recipe and the line-segment rotation math. Load when a build includes a chart or gauge.
- `references/block-catalog.md`: the block → Mural primitive rebuild recipe for each metaphor block (comparison, cycle, chips, pyramid, funnel, quadrant, pillars, hub, timeline, swimlane, tree, venn, spectrum, decision, rings). Load when a build includes a metaphor block.
- `references/shape-catalog.md`: visual-signature → `shape_type` lookup, and the probe-then-replicate loop for verifying a shape choice before replicating it.
- `references/icon-matching.md`: how to reproduce the source's pictograms with real searched icons (search → inspect previews → tint → verify) instead of mismatched emoji, plus the search-cost note and vetted-id shortlist.
- `scripts/line_chart.py`: computes create-ready widget arrays for a (multi-series) line chart from a JSON spec — gridlines, axes, legend, and per-series hypotenuse segments + markers. Use it for any non-trivial line chart instead of hand-computing rotations.
- `scripts/pie_chart.py`: computes create-ready widget arrays for a "pie" (a 100%-stacked bar + legend, since Mural has no wedge primitive) from a JSON spec of slices. Use it for any pie/donut/composition request instead of hand-computing segment widths.
- `scripts/dedupe_widgets.py`: post-build cleanup for the Mural-bridge double-apply bug — reads a `list_widgets` (full) dump and prints the ids of pixel-identical duplicate widgets to delete (keeping one each). Run it as part of Layer 6 whenever the widget count comes back higher than intended.
