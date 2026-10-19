#!/bin/bash
# enforcement/phase-gate.sh — SessionStart
#
# 세션 시작 시 Phase 진입 선행조건을 진단하고 경고한다.
# 차단하지 않고 경고만 출력한다 (SessionStart는 exit 2도 세션 중단 불가).
# 이유: Phase를 건너뛰면 불완전한 산출물 위에 다음 Phase가 쌓인다.
#       조기 발견이 나중 재작업보다 훨씬 저렴하다.
#
# 대체된 텍스트 규칙: skills/sdd/SKILL.md HARD-GATE 섹션

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/constants.sh"
source "$SCRIPT_DIR/lib/logging.sh"
source "$SCRIPT_DIR/lib/init-state.sh"

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"

# 상태 파일 초기화 (없으면 생성)
init_state_dir

# SDD 문서 경로 (skills/sdd/SKILL.md 구조 기준)
SPEC_DIR="$PROJECT_DIR/docs/sdd/spec"
TASK_DIR="$PROJECT_DIR/docs/sdd/task"
ORCH_STATE="$PROJECT_DIR/docs/sdd/ORCHESTRATOR_STATE.md"

# spec 디렉터리가 없으면 SDD 미시작 — 조용히 종료
[ ! -d "$SPEC_DIR" ] && exit 0

# Phase 판정
PHASE=""
WARNINGS=()

# Phase 1: spec 존재 여부
if [ -d "$SPEC_DIR" ] && ls "$SPEC_DIR"/*.md &>/dev/null 2>&1; then
  PHASE="1_done"
else
  # spec도 없으면 Phase 1 미완료
  PHASE="0"
fi

# Phase 3: task 문서 존재 여부
if [ -d "$TASK_DIR" ] && ls "$TASK_DIR"/T-*.md &>/dev/null 2>&1; then
  PHASE="3_done"
fi

# Phase 4: ORCHESTRATOR_STATE.md 존재 여부
if [ -f "$ORCH_STATE" ]; then
  ORCH_STATUS=$(grep -m1 "^status:" "$ORCH_STATE" 2>/dev/null | awk '{print $2}' | tr -d '`')
  case "$ORCH_STATUS" in
    EXECUTING|PAUSED_AT_LIMIT|DONE) PHASE="4_active" ;;
  esac
fi

# Phase별 선행조건 검증
case "$PHASE" in
  "3_done")
    # Phase 3 산출물이 있는데 spec이 없으면 이상
    if [ ! -d "$SPEC_DIR" ] || ! ls "$SPEC_DIR"/*.md &>/dev/null 2>&1; then
      WARNINGS+=("Phase 3 산출물이 있지만 Phase 1 spec이 없습니다")
    fi
    ;;
  "4_active")
    # Phase 4 활성인데 task 문서가 없으면 경고
    if [ ! -d "$TASK_DIR" ] || ! ls "$TASK_DIR"/*/T-*.md "$TASK_DIR"/T-*.md &>/dev/null 2>&1; then
      WARNINGS+=("ORCHESTRATOR_STATE.md가 있지만 태스크 문서(T-*.md)가 없습니다")
    fi
    ;;
esac

# 경고 출력
if [ ${#WARNINGS[@]} -gt 0 ]; then
  echo "" >&2
  echo "[PHASE-GATE] ⚠ Phase 선행조건 경고" >&2
  for w in "${WARNINGS[@]}"; do
    echo "  • $w" >&2
  done
  echo "  /sdd 스킬로 현재 Phase를 확인하세요" >&2
  echo "" >&2
fi

exit 0
