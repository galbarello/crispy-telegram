#!/usr/bin/env python3
"""
plan_reset.py — turn a `list_widgets` dump + a template spec into a reset plan.

Classifies every widget into keep / clear / move / delete by TYPE, sticky COLOR, and
POSITION (never by id, so it works on a duplicated board with fresh ids). See
../references/retro-template-spec.md for the spec schema and the ready-to-use S/S/C spec.

Usage:
    plan_reset.py <dump.json> --spec <spec.json> [--out plan.json]

    <dump.json>  : {"widgets": [ ... ]} as returned by list_widgets (view="full").
                   Also accepts a bare list, or the raw {"widgets": [...]} tool envelope.

Output (stdout, or --out):
    {
      "clear":  ["<sticky_id>", ...],                 # blank via set_sticky_text(id, "")
      "moves":  [{"widget_id": "...", "x": N, "y": N}], # re-home via update_widgets (idempotent)
      "delete": ["<id>", ...],                          # remove via delete_widget([...])
      "unclassified": ["<id>", ...],                    # left untouched; a human decides
      "summary": { ... }
    }

A human-readable summary is also printed to stderr. The planner NEVER puts unclassified
widgets in `delete`.
"""
import argparse
import json
import sys


def _load(path):
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("widgets", data.get("value", []))
    raise SystemExit(f"unrecognized dump shape in {path}")


def _norm_color(c):
    return (c or "").strip().lower()


def _center(w):
    x = w.get("position_x", w.get("x", 0)) or 0
    y = w.get("position_y", w.get("y", 0)) or 0
    ww = w.get("width") or 0
    hh = w.get("height") or 0
    return x + ww / 2.0, y + hh / 2.0


def _wtype(w):
    return (w.get("widget_type") or w.get("type") or "").split(".")[-1].lower()


def _wid(w):
    return w.get("widget_id") or w.get("id")


def _in_zone(cx, cy, z):
    return z["x"] <= cx <= z["x"] + z["width"] and z["y"] <= cy <= z["y"] + z["height"]


def _home_cells(band):
    cells = []
    for r in range(band["rows"]):
        for c in range(band["cols"]):
            cells.append(
                (band["x0"] + c * band["step_x"], band["y0"] + r * band["step_y"])
            )
    return cells  # reading order: row by row, left to right


def plan(widgets, spec):
    clear, moves, delete = [], [], []
    unclassified = []
    processed = set()

    delete_anywhere = {t.lower() for t in spec.get("delete_types_anywhere", [])}
    zone_del_types = {t.lower() for t in spec.get("content_zone_delete_types",
                                                  ["sticky_note", "connector", "comment"])}
    protect = spec.get("protect_text_contains", [])

    # 0) delete-everywhere types (e.g. comments)
    for w in widgets:
        if _wtype(w) in delete_anywhere:
            delete.append(_wid(w))
            processed.add(_wid(w))

    # 1) bands: assign the first cols*rows stickies of each color to home cells,
    #    clear their text; delete the color's extras.
    stickies = [w for w in widgets
                if _wtype(w) == "sticky_note" and _wid(w) not in processed]
    per_band = {}
    for w in stickies:
        col = _norm_color(w.get("background_color"))
        per_band.setdefault(col, []).append(w)

    band_colors = set()
    for band in spec["bands"]:
        color = _norm_color(band["color"])
        band_colors.add(color)
        cands = per_band.get(color, [])
        # reading-order sort by current position so the snap is stable
        cands.sort(key=lambda w: (_center(w)[1], _center(w)[0]))
        cells = _home_cells(band)
        capacity = len(cells)
        keepers, extras = cands[:capacity], cands[capacity:]
        for i, w in enumerate(keepers):
            wid = _wid(w)
            hx, hy = cells[i]
            moves.append({"widget_id": wid, "x": hx, "y": hy})
            clear.append(wid)
            processed.add(wid)
        for w in extras:
            delete.append(_wid(w))
            processed.add(_wid(w))

    # 2) content zones: delete matching, unprocessed widgets inside a zone
    zones = spec.get("content_zones", [])
    for w in widgets:
        wid = _wid(w)
        if wid in processed:
            continue
        t = _wtype(w)
        cx, cy = _center(w)
        if any(_in_zone(cx, cy, z) for z in zones) and t in zone_del_types:
            text = (w.get("text_content") or "")
            if t == "text" and any(p in text for p in protect):
                processed.add(wid)  # scaffold text in a zone — keep
                continue
            delete.append(wid)
            processed.add(wid)

    # 3) leftover stickies (color matches no band, not in a zone) -> unclassified
    for w in stickies:
        wid = _wid(w)
        if wid in processed:
            continue
        col = _norm_color(w.get("background_color"))
        if col not in band_colors:
            unclassified.append(wid)
            processed.add(wid)

    # de-dupe while preserving order
    def _uniq(seq):
        seen, out = set(), []
        for x in seq:
            k = x if isinstance(x, str) else x["widget_id"]
            if k not in seen:
                seen.add(k)
                out.append(x)
        return out

    clear, delete, unclassified = _uniq(clear), _uniq(delete), _uniq(unclassified)
    moves = _uniq(moves)

    summary = {
        "total_widgets": len(widgets),
        "clear": len(clear),
        "moves": len(moves),
        "delete": len(delete),
        "unclassified": len(unclassified),
        "kept": len(widgets) - len(delete) - len(unclassified),
    }
    return {
        "clear": clear,
        "moves": moves,
        "delete": delete,
        "unclassified": unclassified,
        "summary": summary,
    }


def main():
    ap = argparse.ArgumentParser(description="Plan a retro-template reset.")
    ap.add_argument("dump", help="list_widgets dump JSON")
    ap.add_argument("--spec", required=True, help="template spec JSON")
    ap.add_argument("--out", help="write plan JSON here (default: stdout)")
    args = ap.parse_args()

    widgets = _load(args.dump)
    with open(args.spec) as f:
        spec = json.load(f)

    result = plan(widgets, spec)

    out = json.dumps(result, indent=2)
    if args.out:
        with open(args.out, "w") as f:
            f.write(out)
    else:
        print(out)

    s = result["summary"]
    print(
        f"\n[plan_reset] {s['total_widgets']} widgets -> "
        f"clear {s['clear']}, move {s['moves']}, delete {s['delete']}, "
        f"keep {s['kept']}, {s['unclassified']} unclassified.",
        file=sys.stderr,
    )
    if result["unclassified"]:
        print(
            "[plan_reset] unclassified stickies were left untouched — review them by hand.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
