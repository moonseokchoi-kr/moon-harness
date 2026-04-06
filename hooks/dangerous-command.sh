#!/bin/bash
# Moon Harness Hook S2: Dangerous Command Warning
# Event: PreToolUse (Bash)
# Warns before destructive operations

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

[ -z "$COMMAND" ] && exit 0

# Safe rm -rf targets (don't warn for these)
SAFE_RM_TARGETS="node_modules|\.next|dist|build|\.cache|__pycache__|\.pytest_cache|target/debug|target/release"

# Check rm -rf (excluding safe targets)
if echo "$COMMAND" | grep -qE 'rm\s+(-[a-zA-Z]*r[a-zA-Z]*f|--recursive)\s' ; then
  if ! echo "$COMMAND" | grep -qE "rm\s+-rf\s+($SAFE_RM_TARGETS)"; then
    echo "⚠️ 재귀 삭제 명령 감지: rm -rf" >&2
    echo "삭제 대상이 맞는지 확인하세요. 안전 대상: node_modules, .next, dist, build" >&2
    exit 2
  fi
fi

# Check database destructive operations
if echo "$COMMAND" | grep -qiE '(DROP\s+(TABLE|DATABASE|INDEX)|TRUNCATE|DELETE\s+FROM\s+\w+\s*$)'; then
  echo "⚠️ DB 파괴 명령 감지" >&2
  echo "정말 실행하시겠습니까? 이 작업은 되돌릴 수 없습니다." >&2
  exit 2
fi

# Check git force operations
if echo "$COMMAND" | grep -qE 'git\s+push\s+.*--force|git\s+reset\s+--hard'; then
  echo "⚠️ Git 강제 작업 감지" >&2
  echo "force push나 hard reset은 히스토리를 파괴합니다. 정말 필요한지 확인하세요." >&2
  exit 2
fi

# Check pipe to shell (curl | bash pattern)
if echo "$COMMAND" | grep -qE 'curl\s.*\|\s*(ba)?sh|wget\s.*\|\s*(ba)?sh'; then
  echo "⚠️ 파이프 실행 감지: curl | sh" >&2
  echo "원격 스크립트를 직접 실행하는 것은 위험합니다. 먼저 내용을 확인하세요." >&2
  exit 2
fi

exit 0
