#!/bin/bash
# enforcement/escalation-tracker.sh — PostToolUse (Agent)
#
# Agent 도구 완료 후 BLOCKED 결과를 추적한다.
# 같은 태스크에서 3회 BLOCKED 시 ESCALATED로 표시하고 경고를 출력한다.
# 이유: 반복 실패는 태스크 자체의 문제(설계 결함, 컨텍스트 부족)를 의미한다.
#       3회 이후에도 같은 에이전트를 재시도하는 것은 낭비다.
# 대안: adversarial-review 스킬을 호출하여 근본 원인을 분석하라.
#
# 대체된 텍스트 규칙: skills/sdd/SKILL.md Adversarial Escalation 조항

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/constants.sh"
source "$SCRIPT_DIR/lib/logging.sh"
source "$SCRIPT_DIR/lib/state-reader.sh"

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')
[ "$TOOL_NAME" != "Agent" ] && exit 0

# Agent 결과에서 status 추출
# tool_result가 텍스트인 경우와 JSON인 경우 모두 처리
TOOL_RESULT=$(echo "$INPUT" | jq -r '.tool_result // empty')

# BLOCKED 또는 DONE 판정
STATUS=""
case "$TOOL_RESULT" in
  *"BLOCKED"*) STATUS="BLOCKED" ;;
  *"DONE"*)    STATUS="DONE" ;;
  *"NEEDS_CONTEXT"*) STATUS="NEEDS_CONTEXT" ;;
esac

# BLOCKED가 아니면 처리 불필요
[ "$STATUS" != "BLOCKED" ] && exit 0

# 태스크 ID 추출 — tool_input.prompt에서 T-XX 패턴 찾기
PROMPT=$(echo "$INPUT" | jq -r '.tool_input.prompt // empty')
TASK_ID=$(echo "$PROMPT" | grep -oE 'T-[0-9]+' | head -1)

# 태스크 ID가 없으면 로그 기록 건너뜀
[ -z "$TASK_ID" ] && exit 0

# 에이전트 타입 추출
AGENT_TYPE=$(echo "$INPUT" | jq -r '.tool_input.subagent_type // "unknown"')

# REASON 추출 (결과 텍스트에서 BLOCKED 뒤 내용)
REASON=$(echo "$TOOL_RESULT" | grep -oE 'BLOCKED[^.]*\.' | head -1 | sed 's/^BLOCKED:*//' | xargs)
[ -z "$REASON" ] && REASON="이유 불명"

# escalation-log.jsonl에 기록
mkdir -p "$HARNESS_STATE_DIR"
touch "$HARNESS_ESCALATION_LOG"

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
LOG_ENTRY=$(jq -nc \
  --arg task_id "$TASK_ID" \
  --arg agent "$AGENT_TYPE" \
  --arg status "$STATUS" \
  --arg reason "$REASON" \
  --arg ts "$TIMESTAMP" \
  '{"task_id":$task_id,"agent_role":$agent,"status":$status,"reason":$reason,"timestamp":$ts}')

echo "$LOG_ENTRY" >> "$HARNESS_ESCALATION_LOG"

# 같은 태스크의 BLOCKED 횟수 집계
BLOCKED_COUNT=$(grep -c "\"task_id\":\"$TASK_ID\"" "$HARNESS_ESCALATION_LOG" 2>/dev/null || echo "0")

# 3회 미만이면 조용히 종료
[ "$BLOCKED_COUNT" -lt 3 ] && exit 0

# 3회 이상 — 에스컬레이션 경고 출력
echo "" >&2
echo "[ESCALATION] ⚠ $TASK_ID 3회 BLOCKED → 에스컬레이션 필요" >&2
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >&2
echo "  에이전트: $AGENT_TYPE" >&2
echo "" >&2
echo "  실패 기록:" >&2
grep "\"task_id\":\"$TASK_ID\"" "$HARNESS_ESCALATION_LOG" 2>/dev/null | \
  jq -r '"    [\(.timestamp)] \(.reason)"' 2>/dev/null | \
  head -5 >&2
echo "" >&2
echo "  → /adversarial-review 호출을 권장합니다" >&2
echo "" >&2

# ORCHESTRATOR_STATE.md에 ESCALATED 상태 기록 (파일이 있는 경우)
if [ -f "$HARNESS_ORCH_STATE" ]; then
  # T-XX 줄에서 status를 ESCALATED로 갱신
  if grep -q "| $TASK_ID" "$HARNESS_ORCH_STATE" 2>/dev/null; then
    sed -i.bak "s/| $TASK_ID[[:space:]]*|[^|]*/| $TASK_ID | ESCALATED /" "$HARNESS_ORCH_STATE" 2>/dev/null
    rm -f "${HARNESS_ORCH_STATE}.bak"
  fi
fi

exit 0
