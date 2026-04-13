#!/bin/bash
# enforcement/lib/decision-cache.sh
# 5초 TTL 판정 캐시 — 같은 파일을 반복 편집할 때 파싱 비용 절감

# 캐시에서 값 읽기
# 사용: cache_get "role" → "orchestrator" or ""
cache_get() {
  local key="$1"
  local cache_file="$HARNESS_CACHE_DIR/${key//\//_}.cache"

  [ ! -f "$cache_file" ] && return 1

  local now
  now=$(date +%s)
  local mtime
  # macOS와 Linux 모두 지원
  if stat -f%m "$cache_file" &>/dev/null; then
    mtime=$(stat -f%m "$cache_file")
  else
    mtime=$(stat -c%Y "$cache_file")
  fi

  local age=$((now - mtime))
  [ $age -ge "${HARNESS_CACHE_TTL:-5}" ] && return 1

  cat "$cache_file"
}

# 캐시에 값 저장
# 사용: cache_set "role" "orchestrator"
cache_set() {
  local key="$1"
  local value="$2"
  local cache_file="$HARNESS_CACHE_DIR/${key//\//_}.cache"

  mkdir -p "$HARNESS_CACHE_DIR" 2>/dev/null
  echo "$value" > "$cache_file"
}

# 캐시 초기화 (테스트/디버그용)
cache_clear() {
  rm -rf "$HARNESS_CACHE_DIR" 2>/dev/null
}
