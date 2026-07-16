# Operation catalog

The four supported operations, each with an internals path (use when the probe proved it),
a UI fallback (always available), and a verification step. **No operation is complete until
its verification screenshot confirms it.**

Two cross-cutting rules:

- **Discover shortcuts live.** Mural's keyboard shortcuts change; open the in-app `?` help
  panel to read the current toolbar shortcuts rather than hardcoding letters here.
- **Create backgrounds/containers first.** Newer widgets render on top, so an area or
  backing shape must exist before the widgets that sit on it.

---

## 1. Create (sticky / text / shape / title)

**Internals path.** Call the client's create/add API with the widget type, board coords,
size, text, and style; capture the returned id if one is given (useful for later edits).

**UI path.**
1. Select the widget's tool — from the toolbar (click its pixel) or its keyboard shortcut.
2. Compute the target pixel from the board coord (`coordinate-mapping.md`). `left_click` to
   drop a default-size widget, or `left_click_drag` to draw it at a specific size.
3. The widget usually opens in text-edit mode; `type` the text.
4. Commit with `Esc` or a `left_click` on empty canvas.

Notes per type:
- **Sticky** — fixed-ish size, may auto-nudge on collision; leave clearance around the drop
  point so it doesn't relocate.
- **Text box** — free size; draw with a drag when width matters (wrapping).
- **Shape** — pick the shape type from the shape picker; add text on top after it exists.
- **Title** — Mural's title/heading widget; use it for section headings rather than a giant
  text box.

**Verify.** Screenshot the new widget and **read its text back off the image**. If the
create tool reported a position, check the widget actually landed there (no silent nudge).

---

## 2. Edit existing text

**Internals path.** Call a set-text API against the widget's id (from the probe's widget
read or a create response).

**UI path.**
1. Identify the target widget's pixel from a screenshot.
2. `double_click` it to enter text-edit mode.
3. Select all (`Cmd+A`) and `type` the replacement, or click to position the caret and
   `type` to append.
4. Commit (`Esc` / click empty canvas).

**Verify.** Screenshot and confirm the exact string rendered — do not infer from the
keystrokes you sent.

---

## 3. Move & arrange

**Internals path.** If a reliable position-setter exists, set the widget's board coord and
verify; otherwise use the UI (dragging is well-behaved).

**UI path.**
- **Move one** — `left_click` to select, then `left_click_drag` from the widget's pixel to
  the destination pixel (both inside the viewport — see edge auto-pan hazard).
- **Multi-select** — shift-`left_click` each widget, or rubber-band with a `left_click_drag`
  across empty canvas around them, then drag the group.
- **Align / distribute** — with a multi-selection, use Mural's alignment controls
  (context toolbar); read current controls from the `?` panel.
- **Group into an area** — create the **area first** (it renders underneath), then drag
  widgets onto it. In the real UI a geometric drop **does** parent the widget to the area
  (unlike the Mural API, where only an explicit parent link parents it), so the widget then
  moves with the area. Confirm by nudging the area a few px and checking the child follows.

**Verify.** Re-screenshot the **whole affected region**, not just the moved widget — a drag
can shove a neighbour or push something off-screen. Confirm nothing is lost off-view.

---

## 4. Read / inspect

- **Screenshot is authoritative for text and layout.** To read a region, frame it in the
  viewport and screenshot; read strings and positions off the image.
- **JS widget-list probe (optional).** If the probe exposed a widget accessor, use it for
  structure and counts (how many widgets, ids, board coords) to plan work and cross-check —
  but still confirm rendered text visually, since a store value can differ from what paints.
- To inspect a specific widget precisely, pan/zoom so it's large in the viewport, then
  screenshot.
