# Probe and adapt — the hybrid discovery loop

Mural paints widgets to a `<canvas>`, so the DOM is nearly opaque. Before touching the
board, spend one probe cycle discovering what the in-page Mural client exposes. What you
find decides, **per capability**, whether you take the fast internals path or the resilient
UI path. When in doubt, degrade to UI — it always works, it's just slower and pixel-bound.

**Nothing you discover here replaces visual verification.** Even when you drive the board
through internals, confirm the result on a screenshot. Internals can silently no-op, mutate
a detached copy, or lag the render.

## Step 1 — Scan for exposed internals

Run a read-only probe with `javascript_tool` and report back a plain-JSON summary (never
dump huge objects — enumerate keys and types). Look for:

- **Global handles on `window`** — anything Mural-ish: `window.app`, `window.store`,
  `window.mural`, `window.__MURAL__`, `window.__APP__`, Redux/MobX/Zustand stores, or a
  debug/SDK object. Enumerate own keys and flag promising ones.
- **The canvas root's framework instance** — find the main `<canvas>` (or its React root
  container) and walk for a React fiber (`__reactFiber$…` / `__reactProps$…` keys) or a
  framework component instance that holds board state or action dispatchers.
- **A message channel** — a `postMessage`/`BroadcastChannel`/websocket the client uses,
  which may accept scripted commands.
- **Global helpers** — functions like `createWidget`, `getWidgets`, `setText`,
  `getViewport`/`getZoom` hanging off any discovered object.

Example shape of a probe (adapt to what you see — do not assume these names exist):

```js
// returns a small JSON summary, NOT the live objects
const out = { windowKeys: [], canvasFound: false, fiberKeys: [], candidates: [] };
out.windowKeys = Object.keys(window).filter(k => /mural|app|store|board|canvas|sdk/i.test(k));
const c = document.querySelector('canvas');
out.canvasFound = !!c;
if (c) {
  const host = c.closest('[id],[class]') || c.parentElement;
  out.fiberKeys = host ? Object.keys(host).filter(k => /^__react/i.test(k)) : [];
}
JSON.stringify(out);
```

Then drill into whichever handles look real, listing their method names, to see if any
support the three capabilities below.

## Step 2 — Build the capability map

Decide each capability independently — they can resolve to different paths:

| Capability | Internals path (use if a reliable call exists) | UI fallback |
|------------|-----------------------------------------------|-------------|
| **Create at exact board coords** | call the client's create/add API, or dispatch scripted pointer events at computed pixels | `operations.md` → Create |
| **Read widget list / counts / text** | read the store / call a `getWidgets`-style accessor; use only to plan and cross-check | screenshot (authoritative for text) |
| **Set / replace text** | call a set-text API on a widget id | `operations.md` → Edit text |
| **Read viewport (pan/zoom)** | call a `getViewport`/`getZoom` accessor → exact transform | empirical reference-widget calibration (`coordinate-mapping.md`) |

A capability counts as "internals" **only if** you verified it actually works on a throwaway
probe widget and the change showed up on a screenshot. An accessor that reads state is safe;
a mutator you haven't confirmed is not — treat it as UI until proven.

## Step 3 — Dispatching scripted events (when internals allow input but no clean API)

If there's no create/set API but the canvas listens to standard input, you can construct and
`dispatchEvent(...)` synthetic `PointerEvent` / `MouseEvent` / `KeyboardEvent` / `WheelEvent`
on the canvas at computed client pixels. This is more precise than `computer` drags but is
brittle (frameworks may require trusted events, correct `pointerId`/`buttons`, or a full
down→move→up sequence). Treat it as a middle tier: prefer a real API if found; prefer
`computer` coordinate actions if synthetic events don't take. Always screenshot-verify.

## Step 4 — Graceful degradation

If the probe finds nothing usable, proceed **entirely on the UI path** — that is the
designed fallback, not a failure. Note in your working notes that no internals were found so
later steps don't re-probe needlessly. Re-probe only if the page reloads or you suspect the
client version changed.
