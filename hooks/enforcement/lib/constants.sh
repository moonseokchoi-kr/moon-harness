#!/bin/bash
# enforcement/lib/constants.sh
# 모든 gate 훅에서 공유하는 경로 상수

# 프로젝트 루트 (훅 실행 시 cwd가 프로젝트 루트임)
HARNESS_PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-.}"

# ── 크로스플랫폼 경로 정규화 (Windows/Git-bash) ──────────────────────
# Git-bash(MSYS) 의 '/c/foo' 형식은 네이티브 Windows Python 의 open()/Path() 가
# 'C:\c\foo' 로 잘못 해석해 파일을 못 연다. cygpath 로 'C:/foo' 혼합형으로
# 정규화하고 CLAUDE_PROJECT_DIR 도 동일 형식으로 re-export 하여, 이 파일을
# source 하는 모든 bash 게이트와 그들이 띄우는 python -c 호출이 같은 경로를 본다.
# macOS/Linux 에는 cygpath 가 없어 자동으로 no-op(원래 POSIX 경로 유지)된다.
if command -v cygpath >/dev/null 2>&1; then
  HARNESS_PROJECT_ROOT="$(cygpath -m "$HARNESS_PROJECT_ROOT" 2>/dev/null || printf '%s' "$HARNESS_PROJECT_ROOT")"
  export CLAUDE_PROJECT_DIR="$HARNESS_PROJECT_ROOT"
fi

# 상태 파일 디렉토리
HARNESS_STATE_DIR="$HARNESS_PROJECT_ROOT/.claude/state"

# 상태 파일 경로
HARNESS_AGENT_CONTEXT="$HARNESS_STATE_DIR/agent-context.json"
HARNESS_TDD_STATE="$HARNESS_STATE_DIR/tdd-state.json"
HARNESS_E2E_CONFIG="$HARNESS_STATE_DIR/e2e-config.json"
HARNESS_ESCALATION_LOG="$HARNESS_STATE_DIR/escalation-log.jsonl"
HARNESS_PIPELINE_STATE="$HARNESS_STATE_DIR/pipeline.json"

# ORCHESTRATOR_STATE.md 경로 (skills/sdd/SKILL.md 구조 기준)
HARNESS_ORCH_STATE="$HARNESS_PROJECT_ROOT/docs/sdd/ORCHESTRATOR_STATE.md"

# 판정 캐시
HARNESS_CACHE_TTL=5  # 초
HARNESS_CACHE_DIR="/tmp/harness-gate-cache-${CLAUDE_PROJECT_DIR//\//-}"
