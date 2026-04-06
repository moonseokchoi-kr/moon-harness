#!/bin/bash
# Moon Harness — 30-second installer
# Usage: ./setup.sh [--host claude|codex] [--link|--copy]
set -euo pipefail

# ─── Configuration ─────────────────────────────────────────────
HARNESS_NAME="moon-harness"
HARNESS_VERSION="0.1.0"
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Defaults
HOST="claude"
INSTALL_MODE="link"  # link = symlink (dev), copy = copy files (dist)

# ─── Parse args ────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case $1 in
    --host)   HOST="$2"; shift 2 ;;
    --link)   INSTALL_MODE="link"; shift ;;
    --copy)   INSTALL_MODE="copy"; shift ;;
    --help|-h)
      echo "Moon Harness Installer v${HARNESS_VERSION}"
      echo ""
      echo "Usage: ./setup.sh [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  --host claude|codex   Target host (default: claude)"
      echo "  --link                Symlink mode for development (default)"
      echo "  --copy                Copy mode for distribution"
      echo "  -h, --help            Show this help"
      exit 0
      ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

# ─── Host-specific paths ──────────────────────────────────────
case "$HOST" in
  claude)
    SKILL_DIR="$HOME/.claude/skills"
    CONFIG_FILE="CLAUDE.md"
    ;;
  codex)
    SKILL_DIR="$HOME/.agents/skills"
    CONFIG_FILE="AGENTS.md"
    ;;
  *)
    echo "❌ Unknown host: $HOST (supported: claude, codex)"
    exit 1
    ;;
esac

# ─── Skills to install ─────────────────────────────────────────
# Core skills that are part of the harness plugin
CORE_SKILLS=(
  "harness"
  "sdd"
  "sdd-taskrunner"
  "brain-storm"
  "idea-reframe"
  "idea-workshop"
  "deep-idea"
  "adversarial-review"
  "handoff"
  "git-worktree"
)

# ─── Pre-flight checks ─────────────────────────────────────────
echo "🔧 Moon Harness v${HARNESS_VERSION}"
echo "   Host: $HOST"
echo "   Mode: $INSTALL_MODE"
echo "   Target: $SKILL_DIR"
echo ""

# Create skill directory if not exists
mkdir -p "$SKILL_DIR"

# ─── Install skills ────────────────────────────────────────────
INSTALLED=0
SKIPPED=0

for skill in "${CORE_SKILLS[@]}"; do
  SOURCE="$SCRIPT_DIR/../$skill"
  TARGET="$SKILL_DIR/$skill"

  # Check source exists
  if [ ! -d "$SOURCE" ]; then
    echo "   ⚠️  $skill — source not found, skipping"
    ((SKIPPED++))
    continue
  fi

  # Skip if already installed (and not in link mode)
  if [ -e "$TARGET" ] && [ "$INSTALL_MODE" = "copy" ]; then
    echo "   ⏭️  $skill — already exists, skipping"
    ((SKIPPED++))
    continue
  fi

  # Remove existing symlink if re-linking
  if [ -L "$TARGET" ]; then
    rm "$TARGET"
  fi

  if [ "$INSTALL_MODE" = "link" ]; then
    ln -sf "$SOURCE" "$TARGET"
    echo "   🔗 $skill — linked"
  else
    cp -r "$SOURCE" "$TARGET"
    echo "   📦 $skill — copied"
  fi
  ((INSTALLED++))
done

# ─── Post-install: Codex host adaptation ───────────────────────
if [ "$HOST" = "codex" ]; then
  echo ""
  echo "🔄 Adapting for Codex..."

  # Generate AGENTS.md pointer if not exists
  if [ ! -f "$SKILL_DIR/../AGENTS.md" ]; then
    cat > "$SKILL_DIR/../AGENTS.md" << 'AGENTS_EOF'
# Agents Configuration

## Available Skills
Skills are located in ~/.agents/skills/

### Core Workflow
- **sdd**: Spec-Driven Development — 3-phase structured workflow
- **idea-workshop**: Idea lifecycle orchestrator (brain-storm → idea-reframe → deep-idea)
- **harness**: Agent-friendly environment setup and maintenance

### Support
- **adversarial-review**: Escalation when code review fails 3x
- **handoff**: Session context preservation
- **git-worktree**: Isolated feature branches
AGENTS_EOF
    echo "   📝 AGENTS.md — created"
  fi
fi

# ─── Summary ───────────────────────────────────────────────────
echo ""
echo "✅ Done!"
echo "   Installed: $INSTALLED skills"
[ $SKIPPED -gt 0 ] && echo "   Skipped: $SKIPPED skills"
echo ""
echo "Next steps:"
echo "  1. Run '/harness' in a project to set up the environment"
echo "  2. Run '/harness audit' to check harness health"
echo ""
