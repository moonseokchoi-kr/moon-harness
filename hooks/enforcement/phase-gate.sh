#!/bin/bash
# enforcement/phase-gate.sh — SessionStart
#
# 세션 시작 시 Phase 진입 선행조건을 진단하고 경고한다.
# 차단하지 않고 경고만 출력한다 (SessionStart는 exit 2도 세션 중단 불가).
# 이유: Phase를 건너뛰면 불완전한 산출물 위에 다음 Phase가 쌓인다.
#       조기 발견이 나중 재작업보다 훨씬 저렴하다.
#
# 대체된 텍스트 규칙: skills/spec-design/SKILL.md HARD-GATE 섹션

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/constants.sh"
source "$SCRIPT_DIR/lib/logging.sh"
source "$SCRIPT_DIR/lib/init-state.sh"

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"

# 상태 파일 초기화 (없으면 생성)
init_state_dir

# Spec-Design 문서 경로 (skills/spec-design/SKILL.md 구조 기준)
SPEC_DIR="$PROJECT_DIR/docs/spec-design/spec"
DESIGN_DIR="$PROJECT_DIR/docs/spec-design/design"

# spec 문서가 없으면 Spec-Design 미시작 — 조용히 종료
[ ! -d "$SPEC_DIR" ] && exit 0

# Phase 판정
PHASE=""
WARNINGS=()

# Phase 1: spec 존재 여부
if [ -d "$SPEC_DIR" ] && ls "$SPEC_DIR"/*.md &>/dev/null 2>&1; then
  PHASE="1_done"
else
  PHASE="0"
fi

# Phase 2: design/arch 존재 여부
if [ -d "$DESIGN_DIR/arch" ] && ls "$DESIGN_DIR/arch"/*.md &>/dev/null 2>&1; then
  PHASE="2_arch_done"
fi

# Phase별 선행조건 검증
case "$PHASE" in
  "2_arch_done")
    # Phase 2 arch 있는데 spec이 없으면 이상
    if [ ! -d "$SPEC_DIR" ] || ! ls "$SPEC_DIR"/*.md &>/dev/null 2>&1; then
      WARNINGS+=("Phase 2 아키텍처 산출물이 있지만 Phase 1 spec이 없습니다")
    fi
    ;;
esac

# UI 문서가 있는데 IA 문서가 없으면 경고
if [ -d "$DESIGN_DIR/ui" ] && ls "$DESIGN_DIR/ui"/*.md &>/dev/null 2>&1; then
  if [ ! -d "$DESIGN_DIR/ia" ] || ! ls "$DESIGN_DIR/ia"/*.md &>/dev/null 2>&1; then
    WARNINGS+=("UI 명세가 있지만 IA 문서(docs/spec-design/design/ia/)가 없습니다 — ia-designer 단계가 누락됐을 수 있습니다")
  fi
fi

# pipeline.json 에 bundle_path 지정됐는데 디렉토리 비었으면 경고
if [ -f "$HARNESS_PIPELINE_STATE" ]; then
  BUNDLE_PATH=$(jq -r '.bundle_path // ""' "$HARNESS_PIPELINE_STATE" 2>/dev/null)
  if [ -n "$BUNDLE_PATH" ] && [ -d "$BUNDLE_PATH" ]; then
    if ! find "$BUNDLE_PATH" -maxdepth 2 -name "*.html" -print -quit | grep -q .; then
      WARNINGS+=("Claude Design 번들 경로가 지정됐지만 HTML 파일이 없습니다: $BUNDLE_PATH")
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
  echo "  /spec-design 스킬로 현재 Phase를 확인하세요" >&2
  echo "" >&2
fi

exit 0
