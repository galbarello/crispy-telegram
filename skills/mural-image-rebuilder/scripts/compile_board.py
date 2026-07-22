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

COVERAGE (this file)
    Phase A: meta header (eyebrow, title, subtitle, tag chips), section (area + heading), banner,
    callout, cards, metrics, chips, and chart line/pie (via line_chart/pie_chart .build()).
    Phase B: table (area-nested grid of colored header cells + tinted column bodies + routed
    cells: text/bullets/chips/coloredText + badge/icon leading column), flow (step nodes L->R
    with REAL connectors between consecutive nodes, closing the loop when loop:true), comparison
    (N stacked-box columns with intra-column connectors per the block's `connector`), and chart
    chartType:"bar" (real bars from a baseline via bar_chart.build()). Every other block type
    passes through to `manual_blocks` for the model to build (see block-catalog.md / Phase C).

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
import bar_chart    # noqa: E402


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

# --- Phase B geometry (table / flow / comparison) ---
CELL_PAD = 10            # inner padding inside a table body cell
TABLE_HEADER_H = 46      # height of the colored per-column header cells
TABLE_ROW_MIN = 56       # minimum body-row height (tallest cell sets the actual pitch)
BADGE_SIZE = 28          # diameter of a leading-column number badge
ICON_SLOT = 30           # leading-column / node icon box
LINE_H = 20              # ~1 text line for cell-height estimation
BULLET_H = 22            # ~1 bullet line

FLOW_NODE_H = 138        # step-node height (icon + label + desc)
FLOW_GAP = 40            # gap between step nodes

COMP_HEAD_H = 44         # comparison column header height
COMP_BOX_H = 72          # comparison stacked-box height
COMP_BOX_GAP = 40        # vertical gap between stacked boxes (room for the connector)

# spec `shape` -> Mural shape_type for flow nodes (default rounded_square).
FLOW_SHAPE = {"step": "rounded_square", "process": "rectangle",
              "circle": "circle", "rounded_square": "rounded_square"}
# comparison `connector` -> connector arrow_type hint for the emitted connector records.
COMP_ARROW = {"arrow-down": "straight", "arrow": "straight"}

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

    def connect(self, from_key, to_key, **extra):
        """Emit a REAL connector referencing two widget _keys (resolved to ids by the wrapper)."""
        rec = {"from": from_key, "to": to_key}
        rec.update(extra)
        self.d["connectors"].append(rec)
        return rec

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


def _cell_height(cell, col_w):
    """Estimated height of one table cell at column width col_w (drives the row pitch)."""
    if not isinstance(cell, dict):
        cell = {"text": str(cell)}
    inner_w = max(20.0, col_w - 2 * CELL_PAD)
    if cell.get("chips"):
        rows = chip_rows(cell["chips"], inner_w)
        return 2 * CELL_PAD + rows * CHIP_H + max(0, rows - 1) * CHIP_GAP
    if cell.get("bullets"):
        return 2 * CELL_PAD + len(cell["bullets"]) * BULLET_H
    text = cell.get("text") or cell.get("coloredText") or ""
    # Leading-column row label: badge -> icon -> name laid out in a ROW, so name width shrinks.
    if cell.get("badge") or cell.get("icon"):
        used = (BADGE_SIZE + 8 if cell.get("badge") else 0) + (ICON_SLOT + 8 if cell.get("icon") else 0)
        name_w = max(20.0, inner_w - used)
        cpl = max(6, int(name_w / 8.0))
        lines = max(1, int(math.ceil(len(str(text)) / float(cpl)))) if text else 1
        return 2 * CELL_PAD + max(BADGE_SIZE, lines * LINE_H)
    cpl = max(8, int(inner_w / 8.0))
    lines = max(1, int(math.ceil(len(str(text)) / float(cpl)))) if text else 1
    return 2 * CELL_PAD + lines * LINE_H


def _table_layout(block, inner_w):
    """Return (col_w, header_h, row_heights[], total_height) for a table block at inner_w."""
    cols = block.get("columns", []) or []
    ncols = max(1, len(cols))
    col_w = inner_w / float(ncols)
    rows = block.get("rows", []) or []
    row_hs = []
    for row in rows:
        cells = row.get("cells", []) if isinstance(row, dict) else []
        h = TABLE_ROW_MIN
        for ci in range(len(cols)):
            cell = cells[ci] if ci < len(cells) else {}
            h = max(h, _cell_height(cell, col_w))
        row_hs.append(h)
    total = TABLE_HEADER_H + sum(row_hs)
    return col_w, TABLE_HEADER_H, row_hs, total


def content_height(block, inner_w):
    """Estimated content height (below the heading band) for a block at width inner_w."""
    if block is None:
        return MANUAL_H
    # Sizing runs in layout_sections BEFORE the builders dispatch, so any exception here
    # (a malformed block that never reaches its guarded builder) must not crash the board —
    # fall back to a manual-placeholder height; the builder will degrade to manual too.
    try:
        t = block.get("type")
        if t == "banner":
            return BANNER_H
        if t == "table":
            return _table_layout(block, inner_w)[3]
        if t == "flow":
            return FLOW_NODE_H
        if t == "comparison":
            cols = block.get("columns", []) or []
            maxitems = max((len(c.get("items", []) or []) for c in cols if isinstance(c, dict)),
                           default=0)
            return COMP_HEAD_H + maxitems * COMP_BOX_H + max(0, maxitems - 1) * COMP_BOX_GAP
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
    except Exception:
        return MANUAL_H
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


# ---------------------------------------------------------------------------
# Phase B: table — area-nested grid of colored header cells + tinted column
# bodies + type-routed cells (text / bullets / chips / coloredText) with a
# badge/icon leading column. NEVER create_table. See table-fidelity.md.
# ---------------------------------------------------------------------------
def _table_cell(out, sid, ri, ci, cell, cx, ry, col_w, rh, pal, col_hex, area_key,
                icon_index, leading):
    """Route one cell to the right widget(s): chips / bullets / badge+icon / coloredText / text."""
    if not isinstance(cell, dict):
        cell = {"text": str(cell)} if cell not in (None, "") else {}
    kbase = "%s.table.r%dc%d" % (sid, ri, ci)
    inner_x = cx + CELL_PAD
    inner_w = max(20.0, col_w - 2 * CELL_PAD)
    ty = ry + CELL_PAD
    ink = pal.get("ink", DEFAULT_PALETTE["ink"])

    # chips -> one small pill per item, in a wrapping row (never a joined string)
    if cell.get("chips"):
        base_color = resolve(cell.get("color"), pal, "primary") if cell.get("color") else \
            (col_hex or pal.get("primary", DEFAULT_PALETTE["primary"]))
        x, y = inner_x, ty
        for k, ch in enumerate(cell["chips"]):
            if isinstance(ch, dict):
                label = ch.get("label", "")
                color = resolve(ch.get("color"), pal, "primary") if ch.get("color") else base_color
            else:
                label, color = ch, base_color
            w = chip_width(label, inner_w)
            if x > inner_x and x + w > inner_x + inner_w:  # wrap inside the cell
                x = inner_x
                y += CHIP_H + CHIP_GAP
            out.add("create_shapes", {
                "shape_type": "rounded_square", "x": round(x, 1), "y": round(y, 1),
                "width": round(w, 1), "height": CHIP_H,
                "background_color": tint(color, 0.82), "stroke_color": color, "stroke_size": 1,
                "text": str(label), "font_size": 13, "text_align": "center", "font_color": ink,
            }, "%s.chip%d" % (kbase, k), area_key)
            x += w + CHIP_GAP
        return

    # bulleted list -> ONE textbox with "\n• " lines
    if cell.get("bullets"):
        text = "\n".join("• %s" % b for b in cell["bullets"])
        out.add("create_textboxes", {
            "x": round(inner_x, 1), "y": round(ty, 1), "width": round(inner_w, 1),
            "text": text, "font_size": 13, "font_color": ink,
        }, "%s.bullets" % kbase, area_key)
        return

    # leading-column row label -> badge -> icon -> name, laid out in a row
    if leading and (cell.get("badge") or cell.get("icon")):
        label_color = col_hex or pal.get("primary", DEFAULT_PALETTE["primary"])
        x = inner_x
        cy_mid = ry + rh / 2.0
        if cell.get("badge"):
            out.add("create_shapes", {
                "shape_type": "ellipse", "x": round(x, 1), "y": round(cy_mid - BADGE_SIZE / 2.0, 1),
                "width": BADGE_SIZE, "height": BADGE_SIZE,
                "background_color": label_color, "stroke_color": label_color, "stroke_size": 0,
                "text": str(cell["badge"]), "font_size": 13, "bold": True,
                "text_align": "center", "font_color": contrast(label_color),
            }, "%s.badge" % kbase, area_key)
            x += BADGE_SIZE + 8
        if cell.get("icon") is not None:
            nid, concept = resolve_icon(cell["icon"], icon_index)
            if nid is not None:
                out.add("create_icons", {
                    "noun_project_id": nid, "x": round(x, 1),
                    "y": round(cy_mid - ICON_SLOT / 2.0, 1),
                    "width": ICON_SLOT, "height": ICON_SLOT, "color": label_color,
                    "tags": [str(concept)] if concept else [],
                }, "%s.icon" % kbase, area_key)
                x += ICON_SLOT + 8
            else:
                out.warn("section %s table r%dc%d: icon %r unresolved (run search_icons)"
                         % (sid, ri, ci, concept))
        out.add("create_textboxes", {
            "x": round(x, 1), "y": round(cy_mid - LINE_H / 2.0, 1),
            "width": round(cx + col_w - CELL_PAD - x, 1), "text": cell.get("text", ""),
            "font_size": 14, "bold": True, "font_color": label_color,
        }, "%s.name" % kbase, area_key)
        return

    # colored / emphasis text
    if cell.get("coloredText") is not None:
        color = resolve(cell.get("color"), pal, "primary") if cell.get("color") else \
            (col_hex or pal.get("primary", DEFAULT_PALETTE["primary"]))
        out.add("create_textboxes", {
            "x": round(inner_x, 1), "y": round(ty, 1), "width": round(inner_w, 1),
            "text": str(cell["coloredText"]), "font_size": 14, "bold": True, "font_color": color,
        }, "%s.text" % kbase, area_key)
        return

    # plain paragraph text (also the leading-column fallback when there's no badge/icon)
    text = cell.get("text")
    if text:
        out.add("create_textboxes", {
            "x": round(inner_x, 1), "y": round(ty, 1), "width": round(inner_w, 1),
            "text": str(text), "font_size": 14 if leading else 13,
            "bold": bool(leading), "font_color": ink,
        }, "%s.text" % kbase, area_key)


def build_table(out, sid, block, ix, iy, iw, ih, pal, area_key, icon_index):
    cols = block.get("columns", []) or []
    rows = block.get("rows", []) or []
    if not cols:
        out.warn("section %s: table has no `columns` — nothing built" % sid)
        return
    ncols = len(cols)
    col_w, header_h, row_hs, _ = _table_layout(block, iw)

    # Resolve each column's hue: object columns carry a role; bare strings are neutral.
    col_hex = []
    for c in cols:
        if isinstance(c, dict) and c.get("color"):
            col_hex.append(resolve(c["color"], pal, "primary"))
        else:
            col_hex.append(None)

    body_y = iy + header_h
    body_h = sum(row_hs)

    # 1) column tint backgrounds (span all body rows) — backgrounds first, render underneath.
    for ci in range(ncols):
        cx = ix + ci * col_w
        hue = col_hex[ci]
        # `tint` role override on the column object wins over the derived light body fill.
        col = cols[ci]
        if isinstance(col, dict) and col.get("tint"):
            body_bg = resolve(col["tint"], pal, "surface")
        elif hue:
            body_bg = tint(hue, 0.90)
        else:
            body_bg = pal.get("surface", DEFAULT_PALETTE["surface"])
        out.add("create_shapes", {
            "shape_type": "rectangle", "x": round(cx, 1), "y": round(body_y, 1),
            "width": round(col_w, 1), "height": round(body_h, 1),
            "background_color": body_bg, "stroke_color": "#DADCE0", "stroke_size": 1,
        }, "%s.table.coltint%d" % (sid, ci), area_key)

    # 2) header cells — ONE colored cell per column (never a single banner).
    for ci in range(ncols):
        cx = ix + ci * col_w
        col = cols[ci]
        label = col.get("label", "") if isinstance(col, dict) else str(col)
        hdr = col_hex[ci] or MUTED  # neutral columns fall back to a muted header band
        out.add("create_shapes", {
            "shape_type": "rectangle", "x": round(cx, 1), "y": round(iy, 1),
            "width": round(col_w, 1), "height": header_h,
            "background_color": hdr, "stroke_color": hdr, "stroke_size": 0,
            "text": str(label), "font_size": 13, "bold": True,
            "text_align": "center", "font_color": contrast(hdr),
        }, "%s.table.colhead%d" % (sid, ci), area_key)

    # 3) row content — one row baseline per row, cells routed by type.
    ry = body_y
    for ri, row in enumerate(rows):
        cells = row.get("cells", []) if isinstance(row, dict) else []
        rh = row_hs[ri]
        for ci in range(ncols):
            cell = cells[ci] if ci < len(cells) else {}
            cx = ix + ci * col_w
            _table_cell(out, sid, ri, ci, cell, cx, ry, col_w, rh, pal, col_hex[ci],
                        area_key, icon_index, leading=(ci == 0))
        ry += rh


# ---------------------------------------------------------------------------
# Phase B: flow — step nodes left-to-right + REAL connectors between consecutive
# nodes (loop:true closes the cycle). First real exercise of the connector
# handshake: node _keys must be stable and referenced exactly in connectors[].
# ---------------------------------------------------------------------------
def build_flow(out, sid, block, ix, iy, iw, ih, pal, area_key, icon_index):
    steps = block.get("steps", []) or []
    n = len(steps)
    if n == 0:
        out.warn("section %s: flow has no `steps` — nothing built" % sid)
        return
    shape_type = FLOW_SHAPE.get(block.get("shape", "rounded_square"),
                                block.get("shape", "rounded_square"))
    node_w = (iw - (n - 1) * FLOW_GAP) / float(n)
    node_h = min(FLOW_NODE_H, ih)
    ny = iy
    node_keys = []
    for i, step in enumerate(steps):
        nx = ix + i * (node_w + FLOW_GAP)
        color = resolve(step.get("color", CYCLE[i % len(CYCLE)]), pal, "primary")
        nkey = "%s.flow.node%d" % (sid, i)
        # node background (fill first so icon + text land on top)
        out.add("create_shapes", {
            "shape_type": shape_type, "x": round(nx, 1), "y": round(ny, 1),
            "width": round(node_w, 1), "height": round(node_h, 1),
            "background_color": tint(color, 0.88), "stroke_color": color, "stroke_size": 2,
        }, nkey, area_key)
        node_keys.append(nkey)

        tx = nx + 14
        top = ny + 14
        if step.get("icon") is not None:
            nid, concept = resolve_icon(step["icon"], icon_index)
            if nid is not None:
                out.add("create_icons", {
                    "noun_project_id": nid, "x": round(nx + node_w / 2.0 - ICON_SLOT / 2.0, 1),
                    "y": round(top, 1), "width": ICON_SLOT, "height": ICON_SLOT, "color": color,
                    "tags": [str(concept)] if concept else [],
                }, "%s.icon" % nkey, area_key)
                top += ICON_SLOT + 6
            else:
                out.warn("section %s flow node%d: icon %r unresolved (run search_icons)"
                         % (sid, i, concept))
        # label (with optional step number prefix) + optional description
        num = step.get("n")
        label = step.get("label", "")
        if num is not None:
            label = "%s. %s" % (num, label)
        out.add("create_textboxes", {
            "x": round(tx, 1), "y": round(top, 1), "width": round(node_w - 28, 1),
            "text": label, "font_size": 15, "bold": True, "font_color": color,
            "text_align": "center",
        }, "%s.label" % nkey, area_key)
        if step.get("desc"):
            out.add("create_textboxes", {
                "x": round(tx, 1), "y": round(top + 26, 1), "width": round(node_w - 28, 1),
                "text": step["desc"], "font_size": 12,
                "font_color": pal.get("ink", DEFAULT_PALETTE["ink"]), "text_align": "center",
            }, "%s.desc" % nkey, area_key)

    # REAL connectors between consecutive nodes; loop:true adds the closing edge last->first.
    for i in range(n - 1):
        out.connect(node_keys[i], node_keys[i + 1])
    if block.get("loop") and n > 1:
        out.connect(node_keys[-1], node_keys[0], loop=True)


# ---------------------------------------------------------------------------
# Phase B: comparison — N side-by-side columns of stacked boxes with REAL
# connectors between the stacked items (per the block's `connector` field).
# ---------------------------------------------------------------------------
def build_comparison(out, sid, block, ix, iy, iw, ih, pal, area_key):
    cols = block.get("columns", []) or []
    ncols = len(cols)
    if ncols == 0:
        out.warn("section %s: comparison has no `columns` — nothing built" % sid)
        return
    connector = block.get("connector")
    arrow_type = COMP_ARROW.get(connector) if connector else None
    col_w = (iw - (ncols - 1) * COL_GUTTER) / float(ncols)
    for ci, col in enumerate(cols):
        cx = ix + ci * (col_w + COL_GUTTER)
        color = resolve(col.get("color", CYCLE[ci % len(CYCLE)]), pal, "primary")
        # column header title (in the column color)
        out.add("create_titles", {
            "x": round(cx, 1), "y": round(iy, 1), "width": round(col_w, 1),
            "text": col.get("label", ""), "font_size": 18, "bold": True,
            "font_color": color, "text_align": "center",
        }, "%s.comp.c%d.head" % (sid, ci), area_key)

        items = col.get("items", []) or []
        item_keys = []
        by = iy + COMP_HEAD_H
        for k, item in enumerate(items):
            label = item if not isinstance(item, dict) else item.get("label", "")
            bkey = "%s.comp.c%d.box%d" % (sid, ci, k)
            out.add("create_shapes", {
                "shape_type": "rounded_square", "x": round(cx, 1), "y": round(by, 1),
                "width": round(col_w, 1), "height": COMP_BOX_H,
                "background_color": tint(color, 0.85), "stroke_color": color, "stroke_size": 2,
                "text": str(label), "font_size": 14, "text_align": "center",
                "font_color": DEFAULT_PALETTE["ink"],
            }, bkey, area_key)
            item_keys.append(bkey)
            by += COMP_BOX_H + COMP_BOX_GAP

        # REAL connectors joining the stacked items top->bottom (only when requested).
        if connector and len(item_keys) > 1:
            for a in range(len(item_keys) - 1):
                if arrow_type:
                    out.connect(item_keys[a], item_keys[a + 1], arrow_type=arrow_type)
                else:
                    out.connect(item_keys[a], item_keys[a + 1])


def build_chart(out, sid, block, ix, iy, iw, ih, pal, area_key, box):
    """Wire line/pie/bar charts through the reusable builders; unknown types -> manual_blocks."""
    ctype = block.get("chartType")
    geom_area = {"x": ix, "y": iy, "w": iw, "h": ih}

    if ctype == "line":
        try:
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
        except Exception as e:  # never abort the whole board — degrade this block
            out.manual(sid, "chart", "line chart build failed (%s); build from "
                       "primitives" % e, box)
            out.warn("section %s: line chart -> manual_blocks (%s)" % (sid, e))
            return
        # merge shapes backgrounds-first: gridlines under, series (segments->markers), legend.
        # Iterate the returned series dict directly — indexing back by name collapses/duplicates
        # series that share a name (and would emit duplicate _keys).
        shapes = list(res.get("scaffold_shapes", []))
        for _name, arr in res.get("series", {}).items():
            shapes += arr
        shapes += res.get("legend_shapes", [])
        _merge_chart(out, sid, area_key, shapes, res.get("textboxes", []))
        return

    if ctype == "pie":
        try:
            spec = {
                "area": geom_area,
                "slices": [{"name": sl.get("label", ""), "value": sl["value"],
                            "color": resolve(sl.get("color", CYCLE[i % len(CYCLE)]), pal)}
                           for i, sl in enumerate(block.get("slices", []))],
            }
            res = pie_chart.build(spec)
        except Exception as e:  # never abort the whole board — degrade this block
            out.manual(sid, "chart", "pie chart build failed (%s); build from "
                       "primitives" % e, box)
            out.warn("section %s: pie chart -> manual_blocks (%s)" % (sid, e))
            return
        shapes = list(res.get("bar_shapes", [])) + list(res.get("legend_shapes", []))
        _merge_chart(out, sid, area_key, shapes, res.get("textboxes", []))
        return

    if ctype == "bar":
        try:
            colors = [resolve(s.get("color", CYCLE[i % len(CYCLE)]), pal)
                      for i, s in enumerate(block.get("series", []))]
            spec = {
                "area": geom_area,
                "x_labels": block.get("categories", []),
                "y_unit": block.get("yUnit", ""),
                "series": [{"name": s.get("name", ""), "color": colors[i],
                            "values": s["values"]}
                           for i, s in enumerate(block.get("series", []))],
            }
            res = bar_chart.build(spec)
        except Exception as e:  # never abort the whole board — degrade this block
            out.manual(sid, "chart", "bar chart build failed (%s); build from "
                       "primitives" % e, box)
            out.warn("section %s: bar chart -> manual_blocks (%s)" % (sid, e))
            return
        # merge shapes backgrounds-first: gridlines under, bars, then legend swatches.
        shapes = list(res.get("scaffold_shapes", []))
        shapes += res.get("bar_shapes", [])
        shapes += res.get("legend_shapes", [])
        _merge_chart(out, sid, area_key, shapes, res.get("textboxes", []))
        return

    # any other chartType (none left in Phase B) -> model builds it.
    out.manual(sid, "chart", "chartType=%r has no reusable builder (line/pie/bar covered); "
               "build from primitives" % ctype, box)


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
        if t in ("banner", "callout", "cards", "metrics", "chips",
                 "table", "flow", "comparison", "chart"):
            # Every builder degrades to manual_blocks + a warning on any failure — a malformed
            # block must never crash the whole board (build_chart also guards internally).
            try:
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
                elif t == "table":
                    build_table(out, sid, block, ix, iy, iw, ih, pal, area_key, icon_index)
                elif t == "flow":
                    build_flow(out, sid, block, ix, iy, iw, ih, pal, area_key, icon_index)
                elif t == "comparison":
                    build_comparison(out, sid, block, ix, iy, iw, ih, pal, area_key)
                elif t == "chart":
                    build_chart(out, sid, block, ix, iy, iw, ih, pal, area_key, box)
            except Exception as e:
                out.manual(sid, t, "%s build failed (%s); build from primitives" % (t, e), box)
                out.warn("section %s: %s -> manual_blocks (%s)" % (sid, t, e))
        elif t is None:
            # A section frame with no block is usually intentional (area + heading only).
            # But if content was supplied under the wrong key, warn instead of dropping it silently.
            if "blocks" in sec:
                out.warn("section %s: found a `blocks` list, but the schema uses a SINGULAR "
                         "`block` per section — nothing built; fix the spec" % sid)
            elif sec.get("block"):  # a block object is present but has no/unknown `type`
                out.warn("section %s: `block` has no recognized `type` — nothing built" % sid)
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

    def _load(path, what):
        try:
            raw = open(path).read() if path else sys.stdin.read()
            return json.loads(raw)
        except (OSError, ValueError) as e:  # missing file or malformed JSON
            print("compile_board: could not read %s (%s)" % (what, e), file=sys.stderr)
            raise SystemExit(1)

    spec = _load(spec_path, "board-spec" if spec_path else "board-spec (stdin)")
    palette_arg = _load(palette_path, "--palette") if palette_path else None
    icons_json = _load(icons_path, "--icons") if icons_path else None

    result = compile_board(spec, palette_arg, icons_json)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
