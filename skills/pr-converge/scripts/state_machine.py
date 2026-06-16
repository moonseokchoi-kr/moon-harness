"""state_machine.py — pr-converge 상태 전이 로직.

상태 전이표 (spec F6, arch §3.2):

  입력 상태 + 신호 집합 → 출력 상태

전이 우선순위 (높은 순):
  1. 서킷브레이커 발동 (fix_attempts >= 3 또는 iterations > 15) → BLOCKED
  2. 신규 actionable 신호가 있고 수정 push 완료 → WORKING
  3. CI pending + 수정 없음 → WAITING
  4. 에스컬레이션 코멘트만 남음 (자동 신호 green) → NEEDS_HUMAN
  5. 모든 신호 green + 미처리 에스컬레이션 0 → CONVERGED

결정 위임:
  - check_circuit_breaker: hooks.lib.self_improve.circuit_breaker
  - compute_cadence: hooks.lib.self_improve.circuit_breaker

Pure, deterministic, stdlib-only. 네트워크/LLM/gh 호출 절대 금지.
Fail-safe: 예외를 raise하지 않고 구조화된 dict 반환.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from hooks.lib.self_improve.circuit_breaker import (
    check_circuit_breaker,
    compute_cadence,
)

# ─── 상태 상수 ────────────────────────────────────────────────────

STATUS_WORKING = "WORKING"
STATUS_WAITING = "WAITING"
STATUS_NEEDS_HUMAN = "NEEDS_HUMAN"
STATUS_CONVERGED = "CONVERGED"
STATUS_BLOCKED = "BLOCKED"

_VALID_STATUSES = frozenset(
    [STATUS_WORKING, STATUS_WAITING, STATUS_NEEDS_HUMAN, STATUS_CONVERGED, STATUS_BLOCKED]
)


# ─── 신호 구조 ────────────────────────────────────────────────────
#
# signals: List[Dict] — 각 신호 dict는 다음 키를 가진다:
#   "signal_key": str  — 고유 신호 식별자 (예: "ci:unit-tests", "comment:12345")
#   "kind": str        — "ci_fail" | "lint_fail" | "build_fail" | "comment_actionable"
#                        | "comment_escalate" | "ci_pending" | "ci_pass"
#   "push_done": bool  — 이 신호에 대해 수정 push가 완료됐는지 (선택, 기본 False)


def transition_status(state: Dict[str, Any], signals: List[Dict[str, Any]]) -> Dict[str, Any]:
    """pr-converge 상태 전이를 계산한다.

    Args:
        state: 현재 .harness/pr-converge-state.json 내용 (dict).
               필수 키: iterations, fix_attempts, escalations.
        signals: 이번 패스에서 관측된 신호 목록. 각 요소는 dict:
                 {"signal_key": str, "kind": str, "push_done": bool (optional)}.

    Returns:
        {
            "new_status": str,       # 전이 후 상태
            "cadence_seconds": int|None,  # 다음 틱 간격 (None이면 루프 종료)
            "blocked_reason": str|None,   # BLOCKED인 경우 이유
            "transition_reason": str,     # 전이 이유 (디버깅용)
        }

    Fail-safe: state/signals가 비정상이면 보수적으로 BLOCKED 반환하지 않고
               WAITING을 반환 (루프 자체는 계속, 사람이 진단 가능).
    """
    if not isinstance(state, dict):
        return _make_result(STATUS_WAITING, "state가 dict가 아닌 비정상 입력 — WAITING으로 fallback")

    if not isinstance(signals, list):
        signals = []

    # ── 1순위: 서킷브레이커 ────────────────────────────────────────
    cb_result = check_circuit_breaker(state)
    if isinstance(cb_result, dict) and cb_result.get("blocked"):
        reason = cb_result.get("reason", "서킷브레이커 발동")
        return _make_result(STATUS_BLOCKED, reason, blocked_reason=reason)

    # ── 신호 분류 ─────────────────────────────────────────────────
    has_push_done = any(
        bool(s.get("push_done", False))
        for s in signals
        if isinstance(s, dict)
    )
    has_ci_pending = any(
        s.get("kind") == "ci_pending"
        for s in signals
        if isinstance(s, dict)
    )
    has_ci_fail = any(
        s.get("kind") in ("ci_fail", "lint_fail", "build_fail")
        for s in signals
        if isinstance(s, dict)
    )
    has_actionable = any(
        s.get("kind") == "comment_actionable"
        for s in signals
        if isinstance(s, dict)
    )
    has_escalation = any(
        s.get("kind") == "comment_escalate"
        for s in signals
        if isinstance(s, dict)
    )
    # 기존 미처리 에스컬레이션 (state.escalations)
    existing_escalations = state.get("escalations", [])
    has_pending_escalations = bool(
        isinstance(existing_escalations, list) and existing_escalations
    )

    # ── 2순위: 이번 패스에 push 완료 → WORKING ────────────────────
    if has_push_done:
        return _make_result(
            STATUS_WORKING,
            "이번 패스에 수정 push 완료 — CI 재실행 대기",
        )

    # ── 에스컬레이션(신규) 누적 ───────────────────────────────────
    # 새 에스컬레이션 신호가 있으면 판정 시 반영
    total_escalations = has_escalation or has_pending_escalations

    # ── 3순위: 아직 수정할 신호가 있으면 ─────────────────────────
    if has_ci_fail or has_actionable:
        # 수정 push가 이번 패스에 안 됐지만 신호는 남아있음
        # (엔지니어 디스패치 전 또는 수정 실패)
        return _make_result(
            STATUS_WORKING,
            "actionable 신호 존재 — 수정 진행 중",
        )

    # ── 4순위: CI pending, 수정 없음 → WAITING ───────────────────
    if has_ci_pending and not total_escalations:
        return _make_result(
            STATUS_WAITING,
            "CI 결과 대기 중 — 수정 없이 관측 재시도",
        )

    # ── 5순위: 에스컬레이션만 남음 → NEEDS_HUMAN ─────────────────
    if total_escalations and not has_ci_fail and not has_actionable:
        return _make_result(
            STATUS_NEEDS_HUMAN,
            "에스컬레이션 코멘트 미해결 — 사람 응답 대기",
        )

    # ── CI pending + 에스컬레이션 함께 있는 경우 → NEEDS_HUMAN ───
    if has_ci_pending and total_escalations:
        return _make_result(
            STATUS_NEEDS_HUMAN,
            "CI 대기 중 + 에스컬레이션 코멘트 미해결",
        )

    # ── 최종: 모든 신호 green + 에스컬레이션 0 → CONVERGED ───────
    return _make_result(
        STATUS_CONVERGED,
        "모든 CI green + actionable 코멘트 0 + 미처리 에스컬레이션 0 — 머지 요청 준비 완료",
    )


# ─── 내부 헬퍼 ────────────────────────────────────────────────────

def _make_result(
    status: str,
    transition_reason: str,
    blocked_reason: Optional[str] = None,
) -> Dict[str, Any]:
    """상태 전이 결과 dict를 생성한다."""
    return {
        "new_status": status,
        "cadence_seconds": compute_cadence(status),
        "blocked_reason": blocked_reason,
        "transition_reason": transition_reason,
    }


__all__ = [
    "STATUS_WORKING",
    "STATUS_WAITING",
    "STATUS_NEEDS_HUMAN",
    "STATUS_CONVERGED",
    "STATUS_BLOCKED",
    "transition_status",
]
