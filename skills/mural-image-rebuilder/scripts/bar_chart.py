#!/usr/bin/env python3
"""
bar_chart.py — compute create-ready Mural widget arrays for a (grouped) bar chart.

This is the reusable version of the geometry the SKILL.md `bar` guidance describes: one
rectangle per category value drawn UP FROM A BASELINE on a value scale, plus y-axis
gridlines/labels, centered category labels, per-bar value labels, and a legend for
multi-series (grouped) charts. It mirrors the sibling line_chart.py / pie_chart.py: same
`build(spec)` core, same derive-geometry-from-`area`-and-paddings pattern, same output
contract (arrays of create-ready widgets keyed by the Mural create tool that consumes them),
and the same compact-area padding fallback so a short section frame still yields a sane plot.

USAGE
    python3 bar_chart.py spec.json          # read spec from a file
    cat spec.json | python3 bar_chart.py    # or from stdin
    python3 bar_chart.py spec.json --part bar_shapes   # print just one array

It prints a JSON object whose values are arrays you pass straight to the Mural MCP:
    {
      "area":            [ ... ]  -> create_areas     (only if spec.area given)
      "scaffold_shapes": [gridlines...]  -> create_shapes  (create FIRST — renders under bars)
      "bar_shapes":      [bars...]       -> create_shapes  (the category bars)
      "legend_shapes":   [swatches...]   -> create_shapes  (multi-series only)
      "title":           [ ... ]         -> create_titles
      "textboxes":       [y-labels, x-labels, value-labels, legend labels] -> create_textboxes
    }
Create scaffold_shapes + bar_shapes + legend_shapes first (they render under), then the text
on top. Every widget carries `parent_id` when the spec provides one; `create_*` uses ABSOLUTE
coordinates, so create the area first and pass its returned id back as `parent_id`.

SPEC (JSON) — only `series` is strictly required.
    {
      "area":     {"x":120,"y":700,"w":1660,"h":460},   # optional; enables layout derivation
      "parent_id":"0-...",                               # the area id once created
      "x_labels": ["Mon","Tue","Wed","Thu","Fri"],       # category labels (drive bar count)
      "series":   [{"name":"Deploys","color":"#195AD7","values":[3,5,4,8,6]}, ...],
      "y_axis":   {"min":0,"max":10,"step":2},           # optional; else derived from data
      "y_unit":   "",                                     # optional suffix on value/axis labels
      "title":    "Weekly deploys",                      # optional (usually the section heading)
      "subtitle": "...",                                  # optional (top-right)

      # optional explicit geometry (else derived from `area` + the paddings in `style`)
      "plot":  {"left":..,"right":..,"baseline_y":..,"top_y":..},
      "style": {"pad_left":95,"pad_right":55,"plot_top_pad":70,"plot_bottom_pad":92, ...}
    }
Derivation (when `plot` omitted and `area` given) matches line_chart.py:
    plot.left      = area.x + style.pad_left
    plot.right     = area.x + area.w - style.pad_right
    plot.baseline_y= area.y + area.h - style.plot_bottom_pad
    plot.top_y     = area.y + style.plot_top_pad
"""
import json
import math
import sys


DEFAULT_STYLE = {
    "gridline_color": "#eaeaea",
    "label_color": "#6b6480",
    "title_color": "#1e2340",
    "subtitle_color": "#6b6480",
    "value_color": "#4a4e63",
    "title_font": 18,
    "subtitle_font": 11,
    "y_label_font": 10,
    "x_label_font": 10,
    "value_font": 10,
    "legend_font": 11,
    "legend_swatch": 16,
    "legend_gap": 130,           # x-step between legend entries
    "legend_label_dx": 22,       # label x offset from its swatch
    "pad_left": 95,
    "pad_right": 55,
    "plot_top_pad": 70,          # room above tallest bar for the legend/value labels
    "plot_bottom_pad": 92,       # room below baseline for x labels
    "group_pad_frac": 0.16,      # blank fraction on each side of a category slot
    "bar_gap_frac": 0.12,        # blank fraction between bars within a group
    "title_pad": 14,
    "legend_top_pad": 8,         # legend y offset below area top
    "min_bar_w_for_value": 14,   # skip the per-bar value label below this bar width
}


def _pid(spec):
    return spec.get("parent_id")


def _with_pid(w, spec):
    pid = _pid(spec)
    if pid is not None:
        w["parent_id"] = pid
    return w


def _fmt(v):
    return str(int(v)) if float(v).is_integer() else str(v)


def build(spec):
    style = dict(DEFAULT_STYLE)
    style.update(spec.get("style", {}))

    series = spec.get("series") or []
    if not series:
        raise ValueError("bar chart needs at least one series")
    for s in series:
        if not s.get("values"):
            raise ValueError("series %r has no values" % s.get("name"))

    x_labels = spec.get("x_labels", [])
    n = len(x_labels) if x_labels else max(len(s["values"]) for s in series)
    if n < 1:
        raise ValueError("bar chart needs at least one category")
    # Values must line up with the categories; a ragged series is a spec bug, not a layout one.
    for s in series:
        if len(s["values"]) != n:
            raise ValueError("series %r has %d values but there are %d categories"
                             % (s.get("name"), len(s["values"]), n))

    area = spec.get("area")
    yax = spec.get("y_axis", {}) or {}
    ymin = yax.get("min", 0)                       # bars grow from the baseline (usually 0)
    ymax = yax.get("max")
    if ymax is None:
        ymax = max(max(s["values"]) for s in series)
    if ymax <= ymin:                               # avoid a zero/negative scale
        ymax = ymin + 1
    step = yax.get("step") or (ymax - ymin) / 4.0

    # --- geometry: explicit `plot` wins, else derive from area + paddings (line_chart parity) ---
    # On a COMPACT area the fixed paddings can exceed the height and invert the plot; fall back
    # to proportional paddings when they don't leave a positive-height plot.
    tp, bp = style["plot_top_pad"], style["plot_bottom_pad"]
    if area and tp + bp >= area["h"] - 20:
        tp = max(24, round(area["h"] * 0.16))
        bp = max(28, round(area["h"] * 0.22))
    plot = spec.get("plot")
    if plot is None:
        if not area:
            raise ValueError("provide either `plot` bounds or an `area` to derive them from")
        plot = {
            "left": area["x"] + style["pad_left"],
            "right": area["x"] + area["w"] - style["pad_right"],
            "baseline_y": area["y"] + area["h"] - bp,
            "top_y": area["y"] + tp,
        }
    left, right = plot["left"], plot["right"]
    baseline_y, top_y = plot["baseline_y"], plot["top_y"]

    def py(v):
        v = min(max(v, ymin), ymax)
        return baseline_y - (baseline_y - top_y) * (v - ymin) / float(ymax - ymin)

    suffix = spec.get("y_unit", "")
    out = {}

    # area (optional passthrough so a caller can create it in one shot)
    if area:
        a = {"x": area["x"], "y": area["y"], "width": area["w"], "height": area["h"],
             "title": spec.get("title", ""), "showTitle": False}
        for k in ("background", "strokeColor", "strokeWidth"):
            if k in area:
                a[k] = area[k]
        out["area"] = [a]

    # y-axis ticks (accumulate against float drift, same as line_chart)
    ticks = []
    k = 0
    while True:
        val = ymin + step * k
        if val > ymax + 1e-6:
            break
        ticks.append(val)
        k += 1
    if ticks and ticks[-1] < ymax - 1e-6:
        ticks.append(ymax)

    # gridlines (one per tick), full plot width — create FIRST so bars render on top
    grid = []
    gth = 2
    for val in ticks:
        gy = py(val)
        grid.append(_with_pid({
            "shape_type": "rectangle", "x": round(left, 2), "y": round(gy - gth / 2.0, 2),
            "width": round(right - left, 2), "height": gth,
            "background_color": style["gridline_color"],
            "stroke_color": style["gridline_color"], "stroke_size": 0,
        }, spec))
    out["scaffold_shapes"] = grid

    # y-axis labels (left gutter)
    ylab = []
    y_label_x = round((area["x"] + 34) if area else (left - 61), 1)
    for val in ticks:
        ylab.append(_with_pid({
            "x": y_label_x, "y": round(py(val) - 7, 1), "width": 56,
            "text": _fmt(val) + suffix, "font_size": style["y_label_font"],
            "font_color": style["label_color"], "text_align": "right",
        }, spec))

    # --- bars: for each category slot, a group of one bar per series ---
    n_series = len(series)
    slot_w = (right - left) / float(n)
    group_pad = slot_w * style["group_pad_frac"]
    group_w = slot_w - 2 * group_pad
    inner_gap = (group_w * style["bar_gap_frac"]) if n_series > 1 else 0.0
    bar_w = (group_w - inner_gap * (n_series - 1)) / float(n_series)

    bar_shapes = []
    value_labels = []
    for i in range(n):
        slot_x = left + i * slot_w
        for j, s in enumerate(series):
            v = s["values"][i]
            bx = slot_x + group_pad + j * (bar_w + inner_gap)
            top = py(v)
            bh = max(0.0, baseline_y - top)
            color = s["color"]
            bar_shapes.append(_with_pid({
                "shape_type": "rectangle", "x": round(bx, 2), "y": round(top, 2),
                "width": round(bar_w, 2), "height": round(bh, 2),
                "background_color": color, "stroke_color": color, "stroke_size": 0,
            }, spec))
            # per-bar value label, centered over the bar (skip if the bar is too thin to read)
            if bar_w >= style["min_bar_w_for_value"]:
                value_labels.append(_with_pid({
                    "x": round(bx + bar_w / 2.0 - 30, 2), "y": round(top - 17, 2),
                    "width": 60, "text": _fmt(v) + suffix, "font_size": style["value_font"],
                    "font_color": style["value_color"], "bold": True, "text_align": "center",
                }, spec))
    out["bar_shapes"] = bar_shapes

    # x-axis category labels, centered under each slot
    xlab = []
    x_label_y = round(baseline_y + 8, 1)
    for i, lab in enumerate(x_labels):
        cxs = left + i * slot_w + slot_w / 2.0
        xlab.append(_with_pid({
            "x": round(cxs - slot_w / 2.0, 1), "y": x_label_y, "width": round(slot_w, 1),
            "text": str(lab), "font_size": style["x_label_font"],
            "font_color": style["label_color"], "text_align": "center",
        }, spec))

    # title (usually dropped by the caller in favour of the section heading)
    titles = []
    if spec.get("title"):
        tx = (area["x"] + 34) if area else round(left, 1)
        ty = (area["y"] + style["title_pad"]) if area else round(top_y - 60, 1)
        titles.append(_with_pid({
            "x": tx, "y": ty, "width": 700, "text": spec["title"],
            "font_size": style["title_font"], "font_color": style["title_color"], "bold": True,
        }, spec))
    out["title"] = titles

    textboxes = []
    if spec.get("subtitle"):
        sx = (area["x"] + area["w"] - 460) if area else round(right - 400, 1)
        sy = (area["y"] + style["title_pad"] + 6) if area else round(top_y - 54, 1)
        textboxes.append(_with_pid({
            "x": sx, "y": sy, "width": 460, "text": spec["subtitle"],
            "font_size": style["subtitle_font"], "font_color": style["subtitle_color"],
        }, spec))

    # legend (multi-series only): swatch shapes + label textboxes, in the top band
    legend_shapes = []
    if n_series > 1:
        sw = style["legend_swatch"]
        gap = style["legend_gap"]
        right_edge = right
        legend_x0 = round(left, 1)
        if legend_x0 + gap * (n_series - 1) + 90 > right_edge and n_series > 1:
            gap = max(70, min(gap, (right_edge - legend_x0 - 90) / (n_series - 1)))
        legend_y = round((area["y"] + style["legend_top_pad"]) if area else (top_y - 40), 1)
        # keep the legend row above the plot, never over the bars
        if area:
            legend_y = round(min(legend_y, top_y - sw - 4), 1)
        for j, s in enumerate(series):
            lx = round(legend_x0 + gap * j, 1)
            legend_shapes.append(_with_pid({
                "shape_type": "rounded_square", "x": lx, "y": legend_y,
                "width": sw, "height": sw, "background_color": s["color"],
                "stroke_color": s["color"], "stroke_size": 0,
            }, spec))
            textboxes.append(_with_pid({
                "x": round(lx + style["legend_label_dx"], 1), "y": round(legend_y + 0.5, 1),
                "width": 100, "text": s.get("name", ""), "font_size": style["legend_font"],
                "font_color": style["title_color"],
            }, spec))
    out["legend_shapes"] = legend_shapes

    out["textboxes"] = ylab + xlab + value_labels + textboxes
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
