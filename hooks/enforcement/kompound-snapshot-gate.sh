#!/bin/bash
# enforcement/kompound-snapshot-gate.sh — PreToolUse (Bash)
#
# T2 안전망 게이트 (spec F2, arch §5.2). 공유 worktree를
# `git worktree remove`나 `rm -r`/`rm -f`/`--recursive`로 지우기 전에, 그
# 워크트리 안에 아직 kompound(로컬 LLM Wiki)에 박제(snapshot)되지 않은 SDD
# 산출물(spec/arch/ui/api/context/result)이 있는지 판정한다.
#
# 판정·박제·정책 로직은 전부 hooks/lib/kompound_snapshot/ 코어(Python,
# stdlib-only, arch §1 "단일 판정 구현" / CLAUDE.md "결정↔판단 분리")에
# 있다. 이 스크립트는 그 코어를 서브프로세스로 호출해 JSON을 소비할 뿐이고,
# 스캔·네이밍·dedup·판정 로직을 복제하지 않는다.
#
# 🔴 차단 여부는 이 스크립트가 재유도하지 않는다 — 코어가 반환한 verdict를
# `report.blocks_deletion(verdict)`에 그대로 물어서 따른다(A-5 3축 원칙).
# "exit code == 0이면 통과, 그 외는 차단"으로 자체 판단하면
# verify_failed(50)·catalog_unparsed(55)(카탈로그만 실패, raw는 이미 kompound
# 에 보존됨)까지 차단해버리는 함정에 빠진다 — 이게 이 사이클 arch 리뷰가
# 잡아낸 최대 결함(A-5)이었다(F8 게이트 실패가 워크트리 삭제를 막던 원래
# 함정으로의 회귀).
#
# 골격은 worktree-add-gate.sh와 동일: lib/constants.sh·lib/logging.sh 소싱 →
# INPUT 파싱 → tool_name/command 확인 → 관련 명령만 처리 → gate_block/
# gate_pass. worktree-add-gate.sh(git add/checkout/switch만 처리)와 상호
# 간섭 없음 — 이 게이트는 git worktree remove/rm -r/-f/--recursive만 본다.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/constants.sh"
source "$SCRIPT_DIR/lib/logging.sh"

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')
[ "$TOOL_NAME" != "Bash" ] && exit 0

COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
[ -z "$COMMAND" ] && exit 0

# ── 저렴한 프리필터 (arch §5.2.2, 비용 상한 <5ms) ───────────────────────
# 워크트리 삭제류로 "보이는" 명령만 python을 기동한다. 이 정도의 텍스트
# 검사만 한다 — "실제로 워크트리인가"의 사실 판정(코어 wt_target.py 몫)은
# 여기서 하지 않는다.
case "$COMMAND" in
  *worktree*remove*|*rm\ -r*|*rm\ -f*|*--recursive*)
    ;;  # 계속 진행
  *)
    exit 0 ;;
esac

# ── python3 부재 — 인프라 실패, 경고 후 통과 ────────────────────────────
# (기능이 고장났다고 사용자가 워크트리를 영구히 못 지우게 되면 안 된다.)
if ! command -v python3 >/dev/null 2>&1; then
  gate_warn "KOMPOUND-SNAPSHOT-GATE" "python3을 찾을 수 없어 kompound 박제 판정을 건너뜁니다(인프라 실패) — 통과"
  gate_pass "KOMPOUND-SNAPSHOT-GATE" "python3 부재로 통과: $COMMAND"
  exit 0
fi

# ── PYTHONPATH — 이 스크립트 위치 기준으로 플러그인 루트를 유도한다 ─────
# hooks/enforcement/<this>.sh → 두 단계 위 = hooks/의 부모 = 플러그인 루트
# (hooks.lib.kompound_snapshot 패키지가 물리적으로 있는 곳). 설치형 배포에서
# 플러그인 루트와 "프로젝트"(CLAUDE_PROJECT_DIR/HARNESS_PROJECT_ROOT)가
# 다를 수 있으므로 constants.sh의 HARNESS_PROJECT_ROOT는 재사용하지 않는다
# (그건 config/runtime_state 조회용 "프로젝트" 컨텍스트지, 코어 코드 위치가
# 아니다 — arch/task에 없어 이 스크립트가 직접 결정).
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# ── 코어 호출 (arch §5.2.1) — 판정 로직을 복제하지 않고 서브프로세스로 위임 ──
# stderr는 버린다: 사람용 텍스트(human)·승계 경고(inherited_warning)는 JSON
# 필드로도 동일하게 오므로(emit_report 계약), 아래에서 JSON을 통해 그대로
# 재구성한다.
STDOUT_JSON=$(PYTHONPATH="$PLUGIN_ROOT${PYTHONPATH:+:$PYTHONPATH}" \
  python3 -m hooks.lib.kompound_snapshot gate --command "$COMMAND" --json 2>/dev/null)
PY_EXIT=$?

# ── JSON 파싱 실패 = 코어 응답 계약 위반/인프라 실패 → 경고 후 통과 ─────
if ! echo "$STDOUT_JSON" | jq -e . >/dev/null 2>&1; then
  gate_warn "KOMPOUND-SNAPSHOT-GATE" "코어 응답을 JSON으로 파싱하지 못했습니다(exit=$PY_EXIT) — 인프라 실패로 간주해 통과합니다"
  gate_pass "KOMPOUND-SNAPSHOT-GATE" "JSON 파싱 실패로 통과: $COMMAND"
  exit 0
fi

VERDICT=$(echo "$STDOUT_JSON" | jq -r '.verdict // empty')
HUMAN=$(echo "$STDOUT_JSON" | jq -r '.human // empty')
INHERITED_KIND=$(echo "$STDOUT_JSON" | jq -r '.inherited_warning.kind // empty')
INHERITED_TEXT=$(echo "$STDOUT_JSON" | jq -r '.inherited_warning.text // empty')

if [ -z "$VERDICT" ]; then
  gate_warn "KOMPOUND-SNAPSHOT-GATE" "코어 응답에 verdict 필드가 없습니다(exit=$PY_EXIT) — 계약 위반으로 간주해 통과합니다"
  gate_pass "KOMPOUND-SNAPSHOT-GATE" "verdict 없음으로 통과: $COMMAND"
  exit 0
fi

# ── 종료 코드 계약 검사 (arch §5.2.3 "그 외 종료 코드" 분기) ────────────
# gate 서브커맨드가 반환할 수 없는 코드(특히 exit 10=pending은 check 전용,
# 1/2는 report.py 예약)가 나오면 계약 위반으로 간주해 경고 후 통과한다.
case "$PY_EXIT" in
  0|20|30|40|45|50|55|60|70) ;;  # report.VERDICT_TABLE이 gate에 허용하는 종료 코드(10 제외)
  *)
    gate_warn "KOMPOUND-SNAPSHOT-GATE" "코어가 gate 계약 밖의 종료 코드(exit=$PY_EXIT, verdict=$VERDICT)를 반환했습니다 — 계약 위반으로 간주해 통과합니다"
    gate_pass "KOMPOUND-SNAPSHOT-GATE" "계약 위반 종료 코드로 통과: $COMMAND"
    exit 0
    ;;
esac

# ── T1→T2 실패/지연 승계 노출 (A-2) — verdict 판정과 무관하게 항상 먼저 ──
# (코어가 이미 소비/기록을 마쳤다 — 이 스크립트는 있으면 보여주기만 한다.)
if [ "$INHERITED_KIND" = "failure" ]; then
  gate_warn "KOMPOUND-SNAPSHOT-GATE" "[T1 실패 승계] $INHERITED_TEXT"
elif [ "$INHERITED_KIND" = "info" ]; then
  gate_warn "KOMPOUND-SNAPSHOT-GATE" "[T1 카탈로그 지연 승계] $INHERITED_TEXT"
fi

# ── 정책 조회 (arch A-5, 🔴 핵심) — report.blocks_deletion(verdict) ─────
# bash는 verdict 목록을 하드코딩하지 않는다: 새 verdict가 추가돼도 이 조회
# 한 줄이 그대로 맞다(report.py가 단일 진실).
BLOCKS=$(PYTHONPATH="$PLUGIN_ROOT${PYTHONPATH:+:$PYTHONPATH}" python3 -c '
import sys
from hooks.lib.kompound_snapshot import report
sys.stdout.write("1" if report.blocks_deletion(sys.argv[1]) else "0")
' "$VERDICT" 2>/dev/null)

if [ "$BLOCKS" != "0" ] && [ "$BLOCKS" != "1" ]; then
  # 정책 조회 자체가 실패 — report.py의 fail-safe 철학(모르면 보수적으로
  # 차단, F11 정신)과 동일하게 여기서도 보수적으로 차단한다.
  gate_block "KOMPOUND-SNAPSHOT-GATE" \
    "정책 조회(report.blocks_deletion)에 실패해 verdict='$VERDICT'의 안전성을 확인하지 못했습니다 — 보수적으로 차단합니다" \
    "다시 시도하거나, 이 기능이 필요 없다면 HARNESS_KOMPOUND_REPO 환경변수를 비워서 끄세요"
  exit 2
fi

if [ "$BLOCKS" = "1" ]; then
  DETAIL=""
  case "$VERDICT" in
    precondition_failed)
      DIRTY=$(echo "$STDOUT_JSON" | jq -r '(.dirty // []) | join(", ")')
      [ -n "$DIRTY" ] && DETAIL=" — dirty: $DIRTY"
      ;;
    unmapped_blocking)
      UNMAPPED=$(echo "$STDOUT_JSON" | jq -r '(.unmapped // []) | join(", ")')
      [ -n "$UNMAPPED" ] && DETAIL=" — 미등록 프리픽스: $UNMAPPED"
      ;;
    write_failed)
      RAW_ERR=$(echo "$STDOUT_JSON" | jq -r '.raw_stage.error // empty')
      [ -n "$RAW_ERR" ] && DETAIL=" — $RAW_ERR"
      ;;
  esac
  gate_block "KOMPOUND-SNAPSHOT-GATE" "${HUMAN:-워크트리 삭제를 차단했습니다 ($VERDICT)}${DETAIL}" \
    "수동 절차: SDD 산출물(spec/arch/ui/api/result 등)을 marvelous_kompound의 raw/에 verbatim 복사하고 registry/index.md/log.md를 직접 갱신한 뒤 다시 시도하세요. 이 기능이 필요 없다면 HARNESS_KOMPOUND_REPO 환경변수를 비워서 끌 수 있습니다."
  exit 2
fi

# ── 통과 경로 — 전부 gate_pass를 거친다("조용한 통과" 금지, F2 acceptance) ──
case "$VERDICT" in
  snapshotted)
    SNAPSHOTTED=$(echo "$STDOUT_JSON" | jq -r '((.raw_stage.new // []) + (.raw_stage.updated // [])) | join(", ")')
    gate_warn "KOMPOUND-SNAPSHOT-GATE" "박제된 문서: ${SNAPSHOTTED:-(목록 없음)}"
    ;;
  verify_failed|catalog_unparsed)
    gate_warn "KOMPOUND-SNAPSHOT-GATE" "${HUMAN:-카탈로그 갱신 실패 — raw는 보존됨 ($VERDICT)}"
    ;;
  disabled)
    # F16 "안내 1회" — 코어가 반복 노출을 억제할 땐 human이 빈 문자열로 온다.
    [ -n "$HUMAN" ] && gate_warn "KOMPOUND-SNAPSHOT-GATE" "$HUMAN"
    ;;
esac

gate_pass "KOMPOUND-SNAPSHOT-GATE" "${HUMAN:-통과 ($VERDICT)}: $COMMAND"
exit 0
