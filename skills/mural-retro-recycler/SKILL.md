---
name: mural-retro-recycler
description: produce a fresh, empty copy of a retro or workshop mural for the next cycle — duplicate the board, then strip participant content (sticky text, clusters, votes, added widgets) while preserving the template scaffold (title, section headers, icons, prompts, empty grids, grouping areas). use when someone says "spin up next sprint's retro", "reset this board for the next session", "duplicate and clear this mural", or wants a reusable retro/workshop template recycled.
---

# Mural Retro Recycler

## Overview

Turn a **used** retro/workshop mural into a **fresh, empty** one for the next cycle, in two
moves:

1. **Duplicate** the source board (so the original stays as the record of this cycle).
2. **Empty** the copy — clear all sticky text, snap stickies back to their home grid, and
   delete everything participants added — while **preserving the template scaffold**
   (title, section headers + icons, prompt/description text, the blank sticky grids, and any
   grouping areas).

The result is the same board layout, ready to run again, with none of last cycle's content.

**Scaffold vs content — the core distinction.**
- **Scaffold (keep):** areas/frames, the title, section headers and their labels, section
  icons (stickers), description/prompt textboxes, the empty sticky grids in their home
  positions, and empty grouping areas.
- **Content (remove):** sticky *text* (cleared, not the stickies themselves), participant
  stickies added beyond the template grid, clusters dragged into grouping areas, topic labels
  added during the session, connectors, comments, votes, reactions.

## When to use

- "Set up next sprint's retro from this one." / "Recycle this board."
- "Duplicate this mural and clear it out." / "Reset the template for the next workshop."
- Any recurring Start/Stop/Continue, 4Ls, sailboat, or workshop board that is re-run per cycle.

Do NOT use this to build a board from scratch (that's `muralize` → `mural-image-rebuilder`) or
to rebuild from an image (`mural-image-rebuilder`). This skill only **copies + empties** an
existing template.

## Prerequisites

- The source mural is open in a signed-in browser tab and the Mural MCP bridge is live.
- You know (or can derive) the template's **layout spec** — the band grids, colors, and which
  widgets are scaffold. For the Start/Stop/Continue template this pack builds, that spec is in
  `references/retro-template-spec.md`; adapt it for other templates.

## Workflow

### 1. Identify the source

`select_mural` the used board. Run `get_canvas_overview` to confirm counts/types, and
`get_document_tree` (view `compact`) to see the areas and structure. Confirm with the user
which board is "this cycle's" record before duplicating.

### 2. Duplicate — pick a path

There is **no `duplicate_mural` MCP tool**; `create_mural` only makes a **blank** board. Two
ways to get the copy:

- **Path A — Mural UI duplicate (recommended, faithful).** Ask the user to duplicate in Mural:
  *mural menu (⋯) → Duplicate mural*, name it for the next cycle (e.g. "… — Sprint 18"), open
  the copy, and tell you when it's up. Then `select_mural` the copy. This preserves the
  template pixel-for-pixel (icons, formatting, areas, everything) — you only need to empty it.
  This is the default; recommend it unless the user wants it done entirely via MCP.

- **Path B — programmatic scaffold-clone (MCP-only fallback).** When UI duplication isn't an
  option, rebuild just the scaffold into a new blank mural:
  1. `create_mural(title=…, room_id=…)` in the same room (use `list_rooms`/`list_workspaces`
     if you don't have the room id). The user must open the returned link.
  2. Read the source scaffold: `get_document_tree`/`list_widgets` (view `full`) for areas,
     titles, textboxes, shapes; `get_widget_by_id` on each **icon** to recover its
     `noun_project_id` (the `name` field) — icons are stickers and can't be copied by
     reference.
  3. Recreate the scaffold in the new mural with `create_areas`, `create_titles`,
     `create_textboxes`, `create_shapes`, `create_icons`, plus the **blank** sticky grids via
     `create_stickies` (no text). Do NOT copy participant content.
  Path B clones structure only (which is all you need, since the goal is an empty board), but
  it's lossy on exact styling — prefer Path A whenever the user can click Duplicate.

### 3. Empty the target

Operate on the **copy** (Path A) — or skip this step for Path B, whose scaffold-clone is
already empty. On the copy:

1. **Dump widgets:** `list_widgets` (view `full`) → save to a JSON file
   (`{"widgets": [...]}`).
2. **Plan the reset:** run `scripts/plan_reset.py <dump.json> --spec <template-spec.json>`.
   It classifies every widget against the spec and emits three lists:
   - `clear` — sticky ids to blank (kept grid stickies that hold text),
   - `moves` — `[{widget_id, x, y}]` to snap grid stickies back to their home cells (so
     clustered/moved ones return to place),
   - `delete` — ids to remove (stickies beyond grid capacity, anything inside a declared
     content zone such as a grouping area, and added labels/connectors/comments).
   See `references/retro-template-spec.md` for the spec format and the concrete S/S/C spec.
3. **Apply, backgrounds-safe order:**
   - `delete_widget(delete)` first (removes extras and content-zone clutter).
   - `update_widgets(moves)` to re-home stickies — **update is idempotent**, so it is safe from
     the create double-apply bug.
   - `set_sticky_text(widget_id, "")` for each id in `clear` (one call per sticky; this is the
     only tool that actually blanks rendered sticky text — `update_widgets` does **not**).
4. **Reset grouping areas:** any "Group by topic" / affinity area should end empty. The content
   zone in the spec covers it, so its dragged stickies and topic labels are in `delete`.

### 4. Verify (visual, not API)

- `get_canvas_overview` — confirm the sticky count matches the template's home total and no
  stray areas/comments remain.
- `get_widgets_screenshot` on the section headers + a sample of each band — confirm stickies
  are **blank** and **snapped to the grid**, scaffold (headers, icons, descriptions) intact.
  Never trust `set_sticky_text`'s success envelope for "is it blank" — read it off the image
  (same rule as the rebuilder: content validation is visual).
- Report: source (this cycle's record) vs the fresh copy, and the counts cleared/moved/deleted.

## Safety rules

- **Never empty the source** — always duplicate first and empty the *copy*. Confirm which
  mural id is the copy before any `delete_widget`/`set_sticky_text`.
- **Deletion is irreversible via MCP.** Before deleting, sanity-check the `delete` list count
  against the dump (e.g. "deleting 42 of 190 widgets"); if it would remove scaffold, the spec's
  zones/bands are wrong — fix the spec, don't proceed.
- **Preserve scaffold by allow-list, not guesswork.** The spec declares scaffold explicitly
  (areas, titles, icons, description textboxes, band grids); anything not matched as scaffold or
  as a keepable grid sticky is content. When unsure whether a widget is scaffold, keep it and
  flag it to the user rather than delete.
- **One template = one spec.** Different templates (4Ls, sailboat, mad/sad/glad) need their own
  spec (bands, colors, zones). Derive it once from the blank template and reuse it every cycle.

## References

- `references/retro-template-spec.md` — the spec schema + the ready-to-use Start/Stop/Continue
  spec (band grids, colors, grouping-area content zone).
- `scripts/plan_reset.py` — turns a `list_widgets` dump + a spec into `clear`/`moves`/`delete`
  operation lists.
- `references/retro-section-guide.md` — reusable section labels, descriptions, and the
  header/grid treatment the recycler preserves (Start/Stop/Continue + 4Ls, mad/sad/glad,
  sailboat).
