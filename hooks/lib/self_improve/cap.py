"""cap.py — 자동 적용 상한(F13) + 케이던스 계산 재노출.

F13: 한 회고 실행에서 프로젝트 티어 자동 적용 후보가 CAP(기본 5)건을 초과할 때
     CAP건만 적용하고 초과분을 반환한다. Silent truncation 금지 — 잘린 수를 반환.

이 모듈은 cap + 케이던스를 함께 묶어 노출한다 (arch §3.1 "cap+cadence+circuit-breaker engine").
케이던스 로직의 실제 구현은 circuit_breaker.py에 있으며, 이 모듈은 re-export한다.

Pure, deterministic, stdlib-only (F20). No LLM/gh/network calls.
Fail-safe: 예외를 raise하지 않고 구조화된 tuple을 반환한다.
"""

from __future__ import annotations

from typing import List, Tuple

# 케이던스 계산은 circuit_breaker에서 위임
from hooks.lib.self_improve.circuit_breaker import compute_cadence  # noqa: F401

# ─── 상수 ───────────────────────────────────────────────────────

DEFAULT_CAP: int = 5  # F13: 프로젝트 티어 자동 적용 상한


# ─── 5건 상한 ────────────────────────────────────────────────────

def apply_cap(
    candidates: list,
    cap: int = DEFAULT_CAP,
) -> Tuple[list, list]:
    """후보 리스트에 자동 적용 상한을 적용한다 (F13).

    Args:
        candidates: 적용 후보 리스트 (임의 원소).
        cap: 최대 자동 적용 건수 (기본 5). 양의 정수여야 한다.
             0 이하이면 0으로 클램핑한다 (fail-safe).

    Returns:
        (applied, deferred) 튜플:
          - applied: 상위 cap개 (len(applied) <= cap)
          - deferred: 초과분 (len(deferred) = max(0, len(candidates) - cap))

        초과가 발생한 경우 applied 리스트의 각 원소에는 변화가 없다.
        잘린 사실은 반환 구조(deferred 길이 > 0)로 명시된다 (silent truncation 금지).

    동작 예:
        apply_cap([a, b, c, d, e, f], cap=5)
        → ([a, b, c, d, e], [f])

    Fail-safe: candidates가 리스트가 아니면 ([], []) 반환. raise 금지.
    """
    if not isinstance(candidates, list):
        return ([], [])

    safe_cap = max(0, int(cap)) if isinstance(cap, (int, float)) else DEFAULT_CAP

    applied = candidates[:safe_cap]
    deferred = candidates[safe_cap:]

    return (applied, deferred)


# ─── 트런케이션 보고 헬퍼 ────────────────────────────────────────

def cap_report(
    candidates: list,
    cap: int = DEFAULT_CAP,
) -> dict:
    """apply_cap을 실행하고 트런케이션 보고 dict를 반환한다.

    반환 dict 구조:
      {
        "applied": [...],          # 적용 대상 (len <= cap)
        "deferred": [...],         # 초과분 (다음 회고 또는 하네스 제안 큐로)
        "truncated": bool,         # True이면 잘림 발생
        "applied_count": int,
        "deferred_count": int,
      }

    Silent truncation 금지: truncated=True이면 deferred_count > 0이 보장된다.
    """
    applied, deferred = apply_cap(candidates, cap)
    return {
        "applied": applied,
        "deferred": deferred,
        "truncated": len(deferred) > 0,
        "applied_count": len(applied),
        "deferred_count": len(deferred),
    }


__all__ = [
    "DEFAULT_CAP",
    "apply_cap",
    "cap_report",
    "compute_cadence",
]
