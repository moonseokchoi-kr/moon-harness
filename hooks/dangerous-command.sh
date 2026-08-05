#!/bin/bash
# Moon Harness Hook S2: Dangerous Command Warning
# Event: PreToolUse (Bash)
# Warns before destructive operations
#
# heredoc 본문 처리 — 명령 문자열만 보고 판단하면 **문서로 적힌** 파괴적 명령을
# 실제 명령으로 오인한다(2026-08-05 엔트리: 교훈 문서를 heredoc으로 append하는
# 것 자체가 차단됐고, 이 스크립트를 heredoc으로 재작성하는 것도 차단됐다).
# 그래서 heredoc 본문을 판정에서 제외하되 **수신자를 확인**한다:
#
#   - `cat > file` / `tee` 등 **파일 쓰기 싱크**로 가는 본문 → 제외 (데이터다)
#   - `bash` / `sh` / `python3` 등 **인터프리터로 파이프되는** 본문 → 계속 검사
#     (제외하면 heredoc이 이 스크립트의 모든 검사를 우회하는 구멍이 된다)
#
# 판정 불가한 싱크는 **검사 유지**(보수적). 명령부는 heredoc 여부와 무관하게 항상 검사한다.
#
# 근거: .harness/LEARNING.md 2026-08-05 엔트리,
#       .harness/harness-proposals/2026-08-05-enforcement-hook-false-positive-fixes.md
#       (critic이 무조건 제외를 "모든 검사의 우회로 생성"으로 반박)

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

[ -z "$COMMAND" ] && exit 0

# ── heredoc 본문 절단 (파일 쓰기 싱크에 한해) ──────────────────────────────────
COMMAND=$(
  awk '
    function is_write_sink(line) {
      sub(/<<.*/, "", line)                       # heredoc 이전의 명령부만 본다
      if (line ~ /(^|[|;&[:space:]])(cat|tee|dd|sponge)([[:space:]]|$)/) return 1
      if (line ~ />[[:space:]]*[^|&[:space:]]+[[:space:]]*$/) return 1
      if (line ~ /(^|[|;&[:space:]])(ba)?sh([[:space:]]|$)/) return 0
      if (line ~ /(^|[|;&[:space:]])(zsh|ksh|dash|fish)([[:space:]]|$)/) return 0
      if (line ~ /(^|[|;&[:space:]])(python|python3|node|ruby|perl|php)([[:space:]-]|$)/) return 0
      if (line ~ /(^|[|;&[:space:]])(psql|mysql|sqlite3|jq|awk|sed)([[:space:]-]|$)/) return 0
      return 0                                    # 판정 불가 → 검사 유지
    }
    {
      if (skipping) {
        line = $0
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", line)
        if (line == delim) { skipping = 0 }
        next
      }
      if (match($0, /<<-?[[:space:]]*["'"'"']?[A-Za-z_][A-Za-z0-9_]*["'"'"']?/)) {
        d = substr($0, RSTART, RLENGTH)
        sub(/^<<-?[[:space:]]*/, "", d)
        gsub(/["'"'"']/, "", d)
        if (is_write_sink($0)) {
          head = $0                               # 명령부는 검사 대상으로 남긴다
          sub(/<<.*/, "", head)
          print head
          delim = d
          skipping = 1
          next
        }
      }
      print
    }
  ' <<< "$COMMAND"
)

[ -z "$COMMAND" ] && exit 0

# Safe rm -rf targets (don't warn for these)
SAFE_RM_TARGETS="node_modules|\.next|dist|build|\.cache|__pycache__|\.pytest_cache|target/debug|target/release"

# Check rm -rf (excluding safe targets)
if echo "$COMMAND" | grep -qE 'rm\s+(-[a-zA-Z]*r[a-zA-Z]*f|--recursive)\s' ; then
  if ! echo "$COMMAND" | grep -qE "rm\s+-rf\s+($SAFE_RM_TARGETS)"; then
    echo "⚠️ 재귀 삭제 명령 감지: rm -rf" >&2
    echo "삭제 대상이 맞는지 확인하세요. 안전 대상: node_modules, .next, dist, build" >&2
    exit 2
  fi
fi

# Check database destructive operations
if echo "$COMMAND" | grep -qiE '(DROP\s+(TABLE|DATABASE|INDEX)|TRUNCATE|DELETE\s+FROM\s+\w+\s*$)'; then
  echo "⚠️ DB 파괴 명령 감지" >&2
  echo "정말 실행하시겠습니까? 이 작업은 되돌릴 수 없습니다." >&2
  exit 2
fi

# Check git force operations
if echo "$COMMAND" | grep -qE 'git\s+push\s+.*--force|git\s+reset\s+--hard'; then
  echo "⚠️ Git 강제 작업 감지" >&2
  echo "force push나 hard reset은 히스토리를 파괴합니다. 정말 필요한지 확인하세요." >&2
  exit 2
fi

# Check pipe to shell (curl | bash pattern)
if echo "$COMMAND" | grep -qE 'curl\s.*\|\s*(ba)?sh|wget\s.*\|\s*(ba)?sh'; then
  echo "⚠️ 파이프 실행 감지: curl | sh" >&2
  echo "원격 스크립트를 직접 실행하는 것은 위험합니다. 먼저 내용을 확인하세요." >&2
  exit 2
fi

exit 0
