#!/bin/bash
# file-ownership.sh — PreToolUse 훅 (Edit, Write)
# 태스크별 파일 소유권을 강제하여 다른 태스크의 파일 편집을 차단한다.
# ORCHESTRATOR_STATE.md의 파일 소유권 섹션을 참조한다.

set -euo pipefail

# stdin에서 hook 데이터 읽기
HOOK_DATA=$(cat /dev/stdin)

# tool_name 확인 — Edit, Write만 처리
TOOL_NAME=$(echo "$HOOK_DATA" | jq -r '.tool_name // empty')
if [[ "$TOOL_NAME" != "Edit" && "$TOOL_NAME" != "Write" ]]; then
  exit 0
fi

# 편집 대상 파일 경로 추출
FILE_PATH=$(echo "$HOOK_DATA" | jq -r '.tool_input.file_path // empty')
if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# 프로젝트 디렉토리
PROJECT_DIR=$(echo "$HOOK_DATA" | jq -r '.cwd // empty')
if [ -z "$PROJECT_DIR" ]; then
  exit 0
fi

STATE_FILE="$PROJECT_DIR/docs/sdd/ORCHESTRATOR_STATE.md"

# 상태 파일이 없으면 오케스트레이션 모드가 아님 — 통과
if [ ! -f "$STATE_FILE" ]; then
  exit 0
fi

# 파일 소유권 섹션이 없으면 통과
if ! grep -q "## 파일 소유권" "$STATE_FILE"; then
  exit 0
fi

# 현재 에이전트의 태스크 ID 확인
# Agent 도구로 스폰된 서브에이전트는 agent_id가 있음
AGENT_ID=$(echo "$HOOK_DATA" | jq -r '.agent_id // empty')

# agent_id가 있으면 서브에이전트 — 오케스트레이터가 프롬프트로 소유 파일 목록을 전달하므로
# 이 훅은 추가 안전장치 역할. 서브에이전트는 통과시킨다.
if [ -n "$AGENT_ID" ]; then
  exit 0
fi

# 메인 세션에서의 편집 — 파일 소유권 확인
# 상대 경로로 변환
REL_PATH="${FILE_PATH#$PROJECT_DIR/}"

# 파일 소유권 테이블에서 매칭되는 소유자 태스크 찾기
OWNER_TASK=""
while IFS='|' read -r _ task files _; do
  task=$(echo "$task" | xargs)
  files=$(echo "$files" | xargs)

  if [ -z "$task" ] || [ -z "$files" ]; then
    continue
  fi

  # 파일 경로가 소유 파일/디렉토리에 포함되는지 확인
  for owned in $files; do
    owned=$(echo "$owned" | tr -d ',')
    if [[ "$REL_PATH" == "$owned"* ]] || [[ "$REL_PATH" == *"$owned"* ]]; then
      OWNER_TASK="$task"
      break 2
    fi
  done
done < <(sed -n '/## 파일 소유권/,/^## /p' "$STATE_FILE" | grep "^|" | tail -n +3)

# 소유자가 없으면 공유 파일 — 통과
if [ -z "$OWNER_TASK" ]; then
  exit 0
fi

# 메인 세션(오케스트레이터)에서 소유된 파일을 편집하려 하면 차단
# 오케스트레이터는 코드를 직접 작성하지 않아야 한다
echo "파일 소유권 위반: $REL_PATH 는 $OWNER_TASK 소유입니다. 오케스트레이터에서 직접 편집할 수 없습니다. Engineer Agent를 통해 수정하세요." >&2
exit 2
