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
    chartType:"bar" (real bars from a baseline via bar_chart.build()).
    Phase C-1: the STATIC/deterministic metaphor blocks (shape + text only, NO connectors) —
    gauge (linear-meter tile per item: track + value fill in the active `zones` color + `value``unit`),
    pyramid (stacked centered bands, width graded by `direction`), funnel (stacked bands narrowing by
    `value`/order), quadrant (2x2 tinted cells + crosshair + axis pole labels + positioned item dots),
    pillars (capstone bar over N flex columns), spectrum (gradient-approx bar + pole labels + markers),
    rings (nested concentric ellipses, largest-first), and venn (2-3 overlapping semi-transparent
    ellipses). Each validates its spec and degrades to `manual_blocks` + a warning on malformation.
    Phase C-2: the CONNECTOR/GRAPH-heavy metaphor blocks, each emitting REAL connectors
    (Out.connect referencing node _keys, never glyph arrows) —
    cycle (nodes on a ring / 2x2 + loop-closing connectors last->first; flywheel -> curved),
    hub (center node + ringed satellites + center->satellite connectors),
    timeline (horizontal axis + milestone dots + labels alternating above/below; axis carries the
    sequence, no connectors), swimlane (lanes x cols grid: tinted lane bands + col headers + item
    cells; no connectors), gantt (task rows x time columns: phase bands, duration bars + percent
    fills, milestone diamonds, a today line, dependency-arrow connectors), tree (root + recursively
    placed children with parent->child connectors, leaf-count layout, depth-capped), mindmap
    (central root + branches balanced left/right + children fanned beyond, curved branch-colored
    connectors), and decision (top-to-bottom flowchart: terminator/decision/process nodes layered
    by longest-path rank + labeled directed-edge connectors with midpoint labels).
    Phase D: nest — a recursively-nested container layout (a box inside a box …) for
    containment/wrapping diagrams (e.g. HOC layering) the flat `cards` block can't express. Each
    `box` node renders as an `area` frame (showTitle:false) holding a header (bold label in the
    node color + optional muted `meta`) + `desc` + its children laid out inside with padding
    (layout:"column" stacked / layout:"row" side-by-side, equal widths), so children visibly nest
    inside their parent frame; a `callout` node renders as a filled tinted `rounded_square` (a
    leaf). Heights are measured BOTTOM-UP by a shared recursive `_nest_measure` used by BOTH
    `content_height` and the builder, so every parent frame fits its children exactly. Recursion is
    depth-capped (NEST_MAX_DEPTH); no connectors. Every widget carries `_key`/`_parent` (children
    parent to their enclosing box's area). Malformed input (missing `node`, a node without `label`,
    a non-dict node) RAISES so the block degrades to manual_blocks + a warning with clean rollback.

    FULL COVERAGE: every board-spec block type now compiles to widgets. `manual_blocks` should
    only ever hold a genuinely-unknown `type` or a block degraded by a malformed spec (each such
    degrade also emits a warning and rolls back cleanly, leaving just the section area + heading).

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

# --- Phase C-1 geometry (STATIC/deterministic metaphor blocks) ---
# gauge: one meter tile per item, laid out in `columns` like metrics.
GAUGE_H = 156           # tile height
GAUGE_TRACK_H = 24      # linear-meter track/value bar height
GAUGE_GUTTER = 24       # gap between gauge tiles

# pyramid / funnel: stacked centered bands whose width encodes scope/value.
PYR_BAND_H = 62
PYR_GAP = 8
PYR_MIN_FRAC = 0.34     # apex band width as a fraction of the base band
FUN_BAND_H = 58
FUN_GAP = 6
FUN_MIN_FRAC = 0.30     # narrowest stage width fraction (no-values fallback)

# quadrant: a 2x2 tinted plot with axis pole labels + positioned dots.
QUAD_PLOT_H = 460       # plot square-ish height
QUAD_XLABEL_H = 40      # bottom band for x-axis pole labels
QUAD_YLABEL_W = 96      # left gutter for y-axis pole labels
QUAD_DOT = 16           # positioned item dot diameter
# cell tints for [bottom-left, bottom-right, top-left, top-right] (quadrantLabels order).
QUAD_CELL_ROLES = ["warning", "primary", "danger", "success"]

# pillars: a capstone bar over N flex columns.
PILLAR_CAP_H = 56
PILLAR_GAP = 20
PILLAR_H = 210          # column height below the capstone
PILLAR_COL_GUTTER = 24

# spectrum: a horizontal gradient-approximation bar with pole labels + markers.
SPECTRUM_H = 150
SPECTRUM_BAR_H = 28
SPECTRUM_SEG = 12       # number of adjacent color segments approximating the gradient
SPECTRUM_DOT = 18

# rings: nested concentric ellipses.
RINGS_MAX_D = 460

# venn: 2-3 overlapping semi-transparent ellipses.
VENN_MAX_D = 300
VENN_ALPHA = "2E"       # 8-digit hex alpha (~18%) appended to a #RRGGBB fill — verified to
                        # render (block-catalog.md venn recipe); pairwise/triple overlaps stack
                        # darker so the intersection reads.
VENN_H = 420

# --- Phase C-2 geometry (CONNECTOR / GRAPH-heavy metaphor blocks) ---
# Each of these emits REAL connectors (Out.connect) referencing node _keys — never glyph
# arrows. Node shapes carry the _key a connector points at, so every endpoint always resolves.
# cycle: nodes around a ring (or a 2x2 for exactly 4) + connectors closing the loop last->first.
CYCLE_H = 480
CYCLE_NODE_W = 190
CYCLE_NODE_H = 96

# hub: a center node + N satellites ringed around it + a center->satellite connector each.
HUB_H = 480
HUB_CENTER_W = 200
HUB_CENTER_H = 110
HUB_SAT_W = 150
HUB_SAT_H = 76

# timeline: a horizontal axis rectangle + milestone dots + labels alternating above/below.
# The axis carries the sequence, so no connectors are emitted (block-catalog.md).
TIMELINE_H = 320
TIMELINE_AXIS_H = 6
TIMELINE_DOT = 22

# swimlane: a header row of `cols` + one tinted lane band per lane + item cells (no connectors).
SWIM_HEADER_H = 44
SWIM_LANE_H = 108
SWIM_LANE_GAP = 12
SWIM_LABEL_W = 150      # left gutter for lane labels
SWIM_ITEM_H = 64
SWIM_CELL_PAD = 10

# gantt: task rows x time columns, duration bars, milestone diamonds, a today line, dep arrows.
GANTT_AXIS_H = 40       # top band for the timeUnits axis labels
GANTT_ROW_H = 48        # per-task row pitch
GANTT_LABEL_W = 180     # left gutter for task labels
GANTT_BAR_H = 26        # duration bar height (centered in the row band)
GANTT_MS = 26           # milestone diamond size
GANTT_TODAY_W = 6       # today-line thickness (both bg + stroke set so it reads, not a hairline)

# tree: root + recursively placed children with parent->child connectors.
TREE_NODE_W = 168
TREE_NODE_H = 62
TREE_LEVEL_PITCH = 132  # gap between depths (vertical for "down", horizontal for "right")
TREE_ROW_PITCH = 92     # per-leaf spacing on the cross axis
TREE_MAX_DEPTH = 4      # depth cap for legibility (deeper children are ignored)

# mindmap: central node + branches balanced left/right + children fanned beyond each branch.
MIND_H = 520
MIND_ROOT_W = 210
MIND_ROOT_H = 96
MIND_BRANCH_W = 168
MIND_BRANCH_H = 60
MIND_CHILD_W = 154
MIND_CHILD_H = 50
MIND_CHILD_PITCH = 58   # vertical spacing between a branch's children

# decision: layered top-to-bottom flowchart nodes + labeled directed edges.
DEC_NODE_W = 176
DEC_NODE_H = 74
DEC_ROW_PITCH = 132
# node `kind` -> flowchart shape_type (shape-catalog.md): terminator pill / decision rhombus /
# process rectangle.
DEC_KIND_SHAPE = {"start": "terminator", "end": "terminator",
                  "decision": "decision", "process": "process"}

# --- Phase D geometry (nest — recursively-nested container layout) ---
# A box node -> an `area` frame; children laid inside with padding so they visibly nest.
# Heights are measured BOTTOM-UP so every parent frame fits its children exactly.
NEST_PAD_X = 18          # horizontal inner padding inside a box (left+right)
NEST_PAD_TOP = 14        # top padding above the header line
NEST_PAD_BOTTOM = 16     # bottom padding below the last child
NEST_HEADER_H = 30       # header line height (bold label + optional muted meta)
NEST_DESC_LINE_H = 20    # ~1 wrapped line of `desc` body text
NEST_GAP = 16            # vertical gap between stacked (layout:"column") children
NEST_GUTTER = 16         # horizontal gutter between side-by-side (layout:"row") children
NEST_MAX_DEPTH = 5       # recursion cap; nodes at the cap render as leaves (children ignored)

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


def lerp_hex(a, b, t):
    """Linear blend between two hex colors (t=0 -> a, t=1 -> b). For gradient segments."""
    ra, ga, ba = _hx(a)
    rb, gb, bb = _hx(b)
    return "#%02X%02X%02X" % (round(ra + (rb - ra) * t),
                              round(ga + (gb - ga) * t),
                              round(ba + (bb - ba) * t))


def alpha_hex(hex_color, alpha="2E"):
    """Return an 8-digit #RRGGBBAA fill (semi-transparent) — for overlapping venn circles."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return "#%s%s" % (h[:6].upper(), alpha)


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


def _row_cells(row):
    """A table row's cells, accepting BOTH shapes: the documented {"cells":[...]} object
    and the natural bare list [cell, cell, ...]. Anything else yields no cells."""
    if isinstance(row, dict):
        return row.get("cells") or []
    if isinstance(row, list):
        return row
    return []


def _table_layout(block, inner_w):
    """Return (col_w, header_h, row_heights[], total_height) for a table block at inner_w."""
    cols = block.get("columns", []) or []
    ncols = max(1, len(cols))
    col_w = inner_w / float(ncols)
    rows = block.get("rows", []) or []
    row_hs = []
    for row in rows:
        cells = _row_cells(row)
        h = TABLE_ROW_MIN
        for ci in range(len(cols)):
            cell = cells[ci] if ci < len(cells) else {}
            h = max(h, _cell_height(cell, col_w))
        row_hs.append(h)
    total = TABLE_HEADER_H + sum(row_hs)
    return col_w, TABLE_HEADER_H, row_hs, total


# --- Phase C-2 shared metrics (used by BOTH content_height and the builders, so the frame
# always fits what the builder lays out). Each is pure/defensive — no exceptions escape. ---
def _count_tree(node, depth):
    """Return (leaf_count, max_depth) of a tree node, honoring the TREE_MAX_DEPTH cap.
    `node` is an object whose `children` is a list of child node objects."""
    ch = node.get("children") or [] if isinstance(node, dict) else []
    if depth >= TREE_MAX_DEPTH or not ch:
        return 1, depth
    leaves, maxd = 0, depth
    for c in ch:
        if isinstance(c, dict):
            l, d = _count_tree(c, depth + 1)
            leaves += l
            maxd = max(maxd, d)
    return (leaves or 1), maxd


def _decision_ranks(nodes, edges):
    """Layer each decision node by longest-path rank (root=0). Cycle-safe: relaxation is
    bounded to len(nodes) passes. Returns {id: rank}. Ignores malformed nodes/edges."""
    ids = [str(nd["id"]) for nd in nodes
           if isinstance(nd, dict) and nd.get("id") is not None]
    rank = {i: 0 for i in ids}
    for _ in range(len(ids)):
        changed = False
        for e in edges:
            if not isinstance(e, dict):
                continue
            f, t = str(e.get("from")), str(e.get("to"))
            if f in rank and t in rank and rank[t] < rank[f] + 1:
                rank[t] = rank[f] + 1
                changed = True
        if not changed:
            break
    return rank


def _decision_maxrank(block):
    rank = _decision_ranks(block.get("nodes", []) or [], block.get("edges", []) or [])
    return max(rank.values()) if rank else 0


# --- Phase D shared geometry (nest). _nest_children / _nest_desc_h / _nest_measure are used by
# BOTH content_height and build_nest, so the frame and the laid-out children always agree.
# All three are pure/defensive — they NEVER raise (validation + raising lives in build_nest). ---
def _nest_children(node, depth):
    """The child nodes this node renders: none for a `callout` (a leaf) or at the depth cap;
    otherwise its `children` list (verbatim — may hold non-dicts, which the tolerant measure
    counts and build_nest's up-front validator rejects)."""
    if not isinstance(node, dict) or node.get("kind") == "callout":
        return []
    if depth >= NEST_MAX_DEPTH - 1:
        return []
    ch = node.get("children")
    return ch if isinstance(ch, list) else []


def _nest_desc_h(desc, inner_w):
    """Estimated height of a node's `desc` paragraph wrapped at inner_w (0 when absent)."""
    if not desc:
        return 0.0
    cpl = max(12, int(inner_w / 8.0))
    lines = max(1, int(math.ceil(len(str(desc)) / float(cpl))))
    return lines * NEST_DESC_LINE_H + 6


def _nest_measure(node, width, depth):
    """Bottom-up height of a nest node at box width `width`: header + desc + (children extent)
    + padding, so a parent frame fits its children exactly. Tolerant of malformed nodes."""
    inner_w = max(20.0, width - 2 * NEST_PAD_X)
    desc_h = _nest_desc_h(node.get("desc") if isinstance(node, dict) else None, inner_w)
    content_top = NEST_PAD_TOP + NEST_HEADER_H + desc_h
    children = _nest_children(node, depth)
    if not children:
        return content_top + NEST_PAD_BOTTOM
    layout = node.get("layout", "column")
    if layout == "row":
        m = len(children)
        child_w = (inner_w - (m - 1) * NEST_GUTTER) / float(m) if m else inner_w
        extent = max((_nest_measure(c, child_w, depth + 1) for c in children), default=0.0)
    else:  # column: stacked top-to-bottom with a gap between children
        extent = sum(_nest_measure(c, inner_w, depth + 1) for c in children)
        extent += max(0, len(children) - 1) * NEST_GAP
    return content_top + extent + NEST_PAD_BOTTOM


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
        # --- Phase C-1 blocks ---
        if t == "gauge":
            items = block.get("items", []) or []
            cols = max(1, int(block.get("columns", min(len(items), 3) or 1)))
            rows = _grid(len(items), cols)
            return rows * GAUGE_H + max(0, rows - 1) * GAUGE_GUTTER
        if t == "pyramid":
            n = len(block.get("layers", []) or [])
            return n * PYR_BAND_H + max(0, n - 1) * PYR_GAP
        if t == "funnel":
            n = len(block.get("stages", []) or [])
            return n * FUN_BAND_H + max(0, n - 1) * FUN_GAP
        if t == "quadrant":
            return QUAD_PLOT_H + QUAD_XLABEL_H
        if t == "pillars":
            return PILLAR_CAP_H + PILLAR_GAP + PILLAR_H
        if t == "spectrum":
            return SPECTRUM_H
        if t == "rings":
            return min(RINGS_MAX_D, inner_w)
        if t == "venn":
            return VENN_H
        # --- Phase C-2 blocks (connector/graph-heavy) ---
        if t == "cycle":
            return CYCLE_H
        if t == "hub":
            return HUB_H
        if t == "timeline":
            return TIMELINE_H
        if t == "swimlane":
            nlanes = len(block.get("lanes", []) or [])
            return SWIM_HEADER_H + SWIM_LANE_GAP + nlanes * (SWIM_LANE_H + SWIM_LANE_GAP)
        if t == "gantt":
            ntasks = len(block.get("tasks", []) or [])
            return GANTT_AXIS_H + ntasks * GANTT_ROW_H + 16
        if t == "tree":
            # height = depth for "down"; leaf-count * row pitch for "right".
            leaves, maxd = _count_tree({"children": block.get("children", []) or []}, 0)
            if block.get("direction") == "right":
                return max(TREE_NODE_H, leaves * TREE_ROW_PITCH)
            return (maxd + 1) * TREE_LEVEL_PITCH
        if t == "mindmap":
            return MIND_H
        if t == "decision":
            # (max longest-path rank + 1) rows, so the frame fits the deepest branch.
            return (_decision_maxrank(block) + 1) * DEC_ROW_PITCH + 20
        # --- Phase D block (recursively-nested containers) ---
        if t == "nest":
            # Bottom-up: the root box's own height IS the nest's height (below the heading band).
            # Uses the SAME _nest_measure the builder uses, so frame and layout agree. Defensive:
            # a malformed node -> MANUAL_H here (the builder still raises + degrades to manual).
            node = block.get("node")
            if not isinstance(node, dict):
                return MANUAL_H
            return _nest_measure(node, inner_w, 0)
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
    ncells_total = 0
    for ri, row in enumerate(rows):
        cells = _row_cells(row)
        ncells_total += len(cells)
        rh = row_hs[ri]
        for ci in range(ncols):
            cell = cells[ci] if ci < len(cells) else {}
            cx = ix + ci * col_w
            _table_cell(out, sid, ri, ci, cell, cx, ry, col_w, rh, pal, col_hex[ci],
                        area_key, icon_index, leading=(ci == 0))
        ry += rh

    # Guard the silent-empty-table trap: headers + tints rendered but no cell ever did.
    if rows and ncells_total == 0:
        out.warn("section %s: table rows produced no cells — each row must be a list "
                 "[cell, ...] or a {\"cells\": [...]} object (headers/tints built, bodies empty)" % sid)


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


# ===========================================================================
# Phase C-1: STATIC / deterministic metaphor blocks (shape + text only, NO
# connectors). Each validates its required fields and RAISES ValueError on a
# malformed spec so the guarded dispatch in compile_board() degrades the block
# to manual_blocks + a warning (never crashing the whole board). Geometry is
# derived from the inner content region; backgrounds are emitted first so labels
# (create_textboxes, painted last) always land on top. All widgets carry
# _key/_parent; colors resolve via resolve(role_or_hex, pal).
# ===========================================================================
def _gauge_zone_color(zones, value, pal, default_role):
    """Active-zone color: the FIRST band whose `upTo` >= value (bands run min->max).
    Above the last band's upTo, fall back to the last band; no zones -> the default role."""
    if zones:
        for z in zones:
            if not isinstance(z, dict) or "upTo" not in z:
                raise ValueError("gauge zone missing `upTo`")
            if value <= z["upTo"]:
                return resolve(z.get("color", default_role), pal, default_role)
        return resolve(zones[-1].get("color", default_role), pal, default_role)
    return resolve(default_role, pal, "primary")


def build_gauge(out, sid, block, ix, iy, iw, ih, pal, area_key):
    """One linear-meter tile per item: label + track + value fill (colored by the active
    `zones` band, width = (value-min)/(max-min)) + centered `value``unit` (the fidelity)."""
    items = block.get("items", []) or []
    if not items:
        raise ValueError("gauge has no `items`")
    cols = max(1, int(block.get("columns", min(len(items), 3) or 1)))
    cw = (iw - (cols - 1) * GAUGE_GUTTER) / float(cols)
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError("gauge item %d is not an object" % idx)
        for f in ("value", "min", "max"):
            if item.get(f) is None:
                raise ValueError("gauge item %d missing `%s`" % (idx, f))
        value = float(item["value"])
        vmin = float(item["min"])
        vmax = float(item["max"])
        span = vmax - vmin
        if span <= 0:
            raise ValueError("gauge item %d has max<=min" % idx)
        frac = max(0.0, min(1.0, (value - vmin) / span))
        active = _gauge_zone_color(item.get("zones"), value,
                                   pal, item.get("color", "primary"))
        unit = item.get("unit", "") or ""

        r, c = idx // cols, idx % cols
        cx = ix + c * (cw + GAUGE_GUTTER)
        cy = iy + r * (GAUGE_H + GAUGE_GUTTER)
        base = f"{sid}.gauge{idx}"
        # backgrounds first: tile, then track, then the value fill on top.
        out.add("create_shapes", {
            "shape_type": "rounded_square", "x": round(cx, 1), "y": round(cy, 1),
            "width": round(cw, 1), "height": GAUGE_H,
            "background_color": pal.get("surface", DEFAULT_PALETTE["surface"]),
            "stroke_color": tint(active, 0.6), "stroke_size": 1,
        }, f"{base}.bg", area_key)
        track_x = cx + 16
        track_w = cw - 32
        track_y = cy + GAUGE_H - 52
        out.add("create_shapes", {
            "shape_type": "rounded_square", "x": round(track_x, 1), "y": round(track_y, 1),
            "width": round(track_w, 1), "height": GAUGE_TRACK_H,
            "background_color": tint(active, 0.85), "stroke_color": tint(active, 0.6),
            "stroke_size": 1,
        }, f"{base}.track", area_key)
        out.add("create_shapes", {
            "shape_type": "rounded_square", "x": round(track_x, 1), "y": round(track_y, 1),
            "width": round(max(1.0, track_w * frac), 1), "height": GAUGE_TRACK_H,
            "background_color": active, "stroke_color": active, "stroke_size": 0,
        }, f"{base}.fill", area_key)
        # text on top: metric label, big value+unit (the fidelity), min/max ends, caption.
        out.add("create_textboxes", {
            "x": round(cx + 16, 1), "y": round(cy + 14, 1), "width": round(cw - 32, 1),
            "text": item.get("label", ""), "font_size": 14, "bold": True,
            "font_color": pal.get("ink", DEFAULT_PALETTE["ink"]),
        }, f"{base}.label", area_key)
        out.add("create_textboxes", {
            "x": round(cx + 16, 1), "y": round(cy + 42, 1), "width": round(cw - 32, 1),
            "text": "%s%s" % (item["value"], unit), "font_size": 30, "bold": True,
            "font_color": active, "text_align": "center",
        }, f"{base}.value", area_key)
        out.add("create_textboxes", {
            "x": round(track_x, 1), "y": round(track_y + GAUGE_TRACK_H + 2, 1),
            "width": round(track_w, 1),
            "text": "%s%s          %s%s" % (item["min"], unit, item["max"], unit),
            "font_size": 10, "font_color": MUTED,
        }, f"{base}.scale", area_key)
        if item.get("caption"):
            out.add("create_textboxes", {
                "x": round(cx + 16, 1), "y": round(cy + GAUGE_H - 20, 1),
                "width": round(cw - 32, 1), "text": item["caption"],
                "font_size": 11, "italic": True, "font_color": MUTED,
            }, f"{base}.caption", area_key)


def build_pyramid(out, sid, block, ix, iy, iw, ih, pal, area_key):
    """Stacked horizontal bands, widest at the base. `direction:"up"` (default) = apex on top
    (widths grow top->bottom); `direction:"down"` = apex on the bottom (widths shrink)."""
    layers = block.get("layers", []) or []
    n = len(layers)
    if n == 0:
        raise ValueError("pyramid has no `layers`")
    up = block.get("direction", "up") != "down"  # up => apex (narrowest) on top
    for i, layer in enumerate(layers):
        if not isinstance(layer, dict):
            layer = {"label": str(layer)}
        # fraction of full width for this band; monotonic in i.
        if n == 1:
            frac = 1.0
        else:
            g = i / float(n - 1)                       # 0 at top .. 1 at bottom
            frac = (PYR_MIN_FRAC + (1.0 - PYR_MIN_FRAC) * g) if up else \
                   (1.0 - (1.0 - PYR_MIN_FRAC) * g)
        bw = iw * frac
        bx = ix + (iw - bw) / 2.0
        by = iy + i * (PYR_BAND_H + PYR_GAP)
        color = resolve(layer.get("color", CYCLE[i % len(CYCLE)]), pal, "primary")
        out.add("create_shapes", {
            "shape_type": "trapezoid", "x": round(bx, 1), "y": round(by, 1),
            "width": round(bw, 1), "height": PYR_BAND_H,
            "background_color": color, "stroke_color": color, "stroke_size": 0,
            "text": str(layer.get("label", "")), "font_size": 15, "bold": True,
            "text_align": "center", "font_color": contrast(color),
        }, "%s.pyr%d" % (sid, i), area_key)


def build_funnel(out, sid, block, ix, iy, iw, ih, pal, area_key):
    """Stacked bands narrowing top->bottom. Width ∝ `value` when values are given, else a
    linear taper by order. Labels + values are the fidelity (verbatim)."""
    stages = block.get("stages", []) or []
    n = len(stages)
    if n == 0:
        raise ValueError("funnel has no `stages`")
    vals = []
    for s in stages:
        vals.append(s.get("value") if isinstance(s, dict) else None)
    have_vals = all(v is not None for v in vals) and n > 0
    vmax = max((float(v) for v in vals), default=0.0) if have_vals else 0.0
    for i, stage in enumerate(stages):
        if not isinstance(stage, dict):
            stage = {"label": str(stage)}
        if have_vals and vmax > 0:
            # width ∝ value (verbatim proportion — never smooth the taper). Only a tiny
            # absolute floor so a near-zero stage still renders a clickable band.
            frac = max(0.05, float(vals[i]) / vmax)
        elif n == 1:
            frac = 1.0
        else:
            frac = 1.0 - (1.0 - FUN_MIN_FRAC) * (i / float(n - 1))
        frac = min(1.0, frac)
        bw = iw * frac
        bx = ix + (iw - bw) / 2.0
        by = iy + i * (FUN_BAND_H + FUN_GAP)
        color = resolve(stage.get("color", CYCLE[i % len(CYCLE)]), pal, "primary")
        label = stage.get("label", "")
        text = "%s  (%s)" % (label, stage["value"]) if have_vals else str(label)
        out.add("create_shapes", {
            "shape_type": "trapezoid", "x": round(bx, 1), "y": round(by, 1),
            "width": round(bw, 1), "height": FUN_BAND_H,
            "background_color": color, "stroke_color": color, "stroke_size": 0,
            "text": text, "font_size": 15, "bold": True,
            "text_align": "center", "font_color": contrast(color),
        }, "%s.fun%d" % (sid, i), area_key)


def build_quadrant(out, sid, block, ix, iy, iw, ih, pal, area_key):
    """A 2x2 tinted plot + x/y axis pole labels (low/high) + a positioned dot per item at its
    (x,y) in [0,1] (x left->right, y bottom->top), each with the item label."""
    xaxis = block.get("xAxis", {}) or {}
    yaxis = block.get("yAxis", {}) or {}
    qlabels = block.get("quadrantLabels", []) or []  # [bl, br, tl, tr]
    items = block.get("items", []) or []

    plot_x = ix + QUAD_YLABEL_W
    plot_y = iy
    plot_w = iw - QUAD_YLABEL_W
    plot_h = min(QUAD_PLOT_H, ih - QUAD_XLABEL_H)
    hw, hh = plot_w / 2.0, plot_h / 2.0
    ink = pal.get("ink", DEFAULT_PALETTE["ink"])

    # 1) four tinted cells (backgrounds). Order [bl, br, tl, tr] matches quadrantLabels.
    cells = [
        (plot_x,      plot_y + hh),  # bottom-left
        (plot_x + hw, plot_y + hh),  # bottom-right
        (plot_x,      plot_y),       # top-left
        (plot_x + hw, plot_y),       # top-right
    ]
    for qi, (cxp, cyp) in enumerate(cells):
        fill = tint(resolve(QUAD_CELL_ROLES[qi], pal, "surface"), 0.90)
        out.add("create_shapes", {
            "shape_type": "rectangle", "x": round(cxp, 1), "y": round(cyp, 1),
            "width": round(hw, 1), "height": round(hh, 1),
            "background_color": fill, "stroke_color": "#DADCE0", "stroke_size": 1,
        }, "%s.quad.cell%d" % (sid, qi), area_key)

    # 2) crosshair — two thin rectangles (stroke set so they don't inherit the dark default).
    out.add("create_shapes", {
        "shape_type": "rectangle", "x": round(plot_x + hw - 1, 1), "y": round(plot_y, 1),
        "width": 2, "height": round(plot_h, 1),
        "background_color": MUTED, "stroke_color": MUTED, "stroke_size": 0,
    }, "%s.quad.vline" % sid, area_key)
    out.add("create_shapes", {
        "shape_type": "rectangle", "x": round(plot_x, 1), "y": round(plot_y + hh - 1, 1),
        "width": round(plot_w, 1), "height": 2,
        "background_color": MUTED, "stroke_color": MUTED, "stroke_size": 0,
    }, "%s.quad.hline" % sid, area_key)

    # 3) quadrant cell labels (centered-ish in each cell).
    for qi, (cxp, cyp) in enumerate(cells):
        if qi < len(qlabels) and qlabels[qi]:
            out.add("create_textboxes", {
                "x": round(cxp + 10, 1), "y": round(cyp + 10, 1), "width": round(hw - 20, 1),
                "text": str(qlabels[qi]), "font_size": 13, "bold": True,
                "font_color": MUTED, "text_align": "center",
            }, "%s.quad.qlabel%d" % (sid, qi), area_key)

    # 4) axis pole labels: x low/high under the plot, y low/high in the left gutter.
    if xaxis.get("low"):
        out.add("create_textboxes", {
            "x": round(plot_x, 1), "y": round(plot_y + plot_h + 8, 1), "width": round(hw, 1),
            "text": str(xaxis["low"]), "font_size": 12, "bold": True, "font_color": ink,
        }, "%s.quad.xlow" % sid, area_key)
    if xaxis.get("high"):
        out.add("create_textboxes", {
            "x": round(plot_x + hw, 1), "y": round(plot_y + plot_h + 8, 1),
            "width": round(hw, 1), "text": str(xaxis["high"]), "font_size": 12, "bold": True,
            "font_color": ink, "text_align": "right",
        }, "%s.quad.xhigh" % sid, area_key)
    if yaxis.get("high"):
        out.add("create_textboxes", {
            "x": round(ix, 1), "y": round(plot_y + 4, 1), "width": round(QUAD_YLABEL_W - 8, 1),
            "text": str(yaxis["high"]), "font_size": 12, "bold": True, "font_color": ink,
        }, "%s.quad.yhigh" % sid, area_key)
    if yaxis.get("low"):
        out.add("create_textboxes", {
            "x": round(ix, 1), "y": round(plot_y + plot_h - 20, 1),
            "width": round(QUAD_YLABEL_W - 8, 1), "text": str(yaxis["low"]),
            "font_size": 12, "bold": True, "font_color": ink,
        }, "%s.quad.ylow" % sid, area_key)

    # 5) positioned item dots. Validate x/y in [0,1] (out of range -> degrade to manual),
    # then clamp the dot CENTER so the whole dot bbox stays inside the plot.
    r = QUAD_DOT / 2.0
    for di, item in enumerate(items):
        if not isinstance(item, dict) or item.get("x") is None or item.get("y") is None:
            raise ValueError("quadrant item %d missing x/y" % di)
        x = float(item["x"])
        y = float(item["y"])
        if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
            raise ValueError("quadrant item %d x/y out of [0,1]" % di)
        dcx = plot_x + x * plot_w
        dcy = plot_y + (1.0 - y) * plot_h  # y bottom->top
        dcx = min(max(dcx, plot_x + r), plot_x + plot_w - r)
        dcy = min(max(dcy, plot_y + r), plot_y + plot_h - r)
        color = resolve(item.get("color", CYCLE[di % len(CYCLE)]), pal, "primary")
        out.add("create_shapes", {
            "shape_type": "ellipse", "x": round(dcx - r, 1), "y": round(dcy - r, 1),
            "width": QUAD_DOT, "height": QUAD_DOT,
            "background_color": color, "stroke_color": color, "stroke_size": 0,
        }, "%s.quad.dot%d" % (sid, di), area_key)
        out.add("create_textboxes", {
            "x": round(dcx + r + 4, 1), "y": round(dcy - LINE_H / 2.0, 1),
            "width": 140, "text": str(item.get("label", "")), "font_size": 11,
            "font_color": ink,
        }, "%s.quad.dotlabel%d" % (sid, di), area_key)


def build_pillars(out, sid, block, ix, iy, iw, ih, pal, area_key, icon_index):
    """A capstone bar across the top (label from `capstone`) over N flex columns, each with
    an optional icon + title + desc, tinted by the column color."""
    columns = block.get("columns", []) or []
    n = len(columns)
    if n == 0:
        raise ValueError("pillars has no `columns`")
    # capstone bar (backgrounds first).
    cap = block.get("capstone")
    col_y = iy
    if cap:
        cap_bg = resolve(block.get("color", "ink"), pal, "ink")
        out.add("create_shapes", {
            "shape_type": "rectangle", "x": round(ix, 1), "y": round(iy, 1),
            "width": round(iw, 1), "height": PILLAR_CAP_H,
            "background_color": cap_bg, "stroke_color": cap_bg, "stroke_size": 0,
            "text": str(cap), "font_size": 18, "bold": True,
            "text_align": "center", "font_color": contrast(cap_bg),
        }, "%s.pillars.cap" % sid, area_key)
        col_y = iy + PILLAR_CAP_H + PILLAR_GAP
    col_h = min(PILLAR_H, iy + ih - col_y)
    cw = (iw - (n - 1) * PILLAR_COL_GUTTER) / float(n)
    for ci, col in enumerate(columns):
        if not isinstance(col, dict):
            col = {"title": str(col)}
        cx = ix + ci * (cw + PILLAR_COL_GUTTER)
        color = resolve(col.get("color", CYCLE[ci % len(CYCLE)]), pal, "primary")
        out.add("create_shapes", {
            "shape_type": "rectangle", "x": round(cx, 1), "y": round(col_y, 1),
            "width": round(cw, 1), "height": round(col_h, 1),
            "background_color": tint(color, 0.90), "stroke_color": color, "stroke_size": 2,
        }, "%s.pillars.col%d" % (sid, ci), area_key)
        top = col_y + 18
        if col.get("icon") is not None:
            nid, concept = resolve_icon(col["icon"], icon_index)
            if nid is not None:
                out.add("create_icons", {
                    "noun_project_id": nid,
                    "x": round(cx + cw / 2.0 - ICON_SLOT / 2.0, 1), "y": round(top, 1),
                    "width": ICON_SLOT, "height": ICON_SLOT, "color": color,
                    "tags": [str(concept)] if concept else [],
                }, "%s.pillars.col%d.icon" % (sid, ci), area_key)
                top += ICON_SLOT + 8
            else:
                out.warn("section %s pillars col%d: icon %r unresolved (run search_icons)"
                         % (sid, ci, concept))
        out.add("create_textboxes", {
            "x": round(cx + 14, 1), "y": round(top, 1), "width": round(cw - 28, 1),
            "text": str(col.get("title", "")), "font_size": 16, "bold": True,
            "font_color": color, "text_align": "center",
        }, "%s.pillars.col%d.title" % (sid, ci), area_key)
        if col.get("desc"):
            out.add("create_textboxes", {
                "x": round(cx + 14, 1), "y": round(top + 30, 1), "width": round(cw - 28, 1),
                "text": str(col["desc"]), "font_size": 12,
                "font_color": pal.get("ink", DEFAULT_PALETTE["ink"]), "text_align": "center",
            }, "%s.pillars.col%d.desc" % (sid, ci), area_key)


def build_spectrum(out, sid, block, ix, iy, iw, ih, pal, area_key):
    """A horizontal gradient-approximation bar (row of adjacent color segments) + pole labels
    at both ends + a marker (dot + label) per `markers[]` at its `at` in [0,1]."""
    poles = block.get("poles", []) or []
    markers = block.get("markers", []) or []
    ink = pal.get("ink", DEFAULT_PALETTE["ink"])
    c_start = resolve(block.get("startColor", "primary"), pal, "primary")
    c_end = resolve(block.get("endColor", "accent"), pal, "accent")

    bar_y = iy + 46
    seg_w = iw / float(SPECTRUM_SEG)
    # gradient approximation: N adjacent segments blended start->end (backgrounds first).
    for s in range(SPECTRUM_SEG):
        t = s / float(SPECTRUM_SEG - 1) if SPECTRUM_SEG > 1 else 0.0
        out.add("create_shapes", {
            "shape_type": "rectangle", "x": round(ix + s * seg_w, 1), "y": round(bar_y, 1),
            "width": round(seg_w + 1, 1), "height": SPECTRUM_BAR_H,
            "background_color": lerp_hex(c_start, c_end, t),
            "stroke_color": lerp_hex(c_start, c_end, t), "stroke_size": 0,
        }, "%s.spec.seg%d" % (sid, s), area_key)

    # pole labels at each end, below the bar.
    if len(poles) >= 1 and poles[0]:
        out.add("create_textboxes", {
            "x": round(ix, 1), "y": round(bar_y + SPECTRUM_BAR_H + 6, 1),
            "width": round(iw / 2.0, 1), "text": str(poles[0]), "font_size": 13,
            "bold": True, "font_color": ink,
        }, "%s.spec.poleL" % sid, area_key)
    if len(poles) >= 2 and poles[1]:
        out.add("create_textboxes", {
            "x": round(ix + iw / 2.0, 1), "y": round(bar_y + SPECTRUM_BAR_H + 6, 1),
            "width": round(iw / 2.0, 1), "text": str(poles[1]), "font_size": 13,
            "bold": True, "font_color": ink, "text_align": "right",
        }, "%s.spec.poleR" % sid, area_key)

    # markers: small dot on the bar + label above, at `at` in [0,1] (clamped inside the bar).
    r = SPECTRUM_DOT / 2.0
    for mi, m in enumerate(markers):
        at = float(m.get("at", 0.5)) if isinstance(m, dict) else 0.5
        at = max(0.0, min(1.0, at))
        mx = ix + at * iw
        mx = min(max(mx, ix + r), ix + iw - r)
        color = resolve((m.get("color") if isinstance(m, dict) else None)
                        or CYCLE[mi % len(CYCLE)], pal, "primary")
        out.add("create_shapes", {
            "shape_type": "ellipse", "x": round(mx - r, 1),
            "y": round(bar_y + SPECTRUM_BAR_H / 2.0 - r, 1),
            "width": SPECTRUM_DOT, "height": SPECTRUM_DOT,
            "background_color": color, "stroke_color": "#FFFFFF", "stroke_size": 2,
        }, "%s.spec.dot%d" % (sid, mi), area_key)
        label = m.get("label", "") if isinstance(m, dict) else str(m)
        out.add("create_textboxes", {
            "x": round(mx - 70, 1), "y": round(iy + 8, 1), "width": 140,
            "text": str(label), "font_size": 12, "bold": True,
            "font_color": color, "text_align": "center",
        }, "%s.spec.mlabel%d" % (sid, mi), area_key)


def build_rings(out, sid, block, ix, iy, iw, ih, pal, area_key):
    """Nested concentric ellipses (largest created FIRST so it renders underneath), one per
    ring, each labeled near the top of its ring. `rings` list is innermost -> outermost."""
    rings = block.get("rings", []) or []
    n = len(rings)
    if n == 0:
        raise ValueError("rings has no `rings`")
    D = min(RINGS_MAX_D, iw, ih)
    cx = ix + iw / 2.0
    cy = iy + D / 2.0  # shared center; all ellipses concentric
    # Emit OUTERMOST first (largest -> under), so iterate ring index high->low.
    for i in range(n - 1, -1, -1):
        ring = rings[i] if isinstance(rings[i], dict) else {"label": str(rings[i])}
        d = D * (i + 1) / float(n)
        color = resolve(ring.get("color", CYCLE[i % len(CYCLE)]), pal, "primary")
        out.add("create_shapes", {
            "shape_type": "ellipse", "x": round(cx - d / 2.0, 1), "y": round(cy - d / 2.0, 1),
            "width": round(d, 1), "height": round(d, 1),
            "background_color": color, "stroke_color": contrast(color), "stroke_size": 1,
        }, "%s.ring%d" % (sid, i), area_key)
    # labels near the top of each ring (painted last, on top).
    for i in range(n):
        ring = rings[i] if isinstance(rings[i], dict) else {"label": str(rings[i])}
        d = D * (i + 1) / float(n)
        color = resolve(ring.get("color", CYCLE[i % len(CYCLE)]), pal, "primary")
        out.add("create_textboxes", {
            "x": round(cx - d / 2.0 + 10, 1), "y": round(cy - d / 2.0 + 8, 1),
            "width": round(d - 20, 1), "text": str(ring.get("label", "")),
            "font_size": 13, "bold": True, "font_color": contrast(color),
            "text_align": "center",
        }, "%s.ring%d.label" % (sid, i), area_key)


def build_venn(out, sid, block, ix, iy, iw, ih, pal, area_key):
    """2-3 overlapping ellipses with semi-transparent fills (8-digit alpha hex) so the
    intersection reads; each circle labeled, plus an optional centered `overlapLabel`."""
    sets = block.get("sets", []) or []
    n = len(sets)
    if n < 2 or n > 3:
        raise ValueError("venn needs 2 or 3 `sets` (got %d)" % n)
    ink = pal.get("ink", DEFAULT_PALETTE["ink"])
    avail_h = ih - 30  # top label room
    if n == 3:
        D = min(VENN_MAX_D, iw / 1.7, avail_h / 1.55)
    else:
        D = min(VENN_MAX_D, iw / 1.7, avail_h)
    dx = D * 0.62  # horizontal center-to-center distance (overlap ~0.38 D)
    dy = D * 0.55
    midx = ix + iw / 2.0
    top = iy + 24
    if n == 2:
        centers = [(midx - dx / 2.0, top + D / 2.0), (midx + dx / 2.0, top + D / 2.0)]
    else:
        centers = [(midx - dx / 2.0, top + D / 2.0),
                   (midx + dx / 2.0, top + D / 2.0),
                   (midx, top + dy + D / 2.0)]
    # circles (semi-transparent fills so overlaps blend).
    for si, st in enumerate(sets):
        st = st if isinstance(st, dict) else {"label": str(st)}
        color = resolve(st.get("color", CYCLE[si % len(CYCLE)]), pal, "primary")
        ccx, ccy = centers[si]
        out.add("create_shapes", {
            "shape_type": "ellipse", "x": round(ccx - D / 2.0, 1), "y": round(ccy - D / 2.0, 1),
            "width": round(D, 1), "height": round(D, 1),
            "background_color": alpha_hex(color, VENN_ALPHA),
            "stroke_color": color, "stroke_size": 2,
        }, "%s.venn.set%d" % (sid, si), area_key)
    # set labels near the top of each circle.
    for si, st in enumerate(sets):
        st = st if isinstance(st, dict) else {"label": str(st)}
        color = resolve(st.get("color", CYCLE[si % len(CYCLE)]), pal, "primary")
        ccx, ccy = centers[si]
        out.add("create_textboxes", {
            "x": round(ccx - D / 2.0, 1), "y": round(ccy - D / 2.0 + 12, 1),
            "width": round(D, 1), "text": str(st.get("label", "")),
            "font_size": 14, "bold": True, "font_color": color, "text_align": "center",
        }, "%s.venn.set%d.label" % (sid, si), area_key)
    # optional overlap label at the centroid of all centers.
    if block.get("overlapLabel"):
        ox = sum(c[0] for c in centers) / float(n)
        oy = sum(c[1] for c in centers) / float(n)
        out.add("create_textboxes", {
            "x": round(ox - 80, 1), "y": round(oy - LINE_H / 2.0, 1), "width": 160,
            "text": str(block["overlapLabel"]), "font_size": 12, "bold": True,
            "font_color": ink, "text_align": "center",
        }, "%s.venn.overlap" % sid, area_key)


# ===========================================================================
# Phase C-2: CONNECTOR / GRAPH-heavy metaphor blocks. Each lays node shapes
# (whose _key a connector can point at) then emits REAL connectors via
# Out.connect referencing those node _keys — never glyph arrows. Like Phase
# C-1, each validates its spec and RAISES ValueError on malformation so the
# guarded dispatch degrades it to manual_blocks + a warning (rolling back any
# widgets/connectors emitted before the raise). Backgrounds/shapes are emitted
# before their labels (create_textboxes paints last, so labels land on top).
# Every connector endpoint is a node shape emitted in the SAME builder, so no
# connector is ever left dangling.
# ===========================================================================
def _label_node(out, key, area_key, x, y, w, h, shape_type, fill, stroke, stroke_size,
                label, text_color, font_size, icon, icon_index, warn_tag):
    """Emit one graph node whose SHAPE carries `key` (so a connector to `key` always
    resolves). With a resolved icon: icon top-center + label textbox beneath it. Without:
    the label is baked into the shape's own (vertically-centered) text. Shared by hub / tree
    / mindmap; cycle/decision inline their own node treatment (desc lines, kind-shapes)."""
    nid, concept = (None, None)
    if icon is not None:
        nid, concept = resolve_icon(icon, icon_index)
        if nid is None:
            out.warn("%s: icon %r unresolved (run search_icons)" % (warn_tag, concept))
    if nid is not None:
        out.add("create_shapes", {
            "shape_type": shape_type, "x": round(x, 1), "y": round(y, 1),
            "width": round(w, 1), "height": round(h, 1),
            "background_color": fill, "stroke_color": stroke, "stroke_size": stroke_size,
        }, key, area_key)
        out.add("create_icons", {
            "noun_project_id": nid, "x": round(x + w / 2.0 - ICON_SLOT / 2.0, 1),
            "y": round(y + 8, 1), "width": ICON_SLOT, "height": ICON_SLOT,
            "color": stroke, "tags": [str(concept)] if concept else [],
        }, key + ".icon", area_key)
        out.add("create_textboxes", {
            "x": round(x + 8, 1), "y": round(y + 8 + ICON_SLOT + 2, 1),
            "width": round(w - 16, 1), "text": str(label), "font_size": font_size,
            "bold": True, "font_color": text_color, "text_align": "center",
        }, key + ".label", area_key)
    else:
        out.add("create_shapes", {
            "shape_type": shape_type, "x": round(x, 1), "y": round(y, 1),
            "width": round(w, 1), "height": round(h, 1),
            "background_color": fill, "stroke_color": stroke, "stroke_size": stroke_size,
            "text": str(label), "font_size": font_size, "bold": True,
            "text_align": "center", "font_color": text_color,
        }, key, area_key)


def build_cycle(out, sid, block, ix, iy, iw, ih, pal, area_key, icon_index):
    """Nodes placed around a ring (or a 2x2 for exactly 4) + REAL connectors i->i+1 closing the
    loop last->first (loop:true on the closing edge). style:"flywheel" -> curved arrows."""
    steps = block.get("steps", []) or []
    n = len(steps)
    if n < 2:
        raise ValueError("cycle needs >=2 `steps` (got %d)" % n)
    arrow = "curve" if block.get("style") == "flywheel" else None
    nw, nh = CYCLE_NODE_W, CYCLE_NODE_H
    D = min(iw, CYCLE_H)
    cx = ix + iw / 2.0
    cy = iy + D / 2.0

    # node CENTER positions: a 2x2 (clockwise from top-left) for exactly 4, else a ring.
    if n == 4:
        gx = (D / 2.0 - nw / 2.0) * 0.9
        gy = (D / 2.0 - nh / 2.0) * 0.9
        centers = [(cx - gx, cy - gy), (cx + gx, cy - gy),
                   (cx + gx, cy + gy), (cx - gx, cy + gy)]
    else:
        r = max(40.0, D / 2.0 - max(nw, nh) / 2.0)
        centers = [(cx + r * math.cos(-math.pi / 2.0 + 2.0 * math.pi * i / n),
                    cy + r * math.sin(-math.pi / 2.0 + 2.0 * math.pi * i / n))
                   for i in range(n)]

    node_keys = []
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            step = {"label": str(step)}
        ncx, ncy = centers[i]
        nx, ny = ncx - nw / 2.0, ncy - nh / 2.0
        color = resolve(step.get("color", CYCLE[i % len(CYCLE)]), pal, "primary")
        nkey = "%s.cycle.node%d" % (sid, i)
        out.add("create_shapes", {
            "shape_type": "rounded_square", "x": round(nx, 1), "y": round(ny, 1),
            "width": nw, "height": nh,
            "background_color": tint(color, 0.86), "stroke_color": color, "stroke_size": 2,
        }, nkey, area_key)
        node_keys.append(nkey)
        top = ny + 12
        if step.get("icon") is not None:
            nid, concept = resolve_icon(step["icon"], icon_index)
            if nid is not None:
                out.add("create_icons", {
                    "noun_project_id": nid, "x": round(ncx - ICON_SLOT / 2.0, 1),
                    "y": round(top, 1), "width": ICON_SLOT, "height": ICON_SLOT,
                    "color": color, "tags": [str(concept)] if concept else [],
                }, "%s.icon" % nkey, area_key)
                top += ICON_SLOT + 4
            else:
                out.warn("section %s cycle node%d: icon %r unresolved (run search_icons)"
                         % (sid, i, concept))
        label = step.get("label", "")
        if step.get("n") is not None:
            label = "%s. %s" % (step["n"], label)
        out.add("create_textboxes", {
            "x": round(nx + 10, 1), "y": round(top, 1), "width": round(nw - 20, 1),
            "text": label, "font_size": 14, "bold": True, "font_color": color,
            "text_align": "center",
        }, "%s.label" % nkey, area_key)
        if step.get("desc"):
            out.add("create_textboxes", {
                "x": round(nx + 10, 1), "y": round(top + 22, 1), "width": round(nw - 20, 1),
                "text": step["desc"], "font_size": 11, "text_align": "center",
                "font_color": pal.get("ink", DEFAULT_PALETTE["ink"]),
            }, "%s.desc" % nkey, area_key)

    # REAL connectors around the loop; the closing last->first edge is flagged loop:true.
    for i in range(n):
        j = (i + 1) % n
        extra = {}
        if arrow:
            extra["arrow_type"] = arrow
        if j == 0:
            extra["loop"] = True
        out.connect(node_keys[i], node_keys[j], **extra)


def build_hub(out, sid, block, ix, iy, iw, ih, pal, area_key, icon_index):
    """A saturated center node + N satellite nodes ringed around it + a REAL connector from the
    center to each satellite (center->spoke)."""
    center = block.get("center")
    spokes = block.get("spokes", []) or []
    if not isinstance(center, dict) or not center.get("label"):
        raise ValueError("hub needs a `center` object with a `label`")
    if not spokes:
        raise ValueError("hub has no `spokes`")
    ns = len(spokes)
    D = min(iw, HUB_H)
    cx = ix + iw / 2.0
    cy = iy + D / 2.0

    ccolor = resolve(center.get("color", "accent"), pal, "accent")
    center_key = "%s.hub.center" % sid
    _label_node(out, center_key, area_key,
                cx - HUB_CENTER_W / 2.0, cy - HUB_CENTER_H / 2.0, HUB_CENTER_W, HUB_CENTER_H,
                "rounded_square", ccolor, ccolor, 0,
                center.get("label", ""), contrast(ccolor), 17,
                center.get("icon"), icon_index, "section %s hub center" % sid)

    r = max(70.0, D / 2.0 - HUB_SAT_H / 2.0 - 6)
    for i, sp in enumerate(spokes):
        if not isinstance(sp, dict):
            sp = {"label": str(sp)}
        theta = -math.pi / 2.0 + 2.0 * math.pi * i / ns
        scx, scy = cx + r * math.cos(theta), cy + r * math.sin(theta)
        color = resolve(sp.get("color", CYCLE[i % len(CYCLE)]), pal, "primary")
        skey = "%s.hub.spoke%d" % (sid, i)
        _label_node(out, skey, area_key,
                    scx - HUB_SAT_W / 2.0, scy - HUB_SAT_H / 2.0, HUB_SAT_W, HUB_SAT_H,
                    "rounded_square", tint(color, 0.86), color, 2,
                    sp.get("label", ""), color, 13,
                    sp.get("icon"), icon_index, "section %s hub spoke%d" % (sid, i))
        out.connect(center_key, skey)


def build_timeline(out, sid, block, ix, iy, iw, ih, pal, area_key):
    """A horizontal axis rectangle + one dot per milestone at an evenly-spaced position, with
    label(+`at`+desc) textboxes alternating above/below the axis. No connectors — the axis
    itself carries the sequence (block-catalog.md)."""
    ms = block.get("milestones", []) or []
    n = len(ms)
    if n == 0:
        raise ValueError("timeline has no `milestones`")
    ink = pal.get("ink", DEFAULT_PALETTE["ink"])
    axis_y = iy + min(TIMELINE_H, ih) / 2.0
    out.add("create_shapes", {
        "shape_type": "rectangle", "x": round(ix, 1),
        "y": round(axis_y - TIMELINE_AXIS_H / 2.0, 1), "width": round(iw, 1),
        "height": TIMELINE_AXIS_H, "background_color": MUTED, "stroke_color": MUTED,
        "stroke_size": 0,
    }, "%s.timeline.axis" % sid, area_key)

    r = TIMELINE_DOT / 2.0
    colw = iw / float(n)
    for i, m in enumerate(ms):
        if not isinstance(m, dict):
            m = {"label": str(m)}
        mx = ix + (i + 0.5) / n * iw
        color = resolve(m.get("color", CYCLE[i % len(CYCLE)]), pal, "primary")
        out.add("create_shapes", {
            "shape_type": "ellipse", "x": round(mx - r, 1), "y": round(axis_y - r, 1),
            "width": TIMELINE_DOT, "height": TIMELINE_DOT,
            "background_color": color, "stroke_color": "#FFFFFF", "stroke_size": 2,
        }, "%s.timeline.dot%d" % (sid, i), area_key)
        above = (i % 2 == 0)
        label = m.get("label", "")
        if m.get("at") is not None:
            label = "%s — %s" % (m["at"], label)
        lx = min(max(mx - colw / 2.0, ix), ix + iw - colw)
        label_y = (axis_y - r - 8 - 40) if above else (axis_y + r + 8)
        out.add("create_textboxes", {
            "x": round(lx, 1), "y": round(label_y, 1), "width": round(colw, 1),
            "text": str(label), "font_size": 13, "bold": True, "font_color": color,
            "text_align": "center",
        }, "%s.timeline.label%d" % (sid, i), area_key)
        if m.get("desc"):
            out.add("create_textboxes", {
                "x": round(lx, 1), "y": round(label_y + 20, 1), "width": round(colw, 1),
                "text": str(m["desc"]), "font_size": 11, "font_color": MUTED,
                "text_align": "center",
            }, "%s.timeline.desc%d" % (sid, i), area_key)


def build_swimlane(out, sid, block, ix, iy, iw, ih, pal, area_key):
    """A header row of `cols` labels + one tinted horizontal lane band per lane (label in the
    left gutter) + each item as a box in its (lane, col) cell. No connectors."""
    cols = block.get("cols", []) or []
    lanes = block.get("lanes", []) or []
    if not cols:
        raise ValueError("swimlane has no `cols`")
    if not lanes:
        raise ValueError("swimlane has no `lanes`")
    ncols = len(cols)
    ink = pal.get("ink", DEFAULT_PALETTE["ink"])
    grid_x = ix + SWIM_LABEL_W
    colw = (iw - SWIM_LABEL_W) / float(ncols)

    # column headers (backgrounds first — dark band + contrast label baked in).
    for ci, c in enumerate(cols):
        label = c.get("label", "") if isinstance(c, dict) else str(c)
        out.add("create_shapes", {
            "shape_type": "rectangle", "x": round(grid_x + ci * colw, 1), "y": round(iy, 1),
            "width": round(colw, 1), "height": SWIM_HEADER_H,
            "background_color": ink, "stroke_color": ink, "stroke_size": 0,
            "text": str(label), "font_size": 13, "bold": True,
            "text_align": "center", "font_color": contrast(ink),
        }, "%s.swim.colhead%d" % (sid, ci), area_key)

    ly = iy + SWIM_HEADER_H + SWIM_LANE_GAP
    for li, lane in enumerate(lanes):
        if not isinstance(lane, dict):
            lane = {"label": str(lane)}
        color = resolve(lane.get("color", CYCLE[li % len(CYCLE)]), pal, "primary")
        # tinted lane band spanning the full inner width (label gutter + grid).
        out.add("create_shapes", {
            "shape_type": "rectangle", "x": round(ix, 1), "y": round(ly, 1),
            "width": round(iw, 1), "height": SWIM_LANE_H,
            "background_color": tint(color, 0.92), "stroke_color": tint(color, 0.55),
            "stroke_size": 1,
        }, "%s.swim.lane%d" % (sid, li), area_key)
        out.add("create_textboxes", {
            "x": round(ix + 10, 1), "y": round(ly + SWIM_LANE_H / 2.0 - 12, 1),
            "width": round(SWIM_LABEL_W - 16, 1), "text": str(lane.get("label", "")),
            "font_size": 14, "bold": True, "font_color": color,
        }, "%s.swim.lane%d.label" % (sid, li), area_key)
        # item cells at (lane, col).
        for k, item in enumerate(lane.get("items", []) or []):
            if not isinstance(item, dict):
                item = {"col": 0, "text": str(item)}
            col = int(item.get("col", 0) or 0)
            col = min(max(col, 0), ncols - 1)  # clamp stray indices into the grid
            cx = grid_x + col * colw
            icolor = resolve(item.get("color", lane.get("color", CYCLE[li % len(CYCLE)])),
                             pal, "primary")
            out.add("create_shapes", {
                "shape_type": "rounded_square", "x": round(cx + SWIM_CELL_PAD, 1),
                "y": round(ly + (SWIM_LANE_H - SWIM_ITEM_H) / 2.0, 1),
                "width": round(colw - 2 * SWIM_CELL_PAD, 1), "height": SWIM_ITEM_H,
                "background_color": "#FFFFFF", "stroke_color": icolor, "stroke_size": 2,
                "text": str(item.get("text", "")), "font_size": 12, "text_align": "center",
                "font_color": ink,
            }, "%s.swim.lane%d.item%d" % (sid, li, k), area_key)
        ly += SWIM_LANE_H + SWIM_LANE_GAP


def build_gantt(out, sid, block, ix, iy, iw, ih, pal, area_key):
    """A project schedule on the 0..N fractional scale (N = len(timeUnits)): a left label gutter
    + a top axis of unit labels/gridlines, tinted phase bands per `group` run, a duration bar
    (with an inner `percent` fill) or milestone diamond per task, an optional today line, and
    REAL connectors for each `deps` predecessor->successor (built after all bars exist)."""
    units = block.get("timeUnits", []) or []
    tasks = block.get("tasks", []) or []
    if not units:
        raise ValueError("gantt has no `timeUnits`")
    if not tasks:
        raise ValueError("gantt has no `tasks`")
    N = len(units)
    ntasks = len(tasks)
    ink = pal.get("ink", DEFAULT_PALETTE["ink"])
    plot_x = ix + GANTT_LABEL_W
    plot_w = iw - GANTT_LABEL_W
    colw = plot_w / float(N)
    top = iy + GANTT_AXIS_H
    rows_h = ntasks * GANTT_ROW_H

    # 1) phase bands (backgrounds first): each run of consecutive tasks sharing a `group`.
    gi = 0
    while gi < ntasks:
        g = tasks[gi].get("group") if isinstance(tasks[gi], dict) else None
        gj = gi
        while (gj + 1 < ntasks and isinstance(tasks[gj + 1], dict)
               and tasks[gj + 1].get("group") == g):
            gj += 1
        if g:
            by = top + gi * GANTT_ROW_H
            gcolor = resolve(tasks[gi].get("color", "primary"), pal, "primary")
            out.add("create_shapes", {
                "shape_type": "rectangle", "x": round(ix, 1), "y": round(by, 1),
                "width": round(iw, 1), "height": round((gj - gi + 1) * GANTT_ROW_H, 1),
                "background_color": tint(gcolor, 0.94), "stroke_color": tint(gcolor, 0.8),
                "stroke_size": 1,
            }, "%s.gantt.band%d" % (sid, gi), area_key)
            out.add("create_textboxes", {
                "x": round(ix + 8, 1), "y": round(by + 6, 1), "width": round(GANTT_LABEL_W - 12, 1),
                "text": str(g), "font_size": 11, "bold": True, "font_color": gcolor,
            }, "%s.gantt.bandlabel%d" % (sid, gi), area_key)
        gi = gj + 1

    # 2) axis gridlines (thin — set stroke_color so they don't inherit the dark default border).
    for u in range(N + 1):
        gx = plot_x + u * colw
        out.add("create_shapes", {
            "shape_type": "rectangle", "x": round(gx - 1, 1), "y": round(top, 1),
            "width": 2, "height": round(rows_h, 1),
            "background_color": "#DADCE0", "stroke_color": "#DADCE0", "stroke_size": 0,
        }, "%s.gantt.grid%d" % (sid, u), area_key)

    # 3) axis unit labels (narrow textbox centered over each column).
    for u in range(N):
        out.add("create_textboxes", {
            "x": round(plot_x + u * colw, 1), "y": round(iy + 8, 1), "width": round(colw, 1),
            "text": str(units[u]), "font_size": 12, "bold": True, "font_color": MUTED,
            "text_align": "center",
        }, "%s.gantt.axis%d" % (sid, u), area_key)

    # 4) task rows: gutter label + a bar (start/end) OR a milestone diamond (at + milestone).
    id2key = {}
    for ti, task in enumerate(tasks):
        if not isinstance(task, dict):
            raise ValueError("gantt task %d is not an object" % ti)
        ry = top + ti * GANTT_ROW_H
        color = resolve(task.get("color", CYCLE[ti % len(CYCLE)]), pal, "primary")
        key = "%s.gantt.task%d" % (sid, ti)
        out.add("create_textboxes", {
            "x": round(ix + 8, 1), "y": round(ry + GANTT_ROW_H / 2.0 - 10, 1),
            "width": round(GANTT_LABEL_W - 12, 1), "text": str(task.get("label", "")),
            "font_size": 12, "bold": True, "font_color": ink,
        }, "%s.label" % key, area_key)
        if task.get("id") is not None:
            id2key[str(task["id"])] = key

        is_ms = bool(task.get("milestone")) or (task.get("at") is not None
                                                and task.get("start") is None)
        if is_ms:
            if task.get("at") is None:
                raise ValueError("gantt task %d milestone missing `at`" % ti)
            mcx = plot_x + float(task["at"]) * colw
            out.add("create_shapes", {
                "shape_type": "rhombus_smart", "x": round(mcx - GANTT_MS / 2.0, 1),
                "y": round(ry + (GANTT_ROW_H - GANTT_MS) / 2.0, 1),
                "width": GANTT_MS, "height": GANTT_MS,
                "background_color": color, "stroke_color": color, "stroke_size": 0,
            }, key, area_key)
        else:
            start, end = task.get("start"), task.get("end")
            if start is None or end is None:
                raise ValueError("gantt task %d missing `start`/`end` (or `at`+`milestone`)" % ti)
            start, end = float(start), float(end)
            if end <= start:
                raise ValueError("gantt task %d has end<=start" % ti)
            bx = plot_x + start * colw
            bw = (end - start) * colw
            by = ry + (GANTT_ROW_H - GANTT_BAR_H) / 2.0
            out.add("create_shapes", {
                "shape_type": "rounded_square", "x": round(bx, 1), "y": round(by, 1),
                "width": round(max(4.0, bw), 1), "height": GANTT_BAR_H,
                "background_color": tint(color, 0.6), "stroke_color": color, "stroke_size": 1,
            }, key, area_key)
            pct = task.get("percent")
            if pct is not None:
                fw = max(0.0, min(1.0, float(pct) / 100.0)) * bw
                if fw > 0:
                    out.add("create_shapes", {
                        "shape_type": "rounded_square", "x": round(bx, 1), "y": round(by, 1),
                        "width": round(max(4.0, fw), 1), "height": GANTT_BAR_H,
                        "background_color": color, "stroke_color": color, "stroke_size": 0,
                    }, "%s.pct" % key, area_key)
                out.add("create_textboxes", {
                    "x": round(bx + 6, 1), "y": round(by + GANTT_BAR_H / 2.0 - 8, 1),
                    "width": round(max(30.0, bw - 12), 1), "text": "%s%%" % task["percent"],
                    "font_size": 10, "bold": True, "font_color": contrast(color),
                }, "%s.pctlabel" % key, area_key)

    # 5) today line (both bg + stroke set so it reads red, not a default-bordered hairline).
    if block.get("today") is not None:
        tcolor = resolve("danger", pal, "danger")
        tx = plot_x + float(block["today"]) * colw
        out.add("create_shapes", {
            "shape_type": "rectangle", "x": round(tx - GANTT_TODAY_W / 2.0, 1),
            "y": round(top, 1), "width": GANTT_TODAY_W, "height": round(rows_h, 1),
            "background_color": tcolor, "stroke_color": tcolor, "stroke_size": 0,
        }, "%s.gantt.today" % sid, area_key)
        out.add("create_textboxes", {
            "x": round(tx - 40, 1), "y": round(iy + 8, 1), "width": 80, "text": "Today",
            "font_size": 11, "bold": True, "font_color": tcolor, "text_align": "center",
        }, "%s.gantt.todaylabel" % sid, area_key)

    # 6) dependencies (do last, once every bar/milestone _key exists): REAL connectors
    # predecessor->successor. An unknown dep id would dangle, so raise -> degrade the block.
    for ti, task in enumerate(tasks):
        for dep in (task.get("deps") or []):
            if str(dep) not in id2key:
                raise ValueError("gantt task %d dep %r references an unknown task id"
                                 % (ti, dep))
            out.connect(id2key[str(dep)], "%s.gantt.task%d" % (sid, ti), arrow_type="straight")


def build_tree(out, sid, block, ix, iy, iw, ih, pal, area_key, icon_index):
    """Root node + recursively placed children (below for direction:"down", right for "right"),
    each subtree allocated cross-axis space by its leaf count, with REAL parent->child
    connectors. Children inherit the parent color unless they set their own. Depth capped."""
    root = block.get("root")
    if not isinstance(root, dict) or not root.get("label"):
        raise ValueError("tree has no `root`")
    children = block.get("children", []) or []
    down = block.get("direction", "down") != "right"
    work = dict(root)
    work["children"] = children
    total_leaves, _ = _count_tree(work, 0)
    cross0 = ix if down else iy
    cross1 = (ix + iw) if down else (iy + max(TREE_NODE_H, total_leaves * TREE_ROW_PITCH))
    seq = [0]

    def place(node, depth, lo, hi, parent_key, parent_color):
        key = "%s.tree.n%d" % (sid, seq[0])
        seq[0] += 1
        color = resolve(node.get("color", parent_color), pal, "primary")
        mid = (lo + hi) / 2.0
        if down:
            nx, ny = mid - TREE_NODE_W / 2.0, iy + depth * TREE_LEVEL_PITCH
        else:
            nx, ny = ix + depth * TREE_LEVEL_PITCH, mid - TREE_NODE_H / 2.0
        _label_node(out, key, area_key, nx, ny, TREE_NODE_W, TREE_NODE_H,
                    "rounded_square", tint(color, 0.9), color, 2,
                    node.get("label", ""), color, 13,
                    node.get("icon"), icon_index, "section %s tree node" % sid)
        if parent_key is not None:
            out.connect(parent_key, key)
        ch = node.get("children") or []
        if depth < TREE_MAX_DEPTH and ch:
            total = sum(_count_tree(c, depth + 1)[0] for c in ch if isinstance(c, dict)) or 1
            cursor = lo
            for c in ch:
                if not isinstance(c, dict):
                    continue
                w = (hi - lo) * (_count_tree(c, depth + 1)[0] / float(total))
                place(c, depth + 1, cursor, cursor + w, key, color)
                cursor += w

    place(work, 0, cross0, cross1, None,
          resolve(root.get("color", "accent"), pal, "accent"))


def build_mindmap(out, sid, block, ix, iy, iw, ih, pal, area_key, icon_index):
    """A prominent central root + branches balanced left/right (children fanned beyond each
    branch on the same side) + REAL curved connectors root->branch and branch->child, carrying
    the branch color (stroke_color hint) so the whole sub-tree reads in one color."""
    root = block.get("root")
    if not isinstance(root, dict) or not root.get("label"):
        raise ValueError("mindmap has no `root`")
    branches = block.get("branches", []) or []
    if not branches:
        raise ValueError("mindmap has no `branches`")
    H = ih if ih and ih > MIND_H * 0.5 else MIND_H
    cx = ix + iw / 2.0
    cy = iy + H / 2.0

    root_color = resolve(root.get("color", "accent"), pal, "accent")
    root_key = "%s.mind.root" % sid
    _label_node(out, root_key, area_key,
                cx - MIND_ROOT_W / 2.0, cy - MIND_ROOT_H / 2.0, MIND_ROOT_W, MIND_ROOT_H,
                "rounded_square", root_color, root_color, 0,
                root.get("label", ""), contrast(root_color), 17,
                root.get("icon"), icon_index, "section %s mindmap root" % sid)

    # split branches into right (even index) / left (odd index), preserving order per side.
    sides = {"R": [], "L": []}
    for i, br in enumerate(branches):
        sides["R" if i % 2 == 0 else "L"].append((i, br))
    branch_dx = iw * 0.22
    child_dx = iw * 0.40
    for side, items in sides.items():
        sign = 1.0 if side == "R" else -1.0
        m = len(items)
        for j, (i, br) in enumerate(items):
            if not isinstance(br, dict):
                br = {"label": str(br)}
            bcolor = resolve(br.get("color", CYCLE[i % len(CYCLE)]), pal, "primary")
            by = iy + H * (j + 0.5) / m
            bcx = cx + sign * branch_dx
            bkey = "%s.mind.b%d" % (sid, i)
            _label_node(out, bkey, area_key,
                        bcx - MIND_BRANCH_W / 2.0, by - MIND_BRANCH_H / 2.0,
                        MIND_BRANCH_W, MIND_BRANCH_H, "rounded_square",
                        tint(bcolor, 0.85), bcolor, 2, br.get("label", ""), bcolor, 13,
                        br.get("icon"), icon_index, "section %s mindmap branch%d" % (sid, i))
            out.connect(root_key, bkey, arrow_type="curve", stroke_color=bcolor)
            kids = br.get("children", []) or []
            nk = len(kids)
            for k, child in enumerate(kids):
                if not isinstance(child, dict):
                    child = {"label": str(child)}
                ccy = by + (k - (nk - 1) / 2.0) * MIND_CHILD_PITCH
                ccx = cx + sign * child_dx
                ckey = "%s.mind.b%d.c%d" % (sid, i, k)
                _label_node(out, ckey, area_key,
                            ccx - MIND_CHILD_W / 2.0, ccy - MIND_CHILD_H / 2.0,
                            MIND_CHILD_W, MIND_CHILD_H, "rounded_square",
                            tint(bcolor, 0.92), bcolor, 1, child.get("label", ""), bcolor, 12,
                            child.get("icon"), icon_index,
                            "section %s mindmap branch%d child%d" % (sid, i, k))
                out.connect(bkey, ckey, arrow_type="curve", stroke_color=bcolor)


def build_decision(out, sid, block, ix, iy, iw, ih, pal, area_key):
    """A top-to-bottom flowchart: one node shape per `nodes[]` (kind -> terminator/decision/
    process shape), layered by longest-path rank, + a REAL connector per `edges[]` with the
    edge `label` (Yes/No) as a small textbox at the connector's node-to-node midpoint."""
    nodes = block.get("nodes", []) or []
    edges = block.get("edges", []) or []
    if not nodes:
        raise ValueError("decision has no `nodes`")
    ink = pal.get("ink", DEFAULT_PALETTE["ink"])
    node_by_id = {}
    for nd in nodes:
        if not isinstance(nd, dict) or nd.get("id") is None:
            raise ValueError("decision node missing `id`")
        node_by_id[str(nd["id"])] = nd
    for e in edges:
        if not isinstance(e, dict) or e.get("from") is None or e.get("to") is None:
            raise ValueError("decision edge missing `from`/`to`")
        if str(e["from"]) not in node_by_id or str(e["to"]) not in node_by_id:
            raise ValueError("decision edge references an unknown node id")

    ids = list(node_by_id.keys())
    key_of = {nid: "%s.decision.node%d" % (sid, i) for i, nid in enumerate(ids)}
    rank = _decision_ranks(nodes, edges)
    maxrank = max(rank.values()) if rank else 0
    by_rank = {}
    for nid in ids:
        by_rank.setdefault(rank[nid], []).append(nid)

    # positions: rank -> row (top to bottom), spread each row's nodes evenly across the width.
    pos = {}
    for rk in range(maxrank + 1):
        row = by_rank.get(rk, [])
        k = len(row)
        for j, nid in enumerate(row):
            pcx = ix + iw * (j + 0.5) / k
            pcy = iy + DEC_ROW_PITCH * rk + DEC_NODE_H / 2.0 + 10
            pos[nid] = (pcx, pcy)

    for nid in ids:
        nd = node_by_id[nid]
        shape = DEC_KIND_SHAPE.get(nd.get("kind", "process"), "process")
        color = resolve(nd.get("color", "primary"), pal, "primary")
        pcx, pcy = pos[nid]
        out.add("create_shapes", {
            "shape_type": shape, "x": round(pcx - DEC_NODE_W / 2.0, 1),
            "y": round(pcy - DEC_NODE_H / 2.0, 1), "width": DEC_NODE_W, "height": DEC_NODE_H,
            "background_color": tint(color, 0.85), "stroke_color": color, "stroke_size": 2,
            "text": str(nd.get("label", "")), "font_size": 13, "bold": True,
            "text_align": "center", "font_color": ink,
        }, key_of[nid], area_key)

    for ei, e in enumerate(edges):
        f, t = str(e["from"]), str(e["to"])
        out.connect(key_of[f], key_of[t])
        if e.get("label"):
            fx, fy = pos[f]
            tx, ty = pos[t]
            mx, my = (fx + tx) / 2.0, (fy + ty) / 2.0
            out.add("create_textboxes", {
                "x": round(mx - 40, 1), "y": round(my - 10, 1), "width": 80,
                "text": str(e["label"]), "font_size": 11, "bold": True,
                "font_color": ink, "text_align": "center",
            }, "%s.decision.elabel%d" % (sid, ei), area_key)


# ===========================================================================
# Phase D: nest — a recursively-nested container layout (a box inside a box …).
# Each `box` node becomes an `area` frame (showTitle:false) holding a header
# (bold label in the node color + optional muted meta) + desc + its children
# laid out INSIDE with padding, so children visibly nest inside the parent
# frame. A `callout` node becomes a filled tinted `rounded_square` (a leaf).
# Geometry is measured BOTTOM-UP by the shared _nest_measure (above), so every
# frame fits its children exactly. Backgrounds-first: the area frame is emitted
# BEFORE its header/desc/children (so labels, painted last, land on top).
# Children parent to their ENCLOSING box's area _key, so containment reads both
# geometrically (child rect ⊂ parent rect) and structurally (_parent chain).
# Validation raises ValueError on malformed input so the guarded dispatch
# degrades the block to manual_blocks + a warning with clean rollback.
# ===========================================================================
def _nest_validate(node, depth):
    """Raise ValueError if any RENDERED node is malformed (non-dict, or missing `label`).
    Children past a `callout` or the depth cap aren't rendered, so aren't validated."""
    if not isinstance(node, dict):
        raise ValueError("nest node must be an object (got %s)" % type(node).__name__)
    if not node.get("label"):
        raise ValueError("nest node missing `label`")
    for c in _nest_children(node, depth):
        _nest_validate(c, depth + 1)


def _nest_place(out, sid, node, x, y, w, pal, parent_area_key, depth, seq):
    """Lay one node at (x, y, w) with its bottom-up-measured height; recurse into children.
    Returns the node's height so a stacked (column) parent can advance its cursor."""
    idx = seq[0]
    seq[0] += 1
    nkey = "%s.nest.b%d" % (sid, idx)
    color = resolve(node.get("color", "primary"), pal, "primary")
    ink = pal.get("ink", DEFAULT_PALETTE["ink"])
    inner_w = max(20.0, w - 2 * NEST_PAD_X)
    h = _nest_measure(node, w, depth)
    label = node.get("label", "")
    meta = node.get("meta")
    desc = node.get("desc")
    is_callout = node.get("kind") == "callout"

    # backgrounds first: the box frame (area) or the callout fill (shape), BEFORE header/desc.
    if is_callout:
        # a leaf: filled highlight tint of its color + a colored stroke (a shape, not an area).
        out.add("create_shapes", {
            "shape_type": "rounded_square", "x": round(x, 1), "y": round(y, 1),
            "width": round(w, 1), "height": round(h, 1),
            "background_color": tint(color, 0.80), "stroke_color": color, "stroke_size": 2,
        }, nkey, parent_area_key)
        own_parent = parent_area_key       # callout carries no children; text sits on the shape
    else:
        out.add("create_areas", {
            "x": round(x, 1), "y": round(y, 1), "width": round(w, 1), "height": round(h, 1),
            "title": str(label), "showTitle": False,
        }, nkey, parent_area_key)
        own_parent = nkey                  # this box's children/text parent to its own area

    # header line: bold label in the node color + optional muted meta, right-aligned same line.
    hx = x + NEST_PAD_X
    hy = y + NEST_PAD_TOP
    label_w = inner_w
    if meta:
        meta_w = min(inner_w * 0.5, 10 + len(str(meta)) * 7)
        label_w = max(20.0, inner_w - meta_w - 8)
        out.add("create_textboxes", {
            "x": round(hx + inner_w - meta_w, 1), "y": round(hy, 1), "width": round(meta_w, 1),
            "text": str(meta), "font_size": 12, "italic": True, "font_color": MUTED,
            "text_align": "right",
        }, "%s.meta" % nkey, own_parent)
    out.add("create_textboxes", {
        "x": round(hx, 1), "y": round(hy, 1), "width": round(label_w, 1),
        "text": str(label), "font_size": 15, "bold": True, "font_color": color,
    }, "%s.label" % nkey, own_parent)

    if desc:
        out.add("create_textboxes", {
            "x": round(hx, 1), "y": round(hy + NEST_HEADER_H, 1), "width": round(inner_w, 1),
            "text": str(desc), "font_size": 13, "font_color": ink,
        }, "%s.desc" % nkey, own_parent)

    children = _nest_children(node, depth)
    if is_callout or not children:
        return h

    # children start below the header+desc band, inset by the horizontal padding.
    cy0 = y + NEST_PAD_TOP + NEST_HEADER_H + _nest_desc_h(desc, inner_w)
    cx0 = x + NEST_PAD_X
    if node.get("layout", "column") == "row":
        # side by side, splitting the inner width equally with a gutter between them.
        m = len(children)
        child_w = (inner_w - (m - 1) * NEST_GUTTER) / float(m)
        cxp = cx0
        for c in children:
            _nest_place(out, sid, c, cxp, cy0, child_w, pal, own_parent, depth + 1, seq)
            cxp += child_w + NEST_GUTTER
    else:
        # stacked top-to-bottom with a gap; advance the cursor by each child's own height.
        cyp = cy0
        for c in children:
            ch_h = _nest_place(out, sid, c, cx0, cyp, inner_w, pal, own_parent, depth + 1, seq)
            cyp += ch_h + NEST_GAP
    return h


def build_nest(out, sid, block, ix, iy, iw, ih, pal, area_key):
    """Render the root container node (and its recursive children) into the section frame.
    Validates up front so malformed input raises before anything is emitted (the guarded
    dispatch also rolls back). The root box's height == content_height(block), so it fits the
    section's inner region; nested boxes are strictly contained by construction (padding > 0)."""
    node = block.get("node")
    if not isinstance(node, dict):
        raise ValueError("nest requires a `node` object")
    _nest_validate(node, 0)
    _nest_place(out, sid, node, ix, iy, iw, pal, area_key, 0, [0])


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
                 "table", "flow", "comparison", "chart",
                 "gauge", "pyramid", "funnel", "quadrant", "pillars",
                 "spectrum", "rings", "venn",
                 "cycle", "hub", "timeline", "swimlane", "gantt",
                 "tree", "mindmap", "decision", "nest"):
            # Every builder degrades to manual_blocks + a warning on any failure — a malformed
            # block must never crash the whole board (build_chart also guards internally).
            # Snapshot bucket lengths so a builder that raises AFTER emitting some widgets
            # (some validate mid-layout) is rolled back cleanly: degrading means building
            # NOTHING for the section, never a half-build orphaned behind the manual placeholder.
            # (The area + heading were added before this, so they're preserved.)
            _snap = {k: len(v) for k, v in out.d.items()
                     if k not in ("manual_blocks", "warnings")}
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
                elif t == "gauge":
                    build_gauge(out, sid, block, ix, iy, iw, ih, pal, area_key)
                elif t == "pyramid":
                    build_pyramid(out, sid, block, ix, iy, iw, ih, pal, area_key)
                elif t == "funnel":
                    build_funnel(out, sid, block, ix, iy, iw, ih, pal, area_key)
                elif t == "quadrant":
                    build_quadrant(out, sid, block, ix, iy, iw, ih, pal, area_key)
                elif t == "pillars":
                    build_pillars(out, sid, block, ix, iy, iw, ih, pal, area_key, icon_index)
                elif t == "spectrum":
                    build_spectrum(out, sid, block, ix, iy, iw, ih, pal, area_key)
                elif t == "rings":
                    build_rings(out, sid, block, ix, iy, iw, ih, pal, area_key)
                elif t == "venn":
                    build_venn(out, sid, block, ix, iy, iw, ih, pal, area_key)
                elif t == "cycle":
                    build_cycle(out, sid, block, ix, iy, iw, ih, pal, area_key, icon_index)
                elif t == "hub":
                    build_hub(out, sid, block, ix, iy, iw, ih, pal, area_key, icon_index)
                elif t == "timeline":
                    build_timeline(out, sid, block, ix, iy, iw, ih, pal, area_key)
                elif t == "swimlane":
                    build_swimlane(out, sid, block, ix, iy, iw, ih, pal, area_key)
                elif t == "gantt":
                    build_gantt(out, sid, block, ix, iy, iw, ih, pal, area_key)
                elif t == "tree":
                    build_tree(out, sid, block, ix, iy, iw, ih, pal, area_key, icon_index)
                elif t == "mindmap":
                    build_mindmap(out, sid, block, ix, iy, iw, ih, pal, area_key, icon_index)
                elif t == "decision":
                    build_decision(out, sid, block, ix, iy, iw, ih, pal, area_key)
                elif t == "nest":
                    build_nest(out, sid, block, ix, iy, iw, ih, pal, area_key)
            except Exception as e:
                for _k, _n in _snap.items():
                    del out.d[_k][_n:]  # roll back any widgets emitted before the raise
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
