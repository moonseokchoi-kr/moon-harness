"""tests/test_eval_harness_structure.py — evals/ 하네스 구조 단위 테스트 (오프라인).

커버리지:
- 시나리오 JSON 포맷 검증 (필수 키 존재, 타입 체크)
- 유효/무효 시나리오 파싱
- 전체 시나리오 파일 로드 가능 여부 (evals/scenarios/*.json)
- run_eval 모듈 import 가능 여부 (구조 검증)
- _to_bench_score 집계 산술 (bench_runner 연계)
- evals/ 가 pytest tests/ collect에 포함되지 않음을 확인하는 메타 검증

모든 테스트는 네트워크/claude 호출 없이 동작한다 (offline 마커).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

# ── 경로 ──────────────────────────────────────────────────────────────────────
_REPO_ROOT = Path(__file__).resolve().parents[1]
_EVALS_DIR = _REPO_ROOT / "evals"
_SCENARIOS_DIR = _EVALS_DIR / "scenarios"

# run_eval 모듈 import (구조 검증)
sys.path.insert(0, str(_REPO_ROOT))
from evals.run_eval import (
    REQUIRED_CASE_KEYS,
    REQUIRED_TOP_KEYS,
    ScenarioValidationError,
    _aggregate_results,
    _to_bench_score,
    list_scenarios,
    load_scenario,
    validate_scenario,
)


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

def _make_valid_scenario(**overrides: Any) -> dict[str, Any]:
    """최소 유효 시나리오 dict를 생성한다."""
    base: dict[str, Any] = {
        "id": "eval-test-001",
        "description": "테스트용 시나리오",
        "scenario_type": "comment_classification",
        "version": "1.0",
        "cases": [
            {
                "id": "cc-001",
                "input": {"comment": "코멘트 내용", "context": {}},
                "expected_label": "actionable",
                "judge_criteria": {
                    "rubric": "판정 기준",
                    "accept_conditions": ["조건"],
                    "reject_conditions": ["거부 조건"],
                },
            }
        ],
        "judge_model": "claude-3-5-sonnet-20241022",
        "judge_prompt_template": "프롬프트 템플릿 {comment}",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# 1. 모듈 import 가능 여부 (구조 검증)
# ---------------------------------------------------------------------------

@pytest.mark.offline
class TestModuleImport:
    """run_eval 모듈이 네트워크 없이 import 가능한지 확인한다."""

    def test_run_eval_importable(self):
        """evals.run_eval 모듈이 import 가능하다."""
        import evals.run_eval as m
        assert hasattr(m, "load_scenario")
        assert hasattr(m, "validate_scenario")
        assert hasattr(m, "list_scenarios")
        assert hasattr(m, "run_dry")
        assert hasattr(m, "run_live")
        assert hasattr(m, "main")

    def test_required_constants_exported(self):
        """필수 키 상수가 모듈 레벨에서 접근 가능하다."""
        assert isinstance(REQUIRED_TOP_KEYS, set)
        assert isinstance(REQUIRED_CASE_KEYS, set)
        assert "id" in REQUIRED_TOP_KEYS
        assert "cases" in REQUIRED_TOP_KEYS
        assert "judge_prompt_template" in REQUIRED_TOP_KEYS
        assert "id" in REQUIRED_CASE_KEYS
        assert "expected_label" in REQUIRED_CASE_KEYS
        assert "judge_criteria" in REQUIRED_CASE_KEYS


# ---------------------------------------------------------------------------
# 2. 시나리오 JSON 포맷 검증 (결정적 로직)
# ---------------------------------------------------------------------------

@pytest.mark.offline
class TestValidateScenario:
    """validate_scenario: 포맷 검증 단위 테스트."""

    def test_valid_scenario_passes(self):
        """최소 유효 시나리오는 예외 없이 통과한다."""
        data = _make_valid_scenario()
        validate_scenario(data)  # 예외 없어야 함

    def test_missing_top_level_key_raises(self):
        """최상위 필수 키 누락 시 ScenarioValidationError가 발생한다."""
        for key in REQUIRED_TOP_KEYS:
            data = _make_valid_scenario()
            del data[key]
            with pytest.raises(ScenarioValidationError) as exc_info:
                validate_scenario(data)
            assert key in str(exc_info.value)

    def test_empty_id_raises(self):
        """id가 빈 문자열이면 ScenarioValidationError가 발생한다."""
        data = _make_valid_scenario(id="")
        with pytest.raises(ScenarioValidationError, match="id"):
            validate_scenario(data)

    def test_non_string_id_raises(self):
        """id가 문자열이 아니면 ScenarioValidationError가 발생한다."""
        data = _make_valid_scenario(id=123)
        with pytest.raises(ScenarioValidationError, match="id"):
            validate_scenario(data)

    def test_empty_cases_raises(self):
        """cases가 빈 리스트이면 ScenarioValidationError가 발생한다."""
        data = _make_valid_scenario(cases=[])
        with pytest.raises(ScenarioValidationError, match="cases"):
            validate_scenario(data)

    def test_non_list_cases_raises(self):
        """cases가 dict이면 ScenarioValidationError가 발생한다."""
        data = _make_valid_scenario(cases={"wrong": "type"})
        with pytest.raises(ScenarioValidationError, match="cases"):
            validate_scenario(data)

    def test_case_missing_required_key_raises(self):
        """케이스 필수 키 누락 시 ScenarioValidationError가 발생한다."""
        for key in REQUIRED_CASE_KEYS:
            data = _make_valid_scenario()
            del data["cases"][0][key]
            with pytest.raises(ScenarioValidationError):
                validate_scenario(data)

    def test_case_empty_id_raises(self):
        """케이스 id가 빈 문자열이면 ScenarioValidationError가 발생한다."""
        data = _make_valid_scenario()
        data["cases"][0]["id"] = ""
        with pytest.raises(ScenarioValidationError, match="id"):
            validate_scenario(data)

    def test_case_empty_expected_label_raises(self):
        """케이스 expected_label이 빈 문자열이면 ScenarioValidationError가 발생한다."""
        data = _make_valid_scenario()
        data["cases"][0]["expected_label"] = ""
        with pytest.raises(ScenarioValidationError, match="expected_label"):
            validate_scenario(data)

    def test_case_judge_criteria_not_dict_raises(self):
        """케이스 judge_criteria가 dict가 아니면 ScenarioValidationError가 발생한다."""
        data = _make_valid_scenario()
        data["cases"][0]["judge_criteria"] = "not a dict"
        with pytest.raises(ScenarioValidationError, match="judge_criteria"):
            validate_scenario(data)

    def test_multiple_cases_valid(self):
        """복수 케이스가 모두 유효하면 통과한다."""
        extra_case = {
            "id": "cc-002",
            "input": {"comment": "다른 코멘트", "context": {}},
            "expected_label": "escalation",
            "judge_criteria": {"rubric": "기준", "accept_conditions": [], "reject_conditions": []},
        }
        data = _make_valid_scenario()
        data["cases"].append(extra_case)
        validate_scenario(data)  # 예외 없어야 함

    def test_second_case_invalid_raises(self):
        """두 번째 케이스가 유효하지 않으면 ScenarioValidationError가 발생한다."""
        bad_case = {
            "id": "",  # 빈 id
            "input": {},
            "expected_label": "actionable",
            "judge_criteria": {},
        }
        data = _make_valid_scenario()
        data["cases"].append(bad_case)
        with pytest.raises(ScenarioValidationError):
            validate_scenario(data)


# ---------------------------------------------------------------------------
# 3. load_scenario: 파일 I/O + 검증
# ---------------------------------------------------------------------------

@pytest.mark.offline
class TestLoadScenario:
    """load_scenario: 파일 로드 + 검증 통합 테스트."""

    def test_load_valid_file(self, tmp_path: Path):
        """유효한 시나리오 파일을 로드한다."""
        data = _make_valid_scenario()
        path = tmp_path / "valid.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        loaded = load_scenario(path)
        assert loaded["id"] == "eval-test-001"
        assert len(loaded["cases"]) == 1

    def test_load_invalid_json_raises(self, tmp_path: Path):
        """JSON 파싱 실패 시 json.JSONDecodeError가 발생한다."""
        path = tmp_path / "bad.json"
        path.write_text("not valid json{{{", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            load_scenario(path)

    def test_load_missing_file_raises(self, tmp_path: Path):
        """파일이 없으면 OSError/FileNotFoundError가 발생한다."""
        path = tmp_path / "nonexistent.json"
        with pytest.raises(OSError):
            load_scenario(path)

    def test_load_invalid_format_raises(self, tmp_path: Path):
        """필수 키가 누락된 파일은 ScenarioValidationError가 발생한다."""
        data = {"id": "test", "description": "no cases key"}
        path = tmp_path / "invalid.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ScenarioValidationError):
            load_scenario(path)


# ---------------------------------------------------------------------------
# 4. list_scenarios: 시나리오 파일 목록
# ---------------------------------------------------------------------------

@pytest.mark.offline
class TestListScenarios:
    """list_scenarios: 시나리오 파일 목록 반환 테스트."""

    def test_returns_json_files(self, tmp_path: Path):
        """JSON 파일만 반환한다."""
        (tmp_path / "a.json").write_text("{}", encoding="utf-8")
        (tmp_path / "b.json").write_text("{}", encoding="utf-8")
        (tmp_path / "c.txt").write_text("not json", encoding="utf-8")
        result = list_scenarios(tmp_path)
        names = [p.name for p in result]
        assert "a.json" in names
        assert "b.json" in names
        assert "c.txt" not in names

    def test_returns_sorted_list(self, tmp_path: Path):
        """정렬된 목록을 반환한다."""
        for name in ("z.json", "a.json", "m.json"):
            (tmp_path / name).write_text("{}", encoding="utf-8")
        result = list_scenarios(tmp_path)
        assert [p.name for p in result] == ["a.json", "m.json", "z.json"]

    def test_nonexistent_dir_returns_empty(self, tmp_path: Path):
        """존재하지 않는 디렉토리는 빈 목록을 반환한다."""
        result = list_scenarios(tmp_path / "nonexistent")
        assert result == []

    def test_empty_dir_returns_empty(self, tmp_path: Path):
        """빈 디렉토리는 빈 목록을 반환한다."""
        result = list_scenarios(tmp_path)
        assert result == []


# ---------------------------------------------------------------------------
# 5. 실제 시나리오 파일 로드 가능 여부 (evals/scenarios/*.json)
# ---------------------------------------------------------------------------

@pytest.mark.offline
class TestRealScenarioFiles:
    """evals/scenarios/ 아래 실제 JSON 파일들이 유효한지 확인한다."""

    def test_scenarios_dir_exists(self):
        """evals/scenarios/ 디렉토리가 존재한다."""
        assert _SCENARIOS_DIR.is_dir(), f"evals/scenarios/ 디렉토리가 없음: {_SCENARIOS_DIR}"

    def test_at_least_three_scenario_files(self):
        """시나리오 파일이 최소 3개 존재한다."""
        files = list_scenarios(_SCENARIOS_DIR)
        assert len(files) >= 3, f"시나리오 파일 수: {len(files)} (최소 3개 필요)"

    def test_comment_classification_scenario_valid(self):
        """comment_classification.json이 유효하다."""
        path = _SCENARIOS_DIR / "comment_classification.json"
        assert path.exists(), "comment_classification.json 없음"
        scenario = load_scenario(path)
        assert scenario["scenario_type"] == "comment_classification"
        assert len(scenario["cases"]) >= 1

    def test_clustering_quality_scenario_valid(self):
        """clustering_quality.json이 유효하다."""
        path = _SCENARIOS_DIR / "clustering_quality.json"
        assert path.exists(), "clustering_quality.json 없음"
        scenario = load_scenario(path)
        assert scenario["scenario_type"] == "clustering_quality"
        assert len(scenario["cases"]) >= 1

    def test_critic_consistency_scenario_valid(self):
        """critic_consistency.json이 유효하다."""
        path = _SCENARIOS_DIR / "critic_consistency.json"
        assert path.exists(), "critic_consistency.json 없음"
        scenario = load_scenario(path)
        assert scenario["scenario_type"] == "critic_consistency"
        assert len(scenario["cases"]) >= 1

    def test_all_scenario_files_loadable(self):
        """evals/scenarios/의 모든 JSON 파일이 예외 없이 로드된다."""
        files = list_scenarios(_SCENARIOS_DIR)
        errors: list[str] = []
        for path in files:
            try:
                load_scenario(path)
            except (ScenarioValidationError, json.JSONDecodeError, OSError) as exc:
                errors.append(f"{path.name}: {exc}")
        assert not errors, f"시나리오 로드 실패:\n" + "\n".join(errors)

    def test_each_scenario_has_expected_label_in_cases(self):
        """각 시나리오의 모든 케이스에 expected_label이 존재한다."""
        files = list_scenarios(_SCENARIOS_DIR)
        for path in files:
            scenario = load_scenario(path)
            for case in scenario["cases"]:
                assert case["expected_label"], (
                    f"{path.name}: 케이스 {case.get('id')} expected_label 누락"
                )

    def test_results_dir_exists(self):
        """evals/results/ 디렉토리가 존재한다."""
        results_dir = _EVALS_DIR / "results"
        assert results_dir.is_dir(), f"evals/results/ 디렉토리가 없음: {results_dir}"


# ---------------------------------------------------------------------------
# 6. _to_bench_score 집계 산술 (bench_runner 연계)
# ---------------------------------------------------------------------------

@pytest.mark.offline
class TestToBenchScore:
    """_to_bench_score: bench_runner 호환 점수 변환 테스트."""

    def test_perfect_score(self):
        """전체 통과 시 100.0%를 반환한다."""
        score = _to_bench_score(total=5, passed=5)
        assert score["score_pct"] == 100.0
        assert score["passed"] == 5
        assert score["failed"] == 0
        assert score["cold_start"] is False
        assert score["source"] == "live_eval"

    def test_zero_score(self):
        """전체 실패 시 0.0%를 반환한다."""
        score = _to_bench_score(total=5, passed=0)
        assert score["score_pct"] == 0.0
        assert score["passed"] == 0
        assert score["failed"] == 5
        assert score["cold_start"] is False

    def test_partial_score(self):
        """부분 통과 시 정확한 %를 반환한다."""
        score = _to_bench_score(total=10, passed=7)
        assert score["score_pct"] == 70.0
        assert score["failed"] == 3

    def test_cold_start_fewer_than_5(self):
        """케이스 4개 이하이면 cold_start=True를 반환한다."""
        score = _to_bench_score(total=4, passed=4)
        assert score["cold_start"] is True

    def test_cold_start_exactly_5(self):
        """케이스 정확히 5개이면 cold_start=False를 반환한다."""
        score = _to_bench_score(total=5, passed=5)
        assert score["cold_start"] is False

    def test_zero_total_returns_zero_score(self):
        """total=0이면 score_pct=0.0, cold_start=True를 반환한다."""
        score = _to_bench_score(total=0, passed=0)
        assert score["score_pct"] == 0.0
        assert score["cold_start"] is True

    def test_bench_runner_compute_delta_compatible(self):
        """_to_bench_score 반환값이 compute_delta()와 호환된다."""
        try:
            from hooks.lib.self_improve.bench_runner import compute_delta
            baseline = _to_bench_score(total=5, passed=3)
            candidate = _to_bench_score(total=5, passed=5)
            delta = compute_delta(baseline, candidate)
            assert delta["delta_pct"] == pytest.approx(40.0)
            assert delta["held_out_regression"] is False
            assert delta["cold_start"] is False
        except ImportError:
            pytest.skip("bench_runner not available")


# ---------------------------------------------------------------------------
# 7. _aggregate_results 집계 (결정적)
# ---------------------------------------------------------------------------

@pytest.mark.offline
class TestAggregateResults:
    """_aggregate_results: 케이스 결과 집계 단위 테스트."""

    def test_all_pass(self):
        """전체 통과 시 100% 점수를 반환한다."""
        cases = [
            {"case_id": "c1", "passed": True},
            {"case_id": "c2", "passed": True},
            {"case_id": "c3", "passed": True},
        ]
        result = _aggregate_results("test-scenario", cases)
        assert result["total"] == 3
        assert result["passed"] == 3
        assert result["failed"] == 0
        assert result["score_pct"] == 100.0
        assert result["scenario_id"] == "test-scenario"

    def test_all_fail(self):
        """전체 실패 시 0% 점수를 반환한다."""
        cases = [
            {"case_id": "c1", "passed": False},
            {"case_id": "c2", "passed": False},
        ]
        result = _aggregate_results("test-scenario", cases)
        assert result["passed"] == 0
        assert result["failed"] == 2
        assert result["score_pct"] == 0.0

    def test_mixed_pass_fail(self):
        """혼합 결과 시 정확한 집계를 반환한다."""
        cases = [
            {"case_id": "c1", "passed": True},
            {"case_id": "c2", "passed": False},
            {"case_id": "c3", "passed": True},
            {"case_id": "c4", "passed": False},
            {"case_id": "c5", "passed": True},
        ]
        result = _aggregate_results("test-scenario", cases)
        assert result["passed"] == 3
        assert result["failed"] == 2
        assert result["score_pct"] == 60.0

    def test_bench_score_included(self):
        """결과에 bench_score 키가 포함된다."""
        cases = [{"case_id": "c1", "passed": True}] * 5
        result = _aggregate_results("test-scenario", cases)
        assert "bench_score" in result
        assert result["bench_score"]["score_pct"] == 100.0

    def test_cases_preserved_in_result(self):
        """원본 케이스 목록이 결과에 보존된다."""
        cases = [{"case_id": "c1", "passed": True, "extra": "data"}]
        result = _aggregate_results("test-scenario", cases)
        assert result["cases"] == cases

    def test_empty_cases(self):
        """케이스가 없으면 0%를 반환한다."""
        result = _aggregate_results("test-scenario", [])
        assert result["total"] == 0
        assert result["score_pct"] == 0.0


# ---------------------------------------------------------------------------
# 8. evals/ 분리 확인 — pytest 컬렉션 메타 검증
# ---------------------------------------------------------------------------

@pytest.mark.offline
class TestEvalsNotInPytestCollection:
    """evals/ 디렉토리가 pytest tests/ collect에 포함되지 않음을 확인한다."""

    def test_evals_dir_separate_from_tests(self):
        """evals/와 tests/가 물리적으로 다른 디렉토리다."""
        tests_dir = _REPO_ROOT / "tests"
        assert _EVALS_DIR != tests_dir
        assert not _EVALS_DIR.is_relative_to(tests_dir)

    def test_pytest_ini_testpaths_is_tests(self):
        """pytest.ini의 testpaths가 tests만 포함한다."""
        pytest_ini = _REPO_ROOT / "pytest.ini"
        assert pytest_ini.exists(), "pytest.ini 없음"
        content = pytest_ini.read_text(encoding="utf-8")
        # testpaths = tests 라인이 있어야 함
        assert "testpaths" in content
        assert "tests" in content
        # evals가 testpaths에 포함되지 않아야 함
        lines = [l.strip() for l in content.splitlines()]
        for line in lines:
            if line.startswith("testpaths"):
                assert "evals" not in line, (
                    f"pytest.ini testpaths에 evals가 포함됨: {line}"
                )

    def test_run_eval_no_pytest_test_functions(self):
        """run_eval.py에 pytest가 수집할 test_ 함수가 없다."""
        run_eval_path = _EVALS_DIR / "run_eval.py"
        content = run_eval_path.read_text(encoding="utf-8")
        # test_로 시작하는 함수 정의가 없어야 함
        import re
        test_funcs = re.findall(r"^def test_\w+", content, re.MULTILINE)
        assert not test_funcs, (
            f"run_eval.py에 pytest 수집 대상 함수 발견: {test_funcs}"
        )
