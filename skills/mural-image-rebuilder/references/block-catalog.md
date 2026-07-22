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
- **`gantt`** → a project schedule (tasks × time). Build in this order into an `area`
  (`showTitle:false`), reserving a **left gutter** for task labels and a **top band** for the axis;
  let `colW = plot_width / timeUnits.length` and positions map on the **0..N fractional scale**
  (0 = left of first unit, N = right of last):
  1. **Axis:** one `timeUnits` label textbox per column across the top (center each over its
     column — give the textbox a narrow width, since the default is wide and left-aligns) + a thin
     vertical gridline `rectangle` at each column boundary, spanning the rows. **Set `stroke_color`
     on every thin marker shape** — a 2–3px shape with `stroke_size:0` still picks up Mural's dark
     default border, so pass `stroke_color` = the intended line color (dark hairline gridlines read
     fine; a "today" line that inherits the default border looks like just another gridline).
  2. **Phase bands:** for each run of consecutive tasks sharing `group`, a tinted horizontal band
     (light role fill) behind those rows + the group label in the left gutter (like a swimlane lane).
  3. **Task rows** (fixed pitch): left-gutter `label` textbox; **bar** = a `rounded_square` in the
     task `color` at `x = plot_left + start·colW`, `width = (end − start)·colW`, centered in the
     row band; `percent` → an inner filled `rectangle` of `width·percent/100` + a "NN%" textbox.
  4. **Milestones:** an `at`-positioned `rhombus_smart` diamond on its row + the label.
  5. **Today line:** a **~6px** vertical `rectangle` at `plot_left + today·colW` spanning all
     rows, with **both `background_color` and `stroke_color`** set to the danger/accent color (so
     it reads red, not as a default-bordered hairline), + a "Today" label above it.
  6. **Dependencies (do last — the fragile part):** create **all** bars/milestones first, then
     **real connectors** (`connect_widgets`) predecessor→successor **by widget id** for each `deps`
     entry (elbow/straight, subtle color); anchoring only works once both endpoints exist. If the
     graph is dense, draw only the critical-path deps and say so.
  Keep the date/duration labels (positions are the fidelity, bars the approximation); NOT
  `create_table`.
- **`tree`** → the root node shape + child node shapes laid out below (`direction:"down"`) or
  right (`"right"`) of each parent, evenly spaced per subtree, with **real connectors**
  parent→child. Recurse to leaf; create parents before children so connectors anchor.
- **`mindmap`** → an organic radial idea map (distinct from `tree`'s strict hierarchy and `hub`'s
  single ring). Build center-out:
  1. **Root:** a prominent central node (`rounded_square` or `ellipse`, larger, `root.color`, bold
     label) placed at the map center.
  2. **Branches:** distribute the branches **radially** around the root — for a landscape board,
     **balance them left/right** (alternate sides, stacking vertically) rather than a full 360°
     ring; each branch a node in its own `color` at a radius from center.
  3. **Sub-nodes:** fan each branch's `children` out **beyond** their branch node (further from
     center, same side), spaced evenly.
  4. **Links (two steps):** create **real connectors** with `arrow_type:"curve"` (root→branch,
     then branch→child), then **color them in a second pass** — `create_connectors` has **no color
     param**, so `update_widgets` each connector's `strokeColor` (+ `strokeWidth`≈3) to its
     **branch color**. The branch color carrying the whole sub-tree is what makes it read as a
     mind-map. Create every node before its connectors so they anchor (see the gantt deps note);
     curved links read as organic — avoid orthogonal elbows here.
  Keep depth ≤ 2–3 and ~6 branches for legibility; NOT `create_table`.
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
- **`nest`** → a **containment / wrapping** hierarchy (box inside a box). Build as **nested
  `area`s**: create the outer node's area first, then each child's area *inside* it (create
  outer→inner so inner frames render on top; Mural auto-parents a child area created within an
  outer area's bounds, so the group moves as a unit), recursing. Each node = an area (or a filled
  `rounded_square` when `kind:"callout"`) + a header textbox (`**label**` in the node's color, ` ·
  meta` muted) + a `desc` textbox; `layout:"row"` splits the inner width for side-by-side children,
  `column` stacks them. **Size bottom-up** — a container's height is header + desc + its children's
  extent + padding — so parents fit their children exactly. **Never flatten containment into a flat
  `cards` grid** (it destroys the hierarchy — a real bug where a nested "moving parts" section came
  out as 5 equal cards). `scripts/compile_board.py` compiles `nest` directly.
