# Retro section guide — labels, descriptions, and header treatment

Reusable copy and layout for building or refreshing a retro/workshop board. The recycler
**keeps** this scaffold when it empties a board; this file is the source of truth for what a
good, tidy section header looks like when you build or repair one.

## Header treatment (per section)

Each section reads top-to-bottom as **tinted icon → bold label → one-line muted description**,
sitting **directly above its sticky grid** (never stranded off to the side with a big gap):

- **Icon** — a color-coded sticker for the section (Start green, Stop red, Continue amber),
  ~80px, at the grid's left column x. Icons are stickers: to move/recolor one you must
  delete + recreate (recover its `noun_project_id` from `get_widget_by_id.name`).
- **Label** — the bold section word, just right of the icon.
- **Description** — one muted line (`#6b6480`, ~16px) beneath the label.

Keep all sections' grids on **one shared column set** so they align (snap any drift with
`update_widgets`; it's idempotent and safe). Add a **grouping/affinity area** to the side for
clustering stickies by topic. Keep the header out of the tight band gaps — anchor it above the
first row with ~40px clearance.

## Start / Stop / Continue

- **▶ Start** (green) — *things we should begin doing*
  > New things worth trying — practices, tools, or experiments that would make us better.
- **✋ Stop** (red) — *things that aren't working*
  > Habits, processes, or drains that aren't working — let's drop them.
- **⟳ Continue** (amber) — *things worth keeping*
  > What's working well — keep doing it and double down.

Fuller prompt variants (use as a small block beside a band when you want guiding questions):
- **Start** — What new practices/tools are worth trying? What would remove a pain point? What
  have we meant to try but haven't?
- **Stop** — What's slowing us down or adding friction? What isn't delivering value? What feels
  wasteful or redundant?
- **Continue** — What went well that we should protect? What's worth making a habit? Where do we
  double down?

## Other common frameworks (starter copy)

- **4Ls** — Liked / Learned / Lacked / Longed for.
- **Mad / Sad / Glad** — what frustrated us / disappointed us / pleased us.
- **Sailboat** — Wind (what pushes us forward) / Anchors (what holds us back) / Rocks (risks
  ahead) / Island (the goal).

For any framework: give each section a **distinct sticky color** (the recycler keys bands by
color — see `retro-template-spec.md`), put the header above its grid, and include a grouping
area for topic clustering.
