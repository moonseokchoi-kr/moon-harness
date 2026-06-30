"""hooks/lib/self_improve/learning_source.py — I/O 집계 로더.

로컬 LEARNING.md 와 store 디렉터리의 *.md 파일을 읽어 파싱된 엔트리 목록으로
합산한다. 모든 I/O 실패는 catch-and-skip(A 부류)으로 처리하며 raise 절대 금지.

의존:
    hooks.lib.self_improve.parser.parse_learning_entry  (stdlib-only, 순수 함수)

제약:
    - stdlib only (pathlib, os, typing)
    - 모듈 최상위 I/O/env/경로계산 부작용 0 (NFR-2)
    - import 시점 부작용 0
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional, Union

from hooks.lib.self_improve.parser import parse_learning_entry


def load_and_merge(
    local_learning_path: Union[str, os.PathLike, None],
    store_dir: Union[str, os.PathLike, None],
) -> List[dict]:
    """로컬 LEARNING.md 와 store 디렉터리 *.md 를 읽어 파싱된 엔트리 목록을 반환한다.

    반환 타입 불변: 어떤 입력/실패에도 항상 list[dict] 반환. raise 절대 금지.

    Args:
        local_learning_path: 로컬 LEARNING.md 경로. None 또는 읽기 실패 시 [] 처리.
        store_dir: store *.md 디렉터리 경로. None/부재/파일 경로 전달 시 기여 없음.

    Returns:
        로컬 entries(앞) + store entries(파일명 정렬, 뒤) 를 이어붙인 list[dict].
    """
    entries: List[dict] = []

    # ── 로컬 파일 읽기·파싱 (A 부류: 실패 시 []) ─────────────────────────────
    entries.extend(_load_local(local_learning_path))

    # ── store_dir=None → store 기여 없음 ─────────────────────────────────────
    if store_dir is None:
        return entries

    # ── store 디렉터리 열거·파싱·이어붙임 (A 부류: 실패 시 기여 없음) ──────────
    entries.extend(_load_store(store_dir))

    return entries


def _load_local(
    local_learning_path: Union[str, os.PathLike, None],
) -> List[dict]:
    """로컬 LEARNING.md 를 읽어 파싱된 엔트리 목록을 반환한다.

    None, 파일 부재, 읽기 실패 모두 [] 반환 (A 부류).
    """
    if local_learning_path is None:
        return []

    try:
        p = Path(local_learning_path)
        text = p.read_text(encoding="utf-8")
        return parse_learning_entry(text)
    except Exception:
        return []


def _load_store(
    store_dir: Union[str, os.PathLike],
) -> List[dict]:
    """store 디렉터리의 *.md 파일을 파일명 정렬 순으로 읽어 파싱된 엔트리 목록을 반환한다.

    디렉터리 부재, 파일 경로 전달(디렉터리 아님), 열거 실패 → [] (A 부류).
    개별 파일 읽기/파싱 실패 → 그 파일만 skip (A 부류).
    H2 없는 파일 → parse_learning_entry([]) → 0 기여 (B 부류, 정상).
    """
    try:
        d = Path(store_dir)
        if not d.is_dir():
            return []
        md_files = sorted(d.glob("*.md"), key=lambda f: f.name)
    except Exception:
        return []

    result: List[dict] = []
    for md_file in md_files:
        try:
            text = md_file.read_text(encoding="utf-8")
            result.extend(parse_learning_entry(text))
        except Exception:
            # A 부류: 개별 파일 실패 → skip
            continue

    return result
