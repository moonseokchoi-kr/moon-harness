"""circuit_breaker.py — pr-converge 서킷브레이커 + 케이던스 계산.

F6: fix_attempts[signal] >= 3 또는 iterations > 15 → BLOCKED 판정.
F4: 케이던스 매핑 (WORKING/WAITING → 270, NEEDS_HUMAN → 1200, CONVERGED/BLOCKED → None).
    300초는 절대 반환하지 않는다.

Pure, deterministic, stdlib-only (F20). No LLM/gh/network calls.
Fail-safe: 예외를 raise하지 않고 구조화된 dict 또는 None을 반환한다.
"""

from __future__ import annotations

from typing import Dict, Optional

# ─── 상수 ───────────────────────────────────────────────────────

# F6 임계값
FIX_ATTEMPTS_THRESHOLD: int = 3   # >= 3이면 BLOCKED
ITERATIONS_THRESHOLD: int = 15    # > 15이면 BLOCKED (16회 패스에서 발동)

# F4 케이던스 (초) — 300은 절대 사용 안 함
_CADENCE_MAP: Dict[str, Optional[int]] = {
    "WORKING": 270,
    "WAITING": 270,
    "NEEDS_HUMAN": 1200,
    "CONVERGED": None,
    "BLOCKED": None,
}

# 내부 assertion: 300이 절대 반환되지 않음을 코드 레벨에서 보장
assert 300 not in _CADENCE_MAP.values(), "300s cadence must never appear in the map"


# ─── 서킷브레이커 ────────────────────────────────────────────────

def check_circuit_breaker(state: dict) -> dict:
    """pr-converge 상태에서 서킷브레이커 조건을 검사한다 (F6).

    조건 1: fix_attempts 딕셔너리의 임의 신호 횟수 >= FIX_ATTEMPTS_THRESHOLD (3)
    조건 2: iterations > ITERATIONS_THRESHOLD (15)

    두 조건 중 하나라도 충족되면 {"blocked": True, "reason": "..."} 반환.
    아무 조건도 해당되지 않으면 {"blocked": False} 반환.

    Fail-safe: state가 dict가 아니거나 필드가 없으면 {"blocked": False} 반환.
    절대 raise하지 않는다.
    """
    if not isinstance(state, dict):
        return {"blocked": False}

    # 조건 1: fix_attempts 개별 신호 체크
    fix_attempts = state.get("fix_attempts", {})
    if isinstance(fix_attempts, dict):
        for signal, count in fix_attempts.items():
            try:
                if int(count) >= FIX_ATTEMPTS_THRESHOLD:
                    return {
                        "blocked": True,
                        "reason": (
                            f"동일 신호 '{signal}'에 대한 fix_attempts가 "
                            f"{count}회로 임계값({FIX_ATTEMPTS_THRESHOLD})에 도달했습니다. "
                            "루프를 종료하고 사용자에게 에스컬레이션합니다."
                        ),
                        "signal": signal,
                        "fix_attempts": count,
                    }
            except (TypeError, ValueError):
                # count를 int로 변환할 수 없으면 건너뜀 (fail-safe)
                continue

    # 조건 2: 전체 iterations 체크
    iterations = state.get("iterations", 0)
    try:
        iterations_int = int(iterations)
    except (TypeError, ValueError):
        iterations_int = 0

    if iterations_int > ITERATIONS_THRESHOLD:
        return {
            "blocked": True,
            "reason": (
                f"총 iterations가 {iterations_int}회로 임계값({ITERATIONS_THRESHOLD})을 "
                "초과했습니다. 루프를 종료하고 사용자에게 에스컬레이션합니다."
            ),
            "iterations": iterations_int,
        }

    return {"blocked": False}


# ─── 케이던스 계산 ───────────────────────────────────────────────

def compute_cadence(status: str) -> Optional[int]:
    """pr-converge 상태(status)에 따라 다음 틱 간격(초)을 반환한다 (F4).

    반환값:
      - WORKING 또는 WAITING: 270 (초)
      - NEEDS_HUMAN: 1200 (초)
      - CONVERGED 또는 BLOCKED: None (루프 종료, 다음 틱 없음)
      - 알 수 없는 status: None (보수적 기본값)

    300초는 절대 반환하지 않는다.

    Fail-safe: status가 str이 아니어도 raise하지 않고 None 반환.
    """
    if not isinstance(status, str):
        return None

    result = _CADENCE_MAP.get(status.strip().upper(), None)

    # 방어적 assertion: 런타임에서도 300이 나올 수 없음을 보장
    assert result != 300, f"compute_cadence must never return 300; got {result} for status={status!r}"

    return result


__all__ = [
    "FIX_ATTEMPTS_THRESHOLD",
    "ITERATIONS_THRESHOLD",
    "check_circuit_breaker",
    "compute_cadence",
]
