# Block catalog — metaphor block → Mural primitive recipes

How to rebuild each `board-spec` **metaphor block** from Mural primitives. These are the
**build recipes**; the block **schemas** (JSON shape + when-to-use) live in
`../muralize/references/board-spec.md`, keyed by the same block names. Load this reference only
when a build includes one of these blocks (SKILL.md carries the one-line summaries and the
`flow`/`table`/`cards`/`metrics`/`banner`/`callout` basics).

Reuse conventions throughout: color-by-role from `meta.palette`; **real connectors** (never `→`
glyphs); area-nested positioned cells (never `create_table`); the shape choices in
`shape-catalog.md`; and the icon-matching loop in `icon-matching.md`.

- **`comparison`** → N side-by-side columns; each = a heading `title` (in the column `color`) + a
  vertical stack of `rounded_square` boxes in that color, joined top→bottom with **real
  connectors** when `connector:"arrow-down"`. Lay the columns on equal-width grid cells.
- **`cycle`** → node shapes (`circle`/`rounded_square`) placed around a circle (or on a 2×2) with
  **real connectors closing the loop** (last→first); `style:"flywheel"` → curved
  (`arrow_type:"curve"`) connectors. Icons via the icon loop; never glyph arrows.
- **`chips`** → **one small `rounded_square` pill per item**, light `color` fill, laid out in a
  wrapping row (hug text). Never one joined string. (Same discipline as matrix chip cells.)
- **`pyramid`** → stacked `trapezoid`/`triangle_smart` segments of graded width (apex per
  `direction`) + centered label textboxes; create widest-first so labels sit on top.
- **`funnel`** → stacked shapes of decreasing width top→bottom, width ∝ `value`; keep the
  `value`+`label` textboxes (the numbers are the fidelity).
- **`quadrant`** → an `area` split by a crosshair (two thin `rectangle`s), axis labels on the
  edges, optional quadrant labels per cell, one dot+label per item at `(x,y)` normalized to the
  area (x left→right, y bottom→top). NOT `create_table`.
- **`pillars`** → a wide capstone `banner` on top + N tall column `rectangle`s below, each with
  icon + bold title + desc; equal-width columns.
- **`hub`** → a center shape + spoke shapes ringed around it, **real connectors** center↔spoke;
  icons via the icon loop.
- **`timeline`** → a horizontal axis (thin `rectangle` or connector) + a marker dot per milestone
  at its position, `label`+`desc` textboxes alternating above/below the axis.
- **`swimlane`** → a header row of `cols` labels + one tinted horizontal lane band per lane (lane
  `label` at the left, band in lane `color`); place each item as a `rounded_square` box in its
  `(lane, col)` cell on the grid. Equal column widths; NOT `create_table`.
- **`tree`** → the root node shape + child node shapes laid out below (`direction:"down"`) or
  right (`"right"`) of each parent, evenly spaced per subtree, with **real connectors**
  parent→child. Recurse to leaf; create parents before children so connectors anchor.
- **`venn`** → 2–3 overlapping `ellipse` shapes with **semi-transparent** fills so the overlaps
  blend — use an **8-digit alpha hex** for `background_color` (e.g. the role color + `2E` ≈ 18%,
  verified to render), a saturated stroke per set, a set-label textbox outside each, and the
  `overlapLabel` textbox on the intersection.
- **`spectrum`** → a horizontal track (thin `rectangle`) + a pole-label textbox at each end + a
  dot + label per marker positioned at its `at` (0–1) along the track.
- **`decision`** → one node shape per `nodes[]` by `kind` (`start`/`end`→`terminator`,
  `decision`→`decision`/rhombus, `process`→`process`/rectangle) + **real connectors** per
  `edges[]`; put each edge `label` ("Yes"/"No") as a **small textbox at the connector midpoint**
  (Mural connectors carry no text). See `shape-catalog.md`.
- **`rings`** → concentric `ellipse` shapes created **largest (outermost) first** so inner rings
  sit on top, each in its `color`, + a label per ring; `style:"bullseye"` centers them tightly as
  a target.
