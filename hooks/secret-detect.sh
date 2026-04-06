#!/bin/bash
# Moon Harness Hook S1: Secret Detection
# Event: PreToolUse (Bash)
# Scans commands for hardcoded secrets before execution

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

[ -z "$COMMAND" ] && exit 0

# Secret patterns
PATTERNS=(
  'sk-[a-zA-Z0-9]{20,}'          # OpenAI API key
  'ghp_[a-zA-Z0-9]{36}'          # GitHub personal access token
  'gho_[a-zA-Z0-9]{36}'          # GitHub OAuth token
  'AKIA[0-9A-Z]{16}'             # AWS access key
  'xoxb-[0-9]+-[a-zA-Z0-9]+'    # Slack bot token
  'sk_live_[a-zA-Z0-9]+'         # Stripe live key
)

for pattern in "${PATTERNS[@]}"; do
  if echo "$COMMAND" | grep -qE "$pattern"; then
    MATCHED=$(echo "$COMMAND" | grep -oE "$pattern" | head -1)
    REDACTED="${MATCHED:0:6}...${MATCHED: -4}"
    echo "⚠️ 시크릿 패턴 감지: $REDACTED" >&2
    echo "API 키나 토큰을 명령어에 직접 포함하지 마세요." >&2
    echo "환경변수(.env)를 사용하고, .env는 .gitignore에 포함하세요." >&2
    exit 2
  fi
done

# Check for git add of sensitive files
if echo "$COMMAND" | grep -qE 'git (add|commit)'; then
  if echo "$COMMAND" | grep -qE '\.(env|pem|key|cert|p12|pfx)'; then
    echo "⚠️ 민감 파일 커밋 시도 감지" >&2
    echo ".env, .pem, .key 파일은 .gitignore에 포함하세요." >&2
    exit 2
  fi
fi

exit 0
