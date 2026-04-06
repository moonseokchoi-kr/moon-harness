#!/bin/bash
# Moon Harness Hook S3: Sensitive File Protection
# Event: PreToolUse (Edit|Write)
# Warns when modifying files that may contain secrets

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

[ -z "$FILE_PATH" ] && exit 0

# Sensitive file patterns
FILENAME=$(basename "$FILE_PATH")
DIRPATH=$(dirname "$FILE_PATH")

# Check by filename
case "$FILENAME" in
  .env|.env.*|*.pem|*.key|*.cert|*.p12|*.pfx)
    echo "⚠️ 민감 파일 수정 시도: $FILENAME" >&2
    echo "이 파일에 시크릿이 포함되어 있을 수 있습니다." >&2
    echo "수정이 필요하다면 사용자에게 직접 수정을 요청하세요." >&2
    exit 2
    ;;
  credentials.json|serviceAccountKey.json|*.keystore)
    echo "⚠️ 인증 파일 수정 시도: $FILENAME" >&2
    echo "이 파일은 인증 정보를 포함합니다. 사용자에게 직접 수정을 요청하세요." >&2
    exit 2
    ;;
esac

# Check by directory
case "$DIRPATH" in
  */.ssh/*|*/.aws/*|*/.config/gcloud/*)
    echo "⚠️ 시스템 인증 디렉토리 접근: $DIRPATH" >&2
    echo "이 경로는 시스템 인증 정보를 포함합니다." >&2
    exit 2
    ;;
esac

exit 0
