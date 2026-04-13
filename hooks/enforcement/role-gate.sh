#!/bin/bash
# enforcement/role-gate.sh — PreToolUse (Edit|Write)
#
# 역할 기반 파일 편집 제어.
# 오케스트레이터(메인 세션)는 코드/문서를 직접 편집할 수 없다.
# 이유: 오케스트레이터가 코드를 직접 수정하면 에이전트 소유권이 무너지고
#       리뷰/테스트 루프가 우회된다. 반드시 Engineer Agent를 통해야 한다.
# 대안: Agent 도구로 담당 엔지니어 에이전트를 디스패치하라.
#
# 대체된 텍스트 규칙: ~/.claude/rules/orchestrator-no-direct-edit.md

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/constants.sh"
source "$SCRIPT_DIR/lib/logging.sh"
source "$SCRIPT_DIR/lib/state-reader.sh"
source "$SCRIPT_DIR/lib/decision-cache.sh"

INPUT=$(cat)

# Edit, Write만 처리
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')
[[ "$TOOL_NAME" != "Edit" && "$TOOL_NAME" != "Write" ]] && exit 0

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
[ -z "$FILE_PATH" ] && exit 0

# agent-context.json 없으면 오케스트레이션 모드가 아님 — 통과
[ ! -f "$HARNESS_AGENT_CONTEXT" ] && exit 0

# 역할 읽기 (캐시 활용)
ROLE=$(cache_get "agent_role")
if [ -z "$ROLE" ]; then
  ROLE=$(read_agent_role)
  [ -n "$ROLE" ] && cache_set "agent_role" "$ROLE"
fi

# role이 없거나 orchestrator가 아니면 통과
[ -z "$ROLE" ] && exit 0
[ "$ROLE" != "orchestrator" ] && exit 0

# 오케스트레이터 세션: 상태/설정 파일은 편집 허용
case "$FILE_PATH" in
  # 상태 파일 — 오케스트레이터가 직접 관리
  */.claude/state/*|\
  */.claude/shared/ORCHESTRATOR_STATE.md|\
  */ORCHESTRATOR_STATE.md|\
  */.claude/settings*.json)
    gate_pass "ROLE-GATE" "상태 파일 편집 허용: $FILE_PATH"
    exit 0
    ;;
esac

# 나머지는 모두 차단
gate_block "ROLE-GATE" \
  "오케스트레이터는 코드/문서를 직접 편집할 수 없습니다: $(basename "$FILE_PATH")" \
  "Agent 도구로 담당 엔지니어 에이전트를 디스패치하세요"
exit 2
