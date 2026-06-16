"""tests/test_ladder.py — ladder 단위 테스트.

오프라인 전용. 네트워크/LLM 무호출.

커버 범위:
- LADDER_RUNGS 상수: L0→L4→procedural 순서
- get_next_ladder_rung: L0→L4 매핑, 재발 시 현재+1 에스컬레이션
- L3 이상 requires_human=True (사람 게이트)
- L4 이상: 더 이상 에스컬레이션 없음 (최상위 유지)
- fail-safe: 알 수 없는 rung, 잘못된 타입
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from hooks.lib.self_improve.ladder import (
    LADDER_RUNGS,
    get_next_ladder_rung,
)


# ─── LADDER_RUNGS 상수 ────────────────────────────────────────────

class TestLadderRungs:

    def test_ladder_rungs_order(self):
        """사다리 순서: L0 → L1 → L2 → L3 → L4 → procedural."""
        assert LADDER_RUNGS[0] == "L0"
        assert LADDER_RUNGS[1] == "L1"
        assert LADDER_RUNGS[2] == "L2"
        assert LADDER_RUNGS[3] == "L3"
        assert LADDER_RUNGS[4] == "L4"
        assert LADDER_RUNGS[5] == "procedural"

    def test_ladder_has_six_rungs(self):
        """사다리는 L0~L4 + procedural = 6단계."""
        assert len(LADDER_RUNGS) == 6

    def test_ladder_rungs_are_strings(self):
        """모든 단계가 str."""
        for rung in LADDER_RUNGS:
            assert isinstance(rung, str)


# ─── 재발 없음 (escalation=False) ────────────────────────────────

class TestNoRecurrence:

    def test_no_recurrence_stays_at_current_rung(self):
        """재발 없음(recurrence_count=0): 현재 단계 유지."""
        result = get_next_ladder_rung("L0", recurrence_count=0)
        assert result["next_rung"] == "L0"
        assert result["escalated"] is False

    def test_no_recurrence_l2(self):
        """L2에서 재발 없음: L2 유지."""
        result = get_next_ladder_rung("L2", recurrence_count=0)
        assert result["next_rung"] == "L2"
        assert result["escalated"] is False

    def test_negative_recurrence_stays_at_current(self):
        """음수 recurrence_count는 재발 없음으로 처리."""
        result = get_next_ladder_rung("L1", recurrence_count=-1)
        assert result["next_rung"] == "L1"
        assert result["escalated"] is False


# ─── 재발 시 에스컬레이션 ─────────────────────────────────────────

class TestEscalation:

    def test_l0_to_l1_on_recurrence(self):
        """L0 + 재발 1회 → L1 제안."""
        result = get_next_ladder_rung("L0", recurrence_count=1)
        assert result["next_rung"] == "L1"
        assert result["escalated"] is True

    def test_l1_to_l2_on_recurrence(self):
        """L1 + 재발 → L2 제안."""
        result = get_next_ladder_rung("L1", recurrence_count=1)
        assert result["next_rung"] == "L2"
        assert result["escalated"] is True

    def test_l2_to_l3_on_recurrence(self):
        """L2 + 재발 → L3 제안."""
        result = get_next_ladder_rung("L2", recurrence_count=1)
        assert result["next_rung"] == "L3"
        assert result["escalated"] is True

    def test_l3_to_l4_on_recurrence(self):
        """L3 + 재발 → L4 제안."""
        result = get_next_ladder_rung("L3", recurrence_count=1)
        assert result["next_rung"] == "L4"
        assert result["escalated"] is True

    def test_l4_to_procedural_on_recurrence(self):
        """L4 + 재발 → procedural 제안."""
        result = get_next_ladder_rung("L4", recurrence_count=1)
        assert result["next_rung"] == "procedural"
        assert result["escalated"] is True

    def test_procedural_stays_at_procedural(self):
        """procedural은 최상위 — 재발해도 더 올라가지 않는다."""
        result = get_next_ladder_rung("procedural", recurrence_count=5)
        assert result["next_rung"] == "procedural"
        assert result["escalated"] is False

    def test_high_recurrence_count(self):
        """재발 횟수가 크더라도 항상 현재+1만 에스컬레이션."""
        result = get_next_ladder_rung("L0", recurrence_count=100)
        assert result["next_rung"] == "L1"
        assert result["escalated"] is True


# ─── L3+ 사람 게이트 ─────────────────────────────────────────────

class TestHumanGate:

    def test_l0_no_human_gate(self):
        """L0: requires_human=False."""
        result = get_next_ladder_rung("L0", recurrence_count=0)
        assert result["requires_human"] is False

    def test_l1_no_human_gate(self):
        """L1: requires_human=False."""
        result = get_next_ladder_rung("L1", recurrence_count=0)
        assert result["requires_human"] is False

    def test_l2_no_human_gate(self):
        """L2: requires_human=False."""
        result = get_next_ladder_rung("L2", recurrence_count=0)
        assert result["requires_human"] is False

    def test_l3_requires_human(self):
        """L3: requires_human=True (사람 게이트)."""
        result = get_next_ladder_rung("L3", recurrence_count=0)
        assert result["requires_human"] is True

    def test_l4_requires_human(self):
        """L4: requires_human=True."""
        result = get_next_ladder_rung("L4", recurrence_count=0)
        assert result["requires_human"] is True

    def test_procedural_requires_human(self):
        """procedural: requires_human=True."""
        result = get_next_ladder_rung("procedural", recurrence_count=0)
        assert result["requires_human"] is True

    def test_next_rung_l3_requires_human_on_escalation(self):
        """L2 + 재발 → L3 제안 → requires_human=True."""
        result = get_next_ladder_rung("L2", recurrence_count=1)
        assert result["next_rung"] == "L3"
        assert result["requires_human"] is True

    def test_all_rungs_l3_plus_require_human(self):
        """L3, L4, procedural은 모두 requires_human=True."""
        for rung in ["L3", "L4", "procedural"]:
            result = get_next_ladder_rung(rung, recurrence_count=0)
            assert result["requires_human"] is True, f"{rung} should require human"

    def test_all_rungs_below_l3_no_human_gate(self):
        """L0, L1, L2는 requires_human=False (재발 없을 때)."""
        for rung in ["L0", "L1", "L2"]:
            result = get_next_ladder_rung(rung, recurrence_count=0)
            assert result["requires_human"] is False, f"{rung} should not require human"


# ─── 반환 dict 구조 ───────────────────────────────────────────────

class TestReturnShape:

    def test_return_has_required_keys(self):
        """반환 dict에 필수 키가 있어야 한다."""
        result = get_next_ladder_rung("L0", recurrence_count=1)
        required = ["current_rung", "next_rung", "requires_human", "description", "escalated"]
        for key in required:
            assert key in result, f"Missing key: {key}"

    def test_description_is_non_empty_string(self):
        """description은 비어 있지 않은 str."""
        for rung in LADDER_RUNGS:
            result = get_next_ladder_rung(rung, recurrence_count=0)
            assert isinstance(result["description"], str)
            assert len(result["description"]) > 0

    def test_current_rung_echoed(self):
        """current_rung 필드가 입력값을 그대로 반환한다."""
        for rung in LADDER_RUNGS:
            result = get_next_ladder_rung(rung, recurrence_count=0)
            assert result["current_rung"] == rung


# ─── fail-safe ────────────────────────────────────────────────────

class TestFailSafe:

    def test_unknown_rung_falls_back_to_l0(self):
        """알 수 없는 rung은 L0으로 폴백."""
        result = get_next_ladder_rung("UNKNOWN", recurrence_count=1)
        # L0에서 에스컬레이션 → L1
        assert result["next_rung"] == "L1"
        assert result["escalated"] is True

    def test_non_string_rung_falls_back(self):
        """rung이 str이 아니면 raise 없이 폴백."""
        for bad in [None, 42, [], {}]:
            try:
                result = get_next_ladder_rung(bad, recurrence_count=0)
                assert isinstance(result["next_rung"], str)
            except Exception as e:
                pytest.fail(f"get_next_ladder_rung raised for rung={bad!r}: {e}")

    def test_non_int_recurrence_count(self):
        """recurrence_count가 int가 아니면 raise 없이 처리."""
        for bad in [None, "abc", [], {}]:
            try:
                result = get_next_ladder_rung("L0", recurrence_count=bad)
                assert "next_rung" in result
            except Exception as e:
                pytest.fail(f"get_next_ladder_rung raised for recurrence_count={bad!r}: {e}")

    def test_string_recurrence_count(self):
        """recurrence_count가 '5' 같은 str이면 int로 변환 시도."""
        result = get_next_ladder_rung("L0", recurrence_count="5")
        # 재발 있음 → 에스컬레이션
        assert result["next_rung"] == "L1"
