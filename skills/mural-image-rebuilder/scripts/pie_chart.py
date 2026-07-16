#!/usr/bin/env python3
"""
pie_chart.py — compute create-ready Mural widget arrays for a "pie chart".

Mural has NO arc/wedge primitive, so a true pie is not constructible (same limit as the
gauge). The faithful, data-exact substitute — per the SKILL.md `pie` guidance — is a
100%-STACKED HORIZONTAL BAR plus a legend that carries each slice's label, value, and %.
This script does the proportion math once and emits the widgets, so a pie build is as
repeatable as a line chart (see the sibling line_chart.py).

USAGE
    python3 pie_chart.py spec.json
    cat spec.json | python3 pie_chart.py
    python3 pie_chart.py spec.json --part bar_shapes    # print just one array

It prints a JSON object of create-ready arrays:
    {
      "area":          [ ... ]  -> create_areas     (only if spec.area given)
      "bar_shapes":    [ ... ]  -> create_shapes     (the stacked segments — create FIRST)
      "legend_shapes": [ ... ]  -> create_shapes     (legend colour chips)
      "title":         [ ... ]  -> create_titles
      "textboxes":     [ ... ]  -> create_textboxes  (subtitle, % labels, legend labels)
    }
Create bar_shapes + legend_shapes first (they render under), then the text on top. Every
widget carries `parent_id` when the spec provides one; `create_*` uses ABSOLUTE coords, so
create the area first and pass its returned id back as `parent_id`.

AFTER BUILDING: run the Layer-6 dedup check (the Mural bridge sometimes double-applies a
create). Compare get_canvas_overview to the intended count; if higher, dump the area with
list_widgets (full) and clean with scripts/dedupe_widgets.py --parent <area_id>.

SPEC (JSON) — only `slices` is required.
    {
      "area":    {"x":100,"y":3480,"w":1660,"h":320},   # optional; enables layout derivation
      "parent_id": "0-...",                              # the area id once created
      "title":    "Cycle Time by Phase - Share of Total",
      "subtitle": "Share of total cycle time (30 sprints). Not a true pie - Mural has no wedge.",
      "slices":  [{"name":"Coding","value":2368.8,"color":"#4285F4"}, ...],
      "value_suffix": " h",     # optional; appended to the value in the legend (e.g. " h")
      "value_decimals": 1,      # optional; rounding for the value shown in the legend

      # optional explicit geometry (else derived from `area` + the style paddings below)
      "bar": {"left":150, "width":1000, "y":3596, "height":44},
      "style": {"pad_left":50, "bar_top_pad":116, "bar_height":44, "bar_width":1000,
                 "pct_label_gap":24, "legend_gap_below":84,
                 "title_color":"#1e2340", "label_color":"#1e2340", "subtitle_color":"#6b6480",
                 "title_font":18, "subtitle_font":11, "pct_font":11, "legend_font":11,
                 "legend_swatch":16, "min_pct_for_inline_label":3.0}
    }
`min_pct_for_inline_label`: slices below this % get no inline % label above the bar (too
narrow to read); their share still shows in the legend.
"""
import json
import sys


DEFAULT_STYLE = {
    "pad_left": 50,
    "bar_top_pad": 116,       # bar_y = area.y + this
    "bar_height": 44,
    "bar_width": 1000,
    "pct_label_gap": 24,      # % labels sit this far above the bar top
    "legend_gap_below": 84,   # legend row sits this far below the bar top
    "title_pad": 16,          # title y = area.y + this
    "title_color": "#1e2340",
    "label_color": "#1e2340",
    "subtitle_color": "#6b6480",
    "title_font": 18,
    "subtitle_font": 11,
    "pct_font": 11,
    "legend_font": 11,
    "legend_swatch": 16,
    "min_pct_for_inline_label": 3.0,
}


def _with_pid(w, spec):
    pid = spec.get("parent_id")
    if pid is not None:
        w["parent_id"] = pid
    return w


def _fmt_val(v, decimals):
    if float(v).is_integer():
        return str(int(v))
    return f"{v:.{decimals}f}"


def build(spec):
    style = dict(DEFAULT_STYLE)
    style.update(spec.get("style", {}))
    slices = spec["slices"]
    if not slices:
        raise ValueError("need at least one slice")
    total = sum(s["value"] for s in slices)
    if total <= 0:
        raise ValueError("slice values must sum to > 0")

    area = spec.get("area")
    bar = spec.get("bar")
    if bar is None:
        if not area:
            raise ValueError("provide either `bar` geometry or an `area` to derive it from")
        bar = {
            "left": area["x"] + style["pad_left"],
            "width": style["bar_width"],
            "y": area["y"] + style["bar_top_pad"],
            "height": style["bar_height"],
        }
    left, bar_w, bar_y, bar_h = bar["left"], bar["width"], bar["y"], bar["height"]
    decimals = spec.get("value_decimals", 1)
    suffix = spec.get("value_suffix", "")

    out = {}

    if area:
        a = {"x": area["x"], "y": area["y"], "width": area["w"], "height": area["h"],
             "title": spec.get("title", ""), "showTitle": False}
        for k in ("background", "strokeColor", "strokeWidth"):
            if k in area:
                a[k] = area[k]
        out["area"] = [a]

    # stacked bar segments + inline % labels
    bar_shapes = []
    textboxes = []
    cx = left
    pct_y = round(bar_y - style["pct_label_gap"], 2)
    for s in slices:
        frac = s["value"] / total
        w = bar_w * frac
        pct = 100 * frac
        bar_shapes.append(_with_pid({
            "shape_type": "rectangle", "x": round(cx, 2), "y": round(bar_y, 2),
            "width": round(w, 2), "height": bar_h,
            "background_color": s["color"], "stroke_color": s["color"], "stroke_size": 0,
        }, spec))
        if pct >= style["min_pct_for_inline_label"]:
            textboxes.append(_with_pid({
                "x": round(cx + w / 2.0 - 60, 2), "y": pct_y, "width": 120,
                "text": f"{pct:.1f}%", "font_size": style["pct_font"],
                "font_color": style["label_color"], "bold": True, "text_align": "center",
            }, spec))
        cx += w
    out["bar_shapes"] = bar_shapes

    # title
    titles = []
    if spec.get("title"):
        tx = (area["x"] + style["pad_left"]) if area else round(left, 2)
        ty = (area["y"] + style["title_pad"]) if area else round(bar_y - 100, 2)
        titles.append(_with_pid({
            "x": tx, "y": ty, "width": 700, "text": spec["title"],
            "font_size": style["title_font"], "font_color": style["title_color"], "bold": True,
        }, spec))
    out["title"] = titles

    # subtitle (top-right)
    if spec.get("subtitle"):
        sx = (area["x"] + area["w"] - 460) if area else round(left + bar_w - 400, 2)
        sy = (area["y"] + style["title_pad"] + 6) if area else round(bar_y - 94, 2)
        textboxes.insert(0, _with_pid({
            "x": sx, "y": sy, "width": 460, "text": spec["subtitle"],
            "font_size": style["subtitle_font"], "font_color": style["subtitle_color"],
        }, spec))

    # legend: chip per slice + "name - value{suffix} - pct%"
    legend_shapes = []
    n = len(slices)
    legend_left = left
    span = (area["w"] - 2 * style["pad_left"]) if area else bar_w
    gap = span / n
    legend_y = round(bar_y + style["legend_gap_below"], 2)
    sw = style["legend_swatch"]
    for i, s in enumerate(slices):
        lx = legend_left + gap * i
        pct = 100 * s["value"] / total
        legend_shapes.append(_with_pid({
            "shape_type": "rounded_square", "x": round(lx, 2), "y": round(legend_y, 2),
            "width": sw, "height": sw,
            "background_color": s["color"], "stroke_color": s["color"], "stroke_size": 0,
        }, spec))
        textboxes.append(_with_pid({
            "x": round(lx + sw + 6, 2), "y": round(legend_y - 1, 2),
            "width": round(gap - sw - 16, 2),
            "text": f"{s['name']} — {_fmt_val(s['value'], decimals)}{suffix} · {pct:.1f}%",
            "font_size": style["legend_font"], "font_color": style["label_color"],
        }, spec))
    out["legend_shapes"] = legend_shapes
    out["textboxes"] = textboxes
    return out


def _get_part(obj, path):
    cur = obj
    for key in path.split("."):
        cur = cur[key]
    return cur


def main(argv):
    part = None
    path = None
    it = iter(argv)
    for a in it:
        if a == "--part":
            part = next(it)
        else:
            path = a
    raw = open(path).read() if path else sys.stdin.read()
    spec = json.loads(raw)
    result = build(spec)
    print(json.dumps(_get_part(result, part) if part else result))


if __name__ == "__main__":
    main(sys.argv[1:])
