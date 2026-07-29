"""tests/test_kompound_snapshot_scan.py — T-4 (F3 스캔 + repo_dir 도출) 검증.

arch: docs/sdd/design/arch/2026-07-29-kompound-snapshot-hook.md §5.4.1(스캔)
· §5.4.2(repo_dir 도출)
spec: docs/sdd/spec/2026-07-29-kompound-snapshot-hook.md F3

`fake_kompound_env`(tests/conftest.py, T-2)와 이 파일 전용 합성 tmp_path 트리를
함께 쓴다 — 실제 워크스페이스·실제 kompound 스캔은 절대 하지 않는다.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

from hooks.lib.kompound_snapshot.scan import (
    DEFAULT_MAX_ANCHOR_DEPTH,
    KINDS,
    SKIP_DIRS,
    SKIP_NAMES,
    derive_repo_dir,
    find_anchors,
    scan,
)


def _write(path: Path, text: str = "# doc\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ── 상수 바이트 일치 (arch §5.4.1) ───────────────────────────────────────────


def test_constants_match_arch_exactly() -> None:
    assert KINDS == {
        "spec": "spec",
        "specs": "spec",
        "arch": "arch",
        "ui": "ui",
        "api": "api",
        "result": "result",
        "development": "arch",
        "context": "context",
    }
    assert SKIP_DIRS == {".git", "node_modules", "build", "ExternLib", ".venv", "venv"}
    assert SKIP_NAMES == ("ORCHESTRATOR_STATE", "HANDOFF", "-GUIDE", "DESIGN.md", "test-guide-")
    assert DEFAULT_MAX_ANCHOR_DEPTH == 5


# ── 포함: 8종 디렉토리 각각 (spec/specs/design-arch/design-ui/design-api/context/result/development) ──


def test_scan_includes_all_kind_directories(tmp_path: Path) -> None:
    repo = tmp_path / "acme-widget"
    sdd = repo / "docs" / "sdd"

    cases = {
        sdd / "spec" / "a-spec.md": "spec",
        sdd / "specs" / "b-spec.md": "spec",
        sdd / "design" / "arch" / "c-arch.md": "arch",
        sdd / "design" / "ui" / "d-ui.md": "ui",
        sdd / "design" / "api" / "e-api.md": "api",
        sdd / "context" / "f-context.md": "context",
        sdd / "result" / "g-result.md": "result",
        sdd / "development" / "h-dev.md": "arch",
    }
    for path in cases:
        _write(path)

    result = scan([tmp_path])
    by_path = {r["path"]: r["kind"] for r in result["records"]}

    for path, expected_kind in cases.items():
        assert str(path) in by_path, f"missing record for {path}"
        assert by_path[str(path)] == expected_kind

    assert result["errors"] == []
    assert result["anchors"] >= 1


def test_scan_also_matches_docs_sdd_capitalized(tmp_path: Path) -> None:
    repo = tmp_path / "some-repo"
    _write(repo / "Docs" / "sdd" / "spec" / "x-spec.md")

    result = scan([tmp_path])
    paths = [r["path"] for r in result["records"]]
    assert str(repo / "Docs" / "sdd" / "spec" / "x-spec.md") in paths


# ── 제외: task/ tasks/ HANDOFF.md ORCHESTRATOR_STATE.md -GUIDE.md DESIGN.md test-guide-*.md ──


def test_scan_excludes_task_and_special_names(tmp_path: Path) -> None:
    repo = tmp_path / "acme-widget"
    sdd = repo / "docs" / "sdd"

    excluded = [
        sdd / "spec" / "task" / "hidden-spec.md",
        sdd / "task" / "spec" / "hidden2-spec.md",
        sdd / "tasks" / "spec" / "hidden3-spec.md",
        sdd / "spec" / "ORCHESTRATOR_STATE.md",
        sdd / "spec" / "ORCHESTRATOR_STATE_2.md",
        sdd / "spec" / "HANDOFF.md",
        sdd / "spec" / "some-GUIDE.md",
        sdd / "spec" / "DESIGN.md",
        sdd / "spec" / "test-guide-foo.md",
    ]
    for path in excluded:
        _write(path)

    # 포함되어야 할 정상 문서 하나도 같이 심어 스캔 자체가 동작함을 확인한다.
    included = sdd / "spec" / "normal-spec.md"
    _write(included)

    result = scan([tmp_path])
    paths = {r["path"] for r in result["records"]}

    for path in excluded:
        assert str(path) not in paths, f"excluded path leaked into scan results: {path}"
    assert str(included) in paths


def test_scan_excludes_non_md_files(tmp_path: Path) -> None:
    repo = tmp_path / "acme-widget"
    sdd = repo / "docs" / "sdd"
    _write(sdd / "spec" / "notes.txt", "not markdown\n")

    result = scan([tmp_path])
    assert result["records"] == []


# ── 워크트리 문서 포함 (fake_kompound_env 재사용) ────────────────────────────


def test_scan_includes_worktree_documents(fake_kompound_env: Dict[str, Any]) -> None:
    workspace = fake_kompound_env["workspace"]
    result = scan([workspace])
    paths = [r["path"] for r in result["records"]]
    assert any("worktrees" in p and p.endswith("-spec.md") for p in paths), (
        "워크트리 전용 문서가 스캔 결과에 없음"
    )


# ── SKIP_DIRS 하위 미순회 ────────────────────────────────────────────────────


def test_scan_does_not_descend_into_skip_dirs(tmp_path: Path) -> None:
    repo = tmp_path / "acme-widget"
    sdd = repo / "docs" / "sdd"
    # SKIP_DIRS 하위에 유효한 docs/sdd/spec 구조를 심어도 잡히면 안 된다.
    _write(sdd / "spec" / "node_modules" / "docs" / "sdd" / "spec" / "buried-spec.md")
    _write(repo / "node_modules" / "docs" / "sdd" / "spec" / "buried2-spec.md")
    _write(repo / "build" / "docs" / "sdd" / "spec" / "buried3-spec.md")

    # 정상 문서도 하나 둔다.
    normal = sdd / "spec" / "normal-spec.md"
    _write(normal)

    result = scan([tmp_path])
    paths = {r["path"] for r in result["records"]}
    assert str(normal) in paths
    assert not any("node_modules" in p or "/build/" in p for p in paths)


# ── errors[] 부분 실패 ───────────────────────────────────────────────────────


def test_scan_accumulates_errors_on_permission_failure(tmp_path: Path) -> None:
    repo = tmp_path / "acme-widget"
    sdd = repo / "docs" / "sdd"
    broken_dir = sdd / "spec" / "broken"
    _write(broken_dir / "unreachable-spec.md")
    ok = sdd / "spec" / "ok-spec.md"
    _write(ok)

    real_scandir = os.scandir

    def _flaky_scandir(path: Any = "."):
        if str(path) == str(broken_dir):
            raise PermissionError(f"simulated permission error: {path}")
        return real_scandir(path)

    with patch("os.scandir", side_effect=_flaky_scandir):
        result = scan([tmp_path])

    assert result["errors"], "권한 오류가 errors[]에 누적되지 않음"
    assert any(str(broken_dir) == e["path"] for e in result["errors"])
    # 스캔은 계속되어 다른 정상 문서는 여전히 수집된다(부분 실패, 예외로 죽지 않음).
    paths = {r["path"] for r in result["records"]}
    assert str(ok) in paths


def test_scan_reports_anchors_count(tmp_path: Path) -> None:
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    _write(repo_a / "docs" / "sdd" / "spec" / "a-spec.md")
    _write(repo_b / "docs" / "sdd" / "spec" / "b-spec.md")

    result = scan([tmp_path])
    assert result["anchors"] == 2


def test_find_anchors_respects_max_depth(tmp_path: Path) -> None:
    # depth 계산: tmp_path(0)/l1(1)/l2(2)/l3(3)/docs(4)/sdd(anchor, docs 스캔 중 발견).
    # "docs"에 도달하려면 l2->l3 push 조건(3<=max_depth)이 성립해야 한다.
    # max_anchor_depth=2면 l3가 push되지 않아 앵커에 도달하지 못한다
    # (worktrees 세그먼트가 없으므로 깊이 제한이 그대로 적용됨).
    deep_anchor = tmp_path / "l1" / "l2" / "l3" / "docs" / "sdd"
    _write(deep_anchor / "spec" / "deep-spec.md")

    anchors = find_anchors(tmp_path, max_anchor_depth=2)
    assert anchors == []

    anchors_full = find_anchors(tmp_path, max_anchor_depth=DEFAULT_MAX_ANCHOR_DEPTH)
    assert len(anchors_full) == 1


def test_find_anchors_ignores_depth_limit_under_worktrees(tmp_path: Path) -> None:
    # worktrees 세그먼트가 있으면 깊이 제한이 적용되지 않는다(arch §5.4.1 절차1).
    deep_wt_anchor = (
        tmp_path / "repo" / "worktrees" / "wt1" / "l3" / "l4" / "l5" / "l6" / "docs" / "sdd"
    )
    _write(deep_wt_anchor / "spec" / "wt-deep-spec.md")

    anchors = find_anchors(tmp_path, max_anchor_depth=1)
    assert len(anchors) == 1
    assert anchors[0] == deep_wt_anchor


# ── repo_dir 도출 (arch §5.4.2) ──────────────────────────────────────────────


def test_derive_repo_dir_worktrees_segment(tmp_path: Path) -> None:
    repo = tmp_path / "Marvelous_feature"
    anchor = repo / "worktrees" / "my-wt" / "docs" / "sdd"
    anchor.mkdir(parents=True)

    result = derive_repo_dir(anchor, scope_root=tmp_path)
    assert result == repo


def test_derive_repo_dir_git_directory_ancestor(tmp_path: Path) -> None:
    repo = tmp_path / "moon-harness"
    (repo / ".git").mkdir(parents=True)
    anchor = repo / "docs" / "sdd"
    anchor.mkdir(parents=True)

    result = derive_repo_dir(anchor, scope_root=tmp_path)
    assert result == repo


def test_derive_repo_dir_gitdir_file_parsing(tmp_path: Path) -> None:
    main_repo = tmp_path / "Marvelous"
    main_repo.mkdir(parents=True)
    linked_wt = tmp_path / "external-wt-location"
    anchor = linked_wt / "docs" / "sdd"
    anchor.mkdir(parents=True)

    git_file = linked_wt / ".git"
    gitdir_target = main_repo / ".git" / "worktrees" / "external-wt-location"
    git_file.write_text(f"gitdir: {gitdir_target}\n", encoding="utf-8")

    result = derive_repo_dir(anchor, scope_root=tmp_path)
    assert result == main_repo


def test_derive_repo_dir_nested_repo_git_owner_clofab_case(tmp_path: Path) -> None:
    # CLOFab_Web/clofab 유형 — .git 소유자 규칙만으로 CLOFab_Web에 도달해야 한다.
    outer = tmp_path / "CLOFab_Web"
    (outer / ".git").mkdir(parents=True)
    inner = outer / "clofab"
    anchor = inner / "docs" / "sdd"
    anchor.mkdir(parents=True)

    result = derive_repo_dir(anchor, scope_root=tmp_path)
    assert result == outer


def test_derive_repo_dir_falls_back_to_scope_root(tmp_path: Path) -> None:
    repo = tmp_path / "plain-dir-no-git"
    anchor = repo / "docs" / "sdd"
    anchor.mkdir(parents=True)

    result = derive_repo_dir(anchor, scope_root=tmp_path)
    assert result == tmp_path


def test_derive_repo_dir_gitdir_parse_failure_falls_back(tmp_path: Path) -> None:
    repo = tmp_path / "broken-linked-wt"
    anchor = repo / "docs" / "sdd"
    anchor.mkdir(parents=True)
    (repo / ".git").write_text("not a gitdir line at all\n", encoding="utf-8")

    result = derive_repo_dir(anchor, scope_root=tmp_path)
    assert result == tmp_path


def test_scan_records_use_derived_repo_dir(tmp_path: Path) -> None:
    repo = tmp_path / "moon-harness"
    (repo / ".git").mkdir(parents=True)
    _write(repo / "docs" / "sdd" / "spec" / "x-spec.md")

    result = scan([tmp_path])
    assert len(result["records"]) == 1
    assert result["records"][0]["repo_dir"] == str(repo)
