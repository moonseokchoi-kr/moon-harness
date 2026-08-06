"""tests/test_sdd_archive_state.py — 완료된 사이클 STATE 아카이브 결정적 글루.

`skills/sdd-orchestrator/scripts/archive_state.py`의 인터록과 이동/링크 갱신을 고정한다.
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "skills" / "sdd-orchestrator" / "scripts" / "archive_state.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("archive_state", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


archive_state_mod = _load_module()


STATE_TEMPLATE = """# Orchestrator State

## 메타

- feature: `{feature}`
- 상태: {status}

## 파일 소유권

| 태스크 | 소유 파일 |
|--------|-----------|
| T-1 | `a/b.py` |
"""


def _make_project(
    tmp_path: Path,
    *,
    feature: str = "demo-feature",
    status: str = "**COMPLETED**",
    with_result: bool = True,
    snapshot_status: str | None = "DONE",
    git_init: bool = True,
) -> Path:
    root = tmp_path / "proj"
    (root / "docs" / "sdd" / "result").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "sdd" / "ORCHESTRATOR_STATE.md").write_text(
        STATE_TEMPLATE.format(feature=feature, status=status), encoding="utf-8"
    )
    if with_result:
        (root / "docs" / "sdd" / "result" / f"2026-08-04-{feature}.md").write_text(
            "# result\n", encoding="utf-8"
        )
    if snapshot_status is not None:
        sp = root / ".claude" / "state"
        sp.mkdir(parents=True, exist_ok=True)
        (sp / "kompound-snapshot.json").write_text(
            '{"schema_version": 1, "status": "%s"}' % snapshot_status, encoding="utf-8"
        )
    # hooks 패키지를 import할 수 있어야 파싱 SSOT를 재사용할 수 있다
    for rel in ("hooks", "hooks/lib", "hooks/lib/kompound_snapshot"):
        (root / rel).mkdir(parents=True, exist_ok=True)
    for rel in ("hooks/__init__.py", "hooks/lib/__init__.py"):
        src = REPO / rel
        (root / rel).write_text(src.read_text() if src.exists() else "", encoding="utf-8")
    # kompound_snapshot.runtime_state 는 hooks.lib.self_improve.state_io 에 의존한다
    for pkg_name in ("kompound_snapshot", "self_improve"):
        src_pkg = REPO / "hooks" / "lib" / pkg_name
        dst_pkg = root / "hooks" / "lib" / pkg_name
        dst_pkg.mkdir(parents=True, exist_ok=True)
        for f in src_pkg.glob("*.py"):
            (dst_pkg / f.name).write_text(f.read_text(), encoding="utf-8")
    if git_init:
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", "add", "-A"], cwd=root, check=True)
        subprocess.run(
            ["git", "-c", "user.email=t@t.invalid", "-c", "user.name=t",
             "commit", "-q", "-m", "init"],
            cwd=root, check=True,
        )
    return root


# ── 인터록 ────────────────────────────────────────────────────────────────────


def test_completed_cycle_is_archived(tmp_path: Path) -> None:
    root = _make_project(tmp_path)
    r = archive_state_mod.archive_state(root)
    assert r["ok"] and r["archived"], r
    assert r["target"] == "docs/sdd/archive/2026-08-04-demo-feature-ORCHESTRATOR_STATE.md"
    assert not (root / "docs" / "sdd" / "ORCHESTRATOR_STATE.md").exists()
    assert (root / r["target"]).is_file()


def test_bold_status_is_recognized(tmp_path: Path) -> None:
    """실사용 STATE 는 `- 상태: **COMPLETED** (날짜) — 설명` 형태다."""
    root = _make_project(tmp_path, status="**COMPLETED** (2026-08-04) — 13/13 complete")
    r = archive_state_mod.archive_state(root)
    assert r["archived"], r


def test_executing_cycle_is_not_archived(tmp_path: Path) -> None:
    root = _make_project(tmp_path, status="**EXECUTING**")
    r = archive_state_mod.archive_state(root)
    assert r["ok"] and not r["archived"]
    assert "status_not_completed" in r["reason"]
    assert (root / "docs" / "sdd" / "ORCHESTRATOR_STATE.md").is_file()


def test_missing_result_doc_refuses(tmp_path: Path) -> None:
    """result 문서가 없으면 사이클이 끝났다는 증거가 없다."""
    root = _make_project(tmp_path, with_result=False)
    r = archive_state_mod.archive_state(root)
    assert not r["ok"] and r["reason"] == "result_doc_missing"
    assert (root / "docs" / "sdd" / "ORCHESTRATOR_STATE.md").is_file()


def test_pending_snapshot_refuses(tmp_path: Path) -> None:
    """박제가 미뤄진 상태면 거부한다 — T1 은 STATE 존재를 진입 조건으로 쓰므로
    아카이브하면 재시도가 영구히 오지 않는다(비수렴)."""
    root = _make_project(tmp_path, snapshot_status="CATALOG_PENDING")
    r = archive_state_mod.archive_state(root)
    assert not r["ok"] and "snapshot_incomplete" in r["reason"]
    assert (root / "docs" / "sdd" / "ORCHESTRATOR_STATE.md").is_file()


def test_failed_snapshot_refuses(tmp_path: Path) -> None:
    root = _make_project(tmp_path, snapshot_status="FAILED")
    r = archive_state_mod.archive_state(root)
    assert not r["ok"] and "snapshot_incomplete" in r["reason"]


def test_unconfigured_snapshot_does_not_block(tmp_path: Path) -> None:
    """kompound 미설정 프로젝트는 박제할 게 없으므로 인터록에 걸리지 않는다."""
    root = _make_project(tmp_path, snapshot_status="SKIPPED_UNCONFIGURED")
    r = archive_state_mod.archive_state(root)
    assert r["archived"], r


def test_absent_runtime_state_does_not_block(tmp_path: Path) -> None:
    root = _make_project(tmp_path, snapshot_status=None)
    r = archive_state_mod.archive_state(root)
    assert r["archived"], r


def test_state_absent_is_ok_noop(tmp_path: Path) -> None:
    root = _make_project(tmp_path)
    (root / "docs" / "sdd" / "ORCHESTRATOR_STATE.md").unlink()
    r = archive_state_mod.archive_state(root)
    assert r["ok"] and not r["archived"] and r["reason"] == "state_absent"


# ── 멱등 ──────────────────────────────────────────────────────────────────────


def test_second_run_is_noop_and_does_not_overwrite(tmp_path: Path) -> None:
    root = _make_project(tmp_path)
    first = archive_state_mod.archive_state(root)
    assert first["archived"]
    archived = root / first["target"]
    archived.write_text("SENTINEL\n", encoding="utf-8")

    # STATE 를 다시 만들어 두 번째 실행을 유도한다
    (root / "docs" / "sdd" / "ORCHESTRATOR_STATE.md").write_text(
        STATE_TEMPLATE.format(feature="demo-feature", status="**COMPLETED**"),
        encoding="utf-8",
    )
    second = archive_state_mod.archive_state(root)
    assert second["ok"] and not second["archived"]
    assert second["reason"] == "already_archived"
    assert archived.read_text() == "SENTINEL\n"  # 덮어쓰지 않았다


# ── dry-run ───────────────────────────────────────────────────────────────────


def test_dry_run_moves_nothing(tmp_path: Path) -> None:
    root = _make_project(tmp_path)
    r = archive_state_mod.archive_state(root, dry_run=True)
    assert r["ok"] and not r["archived"] and r["reason"] == "dry_run"
    assert r["target"].endswith("2026-08-04-demo-feature-ORCHESTRATOR_STATE.md")
    assert (root / "docs" / "sdd" / "ORCHESTRATOR_STATE.md").is_file()
    assert not (root / "docs" / "sdd" / "archive").exists()


# ── 링크 갱신 범위 ────────────────────────────────────────────────────────────


def test_sdd_tree_links_are_rewritten(tmp_path: Path) -> None:
    root = _make_project(tmp_path)
    doc = root / "docs" / "sdd" / "result" / "2026-08-04-demo-feature.md"
    doc.write_text(
        "# result\n\n계약은 [STATE](../ORCHESTRATOR_STATE.md) 에 있다.\n"
        "경로: `docs/sdd/ORCHESTRATOR_STATE.md`\n",
        encoding="utf-8",
    )
    r = archive_state_mod.archive_state(root)
    assert r["archived"], r
    text = doc.read_text()
    assert "archive/2026-08-04-demo-feature-ORCHESTRATOR_STATE.md" in text
    assert "](../ORCHESTRATOR_STATE.md)" not in text
    assert "`docs/sdd/archive/2026-08-04-demo-feature-ORCHESTRATOR_STATE.md`" in text
    assert doc.relative_to(root).as_posix() in r["rewritten"]


def test_prose_mention_of_bare_filename_is_untouched(tmp_path: Path) -> None:
    """산문 언급은 경로가 아니라 설명이다 — 건드리면 문장이 깨진다."""
    root = _make_project(tmp_path)
    doc = root / "docs" / "sdd" / "result" / "2026-08-04-demo-feature.md"
    doc.write_text(
        "ORCHESTRATOR_STATE.md 상태를 COMPLETED 로 변경한다.\n", encoding="utf-8"
    )
    r = archive_state_mod.archive_state(root)
    assert r["archived"]
    assert doc.read_text() == "ORCHESTRATOR_STATE.md 상태를 COMPLETED 로 변경한다.\n"
    assert r["rewritten"] == []


def test_harness_convention_docs_are_not_reported(tmp_path: Path) -> None:
    """skills/**·agents/** 는 일반 규약 서술이라 매번 보고하면 신호가 무력해진다."""
    root = _make_project(tmp_path)
    (root / "skills").mkdir(exist_ok=True)
    (root / "skills" / "SKILL.md").write_text(
        "경로: `docs/sdd/ORCHESTRATOR_STATE.md`\n", encoding="utf-8"
    )
    (root / "docs" / "plan.md").write_text(
        "[STATE](sdd/ORCHESTRATOR_STATE.md)\n", encoding="utf-8"
    )
    r = archive_state_mod.archive_state(root)
    assert r["archived"]
    assert "docs/plan.md" in r["external_refs"]
    assert "skills/SKILL.md" not in r["external_refs"]


def test_untracked_state_is_moved_without_git(tmp_path: Path) -> None:
    root = _make_project(tmp_path, git_init=False)
    r = archive_state_mod.archive_state(root)
    assert r["archived"], r
    assert (root / r["target"]).is_file()


# ── CLI ───────────────────────────────────────────────────────────────────────


def test_cli_json_exit_zero_on_noop(tmp_path: Path) -> None:
    root = _make_project(tmp_path, status="**EXECUTING**")
    proc = subprocess.run(
        ["python3", str(SCRIPT), "--project-root", str(root), "--json"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert '"archived": false' in proc.stdout


def test_cli_nonzero_on_interlock_failure(tmp_path: Path) -> None:
    root = _make_project(tmp_path, snapshot_status="CATALOG_PENDING")
    proc = subprocess.run(
        ["python3", str(SCRIPT), "--project-root", str(root), "--json"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 1, proc.stdout
