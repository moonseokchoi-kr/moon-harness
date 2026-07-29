"""tests/test_kompound_snapshot_static_imports.py

T-2 (SDD Phase 4, kompound-snapshot-hook) 정적 검사 뼈대 + 공용 fixture
(`fake_kompound_env`, tests/conftest.py) 계약 스모크 테스트.

이 파일은 두 가지를 검증한다 — 파일 소유권상 별도 파일을 새로 만들 수 없어
(T-2 owned files 3개 한정) 한 파일에 담는다:

1. **정적 검사 (F13·F16 acceptance)** — `hooks/lib/kompound_snapshot/` 아래
   모든 `.py`가 stdlib(+ 이 플러그인의 `hooks.*` 네임스페이스, arch §4가 허용한
   `hooks.lib.self_improve` 단방향 재사용 포함) 외 모듈을 import하지 않고,
   사용자 고유 절대경로 리터럴(`/Users/...`, `/home/...`)을 담고 있지 않음을
   검사한다. **모듈이 존재하는 개수를 단정하지 않는다** — T-3~T-11이 파일을
   추가할 때마다 이 테스트가 자동으로 그 파일까지 스캔 범위를 넓힌다.
2. **`fake_kompound_env` fixture 계약 스모크 (arch §9.3, spec F13)** — fixture가
   반환하는 구조가 spec/arch가 고정한 스키마와 정확히 일치하고, kompound가
   커밋 직후 clean 상태(F9/F8 케이스를 그 위에 시뮬레이션할 수 있는 전제)이며,
   §6.3.1 경계 케이스가 실제로 심어져 있음을 확인한다.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PACKAGE_DIR = _REPO_ROOT / "hooks" / "lib" / "kompound_snapshot"
_CONFTEST_PATH = Path(__file__).resolve().parent / "conftest.py"

# ── 스캔 대상 ────────────────────────────────────────────────────────────────


def _iter_package_py_files() -> List[Path]:
    """`hooks/lib/kompound_snapshot/` 아래 모든 `.py`를 반환한다(개수 미단정).

    패키지가 아직 없으면(이론상 불가 — 이 태스크가 `__init__.py`를 만든다)
    빈 리스트를 반환해 이후 테스트가 자명하게 통과한다(스캔 대상 0개).
    """
    if not _PACKAGE_DIR.is_dir():
        return []
    return sorted(_PACKAGE_DIR.rglob("*.py"))


# ── F13 acceptance: stdlib-only import 정적 검사 ────────────────────────────

# 이 플러그인 자신의 네임스페이스(`hooks.*`) — kompound_snapshot의 자기 참조
# import(`hooks.lib.kompound_snapshot.config` 등)와 arch §4가 명시적으로 허용한
# `hooks.lib.self_improve.state_io` 단방향 재사용을 함께 허용한다.
_ALLOWED_NON_STDLIB_ROOTS: Set[str] = {"hooks"}
_ALLOWED_ROOTS: Set[str] = {"__future__"} | _ALLOWED_NON_STDLIB_ROOTS


def _stdlib_roots() -> Set[str]:
    """현재 인터프리터의 표준 라이브러리 최상위 모듈 이름 집합."""
    names = getattr(sys, "stdlib_module_names", None)
    if names:
        return set(names)
    # pragma: no cover - Python 3.10 미만 폴백(이 레포는 3.11+ 전제, CLAUDE.md)
    return set(sys.builtin_module_names)


def _import_roots(tree: ast.Module) -> Iterable[str]:
    """AST에서 import된 최상위 모듈 이름을 전부 뽑는다.

    `from . import x` 처럼 상대 import(level > 0, module=None)는 항상
    패키지 내부 참조이므로 스킵한다(외부 의존이 될 수 없다).
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue  # 상대 import — 패키지 내부, 외부 의존 아님
            if node.module:
                yield node.module.split(".")[0]


def test_kompound_snapshot_package_dir_exists() -> None:
    """T-2 완료 조건: 패키지 디렉토리와 `__init__.py`가 존재한다."""
    assert _PACKAGE_DIR.is_dir(), f"missing package dir: {_PACKAGE_DIR}"
    assert (_PACKAGE_DIR / "__init__.py").is_file()


def test_kompound_snapshot_imports_are_stdlib_or_internal_only() -> None:
    """`hooks/lib/kompound_snapshot/`의 모든 `.py`가 stdlib 외 모듈을
    import하지 않는다(F13 acceptance) — `hooks.*` 내부 참조만 예외.

    현재는 `__init__.py`만 존재해 자명하게 통과한다. 이후 태스크가 모듈을
    추가할 때마다 `_iter_package_py_files()`가 그 파일까지 스캔하므로
    이 테스트를 개별 모듈마다 갱신할 필요가 없다.
    """
    violations: List[str] = []
    for path in _iter_package_py_files():
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        roots = set(_import_roots(tree)) - _stdlib_roots()
        disallowed = roots - _ALLOWED_ROOTS
        if disallowed:
            rel = path.relative_to(_REPO_ROOT)
            violations.append(f"{rel}: non-stdlib import root(s) {sorted(disallowed)}")

    assert not violations, "stdlib-only 위반:\n" + "\n".join(violations)


# ── F16 acceptance: 사용자 고유 절대경로 리터럴 0개 ──────────────────────────

_USER_ABS_PATH_RE = re.compile(r"/(?:Users|home)/[^\s\"'<>]+")


def _string_constants(tree: ast.Module) -> Iterable[str]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.value


def test_kompound_snapshot_has_no_user_specific_absolute_path_literals() -> None:
    """`hooks/lib/kompound_snapshot/`의 어떤 `.py`도 `/Users/...`·`/home/...`
    같은 사용자 고유 절대경로 리터럴을 문자열 상수로 갖지 않는다(F16 acceptance
    — "리터럴 카운트 0"). 스캔 루트·kompound 경로는 `config.resolve_config()`을
    통해서만 주입돼야 한다(env/설정파일/자동탐색), 코드에 박아 넣지 않는다.
    """
    violations: List[str] = []
    for path in _iter_package_py_files():
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for value in _string_constants(tree):
            if _USER_ABS_PATH_RE.search(value):
                rel = path.relative_to(_REPO_ROOT)
                violations.append(f"{rel}: {value!r}")

    assert not violations, "사용자 고유 절대경로 리터럴 발견:\n" + "\n".join(violations)


# ── fake_kompound_env 계약 스모크 (arch §9.3, spec F13 fixture 구조) ────────


def test_fake_kompound_env_is_defined_exactly_once() -> None:
    """`tests/conftest.py`에 `fake_kompound_env`가 정확히 1곳에 정의돼 있다
    (완료 조건: "중복 fixture 정의 없음 — grep으로 1회 등장 확인 가능").
    """
    text = _CONFTEST_PATH.read_text(encoding="utf-8")
    occurrences = len(re.findall(r"^def fake_kompound_env\(", text, flags=re.MULTILINE))
    assert occurrences == 1, (
        f"fake_kompound_env 정의가 {occurrences}회 발견됨(정확히 1회여야 함)"
    )


def test_fake_kompound_env_schema(fake_kompound_env: Dict[str, Any]) -> None:
    """반환 스키마가 spec F13 명세와 정확히 일치한다:
    ``{"kompound": Path, "workspace": Path, "config": dict}``.
    """
    assert set(fake_kompound_env.keys()) == {"kompound", "workspace", "config"}
    assert isinstance(fake_kompound_env["kompound"], Path)
    assert isinstance(fake_kompound_env["workspace"], Path)
    assert isinstance(fake_kompound_env["config"], dict)

    config = fake_kompound_env["config"]
    expected_keys = {
        "schema_version",
        "kompound_repo",
        "scan_root",
        "max_anchor_depth",
        "state_max_age_hours",
        "prefix_map",
    }
    assert set(config.keys()) == expected_keys
    assert config["kompound_repo"] == str(fake_kompound_env["kompound"])
    assert config["scan_root"] == str(fake_kompound_env["workspace"])
    assert isinstance(config["prefix_map"], dict) and config["prefix_map"]


def test_fake_kompound_structure(fake_kompound_env: Dict[str, Any]) -> None:
    """가짜 kompound에 `raw/`·`wiki/{sdd-spec-registry,index,log}.md`가 있다."""
    kompound = fake_kompound_env["kompound"]
    assert (kompound / "raw").is_dir()
    assert (kompound / "wiki" / "sdd-spec-registry.md").is_file()
    assert (kompound / "wiki" / "index.md").is_file()
    assert (kompound / "wiki" / "log.md").is_file()
    assert any((kompound / "raw").iterdir())


def test_fake_kompound_git_is_clean(fake_kompound_env: Dict[str, Any]) -> None:
    """fixture 반환 직후 kompound가 커밋된 clean 상태다.

    이것이 F9(dirty/diverge)·F8(검증 게이트) 케이스를 동일 fixture 위에서
    시뮬레이션 가능함을 보이는 스모크 테스트다 — 각 케이스는 이 clean
    베이스라인 위에 결함(미커밋 변경, 어긋난 upstream 등)을 주입해 재현한다.
    """
    kompound = fake_kompound_env["kompound"]
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=kompound,
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "", f"kompound가 clean이 아님: {result.stdout!r}"


def test_fake_workspace_structure(fake_kompound_env: Dict[str, Any]) -> None:
    """가짜 workspace에 홈 repo 트리 + 워크트리 전용 문서 케이스가 있다."""
    workspace = fake_kompound_env["workspace"]
    prefix_map = fake_kompound_env["config"]["prefix_map"]
    repo_dirs = [d for d in workspace.iterdir() if d.is_dir()]
    assert repo_dirs, "workspace 아래 repo 디렉토리가 없음"

    repo_root = repo_dirs[0]
    assert repo_root.name in prefix_map, "repo 디렉토리 이름이 prefix_map 키와 불일치"

    sdd = repo_root / "docs" / "sdd"
    assert (sdd / "spec").is_dir() and any((sdd / "spec").iterdir())
    assert (sdd / "design" / "arch").is_dir() and any((sdd / "design" / "arch").iterdir())
    assert (sdd / "result").is_dir() and any((sdd / "result").iterdir())

    worktrees_dir = repo_root / "worktrees"
    assert worktrees_dir.is_dir()
    wt_dirs = [d for d in worktrees_dir.iterdir() if d.is_dir()]
    assert wt_dirs, "워크트리 전용 문서 케이스 디렉토리가 없음"
    wt_spec_dir = wt_dirs[0] / "docs" / "sdd" / "spec"
    assert wt_spec_dir.is_dir() and any(wt_spec_dir.iterdir())


def test_fake_kompound_boundary_case_seeded(fake_kompound_env: Dict[str, Any]) -> None:
    """§6.3.1 경계 케이스 — 프리픽스 미등록 + kind 접미사로 끝나는 raw 파일이
    최소 1건 심어져 있고, 그 프리픽스가 유효 프리픽스 집합(설정 병합 후,
    ``prefix_map.values()``) 밖임을 확인한다(스냅샷 집합에서 제외돼야 하는
    이유가 데이터로 성립함).
    """
    kompound = fake_kompound_env["kompound"]
    prefix_map = fake_kompound_env["config"]["prefix_map"]
    valid_prefixes = set(prefix_map.values())

    kind_suffixes = ("-spec", "-arch", "-ui", "-api", "-context", "-result")
    raw_files = list((kompound / "raw").glob("*.md"))

    boundary_candidates = [
        p
        for p in raw_files
        if p.stem.endswith(kind_suffixes)
        and not any(p.stem.startswith(prefix + "-") for prefix in valid_prefixes)
    ]
    assert boundary_candidates, (
        "§6.3.1 경계 케이스(미등록 프리픽스 + kind 접미사) 파일이 raw/에 없음"
    )
