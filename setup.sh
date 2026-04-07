#!/bin/bash
# Moon Harness — 30-second installer
# Usage: ./setup.sh [--host claude|codex] [--link|--copy]
set -euo pipefail

# ─── Configuration ─────────────────────────────────────────────
HARNESS_NAME="moon-harness"
HARNESS_VERSION="0.1.0"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

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
    ;;
  codex)
    SKILL_DIR="$HOME/.agents/skills"
    ;;
  *)
    echo "❌ Unknown host: $HOST (supported: claude, codex)"
    exit 1
    ;;
esac

# ─── Skills to install ─────────────────────────────────────────
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
echo ""
echo "  🌙 Moon Harness v${HARNESS_VERSION}"
echo "  ─────────────────────────────"
echo "  Host:   $HOST"
echo "  Mode:   $INSTALL_MODE"
echo "  Target: $SKILL_DIR"
echo ""

mkdir -p "$SKILL_DIR"

# ─── Install skills ────────────────────────────────────────────
INSTALLED=0
SKIPPED=0

for skill in "${CORE_SKILLS[@]}"; do
  SOURCE="$SCRIPT_DIR/skills/$skill"
  TARGET="$SKILL_DIR/$skill"

  if [ ! -d "$SOURCE" ]; then
    echo "  ⚠️  $skill — source not found, skipping"
    ((SKIPPED++))
    continue
  fi

  # Skip if already exists and not a symlink (copy mode safety)
  if [ -d "$TARGET" ] && [ ! -L "$TARGET" ] && [ "$INSTALL_MODE" = "copy" ]; then
    echo "  ⏭️  $skill — already exists, skipping"
    ((SKIPPED++))
    continue
  fi

  # Remove existing symlink if re-linking
  [ -L "$TARGET" ] && rm "$TARGET"

  if [ "$INSTALL_MODE" = "link" ]; then
    ln -sf "$SOURCE" "$TARGET"
    echo "  🔗 $skill"
  else
    rm -rf "$TARGET"
    cp -r "$SOURCE" "$TARGET"
    echo "  📦 $skill"
  fi
  ((INSTALLED++))
done

# ─── Install agents ────────────────────────────────────────────
if [ "$HOST" = "claude" ]; then
  AGENT_DIR="$HOME/.claude/agents"
elif [ "$HOST" = "codex" ]; then
  AGENT_DIR="$HOME/.agents/agents"
fi

mkdir -p "$AGENT_DIR"
AGENT_COUNT=0

for agent_file in "$SCRIPT_DIR/agents/"*.md; do
  [ ! -f "$agent_file" ] && continue
  BASENAME=$(basename "$agent_file")
  TARGET="$AGENT_DIR/$BASENAME"

  if [ "$INSTALL_MODE" = "link" ]; then
    ln -sf "$agent_file" "$TARGET"
  else
    cp "$agent_file" "$TARGET"
  fi
  ((AGENT_COUNT++))
done
echo "  🤖 $AGENT_COUNT agents → $AGENT_DIR"

# ─── Install global hooks (Claude Code only) ──────────────────
if [ "$HOST" = "claude" ]; then
  echo "  🔒 Installing security hooks..."

  HOOKS_DIR="$HOME/.claude/hooks/moon-harness"
  SETTINGS="$HOME/.claude/settings.json"

  mkdir -p "$HOOKS_DIR"

  # Copy/link hook scripts (security + cmux progress)
  for hook in secret-detect.sh dangerous-command.sh sensitive-file.sh cmux-session-start.sh cmux-session-end.sh cmux-task-progress.sh; do
    if [ "$INSTALL_MODE" = "link" ]; then
      ln -sf "$SCRIPT_DIR/hooks/$hook" "$HOOKS_DIR/$hook"
    else
      cp "$SCRIPT_DIR/hooks/$hook" "$HOOKS_DIR/$hook"
      chmod +x "$HOOKS_DIR/$hook"
    fi
  done
  echo "  🔗 6 hooks → $HOOKS_DIR (3 security + 3 cmux progress)"

  # Check if hooks are registered in settings.json
  if [ -f "$SETTINGS" ] && ! grep -q "moon-harness" "$SETTINGS" 2>/dev/null; then
    echo ""
    echo "  ⚠️  훅을 settings.json에 등록해야 합니다."
    echo "  Claude Code에서 다음을 실행하세요:"
    echo ""
    echo "    /update-config"
    echo "    \"moon-harness 보안 훅 3개를 PreToolUse에 등록해줘."
    echo "     Bash 매처: $HOOKS_DIR/secret-detect.sh, $HOOKS_DIR/dangerous-command.sh"
    echo "     Edit|Write 매처: $HOOKS_DIR/sensitive-file.sh\""
    echo ""
  fi
fi

# ─── Post-install: Codex host adaptation ───────────────────────
if [ "$HOST" = "codex" ]; then
  echo ""
  echo "  🔄 Adapting for Codex..."

  AGENTS_MD="$SKILL_DIR/../AGENTS.md"
  if [ ! -f "$AGENTS_MD" ]; then
    cat > "$AGENTS_MD" << 'AGENTS_EOF'
# Moon Harness — Agent Configuration

## Available Skills
Skills are located in ~/.agents/skills/

### Idea Pipeline
- **idea-workshop**: Idea lifecycle orchestrator
- **brain-storm**: Divergent brainstorming
- **idea-reframe**: Multi-lens reframing (iterates with deep-idea)
- **deep-idea**: Data-driven idea validation

### Implementation
- **sdd**: Spec-Driven Development — 3-phase + review/ship/verify
- **harness**: Agent-friendly environment setup

### Support
- **adversarial-review**: Escalation when review fails 3x
- **handoff**: Session context preservation
- **git-worktree**: Isolated feature branches

## Security Rules
- Do not hardcode API keys. Use environment variables.
- Do not commit .env files.
- Verify external input (SQL injection, XSS).

## Mistake Learning
- Known pitfalls: docs/pitfalls.md
- Lessons learned: docs/lessons-learned.md
- Check relevant pitfalls before starting work in a domain.
AGENTS_EOF
    echo "  📝 AGENTS.md created"
  fi
fi

# ─── Summary ───────────────────────────────────────────────────
echo ""
echo "  ✅ Done! Installed $INSTALLED skills + $AGENT_COUNT agents."
[ $SKIPPED -gt 0 ] && echo "  ⏭️  Skipped $SKIPPED skills."
echo ""
echo "  Next steps:"
echo "    1. Run '/harness' in a project to set up the environment"
echo "    2. Run '/harness audit' to check harness health"
echo "    3. Run '/idea-workshop' to start brainstorming"
echo ""
