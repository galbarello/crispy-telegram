---
name: mural-done-signal
description: give participants a way to signal "I'm finished with this activity" that other participants can see — even while the mural is in private mode. Provisions a shared readiness tracker (per-person tokens, a Working→Done lane, a live "N of M done" status) before private mode, then keeps the shared status current during the round. use when someone says "how do people show they're done in private mode", "I need a finished/ready signal", "track who's completed the activity", or "readiness / completion indicator for a workshop".
---

# Mural Done Signal

## Overview

Facilitators run activities in **private mode** so people ideate independently (no groupthink).
The cost: while private mode is on, **nobody can tell who has finished** — the facilitator either
cuts the round short or waits blindly. This skill provisions a **shared readiness tracker** that
lets every participant see who's done, and keeps that signal alive under private mode as far as
Mural's visibility rules allow.

Two moves:

1. **Provision** a shared tracker on the board **before private mode starts** (so its widgets are
   *shared* content, permanently visible to everyone): a Working→Done lane with one labeled token
   per participant, an aggregate status ("4 of 8 finished" + progress bar + per-person ✓), and a
   legend telling people how to signal done.
2. **Reflect** completion during the round using the mechanism that Mural's private mode actually
   permits — selected by a one-time **calibration probe** (below), not assumed.

## The private-mode constraint (read this first)

Private mode is *designed* to hide each person's canvas activity from peers. Confirmed behavior:
during private mode you see **only content you add**; peers' new objects show as **greyed,
contentless outlines**; cursors are greyed/anonymized. **Floating reactions** (😂👏😢👎😮) broadcast
to everyone and bypass the private-content layer.

Therefore **a "done" signal made of *new* canvas content is invisible to peers until reveal.** The
only channels that *might* reach peers live are (a) moving a **pre-existing shared** widget, and
(b) floating reactions. Which of these works — and whether an owner/facilitator MCP connection can
read private done-actions and write shared updates peers see — is **not documented**. Do not
promise live peer visibility until the calibration probe has settled it. Full detail + the probe
procedure: `references/private-mode-behavior.md`.

## Modes (pick via calibration, degrade gracefully)

| Mode | How "done" is signalled | Live peer-visible? | Needs live agent? | Enabled when |
|------|-------------------------|--------------------|-------------------|--------------|
| **A — token drag** | each person drags their shared token Working→Done | yes, directly | no | shared-widget **moves** propagate in private mode (probe S1) |
| **B — agent-reflected** | person signals privately; agent polls + writes the shared status | yes, via the shared status the owner updates | **yes** | owner can **read** private actions (S2) **and** owner's shared **writes** show to peers (S3) |
| **C — reaction ping** | everyone fires an agreed emoji (👏) when done; agent tallies it | yes, but ephemeral/anonymous — no per-person record | yes (to tally) | always (reactions bypass private content) |

**Selection rule:** prefer **A** (simplest, no live agent) → else **B** (needs the skill running
through the session) → else **C** (the honest floor). If only C is available, say plainly that a
persistent, per-person, peer-visible-live tracker isn't achievable through canvas content under
private mode; the tracker still resolves fully at reveal.

## Workflow

### 1. Bootstrap & calibrate
- Confirm a writable board is open and pinned (`select_mural`); read it once (`get_canvas_overview`).
- Check whether the API exposes private mode: inspect `get_mural_info` / `update_mural_settings`
  for a private-mode flag (lets the skill detect/toggle it). Record what you find.
- **Run the calibration probe** in `references/private-mode-behavior.md` (a 2-participant test of
  S1/S2/S3). Skip only if a prior run already recorded the outcome for this workspace. Pick the mode.

### 2. Provision the tracker (before private mode)
- Get the roster (participant names/count) from the user.
- Build the shared tracker from `references/tracker-spec.md` via `mural-image-rebuilder`'s
  primitives-first rules: an `area` (`showTitle:false`) + heading; a two-zone Working/Done lane;
  **one token shape per participant** (labeled, parented to the area); the status block (count +
  progress bar + per-person ✓ row); the legend textbox with the mode-specific instructions.
  Create backgrounds/areas before their contents (newer widgets render on top).
- Screenshot-verify the tracker renders (lanes, tokens, status, legend) **before** the round starts.

### 3. Run the round
- **Mode A:** nothing to run — participants drag their own tokens; the lane *is* the live status.
  Optionally still update the aggregate count from periodic reads.
- **Mode B / C:** run the **reflection loop** — on an interval (≈ every 10–20s, or on request):
  1. `list_widgets` (`view="compact"` for text/state; `view="full"` scoped only when you need token
     geometry) to read token positions / done-actions (B) or read the reaction feed (C).
  2. Compute the aggregate with `scripts/reflect_status.py` (pure function → the `update_widgets`
     payload for the shared status widgets). No extra board round-trips.
  3. `update_widgets` the shared status (count text, progress-bar width, per-person ✓). This is
     **idempotent** — re-writing the same values never double-creates (only `create_*` doubles), so
     the loop is safe to repeat.
  4. Checkpoint-verify every few cycles with one scoped screenshot; don't screenshot every tick.
- Stop the loop when the round ends or private mode is turned off.

### 4. Reveal & hand off
- When the facilitator ends private mode, all private content becomes visible; do a final reflect so
  the shared status matches the revealed board, and report the completion summary.

## Authoring / execution rules
- **Provision before private mode.** Tokens/status must be *shared* content, or peers can't see them.
- **Never fake state with new content during private mode** expecting peers to read it — they'll see
  a blank outline. Move shared widgets or reflect via the owner-updated status instead.
- **One tracker per board.** Don't scatter status widgets; keep the aggregate in one place.
- **Idempotent updates only** in the loop (`update_widgets`), never `create_*` on repeat.
- **Be honest about the mode** in what you tell the facilitator (live vs at-reveal; per-person vs
  anonymous).

## References
- `references/private-mode-behavior.md`: what each channel shows under private mode, the calibration
  probe (S1/S2/S3), the capability→mode decision table, and the API private-mode-flag check.
- `references/tracker-spec.md`: the shared readiness tracker as a board-spec (lane, tokens, status
  block, legend) in the vocabulary shared with `muralize` / `mural-image-rebuilder`.
- `scripts/reflect_status.py`: pure function — `list_widgets` dump + roster → aggregate (N of M,
  per-person state, progress %) + the `update_widgets` payload for the shared status.
