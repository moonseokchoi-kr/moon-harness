#!/bin/bash
# enforcement/lib/pipeline-utils.sh
# pipeline.json 조작 헬퍼 — spec-design 스킬에서 source 해서 사용한다.
#
# 사용법:
#   source "$HARNESS_HOOKS/enforcement/lib/pipeline-utils.sh"
#   init_pipeline "modal-system" "WITH_UI"
#   set_waiting_for_user "true" "arch"
#   advance_label "PHASE2_ARCH_STRUCTURE_DONE"
#   set_visual_tool "claude-design"
#   inc_iteration

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
# 사용: init_pipeline <feature> <mode:WITH_UI|WITHOUT_UI>
# 레거시 호환: FULL → WITH_UI, SIMPLE → WITHOUT_UI
init_pipeline() {
  local feature="$1"
  local mode="${2:-WITHOUT_UI}"

  # 레거시 모드명 자동 변환
  case "$mode" in
    FULL)   mode="WITH_UI" ;;
    SIMPLE) mode="WITHOUT_UI" ;;
  esac

  # 유효성 검증
  case "$mode" in
    WITH_UI|WITHOUT_UI) ;;
    *)
      echo "[pipeline-utils] 유효하지 않은 mode: $mode (WITH_UI|WITHOUT_UI)" >&2
      return 1
      ;;
  esac

  if [ -z "$feature" ]; then
    echo "[pipeline-utils] feature 이름 필수" >&2
    return 1
  fi

  mkdir -p "$HARNESS_STATE_DIR"

  local session_id="${CLAUDE_SESSION_ID:-$(uuidgen 2>/dev/null || echo "sess-$(date +%s)")}"

  python3 -c "
import json
from datetime import datetime, timezone, timedelta

now = datetime.now(timezone.utc).isoformat()
reset_at = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()

state = {
    'schema_version': 2,
    'feature': '$feature',
    'mode': '$mode',
    'session_id': '$session_id',
    'worktree_path': '',
    'current_label': 'PHASE1_UX_RESEARCH_DONE',
    'waiting_for_user': False,
    'waiting_for_approval_type': None,
    'visual_tool': '',
    'ui_iteration': {'count': 0, 'max': 4},
    'bundle_path': '',
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

# ─── 시각 도구 설정 ───────────────────────────────────────────
# 사용: set_visual_tool <claude-design|stitch>
set_visual_tool() {
  local tool="$1"
  case "$tool" in
    claude-design|stitch) ;;
    *)
      echo "[pipeline-utils] 유효하지 않은 visual_tool: $tool (claude-design|stitch)" >&2
      return 1
      ;;
  esac
  [ ! -f "$HARNESS_PIPELINE_STATE" ] && return 1

  python3 -c "
import json
with open('$HARNESS_PIPELINE_STATE') as f: s = json.load(f)
s['visual_tool'] = '$tool'
s['last_updated'] = '$(_now_iso)'
with open('$HARNESS_PIPELINE_STATE', 'w') as f: json.dump(s, f, indent=2, ensure_ascii=False)
"
}

# ─── 번들 경로 설정 (Claude Design 모드) ──────────────────────
set_bundle_path() {
  local path="$1"
  [ ! -f "$HARNESS_PIPELINE_STATE" ] && return 1

  python3 -c "
import json
with open('$HARNESS_PIPELINE_STATE') as f: s = json.load(f)
s['bundle_path'] = '$path'
s['last_updated'] = '$(_now_iso)'
with open('$HARNESS_PIPELINE_STATE', 'w') as f: json.dump(s, f, indent=2, ensure_ascii=False)
"
}

# ─── iteration 카운터 ────────────────────────────────────────
# 사용: inc_iteration (반환: 새 count)
inc_iteration() {
  [ ! -f "$HARNESS_PIPELINE_STATE" ] && return 1
  python3 -c "
import json
with open('$HARNESS_PIPELINE_STATE') as f: s = json.load(f)
s.setdefault('ui_iteration', {'count': 0, 'max': 4})
s['ui_iteration']['count'] = s['ui_iteration'].get('count', 0) + 1
s['last_updated'] = '$(_now_iso)'
with open('$HARNESS_PIPELINE_STATE', 'w') as f: json.dump(s, f, indent=2, ensure_ascii=False)
print(s['ui_iteration']['count'])
"
}

reset_iteration() {
  [ ! -f "$HARNESS_PIPELINE_STATE" ] && return 1
  python3 -c "
import json
with open('$HARNESS_PIPELINE_STATE') as f: s = json.load(f)
s.setdefault('ui_iteration', {'count': 0, 'max': 4})
s['ui_iteration']['count'] = 0
s['last_updated'] = '$(_now_iso)'
with open('$HARNESS_PIPELINE_STATE', 'w') as f: json.dump(s, f, indent=2, ensure_ascii=False)
"
}

get_iteration() {
  [ ! -f "$HARNESS_PIPELINE_STATE" ] && echo "0" && return 0
  python3 -c "
import json
with open('$HARNESS_PIPELINE_STATE') as f: s = json.load(f)
print(s.get('ui_iteration', {}).get('count', 0))
"
}

get_visual_tool() {
  [ ! -f "$HARNESS_PIPELINE_STATE" ] && echo "" && return 0
  python3 -c "
import json
with open('$HARNESS_PIPELINE_STATE') as f: s = json.load(f)
print(s.get('visual_tool', ''))
"
}

get_bundle_path() {
  [ ! -f "$HARNESS_PIPELINE_STATE" ] && echo "" && return 0
  python3 -c "
import json
with open('$HARNESS_PIPELINE_STATE') as f: s = json.load(f)
print(s.get('bundle_path', ''))
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
print(f\"  feature:    {s.get('feature')}\")
print(f\"  mode:       {s.get('mode')}\")
print(f\"  label:      {s.get('current_label')}\")
print(f\"  visual:     {s.get('visual_tool') or '-'}\")
it = s.get('ui_iteration', {})
print(f\"  iteration:  {it.get('count', 0)}/{it.get('max', 4)}\")
bp = s.get('bundle_path', '')
print(f\"  bundle:     {bp or '-'}\")
print(f\"  waiting:    {s.get('waiting_for_user')} ({s.get('waiting_for_approval_type') or '-'})\")
print(f\"  blocks:     {s.get('circuit_breaker', {}).get('blocks', 0)}/20\")
"
}
