"""tests/test_bench_runner.py — bench_runner 점수 산술 단위 테스트.

커버리지:
- score_baseline: 골든 픽스처 기반 baseline 점수 산출
- score_candidate: candidate_fn 기반 점수 산출
- compute_delta: delta 양수(채택 가능), 음수(채택 불가), zero, cold_start, held_out_regression
- is_adoptable: 채택 게이트 로직 종합 검증
- score_baseline/score_candidate: cold_start 인정 (N < 5 케이스)
- fail-safe: 잘못된 입력에도 cold_start=True 반환

모든 테스트는 네트워크/LLM 호출 없이 동작한다 (offline 마커).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from hooks.lib.self_improve.bench_runner import (
    compute_delta,
    gate_adoption,
    is_adoptable,
    score_baseline,
    score_candidate,
)

# ── 픽스처 경로 ────────────────────────────────────────────────────────────────
_FIXTURES = Path(__file__).resolve().parent / "fixtures"
_TRAIN_SET = (
    Path(__file__).resolve().parents[1]
    / "benchmarks" / "sets" / "train"
)
_HELD_OUT_SET = (
    Path(__file__).resolve().parents[1]
    / "benchmarks" / "sets" / "held-out"
)


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

def _make_score(
    total: int,
    passed: int,
    cold_start: bool | None = None,
) -> dict[str, Any]:
    """점수 dict를 빠르게 생성한다."""
    if cold_start is None:
        from hooks.lib.self_improve.bench_runner import _COLD_START_THRESHOLD
        cold_start = total < _COLD_START_THRESHOLD
    failed = total - passed
    score_pct = (passed / total * 100.0) if total > 0 else 0.0
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "score_pct": score_pct,
        "cold_start": cold_start,
    }


# ---------------------------------------------------------------------------
# score_baseline 테스트
# ---------------------------------------------------------------------------

@pytest.mark.offline
class TestScoreBaseline:
    """score_baseline: 골든 픽스처 + train 셋 기반 검증."""

    def test_train_set_returns_score_dict(self):
        """train 셋이 3개 케이스(N < 5)이므로 cold_start=True를 반환한다."""
        result = score_baseline(_TRAIN_SET)
        assert "total" in result
        assert "score_pct" in result
        assert "cold_start" in result
        # train 셋 케이스 수는 3 < 5 → cold_start
        assert result["cold_start"] is True

    def test_nonexistent_path_returns_cold_start(self, tmp_path: Path):
        """존재하지 않는 경로는 cold_start=True를 반환한다."""
        result = score_baseline(tmp_path / "nonexistent")
        assert result["cold_start"] is True
        assert result["total"] == 0
        assert result["score_pct"] == 0.0

    def test_empty_dir_returns_cold_start(self, tmp_path: Path):
        """빈 디렉토리(케이스 0개)는 cold_start=True를 반환한다."""
        result = score_baseline(tmp_path)
        assert result["cold_start"] is True
        assert result["total"] == 0

    def test_json_file_with_invalid_format_skipped(self, tmp_path: Path):
        """파싱 불가 JSON 파일은 건너뛰고 나머지만 집계한다."""
        (tmp_path / "bad.json").write_text("not json{{{", encoding="utf-8")
        result = score_baseline(tmp_path)
        assert result["total"] == 0
        assert result["cold_start"] is True

    def test_5_cases_not_cold_start(self, tmp_path: Path):
        """케이스가 정확히 5개이면 cold_start=False를 반환한다."""
        for i in range(5):
            case = {
                "id": f"tc-{i:03d}",
                "label": "pass",
                "expected_outcome": "CONVERGED",
                "input": {},
            }
            (tmp_path / f"tc-{i:03d}.json").write_text(
                json.dumps(case), encoding="utf-8"
            )
        result = score_baseline(tmp_path)
        assert result["total"] == 5
        assert result["cold_start"] is False
        assert result["score_pct"] == 100.0

    def test_mixed_pass_fail_labels(self, tmp_path: Path):
        """pass/fail 레이블이 섞인 케이스를 올바르게 집계한다."""
        for i in range(5):
            label = "pass" if i < 3 else "fail"
            case = {
                "id": f"tc-{i:03d}",
                "label": label,
                "expected_outcome": "CONVERGED",
                "input": {},
            }
            (tmp_path / f"tc-{i:03d}.json").write_text(
                json.dumps(case), encoding="utf-8"
            )
        result = score_baseline(tmp_path)
        assert result["total"] == 5
        assert result["passed"] == 3
        assert result["failed"] == 2
        assert result["score_pct"] == 60.0
        assert result["cold_start"] is False


# ---------------------------------------------------------------------------
# score_candidate 테스트
# ---------------------------------------------------------------------------

@pytest.mark.offline
class TestScoreCandidate:
    """score_candidate: candidate_fn 기반 검증."""

    def test_perfect_candidate_fn(self, tmp_path: Path):
        """모든 케이스를 맞히는 candidate_fn은 100% 점수를 반환한다."""
        for i in range(5):
            case = {
                "id": f"tc-{i:03d}",
                "label": "pass",
                "expected_outcome": "CONVERGED",
                "input": {},
            }
            (tmp_path / f"tc-{i:03d}.json").write_text(
                json.dumps(case), encoding="utf-8"
            )

        def perfect_fn(inp: dict) -> str:
            return "CONVERGED"

        result = score_candidate(tmp_path, perfect_fn)
        assert result["score_pct"] == 100.0
        assert result["cold_start"] is False

    def test_zero_candidate_fn(self, tmp_path: Path):
        """모든 케이스를 틀리는 candidate_fn은 0% 점수를 반환한다."""
        for i in range(5):
            case = {
                "id": f"tc-{i:03d}",
                "label": "pass",
                "expected_outcome": "CONVERGED",
                "input": {},
            }
            (tmp_path / f"tc-{i:03d}.json").write_text(
                json.dumps(case), encoding="utf-8"
            )

        def wrong_fn(inp: dict) -> str:
            return "BLOCKED"

        result = score_candidate(tmp_path, wrong_fn)
        assert result["score_pct"] == 0.0
        assert result["cold_start"] is False

    def test_candidate_fn_exception_counts_as_fail(self, tmp_path: Path):
        """candidate_fn이 예외를 발생시키는 케이스는 fail로 처리된다."""
        for i in range(5):
            case = {
                "id": f"tc-{i:03d}",
                "label": "pass",
                "expected_outcome": "CONVERGED",
                "input": {},
            }
            (tmp_path / f"tc-{i:03d}.json").write_text(
                json.dumps(case), encoding="utf-8"
            )

        def crashing_fn(inp: dict) -> str:
            raise RuntimeError("crash")

        result = score_candidate(tmp_path, crashing_fn)
        assert result["passed"] == 0
        assert result["failed"] == 5
        assert result["cold_start"] is False

    def test_cold_start_fewer_than_5_cases(self, tmp_path: Path):
        """케이스 4개는 cold_start=True를 반환한다."""
        for i in range(4):
            case = {
                "id": f"tc-{i:03d}",
                "label": "pass",
                "expected_outcome": "CONVERGED",
                "input": {},
            }
            (tmp_path / f"tc-{i:03d}.json").write_text(
                json.dumps(case), encoding="utf-8"
            )

        def fn(inp: dict) -> str:
            return "CONVERGED"

        result = score_candidate(tmp_path, fn)
        assert result["cold_start"] is True
        assert result["total"] == 4


# ---------------------------------------------------------------------------
# compute_delta 테스트
# ---------------------------------------------------------------------------

@pytest.mark.offline
class TestComputeDelta:
    """compute_delta: delta 산술 + 채택 게이트 로직 검증."""

    def test_golden_fixture_positive_delta(self):
        """골든 픽스처: baseline 80% → candidate 100% → delta=+20.0."""
        baseline = json.loads(
            (_FIXTURES / "bench_baseline.json").read_text(encoding="utf-8")
        )
        candidate = json.loads(
            (_FIXTURES / "bench_candidate.json").read_text(encoding="utf-8")
        )
        result = compute_delta(baseline, candidate)
        assert result["cold_start"] is False
        assert result["delta_pct"] == pytest.approx(20.0)
        assert result["held_out_regression"] is False

    def test_positive_delta_adoptable(self):
        """점수 상승 + 회귀 없음 → 채택 가능."""
        baseline = _make_score(total=5, passed=3)   # 60%
        candidate = _make_score(total=5, passed=5)  # 100%
        result = compute_delta(baseline, candidate)
        assert result["delta_pct"] == pytest.approx(40.0)
        assert result["held_out_regression"] is False
        assert result["cold_start"] is False

    def test_negative_delta_not_adoptable(self):
        """점수 하락 → held_out_regression=True + 채택 불가."""
        baseline = _make_score(total=5, passed=5)   # 100%
        candidate = _make_score(total=5, passed=3)  # 60%
        result = compute_delta(baseline, candidate)
        assert result["delta_pct"] == pytest.approx(-40.0)
        assert result["held_out_regression"] is True
        assert result["cold_start"] is False

    def test_zero_delta(self):
        """점수 동일 → held_out_regression=False, delta_pct=0.0."""
        baseline = _make_score(total=5, passed=4)  # 80%
        candidate = _make_score(total=5, passed=4)  # 80%
        result = compute_delta(baseline, candidate)
        assert result["delta_pct"] == pytest.approx(0.0)
        assert result["held_out_regression"] is False
        assert result["cold_start"] is False

    def test_cold_start_baseline(self):
        """baseline cold_start=True → 전체 cold_start, delta_pct=None."""
        baseline = _make_score(total=3, passed=3)   # cold: total < 5
        candidate = _make_score(total=10, passed=9, cold_start=False)
        assert baseline["cold_start"] is True
        result = compute_delta(baseline, candidate)
        assert result["cold_start"] is True
        assert result["delta_pct"] is None

    def test_cold_start_candidate(self):
        """candidate cold_start=True → 전체 cold_start, delta_pct=None."""
        baseline = _make_score(total=10, passed=8, cold_start=False)
        candidate = _make_score(total=2, passed=2)   # cold: total < 5
        assert candidate["cold_start"] is True
        result = compute_delta(baseline, candidate)
        assert result["cold_start"] is True
        assert result["delta_pct"] is None

    def test_both_cold_start(self):
        """baseline + candidate 모두 cold_start → delta_pct=None."""
        baseline = _make_score(total=1, passed=1)
        candidate = _make_score(total=0, passed=0)
        result = compute_delta(baseline, candidate)
        assert result["cold_start"] is True
        assert result["delta_pct"] is None

    def test_held_out_regression_true_when_score_drops(self):
        """held-out 셋에서 점수 하락 시 held_out_regression=True 반환."""
        baseline = _make_score(total=6, passed=6, cold_start=False)  # 100%
        candidate = _make_score(total=6, passed=5, cold_start=False)  # ~83.3%
        result = compute_delta(baseline, candidate)
        assert result["held_out_regression"] is True

    def test_held_out_no_regression_when_score_same_or_up(self):
        """held-out 셋에서 점수 동일/상승 시 held_out_regression=False."""
        baseline = _make_score(total=6, passed=5, cold_start=False)
        candidate = _make_score(total=6, passed=6, cold_start=False)  # 100%
        result = compute_delta(baseline, candidate)
        assert result["held_out_regression"] is False

    def test_fail_safe_on_malformed_input(self):
        """잘못된 입력(dict 오염)에도 cold_start=True 를 반환한다."""
        result = compute_delta(
            {"score_pct": "not-a-number", "cold_start": False},
            {"score_pct": 80.0, "cold_start": False},
        )
        assert result["cold_start"] is True
        assert result["delta_pct"] is None


# ---------------------------------------------------------------------------
# is_adoptable 테스트
# ---------------------------------------------------------------------------

@pytest.mark.offline
class TestIsAdoptable:
    """is_adoptable: F22 채택 게이트 종합 검증."""

    def test_adoptable_when_score_up_no_regression(self):
        """점수 상승 + 회귀 없음 + 콜드스타트 아님 → 채택 가능."""
        delta = {"delta_pct": 10.0, "held_out_regression": False, "cold_start": False}
        assert is_adoptable(delta) is True

    def test_not_adoptable_score_drop(self):
        """점수 하락 → 채택 불가."""
        delta = {"delta_pct": -5.0, "held_out_regression": True, "cold_start": False}
        assert is_adoptable(delta) is False

    def test_not_adoptable_zero_delta(self):
        """점수 동일(0) → 채택 불가."""
        delta = {"delta_pct": 0.0, "held_out_regression": False, "cold_start": False}
        assert is_adoptable(delta) is False

    def test_not_adoptable_held_out_regression(self):
        """점수 상승이어도 held-out 회귀 → 채택 불가."""
        delta = {"delta_pct": 5.0, "held_out_regression": True, "cold_start": False}
        assert is_adoptable(delta) is False

    def test_not_adoptable_cold_start(self):
        """콜드스타트(delta_pct=None) → 채택 불가."""
        delta = {"delta_pct": None, "held_out_regression": False, "cold_start": True}
        assert is_adoptable(delta) is False

    def test_not_adoptable_cold_start_even_with_score(self):
        """cold_start=True이면 delta_pct가 양수라도 채택 불가."""
        delta = {"delta_pct": 50.0, "held_out_regression": False, "cold_start": True}
        assert is_adoptable(delta) is False

    def test_adoptable_with_large_positive_delta(self):
        """큰 양수 delta → 채택 가능."""
        delta = {"delta_pct": 99.9, "held_out_regression": False, "cold_start": False}
        assert is_adoptable(delta) is True

    def test_golden_fixture_adoptable(self):
        """골든 픽스처(80→100%) → compute_delta 후 is_adoptable=True."""
        baseline = json.loads(
            (_FIXTURES / "bench_baseline.json").read_text(encoding="utf-8")
        )
        candidate = json.loads(
            (_FIXTURES / "bench_candidate.json").read_text(encoding="utf-8")
        )
        delta = compute_delta(baseline, candidate)
        assert is_adoptable(delta) is True


# ---------------------------------------------------------------------------
# gate_adoption 테스트 — F22/F24 채택 게이트 회귀 검증
# ---------------------------------------------------------------------------

@pytest.mark.offline
class TestGateAdoption:
    """gate_adoption: held-out cold_start 포함 채택 게이트 종합 검증 (F22/F24)."""

    def _make_delta(
        self,
        delta_pct: float | None,
        held_out_regression: bool,
        cold_start: bool,
    ) -> dict[str, Any]:
        """compute_delta 반환 형태의 delta dict를 생성한다."""
        return {
            "delta_pct": delta_pct,
            "held_out_regression": held_out_regression,
            "cold_start": cold_start,
        }

    # ── 정상 채택 경로 ───────────────────────────────────────────────────────

    def test_adoptable_when_train_up_held_ok(self):
        """train 점수 상승 + held-out cold_start 아님 + 회귀 없음 → 채택 가능."""
        delta_train = self._make_delta(delta_pct=10.0, held_out_regression=False, cold_start=False)
        delta_held = self._make_delta(delta_pct=5.0, held_out_regression=False, cold_start=False)
        assert gate_adoption(delta_train, delta_held) is True

    # ── held-out cold_start=True → 채택 불가 (F24 핵심 버그 회귀 테스트) ───

    def test_not_adoptable_when_held_out_cold_start(self):
        """held-out cold_start=True(데이터 부족) → 채택 불가 (F24 위반 방지).

        이것이 [P1] 버그 #1의 핵심 회귀 테스트다.
        compute_delta()가 cold_start 시 held_out_regression=False를 반환하므로,
        held_out_regression만 확인하면 cold_start 상황에서 게이트가 무력화된다.
        gate_adoption()은 cold_start를 독립적으로 반드시 확인해야 한다.
        """
        delta_train = self._make_delta(delta_pct=20.0, held_out_regression=False, cold_start=False)
        # held-out 데이터 2건 → cold_start=True, held_out_regression=False (compute_delta 실제 동작)
        delta_held = self._make_delta(delta_pct=None, held_out_regression=False, cold_start=True)
        assert gate_adoption(delta_train, delta_held) is False

    def test_not_adoptable_held_out_cold_start_regardless_of_train(self):
        """held-out cold_start=True이면 train 결과에 관계없이 채택 불가."""
        # train이 완벽한 상승이어도 held-out cold_start가 있으면 불가
        delta_train = self._make_delta(delta_pct=100.0, held_out_regression=False, cold_start=False)
        delta_held = self._make_delta(delta_pct=None, held_out_regression=False, cold_start=True)
        assert gate_adoption(delta_train, delta_held) is False

    # ── train cold_start → 채택 불가 ────────────────────────────────────────

    def test_not_adoptable_when_train_cold_start(self):
        """train cold_start=True → 채택 불가."""
        delta_train = self._make_delta(delta_pct=None, held_out_regression=False, cold_start=True)
        delta_held = self._make_delta(delta_pct=5.0, held_out_regression=False, cold_start=False)
        assert gate_adoption(delta_train, delta_held) is False

    # ── held-out 회귀 → 채택 불가 ────────────────────────────────────────────

    def test_not_adoptable_when_held_out_regression(self):
        """held-out 회귀(held_out_regression=True) → 채택 불가."""
        delta_train = self._make_delta(delta_pct=10.0, held_out_regression=False, cold_start=False)
        delta_held = self._make_delta(delta_pct=-5.0, held_out_regression=True, cold_start=False)
        assert gate_adoption(delta_train, delta_held) is False

    # ── train 점수 하락/동일 → 채택 불가 ────────────────────────────────────

    def test_not_adoptable_when_train_score_drops(self):
        """train 점수 하락 → 채택 불가."""
        delta_train = self._make_delta(delta_pct=-5.0, held_out_regression=True, cold_start=False)
        delta_held = self._make_delta(delta_pct=0.0, held_out_regression=False, cold_start=False)
        assert gate_adoption(delta_train, delta_held) is False

    def test_not_adoptable_when_train_zero_delta(self):
        """train 점수 동일(0) → 채택 불가."""
        delta_train = self._make_delta(delta_pct=0.0, held_out_regression=False, cold_start=False)
        delta_held = self._make_delta(delta_pct=0.0, held_out_regression=False, cold_start=False)
        assert gate_adoption(delta_train, delta_held) is False

    # ── fail-safe ────────────────────────────────────────────────────────────

    def test_fail_safe_on_malformed_delta_train(self):
        """잘못된 delta_train 입력에도 False를 반환한다 (fail-safe)."""
        result = gate_adoption(
            {"cold_start": "not-a-bool"},   # 오염된 dict
            {"cold_start": False, "held_out_regression": False},
        )
        # is_adoptable이 오류를 처리하거나 False 반환 → gate_adoption도 False
        assert result is False

    def test_fail_safe_on_empty_dicts(self):
        """빈 dict 입력에도 False를 반환한다 (fail-safe, 기본값 worst-case)."""
        # 빈 dict → cold_start 기본값 True → False
        assert gate_adoption({}, {}) is False
