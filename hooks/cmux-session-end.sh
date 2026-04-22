#!/bin/bash
# Moon Harness: cmux 세션 종료 시 상태 정리
# Event: Stop
command -v cmux &>/dev/null || exit 0

cmux clear-status claude 2>/dev/null || true
cmux clear-status task 2>/dev/null || true
cmux clear-status spec-design 2>/dev/null || true
cmux clear-status idea 2>/dev/null || true
cmux set-progress 0.0 --label "" 2>/dev/null || true
exit 0
