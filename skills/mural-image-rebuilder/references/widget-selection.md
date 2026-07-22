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
| A Mural **App / embedded widget** (Planner, text form, timer, …) | rebuild its *content* as native primitives — a **Planner → `gantt`** (schedule) / `swimlane` (roadmap) / `table` (task grid) | Mural "Apps" are **not** MCP-creatable (no `create_app`; not in the widget-type registry). See the section below. |
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
- **Areas auto-expand to fit their children — watch for occlusion.** A parented widget that
  extends past an area's bounds makes the area **grow** to contain it; in particular a textbox
  created **without an explicit `width` defaults to ~296px** and can silently push the area's
  right/bottom edge outward. Because a later-created area renders its background **on top** of an
  earlier one, an over-grown panel can then **occlude its neighbor** (seen for real: a sprint
  panel's white card grew to 652px and hid the adjacent analytics column until it was shrunk).
  Fixes: give parented textboxes an explicit `width`, and/or in Layer 6 reset each area's
  `width`/`height` back to the intended bounds after filling it (`update_widgets`; areas don't
  auto-shrink, and children may overflow the smaller bounds harmlessly).

## Mural "Apps" (Planner, forms, timer, …) — the `StructuredWidget` primitive

> **Strategy decision (settled):** for building planner/schedule content, **`gantt` is the
> canonical strategy** — it's the only one that's programmatic, populated, verifiable, and
> reproducible. The native Planner App is a **UI-only, user-owned** option (drop an empty shell
> via `mural-local-driver` only when the user explicitly wants the live Mural app to fill in
> themselves); it is **never an automated build target**, because its contents are opaque to the
> MCP. Don't re-litigate this per run.

Mural's **Apps** panel drops *embedded app widgets* (Planner, text form, timer, pachinko llama, …).
Inspected empirically (a dropped **Planner**): an App is a single widget of type
**`murally.widget.StructuredWidget`** identified by a **`structuredWidgetKey`** naming the app
(the Planner's key is `"planner"`). What the MCP can and can't do with one:

**CAN — read + arrange:**
- **See/identify it:** it appears in `get_canvas_overview` / `list_widgets` / `get_widget_by_id`
  as `murally.widget.StructuredWidget` with its `structuredWidgetKey`, position, and size — so you
  can detect an App and tell *which* one it is.
- **Arrange it** via `update_widgets` (verified live): `x`, `y`, `width`, `height`, `rotation`,
  `hidden`, `locked`, `parentId` (drop it into an area), `title`, `stackingOrder`. So you can
  place, size, reparent, lock, and layer a Planner like any widget.
- **Delete it** with `delete_widget`.

**CANNOT — content is opaque:**
- **Create one** — there is no `create_*` tool for `StructuredWidget`; only Mural's UI inserts an
  App.
- **Read or write its data** — `text_content` is empty, there is **no content/data field**, and
  `get_widgets_screenshot` renders it as a **blank frame**. Its rows/tasks are opaque to the MCP.

**Primitives / recipe:**
- *Insert* a native Planner → **UI only** (`mural-local-driver`: Apps panel → Planner).
- *Position / size / reparent / lock* an existing Planner → `update_widgets` (geometry + `parentId`).
- *Reproduce a Planner's content* — the usual goal, since its data is opaque and it isn't creatable
  → build from primitives: **`gantt`** (schedule with durations/dependencies), `swimlane`
  (now-next-later roadmap), or `table`/area+stickies (task grid). This is what `muralize` already
  emits for a "project plan / delivery schedule" (→ `gantt`) — fully MCP-buildable and reproducible.

## When to fall back to shapes + textboxes

Only when the native primitive genuinely can't express the source (e.g. a table cell
needs styling `create_table` doesn't support). When you do, say so explicitly in the
build notes so it's a conscious tradeoff, not an accident.

## Typography — Proxima Nova is the only face

The canvas renders **only Proxima Nova**. `update_widgets` will accept and store any
`fontFamily` (returning `success:true`), but an unrecognized family silently falls back to the
default — so a serif or any custom face is **not achievable on a Mural board** via the MCP (see
the SKILL "renders ONLY Proxima Nova" note). Reproduce the source's type hierarchy with size,
weight, and casing, not the typeface. A serif belongs only in an HTML render, never the board.
