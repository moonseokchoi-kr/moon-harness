#!/bin/bash
# file-ownership.sh — PreToolUse 훅 (Edit, Write)
# 태스크별 파일 소유권을 강제하여 다른 태스크의 파일 편집을 차단한다.
# ORCHESTRATOR_STATE.md의 파일 소유권 섹션을 참조한다.
#
# 이 훅은 **상태파일 기반** enforcement다 — 권한을 repo 안의 상태 문서에서 끌어온다.
# 따라서 안전 게이트(secret-detect / sensitive-file)와 다른 규율을 따른다:
#
#   (1) 상태 문서의 라이프사이클 상태를 읽어 **활성 구간에서만** enforce한다.
#       완료·부재·해석 불가면 통과한다(fail-open — 조정 보조 장치이므로 차단측으로
#       실패하지 않는다).
#   (2) 표 컬럼은 **위치가 아니라 헤더 이름으로** 판별한다(레포마다 순서가 다르다).
#   (3) 매칭 대상을 **경로 형태 토큰**으로 한정하고 경계를 고정해 비교한다
#       (설명 산문의 단어가 경로로 매칭되면 안 된다).
#   (4) 대상 경로가 PROJECT_DIR 밖이면 즉시 통과한다.
#       ⚠️ (4)는 상태파일 기반 훅에만 적용된다 — secret-detect·sensitive-file 류
#       보안 훅은 레포 밖 쓰기(~/.ssh, ~/.aws)를 계속 검사해야 하므로 이 조항을
#       적용하지 않는다.
#
# 근거: .harness/LEARNING.md 2026-07-01 / 2026-08-05 엔트리 (독립 2신호),
#       .harness/harness-proposals/2026-08-05-enforcement-hook-false-positive-fixes.md

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

# ── (4) 레포 밖 경로는 즉시 통과 ───────────────────────────────────────────────
# 소유권은 이 repo의 상태 문서에서만 정의된다. 프로젝트 밖 절대경로
# (~/.claude/**, /private/tmp/** 스크래치패드 등)에 대해 소유권을 주장할 근거가 없다.
case "$FILE_PATH" in
  /*)
    # 절대경로 — PROJECT_DIR 접두가 아니면 레포 밖
    if [[ "$FILE_PATH" != "$PROJECT_DIR/"* ]]; then
      exit 0
    fi
    REL_PATH="${FILE_PATH#"$PROJECT_DIR"/}"
    ;;
  *)
    # 상대경로 — PROJECT_DIR 기준으로 간주
    REL_PATH="$FILE_PATH"
    ;;
esac

# `..` 로 레포를 벗어나는 경로도 통과 (소유권 주장 근거 없음)
case "/$REL_PATH/" in
  */../*) exit 0 ;;
esac

STATE_FILE="$PROJECT_DIR/docs/sdd/ORCHESTRATOR_STATE.md"

# 상태 파일이 없으면 오케스트레이션 모드가 아님 — 통과
if [ ! -f "$STATE_FILE" ]; then
  exit 0
fi

# 파일 소유권 섹션이 없으면 통과
if ! grep -q "## 파일 소유권" "$STATE_FILE"; then
  exit 0
fi

# ── (1) 라이프사이클 상태 게이트 (fail-open) ───────────────────────────────────
# 활성 구간(EXECUTING / PLANNING)에서만 enforce한다. SDD 사이클이 완료·머지되어
# STATE가 main에 남아 있으면 ownership enforcement가 영구히 살아 메인 세션의
# 정당한 편집을 차단한다(2026-07-01 엔트리). 상태를 못 읽으면 통과한다 —
# ownership은 안전 게이트가 아니라 조정 보조 장치이므로 차단측으로 실패하지 않는다.
STATUS_LINE=$(grep -m1 -E '^[[:space:]]*[-*]?[[:space:]]*(상태|status)[[:space:]]*:' "$STATE_FILE" 2>/dev/null || true)
if [ -z "$STATUS_LINE" ]; then
  exit 0  # 상태 표기 없음 → fail-open
fi
STATUS_UPPER=$(echo "$STATUS_LINE" | tr '[:lower:]' '[:upper:]')
if ! echo "$STATUS_UPPER" | grep -qE 'EXECUTING|PLANNING'; then
  exit 0  # COMPLETED / ABORTED / 해석 불가 → fail-open
fi

# 현재 에이전트의 태스크 ID 확인
# Agent 도구로 스폰된 서브에이전트는 agent_id가 있음
AGENT_ID=$(echo "$HOOK_DATA" | jq -r '.agent_id // empty')

# agent_id가 있으면 서브에이전트 — 오케스트레이터가 프롬프트로 소유 파일 목록을 전달하므로
# 이 훅은 추가 안전장치 역할. 서브에이전트는 통과시킨다.
if [ -n "$AGENT_ID" ]; then
  exit 0
fi

# ── 소유권 표 파싱 ────────────────────────────────────────────────────────────
# 섹션의 `|` 행만 뽑는다. 1행=헤더, 2행=구분선, 3행 이후=데이터.
OWNERSHIP_ROWS=$(sed -n '/## 파일 소유권/,/^## /p' "$STATE_FILE" | grep "^|" || true)
if [ -z "$OWNERSHIP_ROWS" ]; then
  exit 0
fi

HEADER=$(echo "$OWNERSHIP_ROWS" | head -n 1)

# ── (2) 헤더 이름으로 컬럼 판별 ────────────────────────────────────────────────
# `| 태스크 | 소유 파일 |`(태스크 먼저)과 `| 파일 경로 | 소유 태스크 |`(반대) 둘 다
# 실사용된다. 위치를 하드코딩하면 한쪽에서 설명 텍스트를 파일 목록으로 파싱한다.
TASK_COL=0
FILES_COL=0
COL_INDEX=0
while IFS= read -r cell; do
  COL_INDEX=$((COL_INDEX + 1))
  has_task=0; has_file=0
  case "$cell" in *태스크*|*Task*|*task*|*TASK*) has_task=1 ;; esac
  case "$cell" in *파일*|*경로*|*File*|*file*|*Path*|*path*) has_file=1 ;; esac
  # 양쪽 키워드를 다 가진 컬럼은 판별 불가로 간주해 무시한다
  if [ "$has_task" -eq 1 ] && [ "$has_file" -eq 0 ] && [ "$TASK_COL" -eq 0 ]; then
    TASK_COL=$COL_INDEX
  elif [ "$has_file" -eq 1 ] && [ "$has_task" -eq 0 ] && [ "$FILES_COL" -eq 0 ]; then
    FILES_COL=$COL_INDEX
  fi
done < <(echo "$HEADER" | sed 's/^|//; s/|$//' | tr '|' '\n')

# 컬럼을 특정하지 못하면 통과 (fail-open — 잘못된 컬럼으로 파싱해 오탐하는 것보다 낫다)
if [ "$TASK_COL" -eq 0 ] || [ "$FILES_COL" -eq 0 ]; then
  exit 0
fi

# ── (3) 경로 형태 토큰만 매칭 대상으로 삼고 경계를 고정해 비교 ─────────────────
# 소유 셀에는 경로 외에 설명 산문이 섞인다(위임 메모, 괄호 주석 등). 산문 토큰이
# 경로로 취급되면 무관한 파일이 차단된다. 특히 홀로 선 `/`는 부분문자열 매칭에서
# 모든 경로에 걸린다.
is_path_token() {
  local t="$1"
  # 경로에 쓰이지 않는 문자가 있으면 경로 아님 (CJK·공백·괄호·등호 등)
  case "$t" in
    *[!A-Za-z0-9._/@+-]*) return 1 ;;
  esac
  [ -z "$t" ] && return 1
  # 영숫자를 하나도 포함하지 않으면 경로 아님 (홀로 선 `/`, `--`, `...` 배제)
  case "$t" in
    *[A-Za-z0-9]*) ;;
    *) return 1 ;;
  esac
  # `/`를 포함하거나 확장자로 끝나야 경로로 인정
  case "$t" in
    */*) return 0 ;;
    *.[A-Za-z][A-Za-z]|*.[A-Za-z][A-Za-z][A-Za-z]|*.[A-Za-z][A-Za-z][A-Za-z][A-Za-z]) return 0 ;;
  esac
  return 1
}

OWNER_TASK=""
while IFS= read -r row; do
  task=$(echo "$row" | sed 's/^|//; s/|$//' | cut -d'|' -f"$TASK_COL" | xargs || true)
  files=$(echo "$row" | sed 's/^|//; s/|$//' | cut -d'|' -f"$FILES_COL" || true)

  # 구분선(|---|---|) 및 빈 행 건너뛰기
  case "$task" in ''|*---*) continue ;; esac
  [ -z "$files" ] && continue

  for owned in $files; do
    # 백틱·쉼표·인용부호 제거 + 괄호 주석 이후 절단
    owned="${owned%%(*}"
    owned=$(echo "$owned" | tr -d '`,"'"'" )
    owned="${owned%/}"   # 디렉토리 표기의 후행 슬래시 정규화

    is_path_token "$owned" || continue

    # 경계 고정 비교 — 정확히 같거나, 디렉토리 접두인 경우만
    if [ "$REL_PATH" = "$owned" ] || [[ "$REL_PATH" == "$owned"/* ]]; then
      OWNER_TASK="$task"
      break 2
    fi
  done
done < <(echo "$OWNERSHIP_ROWS" | tail -n +2)

# 소유자가 없으면 공유 파일 — 통과
if [ -z "$OWNER_TASK" ]; then
  exit 0
fi

# 메인 세션(오케스트레이터)에서 소유된 파일을 편집하려 하면 차단
# 오케스트레이터는 코드를 직접 작성하지 않아야 한다
echo "파일 소유권 위반: $REL_PATH 는 $OWNER_TASK 소유입니다. 오케스트레이터에서 직접 편집할 수 없습니다. Engineer Agent를 통해 수정하세요." >&2
exit 2
