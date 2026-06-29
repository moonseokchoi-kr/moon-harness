"""code-mapper — codegraph_status 프로브 텍스트 → 3-상태 분류 (순수 함수).

arch §6/§8 기준. *주어진 텍스트*만 분류한다 — codegraph_status를 직접
호출하지 않는다(그건 LLM/MCP 몫). 동일 입력 = 동일 출력, side-effect 0.

분류는 의미 단위(특정 텍스트 정확매치 아님):
  - healthy         : 인덱스 통계(노드/엣지 수, ready 등) 신호
  - not_initialized : "not initialized"(또는 동등 미초기화 신호) 포함
  - unavailable     : 도구 미등록 / 연결 오류 / 미지 / 빈 문자열 (fail-safe)

fail-safe 규율: 미지·비문자열·빈 입력은 항상 unavailable로 수렴한다 →
최악도 grep 폴백으로 떨어져 동작 보장 (arch §12 리스크 완화).
"""

from __future__ import annotations

import re

HEALTHY: str = "healthy"
NOT_INITIALIZED: str = "not_initialized"
UNAVAILABLE: str = "unavailable"

# --- 의미 단위 신호 패턴 (특정 텍스트 정확매치 아님) ---------------------

# 미초기화 신호: "not initialized" 및 동등 표현 (공백/대소문자 무시).
# SSOT는 skills/code-mapper/SKILL.md "3-상태 분류 기준" 표 — "not initialized"
# (또는 동등 미초기화 신호)만 열거한다. 그 표에 없는 외삽 패턴(예: "not indexed")은
# 추가하지 않는다: 실제 codegraph_status가 쓰지 않는 phrasing이고, "files not
# indexed: 0" 같은 정상 응답을 오분류할 여지가 있다. SSOT에 없는 미초기화는
# fail-safe로 unavailable(→ grep 폴백)에 수렴하면 충분하다.
_NOT_INIT_PATTERNS = (
    re.compile(r"not\s+initiali[sz]ed", re.IGNORECASE),
    re.compile(r"\buninitiali[sz]ed\b", re.IGNORECASE),
)

# 통계/준비 신호: 노드·엣지 수치 또는 ready/indexed 상태.
_HEALTHY_PATTERNS = (
    re.compile(r"\bnodes?\b", re.IGNORECASE),
    re.compile(r"\bedges?\b", re.IGNORECASE),
    re.compile(r"\bready\b", re.IGNORECASE),
    re.compile(r"\bsymbols?\s+indexed\b", re.IGNORECASE),
    re.compile(r"\bindex(?:\s+is)?\s+ready\b", re.IGNORECASE),
)


def classify_probe_state(text: str) -> str:
    """codegraph_status 응답 텍스트를 3-상태로 분류한다.

    Args:
        text: codegraph_status MCP 호출의 응답 텍스트 (LLM이 주입). 비문자열/
            빈 문자열도 허용 — fail-safe로 ``unavailable``로 수렴한다.

    Returns:
        ``"healthy"`` / ``"not_initialized"`` / ``"unavailable"`` 중 하나.
    """
    if not isinstance(text, str):
        return UNAVAILABLE

    stripped = text.strip()
    if not stripped:
        return UNAVAILABLE

    # 미초기화 신호가 통계 신호보다 우선한다: "0 nodes ... not initialized"
    # 같은 응답을 healthy로 오분류하면 안 된다 (init 제안 + 폴백이 정답).
    for pat in _NOT_INIT_PATTERNS:
        if pat.search(stripped):
            return NOT_INITIALIZED

    for pat in _HEALTHY_PATTERNS:
        if pat.search(stripped):
            return HEALTHY

    # 미등록/연결오류/미지 신호 → fail-safe.
    return UNAVAILABLE
