# Rebuilder backend contract

This skill is the **local execution backend** for `mural-image-rebuilder`. When a writable
board is open in Chrome but the Mural MCP is unavailable, the rebuilder plans exactly as it
always does (pattern recognition, layout map, layer-by-layer build, `board-spec` mapping)
and hands the build steps here to execute through the browser instead of MCP tool calls.

**What changes:** the execution tool for each step, and the read tool for verification.
**What does not change:** the rebuilder's planning, its `board-spec` → primitive mapping
(`../../muralize/references/board-spec.md`), its fidelity rules, and its Layer-6 diff loop.

## Primitive → local-operation mapping

The rebuilder emits steps in terms of Mural MCP primitives. Map each to a local operation
(`operations.md`), taking the internals path when the probe proved it, else the UI path:

| Rebuilder primitive | Local operation |
|---------------------|-----------------|
| `create_areas` | Create → area. **Do this first** for each section (renders underneath its contents). |
| `create_stickies` | Create → sticky. Leave clearance so it doesn't auto-nudge. |
| `create_textboxes` | Create → text box (draw with a drag when width/wrapping matters). |
| `create_shapes` | Create → shape (pick the `shapeType` from the shape picker; text on top afterward). |
| `create_titles` | Create → title. Use for section headings; place in the reserved top band of the area. |
| text via `update_widgets` / `set_sticky_text` | Edit text. |
| `move_widget_to_area` | Move & arrange → drag the widget onto the (already-created) area so it parents. |
| `connect_widgets` / `connect_widget_to_point` | Connector — see below. |

## Create order and stacking

Preserve the rebuilder's order for the same reason it matters over MCP: **newer widgets
render on top**. Build each section's **area first**, then its backing shapes, then the
content widgets, then connectors. This keeps areas as visual containers and lets geometric
drops parent children in the UI.

## Connectors

There is no `connect_widgets` call on the UI path. Create both endpoint widgets first, then
draw the connector by hovering the source widget's edge until its connection handle appears
and `left_click_drag`-ing from that handle to the target widget. Verify the connector
anchored to both widgets (not to empty canvas) on a screenshot. Preserve directionality; for
loops, close the cycle back to the first node. Never substitute `→`/`->` text glyphs for
real connectors.

## Verification (Layer 6 unchanged)

The rebuilder's Layer-6 verification runs as written — only the read tool swaps: instead of
`get_widgets_screenshot` / `get_viewport_screenshot`, capture a **`claude-in-chrome`
screenshot** of the region and diff it against the source top-left → bottom-right (section
count, per-family widget count, text vs the Pass-A manifest, reading order, overlaps). Fix
discrepancies with local move/edit operations and re-screenshot until it matches. As
everywhere in this skill, content is confirmed on the image, never from a return value.

## Carry-over caveats from the rebuilder

- **Never use stickies for grids/cells/chips** needing precise placement — they auto-nudge.
  Build matrices as an area with positioned shapes + text boxes.
- **Don't rely on Mural's built-in area title** as the visible heading (it overlaps
  content); render a dedicated title widget in the area's reserved top band.
- **Re-verify the whole section after any move**, not just the widget you touched.
