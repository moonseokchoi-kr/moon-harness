#!/bin/bash
# enforcement/stop-pipeline.sh — Stop 훅 Bash 래퍼
#
# Claude Code 의 Stop 훅이 이 스크립트를 호출한다.
# stdin 으로 받은 JSON 을 Python 엔진에 전달하고 결과를 그대로 출력한다.
#
# Python 이 없거나 에러 시 fail-safe 로 allow 반환.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_ENGINE="$SCRIPT_DIR/stop-pipeline.py"

# Python3 필수
if ! command -v python3 &>/dev/null; then
  echo '{"continue": true, "_error": "python3 not found"}'
  exit 0
fi

# Python 엔진 존재 확인
if [ ! -f "$PYTHON_ENGINE" ]; then
  echo '{"continue": true, "_error": "stop-pipeline.py not found"}'
  exit 0
fi

# stdin 을 Python 엔진으로 전달
exec python3 "$PYTHON_ENGINE"
