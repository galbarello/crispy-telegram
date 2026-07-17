#!/usr/bin/env python3
"""
reflect_status.py — turn a `list_widgets` dump + a tracker config into the shared-status update.

Reads where each participant's token currently sits, decides who is DONE (token center inside the
Done zone), and emits the idempotent `update_widgets` payload for the shared status widgets (the
"N of M finished" count, the progress-bar fill width, and the per-person ✓ row). Pure function, no
board round-trips — the skill's reflection loop calls this between one `list_widgets` read and one
`update_widgets` write. See ../references/tracker-spec.md for the tracker layout.

Usage:
    reflect_status.py <dump.json> --config <config.json> [--out updates.json]

    <dump.json>  : list_widgets output (view="full"). Accepts {"widgets":[...]}, {"value":[...]},
                   or a bare list.
    <config.json>:
      {
        "roster": ["Ana", "Ben", ...],
        "done_zone": {"x": 640, "y": 90, "width": 540, "height": 120},
        "status_widgets": {
          "count_id": "0-123",                              # optional: "N of M finished" textbox
          "progress": {"fill_id": "0-124", "track_width": 480},  # optional: inner fill rectangle
          "checks": {"Ana": "0-201", "Ben": "0-202", ...}   # optional: per-person ✓ textboxes
        }
      }

Output (stdout, or --out):
    {
      "done": ["Eli", "Fio"], "working": ["Ana", ...], "missing": [...],
      "count": {"done": 2, "total": 8}, "progress": 0.25,
      "updates": [ {"widget_id": "...", "values": {...}}, ... ],  # feed straight to update_widgets
      "summary": { ... }
    }

`missing` = roster names with no matching token on the board (left out of done/working; surfaced,
never guessed). Tokens are matched to roster names by their text, case-insensitively.
"""
import argparse
import json
import re
import sys

_TAG = re.compile(r"<[^>]+>")


def _load(path):
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("widgets", data.get("value", []))
    raise SystemExit(f"unrecognized dump shape in {path}")


def _center(w):
    x = w.get("position_x", w.get("x", 0)) or 0
    y = w.get("position_y", w.get("y", 0)) or 0
    ww = w.get("width") or 0
    hh = w.get("height") or 0
    return x + ww / 2.0, y + hh / 2.0


def _wid(w):
    return w.get("widget_id") or w.get("id")


def _text(w):
    raw = w.get("text_content", w.get("text", "")) or ""
    return _TAG.sub("", raw).strip()


def _norm(s):
    return (s or "").strip().lower()


def _in_zone(cx, cy, z):
    return z["x"] <= cx <= z["x"] + z["width"] and z["y"] <= cy <= z["y"] + z["height"]


def reflect(widgets, config):
    roster = config["roster"]
    done_zone = config["done_zone"]
    sw = config.get("status_widgets", {})

    # match each roster name to its token widget by (normalized) text
    by_name = {_norm(n): None for n in roster}
    for w in widgets:
        key = _norm(_text(w))
        if key in by_name and by_name[key] is None:
            by_name[key] = w

    done, working, missing = [], [], []
    for name in roster:
        w = by_name[_norm(name)]
        if w is None:
            missing.append(name)
            continue
        cx, cy = _center(w)
        (done if _in_zone(cx, cy, done_zone) else working).append(name)

    total = len(roster)
    n_done = len(done)
    progress = (n_done / total) if total else 0.0

    updates = []
    if sw.get("count_id"):
        updates.append({"widget_id": sw["count_id"],
                        "values": {"text": f"{n_done} of {total} finished"}})
    prog = sw.get("progress")
    if prog and prog.get("fill_id"):
        width = int(round(progress * prog.get("track_width", 0)))
        updates.append({"widget_id": prog["fill_id"], "values": {"width": width}})
    for name, wid in (sw.get("checks") or {}).items():
        is_done = name in done
        glyph = "✓" if is_done else "◦"  # ✓ / ◦
        color = "#00C27A" if is_done else "#666666"
        updates.append({"widget_id": wid,
                        "values": {"text": f"{glyph} {name}", "color": color}})

    return {
        "done": done,
        "working": working,
        "missing": missing,
        "count": {"done": n_done, "total": total},
        "progress": round(progress, 4),
        "updates": updates,
        "summary": {
            "done": n_done, "working": len(working), "missing": len(missing),
            "updates": len(updates),
        },
    }


def main():
    ap = argparse.ArgumentParser(description="Reflect token positions into the shared status.")
    ap.add_argument("dump", help="list_widgets dump JSON")
    ap.add_argument("--config", required=True, help="tracker config JSON")
    ap.add_argument("--out", help="write updates JSON here (default: stdout)")
    args = ap.parse_args()

    widgets = _load(args.dump)
    with open(args.config) as f:
        config = json.load(f)

    result = reflect(widgets, config)

    out = json.dumps(result, indent=2)
    if args.out:
        with open(args.out, "w") as f:
            f.write(out)
    else:
        print(out)

    s = result["summary"]
    print(
        f"\n[reflect_status] {s['done']} done, {s['working']} working, "
        f"{s['missing']} missing -> {s['updates']} widget updates.",
        file=sys.stderr,
    )
    if result["missing"]:
        print(
            f"[reflect_status] no token found for: {', '.join(result['missing'])} "
            "— surfaced, not guessed.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
