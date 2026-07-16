# Mural Skills Pack

Companion [Claude Code](https://claude.com/claude-code) skills for going from raw
ideas or images to a real Mural board.

| Skill | What it does |
|-------|--------------|
| **muralize** | Turns a brainstorm or conversation into a shareable, self-contained HTML infographic **and** a structured `board-spec` that `mural-image-rebuilder` can build into a Mural board losslessly (no OCR). |
| **mural-image-rebuilder** | Reconstructs a Mural from a screenshot or reference image — extracting widget-level structure, layout hierarchy, text, and visual patterns (timelines, matrices, dashboards, strategy frameworks). |
| **mural-local-driver** | Manipulates an **already-open** Mural board **100% locally** through the browser (`claude-in-chrome`) — no Mural API or MCP. Create/edit/move widgets and read board state, probing in-page internals when available and falling back to pixel-accurate automation. Doubles as the local execution backend for `mural-image-rebuilder`. |
| **mural-retro-recycler** | Produces a fresh, empty copy of a recurring retro/workshop board for the next cycle — duplicate the mural, then clear sticky text, snap stickies back to their home grid, and delete everything participants added, while preserving the template scaffold (title, headers, icons, prompts, empty grids, grouping areas). |

`muralize` produces the `board-spec`, and `mural-image-rebuilder` consumes it to build the
board — via the Mural MCP, or via `mural-local-driver` when only a local browser tab is
available.

## Contents

```
mural-skills-pack/
├── .claude-plugin/
│   ├── plugin.json          # Claude Code plugin manifest
│   └── marketplace.json     # lets the folder be added as a plugin marketplace
├── skills/
│   ├── muralize/
│   ├── mural-image-rebuilder/
│   ├── mural-local-driver/
│   └── mural-retro-recycler/
├── install.sh               # copy skills into a Claude Code skills dir
└── README.md
```

## Install

Pick whichever fits how you distribute skills.

### Option A — install script (simplest)

```bash
# user-wide: ~/.claude/skills
./install.sh

# or project-scoped: <dir>/.claude/skills
./install.sh --project /path/to/your/project

# remove them again
./install.sh --uninstall
```

Restart Claude Code (or run `/doctor`) afterward so the skills are picked up.

### Option B — Claude Code plugin

From Claude Code, add this folder as a plugin marketplace, then install the plugin:

```
/plugin marketplace add /path/to/mural-skills-pack
/plugin install mural-skills-pack@mural-skills
```

### Option C — manual copy

Copy the folders under `skills/` into any Claude Code skills directory
(`~/.claude/skills/` for user scope, or `<project>/.claude/skills/` for a project).

## Verify

In Claude Code, the skills should appear as `/muralize`,
`/mural-image-rebuilder`, `/mural-local-driver`, and `/mural-retro-recycler`. Try:

- "muralize this conversation into an infographic and board-spec"
- "rebuild this mural from the attached screenshot"
- "add a sticky to my open mural board" (local driver)
- "duplicate this retro and clear it for next sprint" (retro recycler)

## Requirements

- Claude Code with skills enabled.
- `mural-image-rebuilder` executes best against a live Mural board via the Mural
  MCP server (a board open in a signed-in browser tab); it can also build from a
  standalone image.
- `mural-local-driver` requires the `claude-in-chrome` browser extension enabled,
  the Mural app domain permissioned in the extension, and a writable board already
  open in Chrome. It does **not** use the Mural API or MCP. Not available in
  bypass-permissions sessions.

## Versioning

Current version: **1.1.0** (see `.claude-plugin/plugin.json`).
