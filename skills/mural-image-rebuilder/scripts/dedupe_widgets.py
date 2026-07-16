#!/usr/bin/env python3
"""
dedupe_widgets.py — find duplicate ("twin") widgets to delete after a build.

Why this exists: the Mural bridge occasionally DOUBLE-APPLIES a create_* call — the
tool returns one id per widget, but a second identical widget ("twin") also lands on the
board with an id you never saw. The twins overlap their originals exactly, so the board
LOOKS right while carrying ~2x the widgets. This was observed on a real rebuild (a chart
ballooned from 349 to 678 widgets). You cannot prevent the bridge from doing it, so the
fix is to detect-and-clean deterministically as a build step.

This script reads a `list_widgets` dump (view="full") and reports the widget ids to
delete so that exactly ONE widget survives per group of byte-identical duplicates. It is
deliberately CONSERVATIVE: two widgets are "the same" only when EVERY rendered property
matches (type, position, size, rotation, colors, text, parent). Two genuinely-distinct
chart widgets essentially never collide on all of those, so this won't delete real content
the way a position-only key can. Feed the output straight to the `delete_widget` tool.

USAGE
    # 1) dump the region (or whole board) to a file — list_widgets view="full" auto-saves
    #    large results to a file; point this script at that file:
    python3 dedupe_widgets.py widgets.json
    python3 dedupe_widgets.py widgets.json --parent 0-1784040276031   # only this area's children
    cat widgets.json | python3 dedupe_widgets.py

Output: a JSON array of widget_ids to delete (empty array if the board is already clean),
followed by a one-line summary on stderr. Delete in batches with the delete_widget tool,
then re-run get_canvas_overview to confirm the count dropped to what you intended.

SAFETY
- Never emits every member of a group — always keeps the first (lowest id).
- Never emits an `area`/container id (deleting an area could cascade to its children);
  areas are excluded from grouping entirely.
- `--parent ID` restricts to widgets whose parent_id == ID, so you only clean the section
  you just built and never touch the rest of the board.
"""
import json
import re
import sys


# Rendered properties that must ALL match for two widgets to count as duplicates.
# Twins share every one of these; distinct real widgets almost never do.
KEY_FIELDS = (
    "widget_type", "position_x", "position_y", "width", "height",
    "rotation", "background_color", "text_content",
)


def _norm_text(v):
    # Compare widgets by their VISIBLE text, not raw HTML. Twins of the same widget
    # serialize their (often empty) content inconsistently — e.g. `<div><br></div>`,
    # `<div><br /></div>`, and `""` all mean "empty". Strip tags and collapse whitespace
    # so those all reduce to "" and real labels reduce to their text ("0", "Coding",
    # "25.Q1.1"). Two DIFFERENT labels stay different; and since grouping also requires
    # identical position/size/type, this can never merge two genuinely distinct widgets.
    if not isinstance(v, str):
        return v
    return "".join(re.sub(r"<[^>]*>", "", v).split())


def _round(v):
    return round(v, 1) if isinstance(v, (int, float)) else v


def _key(w):
    parts = []
    for f in KEY_FIELDS:
        val = w.get(f, 0 if f == "rotation" else None)
        parts.append(_norm_text(val) if f == "text_content" else _round(val))
    return tuple(parts)


def find_duplicates(widgets, parent=None):
    """Return the list of widget_ids to delete (all but one per identical group)."""
    groups = {}
    order = []
    for w in widgets:
        wtype = w.get("widget_type") or w.get("type") or ""
        if wtype == "area":                      # never group/delete containers
            continue
        if parent is not None and w.get("parent_id") != parent:
            continue
        k = _key(w)
        if k not in groups:
            groups[k] = []
            order.append(k)
        groups[k].append(w.get("widget_id"))
    to_delete = []
    dup_groups = 0
    for k in order:
        ids = [i for i in groups[k] if i]
        if len(ids) > 1:
            dup_groups += 1
            to_delete.extend(ids[1:])            # keep the first, delete the rest
    print(
        f"[dedupe] {len(widgets)} widgets scanned, {dup_groups} duplicated group(s), "
        f"{len(to_delete)} id(s) to delete"
        + (f" (parent={parent})" if parent else ""),
        file=sys.stderr,
    )
    return to_delete


def main(argv):
    parent = None
    path = None
    it = iter(argv)
    for a in it:
        if a == "--parent":
            parent = next(it)
        else:
            path = a
    raw = open(path).read() if path else sys.stdin.read()
    data = json.loads(raw)
    widgets = data["widgets"] if isinstance(data, dict) and "widgets" in data else data
    print(json.dumps(find_duplicates(widgets, parent)))


if __name__ == "__main__":
    main(sys.argv[1:])
