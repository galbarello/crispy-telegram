# Private mode — what's visible, and how to signal "done" through it

The feasibility of every "done" mechanism hinges on Mural's private-mode visibility rules. This
file records what is **confirmed** from Mural's docs, what is **unknown** (and must be tested), and
the **calibration probe** that settles it.

## Confirmed behavior (Mural docs + facilitation guides)

- Private mode is a facilitator toggle for independent ideation ("avoid groupthink").
- During private mode, **you see only the content you add.** Peers' newly-added objects render as
  **greyed, contentless outlines** — you can tell activity is happening, not *what* it is.
- Cursors are **greyed / anonymized** during private mode.
- **Floating reactions** (😂 👏 😢 👎 😮) are a broadcast overlay — they float across everyone's
  screen and are **not** canvas content, so they are **not** subject to private-content hiding.
- When the facilitator **ends** private mode, all content added during the session becomes visible
  to everyone (optionally with authors kept anonymous).

**Direct corollary:** a "done" signal built from *new canvas content* (a fresh "DONE" sticky, a new
checkmark) is **invisible to peers until reveal** — they'd see a blank outline. Rule that out.

Sources: support.mural.co "Private mode", "Express yourself with Reactions", "Introduction to
facilitation".

## Unknown — must be tested (this decides the mode)

Docs do **not** specify:

- **S1 — shared-widget moves:** if a widget existed on the board (shared) *before* private mode, and
  someone **moves** it during private mode, do peers see the move live? (Likely privatized too,
  since a move of already-visible content would otherwise leak intent — but unconfirmed.)
- **S2 — owner reads of private actions:** can an owner/facilitator connection (the MCP session)
  **read** a participant's private done-action via `list_widgets` / `get_widget_by_id` while private
  mode is on?
- **S3 — owner shared writes:** when the owner **updates a shared widget** via MCP during private
  mode, do peers see that update live?

## Calibration probe (run once per workspace; record the result at the bottom)

Needs **two sessions**: the owner (this MCP connection) + a second participant (a colleague, or a
second account/browser). Turn **private mode ON**, then:

1. **S1 — move visibility.** Before enabling private mode, owner creates a shared token shape.
   Enable private mode. Participant-2 drags that token to a new spot. → *Does the owner (or another
   peer) see the token move live?* YES ⇒ **Mode A** is available.
2. **S2 — owner read.** With private mode on, participant-2 performs a private done-action (drags
   their own token / drops a sticky in their private slot). Owner runs `list_widgets`
   (`view="full"`, scoped to the tracker area). → *Does the owner see participant-2's action
   (new/moved widget, updated position)?* YES ⇒ S2 passes.
3. **S3 — owner write.** With private mode still on, owner `update_widgets` a shared status widget
   (e.g. change its text to "TEST"). → *Does participant-2 see the change live?* YES ⇒ S3 passes.
   S2 **and** S3 ⇒ **Mode B** is available.
4. If S1 fails **and** (S2 or S3) fails ⇒ fall back to **Mode C** (floating reactions).

### Capability → mode

| S1 (moves show) | S2 (owner reads) | S3 (owner writes show) | Mode |
|:---:|:---:|:---:|------|
| ✅ | – | – | **A** (token drag — simplest, no live agent) |
| ❌/? | ✅ | ✅ | **B** (agent-reflected shared status) |
| ❌ | ❌ or ❌ | | **C** (reaction ping — ephemeral floor) |

Prefer A → B → C. If both A and B are available, choose A (no live agent required).

## API private-mode flag check (do at bootstrap)

Before the probe, inspect what the MCP exposes so the skill can detect/automate private mode:

- `get_mural_info` — check the returned settings/metadata for a private-mode field.
- `update_mural_settings` — check whether private mode is a settable property (lets the skill toggle
  it for the probe and detect when a facilitator turns it on/off).

If the API neither reports nor toggles private mode, the skill runs against the human-driven toggle
and relies on the facilitator to tell it when the round is private. Record findings here.

## Recorded outcome (fill in after first live run)

- Date / workspace: _pending first live calibration_
- API exposes private-mode flag: _unknown_
- S1 / S2 / S3: _untested_
- **Selected default mode:** _pending_ (until then, provision the tracker and default to the safest
  available: A if confirmed, else B if the agent is live, else C).
