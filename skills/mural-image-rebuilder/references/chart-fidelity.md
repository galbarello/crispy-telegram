# Chart & gauge fidelity — building `gauge` and `chart` blocks from primitives

Mural has no arc/wedge/donut/polyline primitive, so charts are **approximated** from shapes +
textboxes. The rule throughout: **the numeric value labels are the fidelity; the drawn shapes
are the approximation** — always keep the labels. Load this reference only when a build actually
includes a `gauge` or `chart` block (SKILL.md carries the one-line summary).

## `gauge` — dial / meter for a bounded KPI

A **gauge tile per item** (Mural has no arc/donut primitive, so approximate, and trust the
numeric `value` label for fidelity — not the arc). Two builds:

- **Linear meter (default — renders precisely):** a rounded track `rectangle` (light fill) + a
  filled `rectangle` on top whose width = `track_width × (value − min)/(max − min)` in the active
  zone's color (the `zones` band that contains `value`); the big `value``unit` (bold, active-zone
  color) + `label` above, `min`/`max` end-labels, optional `caption` below.
- **Radial dial (only to match a source that clearly shows a dial):** an `ellipse` with a thick
  `stroke_size` as the face + a thin rotated `rectangle` needle
  (`rotation ≈ 180·(value − min)/(max − min) − 90`) + the centered `value``unit`. Remember Mural
  rotates the needle about its **top-left corner, not its center** (see the line note below), so
  anchor the needle's pivot end deliberately rather than assuming it spins in place — and keep the
  value label as the source of truth, since the dial is approximate.

## `chart` — bar / line / pie

Build from primitives in a plot area (baseline/axis first, it renders under; bars/points next;
labels on top). **Always keep the value labels** — the numbers are the fidelity, the drawn shapes
are the approximation. Reserve a left gutter for the y-scale and a bottom band for category labels.

**Repeatable chart workflow:** (1) compute geometry with the helper for that chart type —
`scripts/line_chart.py` (line) or `scripts/pie_chart.py` (pie/composition); bar and gauge are
simple enough to place from the specs below. (2) Create the `area` first, then its children with
the returned id as `parent_id`, shapes-before-text so labels sit on top. (3) **Always run the
Layer-6 dedup check** — the Mural bridge often double-applies creates, silently doubling a
freshly-built chart; catch it by comparing `get_canvas_overview` to the intended count and clean
with `scripts/dedupe_widgets.py`. (4) Verify with `get_canvas_image` (reliable) rather than
per-widget screenshots (which lag right after creation).

### `bar` (renders precisely — the strong case)
One `rectangle` per value, height = `plot_height × value / maxValue`, sitting on the baseline in
the series `color`; category label (textbox) under each bar, value label above. Multi-series →
bars grouped per category, one color each, plus a legend (color chip + name).

### `line` (renders well — markers + value labels are exact; the connecting line is an approximation)
Treat it like `bar` for the frame (left y-gutter, bottom category band, baseline/axis drawn first
so it sits under the data), then plot points and join them.

- **Point coordinates.** For a series of `n` points, place point `i` at
  `x_i = plot_left + plot_width × i/(n − 1)` (evenly spaced; for a categorical x-axis use the same
  band centers as the bars would use) and
  `y_i = baseline − plot_height × (value_i − yMin)/(yMax − yMin)`, where `yMin`/`yMax` are the
  series' y-scale (usually `yMin = 0`). Larger value = higher on the canvas = smaller `y`. Reserve
  the left gutter for 2–3 y-scale tick labels and the bottom band for the x/category labels.
- **Markers.** One small `ellipse` (~10–12px) per point, created at `x = x_i − r, y = y_i − r` so
  it centers on the point. **Keep the numeric value label** (textbox just above each marker) — the
  markers and labels are the fidelity; the line between them is the approximation.
- **The connecting line — two builds:**
  - **Rotated-rectangle segments (default — precise color, no arrowheads):** for each consecutive
    pair `A=P_i → B=P_{i+1}` (`dx = x_{i+1} − x_i`, `dy = y_{i+1} − y_i`), create a thin
    `rectangle` (height `h` ≈ 2–3px) in the series color with `width = hypot(dx, dy)` and
    `rotation = degrees(atan2(dy, dx))`. **Anchor it at the START point A, NOT the midpoint —
    Mural rotates a shape about its top-left corner (the `x,y` you pass), not its center.** Set
    `x = A.x + (h/2)·sin(θ)`, `y = A.y − (h/2)·cos(θ)` (θ in radians); the box then spans length
    `L` along A→B and its far end lands on B. Anchoring at `(midx − width/2, …)` (the natural
    "center-rotation" guess) makes every sloped segment fly off its dots by up to `L/2` — a real
    bug that shipped once (lines not linking the markers). The `h/2` terms are sub-pixel; the
    load-bearing part is anchoring at A, not the midpoint.
  - **Connectors (`connect_widgets` `arrow_type:"straight"` between consecutive markers):** quicker
    and the segments stay attached when a marker moves, **but every connector draws an arrowhead
    and uses the default connector color** — there is no option to remove the head or set the line
    color. Use only when arrowheaded, default-colored segments are acceptable; otherwise prefer
    the rotated rectangles.
- **Multi-series:** repeat markers + line per series in its own color, and add a legend (color chip
  + series name), exactly as for grouped bars.
- **Area / filled-line charts:** Mural has no vertex-polygon fill, so a true shaded area under the
  curve isn't constructible — draw the line as above and say the fill is omitted (a flat light-fill
  `rectangle` band behind the plot is the only crude stand-in).
- There is no polyline widget: the line is always N−1 discrete segments (rectangles or connectors),
  not one path.
- **Don't hand-compute the trig — use `scripts/line_chart.py`.** Feed it a JSON spec (data values,
  `y_axis` min/max/step, `x_labels`, `series` name+color+values, and either an `area` to derive the
  layout from or explicit `plot` bounds). It emits create-ready arrays: `scaffold_shapes`
  (gridlines) and `legend_shapes` → `create_shapes`; `title` → `create_titles`; `textboxes`
  (y-labels, x-labels, subtitle, legend labels, optional `x_axis_title`) → `create_textboxes`; and
  `series.<name>` (segments then markers, in that order) → one `create_shapes` call each. It does
  the hypotenuse/rotation math per the rules above, carries `parent_id`, and uses absolute coords —
  so create the `area` first, then pass its id back as `parent_id`. `--part series.Cycle` prints
  just one array. This is the reusable form of the geometry; only hand-place for a trivial
  1-series, few-point chart.

### `pie` — no arc/wedge primitive exists (same limit as the gauge), so do NOT fake wedges
Build a **100%-stacked horizontal bar**: one `rectangle` segment per slice, width =
`bar_width × value / total`, in the slice color, laid end to end; plus a **legend** listing each
slice's color chip, `label`, and `value` (or %). State that a true pie isn't constructible from
Mural primitives. (A decorative pie `icon` may sit alongside, but the stacked bar + legend carries
the data.) **Use `scripts/pie_chart.py`** — feed it a JSON spec (`slices` of name+value+color, an
`area` or explicit `bar` geometry, optional `value_suffix`) and it emits create-ready arrays:
`bar_shapes` + `legend_shapes` → `create_shapes` (create first), `title` → `create_titles`,
`textboxes` (subtitle, inline `%` labels, legend labels) → `create_textboxes`. It does the
proportion math and carries `parent_id`; only hand-place for a trivial 2–3 slice bar.
