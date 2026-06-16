"""comment_dedup.py — processed_comment_ids 대조 신규 코멘트 필터링.

SKILL.md Step 1 관측 단계에서, gh로 수집한 전체 코멘트 목록에서
이미 처리된 코멘트(processed_comment_ids)를 제거한 신규 코멘트만 반환한다.

Pure, deterministic, stdlib-only. gh/LLM/네트워크 호출 절대 금지.
Fail-safe: 비정상 입력에 예외 없이 빈 리스트 반환.
"""

from __future__ import annotations

from typing import Any, Dict, List, Set, Union


def filter_new_comments(
    all_comments: List[Dict[str, Any]],
    processed_ids: List[Union[str, int]],
) -> List[Dict[str, Any]]:
    """전체 코멘트 목록에서 미처리 신규 코멘트만 반환한다.

    Args:
        all_comments: gh API로 수집한 전체 코멘트 목록.
                      각 코멘트 dict는 "id" 키를 가져야 한다.
                      없거나 None이면 빈 리스트로 처리.
        processed_ids: 이미 처리된 코멘트 ID 목록
                       (.harness/pr-converge-state.json의 processed_comment_ids).
                       str 또는 int 혼용 허용 — 비교 시 str로 정규화.

    Returns:
        processed_ids에 없는 신규 코멘트 dict 목록.
        입력 순서를 유지한다. 원본 dict는 변경하지 않는다.

    Fail-safe 규칙:
        - all_comments가 list가 아니면 [] 반환.
        - 개별 코멘트가 dict가 아니거나 "id" 키가 없으면 신규로 취급 (누락 방지).
        - processed_ids가 list가 아니면 빈 set으로 처리 (전체를 신규로 취급).
    """
    if not isinstance(all_comments, list):
        return []

    # processed_ids를 str 집합으로 정규화 (str/int 혼용 대응)
    processed_set: Set[str] = _normalize_id_set(processed_ids)

    result: List[Dict[str, Any]] = []
    for comment in all_comments:
        if not isinstance(comment, dict):
            # dict가 아닌 원소는 보수적으로 신규 취급 (누락 방지)
            continue
        comment_id = comment.get("id")
        if comment_id is None:
            # id 없는 코멘트: 신규로 취급 (누락 방지)
            result.append(comment)
            continue
        if _normalize_id(comment_id) not in processed_set:
            result.append(comment)

    return result


def mark_as_processed(
    processed_ids: List[Union[str, int]],
    new_ids: List[Union[str, int]],
) -> List[Union[str, int]]:
    """processed_ids에 new_ids를 추가해 새 목록을 반환한다.

    중복 없이 병합. 원본 리스트를 변경하지 않는다 (불변).

    Args:
        processed_ids: 기존 processed_comment_ids.
        new_ids: 이번 패스에서 새로 처리한 코멘트 ID 목록.

    Returns:
        병합된 새 목록 (str/int 타입 보존, 중복 제거).

    Fail-safe: 어느 쪽이 list가 아니어도 가능한 목록을 반환.
    """
    existing: List[Union[str, int]] = processed_ids if isinstance(processed_ids, list) else []
    additions: List[Union[str, int]] = new_ids if isinstance(new_ids, list) else []

    # 정규화된 str set으로 중복 체크
    seen_str: Set[str] = {_normalize_id(i) for i in existing}
    merged = list(existing)
    for item in additions:
        item_str = _normalize_id(item)
        if item_str not in seen_str:
            merged.append(item)
            seen_str.add(item_str)

    return merged


# ─── 내부 헬퍼 ────────────────────────────────────────────────────

def _normalize_id(value: Any) -> str:
    """코멘트 ID를 str로 정규화 (str/int 혼용 대응)."""
    if value is None:
        return ""
    return str(value).strip()


def _normalize_id_set(ids: Any) -> Set[str]:
    """ID 목록을 str set으로 변환. list가 아니면 빈 set 반환."""
    if not isinstance(ids, list):
        return set()
    return {_normalize_id(i) for i in ids if i is not None}


__all__ = [
    "filter_new_comments",
    "mark_as_processed",
]
