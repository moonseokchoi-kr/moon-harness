#!/bin/bash
# enforcement/lib/logging.sh
# 모든 gate 훅에서 사용하는 통일 형식 로깅

# 차단 메시지 출력 (stderr)
# 사용: gate_block "ROLE-GATE" "오케스트레이터 직접 편집 불가" "Engineer Agent를 디스패치하세요"
gate_block() {
  local gate="$1"
  local reason="$2"
  local action="$3"

  echo "" >&2
  echo "[$gate] ✖ $reason" >&2
  [ -n "$action" ] && echo "  → $action" >&2
  echo "" >&2
}

# 경고 메시지 출력 (stderr, 차단 없음)
# 사용: gate_warn "PHASE-GATE" "design/api 누락 감지"
gate_warn() {
  local gate="$1"
  local reason="$2"

  echo "[$gate] ⚠ $reason" >&2
}

# 통과 메시지 (디버그용, HARNESS_DEBUG=1 시에만 출력)
gate_pass() {
  local gate="$1"
  local reason="$2"

  [ "${HARNESS_DEBUG:-0}" = "1" ] && echo "[$gate] ✔ $reason" >&2
}

# 실행 시간 경고 (100ms 초과 시)
gate_perf_warn() {
  local gate="$1"
  local start_ms="$2"
  local end_ms
  end_ms=$(date +%s%3N)
  local elapsed=$((end_ms - start_ms))

  [ $elapsed -gt 100 ] && echo "[$gate] PERF ${elapsed}ms (목표: 100ms 이내)" >&2
}
