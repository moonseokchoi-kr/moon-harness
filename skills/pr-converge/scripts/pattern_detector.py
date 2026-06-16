"""pattern_detector.py — 반복 CI 실패/리뷰 패턴 감지 + LEARNING append 페이로드 생성.

F15 (spec §F15, arch §3.2):
  동일 signal_key가 2회 이상 fix_attempts에 등장하면 반복 패턴으로 감지.
  감지된 패턴마다 LEARNING.md append 페이로드를 생성한다.

페이로드 포맷 (spec 해결 1 / arch §6 태그 계약):
  {
    "marker": "{YYYY-MM-DD} — {signal_key} / pr-converge",
    "tags": {
        "domain": "pr-converge",
        "stage": "pr-converge",
        "provenance_repo": "{repo_id}",
    },
    "body": "반복 CI/리뷰 실패 패턴: {signal_key} — {attempt_count}회 실패.",
  }

결정 경계:
  - "동일 signal_key" 일치: 결정적 문자열 동등 비교.
  - "같은 리뷰 의도": 프롬프트 레이어(SKILL.md) 담당 — 이 모듈은 관여 안 함.

Pure, deterministic, stdlib-only. gh/LLM/네트워크 호출 절대 금지.
Fail-safe: 예외 없이 구조화된 결과 반환.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

# 반복 패턴 임계값 (F15: 동일 신호 2회 이상)
REPEAT_THRESHOLD: int = 2


def detect_repeated_ci_fail(
    fix_attempts: Dict[str, Any],
    provenance_repo: str = "",
    detected_at: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """fix_attempts 딕셔너리에서 반복 실패 패턴을 감지한다.

    Args:
        fix_attempts: .harness/pr-converge-state.json의 fix_attempts 딕셔너리.
                      키: signal_key (str), 값: 시도 횟수 (int 또는 str).
        provenance_repo: 출처 repo 식별자 (F15 Acceptance: source_repo 필드).
                         비어 있으면 "unknown"으로 폴백.
        detected_at: 감지 일자 ISO 날짜 문자열 (YYYY-MM-DD).
                     None이면 현재 UTC 날짜 사용.

    Returns:
        반복 패턴이 감지된 각 신호에 대한 LEARNING append 페이로드 list.
        패턴 없으면 빈 리스트.

        페이로드 dict:
          {
            "marker": str,      # "YYYY-MM-DD — {signal_key} / pr-converge"
            "tags": dict,       # {domain, stage, provenance_repo}
            "body": str,        # 학습 내용 서술
            "signal_key": str,  # 원본 신호 키 (참조용)
            "attempt_count": int,  # 감지 시점 시도 횟수
          }

    Fail-safe: fix_attempts가 dict가 아니면 [] 반환. raise 금지.
    """
    if not isinstance(fix_attempts, dict):
        return []

    date_str = _resolve_date(detected_at)
    repo = provenance_repo.strip() if isinstance(provenance_repo, str) and provenance_repo.strip() else "unknown"

    payloads: List[Dict[str, Any]] = []
    for signal_key, count in fix_attempts.items():
        if not isinstance(signal_key, str):
            continue
        try:
            attempt_count = int(count)
        except (TypeError, ValueError):
            continue

        if attempt_count >= REPEAT_THRESHOLD:
            payload = _build_payload(signal_key, attempt_count, repo, date_str)
            payloads.append(payload)

    return payloads


def build_learning_payload(
    signal_key: str,
    attempt_count: int,
    provenance_repo: str = "unknown",
    detected_at: Optional[str] = None,
    extra_context: str = "",
) -> Dict[str, Any]:
    """단일 신호에 대한 LEARNING append 페이로드를 직접 생성한다.

    detect_repeated_ci_fail 내부에서도 사용하며, 외부에서 개별 페이로드를
    직접 생성할 때도 호출 가능.

    Args:
        signal_key: 신호 식별자 (예: "ci:unit-tests", "comment:12345").
        attempt_count: 실패 시도 횟수.
        provenance_repo: 출처 repo 식별자.
        detected_at: 감지 일자 (YYYY-MM-DD). None이면 현재 UTC 날짜.
        extra_context: 본문에 추가할 선택적 컨텍스트.

    Returns:
        LEARNING.md append 페이로드 dict.

    Fail-safe: 인자 타입이 올바르지 않으면 가능한 한 동작. raise 금지.
    """
    date_str = _resolve_date(detected_at)
    safe_key = str(signal_key) if signal_key else "unknown-signal"
    safe_repo = str(provenance_repo).strip() if provenance_repo else "unknown"
    safe_count = int(attempt_count) if isinstance(attempt_count, (int, float)) else 0

    return _build_payload(safe_key, safe_count, safe_repo, date_str, extra_context)


# ─── 내부 헬퍼 ────────────────────────────────────────────────────

def _resolve_date(detected_at: Optional[str]) -> str:
    """감지 일자를 YYYY-MM-DD 형식으로 반환. None이면 UTC 오늘 날짜."""
    if detected_at and isinstance(detected_at, str):
        # 간단히 첫 10자 사용 (ISO8601 날짜 부분)
        stripped = detected_at.strip()[:10]
        if len(stripped) == 10:
            return stripped
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _build_payload(
    signal_key: str,
    attempt_count: int,
    provenance_repo: str,
    date_str: str,
    extra_context: str = "",
) -> Dict[str, Any]:
    """LEARNING append 페이로드 dict를 조립한다."""
    marker = f"{date_str} — {signal_key} / pr-converge"
    body_lines = [
        f"반복 CI/리뷰 실패 패턴: `{signal_key}` — {attempt_count}회 실패.",
        f"동일 신호가 {attempt_count}회 이상 fix_attempts에 등록됨.",
        "이 패턴이 여러 프로젝트에서 반복되면 하네스 티어 개선 후보가 됨.",
    ]
    if extra_context:
        body_lines.append(extra_context)

    return {
        "marker": marker,
        "tags": {
            "domain": "pr-converge",
            "stage": "pr-converge",
            "provenance_repo": provenance_repo,
        },
        "body": "\n".join(body_lines),
        "signal_key": signal_key,
        "attempt_count": attempt_count,
    }


__all__ = [
    "REPEAT_THRESHOLD",
    "detect_repeated_ci_fail",
    "build_learning_payload",
]
