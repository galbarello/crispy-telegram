# Icon matching — reproduce the source's pictograms, don't default to emoji

When the source shows pictograms/logos/icons (telescope, people, flask, target, shield,
rocket, grid, magnifying glass…), match them with real icons rather than substituting
mismatched emoji — emoji read as noticeably lower fidelity.

## Decide ONE icon strategy per board, up front

- **Real icons (default when fidelity matters):** `search_icons` per distinct pictogram,
  pick by preview, `create_icons`, tint to match.
- **Emoji fallback (fast, low fidelity):** a single emoji approach for all icons. Use only
  when icons are incidental or search returns nothing usable — and say you're doing it.
- **Never mix** real icons and emoji on the same board (the routing table already says this).
- **Icons on a repeated family are all-or-none.** If one item in a repeated family (KPI/metric
  tiles, cards, steps) gets an icon, they all must — the same rule as "tint all cells or none."
  A build that deprioritizes icons tends to skip one family (seen for real: the outcome-metric
  tiles were left icon-less while the header and flow nodes had icons, which reads as unfinished).
  When you finish, scan every repeated family and confirm the icon count matches the item count.

## Matching loop (real icons)

0. **Check `references/icon-registry.json` FIRST.** It's a machine-readable `concept →
   noun_project_id` map of verified icons (also keyed by `aliases`). If the pictogram (or an
   alias) is there, use its id directly and **skip `search_icons` entirely** — this removes the
   biggest token sink. Only search for concepts absent from the registry; when a fresh search
   yields a clean, verified match, add it to the registry for next time. (When building from a
   muralize board-spec, icons arrive pre-resolved with `noun_project_id` already — no lookup or
   search needed at all.)
1. **Name each distinct pictogram** from what it depicts — that's the search term:
   "telescope", "people group", "line chart", "target", "shield", "rocket", "flask",
   "magnifying glass". Dedupe: if the same pictogram repeats, search once and reuse the id.
2. **`search_icons(term)`** → results carry `id`, `tags`, and `preview_data_url` (a base64
   PNG). **Inspect the preview image** and pick the closest visual match; if
   `preview_failed` is true, judge by `tags`. This is the probe — you're comparing
   candidates to the source crop before committing.
   - **The query is a hint, not a guarantee — results are often off-topic.** Observed:
     "shield security" returned a padlock and a greeting card; "bar graph statistics"
     returned a beer glass and a flow-chart. Always look at the previews; if nothing fits,
     re-search with a synonym ("shield protection", "analytics") before settling.
3. **`create_icons`** in one batch: `{noun_project_id, x, y, width, height, color, tags,
   parent_id}` (`parent_id` nests the icon in its card/panel area so it moves with it).
   - `color`: hex tint to match the source's icon color (monochrome Noun Project icons
     tint cleanly).
   - Keep one consistent icon size across a family; center each in its container.
   - **Icon-in-a-tile composition (the standard for card/KPI/panel icons).** Build the tile
     first (it renders under), then the icon on top. Two looks:
     - **Solid tile + white icon (highest fidelity — matches most infographic icons):** a
       `rounded_square` filled with the family's **accent color** and a **white** (`#FFFFFF`)
       icon centered on it. Sizes that read well: a ~50px tile with a ~30px icon; a ~34px
       tile with a ~22px icon.
     - **Light tile + accent icon:** a pale-tint tile with the icon tinted the accent color —
       softer; use when the source's tiles are pale.
   - **Never use an emoji glyph as the icon** (e.g. a `☁`/`</>` inside a shape) when fidelity
     matters — it's the low-fi fallback, not the target. Real searched icons are the default.
4. **Verify visually:** `get_widgets_screenshot` the placed icons and compare to the source.
   If a match is weak, try an alternate search term or the next page and swap the id.
   - Screenshot the **icon id alone**, not together with its background shape/circle — in a
     composite the shape can occlude the icon and make a rendered icon look missing. (The
     icon still renders on the live canvas, since the newest widget stacks on top.)

## Retrofit: upgrading a board's placeholder icons to real icons

When a board was already built with emoji tiles or shape placeholders and you're raising
fidelity, upgrade **in place** — don't rebuild the board:

- **Emoji-in-a-tile → solid tile + real icon:** `update_widgets` the existing tile shape to
  `{background: <accent>, strokeColor: <accent>, text: ""}` (recolors it and drops the emoji),
  then `create_icons` a white icon centered on it. This edits, so it doesn't duplicate — and
  clearing the emoji via `text: ""` avoids a glyph showing through behind the icon.
- **Shape-placeholder illustration (e.g. a hero built from rectangles/ellipses) → real icons:**
  `delete_widget` the placeholder shapes, then `create_icons` the real ones (laptop, gear,
  database, …) tinted, arranged in the same footprint. Deleting (not hiding) keeps the widget
  list clean.
- Run the **dedup check** afterward (`get_canvas_overview` count vs intended) — a retrofit adds
  icons and removes placeholders, so confirm the net matches.

## Icons are stickers — you can't `update_widgets` them; delete + recreate

`update_widgets` works on shapes, text, titles, stickies, areas, and arrows — **not on icon
(sticker) widgets**. There is no in-place edit to move, resize, or recolor an existing icon:
**`delete_widget` it and `create_icons` a fresh one** at the target x/y/size/tint. Recover the
pictogram first from `get_widget_by_id` — the `noun_project_id` is the widget's **`name`** field
(e.g. `"name": "3203554"`) — so the replacement is the same icon. (This is exactly why the
retrofit above recolors the *tile* with `update_widgets` but always **creates** the icon.)
Delete + recreate is a `create_*`, so run the Layer-6 twin/dedup check afterward.

## Search quality is poor for technical/product concepts — preview, and keep a shortlist

Dev/infra terms miss badly. Observed: "event hub" → a target/crosshair; "cloud" and "snapshot" →
rain/hail clouds (id `30027` is a *hail* cloud); "share nodes" → scissors; "source code" → a
printer. Always inspect previews and re-query with synonyms. Replacements that did land cleanly,
as a starting shortlist: **camera** `76991`, **gears/automation** `7695754`, **plain cloud**
`294810`, **mesh-network nodes** `3794128`. Never ship an icon whose meaning differs from the
source just because the search surfaced it.

More vetted ids (verified good on a strategy-infographic build): **target/bullseye** `7002`,
**cube/box** `25152`, **star** `5603`, **lightbulb** `762`, **magnifying glass** `9873`,
**flask** `8372205`, **analytics/chart** `32220` (search "analytics dashboard", **not** "bar
chart" — that returns a beer glass), **rocket** `36778`, **trophy** `2362859`, **gauge/
speedometer** `1686371`, **stacked layers/blocks** `1209962`, **recycle** `60`, **steps-up /
advancing levels** `3910` (good for "maturity/level" metrics), **refresh/rotate** `72176`
(good for "agility/change"), **user/person** `7078`.

## Cost discipline

Each `search_icons` call returns several base64 previews and is token-heavy. Search **once
per distinct pictogram**, not once per instance, and reuse ids for repeats. Batch all the
`create_icons` placements into a single call.

## When no good icon exists

Fall back to the closest icon, or to a single emoji strategy — and note it explicitly as a
fidelity compromise. Don't pick an icon whose meaning differs from the source's just because
it's visually similar.
