"""hooks/lib/kompound_snapshot/dedup.py — F5 dedup(순수 함수, arch §5.4.4)

``(kind, md5)``로 문서 레코드를 그룹핑하고, 그룹 내 정렬 키
``("worktrees" in path, len(path))``(참고 구현·spec F5 그대로)로 정렬해
첫 번째를 canonical로 채택한다 — non-worktree 우선, 짧은 경로 우선.

해시가 다른 문서는 애초에 서로 다른 ``(kind, md5)`` 그룹으로 분리되므로
자동으로 "별개 문서"로 취급된다(그룹마다 자기 자신이 canonical). 동일
내용(md5)이 3사본 이상이어도 그룹 내 정렬 규칙 하나로 전부 처리된다.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Mapping, Tuple


def _sort_key(record: Mapping[str, Any]) -> Tuple[bool, int]:
    path = record["path"]
    return ("worktrees" in path, len(path))


def dedup(records: List[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """``(kind, md5)`` 그룹핑 후 그룹별 canonical 레코드 리스트를 반환한다.

    입력 순서·리스트 자체는 변경하지 않는다(순수 함수, read-only). 그룹 내
    정렬은 ``("worktrees" in path, len(path))`` 오름차순 — non-worktree
    (``False`` < ``True``)가 먼저, 짧은 경로가 먼저 온다.
    """
    groups: Dict[Tuple[str, str], List[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        groups[(record["kind"], record["md5"])].append(record)

    canonical: List[Dict[str, Any]] = []
    for group in groups.values():
        group_sorted = sorted(group, key=_sort_key)
        canonical.append(dict(group_sorted[0]))

    return canonical
