# board-spec — the shared contract

`board-spec` is a JSON document that fully describes a board/infographic's content and
structure. Muralize emits it; `mural-image-rebuilder` consumes it to build a Mural board
with no vision step. The HTML infographic is rendered from the same spec.

Design goals: **lossless** (verbatim text, exact counts), **primitive-aligned** (every block
maps to a rebuilder tool), **color-by-role** (no scattered hex).

## Top-level shape

```json
{
  "meta": {
    "eyebrow": "PRODUCT STRATEGY · Q3 CASE STUDY",
    "title": "MURAL v3",
    "subtitle": "Turning visual collaboration into structured, AI-ready workflows",
    "tags": ["100% local", "no API", "hybrid: probe → UI"],
    "pattern": "strategy-framework",
    "orientation": "portrait",
    "theme": "brand",
    "palette": {
      "primary": "#195AD7", "success": "#00C27A", "warning": "#FFAA00",
      "danger": "#FF4B4B", "accent": "#8728E6", "surface": "#F0F0F0", "ink": "#202124"
    }
  },
  "sections": [ /* Section objects, in reading order */ ]
}
```

- `eyebrow` *(optional)*: the small kicker/label line **above** the title (e.g. a category
  or "… CASE STUDY"). Part of the header identity — if the infographic shows one, it MUST be
  here so the board reproduces it. Omit only when there is genuinely no kicker.
- `title`: the hero headline. **Rendered in the exact casing given here** — do not force
  upper/lower case in either output. If you want an all-caps look, write it all-caps in the
  spec; if you want title case, write title case. Both outputs must match the spec verbatim.
- `subtitle`: the one-line description under the title.
- `tags` *(optional)*: short header chips shown as a row **below** the subtitle (e.g. status
  or scope pills). Same rule as `eyebrow` — anything the infographic renders as header chips
  belongs here so the board matches.
- `pattern`: `timeline | matrix | dashboard | strategy-framework | mixed` (shared taxonomy).
- `orientation`: `portrait | landscape` — hints the rebuilder's canvas/grid.
- `theme` *(optional, default `"brand"`)*: which stylesheet the `palette` roles resolve from —
  `"brand"` (mural.co marketing, `brand-palette.md`) or `"product"` (Mural UI-Toolkit data-viz,
  `dataviz-palette.md`). Pick per the SKILL.md Layer-3 selection rule (default `brand`; prompt the
  user for dashboards/data-viz). Both outputs read the same `theme`, so they never drift.
- `palette`: semantic color **roles**. Blocks reference roles (e.g. `"color": "success"`),
  never raw hex. One place to re-theme both outputs. The hex must match the selected `theme`'s
  reference file — **default = the Mural brand palette** (the hex above); for `theme:"product"`
  resolve from `dataviz-palette.md` (`primary`→Blueberry `#5B83D2`, `accent`→Grape `#846CE0`,
  system roles unchanged, `surface`→`#F7F7F7`).

**Header / hero — render identically in both outputs.** The header is `eyebrow` → `title` →
`subtitle` → `tags`, top to bottom. The HTML and the Mural board both build it from these
fields, so the "first line" (the eyebrow) and the chip row can never be present in one output
and missing from the other. Rendering:
- HTML: eyebrow as a small letter-spaced label in the accent role; title at the display size;
  subtitle muted; tags as pill/chip elements.
- Mural (rebuilder): eyebrow as a small textbox (accent color, ~13px) placed **above** the
  title widget; title as a `title` widget in the spec's casing; subtitle as a muted textbox;
  each tag as a small `rounded_square`/chip shape in a row beneath the subtitle. See the
  rebuilder's "Consuming a board-spec" mapping.

## Section object

```json
{
  "id": "strategy-validation",
  "title": "FROM THEORY TO IMPACT: OUR STRATEGY VALIDATION SYSTEM",
  "grid": { "row": 2, "col": "full" },
  "block": { /* one Block, see below */ }
}
```

- `title`: rendered as a heading widget (the rebuilder hides the area's built-in title and
  places this in the reserved top band).
- `grid`: coarse placement — `row` (1-based) + `col` (`full | left | right | 1..N`), or an
  explicit `{ "x","y","w","h" }` if you need precision. The rebuilder turns each section into
  an `area` and lays content inside.

## Block types (each maps to a rebuilder primitive)

### flow — sequential steps or a loop
```json
{ "type": "flow", "shape": "step", "loop": false,
  "steps": [
    { "n": 1, "label": "VISION", "desc": "Our long-term belief…", "icon": "telescope", "color": "accent" }
  ] }
```
Rebuilder: one shape per step (`shape`: `step | circle | rounded_square`), icon centered
(icon-matching loop), **real connectors** between steps (`loop:true` closes the cycle). Never
glyph arrows.

### table — matrix / comparison grid
```json
{ "type": "table",
  "columns": [
    { "label": "THEME",                   "color": "accent"  },
    { "label": "KEY QUESTIONS",           "color": "primary" },
    { "label": "EXAMPLES OF EXPERIMENTS", "color": "success" },
    { "label": "PRIMARY KPIS",            "color": "warning" }
  ],
  "rows": [
    { "cells": [    /* a bare list [cell, cell, ...] is also accepted for a row */
      { "text": "Understand", "badge": "1", "icon": "telescope", "color": "accent" },
      { "bullets": ["What problems exist?", "What's changing with AI?"] },
      { "chips": ["Customer interviews", "Journey mapping"] },
      { "coloredText": "Medium", "color": "warning" }
    ] }
  ] }
```
**Columns.** `columns` is one entry per column, either a bare string (label only, neutral
column) or an object `{ "label", "color"?, "tint"? }`. `color` is a palette role = the
**column's hue**: the **header cell** renders in that role (saturated) and the **column body**
renders a light derivation of it, so each column reads as color-coded like a real strategy
table. Optional `tint` (a role) overrides the derived body fill. **Reproduce the source's
per-column colors here** — bare-string columns fall back to a single neutral header band, which
is the fallback, not the goal.

**Cells.** Variants: `text`, `bullets` (→ one textbox with `•` lines), `chips` (→ **one chip
shape per item**, laid out in a row across the cell — never one joined string), `coloredText`
(→ colored text). `fill`/`color` reference palette roles.

**Leading-label cell extras** (the row-header column): `badge` (optional, a short marker like
`"1"` → rendered as a number badge) and `icon` (optional, a concept name like `"telescope"` →
a **real searched icon**, tinted to the column color — resolved via the rebuilder's icon loop,
never an emoji). Together they give the rebuilder the **badge → icon → name** row-label
treatment.

Rebuilder builds the whole table as **area-nested chips + textboxes on a grid — NOT
`create_table`** (its cells render empty), reproducing the per-column header colors, column
tints, chip layout, and row-label badges/icons. Full recipe:
`../mural-image-rebuilder/references/table-fidelity.md`.

### cards — repeated titled items (1+ columns)
```json
{ "type": "cards", "columns": 2,
  "items": [
    { "title": "Customer Context Platform", "desc": "Identity graph, calendar, permissions…",
      "meta": "Feeds: 1,2,4,5,7", "icon": "database", "color": "primary" }
  ] }
```
Rebuilder: title (bold, colored) + desc + optional `meta` line + optional icon, laid out in
`columns`. Used for framework lists, KPI tiles, principles, etc.

### metrics — metric tiles
```json
{ "type": "metrics", "items": [
  { "title": "Learning Velocity", "desc": "Time from hypothesis to decision", "icon": "trophy", "color": "success" }
] }
```

### gauge — dial / meter for a bounded KPI
Use for a **single value read against a min–max scale** ("how are we doing" on one number):
CDN cache hit rate, adoption %, health score, capacity used. Not for an unbounded count (that's
a `metrics` tile) or a comparison of many series (that's a chart — see `dataviz`).
```json
{ "type": "gauge", "columns": 3,
  "items": [
    { "label": "CDN Cache Hit Rate", "value": 87, "min": 0, "max": 100, "unit": "%",
      "zones": [
        { "upTo": 50, "color": "danger" },
        { "upTo": 80, "color": "warning" },
        { "upTo": 100, "color": "success" }
      ],
      "caption": "Up from 62% last sprint" }
  ] }
```
- `value` / `min` / `max` are numbers; `unit` is an optional suffix (`%`, `ms`, `k`). `label`
  names the metric; `caption` is an optional sub-line (trend, target). One or more `items`
  laid out in `columns` (like `metrics`).
- `zones` *(optional)*: ordered bands from `min` upward, each `{ "upTo", "color" }` where
  `color` is a palette role — the segment of the scale up to `upTo` uses that color. The band
  containing `value` is the gauge's "active" color. Omit `zones` for a single-color meter.
- **Render identically from these fields in both outputs** (keystone principle):
  - HTML: a real SVG **semicircular arc gauge** — a track arc, the value arc filled to
    `value/max` in the active zone color, a needle, and the big `value``unit` centered. Follow
    the `dataviz` skill for arc colors and contrast.
  - Mural (rebuilder): Mural has no arc primitive, so build a **gauge tile** — see the
    rebuilder's `gauge` mapping. Trust the numeric `value` label for fidelity; the arc/needle
    is an approximation.

### chart — bar / line / pie
Use to **compare values across categories or series**: trend over time (line), category
comparison (bar), part-to-whole (pie). For a single bounded number use `gauge`; for a headline
number use a `metrics` tile.
```json
{ "type": "chart", "chartType": "bar", "title": "Weekly deploys", "yUnit": "",
  "categories": ["Mon", "Tue", "Wed", "Thu", "Fri"],
  "series": [
    { "name": "Deploys", "color": "primary", "values": [3, 5, 4, 8, 6] }
  ] }
```
```json
{ "type": "chart", "chartType": "line", "title": "p95 latency (ms)",
  "categories": ["W1", "W2", "W3", "W4"],
  "series": [
    { "name": "Before", "color": "warning", "values": [320, 300, 290, 280] },
    { "name": "After",  "color": "success", "values": [210, 180, 150, 140] }
  ] }
```
```json
{ "type": "chart", "chartType": "pie", "title": "Bundle composition",
  "slices": [
    { "label": "App code", "value": 62, "color": "primary" },
    { "label": "Vendor",   "value": 28, "color": "accent" },
    { "label": "Other",    "value": 10, "color": "surface" }
  ] }
```
- `chartType`: `bar | line | pie`.
- **bar / line:** `categories` = x-axis labels; `series` = one or more `{ name, color, values }`
  (`values` length must equal `categories` length; `color` is a palette role — omit to cycle the
  palette). `yUnit` optional. Multiple series → grouped bars / multiple lines with a legend.
- **pie:** `slices` = `{ label, value, color }` list; values are summed for the whole. Keep the
  slice count small (≤6).
- **Verbatim numbers.** `values`/`value` are the real data — never round or invent to make a
  chart look tidy; if a number is unknown, mark the block `"draft": true` and flag it.
- **Render from these fields in both outputs** (keystone principle):
  - HTML: a real inline **SVG chart** (bars / polyline / pie slices) with axis, labels, and a
    legend for multi-series — follow the `dataviz` skill for palette, axis, and contrast.
  - Mural (rebuilder): built from primitives — bars render precisely; lines are point markers +
    connectors; **pie has no arc primitive, so it becomes a 100%-stacked bar + legend** (see the
    rebuilder's `chart` mapping). Always keep value labels so the data is exact.

### banner — full-width emphasis bar
```json
{ "type": "banner", "text": "OUR OPERATING PRINCIPLE — Meet customers where they are…", "style": "dark" }
```
Rebuilder: a filled rectangle + centered text (`style`: `dark | light | accent`).

### callout — highlighted note
```json
{ "type": "callout", "label": "KEY DIFFERENCE", "text": "We are not committed to being right…", "color": "warning" }
```

### comparison — two (or N) labeled parallel columns (e.g. Old Way vs New Way)
```json
{ "type": "comparison", "connector": "arrow-down",
  "columns": [
    { "label": "Old Way (Feature-Driven)", "color": "danger",
      "items": ["Build Features", "Hope They Solve the Right Problem", "Measure Adoption"] },
    { "label": "New Way (Learning-Driven)", "color": "success",
      "items": ["Test Assumptions", "Increase Confidence or Change Direction", "Invest Where Evidence Shows Impact"] }
  ] }
```
Contrast two paths/eras/options. Each column = a header title (colored) + a vertical stack of
box shapes in that column's `color`, joined top→bottom by **real connectors** when
`connector` is `arrow-down` (omit for plain boxes). Rebuilder: N side-by-side columns of
`rounded_square` boxes + connectors; HTML: flex columns with a `↓` between boxes. Pair with a
`callout` for the "key difference".

### cycle — a closed reinforcing loop (evidence loop, flywheel)
```json
{ "type": "cycle", "style": "loop",
  "steps": [
    { "n": 1, "label": "HYPOTHESIZE", "desc": "Define the assumption to test.", "icon": "flask", "color": "accent" },
    { "n": 2, "label": "EXPERIMENT", "desc": "Design the smallest experiment.", "color": "primary" },
    { "n": 3, "label": "EVIDENCE", "desc": "Collect and interpret data.", "color": "success" },
    { "n": 4, "label": "DECIDE", "desc": "Scale, pivot, or stop.", "color": "warning" }
  ] }
```
Use when steps **loop back** (vs a `flow`, which ends). Nodes placed around a circle (or 2×2)
with **real connectors closing the cycle** (last → first). `style`: `loop` (default) or
`flywheel` (momentum — curved arrows, emphasize acceleration). Rebuilder: node shapes +
looping connectors; HTML: radial SVG or 2×2 with curved arrows.

### chips — a row/cloud of labeled pills (falsification list, factor tags, options)
```json
{ "type": "chips", "color": "danger",
  "items": ["Same top problems at every maturity level", "Activation patterns are identical",
            "Adoption clusters by role, not maturity", "Industry explains behavior better"] }
```
Several short peer labels with no order/flow (things to falsify, forces at play, candidate
options). One small `rounded_square` pill per item in a **wrapping row**, filled with `color`
(light). Items may be objects `{ "label", "color" }` for per-chip color. Never collapse into
one string.

### pyramid — stacked hierarchy layers
```json
{ "type": "pyramid", "direction": "up",
  "layers": [ { "label": "Vision", "color": "accent" }, { "label": "Strategy", "color": "primary" },
              { "label": "Execution", "color": "success" } ] }
```
A layered hierarchy where width encodes scope (broad base → narrow apex). `direction`: `up`
(apex on top, default) or `down`. Rebuilder: stacked `trapezoid`/`triangle_smart` segments of
graded width + centered label textboxes; HTML: CSS/SVG trapezoids. Use for maturity ladders,
Maslow-style stacks, strategy layers.

### funnel — narrowing stages with drop-off
```json
{ "type": "funnel",
  "stages": [ { "label": "Visitors", "value": 1000, "color": "primary" },
              { "label": "Signups", "value": 300 }, { "label": "Activated", "value": 120 },
              { "label": "Paying", "value": 40 } ] }
```
Sequential stages where each is a subset of the prior (conversion, pipeline drop-off). Segment
width ∝ `value`. Rebuilder: stacked shapes of decreasing width top→bottom + `value`/`label`;
HTML: SVG funnel. **Verbatim numbers** — never invent to smooth the taper.

### quadrant — 2×2 positioning on two axes
```json
{ "type": "quadrant",
  "xAxis": { "low": "Low Effort", "high": "High Effort" },
  "yAxis": { "low": "Low Impact", "high": "High Impact" },
  "quadrantLabels": ["Fill-ins", "Quick Wins", "Money Pit", "Big Bets"],
  "items": [ { "label": "Feature A", "x": 0.2, "y": 0.8, "color": "success" } ] }
```
Position items by two dimensions (impact/effort, reach/confidence). Distinct from `table`
(that's a data grid). `quadrantLabels` order: `[bottom-left, bottom-right, top-left,
top-right]`. Item `x`/`y` are 0–1 (left→right, bottom→top). Rebuilder: an `area` split by a
crosshair (two thin rectangles), axis labels on the edges, quadrant labels in each cell, one
small dot+label shape per item at its coords; HTML: SVG axes + positioned dots.

### pillars — vertical columns supporting a capstone
```json
{ "type": "pillars", "capstone": "AI-Native Collaboration",
  "columns": [
    { "title": "Enable Learning", "desc": "Experimentation platform, telemetry.", "icon": "flask", "color": "primary" },
    { "title": "Provide Building Blocks", "desc": "Shared capabilities teams reuse.", "icon": "blocks", "color": "accent" }
  ] }
```
A foundation metaphor: N columns (each icon + title + desc) holding up a `capstone` bar. Like
`cards`, but with the explicit "these support X" reading. Rebuilder: a wide capstone `banner`
on top + N tall column `rectangle`s below, each with icon+title+desc; HTML: header bar + flex
columns. (Omit `capstone` for a plain foundation strip.)

### hub — central node with radiating spokes
```json
{ "type": "hub",
  "center": { "label": "Customer", "icon": "people", "color": "accent" },
  "spokes": [ { "label": "Identity", "color": "primary" }, { "label": "Calendar" }, { "label": "Permissions" } ] }
```
One core concept feeding/feeding-from several satellites (a platform + its inputs, a team + its
stakeholders). Rebuilder: a center shape + spoke shapes around it, **real connectors**
center↔spoke; HTML: radial SVG.

### timeline — horizontal axis with milestones
```json
{ "type": "timeline",
  "milestones": [ { "at": "Q1", "label": "Kickoff", "desc": "Charter + team", "color": "primary" },
                  { "at": "Q2", "label": "Beta", "desc": "First cohort", "color": "accent" },
                  { "at": "Q3", "label": "GA", "desc": "Public launch", "color": "success" } ] }
```
Dated/positioned events along a continuous axis (distinct from `flow`, which is stage-to-stage
with no axis). Rebuilder: a horizontal axis line (thin rectangle or connector) + a marker dot
per milestone at its position, label+desc alternating above/below; HTML: SVG axis + markers.

### swimlane — items across lanes × columns (roadmap / now-next-later / process-by-actor)
```json
{ "type": "swimlane", "cols": ["Now", "Next", "Later"],
  "lanes": [
    { "label": "Platform", "color": "primary",
      "items": [ { "col": 0, "text": "Identity graph" }, { "col": 1, "text": "Context service" } ] },
    { "label": "AI", "color": "accent",
      "items": [ { "col": 0, "text": "Recap in sessions" }, { "col": 2, "text": "Autonomous follow-up" } ] }
  ] }
```
A grid of **lanes (workstreams/actors, rows) × columns (time/phases/horizons)** — a roadmap,
now-next-later, or a process split across actors. Distinct from `timeline` (one track) and
`table` (a data/comparison grid). Rebuilder: a header row of `cols` labels; one tinted
horizontal lane band per lane (label at left); each item a `rounded_square` box placed in its
`(lane, col)` cell. HTML: CSS grid (rows = lanes, cols = cols). Item `col` is a 0-based column
index; omit lanes/cells that are empty.

### gantt — project schedule: tasks with durations on a time axis
```json
{ "type": "gantt",
  "timeUnits": ["Q1", "Q2", "Q3", "Q4"],
  "today": 2.3,
  "tasks": [
    { "id": "disc",  "label": "Discovery", "group": "Foundations", "start": 0, "end": 1,   "percent": 100, "color": "primary" },
    { "id": "build", "label": "Build",      "group": "Foundations", "start": 1, "end": 3,   "percent": 40,  "color": "accent",  "deps": ["disc"] },
    { "id": "test",  "label": "Test",       "group": "Launch",      "start": 3, "end": 3.7, "percent": 0,   "color": "warning", "deps": ["build"] },
    { "id": "ga",    "label": "GA launch",  "group": "Launch",      "at": 3.7,  "milestone": true,          "color": "success", "deps": ["test"] }
  ] }
```
A **project/delivery schedule** — tasks with **durations** laid as horizontal bars along a time
axis, optionally with phases, progress, milestones, a "today" line, and dependencies. Distinct
from `timeline` (point milestones, no durations), `swimlane` (categorical lane×column cells, no
continuous bars), and `chart` bar (magnitude from a baseline, not a start→end span).

**Coordinate model:** positions are on a **fractional 0..N scale** where `N = timeUnits.length`
(0 = left edge of the first unit, N = right edge of the last). `start`/`end`/`at`/`today` all use
it. Fields: `timeUnits[]` (ordered column headers = the axis); each task has an `id` (referenced
by `deps`), a `label`, an optional `group` (phase band); a **bar** via `start`+`end` **or** a
**milestone** via `at`+`milestone:true`; optional `percent` (0–100 progress), `color` (palette
role), and `deps` (array of predecessor task `id`s → dependency arrows). `today` is optional.

Rebuilder: an `area` frame with a left label gutter + a top axis header; a duration `rounded_square`
per task (inner fill for `percent`), diamond for milestones, tinted phase bands, a vertical "today"
rectangle, and **real connectors** for `deps` (created after all bars exist). HTML: a CSS grid of
task rows × time columns with positioned bars + an SVG overlay for dependency arrows. See
`../mural-image-rebuilder/references/block-catalog.md` for the full build recipe.

### tree — multi-level hierarchical branching (org chart / decomposition / breakdown)
```json
{ "type": "tree", "direction": "down",
  "root": { "label": "AI-Native Collaboration", "color": "accent" },
  "children": [
    { "label": "Enable Learning", "color": "primary",
      "children": [ { "label": "Telemetry" }, { "label": "Experiment platform" } ] },
    { "label": "Provide Building Blocks", "color": "success", "children": [ { "label": "Context service" } ] }
  ] }
```
A parent→child hierarchy of arbitrary depth (org chart, work breakdown, decomposition).
Distinct from `hub` (single-level radial). `direction`: `down` (default) or `right`. Rebuilder:
the root node shape + recursively placed child node shapes, **real connectors** parent→child;
lay children out below (or right of) their parent with even spacing. HTML: nested CSS/SVG tree
with connector lines. Keep depth ≤ 3–4 for legibility.

### mindmap — central topic with organic radiating branches
```json
{ "type": "mindmap",
  "root": { "label": "AI-Native Collaboration", "color": "accent" },
  "branches": [
    { "label": "Enable Learning", "color": "primary",
      "children": [ { "label": "Telemetry" }, { "label": "Experiment platform" } ] },
    { "label": "Building Blocks", "color": "success",
      "children": [ { "label": "Context service" }, { "label": "Widget SDK" } ] },
    { "label": "Guardrails", "color": "warning",
      "children": [ { "label": "Permissions" } ] }
  ] }
```
A **brainstorm/mind map**: one central topic with branches radiating outward, each branch (and its
sub-nodes) in a distinct **branch color**, connected by curved links. Use for an organic idea map
rooted on one concept. Distinct from `tree` (a strict top-down/left-right hierarchy with
orthogonal lines) and `hub` (a single ring of spokes with no sub-levels). Each branch carries a
`color` that its whole sub-tree inherits; keep depth ≤ 2–3 and branch count ≤ ~6 for legibility.
Rebuilder: a prominent central `root` node + branch nodes distributed **radially** (balanced
left/right for a landscape board) with **curved connectors** (`arrow_type:"curve"`) in each
branch's color; children fan out beyond their branch, connected in the same color; create parents
before children so links anchor. HTML: a central node with curved branch-colored SVG paths
radiating out, children fanning beyond each branch. See
`../mural-image-rebuilder/references/block-catalog.md` for the full build recipe.

### venn — intersecting sets with a shared region
```json
{ "type": "venn", "overlapLabel": "Sweet spot",
  "sets": [ { "label": "Desirable", "color": "primary" }, { "label": "Feasible", "color": "success" },
            { "label": "Viable", "color": "warning" } ] }
```
Two or three overlapping sets whose **intersection** is the point (desirable ∩ feasible ∩
viable, people ∩ process ∩ tech). Rebuilder: 2–3 overlapping `ellipse` shapes with light,
semi-transparent fills in each set's `color` + a set-label textbox outside each circle + the
optional `overlapLabel` textbox centered on the intersection. HTML: overlapping SVG circles with
a multiply/blend so the overlap reads. Keep to 2–3 sets.

### spectrum — qualitative position(s) between two poles
```json
{ "type": "spectrum", "poles": ["Build", "Buy"],
  "markers": [ { "label": "Auth", "at": 0.15, "color": "primary" },
               { "label": "Search", "at": 0.7, "color": "accent" } ] }
```
Place one or more labels along a **continuum between two named poles** (build↔buy,
centralized↔federated, low↔high maturity). Distinct from `gauge` (a single numeric value on a
min–max dial) — a spectrum is qualitative positioning, often of several items. `markers[].at`
is 0–1 (left pole → right pole). Rebuilder: a horizontal track (thin `rectangle`, optionally a
gradient) + a pole-label textbox at each end + a dot+label per marker at its `at`. HTML: a
gradient bar with absolutely-positioned markers.

### decision — branching flowchart with gates (yes/no)
```json
{ "type": "decision",
  "nodes": [
    { "id": "start", "kind": "start",    "label": "New change" },
    { "id": "q1",    "kind": "decision", "label": "Reversible?" },
    { "id": "ship",  "kind": "process",  "label": "Ship it" },
    { "id": "rev",   "kind": "process",  "label": "Review first" }
  ],
  "edges": [ { "from": "start", "to": "q1" },
             { "from": "q1", "to": "ship", "label": "Yes" }, { "from": "q1", "to": "rev", "label": "No" } ] }
```
A process with **branches / decision gates** — not expressible by `flow` (linear) or `cycle`
(loop). Node `kind` → shape: `start`/`end` → `terminator`, `decision` → `decision` (rhombus),
`process` → `process` (rectangle). Rebuilder: one node shape per `nodes[]` + **real connectors**
per `edges[]`; render each edge `label` (e.g. "Yes"/"No") as a **small textbox placed at the
connector's midpoint** — Mural connectors carry no text of their own. Uses the flowchart shapes
in the rebuilder's `references/shape-catalog.md`. HTML: an SVG flowchart. Never fake arrows with
glyphs.

### rings — concentric layers around a core (onion / bullseye)
```json
{ "type": "rings", "style": "onion",
  "rings": [ { "label": "Core product", "color": "accent" }, { "label": "Platform", "color": "primary" },
             { "label": "Ecosystem", "color": "success" } ] }
```
**Nested containment or priority rings** — a core surrounded by layers (product → platform →
ecosystem), or a bullseye of priorities. Distinct from `pyramid` (stacked bands) and `hub`
(spokes). `rings` are listed **innermost → outermost**; `style`: `onion` (concentric layers) or
`bullseye` (priority target, innermost = top priority). Rebuilder: concentric `ellipse` shapes
created **largest first** (so inner rings sit on top), each in its `color`, + a label per ring;
HTML: nested SVG circles.

## Icons

Reference icons by **concept name** (`telescope`, `flask`, `people`, `rocket`, `shield`,
`database`, …). The rebuilder resolves each via its icon-matching loop (search → inspect
previews → verify). Optionally pre-resolve: `"icon": { "concept": "telescope", "noun_project_id": 8437012 }`
to skip the search.

## Rules

- **Verbatim text.** Copy the wording; don't paraphrase silently. Mark unfinished content
  `"draft": true`.
- **Exact counts.** `steps`, `rows`, `chips`, `items` lengths must match the intended board —
  the rebuilder trusts them literally.
- **Color by role only.** Every `color`/`fill` is a `meta.palette` key.
- **Reading order = array order.** Sections and items build in the order listed.
