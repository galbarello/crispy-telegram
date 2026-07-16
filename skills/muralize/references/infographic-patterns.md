# Infographic patterns — choosing and laying out from a brainstorm

Use the SAME dominant-pattern taxonomy as `mural-image-rebuilder` so the two skills align.
Pick the pattern that matches the *shape of the thinking* in the conversation, then map the
harvested themes onto that pattern's blocks.

## How to choose

| The conversation is mostly about… | Pattern | Signature blocks |
|-----------------------------------|---------|------------------|
| A sequence, process, or how something progresses over stages | `timeline` | `flow` (steps or loop) |
| A project plan / delivery schedule — task durations & dependencies over time | `timeline` | `gantt` |
| Comparing options / scoring items across dimensions | `matrix` | `table` |
| Metrics, status, "how are we doing" | `dashboard` | `metrics`, `cards`, `banner` |
| A belief system, bets, pillars, or an operating model | `strategy-framework` | `banner`, `flow`, `table`, `cards`, `callout` |
| Several of the above | `mixed` | choose the dominant; embed others as sections |

Both boards you've built are `strategy-framework` (mixed): a headline belief, a validation
flow, ranked-assumption tables, capability card-lists, a decision framework, and metric tiles.

## Metaphor catalog — pick by the *relationship* between the ideas

A dense strategy infographic is a stack of **visual metaphors**, each chosen because it matches
the relationship the content has. Don't default everything to cards + bullets — ask "what IS
this?" and pick the metaphor, which maps to a `board-spec` block (schema in `board-spec.md`).

**Sequence & progression** — order matters, one direction:
- **Flow / steps** — a process A→B→C. → `flow`.
- **Chevron journey** — numbered stages along a maturity/complexity axis (a "customer journey",
  "crawl→walk→run"). → `flow` with `shape:"step"` (interlocking chevrons) + an axis caption.
- **Pipeline / stage-flow** — stages that each hold a titled bullet-box, arrows between (a
  "KPI framework: Learning→Adoption→Transformation→Outcomes"). → `flow` with `desc`/bullets per step.
- **Timeline** — dated/positioned milestones on a continuous axis. → `timeline`.
- **Funnel** — stages that narrow (conversion, drop-off). → `funnel`.
- **Swimlane / roadmap** — items across **lanes** (workstreams/actors) × **columns** (time,
  phases, now-next-later). → `swimlane`.
- **Gantt / schedule** — tasks with **durations** on a time axis (bars from start→end), often
  with phases, % progress, milestones, and dependencies (a project or delivery plan). Distinct
  from `timeline` (point milestones) and `swimlane` (categorical cells, no durations). → `gantt`.
- **Decision / branching flow** — a process with **yes/no gates** and branches (not linear). →
  `decision`.

**Cycle & reinforcement** — it loops back:
- **Cycle / loop** — a process that repeats ("hypothesize→experiment→evidence→decide→…"). →
  `cycle` (`style:"loop"`). This is the "evidence loop" metaphor — NOT a linear flow.
- **Flywheel** — a self-reinforcing loop where each turn accelerates the next. → `cycle`
  (`style:"flywheel"`).

**Comparison & contrast**:
- **Versus / two paths** — two eras/options/approaches side by side ("Old Way vs New Way"). →
  `comparison` (+ a `callout` for the key difference).
- **Quadrant / 2×2** — items positioned by two axes (impact×effort, reach×confidence). →
  `quadrant`.
- **Matrix / scorecard** — many items scored across the same dimensions (a real data grid). →
  `table` (per-column colors + chips + row-label badges/icons).

**Hierarchy & structure**:
- **Pyramid / layered stack** — layers where breadth = scope (vision→strategy→execution). → `pyramid`.
- **Pillars / foundation** — columns that hold up a capstone ("these capabilities power X"). → `pillars`.
- **Hub & spoke** — one core with satellites feeding it (a platform + its inputs). → `hub`.
- **Tree / mind-map** — multi-level parent→child branching (org chart, work breakdown,
  decomposition). → `tree`.
- **Rings / onion / bullseye** — nested layers around a core (product→platform→ecosystem) or
  priority rings. → `rings`.

**Sets & overlap**:
- **Venn** — two or three sets whose **intersection** is the point (desirable ∩ feasible ∩
  viable). → `venn`.

**Parallel peers** — several items, no order:
- **Cards** — repeated titled items (frameworks, principles, capabilities). → `cards`.
- **Metric tiles** — labeled measures. → `metrics`.
- **Chips / tag cloud** — short peer labels with no flow (things to falsify, forces at play,
  candidate options). → `chips`.

**Quantified & positioning**: **gauge** (one bounded number on a scale) → `gauge`; **chart**
(compare values / trend / part-to-whole) → `chart` (bar/line/pie); **spectrum** (a qualitative
position between two poles — build↔buy, low↔high maturity) → `spectrum`.

**Emphasis / framing**: **banner** (full-width statement) → `banner`; **callout** (highlighted
aside, "Key Difference") → `callout`; and the **header/hero** (eyebrow → title → subtitle → tags)
lives in `meta`.

## Composing a dense strategy infographic (like the reference boards)

A rich board is many metaphors in reading order, not one big grid. A typical strategy layout:

1. **Header/hero** (`meta`) + a row of 2–3 **vision/principle cards** (`cards`).
2. **The core idea** — a short **flow** of the evolution, with a **callout** for the hypothesis.
3. **The journey** — a **chevron flow** across a maturity axis.
4. **The method** — an **evidence `cycle`** (loop), and the assumptions to test as **chips** +
   a research **flow**.
5. **What we'll learn** — the **matrix `table`**.
6. **The shift** — a **`comparison`** (old vs new) + a **callout** for the key difference.
7. **The measures** — a KPI **pipeline flow** and/or **metrics**/**gauge**/**chart**.
8. **The foundation** — **`pillars`** (capabilities) supporting the strategy.
9. **Footer** — a **principle strip** (`cards`, icon+title+desc row) or a closing **banner**.

Match the metaphor to each cluster; vary them so the board reads as a designed system, not a
wall of bullets. Every metaphor block still obeys the fidelity rules below (verbatim text,
exact counts, color-by-role).

## Layout heuristics

- **Header band** first: title + subtitle, optional 2–3 vision/principle cards.
- **One idea per section**; give each a heading and a grid cell. Left-to-right, top-to-bottom
  reading order = array order in the spec.
- **Group by relationship**: things that flow → a `flow`; things that compare → a `table`;
  repeated parallel items → `cards`.
- **Reserve a heading band** at the top of each section (the rebuilder needs ~30px clear).
- **Balance density**: a dense strategy look is the goal, but keep columns aligned and gutters
  consistent.
- **Footer band**: a closing commitment / one-liner, often a dark `banner`.

## Turning brainstorm content into blocks

- Sticky-note clusters → `cards` items or `table` rows.
- A "how we work" / lifecycle discussion → a `flow` (mark `loop:true` if it cycles).
- Ranked or scored lists ("impact vs confidence", "effort vs value") → a `table` with
  `coloredText` cells for the ratings.
- Decision rules ("when do we scale/pivot/kill") → a `cards` or three `callout`s.
- KPIs / success measures → `metrics`.
- A single number read against a scale ("87% cache hit rate", "health 8/10", "62% capacity")
  → a `gauge` (dial/meter). Reach for it when the *position on a min–max range* is the point
  (with red/amber/green `zones`); use a plain `metrics` tile when the raw number stands alone.
- Comparing values across categories or series → a `chart`: **bar** for category comparison,
  **line** for a trend over time (one line per series), **pie** for part-to-whole (few slices).
  Use a chart only when the group produced actual numbers — never invent data to fill one; if
  the shape is qualitative, prefer a `table` or `cards`.
- A guiding statement → a `banner` or `callout`.

## Fidelity from a conversation

- Keep participants' wording for headlines and key phrases; condense supporting text.
- Preserve the *count* of items the group produced (e.g. 10 assumptions → 10 rows), don't
  round or trim silently.
- If a section is thin because the brainstorm didn't cover it, mark items `"draft": true` and
  tell the user what's missing — never pad with invented content.
- Color-code by meaning that emerged in the conversation (e.g. confidence high/med/low →
  success/warning/danger roles), not arbitrarily.
