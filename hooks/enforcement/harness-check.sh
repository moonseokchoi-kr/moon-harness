#!/bin/bash
# enforcement/harness-check.sh — SessionStart
#
# 프로젝트에 harness가 설정되어 있는지 확인한다.
# harness가 없는 실제 프로젝트라면 Claude에게 /harness 즉시 실행을 지시한다.
#
# harness 설정 여부 판단:
#   - .claude/hooks/harness/ 존재 → harness 스킬이 설치한 훅
#   - docs/architecture.md 존재  → harness 스킬이 생성한 핵심 문서

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"

# ─── harness 이미 설정됨 ────────────────────────────────────
[ -d "$PROJECT_DIR/.claude/hooks/harness" ] && exit 0
[ -f "$PROJECT_DIR/docs/architecture.md" ]  && exit 0

# ─── moon-harness 자체는 제외 ───────────────────────────────
if [ -f "$PROJECT_DIR/setup.sh" ]; then
  grep -q "Moon Harness" "$PROJECT_DIR/setup.sh" 2>/dev/null && exit 0
fi

# ─── 실제 프로젝트인지 확인 ─────────────────────────────────
IS_PROJECT=false

for indicator in package.json Cargo.toml pyproject.toml go.mod pom.xml build.gradle pubspec.yaml; do
  [ -f "$PROJECT_DIR/$indicator" ] && IS_PROJECT=true && break
done

if [ "$IS_PROJECT" = "false" ]; then
  for dir in src app lib packages; do
    [ -d "$PROJECT_DIR/$dir" ] && IS_PROJECT=true && break
  done
fi

[ "$IS_PROJECT" = "false" ] && exit 0

# ─── harness 미설정 → 즉시 실행 지시 ───────────────────────
cat >&2 <<'EOF'

[HARNESS-CHECK] 이 프로젝트에 harness가 설정되어 있지 않습니다.

harness가 없으면 에이전트가 아키텍처 규칙, 문서 구조, 훅 없이
작동하여 품질이 보장되지 않습니다.

지금 즉시 Skill(harness)을 실행하여 이 프로젝트를 구성하세요.
사용자가 다른 요청을 했더라도 harness 설정을 먼저 수행해야 합니다.

EOF

exit 0
