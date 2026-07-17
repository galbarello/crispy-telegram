# Readiness tracker — board-spec

The shared "who's done" tracker, expressed in the **board-spec** vocabulary shared with `muralize`
and `mural-image-rebuilder` (see `../../muralize/references/board-spec.md`). Build it with the
rebuilder's primitives-first rules: an `area` (`showTitle:false`) + a heading widget, positioned
cells, **never `create_table`**, brand palette **roles** (default `theme:"brand"`).

**Provision it BEFORE private mode** so every widget is shared content visible to all peers.

## Layout (landscape band, ~1200×360)

```
┌──────────────────────────────────────────────────────────────────────────┐
│  ✔ ACTIVITY READINESS                              4 of 8 finished   50%   │  ← heading + status
│  ┌─────────────────────────────┐   ┌────────────────────────────────────┐ │
│  │ WORKING                      │   │ DONE                               │ │  ← two-zone lane
│  │  (Ana) (Ben) (Cy) (Dev)      │   │  (Eli) (Fio) (Gus) (Hal)           │ │  ← per-person tokens
│  └─────────────────────────────┘   └────────────────────────────────────┘ │
│  ████████████████░░░░░░░░░░░░░░░░  progress                                │  ← progress bar
│  How to signal done: drag your token into DONE.  (mode-specific legend)    │  ← legend
└──────────────────────────────────────────────────────────────────────────┘
```

## Spec

```json
{
  "meta": {
    "title": "Activity readiness",
    "theme": "brand",
    "orientation": "landscape",
    "palette": {
      "primary": "#195AD7", "success": "#00C27A", "warning": "#FFAA00",
      "danger": "#FF4B4B", "accent": "#8728E6", "surface": "#F0F0F0", "ink": "#202124"
    }
  },
  "tracker": {
    "roster": ["Ana", "Ben", "Cy", "Dev", "Eli", "Fio", "Gus", "Hal"],
    "zones": [
      { "id": "working", "label": "WORKING", "color": "surface" },
      { "id": "done",     "label": "DONE",    "color": "success" }
    ],
    "token": { "shape": "rounded_square", "w": 92, "h": 40, "startZone": "working",
               "fill": "primary", "textColor": "#FFFFFF" },
    "status": { "countText": "0 of 8 finished", "progress": 0.0, "perPersonCheck": true },
    "legend": "How to signal done: <mode-specific — see below>."
  }
}
```

## Build recipe (spec → primitives)

1. **Area** (`showTitle:false`), generously sized; heading `title` widget in a reserved top band
   (`accent`/`ink`), e.g. "✔ Activity readiness".
2. **Status block** (top-right): a `status.countText` textbox ("N of M finished", `tabular-nums`);
   a **progress bar** = a track `rectangle` (`surface`) with an inner fill `rectangle` (`success`)
   whose width = `progress × trackWidth`; optional "NN%" label.
3. **Two-zone lane:** one wide `rectangle` per zone — Working (`surface` fill) and Done (light
   `success` tint, ~12–18% alpha). Zone label textboxes at each zone's top-left.
4. **Tokens:** one `token.shape` **per roster entry**, labeled with the name, `primary` fill + white
   text, all starting in the Working zone in a wrapped row. **Parent each token to the area**
   (`parent_id`) so it's a real child (and so a later move is a move of shared content). Keep tokens
   sized to hug the name (don't stretch).
5. **Per-person ✓ row** (if `status.perPersonCheck`): a small name + checkbox glyph per person under
   the status, toggled ✓ when that person is done (Mode B writes these).
6. **Legend** textbox (bottom): the instruction, chosen by mode —
   - Mode A: "Drag your token into **DONE** when you finish."
   - Mode B: "Drop a sticky in your **done slot** (or drag your token) — the counter updates for
     everyone."
   - Mode C: "React with 👏 when you finish — we'll tally it here."

## Notes
- **Colors by role only** (every `fill`/`color` is a palette role) — matches the brand theme.
- The **Done zone** uses `success` because green is Mural's "complete/go" color (see brand-palette).
- Keep the whole tracker in one area so the facilitator can move/collapse it as a unit.
- For Mode A the lane *is* the live status; for B/C the status block + ✓ row are what the agent
  keeps current via `update_widgets`.
