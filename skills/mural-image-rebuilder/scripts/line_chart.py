#!/usr/bin/env python3
"""
line_chart.py — compute create-ready Mural widget arrays for a (multi-series) line chart.

This is the reusable version of the geometry that the SKILL.md `line` guidance describes:
point coordinates on a value scale, hypotenuse-length centered segments (width = hypot(dx,dy),
rotation = atan2(dy,dx)), point markers, gridlines, y-axis ticks, x-axis category labels, and
a legend. It does the trig once so a build never has to hand-compute rotations.

USAGE
    python3 line_chart.py spec.json          # read spec from a file
    cat spec.json | python3 line_chart.py    # or from stdin
    python3 line_chart.py spec.json --part series.Cycle   # print just one array

It prints a JSON object whose values are arrays you pass straight to the Mural MCP:
    {
      "area":            {create_areas: [ this ]}          # only if spec.area given
      "scaffold_shapes": [gridlines...]  -> create_shapes   # create FIRST (renders under data)
      "legend_shapes":   [swatches...]   -> create_shapes
      "title":           [ ... ]         -> create_titles
      "textboxes":       [subtitle, y-labels, legend labels, x-labels] -> create_textboxes
      "series": { "<name>": [segments... then markers...] -> create_shapes (one call/series) }
    }
Within each series array, segments come before markers so markers render on top. Every widget
carries `parent_id` when the spec provides one. `create_*` uses ABSOLUTE coordinates, so create
the area first, then everything else with the returned area id as parent_id.

SPEC (JSON) — only `series` is strictly required; everything else has defaults.
    {
      "area":    {"x":100,"y":2726,"w":1660,"h":686},   # optional; enables derivation + area output
      "parent_id": "0-...",                              # set to the area id once created
      "y_axis":  {"min":0, "max":20000, "step":5000},   # ticks at min..max by step
      "x_labels": ["25.Q1.1", ...],                      # one per data point (drives point count)
      "series":  [{"name":"Cycle","color":"#FF9900","values":[...]}, ...],
      "title":    "Coding, Pickup, Review, Deploy and Cycle",
      "subtitle": "Cycle time (hours) by sprint",
      "x_axis_title": "Sprint",                          # optional bold label under the x labels

      # ---- optional explicit geometry (else derived from `area` + the paddings below) ----
      "plot": {"left":204.5, "right":1695.5, "baseline_y":3264.5, "top_y":2844.5},
      "x":    {"first_center":210, "last_center":1690},
      "style": {"marker":9, "segment_thickness":3, "gridline_color":"#eaeaea",
                 "label_color":"#6b6480", "title_color":"#1e2340",
                 "pad_left":105, "pad_right":65, "plot_top_pad":118, "plot_bottom_pad":148,
                 "x_first_pad":6, "x_last_pad":6}
    }
Derivation (when `plot`/`x` omitted and `area` given):
    plot.left      = area.x + style.pad_left
    plot.right     = area.x + area.w - style.pad_right
    plot.baseline_y= area.y + area.h - style.plot_bottom_pad
    plot.top_y     = area.y + style.plot_top_pad
    x.first_center = plot.left + style.x_first_pad ;  x.last_center = plot.right - style.x_last_pad
"""
import json
import math
import sys


DEFAULT_STYLE = {
    "marker": 9,
    "segment_thickness": 3,
    "gridline_color": "#eaeaea",
    "label_color": "#6b6480",
    "title_color": "#1e2340",
    "subtitle_color": "#6b6480",
    "title_font": 18,
    "subtitle_font": 11,
    "y_label_font": 10,
    "x_label_font": 7,
    "legend_font": 11,
    "legend_swatch": 16,
    "legend_gap": 110,           # x-step between legend entries
    "legend_label_dx": 22,       # label x offset from its swatch
    "pad_left": 105,
    "pad_right": 65,
    "plot_top_pad": 118,
    "plot_bottom_pad": 148,
    "x_first_pad": 6,
    "x_last_pad": 6,
    "legend_top_pad": 57,        # legend y offset below area top
    "title_pad": 14,             # title y offset below area top
}


def _pid(spec):
    return spec.get("parent_id")


def _with_pid(w, spec):
    pid = _pid(spec)
    if pid is not None:
        w["parent_id"] = pid
    return w


def build(spec):
    style = dict(DEFAULT_STYLE)
    style.update(spec.get("style", {}))

    series = spec["series"]
    x_labels = spec.get("x_labels", [])
    n = len(x_labels) if x_labels else max(len(s["values"]) for s in series)
    if n < 2:
        raise ValueError("need at least 2 points to draw a line")

    area = spec.get("area")
    yax = spec.get("y_axis", {"min": 0, "max": None, "step": None})
    ymin = yax.get("min", 0)
    ymax = yax.get("max")
    if ymax is None:
        ymax = max(max(s["values"]) for s in series)
    step = yax.get("step") or (ymax - ymin) / 4.0

    # --- geometry: explicit `plot`/`x` win, else derive from area + paddings ---
    # Paddings default to values tuned for tall charts; on a COMPACT area they can exceed the
    # height and invert the plot (baseline_y ends up above top_y), plotting the data upside-down.
    # Fall back to proportional paddings when the fixed ones don't leave a positive-height plot.
    tp, bp = style["plot_top_pad"], style["plot_bottom_pad"]
    if area and tp + bp >= area["h"] - 20:
        tp = max(26, round(area["h"] * 0.16))
        bp = max(30, round(area["h"] * 0.22))
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
    xspec = spec.get("x")
    if xspec is None:
        xspec = {
            "first_center": plot["left"] + style["x_first_pad"],
            "last_center": plot["right"] - style["x_last_pad"],
        }

    left, right = plot["left"], plot["right"]
    baseline_y, top_y = plot["baseline_y"], plot["top_y"]
    x0, x1 = xspec["first_center"], xspec["last_center"]
    dx = (x1 - x0) / (n - 1)

    def px(i):
        return x0 + dx * i

    def py(v):
        v = min(max(v, ymin), ymax)
        return baseline_y - (baseline_y - top_y) * (v - ymin) / (ymax - ymin)

    mk = style["marker"]
    th = style["segment_thickness"]

    out = {}

    # area (optional passthrough so a caller can create it in one shot)
    if area:
        a = {"x": area["x"], "y": area["y"], "width": area["w"], "height": area["h"],
             "title": spec.get("title", ""), "showTitle": False}
        for k in ("background", "strokeColor", "strokeWidth"):
            if k in area:
                a[k] = area[k]
        out["area"] = [a]

    # gridlines (one per tick value), full plot width
    grid = []
    ticks = []
    t = ymin
    # accumulate ticks robustly against float drift
    k = 0
    while True:
        val = ymin + step * k
        if val > ymax + 1e-6:
            break
        ticks.append(val)
        k += 1
    for val in ticks:
        gy = py(val)
        grid.append(_with_pid({
            "shape_type": "rectangle", "x": round(left, 2), "y": round(gy - th / 2.0, 2),
            "width": round(right - left, 2), "height": th,
            "background_color": style["gridline_color"],
            "stroke_color": style["gridline_color"], "stroke_size": 0,
        }, spec))
    out["scaffold_shapes"] = grid

    # y-axis labels (left gutter)
    ylab = []
    y_label_x = (area["x"] + 50) if area else round(left - 55, 1)
    for val in ticks:
        ylab.append(_with_pid({
            "x": y_label_x, "y": round(py(val) - 6, 1), "width": 55,
            "text": _fmt(val), "font_size": style["y_label_font"],
            "font_color": style["label_color"],
        }, spec))

    # x-axis category labels (centered under each point)
    xlab = []
    x_label_y = round(baseline_y + 9.5, 1)
    for i, lab in enumerate(x_labels):
        xlab.append(_with_pid({
            "x": round(px(i) - 24, 1), "y": x_label_y, "width": 48, "text": str(lab),
            "font_size": style["x_label_font"], "font_color": style["label_color"],
            "text_align": "center",
        }, spec))

    # title
    titles = []
    if spec.get("title"):
        tx = (area["x"] + 50) if area else round(left, 1)
        ty = (area["y"] + style["title_pad"]) if area else round(top_y - 100, 1)
        titles.append(_with_pid({
            "x": tx, "y": ty, "width": 700, "text": spec["title"],
            "font_size": style["title_font"], "font_color": style["title_color"], "bold": True,
        }, spec))
    out["title"] = titles

    # subtitle (top-right)
    textboxes = []
    if spec.get("subtitle"):
        sx = round(right - 395, 1) if not area else (area["x"] + area["w"] - 460)
        sy = (area["y"] + style["title_pad"] + 6) if area else round(top_y - 94, 1)
        textboxes.append(_with_pid({
            "x": sx, "y": sy, "width": 400, "text": spec["subtitle"],
            "font_size": style["subtitle_font"], "font_color": style["subtitle_color"],
        }, spec))

    # legend (swatch shapes + label textboxes), in the top band above the plot.
    # Fit within the plot/area width: clamp the start x and the gap so the last entry
    # (+ its ~90px label) stays inside the right edge instead of overflowing a narrow area.
    legend_shapes = []
    sw = style["legend_swatch"]
    n_series = len(series)
    right_edge = (area["x"] + area["w"] - style["pad_right"]) if area else right
    gap = style["legend_gap"]
    legend_x0 = round(left + 350, 1) if not area else round(area["x"] + 459, 1)
    if legend_x0 + gap * (n_series - 1) + 90 > right_edge:
        legend_x0 = round((area["x"] + style["pad_left"]) if area else left, 1)
        if n_series > 1:
            gap = max(70, min(gap, (right_edge - legend_x0 - 90) / (n_series - 1)))
    # sit the legend row in the top band (between area top and the plot), never over the data
    if area:
        legend_y = round(max(area["y"] + 2, min(area["y"] + style["legend_top_pad"], top_y - sw - 4)), 1)
    else:
        legend_y = round(top_y - 60, 1)
    for j, s in enumerate(series):
        lx = round(legend_x0 + gap * j, 1)
        legend_shapes.append(_with_pid({
            "shape_type": "rounded_square", "x": lx, "y": legend_y,
            "width": sw, "height": sw, "background_color": s["color"],
            "stroke_color": s["color"], "stroke_size": 0,
        }, spec))
        textboxes.append(_with_pid({
            "x": round(lx + style["legend_label_dx"], 1), "y": round(legend_y + 0.5, 1),
            "width": 90, "text": s["name"], "font_size": style["legend_font"],
            "font_color": style["title_color"],
        }, spec))
    out["legend_shapes"] = legend_shapes

    # optional x-axis title, centered under the category labels
    if spec.get("x_axis_title"):
        textboxes.append(_with_pid({
            "x": round((left + right) / 2.0 - 80, 1), "y": round(x_label_y + 29, 1),
            "width": 160, "text": spec["x_axis_title"], "font_size": style["legend_font"],
            "font_color": "#4a4e63", "bold": True, "text_align": "center",
        }, spec))

    out["textboxes"] = ylab + xlab + textboxes

    # series: segments (under) then markers (on top)
    out["series"] = {}
    for s in series:
        vals = s["values"]
        color = s["color"]
        pts = [(px(i), py(vals[i])) for i in range(len(vals))]
        arr = []
        for i in range(len(pts) - 1):
            x_a, y_a = pts[i]
            x_b, y_b = pts[i + 1]
            ddx, ddy = x_b - x_a, y_b - y_a
            length = math.hypot(ddx, ddy)
            ang_rad = math.atan2(ddy, ddx)
            # Mural rotates a shape about its TOP-LEFT corner (the x,y anchor), NOT its center.
            # So anchor the segment at the START point A: place the box's top-left corner so that
            # its left-edge midpoint lands on A after the rotation, then it spans length L along
            # the A->B direction and its far end lands on B. (h is tiny, so the offset is ~h/2.)
            x_tl = x_a + (th / 2.0) * math.sin(ang_rad)
            y_tl = y_a - (th / 2.0) * math.cos(ang_rad)
            arr.append(_with_pid({
                "shape_type": "rectangle", "x": round(x_tl, 2),
                "y": round(y_tl, 2), "width": round(length, 2), "height": th,
                "rotation": round(math.degrees(ang_rad), 2), "background_color": color,
                "stroke_color": color, "stroke_size": 0,
            }, spec))
        for (cx, cy) in pts:
            arr.append(_with_pid({
                "shape_type": "ellipse", "x": round(cx - mk / 2.0, 2),
                "y": round(cy - mk / 2.0, 2), "width": mk, "height": mk,
                "background_color": color, "stroke_color": color, "stroke_size": 0,
            }, spec))
        out["series"][s["name"]] = arr

    return out


def _fmt(v):
    return str(int(v)) if float(v).is_integer() else str(v)


def _get_part(obj, path):
    cur = obj
    for key in path.split("."):
        cur = cur[key]
    return cur


def main(argv):
    part = None
    args = []
    it = iter(argv)
    for a in it:
        if a == "--part":
            part = next(it)
        else:
            args.append(a)
    raw = open(args[0]).read() if args else sys.stdin.read()
    spec = json.loads(raw)
    result = build(spec)
    print(json.dumps(_get_part(result, part) if part else result))


if __name__ == "__main__":
    main(sys.argv[1:])
