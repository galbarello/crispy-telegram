# Data-viz (product) palette — the alternative theme for muralize

The **second** muralize theme, harvested from Mural's **product design system** (the internal UI
Toolkit → *Patterns · Data visualization*), not the marketing site. It is **not the default** — the
mural.co **brand** theme (`references/brand-palette.md`) is. Select this theme (`meta.theme:
"product"`) when the board is a **dashboard / analytics / data-heavy** view, or when the user asks
for the "product", "UI Toolkit", or "data-viz" look. See the theme-selection rule in `SKILL.md`
(Layer 3) — **default is `brand`; prompt the user when it's ambiguous.**

> Why a separate theme: the brand palette is saturated marketing color (indigo/jade/violet). The
> product data-viz palette is a **muted 9-hue categorical scale** tuned for chart legibility and
> accessible contrast. The design system explicitly says to use the **secondary palette for data
> values** and to reserve **system colors** for success/error/warning — so the two don't mix.

## Categorical data-series scale (the "60" range) — use IN ORDER

For any categorical encoding (chart series, chips, distributions, cycle/pillar accents), assign
colors in this documented order — it is the maximum-distinction ordering the design system ships:

| # | Name | Hex (60) | Token |
|---|------|----------|-------|
| 1 | Truffle | `#6C7F79` | `mrl-truffle-60` (grey-green) |
| 2 | Mint | `#2496BC` | `mrl-mint-60` (teal) |
| 3 | Dragonfruit | `#C464BA` | `mrl-dragonfruit-60` (magenta) |
| 4 | Melon | `#5DA03B` | `mrl-melon-60` (green) |
| 5 | Tomato | `#E0484D` | `mrl-tomato-60` (red) |
| 6 | Lemon | `#B69E23` | `mrl-lemon-60` (mustard) |
| 7 | Orange | `#E5791A` | `mrl-orange-60` (orange) |
| 8 | Blueberry | `#5B83D2` | `mrl-blueberry-60` (blue) |
| 9 | Grape | `#846CE0` | `mrl-grape-60` (violet) |

Rule of thumb from the toolkit: **use the 60 value and above** for the data marks themselves; use
the lighter steps (10–40) for fills/tints/gridlines and the darker steps (70–100) for text-on-tint.

## Semantic role baseline (what each role resolves to under `theme:"product"`)

Structural roles map to muted data-viz hues; **system roles keep the system colors** (the toolkit
says: *"for system-level communication (success, errors, warning), continue to use our system
colors"* — so these match the brand theme and are **not** drawn from the categorical scale):

| Role | Hex | Source |
|------|-----|--------|
| `primary` | `#5B83D2` | Blueberry 60 (structural accent) |
| `accent` | `#846CE0` | Grape 60 |
| `success` | `#00C27A` | **system** green (unchanged from brand) |
| `warning` | `#FFAA00` | **system** yellow (unchanged) |
| `danger` | `#FF4B4B` | **system** red (unchanged) |
| `surface` | `#F7F7F7` | product light ground (data-table fill) |
| `ink` | `#202124` | near-black text |
| *(muted text)* | `#666666` | text-muted |
| *(hairline border)* | `#DCE1E5` | cool-grey |

Contrast targets (from the toolkit, enforce these): **≥3:1** for non-text visuals vs their
background, **≥4.5:1** for text. The 60-range hues on white all clear 3:1; put **dark `ink` text**
on any light tint (10–40) and on filled `warning`, white text on filled 60–90 marks.

## Full token ladders (for sequential scales, tints & text-on-tint)

Each hue ships 10→100 (light→dark) plus a `desaturated` step. Use a single hue's ladder for a
**sequential** scale, two hues' ladders back-to-back for a **diverging** scale, and the 10–20 steps
for card/column tints.

```
blueberry   10 #D7E4FF · 20 #CADBFC · 30 #BBD1FB · 40 #8BAFF9 · 50 #6992E2 · 60 #5B83D2 · 70 #406ECB · 80 #2059CA · 90 #1C4DAF · 100 #184295 · desat #ADC7E0
dragonfruit 10 #FFE1F3 · 20 #F6D5F3 · 30 #E6BCE2 · 40 #D897D1 · 50 #CA72C1 · 60 #C464BA · 70 #BA4AAB · 80 #AF4BA8 · 90 #A3439D · 100 #8D3A88 · desat #E8C9DD
grape       10 #DEDCF9 · 20 #D8D8F9 · 30 #CFCFF7 · 40 #A2A3F0 · 50 #8E81E4 · 60 #846CE0 · 70 #7256DB · 80 #5E3ED6 · 90 #4A3AB6 · 100 #3F319B · desat #BDBBDD
lemon       10 #FAF1C1 · 20 #F9F0BE · 30 #F9EDAE · 40 #F5E27F · 50 #E4CB49 · 60 #B69E23 · 70 #8E7417 · 80 #846C15 · 90 #7A6310 · 100 #68540D · desat #E4D795
melon       10 #E3F8D8 · 20 #D6EDCA · 30 #BEE2AB · 40 #A1D687 · 50 #7AB95B · 60 #5DA03B · 70 #4B842E · 80 #45792A · 90 #477231 · 100 #3C6029 · desat #A9D0B2
mint        10 #DCF2F9 · 20 #CFEAF2 · 30 #B1D9E7 · 40 #8AC7DB · 50 #59B5D4 · 60 #2496BC · 70 #097EA5 · 80 #08769B · 90 #017298 · 100 #016384 · desat #A2CBD8
orange      10 #FFE7CC · 20 #FEE2C2 · 30 #FCDAC0 · 40 #F5C792 · 50 #F49E48 · 60 #E5791A · 70 #C94F13 · 80 #BF4C12 · 90 #B24401 · 100 #933901 · desat #EBBA8E
tomato      10 #FBE0DF · 20 #FDD8D8 · 30 #F6C1C2 · 40 #F09497 · 50 #E36367 · 60 #E0484D · 70 #D43A40 · 80 #CD2D33 · 90 #BE2730 · 100 #9D2028 · desat #E5B3B6
truffle     10 #ECEFEE · 20 #DBE1DF · 30 #C5CECB · 40 #AAB6B2 · 50 #839590 · 60 #6C7F79 · 70 #60716C · 80 #50625D · 90 #46534F · 100 #38423F · desat #C4CAC8
```

## Ready-to-inline CSS variables (Layer 5 HTML, `theme:"product"`)

```css
:root{
  /* semantic roles */
  --primary:#5B83D2; --accent:#846CE0; --success:#00C27A;
  --warning:#FFAA00; --danger:#FF4B4B; --surface:#F7F7F7; --ink:#202124;
  --muted:#666666; --border:#DCE1E5;

  /* categorical data-series scale (assign in this order) */
  --dv-1:#6C7F79; --dv-2:#2496BC; --dv-3:#C464BA; --dv-4:#5DA03B; --dv-5:#E0484D;
  --dv-6:#B69E23; --dv-7:#E5791A; --dv-8:#5B83D2; --dv-9:#846CE0;
}
```

Chart-series order (product theme): `--dv-1` → `--dv-2` → … → `--dv-9`, i.e.
`#6C7F79 → #2496BC → #C464BA → #5DA03B → #E0484D → #B69E23 → #E5791A → #5B83D2 → #846CE0`.

## Non-color guidelines (apply under this theme; several help the brand theme too)

**Type treatments**
- Titles/hero: a serif display face is *page-titles only* (the toolkit uses "STK Bureau"); since the
  webfont isn't embeddable, approximate with the artifact's display face and keep it to the title.
  **This serif is HTML-only.** The Mural board renders *only* Proxima Nova — an unknown `fontFamily`
  is stored but silently falls back (see mural-image-rebuilder's font note), so a themed board keeps
  its title in Proxima Nova and leans on the sentence-case + left-align rules below instead. Don't
  promise a serif on the board; only the HTML render can honor it.
- Everything else — metrics, data points, axis/legend/chart labels — a **sans-serif** for number
  legibility (the toolkit uses "ABC Social"). **Left-align**, **sentence case**, always.
- **Numbers:** comma for thousands (`1,256`); **no** superscript for `%`/`$`; **no** `k`/`m`
  abbreviations. Use `tabular-nums` so digits align in columns.

**Metrics** — large number + label for the primary metric on a page; small number inside compact
surfaces (tooltips, tiles). Optional trailing change-indicator (▲/▼ + %) or a badge (`↑ 1% monthly`).

**Legends** — pair color with a second cue (line style / marker shape) so series are distinguishable
without color (accessibility); use a compact grid legend for long series lists; position the legend
by chart type (top/right for lines, under the plot for bars).

**Section layout & rhythm** — favor **spacing + single-line dividers over containers** to cut visual
noise: **2px** divider between major sections, **1px** within a section/component. Use containers
*sparingly* to call out a related metric group. Keep consistent vertical rhythm; use **bold** inline
text (not boxes) to create hierarchy in simple bulleted lists.

## Re-theming an existing board in place (brand ⇄ product)

You can retheme an already-built Mural board without rebuilding it — `update_widgets` recolors are
**idempotent and safe from the create double-apply bug**, so batch them freely. Recipe:

- **Map the categorical families in ORDER** to the data-viz scale (family 1 → Truffle, 2 → Mint,
  3 → Dragonfruit, …), and apply the *same* mapping consistently across every place a family
  appears (columns, flow steps, metrics) so the board reads as one system.
- **Fills/marks use the 60 step; colored TEXT uses the 70–90 step** for AA contrast (the 60 hues
  pass ≥3:1 as marks but fail as text). Set `background`+`strokeColor` on shapes, `color` on text.
- **Keep system colors as system meaning** — a "don't/negative" marker stays `danger`, an
  "our choice/positive" highlight stays `success`; don't repaint them into categorical hues.
- **Icons must be delete + recreate** (stickers can't be `update_widgets`-ed) — recover each
  `noun_project_id` from `get_widget_by_id.name`, then `create_icons` in the new tint.
- Verify the whole board after; the widget count must be unchanged (deletes == recreates).

## Notes

- **Never mix the two themes on one board.** Pick `brand` or `product` for the whole spec.
- Under `product`, data marks come from the **categorical scale**; `success`/`warning`/`danger`
  stay **system** colors and mean system state, not data — don't press Melon/Tomato into service as
  "good/bad" when a semantic role is meant.
- Source: Mural UI Toolkit → *Patterns · Data visualization* + the *Color* token page
  (`mrl-*-60` etc.), fetched via the connected design-system (zeroheight) source of truth.
