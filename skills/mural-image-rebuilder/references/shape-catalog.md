# Shape catalog — match a source shape to a Mural `shape_type`

Repeated shapes (journey stages, flow nodes, badges) carry meaning through their *form*.
Don't guess a `shape_type` from memory — match the source's visual signature here, then
**verify the choice with one probe** (see bottom).

## Visual signature → shape_type

Prefer the smart (snake_case) library; it renders cleaner than the legacy PascalCase set.

| What you see in the source | Use |
|----------------------------|-----|
| Chevron / "process step" banner — notched left edge, pointed right edge, stages that interlock | `step` |
| Solid right-pointing arrow (shaft + head) | `arrow_right` (also `arrow_left`, `arrow_top`, `arrow_down`, `arrow_left_right`) |
| Home-plate / pentagon (flat left, point right, no notch) | `pentagon_smart` |
| Plain rectangle | `rectangle` |
| Rounded rectangle / card | `rounded_square` |
| Circle / oval | `ellipse` (perfect circle: `Circle`) |
| Diamond / decision rhombus | `decision` or `rhombus_smart` |
| Hexagon | `hexagon_smart` |
| Octagon / stop | `octagon` |
| Triangle | `triangle_smart` (right-angle: `right_triangle`) |
| Trapezoid | `trapezoid` |
| Star / burst | `star` |
| Cloud | `cloud` |
| Cylinder / database | `database` (or `stored_data`) |
| Document (wavy bottom) | `document` (stack: `multiple_documents`) |
| Speech bubble | `speech_bubble_left` / `_right` / `_center` |
| Thought bubble | `thinking_bubble_left` / `_right` |
| Ribbon / banner badge | `ribbon`, `simple_ribbon`, `badge` |
| Rounded pill terminator (start/end of a flow) | `terminator` (or `start` / `end`) |
| Cross / plus | `cross` |
| Curved arrow / connector between two widgets | not a shape — use `connect_widgets` |

If two candidates are plausible (e.g. `step` vs `arrow_right` vs `pentagon_smart` for a
chevron), that is exactly when to run the probe rather than commit blind.

## Probe-then-replicate loop (do this for any non-trivial repeated shape)

1. Pick the best-guess `shape_type` from the table.
2. Create **one** probe instance (off to the side, or the first real one), plus — if
   you're unsure — one instance of each rival candidate side by side.
3. `get_widgets_screenshot` the probe(s) and compare against the source crop.
4. Commit to the winner. If you already placed the wrong type, you don't need to recreate —
   `update_widgets` with `{ "shapeType": "<winner>" }` changes it in place (text, color,
   and position are preserved).
5. Delete throwaway probes.

Cost: one extra shape + one screenshot, versus N wrong shapes you'd otherwise have to
notice and redo. Worked example: journey "stage" banners first built as `pentagon_smart`
(home-plate) were probed against `step` and `arrow_right`; `step` matched the source's
interlocking chevrons, and all stages were switched via `shapeType` without rebuilding.

## When nothing matches

Approximate with the closest shape and say so (fidelity to structure over decoration), or
compose the form from primitives. Never silently substitute a shape whose *meaning*
differs (e.g. a `decision` diamond where the source shows a plain step).
