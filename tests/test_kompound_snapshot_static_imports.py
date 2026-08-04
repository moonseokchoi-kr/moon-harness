"""tests/test_kompound_snapshot_static_imports.py

T-2 (SDD Phase 4, kompound-snapshot-hook) 정적 검사 뼈대 + 공용 fixture
(`fake_kompound_env`, tests/conftest.py) 계약 스모크 테스트.

이 파일은 두 가지를 검증한다 — 파일 소유권상 별도 파일을 새로 만들 수 없어
(T-2 owned files 3개 한정) 한 파일에 담는다:

1. **정적 검사 (F13·F16 acceptance)** — `hooks/lib/kompound_snapshot/` 아래
   모든 `.py`가 stdlib 외 모듈을 import하지 않고, 사용자 고유 절대경로
   리터럴(`/Users/...`, `/home/...`)을 담고 있지 않음을 검사한다. 허용되는
   유일한 non-stdlib import는 **전체 dotted path** 기준 두 prefix뿐이다 —
   `hooks.lib.kompound_snapshot`(자기 참조)과
   `hooks.lib.self_improve.state_io`(arch §4가 명시적으로 허용한 단 하나의
   단방향 재사용). `hooks.lib.self_improve`의 다른 하위 모듈(`tier`/`guard`
   등)은 최상위 세그먼트("hooks")만 같을 뿐 이 두 prefix 밖이므로 위반으로
   판정된다 — 회귀 테스트(`test_import_checker_flags_disallowed_self_improve_submodule`)가
   이 판정이 실제로 동작함을 고정한다. **모듈이 존재하는 개수를 단정하지
   않는다** — T-3~T-11이 파일을 추가할 때마다 이 테스트가 자동으로 그
   파일까지 스캔 범위를 넓힌다.
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
#
# 허용되는 non-stdlib import는 정확히 두 **전체 dotted-path prefix**뿐이다
# (arch §4 의존 방향):
#   1. `hooks.lib.kompound_snapshot` — 이 패키지 자기 참조(하위 모듈끼리의
#      내부 import, `hooks.lib.kompound_snapshot.config` 등).
#   2. `hooks.lib.self_improve.state_io` — arch §4가 명시적으로 허용한
#      **단 하나의** 단방향 재사용. `hooks.lib.self_improve`의 다른 하위
#      모듈(`tier`, `guard`, `cursor`, …)은 이 prefix에 포함되지 않으므로
#      **위반**이다 — `self_improve`의 다른 유닛을 끌어오면 두 패키지의
#      경계가 흐려지고 "역방향 의존 금지" 규칙을 우회하는 뒷문이 된다.
#
# 최상위 세그먼트("hooks")만 비교하면 이 경계가 전혀 강제되지 않는다
# (`hooks.lib.self_improve.tier`도 top-level은 "hooks"라 통과해버림) —
# 그래서 아래 검사는 항상 **전체 dotted path**로 prefix 매칭한다.
_ALLOWED_HOOKS_IMPORT_PREFIXES: tuple = (
    "hooks.lib.kompound_snapshot",
    "hooks.lib.self_improve.state_io",
)


def _is_allowed_hooks_import(dotted: str) -> bool:
    """`dotted`(전체 import 경로)가 위 두 허용 prefix 중 하나이거나 그 하위인가.

    경계는 '.' 세그먼트 단위다 — 문자열 접두사만 비교하면
    `hooks.lib.self_improve.state_io_extra` 같은 우연한 이웃 이름까지
    통과시키는 함정이 생긴다.
    """
    return any(
        dotted == prefix or dotted.startswith(prefix + ".")
        for prefix in _ALLOWED_HOOKS_IMPORT_PREFIXES
    )


def _stdlib_roots() -> Set[str]:
    """현재 인터프리터의 표준 라이브러리 최상위 모듈 이름 집합."""
    names = getattr(sys, "stdlib_module_names", None)
    if names:
        return set(names)
    # pragma: no cover - Python 3.10 미만 폴백(이 레포는 3.11+ 전제, CLAUDE.md)
    return set(sys.builtin_module_names)


def _import_paths(tree: ast.Module) -> Iterable[str]:
    """AST에서 import된 **전체 dotted path**를 전부 뽑는다(최상위 세그먼트만이
    아니다 — `hooks.lib.self_improve.tier`처럼 두 번째·세 번째 세그먼트에서
    허용 경계를 벗어나는 import를 잡으려면 전체 경로가 필요하다).

    `from . import x` 처럼 상대 import(level > 0, module=None)는 항상
    패키지 내부 참조이므로 스킵한다(외부 의존이 될 수 없다).
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue  # 상대 import — 패키지 내부, 외부 의존 아님
            if node.module:
                yield node.module


def _find_import_violations(source: str, filename: str = "<test>") -> List[str]:
    """`source`(파이썬 코드 텍스트)에서 stdlib-only 규약을 위반하는 전체
    dotted import path 목록을 반환한다(위반 없으면 빈 리스트).

    파일시스템과 무관한 순수 함수다 — 실 패키지 스캔(아래 테스트)과 회귀
    테스트(합성 소스 문자열)가 이 함수 하나를 공유해, "검사기가 실제로
    위반을 잡는지"를 실 파일을 오염시키지 않고 검증할 수 있다.
    """
    tree = ast.parse(source, filename=filename)
    stdlib = _stdlib_roots()
    violations: List[str] = []
    for dotted in _import_paths(tree):
        top = dotted.split(".")[0]
        if top == "__future__" or top in stdlib:
            continue
        if top == "hooks":
            if not _is_allowed_hooks_import(dotted):
                violations.append(dotted)
            continue
        # top-level이 stdlib도 "hooks"도 아니면 외부 pip 의존 — 무조건 위반.
        violations.append(dotted)
    return violations


def test_kompound_snapshot_package_dir_exists() -> None:
    """T-2 완료 조건: 패키지 디렉토리와 `__init__.py`가 존재한다."""
    assert _PACKAGE_DIR.is_dir(), f"missing package dir: {_PACKAGE_DIR}"
    assert (_PACKAGE_DIR / "__init__.py").is_file()


def test_kompound_snapshot_imports_are_stdlib_or_internal_only() -> None:
    """`hooks/lib/kompound_snapshot/`의 모든 `.py`가 stdlib 외 모듈을
    import하지 않는다(F13 acceptance) — 허용 예외는
    `hooks.lib.kompound_snapshot`(자기 참조)와
    `hooks.lib.self_improve.state_io`(arch §4가 허용한 단 하나의 단방향
    재사용) 두 **전체 경로** prefix뿐이다.

    현재는 `__init__.py`만 존재해 자명하게 통과한다. 이후 태스크가 모듈을
    추가할 때마다 `_iter_package_py_files()`가 그 파일까지 스캔하므로
    이 테스트를 개별 모듈마다 갱신할 필요가 없다.
    """
    violations: List[str] = []
    for path in _iter_package_py_files():
        source = path.read_text(encoding="utf-8")
        found = _find_import_violations(source, filename=str(path))
        if found:
            rel = path.relative_to(_REPO_ROOT)
            violations.append(f"{rel}: disallowed import path(s) {sorted(found)}")

    assert not violations, "stdlib-only 위반:\n" + "\n".join(violations)


def test_import_checker_flags_disallowed_self_improve_submodule() -> None:
    """회귀 케이스 — 검사기가 실제로 위반을 잡는지 검증한다.

    `hooks.lib.self_improve.tier`는 arch §4가 허용한 `state_io` 재사용이
    아니므로, 최상위 세그먼트("hooks")만 보는 느슨한 검사기라면 이 회귀가
    FAIL(=조용히 GREEN)해야 정상이지만, 이 테스트는 그 반대(위반이 실제로
    검출됨)를 요구한다. 실 패키지 파일을 만들지 않고 합성 소스 문자열을
    `_find_import_violations()`에 직접 주입해 검증한다(패키지 오염 없음).
    """
    bad_source = (
        "from __future__ import annotations\n"
        "from hooks.lib.self_improve.tier import classify_tier\n"
    )
    violations = _find_import_violations(bad_source)
    assert violations == ["hooks.lib.self_improve.tier"], (
        f"위반이 검출되지 않음(거짓 GREEN 위험): {violations!r}"
    )


def test_import_checker_allows_state_io_and_self_reference() -> None:
    """양성 대조 — 허용된 두 경로는 위반으로 잡히지 않아야 한다."""
    good_source = (
        "from __future__ import annotations\n"
        "import json\n"
        "from hooks.lib.self_improve.state_io import atomic_write\n"
        "from hooks.lib.kompound_snapshot.config import resolve_config\n"
    )
    assert _find_import_violations(good_source) == []


def test_import_checker_flags_external_pip_dependency() -> None:
    """양성 대조 — stdlib도 `hooks.*`도 아닌 외부 pip 의존은 위반이다."""
    bad_source = "import requests\n"
    assert _find_import_violations(bad_source) == ["requests"]


# ── F16 acceptance: 사용자 고유 절대경로 리터럴 0개 ──────────────────────────
#
# C-2(T-11, ORCHESTRATOR_STATE.md "이월 실행 항목") — 이 정규식이 원래
# `/Users/`·`/home/`(POSIX)만 잡아 arch §2.2 "Windows(Git-bash)에서 깨지지
# 않아야 한다" 제약과 별개로 `C:\Users\...` 같은 Windows 스타일 절대경로
# 리터럴은 못 잡는다는 지적이 있었다. 판단: **백슬래시 형태만 확장한다.**
# `C:/Users/...`(git-bash에서 흔한 forward-slash 표기)는 이미 부분 문자열
# "/Users/"를 포함하므로 기존 정규식이 그대로 잡는다(재확인:
# `test_windows_forward_slash_path_already_caught_by_existing_pattern`).
# 진짜 사각지대는 `C:\Users\<name>\...`(순수 백슬래시)뿐이라 그 한 갈래만
# 추가했다 — 이 패키지 어떤 모듈의 docstring에도 실제로 `C:\Users\...` 값이
# 없음을 확인했다(`config.py`의 유일한 `C:\` 언급은 사용자 이름이 없는
# 일반 예시라 파싱된 문자열 상수는 `C:\` 한 글자뿐이라 이 확장으로도
# 오탐하지 않는다 — `test_config_py_windows_root_docstring_example_still_passes`
# 가 이를 회귀 고정한다).
_USER_ABS_PATH_RE = re.compile(
    r"/(?:Users|home)/[^\s\"'<>]+"
    r"|[A-Za-z]:\\Users\\[^\s\"'<>]+"
)


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


def test_windows_backslash_user_path_literal_is_now_flagged() -> None:
    """C-2 확장 회귀 — `C:\\Users\\<name>\\...` 형태(순수 백슬래시)가 잡힌다."""
    assert _USER_ABS_PATH_RE.search(r"C:\Users\moon\workspace\repo") is not None


def test_windows_forward_slash_path_already_caught_by_existing_pattern() -> None:
    """C-2 판단 근거 — `C:/Users/...`(forward-slash, git-bash 표기)는 확장 없이도
    기존 `/Users/` 패턴이 이미 부분 문자열로 잡는다(재확인, 이중 방어 불필요)."""
    assert _USER_ABS_PATH_RE.search("C:/Users/moon/workspace/repo") is not None


def test_config_py_windows_root_docstring_example_still_passes() -> None:
    """C-2 확장이 기존 회귀를 깨지 않는지 확인 — `config.py`의 `_is_root_path`
    docstring이 예시로 언급하는 `C:\\` 하나뿐인 문자열(사용자 이름 없음)은
    확장된 패턴에도 걸리지 않는다(``Users``가 뒤따르지 않으므로)."""
    assert _USER_ABS_PATH_RE.search(r"path가 파일시스템 루트인가(`/`, `C:\` 등)") is None


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
