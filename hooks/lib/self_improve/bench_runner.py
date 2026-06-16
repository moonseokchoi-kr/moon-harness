"""hooks/lib/self_improve/bench_runner.py — 벤치마크 점수 산술 (결정적).

역할
----
- baseline(OFF) vs candidate(ON) 점수를 비교하여 delta를 산출한다.
- 점수 상승 AND held-out 회귀 없음 → 채택 가능 신호.
- 점수 하락 OR held-out 회귀 → 채택 불가.
- 데이터 N건 미만(콜드스타트) → "측정 불가" 반환, 추정 채택 금지.

제약 (F20, F24)
--------------
- Python 3.9+ stdlib only. 네트워크/LLM 호출 절대 금지.
- 파일 읽기 전용 — write 경로 없음 (frozen 원칙).
- claude -p 호출은 benchmarks/run_live.sh (셸 레이어) 에만.
- fail-safe: 예외 발생 시 cold_start=True 로 안전하게 처리.

공개 API
--------
score_baseline(set_path) -> dict
score_candidate(set_path, candidate_fn) -> dict
compute_delta(baseline, candidate) -> dict
    반환: {"delta_pct": float | None, "held_out_regression": bool, "cold_start": bool}
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

# 콜드스타트 임계: 데이터 N건 미만 시 "측정 불가" (F24 Acceptance)
_COLD_START_THRESHOLD: int = 5

# 채택 가능 결과 키
_DELTA_PCT = "delta_pct"
_HELD_OUT_REGRESSION = "held_out_regression"
_COLD_START = "cold_start"


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------

def _load_cases(set_path: Path) -> list[dict[str, Any]]:
    """디렉토리에서 JSON 케이스 파일을 로드한다 (읽기 전용).

    Args:
        set_path: 벤치마크 셋 디렉토리 경로.

    Returns:
        케이스 dict 목록. 파일이 없거나 읽기 실패 시 빈 목록.
    """
    cases: list[dict[str, Any]] = []
    if not set_path.is_dir():
        logger.warning("벤치마크 셋 경로가 존재하지 않음: %s", set_path)
        return cases

    for json_file in sorted(set_path.glob("*.json")):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            cases.append(data)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("케이스 파일 로드 실패 (%s): %s", json_file.name, exc)

    return cases


def _evaluate_case(
    case: dict[str, Any],
    candidate_fn: Optional[Callable[[dict[str, Any]], str]],
) -> bool:
    """단일 케이스를 평가하여 pass/fail 여부를 반환한다.

    baseline 모드(candidate_fn=None): case["label"] == "pass" 이면 통과.
    candidate 모드: candidate_fn(case["input"]) 반환값이
        case["expected_outcome"] 와 일치하면 통과.

    Args:
        case: 케이스 dict.
        candidate_fn: 후보 함수 (baseline 모드에서는 None).

    Returns:
        True if pass, False if fail.
    """
    if candidate_fn is None:
        # baseline 모드: 레이블된 정답 사용
        return str(case.get("label", "fail")).lower() == "pass"

    # candidate 모드: candidate_fn이 expected_outcome을 맞히면 pass
    try:
        actual = candidate_fn(case.get("input", {}))
        expected = str(case.get("expected_outcome", ""))
        return str(actual).strip() == expected.strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("candidate_fn 실행 실패 (id=%s): %s", case.get("id"), exc)
        return False


def _score_set(
    cases: list[dict[str, Any]],
    candidate_fn: Optional[Callable[[dict[str, Any]], str]],
) -> dict[str, Any]:
    """케이스 목록을 평가하여 점수 dict를 반환한다.

    Args:
        cases: 케이스 dict 목록.
        candidate_fn: 후보 함수 (None이면 baseline 모드).

    Returns:
        {
            "total": int,
            "passed": int,
            "failed": int,
            "score_pct": float,  # passed / total * 100 (total == 0 이면 0.0)
            "cold_start": bool,  # total < _COLD_START_THRESHOLD
        }
    """
    total = len(cases)
    cold_start = total < _COLD_START_THRESHOLD

    if total == 0:
        return {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "score_pct": 0.0,
            "cold_start": True,
        }

    passed = sum(1 for c in cases if _evaluate_case(c, candidate_fn))
    failed = total - passed
    score_pct = (passed / total) * 100.0

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "score_pct": score_pct,
        "cold_start": cold_start,
    }


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------

def score_baseline(set_path: Path) -> dict[str, Any]:
    """baseline(OFF) 상태 점수를 산출한다.

    frozen 골든 케이스의 레이블을 그대로 정답으로 사용한다.
    파일을 읽기만 하며 절대 쓰지 않는다.

    Args:
        set_path: 벤치마크 셋 디렉토리 경로 (train/ 또는 held-out/).

    Returns:
        점수 dict. cold_start=True 이면 score_pct 는 0.0 (측정 불가).
    """
    try:
        cases = _load_cases(Path(set_path))
        return _score_set(cases, candidate_fn=None)
    except Exception as exc:  # noqa: BLE001
        logger.error("score_baseline 실패 (fail-safe 반환): %s", exc)
        return {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "score_pct": 0.0,
            "cold_start": True,
        }


def score_candidate(
    set_path: Path,
    candidate_fn: Callable[[dict[str, Any]], str],
) -> dict[str, Any]:
    """candidate(ON) 상태 점수를 산출한다.

    candidate_fn은 각 케이스의 input을 받아 expected_outcome 형식의 문자열을
    반환하는 순수 함수여야 한다. 네트워크/LLM 호출 금지.

    frozen 파일을 읽기만 한다 — write 경로 없음.

    Args:
        set_path: 벤치마크 셋 디렉토리 경로 (train/ 또는 held-out/).
        candidate_fn: 후보 평가 함수 (input dict → outcome str).

    Returns:
        점수 dict. cold_start=True 이면 score_pct 는 0.0 (측정 불가).
    """
    try:
        cases = _load_cases(Path(set_path))
        return _score_set(cases, candidate_fn=candidate_fn)
    except Exception as exc:  # noqa: BLE001
        logger.error("score_candidate 실패 (fail-safe 반환): %s", exc)
        return {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "score_pct": 0.0,
            "cold_start": True,
        }


def compute_delta(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    """baseline vs candidate 점수 델타를 계산하고 채택 가능 여부를 판정한다.

    채택 가능 조건 (F22):
    - delta_pct > 0 (점수 상승)
    - held_out_regression == False (held-out 회귀 없음)
    - cold_start == False (충분한 데이터)

    콜드스타트 (F24):
    - baseline 또는 candidate 중 하나라도 cold_start=True 이면
      delta_pct=None, held_out_regression=False, cold_start=True 반환.
    - 이 경우 채택 결정을 내릴 수 없으며 추정 기반 채택 금지.

    점수 하락 또는 held-out 회귀:
    - delta_pct <= 0 이면 채택 불가 (F22).
    - held-out 전용 dict를 인자로 전달하면 held_out_regression 필드로
      회귀 여부를 직접 판정한다.

    Args:
        baseline: score_baseline() 또는 score_candidate() 반환 dict.
        candidate: score_candidate() 반환 dict.

    Returns:
        {
            "delta_pct": float | None,
            "held_out_regression": bool,
            "cold_start": bool,
        }

    "delta_pct" 해석:
        - None: 콜드스타트(측정 불가)
        - > 0: 점수 상승 (채택 가능 신호)
        - == 0: 점수 동일 (채택 불가)
        - < 0: 점수 하락 (채택 불가)
    """
    try:
        baseline_cold = bool(baseline.get("cold_start", True))
        candidate_cold = bool(candidate.get("cold_start", True))

        # 콜드스타트: 어느 쪽이든 데이터 부족 → 측정 불가
        if baseline_cold or candidate_cold:
            logger.info("콜드스타트: 데이터 부족, 측정 불가 반환.")
            return {
                _DELTA_PCT: None,
                _HELD_OUT_REGRESSION: False,
                _COLD_START: True,
            }

        baseline_score: float = float(baseline.get("score_pct", 0.0))
        candidate_score: float = float(candidate.get("score_pct", 0.0))

        delta_pct = candidate_score - baseline_score

        # held_out_regression: candidate가 baseline보다 점수가 낮으면 회귀
        # (held-out 셋으로 compute_delta를 호출할 때 적용)
        held_out_regression = delta_pct < 0.0

        return {
            _DELTA_PCT: delta_pct,
            _HELD_OUT_REGRESSION: held_out_regression,
            _COLD_START: False,
        }

    except (TypeError, ValueError, KeyError) as exc:
        logger.error("compute_delta 실패 (fail-safe: cold_start 반환): %s", exc)
        return {
            _DELTA_PCT: None,
            _HELD_OUT_REGRESSION: False,
            _COLD_START: True,
        }


def is_adoptable(delta: dict[str, Any]) -> bool:
    """compute_delta 결과로 채택 가능 여부를 판정한다 (F22 게이트).

    채택 가능 조건:
    1. cold_start == False (충분한 데이터)
    2. delta_pct > 0 (점수 상승)
    3. held_out_regression == False (held-out 회귀 없음)

    Args:
        delta: compute_delta() 반환 dict.

    Returns:
        True if adoptable, False otherwise.
    """
    if delta.get(_COLD_START, True):
        return False
    delta_pct = delta.get(_DELTA_PCT)
    if delta_pct is None or delta_pct <= 0.0:
        return False
    if delta.get(_HELD_OUT_REGRESSION, True):
        return False
    return True
