# Pattern catalog

Use this reference to classify the source image before building.

## Timeline

Visual signs:
- Repeating milestones
- Linear or curved progression
- Date labels, phases, or numbered steps
- Left-to-right or top-to-bottom flow

Build with: node widgets + `connect_widgets` for the flow line/arrows; detail cards as
shapes/textboxes or a titled `area`. Not glyph arrows.

Rebuild order:
1. Axis or flow line
2. Milestones or checkpoints
3. Detail cards attached to each point
4. Labels, badges, and annotations

## Matrix / quadrant

Visual signs:
- 2x2 or grid layout
- Axis labels on top and side
- Comparison cells or scorecards
- Repeated content in each cell

Build with: an `area` containing positioned chips + textboxes on a row/column grid.
Do NOT use `create_table` (its cells render empty here). A cell that shows several chips
in the source gets several chip widgets; a bulleted cell gets one textbox. Confirm content
by screenshotting the child widgets.

Rebuild order:
1. Outer grid frame
2. Axis labels
3. Cell containers
4. Cell content and repeated widget families

## Dashboard

Visual signs:
- KPI tiles
- Summary numbers
- Small charts or charts with legends
- Dense, information-first composition

Chart sub-types to recognize (route each to the matching `chart` build in SKILL.md's
board-spec section — the geometry there applies to the vision path too):
- **Bar/column** — rectangular bars rising from a baseline (renders precisely).
- **Line** — markers connected by rising/falling segments, often multi-series with a
  legend; a trend/time series. Rebuild as markers + value labels + joined segments
  (rotated-rectangle segments by default; connectors only if arrowheaded lines are
  acceptable). Transcribe the point values — the numeric labels are the fidelity, the
  drawn line is an approximation.
- **Pie/donut** — build a 100%-stacked horizontal bar + legend (no true wedge primitive).
- **Gauge/dial** — build a linear meter (or an approximate radial dial), trusting the
  numeric value label.

Build with: KPI tiles as shape-background + textbox (or titled `areas`); charts from
primitives per the `chart` guidance in SKILL.md (axis/baseline first, then data, then
labels on top). Not stickies.

Rebuild order:
1. Header and summary row
2. KPI tiles
3. Primary charts or data blocks
4. Supporting notes, legends, and filters

## Strategy framework

Visual signs:
- Pillars, layers, flywheels, loops, ladders, or stages
- Conceptual labels with arrows or brackets
- Large central idea with supporting blocks

Build with: `areas` for the core concept and supporting regions (parent children via
`parent_id`); `connect_widgets` for directional markers.

Rebuild order:
1. Core container or central concept
2. Supporting structure around it
3. Connectors or directional markers
4. Explanatory text and labels

## Mixed patterns

When the board contains more than one pattern:
- Choose the dominant pattern by visual area and reading order.
- Treat the secondary pattern as a nested substructure.
- Preserve the nested pattern only after the dominant structure is stable.
