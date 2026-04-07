#!/bin/bash
# Moon Harness: 태스크 상태 변경 시 cmux 진행률 업데이트
# Event: PostToolUse (matcher: TaskUpdate|TaskCreate)
command -v cmux &>/dev/null || exit 0

INPUT=$(cat)

# tool_input에서 상태 추출
STATUS=$(echo "$INPUT" | jq -r '.tool_input.status // empty' 2>/dev/null)
SUBJECT=$(echo "$INPUT" | jq -r '.tool_input.subject // empty' 2>/dev/null)

# TaskCreate는 subject만 있고 status 없음
if [ -z "$STATUS" ] && [ -n "$SUBJECT" ]; then
  cmux set-status task "📋 $SUBJECT" --icon "plus.circle" 2>/dev/null || true
  exit 0
fi

case "$STATUS" in
  in_progress)
    # tool_result에서 subject 가져오기 (TaskUpdate는 tool_input에 subject 없을 수 있음)
    if [ -z "$SUBJECT" ]; then
      SUBJECT=$(echo "$INPUT" | jq -r '.tool_result.subject // "작업 중"' 2>/dev/null)
    fi
    cmux set-status task "$SUBJECT" --icon "hammer" --color "#FF9800" 2>/dev/null || true
    ;;
  completed)
    if [ -z "$SUBJECT" ]; then
      SUBJECT=$(echo "$INPUT" | jq -r '.tool_result.subject // "완료"' 2>/dev/null)
    fi
    cmux set-status task "✓ $SUBJECT" --icon "checkmark" --color "#4CAF50" 2>/dev/null || true
    ;;
esac

exit 0
