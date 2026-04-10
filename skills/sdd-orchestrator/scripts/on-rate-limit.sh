#!/bin/bash
# on-rate-limit.sh — StopFailure(rate_limit) 훅
# 리밋 도달 시 자동 실행: 상태 저장 + 사용자 알림
# 토큰 소비 없음 (셸 스크립트)
#
# 주의: Claude Max의 extra usage에서는 StopFailure가 트리거되지 않을 수 있음.
# 이 경우 오케스트레이터 내부의 Agent 에러 기반 리밋 감지가 1차 방어선.
# 이 스크립트는 StopFailure가 실제로 트리거될 때의 2차 방어선.

set -euo pipefail

# stdin에서 hook 데이터 읽기
HOOK_DATA=$(cat /dev/stdin)
PROJECT_DIR=$(echo "$HOOK_DATA" | jq -r '.cwd // empty')

if [ -z "$PROJECT_DIR" ]; then
  PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
fi

STATE_FILE="$PROJECT_DIR/.claude/shared/ORCHESTRATOR_STATE.md"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# 상태 파일이 없으면 오케스트레이터 세션이 아님 — 종료
if [ ! -f "$STATE_FILE" ]; then
  exit 0
fi

# 상태를 PAUSED_AT_LIMIT으로 변경
sed -i '' "s/^- 상태: EXECUTING/- 상태: PAUSED_AT_LIMIT/" "$STATE_FILE"

# 이력에 기록
echo "- [$TIMESTAMP] StopFailure: rate_limit 감지, 상태 저장 완료" >> "$STATE_FILE"

# interrupted 상태로 실행 중이던 태스크 변경
sed -i '' 's/| implementing |/| interrupted |/g' "$STATE_FILE"
sed -i '' 's/| reviewing |/| interrupted |/g' "$STATE_FILE"
sed -i '' 's/| fixing |/| interrupted |/g' "$STATE_FILE"
sed -i '' 's/| testing |/| interrupted |/g' "$STATE_FILE"

# 리셋 시간 계산 (다음 날 01:00 KST)
TOMORROW_1AM=$(date -v+1d -j -f '%Y-%m-%d %H:%M:%S' "$(date -v+1d '+%Y-%m-%d') 01:00:30" '+%s' 2>/dev/null)
NOW=$(date '+%s')

if [ -n "$TOMORROW_1AM" ] && [ "$TOMORROW_1AM" -gt "$NOW" ]; then
  SLEEP_SEC=$((TOMORROW_1AM - NOW))

  # resume_at 기록
  RESUME_AT=$(date -v+1d -j -f '%H:%M:%S' '01:00:30' '+%Y-%m-%dT%H:%M:%S+09:00' 2>/dev/null || echo "unknown")
  sed -i '' "s/^- resume_at:.*/- resume_at: $RESUME_AT/" "$STATE_FILE"

  echo "- [$TIMESTAMP] 리밋 감지: 재개 예정 시각 $RESUME_AT" >> "$STATE_FILE"
fi

echo "- [$TIMESTAMP] 상태 저장 완료. 'sdd-orchestrator resume'으로 재개하세요." >> "$STATE_FILE"

exit 0
