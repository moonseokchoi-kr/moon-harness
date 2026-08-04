"""hooks/lib/kompound_snapshot/naming.py — F4/F12 네이밍(순수 함수, arch §5.4.3)

출력은 ``raw/<project>-<feature>-<kind>.md``. 4단계:

1. ``<project>`` = ``prefix_map[repo_dir 디렉토리 이름]``. 조회 실패 또는 값이
   ``None``이면 예외를 던지지 않고 ``{"unmapped": repo_dir}``을 반환한다(F12).
   1차 조회가 실패하면 ``scan_root``가 주어질 때 arch §5.4.2 규칙5의 완화
   재조회(스코프 루트 기준 상대경로의 선두 1세그먼트 → 선두 2세그먼트)를 시도한다.
2. ``<kind>`` — ``scan.py``가 이미 ``KINDS``로 매핑을 끝낸 값을 그대로 쓴다
   (레코드의 ``kind`` 필드). 이 모듈은 kind 매핑을 다시 하지 않는다.
3. ``<feature>`` = 원본 파일명(stem)에서 날짜 프리픽스(``^\\d{4}-\\d{2}-\\d{2}-``)와
   접미사(``-spec``/``-dev``/``-result``)를 제거한 나머지.
4. ``<project>-<project>-...`` 꼴이면 중복된 프리픽스 하나를 접는다.

**주의(T-4 결정 — task 문서 명시 지침)**: 기본 프리픽스 매핑(spec F4의 10종)은
이 모듈이 정의하지 않는다. 그 값의 단일 진실은 T-3 ``config.py``의
``resolve_config()``이며, 이 모듈은 ``prefix_map``을 순수하게 인자로만 받는다.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

_DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-")
_FEATURE_SUFFIXES = ("-spec", "-dev", "-result")


def _strip_feature(stem: str) -> str:
    """날짜 프리픽스와 kind 접미사를 제거해 ``<feature>``를 얻는다."""
    feature = _DATE_PREFIX_RE.sub("", stem)
    for suffix in _FEATURE_SUFFIXES:
        if feature.endswith(suffix):
            feature = feature[: -len(suffix)]
            break
    return feature


def _fold_duplicate_prefix(project: str, feature: str) -> str:
    """``feature``가 이미 ``<project>-``로 시작하면 그 접두를 접어낸다.

    예: project="codegraph", feature="codegraph-internal-mcp" →
    "internal-mcp" (최종 raw_name이 "codegraph-codegraph-internal-mcp-result"가
    아니라 "codegraph-internal-mcp-result"가 되도록).
    """
    prefix = project + "-"
    if feature.startswith(prefix):
        return feature[len(prefix) :]
    return feature


def resolve_prefix(
    repo_dir: str,
    prefix_map: Mapping[str, Optional[str]],
    scan_root: Optional[str] = None,
) -> Optional[str]:
    """``repo_dir``로 ``prefix_map``을 조회한다(arch §5.4.2 규칙5).

    1차: ``repo_dir``의 디렉토리 이름으로 조회. 값이 존재하고 ``None``이
    아니면 그 값을 반환한다.

    실패(키 없음 또는 값이 ``None``)하고 ``scan_root``가 주어지면, ``repo_dir``의
    ``scan_root`` 기준 상대경로에서 선두 1세그먼트 → 선두 2세그먼트(``/``로
    결합) 순으로 완화 재조회한다. 그래도 실패하면 ``None``(미등록)을 반환한다
    — 예외를 던지지 않는다.
    """
    name = Path(repo_dir).name
    value = prefix_map.get(name)
    if value is not None:
        return value

    if scan_root is None:
        return None

    try:
        rel = Path(repo_dir).resolve().relative_to(Path(scan_root).resolve())
    except (ValueError, OSError):
        return None

    parts = rel.parts
    if not parts:
        return None

    one_segment = prefix_map.get(parts[0])
    if one_segment is not None:
        return one_segment

    if len(parts) >= 2:
        two_segment_key = "/".join(parts[:2])
        two_segment = prefix_map.get(two_segment_key)
        if two_segment is not None:
            return two_segment

    return None


def name_document(
    record: Mapping[str, Any],
    prefix_map: Mapping[str, Optional[str]],
    scan_root: Optional[str] = None,
) -> Dict[str, Any]:
    """문서 레코드를 ``raw/<project>-<feature>-<kind>.md``로 변환한다(순수 함수).

    ``record``는 최소 ``{"kind", "path", "repo_dir"}``를 갖는 매핑이다(scan.py
    레코드 스키마와 호환). 프리픽스 조회 실패 시 예외 없이
    ``{"unmapped": repo_dir}``을 반환한다(F12) — ``pending``에는 절대 합산하지
    않는다(그 집계는 이 함수의 반환 shape로 상위 계층이 구분한다:
    ``"raw_name"`` 키가 있으면 명명 성공, ``"unmapped"`` 키가 있으면 미등록).
    """
    repo_dir = record["repo_dir"]
    project = resolve_prefix(repo_dir, prefix_map, scan_root)
    if project is None:
        return {"unmapped": repo_dir}

    kind = record["kind"]
    stem = Path(record["path"]).stem
    feature = _strip_feature(stem)
    feature = _fold_duplicate_prefix(project, feature)

    return {"raw_name": f"raw/{project}-{feature}-{kind}.md"}
