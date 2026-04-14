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
# macOS의 "sed -i ''"와 GNU sed의 "sed -i" 차이를 처리합니다.
if sed --version >/dev/null 2>&1; then
  # GNU sed
  sed -i "s/^- 상태: EXECUTING/- 상태: PAUSED_AT_LIMIT/" "$STATE_FILE"
  sed -i 's/| implementing |/| interrupted |/g' "$STATE_FILE"
  sed -i 's/| reviewing |/| interrupted |/g' "$STATE_FILE"
  sed -i 's/| fixing |/| interrupted |/g' "$STATE_FILE"
  sed -i 's/| testing |/| interrupted |/g' "$STATE_FILE"
else
  # Assume BSD/macOS sed
  sed -i '' "s/^- 상태: EXECUTING/- 상태: PAUSED_AT_LIMIT/" "$STATE_FILE"
  sed -i '' 's/| implementing |/| interrupted |/g' "$STATE_FILE"
  sed -i '' 's/| reviewing |/| interrupted |/g' "$STATE_FILE"
  sed -i '' 's/| fixing |/| interrupted |/g' "$STATE_FILE"
  sed -i '' 's/| testing |/| interrupted |/g' "$STATE_FILE"
fi

# 리셋 시간 계산 (다음 날 01:00 KST)
# macOS와 GNU date 옵션 차이 처리 (간단한 fallback)
if date -v+1d >/dev/null 2>&1; then
  TOMORROW_1AM=$(date -v+1d -j -f '%Y-%m-%d %H:%M:%S' "$(date -v+1d '+%Y-%m-%d') 01:00:30" '+%s' 2>/dev/null || true)
  RESUME_AT=$(date -v+1d -j -f '%H:%M:%S' '01:00:30' '+%Y-%m-%dT%H:%M:%S+09:00' 2>/dev/null || echo "unknown")
else
  # GNU date fallback: use --date='tomorrow 01:00:30'
  TOMORROW_1AM=$(date --date='tomorrow 01:00:30' '+%s' 2>/dev/null || true)
  RESUME_AT=$(date --date='tomorrow 01:00:30' '+%Y-%m-%dT%H:%M:%S+09:00' 2>/dev/null || echo "unknown")
fi

NOW=$(date '+%s')

if [ -n "$TOMORROW_1AM" ] && [ "$TOMORROW_1AM" -gt "$NOW" ]; then
  SLEEP_SEC=$((TOMORROW_1AM - NOW))

  # resume_at 기록
  # sed 호환성 함수 처리 위에서 이미 적용되므로 reuse
  if sed --version >/dev/null 2>&1; then
    sed -i "s/^- resume_at:.*/- resume_at: $RESUME_AT/" "$STATE_FILE"
  else
    sed -i '' "s/^- resume_at:.*/- resume_at: $RESUME_AT/" "$STATE_FILE"
  fi

  echo "- [$TIMESTAMP] 리밋 감지: 재개 예정 시각 $RESUME_AT" >> "$STATE_FILE"
fi

echo "- [$TIMESTAMP] 상태 저장 완료. 'sdd-orchestrator resume'으로 재개하세요." >> "$STATE_FILE"

exit 0
