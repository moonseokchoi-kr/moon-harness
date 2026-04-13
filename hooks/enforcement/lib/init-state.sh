#!/bin/bash
# enforcement/lib/init-state.sh
# .claude/state/ 디렉토리와 초기 상태 파일을 생성한다.
# SessionStart 훅(phase-gate.sh)에서 호출된다.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/constants.sh"

init_state_dir() {
  mkdir -p "$HARNESS_STATE_DIR"

  # agent-context.json — 없으면 기본값으로 생성
  if [ ! -f "$HARNESS_AGENT_CONTEXT" ]; then
    cat > "$HARNESS_AGENT_CONTEXT" <<'EOF'
{
  "role": "orchestrator",
  "task_id": null,
  "dispatch_phase": null,
  "session_id": null
}
EOF
  fi

  # tdd-state.json — 없으면 빈 객체로 생성
  if [ ! -f "$HARNESS_TDD_STATE" ]; then
    echo '{}' > "$HARNESS_TDD_STATE"
  fi

  # escalation-log.jsonl — 없으면 빈 파일 생성
  if [ ! -f "$HARNESS_ESCALATION_LOG" ]; then
    touch "$HARNESS_ESCALATION_LOG"
  fi

  # e2e-config.json — 없으면 기본 템플릿 생성
  if [ ! -f "$HARNESS_E2E_CONFIG" ]; then
    cat > "$HARNESS_E2E_CONFIG" <<'EOF'
{
  "enabled": false,
  "test_dir": "e2e/",
  "patterns": [
    { "source": "src/features/**", "e2e": "e2e/{name}.spec.ts" },
    { "source": "src/pages/**",    "e2e": "e2e/pages/{name}.spec.ts" }
  ],
  "exempt": [
    "src/utils/**",
    "src/types/**",
    "src/constants/**"
  ]
}
EOF
  fi
}
