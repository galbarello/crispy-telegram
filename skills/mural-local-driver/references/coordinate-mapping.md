# Coordinate mapping — board coords ↔ screen pixels

On the UI path, every action is a pixel on the screen, but the board reasons in **board
coordinates** that pan and zoom independently of the window. Getting this transform right is
the single biggest determinant of whether UI-driven placement lands where you intend. If the
probe exposed the viewport (pan/zoom), use that and skip the empirical steps.

## The transform

```
pixel = origin_px + (board − pan) · zoom
board = pan + (pixel − origin_px) / zoom
```

- `zoom` — board units per… actually screen pixels per board unit (Mural's zoom factor).
- `pan` — the board coordinate currently at the canvas's top-left.
- `origin_px` — the screen pixel of the canvas's top-left (account for toolbars/panels; it
  is **not** `(0,0)` of the window).

## Step 1 — Normalize the view

Before placing anything, put the view in a **known, stable** state so the transform doesn't
drift under you:

- Set a round zoom (e.g. 100%) via Mural's zoom control, or use **fit-to-screen** to frame
  the working region. Discover the exact control/shortcut from the in-app `?` panel.
- Pan so the region you're about to edit is fully inside the viewport with margin — never
  work against the viewport edge (see hazards below).

## Step 2 — Recover the transform

**Preferred (internals):** if the probe found a viewport accessor, read `pan` and `zoom`
directly, and measure `origin_px` once from the canvas element's bounding rect via
`javascript_tool` (`canvas.getBoundingClientRect()`).

**Empirical (pure UI):** calibrate with a reference widget.

1. Create one throwaway widget at a **known** board coord (or read an existing widget's
   board coord if a read accessor exists).
2. Screenshot and read the widget's pixel position (e.g. its top-left) off the image.
3. Repeat with a second widget at a different known board coord.
4. Solve for `zoom` and `origin_px − pan·zoom` from the two (board, pixel) pairs (do it
   separately for x and y). Two points suffice; a third is a good sanity check.
5. Delete the throwaway widget(s).

Once solved, compute the pixel for any target board coord — and verify the first real
placement lands where predicted before trusting the calibration for the rest.

## Step 3 — Re-derive after any change

Any pan, zoom, fit, or window resize **invalidates** the transform. Re-derive (or re-read
the viewport) after each. Prefer to finish all work in one region at one zoom, then
deliberately pan/zoom to the next region and recalibrate, rather than nudging the view
mid-operation.

## Hazards

- **Edge-of-viewport auto-pan.** Dragging a widget to or past the viewport edge makes Mural
  auto-scroll, so the drop lands somewhere unexpected. Keep both the drag start and end well
  inside the viewport; move the view first if the destination is off-screen.
- **Scroll = zoom or pan.** In Mural, wheel/trackpad gestures pan or zoom the canvas
  (modifier-dependent). Use `computer` `scroll` intentionally and re-derive the transform
  afterward; don't let an incidental scroll go unnoticed.
- **Momentum / smoothing.** Fast programmatic drags can undershoot. If a drop misses,
  screenshot, read the actual landing pixel, and correct with a second short drag.
- **Device pixel ratio.** On HiDPI displays, screenshot pixels may differ from CSS pixels.
  Calibrate from the screenshot you'll actually read, so the ratio cancels out.
