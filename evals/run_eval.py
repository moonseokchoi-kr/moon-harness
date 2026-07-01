#!/usr/bin/env python3
"""evals/run_eval.py — 라이브 eval 진입점 (F21 live layer).

역할
----
- evals/scenarios/ 아래 JSON 시나리오를 로드한다.
- --live 플래그가 있을 때만 claude -p 헤드리스 호출 + LLM-judge 채점을 실행한다.
- --live 없으면 dry-run 출력 후 종료 (API 크레딧 소비 없음).
- 결과를 evals/results/{date}-result.json에 기록한다.

분리 원칙 (F21)
--------------
- 이 스크립트는 pytest tests/ 스위트에 절대 포함되지 않는다.
- claude -p 호출은 이 파일의 _run_judge_live() 함수에만 존재한다.
- 결정적 로직(시나리오 파싱, 집계)은 stdlib only — 네트워크 호출 없음.
- T-9 bench_runner 점수 산술 재사용: _to_bench_score() 참조.

사용법
------
  python evals/run_eval.py --help
  python evals/run_eval.py --live [--scenario <name>] [--output <path>]
  python evals/run_eval.py                # dry-run (claude 호출 없음)

주의
----
- --live 실행 시 claude CLI가 PATH에 있어야 한다.
- 실제 API 크레딧이 소비된다.
- CI 환경에서는 이 스크립트를 직접 실행하지 않는다.
  pytest tests/ 는 이 스크립트를 import/실행하지 않는다.
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# ── 경로 상수 ─────────────────────────────────────────────────────────────────
_EVALS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _EVALS_DIR.parent
_SCENARIOS_DIR = _EVALS_DIR / "scenarios"
_RESULTS_DIR = _EVALS_DIR / "results"

# bench_runner import (점수 산술 재사용, T-9 의존)
# CI 오프라인 구조 검증 시 import 실패를 graceful하게 처리한다.
try:
    sys.path.insert(0, str(_REPO_ROOT))
    from hooks.lib.self_improve.bench_runner import compute_delta, is_adoptable
    _BENCH_RUNNER_AVAILABLE = True
except ImportError:
    _BENCH_RUNNER_AVAILABLE = False

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 시나리오 파싱 (결정적 — stdlib only, 네트워크 없음)
# ---------------------------------------------------------------------------

class ScenarioValidationError(ValueError):
    """시나리오 JSON 포맷 오류."""


REQUIRED_TOP_KEYS = {"id", "description", "scenario_type", "cases", "judge_prompt_template"}
REQUIRED_CASE_KEYS = {"id", "input", "expected_label", "judge_criteria"}


def load_scenario(path: Path) -> dict[str, Any]:
    """시나리오 JSON 파일을 로드하고 유효성을 검증한다.

    Args:
        path: 시나리오 JSON 파일 경로.

    Returns:
        파싱된 시나리오 dict.

    Raises:
        ScenarioValidationError: 필수 키 누락 또는 포맷 오류.
        json.JSONDecodeError: JSON 파싱 실패.
        OSError: 파일 읽기 실패.
    """
    raw = path.read_text(encoding="utf-8")
    data: dict[str, Any] = json.loads(raw)
    validate_scenario(data)
    return data


def validate_scenario(data: dict[str, Any]) -> None:
    """시나리오 dict의 필수 키와 타입을 검증한다.

    Args:
        data: 시나리오 dict.

    Raises:
        ScenarioValidationError: 필수 키 누락 또는 타입 오류.
    """
    missing = REQUIRED_TOP_KEYS - set(data.keys())
    if missing:
        raise ScenarioValidationError(f"시나리오 필수 키 누락: {sorted(missing)}")

    if not isinstance(data["id"], str) or not data["id"]:
        raise ScenarioValidationError("시나리오 'id'는 비어 있지 않은 문자열이어야 합니다.")

    if not isinstance(data["cases"], list) or not data["cases"]:
        raise ScenarioValidationError("'cases'는 비어 있지 않은 리스트여야 합니다.")

    for i, case in enumerate(data["cases"]):
        missing_case = REQUIRED_CASE_KEYS - set(case.keys())
        if missing_case:
            raise ScenarioValidationError(
                f"cases[{i}] 필수 키 누락: {sorted(missing_case)}"
            )
        if not isinstance(case["id"], str) or not case["id"]:
            raise ScenarioValidationError(f"cases[{i}]['id']는 비어 있지 않은 문자열이어야 합니다.")
        if not isinstance(case["expected_label"], str) or not case["expected_label"]:
            raise ScenarioValidationError(
                f"cases[{i}]['expected_label']는 비어 있지 않은 문자열이어야 합니다."
            )
        if not isinstance(case["judge_criteria"], dict):
            raise ScenarioValidationError(f"cases[{i}]['judge_criteria']는 dict여야 합니다.")


def list_scenarios(scenarios_dir: Path | None = None) -> list[Path]:
    """scenarios/ 디렉토리의 JSON 시나리오 파일 목록을 반환한다.

    Args:
        scenarios_dir: 시나리오 디렉토리 (기본: evals/scenarios/).

    Returns:
        정렬된 시나리오 파일 경로 목록.
    """
    target = scenarios_dir or _SCENARIOS_DIR
    if not target.is_dir():
        return []
    return sorted(target.glob("*.json"))


# ---------------------------------------------------------------------------
# bench_runner 점수 산술 연계 (T-9 재사용)
# ---------------------------------------------------------------------------

def _to_bench_score(
    total: int,
    passed: int,
) -> dict[str, Any]:
    """라이브 eval 결과를 bench_runner 호환 점수 dict로 변환한다.

    bench_runner.score_baseline() / score_candidate() 출력 형식과 동일하여
    compute_delta() / is_adoptable()을 직접 연계 가능하다.

    Args:
        total: 전체 케이스 수.
        passed: 통과 케이스 수.

    Returns:
        bench_runner 호환 점수 dict.
    """
    # bench_runner._COLD_START_THRESHOLD = 5
    cold_start_threshold = 5
    cold_start = total < cold_start_threshold
    failed = total - passed
    score_pct = (passed / total * 100.0) if total > 0 else 0.0
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "score_pct": score_pct,
        "cold_start": cold_start,
        "source": "live_eval",
    }


# ---------------------------------------------------------------------------
# LLM-judge 호출 (라이브 전용 — --live 플래그 없으면 절대 실행 안 됨)
# ---------------------------------------------------------------------------

def _check_claude_cli() -> bool:
    """claude CLI 가용 여부를 확인한다.

    Returns:
        True if claude CLI가 PATH에 있음, False otherwise.
    """
    try:
        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _run_judge_live(
    scenario: dict[str, Any],
    case: dict[str, Any],
    model: str | None = None,
) -> dict[str, Any]:
    """단일 케이스를 claude -p 헤드리스로 LLM-judge 채점한다.

    경고: 이 함수는 --live 플래그가 있을 때만 호출된다.
    실제 API 크레딧을 소비한다.

    모델 선택 우선순위: 인자 model > scenario["judge_model"] > CLI 기본값(무지정).

    Args:
        scenario: 시나리오 dict (judge_prompt_template 포함).
        case: 개별 케이스 dict.
        model: claude --model 로 전달할 모델 id (None이면 judge_model 필드로 폴백).

    Returns:
        {
            "case_id": str,
            "expected_label": str,
            "judge_label": str | None,  # claude 응답 파싱 결과
            "judge_reason": str | None,
            "passed": bool,
            "raw_response": str,
            "error": str | None,
        }
    """
    prompt_template = scenario.get("judge_prompt_template", "")
    # 템플릿에 케이스 데이터 삽입
    prompt = prompt_template.format(
        comment=json.dumps(case["input"].get("comment", ""), ensure_ascii=False),
        context=json.dumps(case["input"].get("context", {}), ensure_ascii=False),
        comments=json.dumps(case["input"].get("comments", []), ensure_ascii=False),
        expected_clusters=json.dumps(
            case["input"].get("expected_clusters", {}), ensure_ascii=False
        ),
        original_claim=json.dumps(
            case["input"].get("original_claim", ""), ensure_ascii=False
        ),
        rebuttal=json.dumps(case["input"].get("rebuttal", ""), ensure_ascii=False),
        evidence=json.dumps(case["input"].get("evidence", {}), ensure_ascii=False),
    )

    resolved_model = model or scenario.get("judge_model") or None
    cmd = ["claude"]
    if resolved_model:
        cmd += ["--model", resolved_model]
    cmd += ["-p", prompt]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )
        raw_response = proc.stdout.strip()

        # JSON 응답 파싱 시도
        judge_label: str | None = None
        judge_reason: str | None = None
        try:
            # claude 응답에서 JSON 블록 추출 시도
            response_data = _extract_json(raw_response)
            judge_label = str(response_data.get("label", "")).strip() or None
            judge_reason = str(response_data.get("reason", "")).strip() or None
        except (json.JSONDecodeError, ValueError, AttributeError):
            # JSON 파싱 실패 시 텍스트에서 레이블 탐색
            judge_label = _extract_label_from_text(
                raw_response, case["expected_label"]
            )

        passed = judge_label == case["expected_label"] if judge_label else False

        return {
            "case_id": case["id"],
            "expected_label": case["expected_label"],
            "judge_label": judge_label,
            "judge_reason": judge_reason,
            "passed": passed,
            "raw_response": raw_response,
            "error": None,
        }

    except subprocess.TimeoutExpired:
        return {
            "case_id": case["id"],
            "expected_label": case["expected_label"],
            "judge_label": None,
            "judge_reason": None,
            "passed": False,
            "raw_response": "",
            "error": "claude -p 타임아웃 (60s)",
        }
    except FileNotFoundError:
        return {
            "case_id": case["id"],
            "expected_label": case["expected_label"],
            "judge_label": None,
            "judge_reason": None,
            "passed": False,
            "raw_response": "",
            "error": "claude CLI를 찾을 수 없음. PATH 확인 필요.",
        }


def _extract_json(text: str) -> dict[str, Any]:
    """텍스트에서 JSON 객체를 추출한다 (코드 블록 포함).

    Args:
        text: claude 응답 텍스트.

    Returns:
        파싱된 dict.

    Raises:
        json.JSONDecodeError: JSON 파싱 실패.
        ValueError: JSON 객체를 찾을 수 없음.
    """
    # ```json ... ``` 블록 추출 시도
    import re
    json_block = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if json_block:
        return json.loads(json_block.group(1))

    # 중괄호 범위 추출 시도
    start = text.find("{")
    end = text.rfind("}") + 1
    if start != -1 and end > start:
        return json.loads(text[start:end])

    raise ValueError("JSON 객체를 찾을 수 없음")


def _extract_label_from_text(text: str, expected_label: str) -> str | None:
    """텍스트에서 레이블을 단순 검색한다 (fallback).

    Args:
        text: 응답 텍스트.
        expected_label: 기대 레이블 (후보 레이블 목록 확장에 사용).

    Returns:
        발견된 레이블 또는 None.
    """
    known_labels = {
        "actionable", "escalation",
        "GOOD_CLUSTERING", "BAD_CLUSTERING",
        "UPHELD", "REFUTED", "NARROW",
    }
    for label in known_labels:
        if label.lower() in text.lower():
            return label
    return None


# ---------------------------------------------------------------------------
# 집계 (결정적 — stdlib only)
# ---------------------------------------------------------------------------

def _aggregate_results(
    scenario_id: str,
    case_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """케이스 결과를 집계하여 시나리오 수준 요약을 생성한다.

    Args:
        scenario_id: 시나리오 ID.
        case_results: 케이스별 judge 결과 목록.

    Returns:
        집계된 시나리오 결과 dict.
    """
    total = len(case_results)
    passed = sum(1 for r in case_results if r.get("passed", False))
    failed = total - passed
    score_pct = (passed / total * 100.0) if total > 0 else 0.0

    bench_score = _to_bench_score(total, passed)

    return {
        "scenario_id": scenario_id,
        "total": total,
        "passed": passed,
        "failed": failed,
        "score_pct": score_pct,
        "bench_score": bench_score,
        "cases": case_results,
    }


# ---------------------------------------------------------------------------
# 실행 모드
# ---------------------------------------------------------------------------

def run_dry(scenarios_dir: Path | None = None) -> None:
    """dry-run 모드: 시나리오 목록과 케이스 요약을 출력하고 종료한다.

    API 크레딧을 소비하지 않는다.

    Args:
        scenarios_dir: 시나리오 디렉토리 (기본: evals/scenarios/).
    """
    scenario_files = list_scenarios(scenarios_dir)
    print("=== dry-run 모드 (claude 호출 없음) ===")
    print(f"시나리오 디렉토리: {scenarios_dir or _SCENARIOS_DIR}")
    print(f"발견된 시나리오 파일: {len(scenario_files)}개")
    print()

    total_cases = 0
    for path in scenario_files:
        try:
            scenario = load_scenario(path)
            n_cases = len(scenario.get("cases", []))
            total_cases += n_cases
            print(f"  [{scenario['scenario_type']}] {scenario['id']}")
            print(f"    파일: {path.name}")
            print(f"    케이스 수: {n_cases}개")
            for case in scenario.get("cases", []):
                print(f"      - {case['id']}: expected_label={case['expected_label']}")
            print()
        except (ScenarioValidationError, json.JSONDecodeError, OSError) as exc:
            print(f"  ERROR: {path.name} 로드 실패 — {exc}")

    print(f"총 케이스: {total_cases}개")
    print()
    print("실제 실행: python evals/run_eval.py --live")
    print("주의: --live 실행 시 실제 API 크레딧이 소비됩니다.")


def run_live(
    scenario_filter: str | None = None,
    output_path: Path | None = None,
    scenarios_dir: Path | None = None,
    model: str | None = None,
) -> Path:
    """라이브 모드: claude -p 헤드리스로 시나리오를 실행하고 결과를 저장한다.

    경고: 실제 API 크레딧이 소비됩니다.

    Args:
        scenario_filter: 특정 시나리오 ID 또는 파일명 (None이면 전체 실행).
        output_path: 결과 JSON 저장 경로 (None이면 자동 생성).
        scenarios_dir: 시나리오 디렉토리 (기본: evals/scenarios/).

    Returns:
        결과 파일 경로.
    """
    # claude CLI 가용 여부 확인
    if not _check_claude_cli():
        print(
            "WARNING: claude CLI를 찾을 수 없습니다. "
            "--live 실행을 스킵합니다.\n"
            "claude CLI 설치: https://claude.ai/download",
            file=sys.stderr,
        )
        print("SKIP: claude CLI 부재로 라이브 eval 스킵됨.")
        # graceful degrade: 빈 결과 기록
        result = {
            "run_at": datetime.now().isoformat(),
            "mode": "live",
            "status": "SKIPPED",
            "reason": "claude CLI not found",
            "scenarios": [],
        }
        return _save_result(result, output_path)

    scenario_files = list_scenarios(scenarios_dir)
    if scenario_filter:
        scenario_files = [
            p for p in scenario_files
            if scenario_filter in p.name or scenario_filter in p.stem
        ]

    all_scenario_results: list[dict[str, Any]] = []
    total_passed = 0
    total_cases = 0

    for path in scenario_files:
        print(f"시나리오 실행 중: {path.name}")
        try:
            scenario = load_scenario(path)
        except (ScenarioValidationError, json.JSONDecodeError, OSError) as exc:
            print(f"  ERROR: 로드 실패 — {exc}", file=sys.stderr)
            continue

        case_results: list[dict[str, Any]] = []
        for case in scenario.get("cases", []):
            print(f"  케이스: {case['id']} ...", end=" ", flush=True)
            result = _run_judge_live(scenario, case, model=model)
            case_results.append(result)
            status = "PASS" if result["passed"] else "FAIL"
            print(f"{status} (judge={result['judge_label']})")

        agg = _aggregate_results(scenario["id"], case_results)
        all_scenario_results.append(agg)
        total_passed += agg["passed"]
        total_cases += agg["total"]

        print(f"  -> {agg['passed']}/{agg['total']} 통과 ({agg['score_pct']:.1f}%)")
        print()

    # bench_runner 연계 집계
    overall_bench = _to_bench_score(total_cases, total_passed)
    bench_delta: dict[str, Any] | None = None
    if _BENCH_RUNNER_AVAILABLE and total_cases > 0:
        # 라이브 결과를 baseline으로 삼아 self-delta 계산 (앵커 점수 기록용)
        bench_delta = {
            "note": "라이브 eval 결과 앵커 — compute_delta()로 baseline 대비 비교 가능",
            "score": overall_bench,
        }

    final_result = {
        "run_at": datetime.now().isoformat(),
        "mode": "live",
        "status": "COMPLETED",
        "total_cases": total_cases,
        "total_passed": total_passed,
        "overall_score_pct": (
            total_passed / total_cases * 100.0 if total_cases > 0 else 0.0
        ),
        "bench_score": overall_bench,
        "bench_delta_anchor": bench_delta,
        "scenarios": all_scenario_results,
    }

    result_path = _save_result(final_result, output_path)
    print(f"결과 저장: {result_path}")
    print(
        f"최종 점수: {total_passed}/{total_cases} "
        f"({final_result['overall_score_pct']:.1f}%)"
    )
    return result_path


def _save_result(
    result: dict[str, Any],
    output_path: Path | None,
) -> Path:
    """결과 dict를 JSON 파일로 저장한다.

    Args:
        result: 저장할 결과 dict.
        output_path: 저장 경로 (None이면 evals/results/{date}-result.json).

    Returns:
        저장된 파일 경로.
    """
    if output_path is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
        _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        output_path = _RESULTS_DIR / f"{date_str}-result.json"

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return output_path


# ---------------------------------------------------------------------------
# CLI 진입점
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    """CLI 인자 파서를 생성한다."""
    parser = argparse.ArgumentParser(
        prog="run_eval",
        description=(
            "evals/ 라이브 eval 하네스 (F21 live layer).\n\n"
            "[주의] --live 플래그를 사용하면 실제 API 크레딧이 소비됩니다.\n"
            "       별도 API 크레딧 비용 발생.\n"
            "       claude CLI가 PATH에 없으면 graceful하게 스킵됩니다.\n\n"
            "이 스크립트는 pytest tests/ 스위트와 완전히 분리됩니다 (F21).\n"
            "오프라인 구조 검증만 필요하면:\n"
            "  pytest tests/test_eval_harness_structure.py"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--live",
        action="store_true",
        default=False,
        help=(
            "라이브 모드 활성화 — claude -p 헤드리스 실행. "
            "이 플래그 없으면 dry-run만 실행됩니다."
        ),
    )
    parser.add_argument(
        "--scenario",
        metavar="NAME",
        default=None,
        help="실행할 시나리오 이름 또는 파일명 필터 (기본: 전체 실행)",
    )
    parser.add_argument(
        "--output",
        metavar="PATH",
        default=None,
        help=(
            "결과 JSON 저장 경로 "
            "(기본: evals/results/YYYY-MM-DD-result.json)"
        ),
    )
    parser.add_argument(
        "--scenarios-dir",
        metavar="DIR",
        default=None,
        help=f"시나리오 디렉토리 경로 (기본: {_SCENARIOS_DIR})",
    )
    parser.add_argument(
        "--model",
        metavar="ID",
        default=None,
        help=(
            "judge 호출에 사용할 claude --model id "
            "(미지정 시 시나리오의 judge_model 필드 → CLI 기본값 순으로 폴백)"
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI 메인 진입점.

    Args:
        argv: 인자 목록 (None이면 sys.argv 사용).

    Returns:
        종료 코드 (0: 성공, 1: 오류).
    """
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    parser = _build_parser()
    args = parser.parse_args(argv)

    scenarios_dir = Path(args.scenarios_dir) if args.scenarios_dir else None
    output_path = Path(args.output) if args.output else None

    if not args.live:
        run_dry(scenarios_dir=scenarios_dir)
        return 0

    # --live: 실제 실행 (API 크레딧 소비)
    print("=== 라이브 eval 실행 ===")
    print("⚠️  실제 API 크레딧이 소비됩니다.")
    print()
    run_live(
        scenario_filter=args.scenario,
        output_path=output_path,
        scenarios_dir=scenarios_dir,
        model=args.model,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
