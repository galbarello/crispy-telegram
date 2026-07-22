# Performance spec — faster Mural board builds

Design record for speeding up board construction via the `mural-image-rebuilder` and `muralize`
skills. Maintainer doc (not deployed by `install.sh`); the *actionable* rules live in the skill
files noted below.

## Problem

Builds are model-driven and slow. A real build this session — a 5-column strategy infographic —
cost:

- **~14+ separate `create_*` calls** (shapes split 4-5 ways, textboxes ~6 ways, plus titles /
  icons / connectors). Each call is a **serialized round-trip through the browser bridge**, so
  wall-clock is dominated by call count.
- **~17 `search_icons` calls** returning heavy base64 previews — the dominant token sink.
- **Several full-board `get_canvas_image` screenshots** mid-build — heavy, mostly redundant.

A prior direct-API / local-browser "fast driver" was **built and discarded** — the MCP is the
fastest backend (memory `mural-fast-driver-verdict`). So every lever here optimizes **within MCP
usage**; no new backend.

## Levers (ranked by speedup ÷ effort)

| # | Lever | Type | Effort | Speedup |
|---|-------|------|--------|---------|
| 1 | Maximal batching (≤1 create per type) | docs | S | High — ~14 → ~6 calls |
| 2 | Icon concept→id registry + pre-resolution | data + docs | S | High — ~17 → ~0 searches |
| 3 | Verification budget (geometry diffs; 1 final screenshot) | docs | S | Medium |
| 4 | `compile_board.py` — spec→payload compiler, core blocks | code | M | High — kills hand-coords |
| 5 | Compiler Phase B (table, flow/comparison + connector handshake) | code | M | Med-High |
| 6 | Compiler Phase C (metaphor blocks) | code | L | Low (demand-driven) |

## Sprint 1 (shipped — docs/data, no new executable)

### 1. Maximal batching
One `create_*` call per widget TYPE per board, fixed order `create_areas → create_titles →
create_shapes → create_icons → create_textboxes → create_connectors`; each list ordered
**backgrounds-first**; ~80-widget size cap; connectors last.
→ `skills/mural-image-rebuilder/SKILL.md` ("Maximal batching" section), `references/rebuild-workflow.md`.

**Z-order validation experiment — RESULT: CONFIRMED.** Three overlapping opaque rects created in
one `create_shapes` call as `[red, green, blue]` landed with `stackingOrder` red=169 < green=170
< blue=171 → **last item in the list renders on top**. So a single batched call with backgrounds
first reproduces z-order; no need to split background vs foreground calls.

**Secondary finding — response array order is unreliable.** The create response's `shapes`/ids
array came back *reversed* vs input (`response[0]` = blue = input[2]). **Map returned ids to
widgets by the returned `position_x`/`position_y`, not by array index** — critical when wiring
connectors. If a fallback for z-order had been needed (it wasn't), it would be a single
idempotent `update_widgets` setting `stackingOrder` per id.

### 2. Icon registry
`skills/mural-image-rebuilder/references/icon-registry.json` — verified `concept → noun_project_id`
map (with aliases/notes), seeded from the ~19 vetted ids previously prose-only in
`icon-matching.md`. Consulted as **step 0** of the matching loop (skip `search_icons` on a hit).
muralize **pre-resolves** each icon concept into the board-spec's `icon.noun_project_id`, so the
rebuilder searches for nothing known.
→ `icon-registry.json` (new), `references/icon-matching.md`, `muralize/SKILL.md`.

### 3. Verification budget
0 full-board screenshots mid-build; geometry via `list_widgets` bbox diffs; content via
`list_widgets` `text_content`; dedup via `get_canvas_overview` count; **exactly one
`get_canvas_image` at the end**.
→ `skills/mural-image-rebuilder/SKILL.md` (Layer 6), `references/rebuild-workflow.md`.

## Sprint 2 — `scripts/compile_board.py` (Phase A SHIPPED)

Deterministic board-spec → batched create-payload compiler, mirroring `line_chart.py`'s output
contract (one JSON object keyed by create tool, backgrounds-first). Reuses `line_chart.py` /
`pie_chart.py` for `chart` blocks via their importable `build()` cores.

- **CLI:** `python3 compile_board.py <spec.json> --palette <palette.json> --icons references/icon-registry.json`
  (spec also accepted on stdin). Output keyed `create_areas/create_titles/create_shapes/
  create_icons/create_textboxes/connectors/manual_blocks/warnings`; every widget carries a `_key`,
  and content nested in a section frame also carries a `_parent` (top-level items — the `meta.*`
  header and the area frames — have no `_parent`).
- **Connector handshake:** each widget gets a stable logical `_key`; `connectors` reference keys;
  the build wrapper maps `_key → returned id` **by `position_x/y`** (never by array index — see the
  response-order finding) after each create batch, then issues one `create_connectors` call.
- **Phase A — SHIPPED:** `meta` header, `section`, `banner`, `callout`, `cards`, `metrics`,
  `chips`, and `chart` (line/pie via the scripts).
- **Phase B — SHIPPED:** `table` (area-nested chips + textboxes per `table-fidelity.md` — colored
  per-column headers, tinted bodies, chip/bullet/badge cells), `flow` (step nodes + real
  connectors, closing the cycle on `loop:true`), `comparison` (stacked columns + intra-column
  connectors), and `chart chartType:"bar"` (new sibling `bar_chart.py`, grouped multi-series).
  This is the first real use of the connector handshake — validated that every emitted connector's
  `from`/`to` `_key` exists among the emitted widgets. Broken sub-builders degrade to
  `manual_blocks` + a warning (exit 0), like line/pie.
- **Phase C (deferred, L, demand-driven):** the remaining metaphor blocks (`gauge`, `cycle`,
  `pyramid`, `funnel`, `quadrant`, `pillars`, `hub`, `timeline`, `swimlane`, `gantt`, `tree`,
  `mindmap`, `venn`, `spectrum`, `decision`, `rings`) — where the model's fidelity judgment matters
  most; do NOT build speculatively.
- **Graceful degradation:** uncovered block types pass through as `manual_blocks` (with `{section,
  type,reason,box}`); unresolved icons drop to `warnings[]` without failing the block. Treat
  compiler output as a tweakable starting payload, not a frozen board.
- **Known limitation:** height estimation is heuristic (char-count wrapping, fixed tile/chip
  pitch), so long body text can overflow a tile — spot-check compiled geometry once in Layer 6.
  A section whose content uses an unexpected shape (e.g. a `blocks` list instead of the schema's
  singular `block`) is silently skipped — validate specs against `board-spec.md`.

## Risks

- **z-order assumption** — de-risked (experiment confirmed); `stackingOrder`-patch fallback exists.
- **Over-batching** — one giant `create_*` may hit a payload cap and amplifies the bridge
  double-apply bug → ~80-widget cap + mandatory post-batch dedup.
- **Compiler drift vs fidelity** — scope the compiler to deterministic geometry; keep metaphors
  model-driven.
- **Registry staleness** — verified-only entries + fall-through to `search_icons` keeps it safe.
