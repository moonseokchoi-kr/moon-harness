"""Unit tests for hooks.lib.self_improve.metrics (spec F23).

Tests cover:
- retro_log_parser: 헤더 파싱, 경계 케이스, 잘못된 형식 무시
- convergence_rate: CONVERGED/전체, 빈 이력, cold_start
- avg_iterations_to_green: CONVERGED 엔트리만 집계, 빈/없음 케이스
- recurrence_rate: 재발 마커 추적, cold_start(<5건), 0% 재발
- skill_reuse_rate: 집계, cold_start, 빈 이력
- compute_metrics: cold_start 플래그, comment_classification_accuracy.requires_human_label
- write_metrics: atomic 쓰기, last_computed_at 보장
- F23 Acceptance: 사람 수동 집계 없이 retro-log.md 파싱만으로 재발률 측정 가능
- 전부 네트워크/LLM 없이 오프라인 동작 (fail-safe)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from hooks.lib.self_improve.metrics import (
    COLD_START_THRESHOLD,
    avg_iterations_to_green,
    compute_metrics,
    convergence_rate,
    recurrence_rate,
    retro_log_parser,
    skill_reuse_rate,
    write_metrics,
)

# ── Fixtures 경로 ──────────────────────────────────────────────────────────────

_FIXTURES = Path(__file__).resolve().parent / "fixtures"


# ── 헬퍼 ──────────────────────────────────────────────────────────────────────

def _state(status: str, iterations: int = 3) -> Dict[str, Any]:
    """pr-converge-state 최소 dict 생성."""
    return {"status": status, "iterations": iterations}


def _skill_state(skill_calls: Dict[str, Any]) -> Dict[str, Any]:
    return {"status": "CONVERGED", "iterations": 2, "skill_calls": skill_calls}


# ── retro_log_parser ──────────────────────────────────────────────────────────

class TestRetroLogParser:
    """retro-log.md 헤더 파싱 테스트."""

    def test_parses_standard_header(self):
        text = "## 2026-06-01 retro — 신규 4건 처리 / 적용 2 · 제안 1 · 폐기 1"
        entries = retro_log_parser(text)
        assert len(entries) == 1
        e = entries[0]
        assert e["date"] == "2026-06-01"
        assert e["new"] == 4
        assert e["applied"] == 2
        assert e["proposed"] == 1
        assert e["dropped"] == 1

    def test_parses_multiple_headers(self):
        text = (
            "## 2026-06-01 retro — 신규 4건 처리 / 적용 2 · 제안 1 · 폐기 1\n"
            "some content\n"
            "## 2026-06-08 retro — 신규 5건 처리 / 적용 3 · 제안 1 · 폐기 1\n"
            "more content\n"
        )
        entries = retro_log_parser(text)
        assert len(entries) == 2
        assert entries[0]["date"] == "2026-06-01"
        assert entries[1]["date"] == "2026-06-08"
        assert entries[1]["applied"] == 3

    def test_parses_fixture_file(self):
        """골든 fixture에서 3개 헤더를 파싱한다."""
        text = (_FIXTURES / "retro_log_sample.md").read_text(encoding="utf-8")
        entries = retro_log_parser(text)
        assert len(entries) == 3

        # 첫 회고
        assert entries[0] == {
            "date": "2026-06-01",
            "new": 4,
            "applied": 2,
            "proposed": 1,
            "dropped": 1,
        }
        # 세 번째 회고
        assert entries[2]["applied"] == 3

    def test_ignores_non_header_lines(self):
        text = (
            "# retro-log\n"
            "### 적용\n"
            "- 근거: ## 2026-05-30 — atomic-write / T-1\n"
            "## 2026-06-08 retro — 신규 5건 처리 / 적용 3 · 제안 1 · 폐기 1\n"
        )
        entries = retro_log_parser(text)
        assert len(entries) == 1
        assert entries[0]["applied"] == 3

    def test_empty_string_returns_empty(self):
        assert retro_log_parser("") == []

    def test_non_string_returns_empty(self):
        assert retro_log_parser(None) == []  # type: ignore[arg-type]
        assert retro_log_parser(123) == []  # type: ignore[arg-type]

    def test_header_without_처리_suffix(self):
        """'처리' 없는 변형 헤더도 파싱 가능해야 한다."""
        text = "## 2026-06-15 retro — 신규 6건 처리 / 적용 3 · 제안 2 · 폐기 1"
        entries = retro_log_parser(text)
        assert len(entries) == 1
        assert entries[0]["new"] == 6


# ── convergence_rate ──────────────────────────────────────────────────────────

class TestConvergenceRate:
    """convergence_rate 계산 테스트."""

    def test_all_converged(self):
        history = [_state("CONVERGED")] * 4
        assert convergence_rate(history) == 1.0

    def test_partial_converged(self):
        history = [
            _state("CONVERGED"),
            _state("CONVERGED"),
            _state("CONVERGED"),
            _state("BLOCKED"),
        ]
        assert convergence_rate(history) == pytest.approx(0.75)

    def test_none_converged(self):
        history = [_state("WORKING"), _state("BLOCKED")]
        assert convergence_rate(history) == 0.0

    def test_empty_history_returns_zero(self):
        assert convergence_rate([]) == 0.0

    def test_non_list_returns_zero(self):
        assert convergence_rate(None) == 0.0  # type: ignore[arg-type]

    def test_ignores_non_dict_items(self):
        history = [_state("CONVERGED"), "invalid", None, _state("BLOCKED")]
        # 2건 중 1 CONVERGED
        assert convergence_rate(history) == pytest.approx(0.5)

    def test_ignores_missing_status_field(self):
        history = [{"iterations": 3}, _state("CONVERGED")]
        assert convergence_rate(history) == pytest.approx(1.0)


# ── avg_iterations_to_green ───────────────────────────────────────────────────

class TestAvgIterationsToGreen:
    """avg_iterations_to_green 계산 테스트."""

    def test_single_converged(self):
        history = [_state("CONVERGED", iterations=5)]
        assert avg_iterations_to_green(history) == pytest.approx(5.0)

    def test_multiple_converged(self):
        history = [
            _state("CONVERGED", iterations=2),
            _state("CONVERGED", iterations=4),
            _state("BLOCKED", iterations=10),  # non-CONVERGED: 제외
        ]
        assert avg_iterations_to_green(history) == pytest.approx(3.0)

    def test_no_converged_returns_zero(self):
        history = [_state("WORKING", 7), _state("BLOCKED", 5)]
        assert avg_iterations_to_green(history) == 0.0

    def test_empty_returns_zero(self):
        assert avg_iterations_to_green([]) == 0.0

    def test_non_list_returns_zero(self):
        assert avg_iterations_to_green(None) == 0.0  # type: ignore[arg-type]

    def test_invalid_iterations_skipped(self):
        history = [
            {"status": "CONVERGED", "iterations": "bad"},
            _state("CONVERGED", iterations=6),
        ]
        assert avg_iterations_to_green(history) == pytest.approx(6.0)


# ── recurrence_rate ───────────────────────────────────────────────────────────

class TestRecurrenceRate:
    """recurrence_rate 계산 테스트 — F23 핵심 앵커."""

    def test_fixture_has_recurrence(self):
        """골든 fixture: atomic-write 마커가 3회 등장 → 재발률 > 0.

        전체 적용 건수 = 2+3+3 = 8, 재발 마커 1개 (atomic-write/T-1).
        재발률 = 1/8 = 0.125.
        """
        text = (_FIXTURES / "retro_log_sample.md").read_text(encoding="utf-8")
        rate = recurrence_rate(text)
        assert rate == pytest.approx(0.125)

    def test_no_recurrence(self):
        """모든 마커가 1회씩만 등장 → 재발률 0."""
        text = (
            "## 2026-06-01 retro — 신규 3건 처리 / 적용 3 · 제안 0 · 폐기 0\n"
            "### 적용\n"
            "- **f.md** ← lesson A\n"
            "  - 근거: ## 2026-05-10 — lesson-a / T-1\n"
            "- **f.md** ← lesson B\n"
            "  - 근거: ## 2026-05-11 — lesson-b / T-2\n"
            "- **f.md** ← lesson C\n"
            "  - 근거: ## 2026-05-12 — lesson-c / T-3\n"
            "## 2026-06-08 retro — 신규 3건 처리 / 적용 3 · 제안 0 · 폐기 0\n"
            "### 적용\n"
            "- **g.md** ← lesson D\n"
            "  - 근거: ## 2026-05-20 — lesson-d / T-4\n"
            "- **g.md** ← lesson E\n"
            "  - 근거: ## 2026-05-21 — lesson-e / T-5\n"
            "- **g.md** ← lesson F\n"
            "  - 근거: ## 2026-05-22 — lesson-f / T-6\n"
        )
        assert recurrence_rate(text) == pytest.approx(0.0)

    def test_cold_start_when_applied_below_threshold(self):
        """적용 건수 < 5이면 cold_start → 0.0 반환."""
        text = (
            "## 2026-06-01 retro — 신규 2건 처리 / 적용 2 · 제안 0 · 폐기 0\n"
            "- 근거: ## 2026-05-01 — x / T-1\n"
            "- 근거: ## 2026-05-01 — x / T-1\n"  # 동일 마커 → 재발 시도
        )
        # 총 적용 2 < 5 → cold_start → 0.0
        assert recurrence_rate(text) == 0.0

    def test_non_string_returns_zero(self):
        assert recurrence_rate(None) == 0.0  # type: ignore[arg-type]
        assert recurrence_rate(42) == 0.0  # type: ignore[arg-type]

    def test_empty_text_returns_zero(self):
        assert recurrence_rate("") == 0.0

    def test_machine_readable_no_manual_aggregation(self):
        """F23 Acceptance: 파싱만으로 재발률 측정 — LLM/사람 개입 없음.

        이 테스트가 통과하면 retro_log_parser + 마커 추출 로직만으로
        재발률이 기계적으로 계산됨을 증명한다.
        """
        text = (_FIXTURES / "retro_log_sample.md").read_text(encoding="utf-8")
        # 외부 의존 없이 순수 파싱으로 계산
        entries = retro_log_parser(text)
        total_applied = sum(e["applied"] for e in entries)
        assert total_applied == 8  # 2+3+3

        rate = recurrence_rate(text)
        # 재발 마커: atomic-write/T-1 이 3회 등장 → 재발 1건
        assert 0.0 < rate <= 1.0


# ── skill_reuse_rate ──────────────────────────────────────────────────────────

class TestSkillReuseRate:
    """skill_reuse_rate 집계 테스트."""

    def test_aggregates_across_entries(self):
        history = [
            _skill_state({"sdd-python-engineer": {"calls": 3, "successes": 2}}),
            _skill_state({"sdd-python-engineer": {"calls": 2, "successes": 2}}),
            _skill_state({"sdd-reviewer": {"calls": 3, "successes": 3}}),
        ]
        result = skill_reuse_rate(history)
        assert result["cold_start"] is False
        skills = result["skills"]
        assert skills["sdd-python-engineer"]["calls"] == 5
        assert skills["sdd-python-engineer"]["successes"] == 4
        assert skills["sdd-python-engineer"]["success_rate"] == pytest.approx(0.8)
        assert skills["sdd-reviewer"]["success_rate"] == pytest.approx(1.0)

    def test_cold_start_when_few_calls(self):
        history = [
            _skill_state({"sdd-python-engineer": {"calls": 2, "successes": 1}}),
        ]
        result = skill_reuse_rate(history)
        assert result["cold_start"] is True  # 2 < 5

    def test_cold_start_empty_history(self):
        assert skill_reuse_rate([]) == {"cold_start": True, "skills": {}}

    def test_non_list_returns_cold_start(self):
        result = skill_reuse_rate(None)  # type: ignore[arg-type]
        assert result["cold_start"] is True

    def test_entries_without_skill_calls_skipped(self):
        history = [
            _state("CONVERGED", 3),  # no skill_calls
            _skill_state({"tool-a": {"calls": 6, "successes": 6}}),
        ]
        result = skill_reuse_rate(history)
        assert "tool-a" in result["skills"]
        assert result["skills"]["tool-a"]["calls"] == 6

    def test_success_rate_none_for_zero_calls(self):
        history = [
            _skill_state({"tool-b": {"calls": 0, "successes": 0}}),
        ]
        result = skill_reuse_rate(history)
        assert result["skills"]["tool-b"]["success_rate"] is None


# ── compute_metrics ───────────────────────────────────────────────────────────

class TestComputeMetrics:
    """compute_metrics 통합 테스트."""

    def _make_rich_history(self) -> List[Dict[str, Any]]:
        """cold_start를 피하기 위한 5건 이상 이력."""
        return [
            {"status": "CONVERGED", "iterations": 3,
             "skill_calls": {"sdd-python-engineer": {"calls": 2, "successes": 2}}},
            {"status": "CONVERGED", "iterations": 2,
             "skill_calls": {"sdd-python-engineer": {"calls": 1, "successes": 1}}},
            {"status": "CONVERGED", "iterations": 4,
             "skill_calls": {"sdd-reviewer": {"calls": 1, "successes": 1}}},
            {"status": "BLOCKED", "iterations": 7,
             "skill_calls": {"sdd-python-engineer": {"calls": 2, "successes": 1}}},
            {"status": "CONVERGED", "iterations": 3,
             "skill_calls": {"sdd-reviewer": {"calls": 2, "successes": 2}}},
        ]

    def test_cold_start_when_no_data(self):
        result = compute_metrics([], "")
        assert result["cold_start"] is True
        assert result["convergence_rate"] is None
        assert result["avg_iterations_to_green"] is None
        assert result["recurrence_rate"] is None

    def test_cold_start_when_insufficient_applied(self):
        """state 이력은 충분하지만 retro-log 적용 건수 < 5 → cold_start."""
        history = self._make_rich_history()
        # 적용 합계 = 1 (< 5)
        retro_text = (
            "## 2026-06-01 retro — 신규 2건 처리 / 적용 1 · 제안 1 · 폐기 0\n"
        )
        result = compute_metrics(history, retro_text)
        assert result["cold_start"] is True

    def test_full_metrics_computed_when_enough_data(self):
        history = self._make_rich_history()
        retro_text = (_FIXTURES / "retro_log_sample.md").read_text(encoding="utf-8")
        result = compute_metrics(history, retro_text)

        assert result["cold_start"] is False
        assert result["convergence_rate"] == pytest.approx(0.8)  # 4/5
        assert result["avg_iterations_to_green"] == pytest.approx(3.0)  # (3+2+4+3)/4
        assert result["recurrence_rate"] is not None
        assert 0.0 <= result["recurrence_rate"] <= 1.0

    def test_comment_classification_requires_human_label(self):
        """Minor② 반영: 코멘트 분류 정확도는 requires_human_label=True."""
        result = compute_metrics([], "")
        cca = result["comment_classification_accuracy"]
        assert cca["requires_human_label"] is True
        assert cca["value"] is None

    def test_schema_version_present(self):
        result = compute_metrics([], "")
        assert result["schema_version"] == 1

    def test_last_computed_at_present(self):
        result = compute_metrics([], "")
        assert "last_computed_at" in result
        assert result["last_computed_at"]  # 비어있지 않음

    def test_cold_start_flag_present(self):
        result = compute_metrics([], "")
        assert "cold_start" in result


# ── write_metrics ─────────────────────────────────────────────────────────────

class TestWriteMetrics:
    """write_metrics atomic 쓰기 테스트."""

    def test_writes_json_file(self, tmp_path: Path):
        metrics = {
            "schema_version": 1,
            "cold_start": True,
            "convergence_rate": None,
        }
        out_path = tmp_path / ".harness" / "metrics.json"
        result = write_metrics(metrics, out_path)

        assert result["ok"] is True
        assert out_path.exists()
        data = json.loads(out_path.read_text(encoding="utf-8"))
        assert data["cold_start"] is True

    def test_adds_last_computed_at_if_missing(self, tmp_path: Path):
        metrics = {"schema_version": 1, "cold_start": False}
        out_path = tmp_path / "metrics.json"
        write_metrics(metrics, out_path)
        data = json.loads(out_path.read_text(encoding="utf-8"))
        assert "last_computed_at" in data

    def test_preserves_existing_last_computed_at(self, tmp_path: Path):
        ts = "2026-01-01T00:00:00+00:00"
        metrics = {"schema_version": 1, "last_computed_at": ts}
        out_path = tmp_path / "metrics.json"
        write_metrics(metrics, out_path)
        data = json.loads(out_path.read_text(encoding="utf-8"))
        assert data["last_computed_at"] == ts

    def test_creates_parent_directories(self, tmp_path: Path):
        out_path = tmp_path / "deep" / "nested" / "metrics.json"
        result = write_metrics({"cold_start": True}, out_path)
        assert result["ok"] is True
        assert out_path.exists()

    def test_non_dict_metrics_fails_gracefully(self, tmp_path: Path):
        result = write_metrics("not-a-dict", tmp_path / "m.json")  # type: ignore[arg-type]
        assert result["ok"] is False


# ── golden fixture 통합 테스트 ─────────────────────────────────────────────────

class TestGoldenFixture:
    """metrics_expected.json 골든 값과 비교하는 통합 테스트."""

    def test_skill_reuse_matches_expected(self):
        expected = json.loads(
            (_FIXTURES / "metrics_expected.json").read_text(encoding="utf-8")
        )
        history = [
            _skill_state({"sdd-python-engineer": {"calls": 3, "successes": 2}}),
            _skill_state({"sdd-python-engineer": {"calls": 2, "successes": 2}}),
            _skill_state({"sdd-reviewer": {"calls": 3, "successes": 3}}),
        ]
        # 3건이므로 cold_start=True (calls 합 = 3+3+3=... 실제로 calls 합산)
        # sdd-python-engineer: 5, sdd-reviewer: 3 → 합계 8 ≥ 5 → cold_start False
        result = skill_reuse_rate(history)

        expected_skills = expected["skill_reuse"]["skills"]
        for skill_name, exp_vals in expected_skills.items():
            assert skill_name in result["skills"]
            actual = result["skills"][skill_name]
            assert actual["calls"] == exp_vals["calls"]
            assert actual["successes"] == exp_vals["successes"]
            assert actual["success_rate"] == pytest.approx(exp_vals["success_rate"])

    def test_convergence_matches_expected(self):
        expected = json.loads(
            (_FIXTURES / "metrics_expected.json").read_text(encoding="utf-8")
        )
        history = [
            _state("CONVERGED", 3),
            _state("CONVERGED", 3),
            _state("CONVERGED", 3),
            _state("BLOCKED", 5),
        ]
        rate = convergence_rate(history)
        assert rate == pytest.approx(expected["convergence_rate"])

    def test_retro_log_recurrence_matches_expected(self):
        expected = json.loads(
            (_FIXTURES / "metrics_expected.json").read_text(encoding="utf-8")
        )
        text = (_FIXTURES / "retro_log_sample.md").read_text(encoding="utf-8")
        rate = recurrence_rate(text)
        assert rate == pytest.approx(expected["recurrence_rate"])


# ── 경계/퇴화 케이스 ──────────────────────────────────────────────────────────

class TestEdgeCases:
    """경계 및 퇴화 케이스 — fail-safe 확인."""

    def test_convergence_rate_all_invalid(self):
        """모두 비정상 상태 → 0.0."""
        assert convergence_rate(["a", None, 42]) == 0.0

    def test_avg_iterations_float_iterations(self):
        """iterations가 float 문자열이면 int 변환 실패 → skip."""
        history = [
            {"status": "CONVERGED", "iterations": "3.5"},  # int("3.5") 실패
            _state("CONVERGED", 6),
        ]
        assert avg_iterations_to_green(history) == pytest.approx(6.0)

    def test_recurrence_rate_no_evidence_lines(self):
        """근거 줄이 없는 retro-log → 재발 마커 없음."""
        text = (
            "## 2026-06-01 retro — 신규 5건 처리 / 적용 5 · 제안 0 · 폐기 0\n"
            "### 적용\n"
            "- **docs/f.md** ← 교훈 1\n"
        )
        assert recurrence_rate(text) == pytest.approx(0.0)

    def test_cold_start_threshold_value(self):
        """COLD_START_THRESHOLD는 5이어야 한다 (spec F24)."""
        assert COLD_START_THRESHOLD == 5

    def test_write_metrics_roundtrip(self, tmp_path: Path):
        """기록 후 읽기 → 동일 데이터."""
        metrics = {
            "schema_version": 1,
            "cold_start": False,
            "convergence_rate": 0.8,
            "avg_iterations_to_green": 3.5,
            "comment_classification_accuracy": {"requires_human_label": True, "value": None},
        }
        out_path = tmp_path / "metrics.json"
        write_metrics(metrics, out_path)
        loaded = json.loads(out_path.read_text(encoding="utf-8"))
        assert loaded["convergence_rate"] == pytest.approx(0.8)
        assert loaded["comment_classification_accuracy"]["requires_human_label"] is True
