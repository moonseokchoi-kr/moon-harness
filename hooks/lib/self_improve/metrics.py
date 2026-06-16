"""hooks/lib/self_improve/metrics.py — 핵심 지표 텔레메트리 (spec F23).

자동 측정 가능한 지표만 결정적으로 산출한다. 사후 사람 검토 지표
(오에스컬레이션률, critic precision/recall)는 이 모듈에서 구현하지 않는다
(F23 주석: Phase 2.5/3, 가정 3).

공개 API:
    retro_log_parser(text)       → list[dict]     retro-log.md 헤더 파싱
    convergence_rate(history)    → float           CONVERGED/전체 비율
    avg_iterations_to_green(history) → float       green까지 평균 iteration
    recurrence_rate(retro_log_text)  → float       동일 교훈 재발률
    skill_reuse_rate(history)    → dict            스킬별 호출/성공 집계
    write_metrics(metrics, path) → dict            atomic_write 래퍼

하드 불변식:
    - Python 3.9+ stdlib only.
    - 네트워크/LLM 호출 절대 금지.
    - 모든 함수는 fail-safe — 예외를 밖으로 raise하지 않는다.
    - cold_start: 입력 데이터가 5건 미만이면 cold_start=True 플래그.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from hooks.lib.self_improve.state_io import atomic_write

# ── 상수 ──────────────────────────────────────────────────────────────────────

# 재발률 cold_start 임계값 (F24: 5건 미만이면 "측정 불가")
_COLD_START_THRESHOLD = 5

# retro-log.md 헤더 패턴:
#   ## YYYY-MM-DD retro — 신규 N건 처리 / 적용 A · 제안 P · 폐기 D
_RETRO_HEADER_RE = re.compile(
    r"^##\s+(?P<date>\d{4}-\d{2}-\d{2})\s+retro\s+[—\-]+\s+"
    r"신규\s+(?P<new>\d+)건(?:\s+처리)?\s*/\s*"
    r"적용\s+(?P<applied>\d+)\s+[··]\s+제안\s+(?P<proposed>\d+)\s+[··]\s+폐기\s+(?P<dropped>\d+)",
    re.UNICODE,
)

# 교훈 마커 라인 패턴 (rollback diff 블록 근거 줄):
#   - 근거: {LEARNING 엔트리 마커들}
_EVIDENCE_RE = re.compile(r"^\s*-\s*근거\s*:\s*(.+)$", re.MULTILINE)

# 마커 날짜 패턴 (## YYYY-MM-DD — ... 형식으로 근거에 등장)
_MARKER_TOKEN_RE = re.compile(
    r"##\s*\d{4}-\d{2}-\d{2}\s+[—\-]+\s+\S+|"
    r"\d{4}-\d{2}-\d{2}\s+[—\-]+\s+\S+"
)


# ── retro-log 파서 ─────────────────────────────────────────────────────────────

def retro_log_parser(text: str) -> List[Dict[str, Any]]:
    """retro-log.md 텍스트에서 회고 헤더를 파싱한다.

    spec "상태 파일 계약" 포맷:
        ## YYYY-MM-DD retro — 신규 N건 처리 / 적용 A · 제안 P · 폐기 D

    반환:
        list of dict: [{"date": str, "new": int, "applied": int,
                        "proposed": int, "dropped": int}, ...]

    실패하면 빈 리스트 반환 (fail-safe, raise 금지).
    """
    if not isinstance(text, str):
        return []

    result: List[Dict[str, Any]] = []
    for line in text.splitlines():
        m = _RETRO_HEADER_RE.match(line.strip())
        if m:
            try:
                result.append(
                    {
                        "date": m.group("date"),
                        "new": int(m.group("new")),
                        "applied": int(m.group("applied")),
                        "proposed": int(m.group("proposed")),
                        "dropped": int(m.group("dropped")),
                    }
                )
            except (ValueError, AttributeError):
                # 정수 변환 실패는 silent skip (fail-safe)
                continue

    return result


# ── 수렴 지표 ─────────────────────────────────────────────────────────────────

def convergence_rate(state_history: List[Dict[str, Any]]) -> float:
    """CONVERGED/전체 실행 비율을 반환한다.

    Args:
        state_history: pr-converge-state JSON dict의 이력 list.
                       각 dict에 "status" 필드가 있어야 한다.

    Returns:
        0.0 ~ 1.0 범위의 float. 데이터 없으면 0.0 (cold_start 케이스).
        fail-safe: 예외 미발생.
    """
    if not isinstance(state_history, list) or not state_history:
        return 0.0

    total = 0
    converged = 0
    for item in state_history:
        if not isinstance(item, dict):
            continue
        status = item.get("status")
        if not isinstance(status, str):
            continue
        total += 1
        if status == "CONVERGED":
            converged += 1

    if total == 0:
        return 0.0
    return converged / total


def avg_iterations_to_green(state_history: List[Dict[str, Any]]) -> float:
    """CONVERGED 상태 엔트리들의 평균 iteration 횟수를 반환한다.

    Args:
        state_history: pr-converge-state JSON dict의 이력 list.
                       각 dict에 "iterations" 필드가 있어야 한다.

    Returns:
        float. CONVERGED 엔트리가 없으면 0.0 (cold_start 케이스).
        fail-safe.
    """
    if not isinstance(state_history, list) or not state_history:
        return 0.0

    total_iters = 0
    count = 0
    for item in state_history:
        if not isinstance(item, dict):
            continue
        if item.get("status") != "CONVERGED":
            continue
        iters = item.get("iterations")
        try:
            total_iters += int(iters)  # type: ignore[arg-type]
            count += 1
        except (TypeError, ValueError):
            continue

    if count == 0:
        return 0.0
    return total_iters / count


# ── 재발률 ────────────────────────────────────────────────────────────────────

def _extract_evidence_markers(retro_section: str) -> List[str]:
    """retro-log 블록 본문에서 근거 마커 토큰을 추출한다.

    "- 근거: ## YYYY-MM-DD — feature / T-N" 형식의 줄에서 마커를 파싱.
    """
    tokens: List[str] = []
    for m in _EVIDENCE_RE.finditer(retro_section):
        evidence_line = m.group(1)
        found = _MARKER_TOKEN_RE.findall(evidence_line)
        tokens.extend(t.strip() for t in found)
    return tokens


def recurrence_rate(retro_log_text: str) -> float:
    """동일 교훈 재발률을 계산한다 (F23 핵심 앵커).

    재발률 정의:
        재발률 = 재발 교훈 건수 / 전체 적용 건수

    "재발"은 동일 retro-log에서 두 번 이상 '근거' 마커로 등장한
    LEARNING.md 엔트리를 의미한다.

    Args:
        retro_log_text: retro-log.md 전체 텍스트.

    Returns:
        0.0 ~ 1.0 범위의 float.
        - 전체 적용 건수 < _COLD_START_THRESHOLD이면 0.0 반환
          (cold_start; compute_metrics에서 cold_start=True 처리).
        fail-safe.
    """
    if not isinstance(retro_log_text, str):
        return 0.0

    # 전체 적용 건수는 헤더의 applied 합계로 산출
    entries = retro_log_parser(retro_log_text)
    total_applied = sum(e.get("applied", 0) for e in entries)

    if total_applied < _COLD_START_THRESHOLD:
        return 0.0

    # 근거 마커 전체 추출 — 같은 마커가 여러 회고에 등장하면 재발
    marker_counts: Dict[str, int] = {}
    for m in _EVIDENCE_RE.finditer(retro_log_text):
        evidence_line = m.group(1)
        for token in _MARKER_TOKEN_RE.findall(evidence_line):
            key = token.strip()
            if key:
                marker_counts[key] = marker_counts.get(key, 0) + 1

    recurrence_count = sum(1 for cnt in marker_counts.values() if cnt >= 2)

    return recurrence_count / total_applied


# ── 스킬 재사용률 ─────────────────────────────────────────────────────────────

def skill_reuse_rate(state_history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """스킬별 호출/성공 집계 (기초 구조).

    state_history의 각 엔트리에서 "skill_calls" 필드를 읽는다.
    형식: {"skill_name": {"calls": int, "successes": int}, ...}

    반환:
        {
            "cold_start": bool,
            "skills": {
                "<skill_name>": {
                    "calls": int,
                    "successes": int,
                    "success_rate": float | None,
                }
            }
        }
    """
    if not isinstance(state_history, list):
        return {"cold_start": True, "skills": {}}

    skills: Dict[str, Dict[str, int]] = {}

    for item in state_history:
        if not isinstance(item, dict):
            continue
        skill_calls = item.get("skill_calls")
        if not isinstance(skill_calls, dict):
            continue
        for skill_name, counts in skill_calls.items():
            if not isinstance(counts, dict):
                continue
            if skill_name not in skills:
                skills[skill_name] = {"calls": 0, "successes": 0}
            try:
                skills[skill_name]["calls"] += int(counts.get("calls", 0))
                skills[skill_name]["successes"] += int(counts.get("successes", 0))
            except (TypeError, ValueError):
                continue

    total_calls = sum(v["calls"] for v in skills.values())
    cold_start = total_calls < _COLD_START_THRESHOLD

    result_skills: Dict[str, Any] = {}
    for name, agg in skills.items():
        calls = agg["calls"]
        succs = agg["successes"]
        result_skills[name] = {
            "calls": calls,
            "successes": succs,
            "success_rate": (succs / calls) if calls > 0 else None,
        }

    return {"cold_start": cold_start, "skills": result_skills}


# ── 지표 기록 ─────────────────────────────────────────────────────────────────

def compute_metrics(
    state_history: List[Dict[str, Any]],
    retro_log_text: str,
) -> Dict[str, Any]:
    """모든 자동 측정 지표를 계산하여 단일 dict로 반환한다.

    .harness/metrics.json에 기록할 스키마를 생성한다.
    cold_start 판정: state_history < 5건 또는 총 적용 건수 < 5건.

    Returns:
        {
            "schema_version": 1,
            "last_computed_at": "<ISO8601>",
            "cold_start": bool,
            "convergence_rate": float | None,
            "avg_iterations_to_green": float | None,
            "recurrence_rate": float | None,
            "skill_reuse": dict,
            "comment_classification_accuracy": {
                "requires_human_label": true,
                "value": null
            }
        }
    """
    # cold_start 판정: 유효한 state 이력 건수
    valid_states = [
        item for item in (state_history or [])
        if isinstance(item, dict) and isinstance(item.get("status"), str)
    ]
    retro_entries = retro_log_parser(retro_log_text) if isinstance(retro_log_text, str) else []
    total_applied = sum(e.get("applied", 0) for e in retro_entries)

    cold_start = len(valid_states) < _COLD_START_THRESHOLD or total_applied < _COLD_START_THRESHOLD

    # 각 지표 계산 (fail-safe)
    conv_rate: Optional[float]
    avg_iter: Optional[float]
    recur_rate: Optional[float]

    if cold_start:
        conv_rate = None
        avg_iter = None
        recur_rate = None
    else:
        try:
            conv_rate = convergence_rate(state_history)
        except Exception:
            conv_rate = None

        try:
            avg_iter = avg_iterations_to_green(state_history)
        except Exception:
            avg_iter = None

        try:
            recur_rate = recurrence_rate(retro_log_text)
        except Exception:
            recur_rate = None

    try:
        skill_info = skill_reuse_rate(state_history)
    except Exception:
        skill_info = {"cold_start": True, "skills": {}}

    return {
        "schema_version": 1,
        "last_computed_at": datetime.now(timezone.utc).isoformat(),
        "cold_start": cold_start,
        "convergence_rate": conv_rate,
        "avg_iterations_to_green": avg_iter,
        "recurrence_rate": recur_rate,
        "skill_reuse": skill_info,
        # Minor② 반영: 코멘트 분류 정확도는 사후 라벨 필요
        "comment_classification_accuracy": {
            "requires_human_label": True,
            "value": None,
        },
    }


def write_metrics(metrics: Dict[str, Any], path: Path) -> Dict[str, Any]:
    """지표 dict를 atomic_write로 path에 기록한다.

    last_computed_at 필드가 없으면 현재 시각으로 채운다.

    반환:
        atomic_write 결과: {"ok": bool, "path": str} 또는 {"ok": False, "error": str}

    fail-safe: 예외 미발생.
    """
    if not isinstance(metrics, dict):
        return {"ok": False, "error": "metrics must be a dict"}

    # last_computed_at 보장
    if "last_computed_at" not in metrics:
        metrics = dict(metrics)
        metrics["last_computed_at"] = datetime.now(timezone.utc).isoformat()

    try:
        return atomic_write(path, metrics)
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── 공개 API ──────────────────────────────────────────────────────────────────

__all__ = [
    "retro_log_parser",
    "convergence_rate",
    "avg_iterations_to_green",
    "recurrence_rate",
    "skill_reuse_rate",
    "compute_metrics",
    "write_metrics",
    "COLD_START_THRESHOLD",
]

# 공개 상수 (테스트에서 참조 가능)
COLD_START_THRESHOLD = _COLD_START_THRESHOLD
