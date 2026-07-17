---
name: muralize
description: turn a brainstorm or conversation into a shareable infographic (self-contained HTML) AND a structured board-spec that mural-image-rebuilder builds into a Mural board losslessly (no OCR). use when synthesizing a discussion, brainstorm, or notes into a strategy infographic, or when going from conversation to a Mural board.
---

# Muralize

## Overview

Turn a conversation / brainstorm into two aligned artifacts:

1. **An infographic** — a self-contained HTML page (rendered via the Artifact tool),
   styled like a dense strategy infographic (color-coded sections, flows, chip-tables,
   icons). Shareable, theme-aware, editable.
2. **A `board-spec`** — a structured JSON description of the same content
   (`references/board-spec.md`).

```
conversation / brainstorm
        │   muralize
        ▼
infographic.html   +   board-spec.json
        │   mural-image-rebuilder (reads the spec — no vision)
        ▼
   live Mural board (exact text & structure)
```

**Keystone principle: the `board-spec` is the single source of truth; the HTML is rendered
from it.** Both the infographic and the Mural board come from the same structure, so they
never drift. Because `mural-image-rebuilder` consumes the spec directly, the pipeline is
**lossless** — none of the OCR/vision errors (garbled text, miscounted cells, wrong shape
types) that come from re-reading a raster.

## When to use

- Someone says "turn this discussion / these notes / this brainstorm into a board / infographic."
- You've just facilitated or transcribed a brainstorm and want a synthesized visual.
- You want a conversation to end up as a Mural board and want it faithful, not approximated.

Do NOT use this to rebuild an EXISTING image — that's `mural-image-rebuilder` (image → board).
Muralize is the upstream half (conversation → spec + infographic).

## Shared vocabulary

Muralize speaks the SAME language as `mural-image-rebuilder` so the two compose cleanly:

- The dominant-pattern taxonomy: `timeline`, `matrix`, `dashboard`, `strategy-framework`, `mixed`.
- Widget/shape names from `../mural-image-rebuilder/references/widget-selection.md` and
  `shape-catalog.md` (e.g. a chevron step is `step`, a matrix is area-nested chips + text —
  never `create_table`, flows use real connectors).
- Icons are named by concept (e.g. `telescope`, `flask`, `people`); the rebuilder resolves
  them with its icon-matching loop, or muralize may pre-resolve `noun_project_id`s.

For visual quality of the HTML, follow the `artifact-design` skill; for any charts/color,
follow `dataviz`.

## Workflow (layers)

### Layer 0 — Harvest & cluster
- Read the whole conversation/brainstorm end to end.
- Extract the raw material: ideas, decisions, data points, questions, quotes.
- Affinity-map into themes; dedupe; drop tangents. Keep the participants' own wording where
  it carries meaning.

### Layer 1 — Pattern & information architecture
- Choose the dominant infographic **pattern** from the shared taxonomy.
- Lay out the **sections**: title, section list, hierarchy, reading order, and a grid
  (rows/columns) with generous gutters. This becomes `board-spec.sections[].grid`.

### Layer 2 — Content per section (verbatim-biased)
- Write each section's headline + copy, condensed but faithful to the source.
- **Never invent facts to fill a section.** If the brainstorm didn't cover something, mark
  it `"draft": true` or leave a `"gap"` note rather than fabricating. Surface gaps to the user.

### Layer 3 — Visual system
- Define semantic color roles (`primary`, `success`, `warning`, `danger`, `surface`, …) once,
  in `meta.palette` — the HTML and the eventual Mural board both reference these roles, not
  scattered hex. **Use the Mural brand palette as the default baseline** (role hex + brand token
  library + inline CSS vars in `references/brand-palette.md`); only theme away from it when the
  user asks. Validate contrast (`warning`/light tints take dark `ink` labels, never white body).
- Plan icons per section (concept names).

### Layer 4 — Emit the `board-spec`
- Produce the full `board-spec` JSON per `references/board-spec.md`. This is the source of
  truth. Every block uses a type that maps to a rebuilder primitive. Pick the block whose
  **visual metaphor** matches the relationship (see `references/infographic-patterns.md`):
  `flow` (sequence), `decision` (branching flow), `cycle` (loop/flywheel), `comparison` (vs),
  `table` (matrix), `quadrant` (2×2), `swimlane` (lanes × columns / roadmap), `timeline` (dated
  axis), `gantt` (schedule/plan with durations), `pyramid`/`funnel` (hierarchy/narrowing),
  `pillars`/`hub`/`tree`/`mindmap`/`rings` (structure),
  `venn` (overlap), `spectrum` (continuum), `cards`/`metrics`/`chips` (parallel items),
  `gauge`/`chart` (quantified), `banner`/`callout` (emphasis).
- **Capture the header/hero in `meta`, not just in the HTML.** Any eyebrow/kicker line, the
  title (in its exact casing), the subtitle, and any header chips go in `meta.eyebrow` /
  `meta.title` / `meta.subtitle` / `meta.tags`. If the infographic shows a "first line"
  eyebrow or a row of chips, they MUST be in the spec — otherwise the board can't reproduce
  them and the two outputs drift (the header is the most common drift point). Do not add
  header chrome in Layer 5's HTML that has no home in the spec.

### Layer 5 — Compose the infographic (HTML) from the spec
- Render the spec to a self-contained HTML page (inline CSS, embedded SVG icons, no external
  assets — the Artifact tool's CSP forbids remote resources). Theme-aware (light/dark).
- **Treat the HTML as a first-class, productized artifact — NOT a preview of the Mural board.**
  It runs in a browser, so it is **not** bound by Mural-primitive limits: render **real** SVG
  donuts/gauge arcs, area-filled line charts, gradients, and shadows (the board *approximates*
  these — the HTML must not). Aim for **dashboard-grade density**, a systematic type/spacing/
  elevation scale, **one** consistent icon set, and `tabular-nums` on all data. This is the main
  lever for closing the quality gap with hand-made/AI-image infographics. Follow
  `references/html-quality.md` (design baseline + real-SVG chart recipes + polish checklist) and
  the `artifact-design` skill.
- Render any `table` block with **per-column header colors + column tints** from each
  `columns[].color` (saturated header cell, light column body), `chips` as individual pills in a
  row, and the leading column's `badge` + `icon` — the same coloring/structure the Mural board
  builds, so the infographic and board don't drift on the table.
- Render any `gauge` block as an inline **SVG semicircular arc gauge** (track arc + value arc
  filled to `value/max` in the active `zones` color + needle + centered `value``unit`),
  following the `dataviz` skill for arc color and contrast. Drive it from the same `value` /
  `min` / `max` / `zones` the board reads — never hardcode the arc.
- Render any `chart` block as an inline **SVG chart** — bars, a polyline (line), or pie slices
  per `chartType` — with axis, category/value labels, and a legend for multi-series, following
  the `dataviz` skill. Drive geometry from the block's `categories`/`series`/`slices`;
  never hardcode bar heights or slice angles.
- Render the **metaphor blocks** so the HTML reads like the board (same structure, so they don't
  drift): `comparison` → flex columns of stacked boxes with `↓` between; `cycle` → nodes around
  a ring (or 2×2) with SVG loop arrows (curved for `flywheel`); `chips` → a flex-wrap row of
  colored pills; `pyramid`/`funnel` → stacked CSS/SVG trapezoid bands (width by layer/`value`);
  `quadrant` → a CSS grid with axis labels + positioned dots; `pillars` → a capstone bar over
  flex columns; `hub` → a radial SVG (center + spokes + lines); `timeline` → an SVG axis with
  alternating milestone markers; `swimlane` → a CSS grid (rows=lanes, cols=cols) with tinted lane
  bands; `gantt` → a CSS grid of task rows × time columns with positioned duration bars (inner
  `%` fill), milestone ◆s, a "Today" line, and an absolutely-positioned SVG overlay for the
  dependency arrows; `tree` → a nested CSS/SVG hierarchy with parent→child lines; `mindmap` → a
  central node with curved, **branch-colored** paths radiating out (SVG), children fanning beyond
  each branch; `venn` → overlapping SVG
  circles (blend so the intersection reads); `spectrum` → a gradient bar with absolutely-positioned
  pole labels + markers; `decision` → an SVG flowchart (terminator/diamond/rectangle nodes +
  labeled edges); `rings` → nested SVG circles. Drive every one from the spec fields — never
  hardcode geometry.
- Publish with the Artifact tool (the shareable link) **and save a standalone local copy** so the
  page persists beyond the session and can be served offline: write it to the project's
  `muralize-output/pages/<slug>.html` **with a full `<!doctype html><html><head>…</head><body>`
  wrapper** (the Artifact tool adds that wrapper at publish time, but a locally-served file needs
  it itself), then add a card for it to `muralize-output/index.html` (the gallery). Create the
  folder if absent. Serve with `python3 -m http.server` from `muralize-output/`.

### Layer 6 — Verify & hand off
- Self-check: every harvested theme is represented; section count and reading order match
  the spec; text is faithful; gaps are flagged, not invented.
- Hand off: give `mural-image-rebuilder` the `board-spec` (preferred, lossless). Only fall
  back to its vision path if a spec isn't available.

## Authoring rules

- **One source of truth.** Generate the HTML from the spec, not separately — or they drift.
- **One pattern per infographic** (embed secondary patterns as sub-blocks).
- **Faithful text, flagged gaps.** Condense; don't fabricate.
- **Semantic color roles**, defined once.
- **Self-contained HTML** (inline everything) so the Artifact renders and stays portable.
- **Density is fine** — the target look is a dense strategy board; preserve section count and
  hierarchy over decoration.

## Composition with mural-image-rebuilder

The rebuilder has a spec-consumption mode (see its "Consuming a board-spec" section): given a
`board-spec`, it builds the Mural board directly from the structured content — areas with
`showTitle:false` + heading widgets, matrices as area-nested chips/text, flows with real
connectors, icons via its icon-matching loop — with **no vision step**, so text and counts
are exact. The infographic image is the human-facing artifact; the spec is the machine path.

## References

- `references/board-spec.md`: the shared board-spec JSON schema (the contract with the rebuilder).
- `references/brand-palette.md`: the **default Mural brand palette** — role→hex baseline, the full
  brand token library (for chart series/chips), and ready-to-inline CSS variables.
- `references/html-quality.md`: how to make the **HTML** infographic a first-class, productized
  artifact — design baseline (type/spacing/elevation scales), **real-SVG chart recipes** (donut,
  gauge arc, area line, bars, KPI tiles), density/layout, iconography, and a polish checklist.
- `references/infographic-patterns.md`: how to choose and lay out each infographic pattern from a brainstorm.
