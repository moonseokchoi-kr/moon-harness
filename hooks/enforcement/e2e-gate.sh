#!/bin/bash
# enforcement/e2e-gate.sh — PreToolUse (Bash)
#
# git commit 시 변경된 feature 파일에 대응하는 E2E 파일 존재 여부 확인.
# 이유: E2E 테스트 없는 기능은 통합 수준의 회귀를 잡을 수 없다.
#       커밋 시점에 강제함으로써 "나중에 쓰겠다"는 미루기를 차단한다.
# 대안: e2e/ 디렉토리에 대응하는 스펙 파일을 먼저 작성하라.
#       특정 파일이 E2E 불필요하면 e2e-config.json의 exempt에 추가하라.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/constants.sh"
source "$SCRIPT_DIR/lib/logging.sh"
source "$SCRIPT_DIR/lib/state-reader.sh"

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')
[ "$TOOL_NAME" != "Bash" ] && exit 0

COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
[ -z "$COMMAND" ] && exit 0

# git commit 명령만 처리
case "$COMMAND" in
  *git\ commit*) ;;
  *) exit 0 ;;
esac

# e2e-config.json 없거나 비활성화면 통과
E2E_ENABLED=$(read_e2e_enabled)
[ "$E2E_ENABLED" != "true" ] && exit 0

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"

# staged 파일 목록 가져오기
STAGED_FILES=$(git -C "$PROJECT_DIR" diff --cached --name-only 2>/dev/null)
[ -z "$STAGED_FILES" ] && exit 0

# e2e-config.json에서 패턴과 exempt 읽기
E2E_TEST_DIR=$(jq -r '.test_dir // "e2e/"' "$HARNESS_E2E_CONFIG" 2>/dev/null)
EXEMPT_PATTERNS=$(jq -r '.exempt[]? // empty' "$HARNESS_E2E_CONFIG" 2>/dev/null)

MISSING_E2E=()

while IFS= read -r file; do
  # 테스트 파일 자체는 건너뜀
  case "$file" in
    *test*|*spec*|*e2e*|*.md|*.json|*.yaml|*.yml|*.lock|*.sh)
      continue ;;
  esac

  # exempt 패턴 확인
  EXEMPTED=false
  while IFS= read -r pattern; do
    [ -z "$pattern" ] && continue
    # glob 매칭 (bash extglob 없이 단순 패턴)
    pattern_clean="${pattern//\*\*/.*}"
    pattern_clean="${pattern_clean//\*/[^/]*}"
    if echo "$file" | grep -qE "^${pattern_clean}$" 2>/dev/null; then
      EXEMPTED=true
      break
    fi
  done <<< "$EXEMPT_PATTERNS"
  [ "$EXEMPTED" = "true" ] && continue

  # source 파일인지 확인 (src/, app/, lib/ 하위)
  case "$file" in
    src/*|app/*|lib/*|pages/*|components/*|features/*)
      ;;
    *)
      continue ;;
  esac

  # 파일명에서 basename 추출 (확장자 제거)
  BASENAME=$(basename "$file")
  NAME="${BASENAME%.*}"

  # 대응하는 E2E 파일이 존재하는지 확인
  E2E_EXISTS=false

  # staged 파일 중 대응 E2E 파일이 있는가?
  while IFS= read -r staged; do
    case "$staged" in
      *"$NAME"*spec*|*"$NAME"*e2e*|*"$NAME"*test*)
        case "$staged" in
          "$E2E_TEST_DIR"*|*e2e*|*cypress*|*playwright*)
            E2E_EXISTS=true
            break ;;
        esac ;;
    esac
  done <<< "$STAGED_FILES"

  # 이미 존재하는 E2E 파일이 있는가? (이전에 작성된 것)
  if [ "$E2E_EXISTS" = "false" ]; then
    if find "$PROJECT_DIR/$E2E_TEST_DIR" -name "*${NAME}*" 2>/dev/null | grep -q .; then
      E2E_EXISTS=true
    fi
  fi

  if [ "$E2E_EXISTS" = "false" ]; then
    MISSING_E2E+=("$file")
  fi
done <<< "$STAGED_FILES"

# E2E 파일 누락이 없으면 통과
[ ${#MISSING_E2E[@]} -eq 0 ] && exit 0

# 누락된 파일 목록 출력 후 차단
echo "" >&2
echo "[E2E-GATE] ✖ E2E 테스트 파일 누락" >&2
echo "  다음 파일에 대응하는 E2E 스펙이 없습니다:" >&2
for f in "${MISSING_E2E[@]}"; do
  BNAME=$(basename "$f")
  NAME="${BNAME%.*}"
  echo "    • $f  →  ${E2E_TEST_DIR}${NAME}.spec.ts" >&2
done
echo "" >&2
echo "  E2E 파일을 먼저 작성하거나," >&2
echo "  불필요한 경우 .claude/state/e2e-config.json의 exempt에 추가하세요." >&2
echo "" >&2
exit 2
