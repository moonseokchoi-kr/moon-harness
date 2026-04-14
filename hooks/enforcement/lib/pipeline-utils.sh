#!/bin/bash
# enforcement/lib/pipeline-utils.sh
# pipeline.json 조작 헬퍼 — sdd 스킬에서 source 해서 사용한다.
#
# 사용법:
#   source "$HARNESS_HOOKS/enforcement/lib/pipeline-utils.sh"
#   init_pipeline "modal-system" "FULL"
#   set_waiting_for_user "true" "arch"
#   advance_label "PHASE2_ARCH_STRUCTURE_DONE"

# bash/zsh 호환 SCRIPT_DIR 계산
if [ -n "${BASH_SOURCE-}" ] && [ -n "${BASH_SOURCE[0]-}" ]; then
  _PIPELINE_UTILS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
elif [ -n "${ZSH_VERSION-}" ]; then
  _PIPELINE_UTILS_DIR="$(cd "$(dirname "${(%):-%x}")" && pwd)"
else
  _PIPELINE_UTILS_DIR="$(cd "$(dirname "$0")" && pwd)"
fi
source "$_PIPELINE_UTILS_DIR/constants.sh"

# ─── 시간 ──────────────────────────────────────────────────────

_now_iso() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

# ─── pipeline.json 초기화 ─────────────────────────────────────
# 사용: init_pipeline <feature> <mode:FULL|SIMPLE>
init_pipeline() {
  local feature="$1"
  local mode="${2:-SIMPLE}"

  if [ -z "$feature" ]; then
    echo "[pipeline-utils] feature 이름 필수" >&2
    return 1
  fi

  mkdir -p "$HARNESS_STATE_DIR"

  local session_id="${CLAUDE_SESSION_ID:-$(uuidgen 2>/dev/null || echo "sess-$(date +%s)")}"

  python3 -c "
import json, sys
from datetime import datetime, timezone, timedelta

now = datetime.now(timezone.utc).isoformat()
reset_at = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()

state = {
    'schema_version': 1,
    'feature': '$feature',
    'mode': '$mode',
    'session_id': '$session_id',
    'worktree_path': '',
    'current_label': 'PHASE1_UX_RESEARCH_DONE',
    'waiting_for_user': False,
    'waiting_for_approval_type': None,
    'last_action_directive': '',
    'circuit_breaker': {
        'blocks': 0,
        'max_blocks': 20,
        'reset_at': reset_at,
    },
    'created_at': now,
    'last_updated': now,
}

with open('$HARNESS_PIPELINE_STATE', 'w') as f:
    json.dump(state, f, indent=2, ensure_ascii=False)
"
  echo "[pipeline] ✓ 초기화 완료: $feature ($mode)"
}

# ─── 라벨 전환 ────────────────────────────────────────────────
# 사용: advance_label <new_label>
advance_label() {
  local new_label="$1"
  [ -z "$new_label" ] && return 1
  [ ! -f "$HARNESS_PIPELINE_STATE" ] && return 1

  python3 -c "
import json
with open('$HARNESS_PIPELINE_STATE') as f: s = json.load(f)
s['current_label'] = '$new_label'
s['last_updated'] = '$(_now_iso)'
s['waiting_for_user'] = False
s['waiting_for_approval_type'] = None
with open('$HARNESS_PIPELINE_STATE', 'w') as f: json.dump(s, f, indent=2, ensure_ascii=False)
"
}

# ─── 사용자 게이트 설정 ───────────────────────────────────────
# 사용: set_waiting_for_user <true|false> <approval_type>
set_waiting_for_user() {
  local waiting="$1"
  local approval_type="${2:-null}"
  [ ! -f "$HARNESS_PIPELINE_STATE" ] && return 1

  python3 -c "
import json
with open('$HARNESS_PIPELINE_STATE') as f: s = json.load(f)
s['waiting_for_user'] = ('$waiting' == 'true')
s['waiting_for_approval_type'] = None if '$approval_type' == 'null' else '$approval_type'
s['last_updated'] = '$(_now_iso)'
with open('$HARNESS_PIPELINE_STATE', 'w') as f: json.dump(s, f, indent=2, ensure_ascii=False)
"
}

# ─── worktree 경로 설정 ───────────────────────────────────────
set_worktree_path() {
  local path="$1"
  [ ! -f "$HARNESS_PIPELINE_STATE" ] && return 1

  python3 -c "
import json
with open('$HARNESS_PIPELINE_STATE') as f: s = json.load(f)
s['worktree_path'] = '$path'
s['last_updated'] = '$(_now_iso)'
with open('$HARNESS_PIPELINE_STATE', 'w') as f: json.dump(s, f, indent=2, ensure_ascii=False)
"
}

# ─── 파이프라인 종료 ──────────────────────────────────────────
cancel_pipeline() {
  if [ -f "$HARNESS_PIPELINE_STATE" ]; then
    rm -f "$HARNESS_PIPELINE_STATE"
    echo "[pipeline] ✓ 종료됨"
  else
    echo "[pipeline] · 활성 파이프라인 없음"
  fi
}

# ─── 현재 상태 조회 ───────────────────────────────────────────
show_pipeline() {
  if [ ! -f "$HARNESS_PIPELINE_STATE" ]; then
    echo "[pipeline] · 비활성"
    return 0
  fi

  python3 -c "
import json
with open('$HARNESS_PIPELINE_STATE') as f: s = json.load(f)
print(f\"  feature: {s.get('feature')}\")
print(f\"  mode:    {s.get('mode')}\")
print(f\"  label:   {s.get('current_label')}\")
print(f\"  waiting: {s.get('waiting_for_user')} ({s.get('waiting_for_approval_type') or '-'})\")
print(f\"  blocks:  {s.get('circuit_breaker', {}).get('blocks', 0)}/20\")
"
}
