#!/bin/bash
# enforcement/worktree-add-gate.sh — PreToolUse (Bash)
#
# Phase 4(EXECUTING) 중 공유 worktree 병렬 git 충돌 두 가지를 물리적으로 차단한다.
#   (a) 광역 stage: `git add -A` / `git add --all` / `git add .`
#       → 다른 태스크의 미완성 파일을 자기 커밋으로 흡수한다.
#   (b) 워커 브랜치 전환/생성: `git checkout -b` / `git switch -c`(/-B/--create)
#       → 이후 커밋이 새 브랜치에 쌓여 원래 feature 브랜치가 뒤처지고, 머지 시 tip을 놓친다.
#
# 대안: 소유 파일만 명시적으로 add(`git add path/to/file`). 브랜치는 Phase 2에서
#       git-worktree 스킬이 이미 만들었으니 worktree에서 그대로 작업한다.
#
# 대체된 텍스트 규칙: CLAUDE.md "git(병렬 작업)" 조항 + .harness/LEARNING.md
#   (2026-06-17 sdd-orchestration 엔트리, "enforcement(L3) 후보").
#
# 스코프: ORCHESTRATOR_STATE.md 가 EXECUTING/PAUSED_AT_LIMIT 일 때만 작동(branch-gate 와 동일).
#         Phase 4 밖에서는 광역 add/브랜치 생성이 정당하므로 통과시킨다.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/constants.sh"
source "$SCRIPT_DIR/lib/logging.sh"
source "$SCRIPT_DIR/lib/state-reader.sh"
source "$SCRIPT_DIR/lib/decision-cache.sh"

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')
[ "$TOOL_NAME" != "Bash" ] && exit 0

COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
[ -z "$COMMAND" ] && exit 0

# 관련 git 명령어만 처리 (빠른 통과)
case "$COMMAND" in
  *git\ add*|*git\ checkout*|*git\ switch*)
    ;;  # 계속 진행
  *)
    exit 0 ;;
esac

# ORCHESTRATOR_STATE.md 없으면 Phase 4 아님 — 통과
[ ! -f "$HARNESS_ORCH_STATE" ] && exit 0

# Phase 4 실행 중인지 확인 (캐시 활용)
ORCH_STATUS=$(cache_get "orch_status")
if [ -z "$ORCH_STATUS" ]; then
  ORCH_STATUS=$(read_orch_status)
  [ -n "$ORCH_STATUS" ] && cache_set "orch_status" "$ORCH_STATUS"
fi

case "$ORCH_STATUS" in
  EXECUTING|PAUSED_AT_LIMIT) ;;  # Phase 4 활성 — 계속 진행
  *) exit 0 ;;  # Phase 4 아님 — 통과
esac

# ── (a) 광역 stage 감지 ──────────────────────────────────────────────
# 차단: `-A`, `--all`, 단독 `.` 토큰.  허용: `git add path`, `git add foo.txt`, `git add -p`.
if echo "$COMMAND" | grep -Eq 'git[[:space:]]+add([[:space:]]+[^;&|]*)?[[:space:]]+(-A|--all)([[:space:]]|$|[;&|])'; then
  gate_block "WORKTREE-ADD-GATE" \
    "Phase 4 공유 worktree에서 광역 stage(\`git add -A/--all\`) 불가 — 다른 태스크 파일을 흡수합니다" \
    "소유 파일만 명시적으로 추가하세요: git add <소유 파일 경로>"
  exit 2
fi
if echo "$COMMAND" | grep -Eq 'git[[:space:]]+add([[:space:]]+-[A-Za-z]+)*[[:space:]]+\.([[:space:]]|$|[;&|])'; then
  gate_block "WORKTREE-ADD-GATE" \
    "Phase 4 공유 worktree에서 광역 stage(\`git add .\`) 불가 — 다른 태스크 파일을 흡수합니다" \
    "소유 파일만 명시적으로 추가하세요: git add <소유 파일 경로>"
  exit 2
fi

# ── (b) 워커 브랜치 전환/생성 감지 ───────────────────────────────────
# 차단: `git checkout -b/-B <name>`, `git switch -c/-C/--create <name>`.
if echo "$COMMAND" | grep -Eq 'git[[:space:]]+checkout[[:space:]]+(-b|-B)([[:space:]]|$)' \
   || echo "$COMMAND" | grep -Eq 'git[[:space:]]+switch[[:space:]]+([^;&|]*[[:space:]])?(-c|-C|--create)([[:space:]]|$)'; then
  gate_block "WORKTREE-ADD-GATE" \
    "Phase 4 실행 중 브랜치 생성/전환 불가 — feature 브랜치가 뒤처져 머지 tip을 놓칩니다" \
    "Phase 2에서 만든 worktree 브랜치에서 그대로 작업하세요(브랜치 전환 금지)"
  exit 2
fi

gate_pass "WORKTREE-ADD-GATE" "git 명령 통과: $COMMAND"
exit 0
