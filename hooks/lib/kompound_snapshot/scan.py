"""hooks/lib/kompound_snapshot/scan.py — F3 스캔 + repo_dir 도출 (arch §5.4.1/§5.4.2)

`docs/sdd/`(또는 `Docs/sdd/`) 앵커를 찾아 그 하위의 spec/arch/ui/api/context/
result 문서를 read-only로 수집하는 2단 스캔이다.

절차 (arch §5.4.1):
1. **앵커 탐색** — 각 스코프 루트에서 깊이 <= ``max_anchor_depth``(기본 5)까지만
   순회해 ``docs/sdd``/``Docs/sdd`` 디렉토리를 찾는다. ``SKIP_DIRS``는 이 단계
   에서도 프루닝하지만, 경로에 ``worktrees`` 세그먼트가 있으면 깊이 제한을
   적용하지 않는다(§2.3 실측 근거 — 워크트리 전용 문서가 실재).
2. **앵커 하위 전수 순회** — 앵커 아래는 깊이 제한 없이 전부 순회한다
   (``SKIP_DIRS`` 적용).
3. **kind 결정** — 앵커부터 현재 디렉토리까지의 세그먼트를 역순으로 훑어
   ``KINDS``에 먼저 걸리는 값을 채택한다. 못 찾으면 대상 아님.
4. **제외** — 경로에 ``/task`` 세그먼트가 있으면 스킵(``task/``·``tasks/`` 동시
   커버). 파일명이 ``SKIP_NAMES`` 중 하나를 포함하면 스킵. ``.md``가 아니면
   스킵.
5. **레코드 생성** — ``{"kind", "path", "md5", "mtime", "repo_dir"}``.
6. **오류 처리** — 개별 파일/디렉토리 권한 오류는 예외를 던지지 않고
   ``errors[]``에 누적하며 스캔을 계속한다(fail-safe, F13/F11).

이 모듈의 모든 공개 함수는 read-only이며 예외를 밖으로 던지지 않는다(권한
오류 등은 ``errors[]``로 흡수한다). stdlib만 사용한다(F13).
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

# ── 상수 (arch §5.4.1, 설계 SSOT 참고 구현 L153-178과 바이트 그대로 일치) ────

KINDS: Dict[str, str] = {
    "spec": "spec",
    "specs": "spec",
    "arch": "arch",
    "ui": "ui",
    "api": "api",
    "result": "result",
    "development": "arch",
    "context": "context",
}

SKIP_DIRS = {".git", "node_modules", "build", "ExternLib", ".venv", "venv"}

SKIP_NAMES = ("ORCHESTRATOR_STATE", "HANDOFF", "-GUIDE", "DESIGN.md", "test-guide-")

DEFAULT_MAX_ANCHOR_DEPTH = 5


# ── 앵커 탐색 (절차 1) ───────────────────────────────────────────────────────


def _is_sdd_anchor(path: Path) -> bool:
    """``path``가 ``docs/sdd`` 또는 ``Docs/sdd`` 디렉토리인가."""
    return path.name == "sdd" and path.parent.name in ("docs", "Docs")


def _has_worktrees_segment(path: Path) -> bool:
    return "worktrees" in path.parts


def find_anchors(
    scope_root: Path,
    max_anchor_depth: int = DEFAULT_MAX_ANCHOR_DEPTH,
    errors: Optional[List[Dict[str, str]]] = None,
) -> List[Path]:
    """``scope_root`` 하위에서 ``docs/sdd``/``Docs/sdd`` 앵커 디렉토리를 찾는다.

    깊이 <= ``max_anchor_depth``까지만 순회하되, 경로에 ``worktrees`` 세그먼트가
    있으면 깊이 제한을 적용하지 않는다. ``SKIP_DIRS``는 항상 프루닝한다.
    개별 디렉토리 접근 오류는 ``errors``(주어졌다면)에 누적하고 계속 진행한다.
    """
    anchors: List[Path] = []
    if errors is None:
        errors = []

    scope_root = Path(scope_root)
    if not scope_root.is_dir():
        return anchors

    stack: List[Tuple[Path, int]] = [(scope_root, 0)]
    while stack:
        current, depth = stack.pop()
        try:
            entries = list(os.scandir(current))
        except OSError as exc:
            errors.append({"path": str(current), "error": str(exc)})
            continue

        for entry in entries:
            try:
                is_dir = entry.is_dir(follow_symlinks=False)
            except OSError as exc:
                errors.append({"path": entry.path, "error": str(exc)})
                continue
            if not is_dir:
                continue

            name = entry.name
            if name in SKIP_DIRS:
                continue

            child = Path(entry.path)
            if _is_sdd_anchor(child):
                anchors.append(child)
                continue  # 앵커 자신의 하위는 절차2(전수 순회)가 담당한다

            if _has_worktrees_segment(child) or depth + 1 <= max_anchor_depth:
                stack.append((child, depth + 1))

    return anchors


# ── repo_dir 도출 (arch §5.4.2, 규칙 1~4) ───────────────────────────────────


def _read_gitdir_file(git_path: Path) -> Optional[Path]:
    """``.git``이 ``gitdir:`` 파일이면 파싱해 본체 repo 루트를 반환한다.

    ``gitdir: <path>``의 ``<path>``는 보통
    ``<main-repo>/.git/worktrees/<name>`` 형태다. 그 접미사를 제거한 것이
    본체 repo 루트다. 형식 불일치·파싱 실패 시 예외를 던지지 않고 ``None``을
    반환한다(호출자가 다음 규칙으로 폴백).
    """
    try:
        content = git_path.read_text(encoding="utf-8")
    except OSError:
        return None

    stripped = content.strip()
    if not stripped:
        return None
    first_line = stripped.splitlines()[0]
    if not first_line.startswith("gitdir:"):
        return None

    raw_path = first_line[len("gitdir:") :].strip()
    if not raw_path:
        return None

    gitdir_path = Path(raw_path)
    if not gitdir_path.is_absolute():
        gitdir_path = git_path.parent / gitdir_path

    parts = gitdir_path.parts
    if len(parts) >= 3 and parts[-3] == ".git" and parts[-2] == "worktrees":
        root_parts = parts[:-3]
        if not root_parts:
            return None
        return Path(*root_parts)
    return None


def derive_repo_dir(anchor: Path, scope_root: Path) -> Path:
    """arch §5.4.2 규칙 1~4 — 앵커에서 위로 올라가며 repo 루트를 도출한다.

    1. 경로에 ``worktrees`` 세그먼트가 있으면 그 세그먼트의 부모를 즉시 채택.
    2. 아니면 ``.git``(디렉토리 또는 ``gitdir:`` 파일)을 가진 첫 조상을 채택.
       ``gitdir:`` 파일이면 내용을 파싱해 본체 repo 루트를 도출한다(파싱 실패
       시 예외 없이 다음 규칙으로 폴백).
    3. 둘 다 실패하면 스코프 루트 자신을 repo 루트로 본다.
    """
    anchor = Path(anchor)
    scope_root = Path(scope_root)

    parts = anchor.parts
    if "worktrees" in parts:
        idx = parts.index("worktrees")
        if idx > 0:
            return Path(*parts[:idx])
        return scope_root

    current = anchor
    while True:
        git_path = current / ".git"
        if git_path.is_dir():
            return current
        if git_path.is_file():
            resolved = _read_gitdir_file(git_path)
            return resolved if resolved is not None else scope_root

        parent = current.parent
        if parent == current:
            return scope_root
        current = parent


# ── 앵커 하위 전수 순회 (절차 2) ─────────────────────────────────────────────


def _kind_for_dir(anchor: Path, directory: Path) -> Optional[str]:
    """앵커부터 ``directory``까지의 세그먼트를 역순으로 훑어 첫 KINDS 매치를 채택."""
    try:
        rel_parts = directory.relative_to(anchor).parts
    except ValueError:
        return None
    for segment in reversed(rel_parts):
        if segment in KINDS:
            return KINDS[segment]
    return None


def _walk_anchor(
    anchor: Path, errors: List[Dict[str, str]]
) -> Iterator[Tuple[Path, List[str]]]:
    """앵커 하위를 깊이 제한 없이 순회한다(``SKIP_DIRS`` 프루닝).

    각 디렉토리에 대해 ``(디렉토리, 파일명 리스트)``를 산출한다. 디렉토리 접근
    오류는 ``errors``에 누적하고 그 서브트리만 건너뛴다.
    """
    stack: List[Path] = [anchor]
    while stack:
        current = stack.pop()
        try:
            entries = list(os.scandir(current))
        except OSError as exc:
            errors.append({"path": str(current), "error": str(exc)})
            continue

        file_names: List[str] = []
        for entry in entries:
            try:
                is_dir = entry.is_dir(follow_symlinks=False)
            except OSError as exc:
                errors.append({"path": entry.path, "error": str(exc)})
                continue
            if is_dir:
                if entry.name not in SKIP_DIRS:
                    stack.append(Path(entry.path))
            else:
                file_names.append(entry.name)

        yield current, file_names


def _is_excluded_dir(directory: Path, anchor: Path) -> bool:
    """``task``/``tasks`` **세그먼트** 제외 규칙(arch §5.4.1 절차4 — 부분 문자열이
    아니라 정확한 경로 세그먼트 매칭이어야 한다).

    ``anchor``(``docs/sdd``) 기준 상대 세그먼트만 검사한다 — 절대경로 전체를
    보면 스코프 루트 상위 어딘가에 우연히 ``task``라는 디렉토리가 있어도
    오탐하기 때문이다(``_kind_for_dir``와 동일하게 앵커 상대 기준을 쓴다).

    ``task-notes``/``tasklog``/``taskforce-v2``처럼 ``task``로 시작하지만
    세그먼트 전체가 ``task``/``tasks``가 아닌 디렉토리는 제외하지 않는다 —
    이전 구현(``"/task" in directory.as_posix()``)의 부분 문자열 오탐을
    회귀 테스트로 고정한다([P1] 리뷰 반영, it.2).
    """
    try:
        rel_parts = directory.relative_to(anchor).parts
    except ValueError:
        rel_parts = directory.parts
    return bool({"task", "tasks"} & set(rel_parts))


def _is_excluded_name(name: str) -> bool:
    return any(marker in name for marker in SKIP_NAMES)


def _make_record(
    file_path: Path,
    kind: str,
    repo_dir: Path,
    errors: List[Dict[str, str]],
) -> Optional[Dict[str, Any]]:
    try:
        data = file_path.read_bytes()
        digest = hashlib.md5(data).hexdigest()
        mtime = file_path.stat().st_mtime
    except OSError as exc:
        errors.append({"path": str(file_path), "error": str(exc)})
        return None

    return {
        "kind": kind,
        "path": str(file_path),
        "md5": digest,
        "mtime": mtime,
        "repo_dir": str(repo_dir),
    }


# ── 공개 API ─────────────────────────────────────────────────────────────


def scan(
    scope_roots: Sequence[Any],
    max_anchor_depth: int = DEFAULT_MAX_ANCHOR_DEPTH,
) -> Dict[str, Any]:
    """스코프 루트 리스트를 스캔해 문서 레코드를 수집한다(read-only, fail-safe).

    반환: ``{"records": [...], "anchors": int, "errors": [...]}``.
    ``errors``가 비어있지 않아도 예외를 던지지 않는다 — 부분 실패는 구조화된
    신호로만 전달한다(F11 "스캔 실패"는 상위 계층인 report/cli가 이 신호를
    보고 판정한다).
    """
    errors: List[Dict[str, str]] = []
    records: List[Dict[str, Any]] = []
    anchors_total = 0

    for scope_root_raw in scope_roots:
        scope_root = Path(scope_root_raw)
        anchors = find_anchors(scope_root, max_anchor_depth, errors)
        anchors_total += len(anchors)

        for anchor in anchors:
            repo_dir = derive_repo_dir(anchor, scope_root)

            for directory, file_names in _walk_anchor(anchor, errors):
                kind = _kind_for_dir(anchor, directory)
                if kind is None:
                    continue
                if _is_excluded_dir(directory, anchor):
                    continue

                for name in file_names:
                    if not name.endswith(".md"):
                        continue
                    if _is_excluded_name(name):
                        continue

                    record = _make_record(directory / name, kind, repo_dir, errors)
                    if record is not None:
                        records.append(record)

    return {"records": records, "anchors": anchors_total, "errors": errors}
