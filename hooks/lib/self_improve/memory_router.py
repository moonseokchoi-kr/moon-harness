"""memory_router.py — on-demand 태그 기반 메모리 라우터 (F18).

LEARNING.md 엔트리 리스트를 받아 현재 컨텍스트 도메인과 일치하는 항목만 선별한다.
전체 로드(@import) 방식을 대체한다.

토큰 예산:
  - always_on_budget: ~800 토큰 이내 (항상 로드되는 계층)
  - ondemand_budget:  ~500 토큰 이내 (on-demand 검색 계층)

토큰 길이 추정: len(text) // 4 (GPT 기준 rough estimate, stdlib only).

계층 구분:
  - always-on: domain 태그 없음 (tags=None) 또는 domain 태그가 컨텍스트와 일치하지 않지만
               "always_on" 플래그가 있는 엔트리.
  - on-demand: domain 태그가 context_domain과 정확히 일치하는 엔트리.

실제 구현에서 always-on 계층은 domain에 무관하게 고정 로드되는 엔트리를 의미하지만,
이 결정적 라우터에서는 도메인 매칭 여부로 계층을 구분한다:
  - domain 일치 → on-demand 계층
  - domain 불일치 또는 태그 없음 → always-on 계층 (단, 예산 내에서만 포함)

Pure, deterministic, stdlib-only (F20). No LLM/gh/network calls.
Fail-safe: 예외를 raise하지 않고 구조화된 dict를 반환한다.
"""

from __future__ import annotations

from typing import Dict, List, Optional

# ─── 상수 ───────────────────────────────────────────────────────

DEFAULT_ALWAYS_ON_BUDGET: int = 800   # F18: 항상 로드 계층 토큰 상한
DEFAULT_ONDEMAND_BUDGET: int = 500    # F18: on-demand 계층 토큰 상한

CHARS_PER_TOKEN: int = 4              # 토큰 추정: len(text) // 4


# ─── 내부 헬퍼 ───────────────────────────────────────────────────

def _estimate_tokens(text: str) -> int:
    """텍스트의 토큰 수를 추정한다. len(text) // CHARS_PER_TOKEN."""
    if not isinstance(text, str):
        return 0
    return max(0, len(text) // CHARS_PER_TOKEN)


def _entry_text(entry: dict) -> str:
    """엔트리의 raw 텍스트를 추출한다. raw 필드 우선, 없으면 body."""
    if not isinstance(entry, dict):
        return ""
    raw = entry.get("raw", "")
    if isinstance(raw, str) and raw:
        return raw
    body = entry.get("body", "")
    return body if isinstance(body, str) else ""


def _entry_domain(entry: dict) -> Optional[str]:
    """엔트리의 domain 태그를 반환한다. 없으면 None."""
    if not isinstance(entry, dict):
        return None
    tags = entry.get("tags")
    if not isinstance(tags, dict):
        return None
    domain = tags.get("domain")
    return domain if isinstance(domain, str) and domain else None


# ─── 메인 라우터 ─────────────────────────────────────────────────

def route_memory(
    entries: List[dict],
    context_domain: str,
    always_on_budget: int = DEFAULT_ALWAYS_ON_BUDGET,
    ondemand_budget: int = DEFAULT_ONDEMAND_BUDGET,
) -> dict:
    """컨텍스트 도메인에 따라 LEARNING.md 엔트리를 라우팅한다 (F18).

    Args:
        entries: parse_learning_entry()로 파싱된 엔트리 dict 리스트.
        context_domain: 현재 작업 컨텍스트 도메인 (예: "auth", "pipeline").
        always_on_budget: always-on 계층 토큰 상한 (기본 800).
        ondemand_budget: on-demand 계층 토큰 상한 (기본 500).

    Returns:
        {
            "always_on": [...],          # always-on 계층 엔트리
            "on_demand": [...],          # on-demand 계층 엔트리
            "always_on_tokens": int,     # always-on 계층 소비 토큰
            "ondemand_tokens": int,      # on-demand 계층 소비 토큰
            "always_on_truncated": bool, # always-on 잘림 여부
            "ondemand_truncated": bool,  # on-demand 잘림 여부
            "always_on_dropped": int,    # always-on 예산 초과로 제외된 엔트리 수
            "ondemand_dropped": int,     # on-demand 예산 초과로 제외된 엔트리 수
        }

    엔트리를 통째 로드하지 않는다 — domain 태그 필터링 후 예산 내에서 선택.
    예산 초과 시 엔트리를 잘라내고 잘린 사실을 반환 dict에 기록한다 (silent truncation 금지).

    Fail-safe: entries가 리스트가 아니면 빈 결과 반환. raise 금지.
    """
    result: dict = {
        "always_on": [],
        "on_demand": [],
        "always_on_tokens": 0,
        "ondemand_tokens": 0,
        "always_on_truncated": False,
        "ondemand_truncated": False,
        "always_on_dropped": 0,
        "ondemand_dropped": 0,
    }

    if not isinstance(entries, list):
        return result

    domain_query = context_domain.strip() if isinstance(context_domain, str) else ""

    # 도메인 일치 여부로 계층 분류
    always_on_candidates: List[dict] = []
    ondemand_candidates: List[dict] = []

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        entry_domain = _entry_domain(entry)
        if entry_domain is not None and entry_domain == domain_query:
            ondemand_candidates.append(entry)
        else:
            always_on_candidates.append(entry)

    # always-on 계층: 예산 내에서 선택
    always_on_tokens = 0
    always_on_selected: List[dict] = []
    always_on_dropped = 0
    for entry in always_on_candidates:
        text = _entry_text(entry)
        tokens = _estimate_tokens(text)
        if always_on_tokens + tokens <= always_on_budget:
            always_on_selected.append(entry)
            always_on_tokens += tokens
        else:
            always_on_dropped += 1

    # on-demand 계층: domain 일치 → 예산 내에서 선택
    ondemand_tokens = 0
    ondemand_selected: List[dict] = []
    ondemand_dropped = 0
    for entry in ondemand_candidates:
        text = _entry_text(entry)
        tokens = _estimate_tokens(text)
        if ondemand_tokens + tokens <= ondemand_budget:
            ondemand_selected.append(entry)
            ondemand_tokens += tokens
        else:
            ondemand_dropped += 1

    result["always_on"] = always_on_selected
    result["on_demand"] = ondemand_selected
    result["always_on_tokens"] = always_on_tokens
    result["ondemand_tokens"] = ondemand_tokens
    result["always_on_truncated"] = always_on_dropped > 0
    result["ondemand_truncated"] = ondemand_dropped > 0
    result["always_on_dropped"] = always_on_dropped
    result["ondemand_dropped"] = ondemand_dropped

    return result


__all__ = [
    "DEFAULT_ALWAYS_ON_BUDGET",
    "DEFAULT_ONDEMAND_BUDGET",
    "route_memory",
]
