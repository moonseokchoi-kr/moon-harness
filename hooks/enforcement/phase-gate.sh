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
CONTEXT_DIR="$PROJECT_DIR/docs/sdd/context"
SPEC_DIR="$PROJECT_DIR/docs/sdd/spec"
DESIGN_DIR="$PROJECT_DIR/docs/sdd/design"
TASK_DIR="$PROJECT_DIR/docs/sdd/task"
ORCH_STATE="$PROJECT_DIR/docs/sdd/ORCHESTRATOR_STATE.md"

# context 문서가 없으면 SDD 미시작 — 조용히 종료
[ ! -d "$CONTEXT_DIR" ] && [ ! -d "$SPEC_DIR" ] && exit 0

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

# Phase 2: design 존재 여부
if [ -d "$DESIGN_DIR" ]; then
  HAS_ARCH=false
  HAS_UI=false
  HAS_API=false

  ls "$DESIGN_DIR"/arch*/*.md "$DESIGN_DIR"/arch*.md &>/dev/null 2>&1 && HAS_ARCH=true
  ls "$DESIGN_DIR"/ui*/*.md "$DESIGN_DIR"/ui*.md &>/dev/null 2>&1 && HAS_UI=true
  ls "$DESIGN_DIR"/api*/*.md "$DESIGN_DIR"/api*.md &>/dev/null 2>&1 && HAS_API=true

  if [ "$HAS_ARCH" = "true" ]; then
    PHASE="2_done"
  fi
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
  "2_done"|"3_done")
    # Phase 2 완료됐는데 spec이 없으면 이상
    if [ ! -d "$SPEC_DIR" ] || ! ls "$SPEC_DIR"/*.md &>/dev/null 2>&1; then
      WARNINGS+=("Phase 2 산출물이 있지만 Phase 1 spec이 없습니다")
    fi
    ;;
  "3_done")
    # Phase 3 완료됐는데 design이 없으면 이상
    if [ ! -d "$DESIGN_DIR" ] || ! ls "$DESIGN_DIR"/arch*/*.md "$DESIGN_DIR"/arch*.md &>/dev/null 2>&1; then
      WARNINGS+=("Phase 3 태스크가 있지만 Phase 2 architecture 설계 문서가 없습니다")
    fi
    ;;
  "4_active")
    # Phase 4 활성인데 task 문서가 없으면 경고
    if [ ! -d "$TASK_DIR" ] || ! ls "$TASK_DIR"/*/T-*.md "$TASK_DIR"/T-*.md &>/dev/null 2>&1; then
      WARNINGS+=("ORCHESTRATOR_STATE.md가 있지만 태스크 문서(T-*.md)가 없습니다")
    fi
    ;;
esac

# E2E 커버리지 계획 검증 — Phase 무관, UI 명세가 있으면 항상 확인
if [ -d "$DESIGN_DIR/ui" ] && ls "$DESIGN_DIR/ui"/*.md &>/dev/null 2>&1; then
  if [ ! -f "$HARNESS_E2E_CONFIG" ]; then
    WARNINGS+=("UI 명세가 있지만 .claude/state/e2e-config.json이 없습니다 — sdd-ui-designer Step 5(E2E 커버리지 계획)가 누락됐을 수 있습니다")
  else
    E2E_ENABLED=$(jq -r '.enabled // false' "$HARNESS_E2E_CONFIG" 2>/dev/null)
    if [ "$E2E_ENABLED" != "true" ]; then
      WARNINGS+=("e2e-config.json이 비활성(enabled: false)입니다 — E2E 커버리지 계획을 검토하세요")
    fi
  fi
fi

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
