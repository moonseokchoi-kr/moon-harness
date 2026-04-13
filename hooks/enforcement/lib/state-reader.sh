#!/bin/bash
# enforcement/lib/state-reader.sh
# 상태 파일 읽기 헬퍼 — 파일 없을 때 안전한 기본값 반환

# agent-context.json에서 role 읽기
# 반환: role 문자열 or 빈 문자열
read_agent_role() {
  local file="${HARNESS_AGENT_CONTEXT}"
  [ ! -f "$file" ] && return 0
  jq -r '.role // empty' "$file" 2>/dev/null
}

# agent-context.json에서 task_id 읽기
read_agent_task_id() {
  local file="${HARNESS_AGENT_CONTEXT}"
  [ ! -f "$file" ] && return 0
  jq -r '.task_id // empty' "$file" 2>/dev/null
}

# tdd-state.json에서 특정 태스크의 TDD 상태 읽기
# 사용: read_tdd_status "T-1"
read_tdd_status() {
  local task_id="$1"
  local file="${HARNESS_TDD_STATE}"
  [ ! -f "$file" ] && echo "" && return 0
  jq -r --arg t "$task_id" '.[$t].status // empty' "$file" 2>/dev/null
}

# tdd-state.json에서 TDD 모드 읽기 (FULL or SKIP)
read_tdd_mode() {
  local task_id="$1"
  local file="${HARNESS_TDD_STATE}"
  [ ! -f "$file" ] && echo "" && return 0
  jq -r --arg t "$task_id" '.[$t].mode // empty' "$file" 2>/dev/null
}

# ORCHESTRATOR_STATE.md에서 status 읽기
# 반환: EXECUTING, PAUSED_AT_LIMIT, DONE, 빈 문자열
read_orch_status() {
  local file="${HARNESS_ORCH_STATE}"
  [ ! -f "$file" ] && echo "" && return 0
  grep -m1 "^status:" "$file" 2>/dev/null | awk '{print $2}' | tr -d '`'
}

# escalation-log.jsonl에서 특정 태스크의 BLOCKED 횟수 읽기
read_blocked_count() {
  local task_id="$1"
  local file="${HARNESS_ESCALATION_LOG}"
  [ ! -f "$file" ] && echo "0" && return 0
  grep -c "\"task_id\":\"$task_id\".*\"status\":\"BLOCKED\"" "$file" 2>/dev/null || echo "0"
}

# e2e-config.json 읽기
read_e2e_enabled() {
  local file="${HARNESS_E2E_CONFIG}"
  [ ! -f "$file" ] && echo "false" && return 0
  jq -r '.enabled // false' "$file" 2>/dev/null
}
