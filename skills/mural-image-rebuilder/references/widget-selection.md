# Widget selection reference

Which Mural widget/tool to use for each thing you see in a source image. The default
failure mode is faking a native structure out of loose textboxes and glyphs — this table
prevents that. All tools listed here exist in the Mural MCP.

## Source element → tool

| Source element | Tool | Notes |
|----------------|------|-------|
| Grid / matrix / comparison / scored table | an `area` with positioned chips + textboxes parented to it | Do NOT use `create_table` — its cells render empty in this environment (create doesn't fill; `update_widgets textContent` reports success but leaves cells blank). Lay out cells on a row/column grid; represent a cell's multiple chips as multiple chip widgets, and bulleted cells as one textbox. Verify content by screenshotting the child widgets. |
| Sequential steps / loop / dependency arrows | nodes first, then `connect_widgets` (or `connect_widget_to_point`) | Real connectors anchor to widgets and survive moves. Never use `→`/`->` text glyphs. |
| Titled region / section / swimlane | `create_areas`, then children with `parent_id` | Areas are the only real container. Parent children so the section moves as a unit. |
| Section headline / banner | `create_titles` | Auto-resizing; supports decoration (border, radius, shadow). |
| Body copy / paragraph / cell text | `create_textboxes` | Set `width`; use `background_color` when you need a coloured chip/cell without a table. |
| KPI tile / card | shape background (created first) + textbox on top, or a titled `area` | Not a sticky. |
| Icon / logo / pictogram | `search_icons` → `create_icons` | Pick ONE strategy per board — all real icons, or accept emoji-in-textbox as an explicit low-fidelity fallback. Don't mix. |
| Literal sticky note in the source | `create_stickies` | Only when the source actually shows sticky notes. |
| Bulk restyle after building | `update_widgets` | Change fill/stroke/font across many widgets without recreating them. |
| Read back / verify | `get_viewport_screenshot`, `get_canvas_image`, `get_widgets_screenshot` | Required in Layer 6. |

## Sticky notes — the biggest gotcha

Evidence from real builds: stickies aimed at a tight grid were flung far from target,
including to negative coordinates —

- requested `(20, 1150)` → placed `(-164, 966)`
- requested `(120, 1150)` → placed `(-64, 1334)`
- matrix rows near `y≈2810/3010` → placed at `x = -144`

Why: sticky notes are a fixed large size (~168×168px) and **auto-nudge on collision**,
so any dense or precise arrangement scatters. The nudge is reported in the create
response as `requested_x`/`requested_y` differing from the final position — scan for it.

**Rule:** never use stickies for grids, table cells, chips, tight rows, or precise
layouts. Use `create_table`, textboxes (with `background_color`), or shapes. Reserve
stickies for when the source literally depicts sticky notes.

## Stacking and containment

- **Newer widgets render on top.** Create backgrounds and `areas` first, then content,
  then connectors (whose endpoints must already exist).
- **Containment is by `parent_id`, not geometry.** A widget inside an area's bounds is
  NOT a child unless you set `parent_id` (at creation) or call `move_widget_to_area`.
  Only true children move/group with the area.
- Size areas generously and keep their top edge clear so the title stays legible.

## When to fall back to shapes + textboxes

Only when the native primitive genuinely can't express the source (e.g. a table cell
needs styling `create_table` doesn't support). When you do, say so explicitly in the
build notes so it's a conscious tradeoff, not an accident.
