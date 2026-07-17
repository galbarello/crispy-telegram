# HTML infographic quality — make the artifact, not a board preview

The muralize HTML is a **first-class deliverable**, not a low-fi preview of the Mural board.
It runs in a real browser, so it is **NOT bound by Mural-primitive limits** — the single biggest
quality lever. The board approximates (no arc/wedge, rotated-rectangle "lines", no gradients); the
**HTML must not** — draw real SVG arcs, gradients, area fills, shadows. Same `board-spec`, same
verbatim content and palette **roles** (see `brand-palette.md`), but the HTML render aims for a
polished, dense, productized dashboard. Follow the `artifact-design` skill for craft.

## Design baseline (build on the brand tokens)

Inline the brand `:root` variables from `brand-palette.md`, then add scales so spacing/type/depth
are systematic, not ad-hoc:

```css
:root{
  /* type scale (1.25) */   --f-eyebrow:12px; --f-body:14.5px; --f-h3:17px; --f-h2:22px; --f-h1:clamp(30px,4.6vw,52px);
  /* spacing scale (4px) */ --s1:4px; --s2:8px; --s3:12px; --s4:16px; --s5:24px; --s6:32px; --s7:48px;
  /* radii + elevation */   --r:14px; --r-sm:9px;
  --shadow-sm:0 1px 2px rgba(20,19,40,.05);
  --shadow:0 1px 2px rgba(20,19,40,.05),0 8px 24px -12px rgba(60,40,120,.16);
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,Roboto,Helvetica,Arial,sans-serif;
  --mono:ui-monospace,"SF Mono","JetBrains Mono",Menlo,Consolas,monospace;
}
```
- **Type**: one scale, `text-wrap:balance` on headings, body ≤ 65ch, uppercase mono eyebrows with
  letter-spacing. **`font-variant-numeric:tabular-nums`** on every number in tiles/tables/charts.
- **Depth**: panels get `--shadow`; hover-lift interactive cards a touch. Borders are 1px in the
  cool-grey token.
- **Both themes**: define tokens under `@media(prefers-color-scheme:dark)` **and**
  `:root[data-theme=…]` (the artifact toggle must win). Give dark its own chart colors.

## Charts — real SVG (this is where the quality gap lives)

Do **not** port the board's chart hacks. Render true SVG, driven by the spec's data:

- **`chart` pie/donut** → a real **SVG donut**: one `<circle>` per slice with `stroke-dasharray`
  = `sliceLen circumference-sliceLen` and a rotated `stroke-dashoffset`, thick `stroke`, no fill;
  a centered total/label; a legend with value + %. (The board can only do a stacked bar — the HTML
  should show the actual ring the source shows.)
- **`gauge`** → an SVG **semicircular arc**: a track `<path>` arc + a value arc to
  `value/(max-min)` in the active zone color + a centered `value``unit`. Real arc, not a meter bar.
- **`chart` line** → a real **`<polyline>`** per series (never rotated rectangles) with: a faint
  gridline set, y-axis ticks, x categories, marker dots, a **subtle area fill** under the primary
  series (`<polygon>` or `<path>` with a `linearGradient` fading to transparent), and a legend.
- **`chart` bar** → `<rect>`s with rounded tops, value labels above, category axis; grouped/one
  color per series with a legend.
- **KPI / stat tiles** → big tabular-nums value in the accent, a small muted label above, an
  optional caption/delta below; on a white/`surface` card with a hairline border.

Always keep value labels (the numbers are the fidelity). Compute geometry from
`categories`/`series`/`slices`/`value` — never hardcode a bar height or slice angle.

## Density & dashboard layout

Match the source's information density. For dashboard-pattern boards, use a **multi-column CSS
grid** with tight gutters (`--s4`) and pack regions like the reference: a header band, a
KPI/benchmark tile row, a chart, a data table + a donut side-by-side, content panels, and a
footer strip of insight cards. A dense, balanced grid reads as "productized"; one-idea-per-huge-
section reads as a slide. Keep columns aligned and gutters even.

## Iconography

Use **one consistent inline-SVG line-icon set** — 24×24 viewBox, `fill:none`,
`stroke:currentColor`, `stroke-width:2`, round caps/joins — sized per context (18–22px in tiles,
28–34px in cards) and colored via `currentColor`/role. Never mix hand-drawn one-offs with emoji;
pick the set once and reuse. A tinted rounded-square tile behind a white icon is the default
card/KPI treatment.

## Quality checklist (before publishing the artifact)

- [ ] Charts are **real SVG** (donut is an actual ring, line is a real polyline w/ area fill,
      gauge is an arc) — not the board's stacked-bar / rotated-rectangle approximations.
- [ ] One type scale + one spacing scale used throughout; numbers use `tabular-nums`.
- [ ] Panels have consistent radius + elevation; borders are the hairline cool-grey token.
- [ ] One icon set, consistent stroke/size; no emoji-for-icons.
- [ ] Density matches the source (dashboard = dense multi-column grid, aligned).
- [ ] Both light and dark render well (toggle wins over the media query); AA contrast — dark
      `ink` text on `success`/`warning` fills (per `brand-palette.md`).
- [ ] Body text ≤ ~65ch; headings `text-wrap:balance`; nothing scrolls sideways.
- [ ] The HTML looks like a shippable product page, not a wireframe of the board.
