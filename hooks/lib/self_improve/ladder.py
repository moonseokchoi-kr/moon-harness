"""ladder.py — 학습 메커니즘 사다리 라우터 (F17).

L0–L4 + 절차적 메모리 순서로 사다리를 정의하고,
재발 횟수에 따라 다음 단계를 제안한다.

사다리:
  L0: passive — LEARNING.md 기록 (입력층)
  L1: 큐레이션/압축 — docs/lessons-learned.md 일반화 교훈
  L2: 관련성 라우팅 — 태그 on-demand 로드 (progressive disclosure)
  L3: enforcement — hooks/체크로 구현 (사람 게이트)
  L4: 프롬프트/agent 수정 (사람 게이트)
  procedural: 성공 절차의 스킬 결정화 (사람 게이트)

L3 이상은 requires_human=True (하네스 티어, 자동 적용 불가).

Pure, deterministic, stdlib-only (F20). No LLM/gh/network calls.
Fail-safe: 예외를 raise하지 않고 구조화된 dict를 반환한다.
"""

from __future__ import annotations

from typing import List

# ─── 상수 ───────────────────────────────────────────────────────

LADDER_RUNGS: List[str] = ["L0", "L1", "L2", "L3", "L4", "procedural"]

# L3 이상(인덱스 3+)은 사람 게이트 필수
_HUMAN_GATE_INDEX: int = 3

# 각 단계 설명
_RUNG_DESCRIPTIONS: dict = {
    "L0": "passive — LEARNING.md에 기록 (입력층)",
    "L1": "큐레이션/압축 — docs/lessons-learned.md에 일반화 교훈 기록",
    "L2": "관련성 라우팅 — 태그 on-demand 로드 (progressive disclosure)",
    "L3": "enforcement — 교훈을 hooks/체크로 구현",
    "L4": "프롬프트/agent 수정",
    "procedural": "성공 절차의 스킬 결정화",
}


# ─── 사다리 라우터 ───────────────────────────────────────────────

def get_next_ladder_rung(current_rung: str, recurrence_count: int) -> dict:
    """재발 횟수에 따라 다음 사다리 단계를 제안한다 (F17).

    Args:
        current_rung: 현재 사다리 단계 ("L0", "L1", ..., "procedural").
        recurrence_count: 동일 교훈 재발 횟수 (0이면 재발 없음).

    Returns:
        {
            "current_rung": str,       # 현재 단계
            "next_rung": str | None,   # 제안 단계 (재발 없으면 None)
            "requires_human": bool,    # L3 이상이면 True (자동 적용 불가)
            "description": str,        # 다음 단계 설명
            "escalated": bool,         # 에스컬레이션 여부
        }

    재발이 있을 때(recurrence_count >= 1): 현재 단계 + 1 제안.
    재발이 없을 때: 현재 단계 유지 (next_rung=current_rung, escalated=False).
    이미 최상위 단계이면: next_rung=current_rung 유지 (더 이상 에스컬레이션 없음).

    Fail-safe: current_rung이 알 수 없는 값이면 L0에서 시작. raise 금지.
    """
    # current_rung 정규화
    if not isinstance(current_rung, str):
        current_rung = "L0"

    # recurrence_count 정규화
    try:
        recurrence_int = int(recurrence_count)
    except (TypeError, ValueError):
        recurrence_int = 0

    # 알 수 없는 단계는 L0으로 폴백
    if current_rung not in LADDER_RUNGS:
        current_rung = "L0"

    current_idx = LADDER_RUNGS.index(current_rung)

    # 재발이 없으면 현재 단계 유지
    if recurrence_int <= 0:
        requires_human = current_idx >= _HUMAN_GATE_INDEX
        return {
            "current_rung": current_rung,
            "next_rung": current_rung,
            "requires_human": requires_human,
            "description": _RUNG_DESCRIPTIONS.get(current_rung, current_rung),
            "escalated": False,
        }

    # 재발: 한 단계 에스컬레이션
    next_idx = min(current_idx + 1, len(LADDER_RUNGS) - 1)
    next_rung = LADDER_RUNGS[next_idx]
    escalated = next_idx != current_idx

    requires_human = next_idx >= _HUMAN_GATE_INDEX

    return {
        "current_rung": current_rung,
        "next_rung": next_rung,
        "requires_human": requires_human,
        "description": _RUNG_DESCRIPTIONS.get(next_rung, next_rung),
        "escalated": escalated,
    }


__all__ = [
    "LADDER_RUNGS",
    "get_next_ladder_rung",
]
