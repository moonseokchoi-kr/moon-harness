#!/bin/bash
# enforcement/branch-gate.sh — PreToolUse (Bash)
#
# Phase 4 실행 중 main 브랜치 직접 커밋/푸시 차단.
# 이유: Phase 4에서 모든 구현은 worktree에서 수행해야 한다.
#       main 직접 수정은 검토되지 않은 코드가 바로 반영되어
#       리뷰/테스트 루프가 우회된다.
# 대안: git worktree list 로 현재 worktree를 확인하고 해당 경로에서 작업하라.
#
# 대체된 텍스트 규칙: skills/sdd/SKILL.md "Phase 4 worktree 격리" 조항

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

# 관련 git 명령어만 처리
case "$COMMAND" in
  *git\ commit*|*git\ push*|*git\ merge*|*git\ rebase*)
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

# 현재 브랜치 확인
CURRENT_BRANCH=$(git -C "${CLAUDE_PROJECT_DIR:-.}" rev-parse --abbrev-ref HEAD 2>/dev/null)
[ "$CURRENT_BRANCH" != "main" ] && [ "$CURRENT_BRANCH" != "master" ] && exit 0

# main/master 브랜치에서 쓰기 명령 — 차단
gate_block "BRANCH-GATE" \
  "Phase 4 실행 중 main 브랜치 직접 수정 불가 (현재: $CURRENT_BRANCH)" \
  "worktree에서 작업하세요: git worktree list"
exit 2
