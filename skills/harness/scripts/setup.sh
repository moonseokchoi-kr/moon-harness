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
  "harness-controller"
  "sdd"
  "sdd-taskrunner"
  "sdd-orchestrator"
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

# ─── Install hooks ────────────────────────────────────────────
if [ "$HOST" = "claude" ]; then
  echo ""
  echo "🪝 Installing hooks..."

  HOOK_SOURCE="$SCRIPT_DIR/../../hooks"
  HOOK_DIR="$HOME/.claude/hooks/$HARNESS_NAME"
  mkdir -p "$HOOK_DIR"

  HOOK_FILES=(
    "secret-detect.sh"
    "dangerous-command.sh"
    "sensitive-file.sh"
    "file-ownership.sh"
    "cmux-session-start.sh"
    "cmux-session-end.sh"
    "cmux-task-progress.sh"
  )

  # on-rate-limit.sh는 sdd-orchestrator 스킬 내부에 있음
  ORCH_HOOK_SOURCE="$SCRIPT_DIR/../../skills/sdd-orchestrator/scripts/on-rate-limit.sh"

  for hook in "${HOOK_FILES[@]}"; do
    if [ -f "$HOOK_SOURCE/$hook" ]; then
      if [ "$INSTALL_MODE" = "link" ]; then
        ln -sf "$HOOK_SOURCE/$hook" "$HOOK_DIR/$hook"
      else
        cp "$HOOK_SOURCE/$hook" "$HOOK_DIR/$hook"
        chmod +x "$HOOK_DIR/$hook"
      fi
      echo "   🪝 $hook — installed"
    fi
  done

  # on-rate-limit.sh (스킬 내부에서)
  if [ -f "$ORCH_HOOK_SOURCE" ]; then
    if [ "$INSTALL_MODE" = "link" ]; then
      ln -sf "$ORCH_HOOK_SOURCE" "$HOOK_DIR/on-rate-limit.sh"
    else
      cp "$ORCH_HOOK_SOURCE" "$HOOK_DIR/on-rate-limit.sh"
      chmod +x "$HOOK_DIR/on-rate-limit.sh"
    fi
    echo "   🪝 on-rate-limit.sh — installed"
  fi

  # ─── Register hooks in settings.json ──────────────────────────
  echo ""
  echo "📋 Registering hooks in settings.json..."

  SETTINGS_FILE="$HOME/.claude/settings.json"

  # settings.json이 없으면 생성
  if [ ! -f "$SETTINGS_FILE" ]; then
    echo '{}' > "$SETTINGS_FILE"
  fi

  # jq가 있으면 자동 등록
  if command -v jq &>/dev/null; then
    TEMP_SETTINGS=$(mktemp)

    jq --arg hook_dir "$HOOK_DIR" '
      # PreToolUse hooks
      .hooks.PreToolUse = (
        (.hooks.PreToolUse // []) |
        [.[] | select(.hooks[0].command | contains("secret-detect") or contains("dangerous-command") or contains("sensitive-file") or contains("file-ownership") | not)] +
        [
          {"matcher": {"tool_name": "Bash"}, "hooks": [{"type": "command", "command": ($hook_dir + "/secret-detect.sh")}]},
          {"matcher": {"tool_name": "Bash"}, "hooks": [{"type": "command", "command": ($hook_dir + "/dangerous-command.sh")}]},
          {"matcher": {"tool_name": "Write"}, "hooks": [{"type": "command", "command": ($hook_dir + "/sensitive-file.sh")}]},
          {"matcher": {"tool_name": "Edit"}, "hooks": [{"type": "command", "command": ($hook_dir + "/file-ownership.sh")}]},
          {"matcher": {"tool_name": "Write"}, "hooks": [{"type": "command", "command": ($hook_dir + "/file-ownership.sh")}]}
        ]
      ) |
      # StopFailure hook
      .hooks.StopFailure = (
        (.hooks.StopFailure // []) |
        [.[] | select(.hooks[0].command | contains("on-rate-limit") | not)] +
        [
          {"matcher": {"error_type": "rate_limit"}, "hooks": [{"type": "command", "command": ($hook_dir + "/on-rate-limit.sh")}]}
        ]
      )
    ' "$SETTINGS_FILE" > "$TEMP_SETTINGS" && mv "$TEMP_SETTINGS" "$SETTINGS_FILE"

    echo "   ✅ Hooks registered in settings.json"
  else
    echo "   ⚠️  jq not found — manual hook registration required"
    echo "   Add the following to ~/.claude/settings.json hooks section:"
    echo "   - PreToolUse: secret-detect, dangerous-command, sensitive-file, file-ownership"
    echo "   - StopFailure: on-rate-limit (matcher: rate_limit)"
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
