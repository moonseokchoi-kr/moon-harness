#!/bin/bash
# enforcement/tdd-gate.sh — PreToolUse (Edit)
#
# TDD Iron Law 강제.
# 구현자(sdd-*-engineer)는 테스트 파일을 수정할 수 없다.
# 이유: 테스트 파일을 수정하면 RED → GREEN 사이클이 무의미해지고
#       테스트가 구현을 검증하는 게 아니라 구현에 맞춰지게 된다.
# 대안: 테스트를 통과시키려면 구현 파일을 수정하라.
#
# 대체된 텍스트 규칙: skills/sdd/SKILL.md TDD Iron Law 금지 조항

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/constants.sh"
source "$SCRIPT_DIR/lib/logging.sh"
source "$SCRIPT_DIR/lib/state-reader.sh"
source "$SCRIPT_DIR/lib/decision-cache.sh"

INPUT=$(cat)

# Edit만 처리 (Write는 신규 파일이므로 테스트 파일 작성은 허용)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')
[ "$TOOL_NAME" != "Edit" ] && exit 0

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
[ -z "$FILE_PATH" ] && exit 0

# agent-context.json 없으면 통과
[ ! -f "$HARNESS_AGENT_CONTEXT" ] && exit 0

# 역할 읽기
ROLE=$(cache_get "agent_role")
if [ -z "$ROLE" ]; then
  ROLE=$(read_agent_role)
  [ -n "$ROLE" ] && cache_set "agent_role" "$ROLE"
fi

# 구현자 에이전트만 적용
# sdd-*-engineer 또는 sdd-implementer 패턴
case "$ROLE" in
  sdd-*-engineer|sdd-implementer) ;;  # 계속 진행
  *) exit 0 ;;
esac

# 편집 대상이 테스트 파일인가?
FILENAME=$(basename "$FILE_PATH")
IS_TEST=false
case "$FILENAME" in
  *.test.*|*.spec.*|*_test.*|*_spec.*)
    IS_TEST=true ;;
esac
# 디렉토리 패턴도 확인
case "$FILE_PATH" in
  */__tests__/*|*/test/*|*/tests/*|*/e2e/*)
    IS_TEST=true ;;
esac

if [ "$IS_TEST" = "true" ]; then
  gate_block "TDD-GATE" \
    "구현자는 테스트 파일을 수정할 수 없습니다: $(basename "$FILE_PATH")" \
    "테스트를 통과시키려면 구현 파일을 수정하세요"
  exit 2
fi

# TDD 모드 확인 (FULL 모드인 태스크만 엄격 적용)
TASK_ID=$(read_agent_task_id)
if [ -n "$TASK_ID" ]; then
  TDD_MODE=$(read_tdd_mode "$TASK_ID")
  TDD_STATUS=$(read_tdd_status "$TASK_ID")

  gate_pass "TDD-GATE" "[$TASK_ID] 상태=$TDD_STATUS 모드=$TDD_MODE — 구현 파일 편집 허용"
fi

exit 0
