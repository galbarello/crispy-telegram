#!/usr/bin/env python3
"""
compile_board.py — deterministic board-spec -> batched Mural create-payload compiler.

This is Sprint 2 of the build-speed effort (see repo-root PERFORMANCE-SPEC.md, "Sprint 2+").
It turns a muralize `board-spec` (schema: ../../muralize/references/board-spec.md) into a single
JSON object of create-ready widget arrays — the SAME output contract the sibling chart scripts
(line_chart.py / pie_chart.py) use — so a build never hand-computes coordinates. All geometry is
derived deterministically from each section's `grid`; text/colors come verbatim from the spec.

OUTPUT CONTRACT
    A JSON object printed to stdout, keyed by the Mural create tool that consumes each array:
        {
          "create_areas":     [ {x,y,width,height,title,showTitle,_key}, ... ],
          "create_titles":    [ {x,y,text,font_size,font_color,bold,_key,_parent}, ... ],
          "create_shapes":    [ {shape_type,x,y,width,height,background_color,...,_key,_parent}, ... ],
          "create_icons":     [ {noun_project_id,x,y,width,height,color,tags,_key,_parent}, ... ],
          "create_textboxes": [ {x,y,text,width,font_size,font_color,_key,_parent}, ... ],
          "connectors":       [ {from,to,loop?,arrow_type?}, ... ],   # references _keys, not ids
          "manual_blocks":    [ {section,type,reason,box}, ... ],      # uncompiled blocks
          "warnings":         [ "..." , ... ]                          # e.g. unresolved icons
        }
    Every emitted widget carries a stable logical `_key` (e.g. "sec2.card0.bg") and, where it
    belongs inside a section frame, a `_parent` key referencing the owning area's `_key`. The
    build wrapper creates the areas first, maps each returned area id back by position (see the
    "response-order finding" in PERFORMANCE-SPEC.md), sets `parent_id` from `_parent`, then
    creates the rest. `connectors[]` reference `_key`s via {from,to}; the wrapper resolves them
    to widget ids after the create batches and issues one create_connectors call. (Phase A blocks
    emit no connectors — the array is present for the Phase B handshake.)

    Field names mirror what the MCP create_* tools expect (x, y, width, height, background_color,
    stroke_color, stroke_size, text, font_size, font_color, text_align, bold, ...). Underscore-
    prefixed keys (_key, _parent) are compiler metadata the wrapper strips before the API call.

Z-ORDER / BACKGROUNDS-FIRST
    The MCP renders the LAST widget in a create list on top (confirmed experiment, Sprint 1), and
    the build order is create_areas -> create_titles -> create_shapes -> create_icons ->
    create_textboxes. So: areas sit at the bottom; fills/tints go in create_shapes ordered
    backgrounds-first (list position == paint order); icons over shapes; and body text goes in
    create_textboxes so it always lands on top of its fill. Centered "chip"/banner labels are
    baked into the shape's own `text` (shapes vertically-center text) to avoid an overlay.

PHASE A COVERAGE (this file)
    meta header (eyebrow, title, subtitle, tag chips), section (area + heading), banner, callout,
    cards, metrics, chips, and chart (line/pie via line_chart.build()/pie_chart.build()). Bar
    charts and every other block type pass through to `manual_blocks` for the model to build. See
    PERFORMANCE-SPEC.md Phase B/C for table, flow/comparison, and the metaphor blocks.

CLI
    python3 compile_board.py board-spec.json --palette palette.json --icons icon-registry.json
    cat board-spec.json | python3 compile_board.py --palette palette.json --icons icon-registry.json
    # --palette maps role->hex (resolved externally). Falls back to the spec's meta.palette, then
    #   to a built-in default, so a role always resolves.
    # --icons is the repo's references/icon-registry.json (concept->{noun_project_id,aliases});
    #   icon concepts resolve to a noun_project_id, else the icon is dropped and a warning recorded.
"""
import json
import math
import os
import sys

# line_chart.py / pie_chart.py live beside this file; import their reusable build() cores.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import line_chart  # noqa: E402
import pie_chart    # noqa: E402


# ---------------------------------------------------------------------------
# Fixed layout constants (deterministic geometry — no measuring, no vision).
# ---------------------------------------------------------------------------
CANVAS_X0 = 120           # board origin (top-left margin)
CANVAS_Y0 = 120
CONTENT_W_LANDSCAPE = 1660
CONTENT_W_PORTRAIT = 1120
COL_GUTTER = 40           # gap between side-by-side (left/right) sections
ROW_GUTTER = 48           # gap between stacked section rows
SECTION_PAD = 24          # inner padding inside a section frame
HEAD_BAND = 64            # reserved top band per section for its heading
PAD_BOTTOM = 24

CARD_GUTTER = 24
CARD_H = 156
MET_H = 132
CHIP_H = 40
CHIP_GAP = 12
BANNER_H = 96
CHART_LINE_H = 460
CHART_PIE_H = 320
MANUAL_H = 220            # placeholder frame height for uncompiled blocks

# Default palette (Mural brand roles from board-spec.md) — the resolution floor.
DEFAULT_PALETTE = {
    "primary": "#195AD7", "success": "#00C27A", "warning": "#FFAA00",
    "danger": "#FF4B4B", "accent": "#8728E6", "surface": "#F0F0F0", "ink": "#202124",
}
MUTED = "#6b6480"         # muted label color (matches the chart scripts)
CYCLE = ["primary", "accent", "success", "warning", "danger"]  # series color fallback order


# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------
def resolve(color, palette, fallback="ink"):
    """Resolve a palette role (or literal #hex) to a hex string. `fallback` is a role name."""
    if color and isinstance(color, str):
        if color.startswith("#"):
            return color
        if color in palette:
            return palette[color]
    return palette.get(fallback, DEFAULT_PALETTE["ink"])


def _hx(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def tint(hex_color, t):
    """Blend toward white by fraction t (0=orig, 1=white) — for light fills."""
    r, g, b = _hx(hex_color)
    r = round(r + (255 - r) * t)
    g = round(g + (255 - g) * t)
    b = round(b + (255 - b) * t)
    return "#%02X%02X%02X" % (r, g, b)


def contrast(hex_color):
    """Pick white or dark ink for legible text on the given fill."""
    r, g, b = _hx(hex_color)
    lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
    return "#FFFFFF" if lum < 0.6 else DEFAULT_PALETTE["ink"]


# ---------------------------------------------------------------------------
# Icon registry
# ---------------------------------------------------------------------------
def build_icon_index(icons_json):
    """concept/alias (lowercased) -> noun_project_id (string) from icon-registry.json."""
    idx = {}
    for concept, meta in (icons_json or {}).get("icons", {}).items():
        nid = meta.get("noun_project_id")
        if nid is None:
            continue
        idx[concept.lower()] = nid
        for alias in meta.get("aliases", []):
            idx.setdefault(alias.lower(), nid)
    return idx


def resolve_icon(item_icon, icon_index):
    """Return (noun_project_id:int|None, concept:str|None). Pre-resolved ids win over lookups."""
    if item_icon is None:
        return None, None
    if isinstance(item_icon, dict):
        nid = item_icon.get("noun_project_id")
        concept = item_icon.get("concept")
        if nid is not None:
            return int(nid), concept
    else:
        concept = item_icon
    if concept:
        nid = icon_index.get(str(concept).lower())
        if nid is not None:
            return int(nid), concept
    return None, concept


# ---------------------------------------------------------------------------
# Output accumulator
# ---------------------------------------------------------------------------
class Out:
    def __init__(self):
        self.d = {
            "create_areas": [], "create_titles": [], "create_shapes": [],
            "create_icons": [], "create_textboxes": [], "connectors": [],
            "manual_blocks": [], "warnings": [],
        }

    def add(self, bucket, widget, key, parent=None):
        widget["_key"] = key
        if parent is not None:
            widget["_parent"] = parent
        self.d[bucket].append(widget)
        return widget

    def warn(self, msg):
        self.d["warnings"].append(msg)

    def manual(self, section, btype, reason, box):
        self.d["manual_blocks"].append(
            {"section": section, "type": btype, "reason": reason, "box": box})


# ---------------------------------------------------------------------------
# Height estimation — used to size section frames before laying content inside.
# The builders below reproduce the same per-item pitch, so content always fits.
# ---------------------------------------------------------------------------
def _grid(n, cols):
    return int(math.ceil(n / float(cols))) if n else 0


def chip_width(label, inner_w):
    return min(inner_w, 28 + len(str(label)) * 9)


def chip_rows(items, inner_w):
    rows, x = 1, 0.0
    for it in items:
        label = it["label"] if isinstance(it, dict) else it
        w = chip_width(label, inner_w)
        if x > 0 and x + w > inner_w:
            rows += 1
            x = 0.0
        x += w + CHIP_GAP
    return rows


def content_height(block, inner_w):
    """Estimated content height (below the heading band) for a block at width inner_w."""
    if block is None:
        return MANUAL_H
    t = block.get("type")
    if t == "banner":
        return BANNER_H
    if t == "callout":
        text = block.get("text", "")
        cpl = max(20, int(inner_w / 9))
        lines = max(1, int(math.ceil(len(text) / float(cpl))))
        head = 30 if block.get("label") else 0
        return 32 + head + lines * 24
    if t == "cards":
        cols = max(1, int(block.get("columns", 2)))
        rows = _grid(len(block.get("items", [])), cols)
        return rows * CARD_H + max(0, rows - 1) * CARD_GUTTER
    if t == "metrics":
        items = block.get("items", [])
        cols = max(1, int(block.get("columns", min(len(items), 3) or 1)))
        rows = _grid(len(items), cols)
        return rows * MET_H + max(0, rows - 1) * CARD_GUTTER
    if t == "chips":
        rows = chip_rows(block.get("items", []), inner_w)
        return rows * CHIP_H + max(0, rows - 1) * CHIP_GAP
    if t == "chart":
        return CHART_PIE_H if block.get("chartType") == "pie" else CHART_LINE_H
    return MANUAL_H


# ---------------------------------------------------------------------------
# Block builders. Each lays widgets into `out` within the inner content region
# (ix, iy, iw, ih), parented to the section's area key. Backgrounds-first.
# ---------------------------------------------------------------------------
def build_banner(out, sid, block, ix, iy, iw, ih, pal, area_key):
    style = block.get("style", "dark")
    if style == "light":
        bg = pal.get("surface", DEFAULT_PALETTE["surface"])
    elif style == "accent":
        bg = resolve(block.get("color", "accent"), pal, "accent")
    else:  # dark
        bg = pal.get("ink", DEFAULT_PALETTE["ink"])
    out.add("create_shapes", {
        "shape_type": "rectangle", "x": ix, "y": iy, "width": iw, "height": BANNER_H,
        "background_color": bg, "stroke_color": bg, "stroke_size": 0,
        "text": block.get("text", ""), "font_size": 20, "bold": True,
        "font_color": contrast(bg), "text_align": "center",
    }, f"{sid}.banner", area_key)


def build_callout(out, sid, block, ix, iy, iw, ih, pal, area_key):
    color = resolve(block.get("color", "warning"), pal, "warning")
    bg = tint(color, 0.85)
    out.add("create_shapes", {
        "shape_type": "rounded_square", "x": ix, "y": iy, "width": iw, "height": ih,
        "background_color": bg, "stroke_color": color, "stroke_size": 2,
    }, f"{sid}.callout.bg", area_key)
    ty = iy + 16
    if block.get("label"):
        out.add("create_textboxes", {
            "x": ix + 18, "y": ty, "width": iw - 36, "text": block["label"].upper(),
            "font_size": 12, "font_color": color, "bold": True,
        }, f"{sid}.callout.label", area_key)
        ty += 28
    out.add("create_textboxes", {
        "x": ix + 18, "y": ty, "width": iw - 36, "text": block.get("text", ""),
        "font_size": 16, "font_color": pal.get("ink", DEFAULT_PALETTE["ink"]),
    }, f"{sid}.callout.text", area_key)


def _tile(out, sid, kind, idx, item, cx, cy, cw, ch, pal, area_key, icon_index,
          title_font):
    """Shared card/metric tile: bg fill + optional icon + title/desc/meta text."""
    color = resolve(item.get("color", "primary"), pal, "primary")
    bg = tint(color, 0.90)
    out.add("create_shapes", {
        "shape_type": "rounded_square", "x": round(cx, 1), "y": round(cy, 1),
        "width": round(cw, 1), "height": ch,
        "background_color": bg, "stroke_color": color, "stroke_size": 2,
    }, f"{sid}.{kind}{idx}.bg", area_key)

    tx = cx + 16
    if item.get("icon") is not None:
        nid, concept = resolve_icon(item["icon"], icon_index)
        if nid is not None:
            out.add("create_icons", {
                "noun_project_id": nid, "x": round(cx + 14, 1), "y": round(cy + 14, 1),
                "width": 30, "height": 30, "color": color,
                "tags": [str(concept)] if concept else [],
            }, f"{sid}.{kind}{idx}.icon", area_key)
            tx = cx + 54
        else:
            out.warn("section %s %s%d: icon %r unresolved (run search_icons)"
                     % (sid, kind, idx, concept))

    out.add("create_textboxes", {
        "x": round(tx, 1), "y": round(cy + 14, 1), "width": round(cx + cw - tx - 14, 1),
        "text": item.get("title", ""), "font_size": title_font, "bold": True,
        "font_color": color,
    }, f"{sid}.{kind}{idx}.title", area_key)
    if item.get("desc"):
        out.add("create_textboxes", {
            "x": round(cx + 16, 1), "y": round(cy + 52, 1), "width": round(cw - 32, 1),
            "text": item["desc"], "font_size": 13,
            "font_color": pal.get("ink", DEFAULT_PALETTE["ink"]),
        }, f"{sid}.{kind}{idx}.desc", area_key)
    if item.get("meta"):
        out.add("create_textboxes", {
            "x": round(cx + 16, 1), "y": round(cy + ch - 28, 1), "width": round(cw - 32, 1),
            "text": item["meta"], "font_size": 11, "italic": True, "font_color": MUTED,
        }, f"{sid}.{kind}{idx}.meta", area_key)


def build_cards(out, sid, block, ix, iy, iw, ih, pal, area_key, icon_index):
    items = block.get("items", [])
    cols = max(1, int(block.get("columns", 2)))
    cw = (iw - (cols - 1) * CARD_GUTTER) / float(cols)
    for idx, item in enumerate(items):
        r, c = idx // cols, idx % cols
        cx = ix + c * (cw + CARD_GUTTER)
        cy = iy + r * (CARD_H + CARD_GUTTER)
        _tile(out, sid, "card", idx, item, cx, cy, cw, CARD_H, pal, area_key,
              icon_index, title_font=16)


def build_metrics(out, sid, block, ix, iy, iw, ih, pal, area_key, icon_index):
    items = block.get("items", [])
    cols = max(1, int(block.get("columns", min(len(items), 3) or 1)))
    cw = (iw - (cols - 1) * CARD_GUTTER) / float(cols)
    for idx, item in enumerate(items):
        r, c = idx // cols, idx % cols
        cx = ix + c * (cw + CARD_GUTTER)
        cy = iy + r * (MET_H + CARD_GUTTER)
        _tile(out, sid, "metric", idx, item, cx, cy, cw, MET_H, pal, area_key,
              icon_index, title_font=22)


def build_chips(out, sid, block, ix, iy, iw, ih, pal, area_key):
    default_color = resolve(block.get("color", "primary"), pal, "primary")
    x, y = ix, iy
    for idx, it in enumerate(block.get("items", [])):
        if isinstance(it, dict):
            label = it.get("label", "")
            color = resolve(it.get("color", block.get("color", "primary")), pal, "primary")
        else:
            label, color = it, default_color
        w = chip_width(label, iw)
        if x > ix and x + w > ix + iw:  # wrap
            x = ix
            y += CHIP_H + CHIP_GAP
        out.add("create_shapes", {
            "shape_type": "rounded_square", "x": round(x, 1), "y": round(y, 1),
            "width": round(w, 1), "height": CHIP_H,
            "background_color": tint(color, 0.82), "stroke_color": color, "stroke_size": 1,
            "text": str(label), "font_size": 14, "text_align": "center",
            "font_color": DEFAULT_PALETTE["ink"],
        }, f"{sid}.chip{idx}", area_key)
        x += w + CHIP_GAP


def build_chart(out, sid, block, ix, iy, iw, ih, pal, area_key, box):
    """Wire line/pie charts through the reusable builders; bar -> manual_blocks."""
    ctype = block.get("chartType")
    geom_area = {"x": ix, "y": iy, "w": iw, "h": ih}

    if ctype == "line":
        colors = [resolve(s.get("color", CYCLE[i % len(CYCLE)]), pal)
                  for i, s in enumerate(block.get("series", []))]
        spec = {
            "area": geom_area,
            "x_labels": block.get("categories", []),
            "series": [{"name": s.get("name", ""), "color": colors[i],
                        "values": s["values"]}
                       for i, s in enumerate(block.get("series", []))],
        }
        res = line_chart.build(spec)
        # merge shapes backgrounds-first: gridlines under, series (segments->markers), legend.
        shapes = list(res.get("scaffold_shapes", []))
        for name in [s.get("name", "") for s in block.get("series", [])]:
            shapes += res["series"].get(name, [])
        shapes += res.get("legend_shapes", [])
        _merge_chart(out, sid, area_key, shapes, res.get("textboxes", []))
        return

    if ctype == "pie":
        spec = {
            "area": geom_area,
            "slices": [{"name": sl.get("label", ""), "value": sl["value"],
                        "color": resolve(sl.get("color", CYCLE[i % len(CYCLE)]), pal)}
                       for i, sl in enumerate(block.get("slices", []))],
        }
        res = pie_chart.build(spec)
        shapes = list(res.get("bar_shapes", [])) + list(res.get("legend_shapes", []))
        _merge_chart(out, sid, area_key, shapes, res.get("textboxes", []))
        return

    # bar (no reusable builder yet) and any other chartType -> model builds it.
    out.manual(sid, "chart", "chartType=%r has no reusable builder (line/pie only in "
               "Phase A); build from primitives" % ctype, box)


def _merge_chart(out, sid, area_key, shapes, textboxes):
    for i, w in enumerate(shapes):
        out.add("create_shapes", w, "%s.chart.s%d" % (sid, i), area_key)
    for i, w in enumerate(textboxes):
        out.add("create_textboxes", w, "%s.chart.t%d" % (sid, i), area_key)


# ---------------------------------------------------------------------------
# meta header
# ---------------------------------------------------------------------------
def build_meta(out, meta, pal, content_w):
    """Header identity: eyebrow -> title -> subtitle -> tag chips (top to bottom).
    Returns the y where sections should start."""
    x = CANVAS_X0
    y = CANVAS_Y0
    accent = pal.get("accent", DEFAULT_PALETTE["accent"])
    ink = pal.get("ink", DEFAULT_PALETTE["ink"])

    if meta.get("eyebrow"):
        out.add("create_textboxes", {
            "x": x, "y": y, "width": content_w, "text": meta["eyebrow"],
            "font_size": 14, "bold": True, "font_color": accent,
        }, "meta.eyebrow")
        y += 28
    if meta.get("title"):
        out.add("create_titles", {
            "x": x, "y": y, "width": content_w, "text": meta["title"],  # verbatim casing
            "font_size": 46, "bold": True, "font_color": ink,
        }, "meta.title")
        y += 66
    if meta.get("subtitle"):
        out.add("create_textboxes", {
            "x": x, "y": y, "width": content_w, "text": meta["subtitle"],
            "font_size": 20, "font_color": MUTED,
        }, "meta.subtitle")
        y += 42
    tags = meta.get("tags", [])
    if tags:
        cx = x
        chip_bg = tint(pal.get("primary", DEFAULT_PALETTE["primary"]), 0.85)
        for k, tag in enumerate(tags):
            w = chip_width(tag, content_w)
            out.add("create_shapes", {
                "shape_type": "rounded_square", "x": round(cx, 1), "y": y,
                "width": round(w, 1), "height": CHIP_H,
                "background_color": chip_bg,
                "stroke_color": pal.get("primary", DEFAULT_PALETTE["primary"]),
                "stroke_size": 1, "text": str(tag), "font_size": 14,
                "text_align": "center", "font_color": DEFAULT_PALETTE["ink"],
            }, "meta.tag%d" % k)
            cx += w + CHIP_GAP
        y += CHIP_H
    return y + ROW_GUTTER


# ---------------------------------------------------------------------------
# Section layout: assign each section a (row, col) -> absolute box, then build.
# ---------------------------------------------------------------------------
def layout_sections(sections, content_w):
    """Return list of (section, box) where box = (x, y, w, h). Deterministic grid flow."""
    # Pass 1: assign an effective row + col to every section.
    next_row = 1
    for sec in sections:
        g = sec.get("grid") or {}
        explicit = all(k in g for k in ("x", "y", "w", "h"))
        sec["_explicit"] = explicit
        if explicit:
            continue
        row = g.get("row")
        if row is None:
            row = next_row
        next_row = max(next_row, int(row)) + 1
        sec["_row"] = int(row)
        sec["_col"] = g.get("col", "full")

    # Pass 2: for each row, resolve columns to x/width.
    half = (content_w - COL_GUTTER) / 2.0
    rows = {}
    for sec in sections:
        if sec.get("_explicit"):
            continue
        rows.setdefault(sec["_row"], []).append(sec)

    for row_secs in rows.values():
        # Determine column count for this row.
        cols_vals = [s["_col"] for s in row_secs]
        numeric = [int(c) for c in cols_vals if isinstance(c, int)
                   or (isinstance(c, str) and c.isdigit())]
        for s in row_secs:
            col = s["_col"]
            if col == "full":
                s["_x"], s["_w"] = CANVAS_X0, content_w
            elif col == "left":
                s["_x"], s["_w"] = CANVAS_X0, half
            elif col == "right":
                s["_x"], s["_w"] = CANVAS_X0 + half + COL_GUTTER, half
            elif numeric:
                ncols = max(numeric)
                cw = (content_w - (ncols - 1) * COL_GUTTER) / float(ncols)
                k = int(col) - 1
                s["_x"] = CANVAS_X0 + k * (cw + COL_GUTTER)
                s["_w"] = cw
            else:
                s["_x"], s["_w"] = CANVAS_X0, content_w

    # Pass 3: compute each section height, then stack rows top-down.
    for sec in sections:
        if sec.get("_explicit"):
            continue
        iw = sec["_w"] - 2 * SECTION_PAD
        sec["_h"] = HEAD_BAND + content_height(sec.get("block"), iw) + PAD_BOTTOM

    return rows


def compile_board(spec, palette_arg, icons_json):
    out = Out()
    meta = spec.get("meta", {})

    # Palette: default floor < spec meta.palette < external --palette.
    pal = dict(DEFAULT_PALETTE)
    pal.update(meta.get("palette", {}))
    pal.update(palette_arg or {})

    icon_index = build_icon_index(icons_json)
    content_w = (CONTENT_W_PORTRAIT if meta.get("orientation") == "portrait"
                 else CONTENT_W_LANDSCAPE)

    sections_start_y = build_meta(out, meta, pal, content_w)

    sections = spec.get("sections", [])
    rows = layout_sections(sections, content_w)

    # Assign absolute y per row (grid-flow sections), stacking in row order.
    y = sections_start_y
    for row_no in sorted(rows.keys()):
        row_secs = rows[row_no]
        row_h = max(s["_h"] for s in row_secs)
        for s in row_secs:
            s["_y"] = y
            s["_h"] = row_h  # equalize heights across the row
        y += row_h + ROW_GUTTER

    # Build every section (explicit-coord sections use their own box).
    for i, sec in enumerate(sections):
        sid = "sec%d" % i
        if sec.get("_explicit"):
            g = sec["grid"]
            sx, sy, sw, sh = g["x"], g["y"], g["w"], g["h"]
        else:
            sx, sy, sw, sh = sec["_x"], sec["_y"], sec["_w"], sec["_h"]
        box = {"x": round(sx, 1), "y": round(sy, 1),
               "width": round(sw, 1), "height": round(sh, 1)}

        # Section frame (area) + heading title in the reserved top band.
        area_key = "%s.area" % sid
        out.add("create_areas", {
            "x": box["x"], "y": box["y"], "width": box["width"], "height": box["height"],
            "title": sec.get("title", ""), "showTitle": False,
        }, area_key)
        block = sec.get("block") or {}
        # Heading text: section title, else the chart block's own title.
        heading = sec.get("title") or (block.get("title") if block.get("type") == "chart" else None)
        if heading:
            out.add("create_titles", {
                "x": round(sx + SECTION_PAD, 1), "y": round(sy + 16, 1),
                "width": round(sw - 2 * SECTION_PAD, 1), "text": heading,
                "font_size": 22, "bold": True, "font_color": pal.get("ink", DEFAULT_PALETTE["ink"]),
            }, "%s.head" % sid, area_key)

        # Inner content region below the heading band.
        ix = sx + SECTION_PAD
        iy = sy + HEAD_BAND
        iw = sw - 2 * SECTION_PAD
        ih = sh - HEAD_BAND - PAD_BOTTOM

        t = block.get("type")
        if t == "banner":
            build_banner(out, sid, block, ix, iy, iw, ih, pal, area_key)
        elif t == "callout":
            build_callout(out, sid, block, ix, iy, iw, ih, pal, area_key)
        elif t == "cards":
            build_cards(out, sid, block, ix, iy, iw, ih, pal, area_key, icon_index)
        elif t == "metrics":
            build_metrics(out, sid, block, ix, iy, iw, ih, pal, area_key, icon_index)
        elif t == "chips":
            build_chips(out, sid, block, ix, iy, iw, ih, pal, area_key)
        elif t == "chart":
            build_chart(out, sid, block, ix, iy, iw, ih, pal, area_key, box)
        elif t is None:
            pass  # section frame with no block (rare) — just the area + heading.
        else:
            out.manual(sid, t, "block type %r not in Phase A; build from primitives "
                       "(see block-catalog.md)" % t, box)

    return out.d


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv):
    spec_path = None
    palette_path = None
    icons_path = None
    it = iter(argv)
    for a in it:
        if a == "--palette":
            palette_path = next(it)
        elif a == "--icons":
            icons_path = next(it)
        elif a in ("-h", "--help"):
            print(__doc__)
            return 0
        else:
            spec_path = a

    raw = open(spec_path).read() if spec_path else sys.stdin.read()
    spec = json.loads(raw)
    palette_arg = json.loads(open(palette_path).read()) if palette_path else None
    icons_json = json.loads(open(icons_path).read()) if icons_path else None

    result = compile_board(spec, palette_arg, icons_json)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
