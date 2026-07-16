# Matrix / table fidelity — the concrete recipe

Tables are the most-faked structure in a rebuild. `create_table` renders **empty cells** in this
environment (see the SKILL caveat), so every matrix is built as an **`area` of positioned
cells**. This file is the recipe for making that reconstruction read like the source, not just
carry the text. Follow it whenever the source shows a grid / matrix / comparison table.

**Driven by a muralize `board-spec`?** The fidelity inputs come straight from the spec: each
`columns[]` entry's `color`/`tint` → the per-column header color + column-body tint below; a
leading cell's `badge` + `icon` → the row-label badge + searched icon; `chips` → one chip each.
Apply them exactly as this recipe describes — the spec already carries what an image build has
to infer by eye.

## Layout skeleton (build in this order — backgrounds first, they render underneath)

1. **Container** — one `area` (no title / `showTitle:false`), sized to the whole table. Reserve
   the top ~52px for the header row.
2. **Column tint backgrounds** — one `rectangle` per column, spanning all body rows, filled with
   that column's source color (light tint), thin `stroke` for the cell border. **Match the
   source's per-column fills** — they carry meaning (e.g. the "experiments" column is green, the
   "capabilities" column is coral). Parent each to the area.
3. **Header cells — one colored cell per column, NOT a single banner.** The single most common
   miss. Build the header as one `rectangle` per column, each filled to match **that column's**
   color (a saturated version of the column tint, or the source's header color), with a `title`
   on top in a contrasting color. Only use a single full-width header band if the source actually
   shows one. Header text color must contrast its own cell (white on saturated, dark on light).
4. **Row content** — see cell-type routing below. Fixed row pitch; start row 1 below the header.

## Cell-type routing (match the source's widget count per cell)

| Source cell shows… | Build | Never |
|--------------------|-------|-------|
| A **row of chips / pills / tags** (e.g. 3 experiments) | **one chip shape per chip**, laid out **in the same arrangement as the source** — a row of N across if the source shows a row, sized to **hug its text** (uniform height ~34–40px, width to fit the label), wrapping to a second line only if they overflow the cell | a single full-width chip per line; one `"a · b · c"` string; a sticky |
| A **bulleted list** | one textbox with `\n•` lines | separate widget per bullet |
| **Plain paragraph text** | one textbox | chips |
| **Colored/emphasis text** | a textbox with that `font_color` | plain text |
| The **leading label column** (row header: number + icon + name) | replicate the row-label treatment — a small number **badge** (a `circle`/`ellipse` shape with the digit, or a bold colored number) + a **real searched icon** (see "Leading-column icon treatment" below) + the name textbox, in the tinted label cell | a bare bold string when the source shows a numbered/iconned badge; a mismatched emoji in place of the source's icon |

**Chip sizing rule.** A chip hugs its content — do not stretch one chip across the whole cell,
and do not collapse a multi-chip cell into one bar. If the source shows 3 chips in a row, the
board shows 3 chip widgets in a row. The chip *count* is fidelity; the arrangement is fidelity;
a joined string loses both. Use a wide-not-tall shape (`rounded_square` or `rectangle` with
`width > height`) so it reads as a pill, not a square.

## Leading-column icon treatment

When the leading label column shows a small **icon / pictogram** beside each row's number and
name (a common infographic pattern), reproduce it with a **real searched icon** — never an emoji
or a bare glyph — following `references/icon-matching.md`:

- Name each distinct row pictogram as a search term, `search_icons`, inspect the previews, then
  `create_icons` **tinted to the row/column color** so the column reads as one icon family.
- Keep one consistent slot for every row: **badge → icon → name** in a row (icon ~20–28px,
  vertically centered on the badge), or the icon centered above the name — whichever the source
  uses. Use the *same* arrangement for all rows.
- Reuse an icon id when the same pictogram repeats; search once per distinct concept, not per row.
- Create the icon **after** the tinted label cell so it sits on top, and screenshot-verify it
  landed inside the cell (icons can nudge on create) — read it back with the child-widget
  screenshot, not just the API response.
- Fallback only if no icon matches: a simple tinted shape glyph, and **say so**. Do not
  substitute a mismatched emoji, and do not mix real icons on some rows with emoji on others.
- This is the same icon strategy the rest of the board uses — pick one approach per board and
  apply it to the table's row labels too, so the table doesn't look off from the sections around
  it.

## Row rhythm

- Fixed row pitch (content height + padding); align every column's cell to the same row baseline.
- If the source shows separators, add a thin full-width `rectangle` (1–2px, light) between rows,
  or alternate very-light row fills. Skip if columns are already tinted and the source has no
  visible row lines.
- Keep vertical padding consistent so the tallest cell in a row sets the pitch (bulleted cells
  and chip-stacks are usually the tallest — size the row to them).

## Verify (Layer 6, applied to the table)

- Screenshot the **child cells/chips** (pass their ids — the area renders as an empty frame), and
  read the text off the image. Confirm: every populated cell shows text; **every multi-chip cell
  has the same chip count as the source**; header cells are colored per column.
- Cross-check `list_widgets` (`view="compact"`) `text_content` for each cell — non-empty there +
  blank on screen = render lag, not a miss; do **not** recreate (you'll duplicate).
- Diff the chip count per cell against the source's Pass-A manifest.
