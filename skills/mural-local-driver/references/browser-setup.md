# Browser setup — claude-in-chrome prerequisites

This skill acts entirely through the `claude-in-chrome` browser automation, which drives the
user's **real, logged-in Chrome session** (pages open as tabs in that session, not a
separate or headless browser). That is exactly what "manipulate the open Mural board 100%
locally" requires — but it comes with hard preconditions. Check them before any action.

## Load the tools

Browser tools are deferred; load the set you need in **one** batched `ToolSearch` call:

```
ToolSearch with query "select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__computer,mcp__claude-in-chrome__read_page,mcp__claude-in-chrome__javascript_tool"
```

Add `read_console_messages` / `read_network_requests` only if you end up debugging the page.
Do not load tools one at a time.

Tools you will use most:

- `tabs_context_mcp` — read the list of open tabs; find and target the Mural board tab.
- `computer` — coordinate mouse/keyboard: `left_click`, `right_click`, `double_click`,
  `middle_click`, `left_click_drag`, `type`, `scroll`. Screenshots come back from the
  page/viewport capture as image blocks.
- `javascript_tool` — run arbitrary JavaScript in the page. This is the lever for probing
  Mural internals and dispatching scripted events (see `probe-and-adapt.md`).
- `read_page` — reads the page; near-useless for widget state on a canvas app, but fine for
  chrome/menus and confirming URL/title.
- `navigate` — only if you must (re)open the board URL; prefer acting on the existing tab.

## Preconditions (fail loudly if unmet)

1. **Extension installed & enabled for this session.** The `claude-in-chrome` Chrome
   extension must be present and browser tools enabled. If not, tell the user to run
   `/chrome` (or restart Claude Code for the one-time enable prompt). Landing page:
   `https://claude.ai/chrome`.
2. **Mural domain pre-permissioned.** `claude-in-chrome` gates actions per domain. The
   user must allow-list the Mural app domain in the extension. A denial surfaces as
   "Claude in Chrome is denied on `<domain>`" / `domain_rule_denied`; the first action on a
   new domain triggers a `chrome_permission_prompt`.
3. **Not in bypass-permissions mode.** Browser tools are **unavailable** when the session
   auto-allows tool calls (`bypassPermissions`). If you're in that mode, browser automation
   will not run — tell the user to switch modes.
4. **A writable board is open.** Confirm via `tabs_context_mcp` that a Mural board tab is
   open, its URL is an editable board (not a viewer/embed/read-only share), and the user is
   signed in as an editor.

## Failure modes and how they present

- **`computer` is a single-holder lock.** "Computer use is in use by another Claude
  session." Only one session can drive the mouse/keyboard at a time; the user can press
  `Esc` / `Ctrl+C` to abort. Expect an on-screen "Claude is using your computer" banner.
- **Dead bridge.** "bridge-failed" / "disabled after repeated failures — restart to retry"
  means the extension connection dropped. Read-only fallbacks (`WebFetch`/`WebSearch`) do
  not help for a live board; the fix is reconnecting the extension
  (`https://clau.de/chrome/reconnect`) or restarting.
- **Managed-policy block.** An org's managed settings can deny the MCP server entirely — no
  override; report it and stop.
- **No Chromium browser detected** → the skill is unavailable.

## Targeting rule

Always act on the **tab the user already has open**. Do not spawn a fresh tab or navigate
away — that would leave their board and act on the wrong context. Use `tabs_context_mcp` to
pin the correct tab, and re-read it if a subsequent action reports it lost the target.
