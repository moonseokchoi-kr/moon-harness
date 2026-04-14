#!/bin/bash
# Moon Harness — One-touch installer
# Usage: ./setup.sh [--copy]
#
# 기본(symlink 모드): 파일을 심링크로 연결 — repo 수정이 즉시 반영됨
# --copy 모드: 파일을 복사 — repo 없이 독립 배포용
set -euo pipefail

HARNESS_VERSION="0.2.0"
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_DIR="$HOME/.claude"
INSTALL_MODE="link"

# ─── Parse args ────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case $1 in
    --copy)   INSTALL_MODE="copy"; shift ;;
    --help|-h)
      echo "Moon Harness Installer v${HARNESS_VERSION}"
      echo "Usage: ./setup.sh [--copy]"
      echo ""
      echo "  (기본) symlink 모드 — repo 수정이 즉시 반영"
      echo "  --copy              — 파일 복사 (독립 배포용)"
      exit 0 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

# ─── Helpers ───────────────────────────────────────────────────
ok()   { echo "  ✓ $*"; }
skip() { echo "  · $* (이미 설치됨)"; }
warn() { echo "  ⚠ $*"; }
fail() { echo "  ✗ $*" >&2; exit 1; }

install_item() {
  local src="$1" dst="$2"
  if [ "$INSTALL_MODE" = "link" ]; then
    [ -L "$dst" ] && rm "$dst"
    ln -sf "$src" "$dst"
  else
    [ -f "$src" ] && cp "$src" "$dst" && chmod +x "$dst"
    [ -d "$src" ] && cp -r "$src" "$dst"
  fi
}

# ─── Pre-flight ────────────────────────────────────────────────
echo ""
echo "  🌙 Moon Harness v${HARNESS_VERSION}"
echo "  ─────────────────────────────────"
echo "  Mode:   $INSTALL_MODE"
echo "  Source: $REPO_DIR"
echo "  Target: $CLAUDE_DIR"
echo ""

command -v python3 &>/dev/null || fail "python3가 필요합니다"
command -v jq &>/dev/null     || warn "jq가 없습니다 — settings.json 업데이트 시 필요"

# ─── 1. Skills ─────────────────────────────────────────────────
SKILL_DIR="$CLAUDE_DIR/skills"
mkdir -p "$SKILL_DIR"

SKILLS=(
  harness sdd sdd-taskrunner
  brain-storm idea-reframe idea-workshop deep-idea
  adversarial-review handoff git-worktree
  sdd-orchestrator
)

SKILL_COUNT=0
for skill in "${SKILLS[@]}"; do
  src="$REPO_DIR/skills/$skill"
  dst="$SKILL_DIR/$skill"
  [ ! -d "$src" ] && continue
  if [ -L "$dst" ] && [ "$(readlink "$dst")" = "$src" ]; then
    skip "skill: $skill"
  else
    install_item "$src" "$dst"
    ok "skill: $skill"
    ((SKILL_COUNT++))
  fi
done

# ─── 2. Agents ─────────────────────────────────────────────────
AGENT_DIR="$CLAUDE_DIR/agents"
mkdir -p "$AGENT_DIR"

AGENT_COUNT=0
for src in "$REPO_DIR/agents/"*.md; do
  [ ! -f "$src" ] && continue
  base=$(basename "$src")
  dst="$AGENT_DIR/$base"
  if [ -L "$dst" ] && [ "$(readlink "$dst")" = "$src" ]; then
    skip "agent: $base"
  else
    install_item "$src" "$dst"
    ((AGENT_COUNT++))
  fi
done
ok "$AGENT_COUNT agents → $AGENT_DIR"

# ─── 3. Hooks ──────────────────────────────────────────────────
MH_DIR="$CLAUDE_DIR/hooks/moon-harness"
ENF_LINK="$CLAUDE_DIR/hooks/enforcement"
mkdir -p "$MH_DIR"

# moon-harness 개별 훅 심링크
MH_HOOKS=(
  secret-detect.sh dangerous-command.sh sensitive-file.sh
  file-ownership.sh
  cmux-session-start.sh cmux-session-end.sh cmux-task-progress.sh
)
for hook in "${MH_HOOKS[@]}"; do
  src="$REPO_DIR/hooks/$hook"
  dst="$MH_DIR/$hook"
  [ ! -f "$src" ] && continue
  if [ -L "$dst" ] && [ "$(readlink "$dst")" = "$src" ]; then
    skip "hook: $hook"
  else
    install_item "$src" "$dst"
    ok "hook: $hook"
  fi
done

# enforcement 디렉토리 심링크 (또는 복사)
ENF_SRC="$REPO_DIR/hooks/enforcement"
if [ -L "$ENF_LINK" ] && [ "$(readlink "$ENF_LINK")" = "$ENF_SRC" ]; then
  skip "hook: enforcement/"
elif [ "$INSTALL_MODE" = "link" ]; then
  [ -L "$ENF_LINK" ] && rm "$ENF_LINK"
  [ -d "$ENF_LINK" ] && mv "$ENF_LINK" "${ENF_LINK}.bak.$(date +%s)"
  ln -sf "$ENF_SRC" "$ENF_LINK"
  ok "hook: enforcement/ (symlink)"
else
  [ -d "$ENF_LINK" ] && mv "$ENF_LINK" "${ENF_LINK}.bak.$(date +%s)"
  cp -r "$ENF_SRC" "$ENF_LINK"
  chmod +x "$ENF_LINK"/*.sh "$ENF_LINK"/*.py "$ENF_LINK"/lib/*.sh 2>/dev/null
  ok "hook: enforcement/ (copy)"
fi

# ─── 4. settings.json 훅 등록 ──────────────────────────────────
SETTINGS="$CLAUDE_DIR/settings.json"

# settings.json 없으면 최소 구조로 생성
if [ ! -f "$SETTINGS" ]; then
  echo '{"hooks":{}}' > "$SETTINGS"
  ok "settings.json 생성"
fi

# Python으로 settings.json 업데이트
python3 - "$SETTINGS" "$MH_DIR" "$ENF_LINK" <<'PYEOF'
import json, sys, os, tempfile, shutil

settings_path = sys.argv[1]
mh_dir        = sys.argv[2]
enf_dir       = sys.argv[3]

def cmd(path): return {"type": "command", "command": path}

# 등록할 훅 목록 (이벤트 → matcher → 훅 순서)
HOOKS_TO_ADD = {
    "SessionStart": [
        (None, [
            cmd(f"{enf_dir}/phase-gate.sh"),
            cmd(f"{enf_dir}/harness-check.sh"),
        ]),
    ],
    "PreToolUse": [
        ("Bash", [
            cmd(f"{mh_dir}/dangerous-command.sh"),
            cmd(f"{mh_dir}/secret-detect.sh"),
            cmd(f"{enf_dir}/branch-gate.sh"),
            cmd(f"{enf_dir}/e2e-gate.sh"),
        ]),
        ("Edit|Write", [
            cmd(f"{mh_dir}/sensitive-file.sh"),
            cmd(f"{mh_dir}/file-ownership.sh"),
            cmd(f"{enf_dir}/role-gate.sh"),
            cmd(f"{enf_dir}/tdd-gate.sh"),
        ]),
    ],
    "PostToolUse": [
        ("TaskUpdate|TaskCreate", [
            cmd(f"{mh_dir}/cmux-task-progress.sh"),
        ]),
        ("Agent", [
            cmd(f"{enf_dir}/escalation-tracker.sh"),
        ]),
    ],
    "Stop": [
        (None, [
            cmd(f"{enf_dir}/stop-pipeline.sh"),
            cmd(f"{mh_dir}/cmux-session-end.sh"),
        ]),
    ],
}

with open(settings_path) as f:
    settings = json.load(f)

if "hooks" not in settings:
    settings["hooks"] = {}

added = 0

for event, matcher_groups in HOOKS_TO_ADD.items():
    if event not in settings["hooks"]:
        settings["hooks"][event] = []

    event_entries = settings["hooks"][event]

    for matcher, new_hooks in matcher_groups:
        # 기존 엔트리 중 matcher가 같은 것 찾기
        target_entry = None
        for entry in event_entries:
            entry_matcher = entry.get("matcher")
            if matcher is None and entry_matcher is None:
                target_entry = entry; break
            if entry_matcher == matcher:
                target_entry = entry; break

        # 없으면 새 엔트리 생성
        if target_entry is None:
            target_entry = {"hooks": []}
            if matcher:
                target_entry = {"matcher": matcher, "hooks": []}
            event_entries.append(target_entry)

        if "hooks" not in target_entry:
            target_entry["hooks"] = []

        # 기존 커맨드 경로 집합 (basename 기준)
        existing_basenames = {
            os.path.basename(h.get("command", ""))
            for h in target_entry["hooks"]
            if isinstance(h, dict)
        }

        for hook in new_hooks:
            basename = os.path.basename(hook["command"])
            if basename not in existing_basenames:
                target_entry["hooks"].append(hook)
                existing_basenames.add(basename)
                added += 1

# 원자적 쓰기 (temp → rename)
tmp = settings_path + ".tmp"
with open(tmp, "w") as f:
    json.dump(settings, f, indent=2, ensure_ascii=False)
    f.write("\n")
shutil.move(tmp, settings_path)

print(f"  ✓ settings.json: {added}개 훅 등록 완료" if added else "  · settings.json: 이미 최신 상태")
PYEOF

# ─── 5. Summary ────────────────────────────────────────────────
echo ""
echo "  ✅ 설치 완료!"
echo ""
echo "  설치된 항목:"
echo "    Skills  : $SKILL_COUNT개"
echo "    Agents  : $AGENT_COUNT개"
echo "    Hooks   : moon-harness/ + enforcement/"
echo "    Config  : $SETTINGS"
echo ""
echo "  다음 단계:"
echo "    1. Claude Code 재시작 (settings.json 변경 적용)"
echo "    2. 프로젝트에서 /harness 실행 → 환경 구성"
echo "    3. /sdd 로 개발 시작"
echo ""
