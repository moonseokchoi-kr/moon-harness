"""tests/test_cap_cadence.py — cap, cadence, circuit_breaker 단위 테스트.

오프라인 전용. 네트워크/LLM 무호출.

커버 범위:
- check_circuit_breaker: fix_attempts 경계(3 → BLOCKED), iterations 경계(16 → BLOCKED)
- compute_cadence: WORKING/WAITING → 270, NEEDS_HUMAN → 1200, CONVERGED/BLOCKED → None
                   300 반환 없음 어서션
- apply_cap: 상한 이내 그대로, 6건 → 5+1 트런케이션
- cap_report: truncated 플래그 확인
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from hooks.lib.self_improve.circuit_breaker import (
    FIX_ATTEMPTS_THRESHOLD,
    ITERATIONS_THRESHOLD,
    check_circuit_breaker,
    compute_cadence,
)
from hooks.lib.self_improve.cap import (
    DEFAULT_CAP,
    apply_cap,
    cap_report,
)


# ─── check_circuit_breaker ───────────────────────────────────────

class TestCheckCircuitBreaker:

    def test_no_block_empty_state(self):
        """비어 있는 상태: 블록되지 않아야 한다."""
        result = check_circuit_breaker({})
        assert result["blocked"] is False

    def test_no_block_below_threshold(self):
        """fix_attempts가 임계값 미만이면 블록되지 않는다."""
        state = {"fix_attempts": {"ci-lint": 2}, "iterations": 3}
        result = check_circuit_breaker(state)
        assert result["blocked"] is False

    def test_block_fix_attempts_exactly_threshold(self):
        """fix_attempts가 정확히 임계값(3)이면 BLOCKED."""
        state = {
            "fix_attempts": {"ci-lint": FIX_ATTEMPTS_THRESHOLD},
            "iterations": 1,
        }
        result = check_circuit_breaker(state)
        assert result["blocked"] is True
        assert "signal" in result
        assert result["signal"] == "ci-lint"

    def test_block_fix_attempts_above_threshold(self):
        """fix_attempts >= 3이면 BLOCKED."""
        state = {"fix_attempts": {"test-fail": 5}, "iterations": 2}
        result = check_circuit_breaker(state)
        assert result["blocked"] is True
        assert result["signal"] == "test-fail"

    def test_block_multiple_signals_one_over(self):
        """여러 신호 중 하나가 임계값 이상이면 BLOCKED."""
        state = {
            "fix_attempts": {"lint": 1, "build": 3, "test": 2},
            "iterations": 5,
        }
        result = check_circuit_breaker(state)
        assert result["blocked"] is True
        assert result["signal"] == "build"

    def test_no_block_iterations_at_threshold(self):
        """iterations == 15는 BLOCKED가 아니다 (초과가 아니므로)."""
        state = {"fix_attempts": {}, "iterations": ITERATIONS_THRESHOLD}
        result = check_circuit_breaker(state)
        assert result["blocked"] is False

    def test_block_iterations_exceed_threshold(self):
        """iterations > 15이면 BLOCKED (16회 패스에서 발동)."""
        state = {"fix_attempts": {}, "iterations": ITERATIONS_THRESHOLD + 1}
        result = check_circuit_breaker(state)
        assert result["blocked"] is True
        assert result["iterations"] == ITERATIONS_THRESHOLD + 1

    def test_block_iterations_far_above(self):
        """iterations가 훨씬 크면 BLOCKED."""
        state = {"fix_attempts": {}, "iterations": 100}
        result = check_circuit_breaker(state)
        assert result["blocked"] is True

    def test_reason_field_present_when_blocked(self):
        """BLOCKED 시 reason 필드가 있어야 한다."""
        state = {"fix_attempts": {"x": 3}, "iterations": 1}
        result = check_circuit_breaker(state)
        assert result["blocked"] is True
        assert isinstance(result.get("reason"), str)
        assert len(result["reason"]) > 0

    def test_fail_safe_non_dict_state(self):
        """state가 dict가 아니면 블록되지 않고 raise하지 않는다."""
        for bad in [None, "string", 42, [1, 2, 3]]:
            result = check_circuit_breaker(bad)
            assert result["blocked"] is False, f"Expected not blocked for {bad!r}"

    def test_fail_safe_bad_count_type(self):
        """fix_attempts 값이 숫자가 아닌 경우 무시하고 계속 처리한다."""
        state = {"fix_attempts": {"bad": "not-a-number", "good": 3}, "iterations": 0}
        result = check_circuit_breaker(state)
        # "good" 신호가 3이므로 BLOCKED
        assert result["blocked"] is True

    def test_no_fix_attempts_key(self):
        """fix_attempts 키가 없어도 fail-safe하게 동작."""
        state = {"iterations": 10}
        result = check_circuit_breaker(state)
        assert result["blocked"] is False


# ─── compute_cadence ─────────────────────────────────────────────

class TestComputeCadence:

    def test_working_returns_270(self):
        assert compute_cadence("WORKING") == 270

    def test_waiting_returns_270(self):
        assert compute_cadence("WAITING") == 270

    def test_needs_human_returns_1200(self):
        assert compute_cadence("NEEDS_HUMAN") == 1200

    def test_converged_returns_none(self):
        assert compute_cadence("CONVERGED") is None

    def test_blocked_returns_none(self):
        assert compute_cadence("BLOCKED") is None

    def test_300_never_returned(self):
        """300초는 절대 반환되지 않는다 — 핵심 spec 제약."""
        all_statuses = [
            "WORKING", "WAITING", "NEEDS_HUMAN",
            "CONVERGED", "BLOCKED",
            # 알 수 없는 상태
            "UNKNOWN", "", "whatever",
        ]
        for s in all_statuses:
            result = compute_cadence(s)
            assert result != 300, f"compute_cadence({s!r}) must not return 300"

    def test_unknown_status_returns_none(self):
        """알 수 없는 status는 None (보수적 기본값)."""
        assert compute_cadence("FOOBAR") is None
        assert compute_cadence("") is None

    def test_case_insensitive(self):
        """status는 대소문자 구분 없이 처리한다."""
        assert compute_cadence("working") == 270
        assert compute_cadence("Waiting") == 270
        assert compute_cadence("needs_human") == 1200
        assert compute_cadence("converged") is None
        assert compute_cadence("blocked") is None

    def test_fail_safe_non_string(self):
        """status가 str이 아니면 None 반환, raise하지 않는다."""
        for bad in [None, 42, [], {}]:
            result = compute_cadence(bad)
            assert result is None, f"Expected None for {bad!r}"
            assert result != 300


# ─── apply_cap ───────────────────────────────────────────────────

class TestApplyCap:

    def test_below_cap_no_truncation(self):
        """후보가 상한보다 적으면 그대로 반환하고 초과분은 빈 리스트."""
        candidates = [1, 2, 3]
        applied, deferred = apply_cap(candidates, cap=5)
        assert applied == [1, 2, 3]
        assert deferred == []

    def test_exactly_cap_no_truncation(self):
        """후보가 정확히 상한이면 초과 없음."""
        candidates = list(range(5))
        applied, deferred = apply_cap(candidates, cap=5)
        assert len(applied) == 5
        assert deferred == []

    def test_six_candidates_truncated_to_five(self):
        """6건 후보 → 적용 5건 + 초과 1건 (F13 Acceptance)."""
        candidates = ["a", "b", "c", "d", "e", "f"]
        applied, deferred = apply_cap(candidates, cap=5)
        assert applied == ["a", "b", "c", "d", "e"]
        assert deferred == ["f"]
        assert len(applied) == 5
        assert len(deferred) == 1

    def test_many_candidates_truncated(self):
        """10건 후보, cap=5 → 5+5."""
        candidates = list(range(10))
        applied, deferred = apply_cap(candidates, cap=5)
        assert len(applied) == 5
        assert len(deferred) == 5
        assert applied == [0, 1, 2, 3, 4]
        assert deferred == [5, 6, 7, 8, 9]

    def test_custom_cap(self):
        """cap 파라미터 커스텀 동작."""
        candidates = list(range(8))
        applied, deferred = apply_cap(candidates, cap=3)
        assert len(applied) == 3
        assert len(deferred) == 5

    def test_empty_candidates(self):
        """빈 후보 리스트: ([], [])."""
        applied, deferred = apply_cap([], cap=5)
        assert applied == []
        assert deferred == []

    def test_fail_safe_non_list(self):
        """candidates가 리스트가 아니면 ([], []) 반환, raise 금지."""
        for bad in [None, "string", 42, {"a": 1}]:
            applied, deferred = apply_cap(bad, cap=5)
            assert applied == []
            assert deferred == []

    def test_default_cap_is_five(self):
        """기본 cap은 5."""
        assert DEFAULT_CAP == 5
        candidates = list(range(7))
        applied, deferred = apply_cap(candidates)  # cap=5 기본값
        assert len(applied) == 5
        assert len(deferred) == 2


# ─── cap_report ──────────────────────────────────────────────────

class TestCapReport:

    def test_no_truncation_report(self):
        """상한 이내: truncated=False."""
        report = cap_report([1, 2, 3], cap=5)
        assert report["truncated"] is False
        assert report["deferred_count"] == 0
        assert report["applied_count"] == 3
        assert report["applied"] == [1, 2, 3]
        assert report["deferred"] == []

    def test_truncation_report_six_items(self):
        """6건 후보: truncated=True, deferred_count=1."""
        candidates = ["a", "b", "c", "d", "e", "f"]
        report = cap_report(candidates, cap=5)
        assert report["truncated"] is True
        assert report["applied_count"] == 5
        assert report["deferred_count"] == 1
        assert report["deferred"] == ["f"]

    def test_truncated_implies_deferred_count_positive(self):
        """truncated=True이면 deferred_count > 0 (silent truncation 금지)."""
        report = cap_report(list(range(10)), cap=5)
        if report["truncated"]:
            assert report["deferred_count"] > 0
