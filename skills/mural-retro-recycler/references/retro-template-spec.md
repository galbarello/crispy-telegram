# Retro template spec

The spec tells `plan_reset.py` how to classify every widget on a used board into
**keep / clear / move / delete**. It classifies by **type, sticky color, and position**
— never by widget id — because a duplicated board gets fresh ids, so an id-based allow-list
would break on the copy. Type/color/zone rules survive duplication.

## How classification works

- `area`, `title`, `text` (paragraph), `sticker` (icon), `shape` → **scaffold, kept** and
  **never cleared** (only `sticky_note` text is blanked). Exceptions: a `text`/`sticky_note`
  inside a **content zone** is content (see below).
- `sticky_note` → matched to a **band** by `background_color`:
  - the first `cols × rows` of that color (in reading order) are **kept**: their text is
    **cleared** and they are **moved** to their home cells (so clustered/moved ones snap back);
  - any **beyond capacity** are **deleted** (participant-added extras).
- **Content zones** (e.g. a "Group by topic" area): any widget whose center falls inside, and
  whose type is in `content_zone_delete_types`, is **deleted** — unless it's a band sticky
  already kept (snapped out) or its text matches `protect_text_contains` (guards the zone's own
  scaffold text, like its instruction line).
- `comment` (and anything in `delete_types_anywhere`) → **deleted** everywhere.
- A sticky matching no band and in no zone → **unclassified**: left untouched and reported, so
  a human decides. The planner never deletes unclassified widgets.

## Schema

```jsonc
{
  "sticky_size": 168,                 // px; used only for center calc if width absent
  "bands": [
    {
      "name": "Start",
      "color": "#aaed92",             // exact sticky background hex (case-insensitive)
      "x0": 3658, "y0": 39,           // home cell of row 0, col 0 (top-left of the grid)
      "cols": 9, "rows": 5,
      "step_x": 191, "step_y": 191    // cell pitch
    }
    // … one band per section
  ],
  "content_zones": [
    { "name": "Group by topic", "x": 5620, "y": 40, "width": 1720, "height": 2560 }
  ],
  "content_zone_delete_types": ["sticky_note", "connector", "comment", "text"],
  "protect_text_contains": ["Drag related stickies", "Group by topic"],
  "delete_types_anywhere": ["comment"]
}
```

Field notes:
- **bands** define both the color→section mapping and the home grid to snap back to. Derive
  `x0/y0/cols/rows/step_*` from the *blank* template once.
- **content_zones** are rectangles in canvas coords. The grouping/affinity area is the usual
  one; add more for parking lots, "dot vote" zones, etc.
- **protect_text_contains** keeps a zone's own scaffold text alive (substring match on the
  widget's `text_content`). Everything else texty in the zone (participant topic labels) is
  deletable.
- Leave `delete_types_anywhere` empty to keep comments; include `"comment"` to wipe them.

## Ready-to-use spec — Start / Stop / Continue (this pack's template)

Matches the board this pack builds: three color-banded 9×5 grids on a shared 9-column set
(x = 3658, 3849, 4040, 4231, 4422, 4613, 4804, 4995, 5186; pitch 191), plus a "Group by topic"
grouping area on the right. Save as `sxc-spec.json` and pass with `--spec`.

```json
{
  "sticky_size": 168,
  "bands": [
    { "name": "Start",    "color": "#aaed92", "x0": 3658, "y0": 39,   "cols": 9, "rows": 5, "step_x": 191, "step_y": 191 },
    { "name": "Stop",     "color": "#febbbe", "x0": 3658, "y0": 1136, "cols": 9, "rows": 5, "step_x": 191, "step_y": 191 },
    { "name": "Continue", "color": "#fcf281", "x0": 3658, "y0": 2238, "cols": 9, "rows": 5, "step_x": 191, "step_y": 191 }
  ],
  "content_zones": [
    { "name": "Group by topic", "x": 5620, "y": 40, "width": 1720, "height": 2560 }
  ],
  "content_zone_delete_types": ["sticky_note", "connector", "comment", "text"],
  "protect_text_contains": ["Drag related stickies", "Group by topic"],
  "delete_types_anywhere": []
}
```

> Home total for this template = 3 bands × 45 = **135** grid stickies. After a reset the sticky
> count should be exactly 135 and every one blank — a quick `get_canvas_overview` check.

## Adapting to other templates

For 4Ls, sailboat, mad/sad/glad, etc.: keep the same schema, redefine `bands` (one per zone,
each with its color + home grid) and `content_zones`. If a template groups by *columns* rather
than color, give each column band a distinct color in the blank template first so the planner
can tell them apart — color is the band key.
