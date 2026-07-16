#!/usr/bin/env bash
#
# install.sh — copy the Mural skills into a Claude Code skills directory.
#
# Usage:
#   ./install.sh                 # install for the current user (~/.claude/skills)
#   ./install.sh --project DIR   # install into DIR/.claude/skills (project-scoped)
#   ./install.sh --uninstall     # remove the two skills from ~/.claude/skills
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$SCRIPT_DIR/skills"
SKILLS=(muralize mural-image-rebuilder mural-local-driver mural-retro-recycler)

TARGET="$HOME/.claude/skills"
MODE="install"

while [ $# -gt 0 ]; do
  case "$1" in
    --project)
      shift
      [ $# -gt 0 ] || { echo "error: --project needs a directory" >&2; exit 1; }
      TARGET="$1/.claude/skills"
      ;;
    --uninstall) MODE="uninstall" ;;
    -h|--help)
      sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) echo "error: unknown argument: $1" >&2; exit 1 ;;
  esac
  shift
done

if [ "$MODE" = "uninstall" ]; then
  for s in "${SKILLS[@]}"; do
    if [ -d "$TARGET/$s" ]; then
      rm -rf "$TARGET/$s"
      echo "removed  $TARGET/$s"
    else
      echo "skip     $TARGET/$s (not present)"
    fi
  done
  echo "Done. Restart Claude Code or run /doctor to refresh the skill list."
  exit 0
fi

mkdir -p "$TARGET"
for s in "${SKILLS[@]}"; do
  if [ ! -d "$SRC/$s" ]; then
    echo "error: missing source skill: $SRC/$s" >&2
    exit 1
  fi
  rm -rf "$TARGET/$s"
  cp -R "$SRC/$s" "$TARGET/$s"
  find "$TARGET/$s" -name '.DS_Store' -delete 2>/dev/null || true
  echo "installed  $TARGET/$s"
done

echo
echo "Installed ${#SKILLS[@]} skills into $TARGET"
echo "Restart Claude Code (or run /doctor) so the skills are picked up."
