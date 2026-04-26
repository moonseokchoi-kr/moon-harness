#!/bin/bash
# enforcement/lib/constants.sh
# 모든 gate 훅에서 공유하는 경로 상수

# 프로젝트 루트 (훅 실행 시 cwd가 프로젝트 루트임)
HARNESS_PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-.}"

# 상태 파일 디렉토리
HARNESS_STATE_DIR="$HARNESS_PROJECT_ROOT/.harness/state"

# 상태 파일 경로
HARNESS_AGENT_CONTEXT="$HARNESS_STATE_DIR/agent-context.json"
HARNESS_PIPELINE_STATE="$HARNESS_STATE_DIR/pipeline.json"

# 판정 캐시
HARNESS_CACHE_TTL=5  # 초
HARNESS_CACHE_DIR="/tmp/harness-gate-cache-${CLAUDE_PROJECT_DIR//\//-}"
