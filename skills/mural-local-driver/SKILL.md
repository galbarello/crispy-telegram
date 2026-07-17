---
name: mural-local-driver
description: drive an already-open mural board entirely through the local browser (claude-in-chrome), with no mural api or mcp — create/edit/move widgets and read board state via in-page javascript when available, falling back to pixel-accurate coordinate and keyboard automation. use when manipulating an open mural tab locally, or as the local execution backend for mural-image-rebuilder when the mural mcp is unavailable.
---

# Mural Local Driver

## Overview

Manipulate an **already-open** Mural board **100% locally** — through the user's own
Chrome tab via the built-in `claude-in-chrome` browser automation. No Mural API, no Mural
MCP, no server bridge: every action is a click, drag, keystroke, screenshot, or piece of
in-page JavaScript against the real, signed-in canvas the user is looking at.

Mural is a **canvas/WebGL app**: widgets are painted to a `<canvas>`, not exposed as
semantic DOM nodes, so reading the DOM tells you almost nothing about the board. This skill
therefore runs a **hybrid** strategy:

- **Probe first.** Inspect the page for any in-app Mural client internals you can call or
  read (a store, an SDK on `window`, the canvas root's React fiber, a postMessage channel).
  When present, they give exact board coordinates, reliable text, and structural reads.
- **Fall back to UI.** When internals aren't exposed, drive the visible app with
  pixel-accurate coordinate actions (`computer`: `left_click`, `left_click_drag`, `type`,
  `scroll`) and Mural's own keyboard shortcuts.

**Verify visually, always.** Never conclude an action worked from a tool's return value or
a JS call resolving. The only source of truth is a **screenshot you read back**. This
mirrors `mural-image-rebuilder`'s rule that content validation is visual, not API — it
applies with full force here because there is no trustworthy API in the loop at all.

## Prerequisites & bootstrap

Load the browser tools in **one batched `ToolSearch`** at the start of a session:

```
ToolSearch with query "select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__computer,mcp__claude-in-chrome__read_page,mcp__claude-in-chrome__javascript_tool"
```

Then bootstrap:

1. **Confirm the environment** (see `references/browser-setup.md`): the `claude-in-chrome`
   extension is installed and enabled for this session; the Mural app domain is
   pre-permissioned in the extension; the session is **not** in `bypassPermissions` mode
   (browser tools are unavailable there).
2. **Locate the tab.** Call `tabs_context_mcp` and find the open Mural board tab. Do **not**
   open a new/headless tab — act on the tab the user already has open.
3. **Confirm it's writable.** The URL should be an editable board (e.g. an
   `app.<mural-domain>/.../m/...` board URL, not a viewer/embed link) and the user must be
   signed in as an editor.
4. **Baseline screenshot.** Capture the current viewport so you have a before-state to diff
   every mutation against.

If any precondition fails, stop and tell the user exactly what to fix (enable via `/chrome`,
permission the domain, open/edit the board) rather than guessing.

## Hybrid strategy (probe first, UI fallback)

Run the probe **once** at the start of the session (`references/probe-and-adapt.md`). It
returns a **capability map**, and each capability can resolve to a different path:

| Capability | If internals expose it | Otherwise |
|------------|------------------------|-----------|
| Create at exact board coords | call the create API / dispatch scripted events | UI: pick tool → click/drag at pixel → type → commit |
| Read widget list / counts / text | read the store | screenshot only (authoritative for text) |
| Set/replace text | call set-text | UI: double-click → `Cmd+A` → type → commit |

Hard rules that hold on **either** path:

- **Confirm every mutation with a screenshot** before moving on.
- **After a move, re-screenshot the whole affected region**, not just the widget you
  dragged — a reposition can push neighbours or the dragged widget off-screen, and you will
  not notice from a return value (the spirit of the rebuilder's off-screen-nudge lesson).
- **Create containers/backgrounds first.** Mural renders the most recently created widget on
  top, so make an area or backing shape before the widgets that sit on it.

## Coordinate model

The UI path lives or dies on the **board↔pixel transform**. See
`references/coordinate-mapping.md`. In short:

- **Normalize the view** to a known zoom and origin (Mural's zoom / fit-to-screen controls)
  before placing anything, so the transform is stable.
- **Recover the transform** either from the probe (if pan/zoom are exposed) or empirically:
  place one reference widget at a known board coord, screenshot it, and read its pixel back.
  Then `pixel = origin_px + (board − pan) · zoom`.
- **Re-derive after any pan or zoom.** Keep work inside the visible viewport and pan
  deliberately between regions rather than dragging across the viewport edge.

## Operations

Full catalog with internals-path, UI-path, and per-op verification in
`references/operations.md`. The four supported operations:

| Operation | UI path (fallback) | Verify |
|-----------|--------------------|--------|
| **Create** (sticky / text / shape / title) | pick tool via toolbar or shortcut → click/drag at target pixel → type → commit (`Esc`/click-away) | screenshot the new widget, read its text back |
| **Edit text** | double-click widget pixel → `Cmd+A` replace (or position to append) → commit | screenshot, confirm the string |
| **Move & arrange** | `left_click` select → `left_click_drag` to destination; multi-select via shift-click / rubber-band; group by dragging onto an area | re-screenshot the whole region |
| **Read / inspect** | screenshot (authoritative for text) + optional JS widget-list probe for counts/structure | — |

Discover Mural's **current** keyboard shortcuts from its in-app `?` help panel rather than
hardcoding them — they change over time.

### Native Apps (Planner, forms, …) — UI-insert only, treat as opaque

Mural's **Apps** (Planner, text form, timer, …) are embedded widgets the Mural MCP cannot create
or configure. The **only** way to place one is Mural's browser UI, which this driver can drive:
open the **Apps** panel from the toolbar → pick the app (e.g. **Planner**) → click to drop it on
the canvas. Once placed, it reads back through the MCP as a `murally.widget.StructuredWidget`
(its `structuredWidgetKey` names the app — the Planner's is `"planner"`), and you **can** then
position / size / reparent / lock it via `update_widgets`. But the app's internal data is
**opaque** — you can't reliably populate or read its contents through the MCP or DOM probing, so
don't try to fill it programmatically. When the goal is
a *populated, reproducible* planner, rebuild the content with native primitives
(`gantt`/`swimlane`/`table`) per `../mural-image-rebuilder/references/widget-selection.md`; drop the
native App only when the user specifically wants the interactive Mural app itself.

## Use as a rebuilder backend

This skill is the **local execution backend** for `mural-image-rebuilder`. When a writable
board is open in Chrome but the Mural MCP is unavailable, the rebuilder's build plan (or a
`muralize` `board-spec`) executes here instead. The mapping from each rebuilder primitive
(`create_areas`, `create_stickies`, `create_textboxes`, `create_shapes`, `create_titles`,
`connect_widgets`, text edits, `move_widget_to_area`) to a local operation — and the
create-order and connector handling — is in `references/rebuilder-backend.md`. The
rebuilder's Layer-6 diff loop is unchanged; only the read tool swaps to a browser
screenshot.

## Quality checks

Before finishing, confirm each — they are pass/fail:

- The action targeted the **already-open, writable** Mural tab (not a new tab, not a viewer).
- The capability probe ran and a path was chosen per capability.
- **Every** created/edited widget was confirmed on a **screenshot**, with its text read off
  the image — never inferred from a return value.
- After every move, the whole affected region was re-screenshotted; nothing was left
  off-screen or shoved onto a neighbour.
- Containers/backgrounds were created before their contents (newer widgets stack on top).
- On the UI path, the coordinate transform was re-derived after any pan/zoom.

If any item fails, the operation is not done.

## References

- `references/browser-setup.md`: `claude-in-chrome` prerequisites, tool loading, targeting the open tab, and failure modes (permissions, bypass mode, dead bridge, computer-use lock).
- `references/probe-and-adapt.md`: the internals-discovery loop — JS probes for Mural client globals/store/fiber, the capability matrix, dispatching scripted events, and graceful degradation to pure UI.
- `references/coordinate-mapping.md`: normalizing the view and recovering the board↔pixel transform, plus scroll/drag hazards and how to pan between regions.
- `references/operations.md`: the full create / edit-text / move-arrange / read-inspect catalog, each with internals + UI paths and verification.
- `references/rebuilder-backend.md`: the execution-backend contract — mapping `mural-image-rebuilder` primitives and `board-spec` blocks onto local operations.
