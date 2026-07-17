# Mural brand palette — the default baseline for muralize

The **default** `meta.palette` for every muralize board is the **Mural brand palette**, pulled
from mural.co's own design tokens. Use it unless the user asks for a different theme or the
source content dictates other colors. Blocks still reference **roles** (`"color": "primary"`),
never raw hex — this file just fixes what those roles resolve to.

## Role baseline (what each semantic role resolves to)

| Role | Hex | Mural token |
|------|-----|-------------|
| `primary` | `#195AD7` | indigo |
| `accent` | `#8728E6` | violet |
| `success` | `#00C27A` | jade (Mural's CTA green) |
| `warning` | `#FFAA00` | mural-yellow |
| `danger` | `#FF4B4B` | mural-red |
| `surface` | `#F0F0F0` | lightgrey (matches the site's light card ground; `#EDEDDB` natural is the optional warm-cream alternative) |
| `ink` | `#202124` | near-black (brand text) |
| *(muted text)* | `#666666` | text-muted |
| *(hairline border)* | `#DCE1E5` | cool-grey |

Contrast (verified against the live render): dark `ink` text passes AA on white and `surface`.
On **filled** `success`/jade and `warning` swatches use **dark `ink` text, not white** — mural.co
itself puts **black** text on its green CTA. `primary`/`accent`/`danger` fills take white text
fine.

## Ready-to-inline CSS variables (Layer 5 HTML)

Muralize renders self-contained HTML (no external stylesheet), so inline these custom properties
in the artifact's `:root` and drive every color from them:

```css
:root{
  /* semantic roles */
  --primary:#195AD7; --accent:#8728E6; --success:#00C27A;
  --warning:#FFAA00; --danger:#FF4B4B; --surface:#F0F0F0; --ink:#202124;
  --muted:#666666; --border:#DCE1E5;

  /* full Mural brand token library — for chart series, chips, and secondary accents */
  --mural-blue:#5887FF; --indigo:#195AD7; --violet:#8728E6; --grape:#BE53FF;
  --jade:#00C27A; --mural-green:#00843F; --spring:#8FEC7F; --mint:#B4F5C8;
  --mural-red:#FF4B4B; --burgundy:#C8056E; --orange:#ED6000;
  --mural-yellow:#FFAA00; --lemon:#FFE146; --canary:#FFED87;
  --mural-pink:#FC83FF; --flamingo:#FF98B4; --blush:#FFCEE0;
  --sky:#79C1FF; --ice:#BED7FF; --lavender:#E6BFFF; --natural:#EDEDDB;
}
```

For light **column tints / card bodies**, use a brand token at ~12–18% (8-digit alpha hex, e.g.
`#195AD71F`) rather than inventing pastels — this matches how the Mural board rebuilds tints.

## Full brand token library (for multi-series charts, chips, secondary accents)

Mural's identity is deliberately **multi-color** (the rainbow "Mural" logo on a black hero, with
a green primary action). When a block needs more than the 7 roles — e.g. a 3–5 series line chart,
a chip cloud, or a distribution — draw from these instead of arbitrary hex, so it stays on-brand:

- **Blues/purples:** mural-blue `#5887FF` · indigo `#195AD7` · violet `#8728E6` · grape `#BE53FF`
  · sky `#79C1FF` · ice `#BED7FF` · lavender `#E6BFFF`
- **Greens:** jade `#00C27A` · mural-green `#00843F` · spring `#8FEC7F` · mint `#B4F5C8`
- **Warm/reds:** mural-red `#FF4B4B` · burgundy `#C8056E` · orange `#ED6000`
- **Yellows:** mural-yellow `#FFAA00` · lemon `#FFE146` · canary `#FFED87`
- **Pinks:** mural-pink `#FC83FF` · flamingo `#FF98B4` · blush `#FFCEE0`
- **Neutrals:** natural `#EDEDDB` · cool-grey `#DCE1E5` · grey `#8C8C8C` · muted `#666666`

Suggested **chart-series order** (max contrast, on-brand): `#195AD7` → `#00C27A` → `#FFAA00` →
`#FF4B4B` → `#8728E6` → `#79C1FF`.

## Notes

- **Green is the action color.** Mural's primary CTA is green (jade); reserve `success`/jade for
  positive/complete states and prominent "go" emphasis, and use `primary` (indigo) as the
  dominant structural accent.
- **Optional dark hero.** mural.co leads with a **black** hero (`#0B0B0B`-ish) and the multi-color
  logo. For a bold header band, a dark hero with white title + a brand-color eyebrow is on-brand;
  keep body sections on light `surface`/white for readability.
- **Verified against the live render (mural.co):** the primary CTA is jade `rgb(0,194,122)` =
  `#00C27A` with **black** text; the page background is white with cool-grey `#DCE1E5` borders and
  light-grey card grounds; the wordmark uses mural-red, mural-blue, mural-green and mural-pink —
  all confirmed present in the token library above.
- Source: mural.co CSS design tokens + live-rendered element sampling.
