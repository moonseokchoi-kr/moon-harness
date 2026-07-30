"""tests/test_kompound_snapshot_apply.py — T-10 `apply.py` 통합 테스트.

F6(멱등 적용) + arch §6.3.0((i)/(ii) 2단 분리·커밋 경계)를 `fake_kompound_env`
(tests/conftest.py, T-2) 위에서 검증한다. 전부 `tmp_path` 기반 — 실제
kompound(`/Users/.../marvelous_kompound`)에는 절대 쓰지 않는다.

이 파일이 반드시 커버하는 것(task 문서 "테스트" 절 그대로):

- (i) 성공 + (ii) 성공 → 커밋 2개, `runtime_state` DONE
- (ii)만 실패 → raw 커밋 유지·워킹트리 clean·상태 `CATALOG_PENDING`
- (i) 실패 → `write_failed`, 카탈로그 미시도
- F9 dirty → 박제 시도조차 하지 않음(`precondition_failed`)
- D-impl-1 — F6상 `unchanged`(또는 이번 실행에 포함되지도 않은) 문서가
  registry에 미링크 상태면 `new_docs`에 포함되어 행을 얻는다(자기 치유)
- C-7 — `totals`가 실제로 계산·전달되어 카운트 문장이 갱신된다
- C-6 — `raw_name` 충돌 검출(조용한 덮어쓰기 없음)
- C-4 — 같은 `raw_name`으로 수렴하는 내용 상이 2건 → mtime 최신본 채택
- F6 멱등 — 2회 연속 실행 시 두 번째 카운트 0 + `git status -- raw/` 빈 문자열
- 배타 락 — 이미 잡힌 락이 있으면 시도조차 하지 않고 `busy`로 통과
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from hooks.lib.kompound_snapshot import apply as apply_mod
from hooks.lib.kompound_snapshot import git_state, runtime_state


# ── 테스트 인프라 헬퍼 ───────────────────────────────────────────────────────


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            "git",
            "-c",
            "user.email=fixture@example.invalid",
            "-c",
            "user.name=test-apply",
            "-c",
            "commit.gpgsign=false",
            *args,
        ],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def _git_status_porcelain(repo: Path, *paths: str) -> str:
    result = subprocess.run(
        ["git", "status", "--porcelain", "--", *paths] if paths else ["git", "status", "--porcelain"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _commit_count(repo: Path) -> int:
    result = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return int(result.stdout.strip())


def _make_source_file(
    tmp_path: Path, name: str, content: str, *, mtime: Optional[float] = None
) -> Path:
    """소스 문서 파일을 만들어 경로를 반환한다(스캔 트리를 실제로 흉내내지
    않고 임의 위치에 둬도 apply.py 입장에서는 `record["path"]`만 읽으므로
    무방하다)."""
    src_dir = tmp_path / "sources"
    src_dir.mkdir(parents=True, exist_ok=True)
    path = src_dir / name
    path.write_text(content, encoding="utf-8")
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def _record(path: Path, *, kind: str, repo_dir: str) -> Dict[str, Any]:
    content_bytes = path.read_bytes()
    return {
        "kind": kind,
        "path": str(path),
        "md5": hashlib.md5(content_bytes).hexdigest(),
        "mtime": path.stat().st_mtime,
        "repo_dir": repo_dir,
    }


def _read_state(project_root: Path) -> Dict[str, Any]:
    state_file = runtime_state.state_path_for(project_root)
    return json.loads(state_file.read_text(encoding="utf-8"))


@pytest.fixture()
def project_root(tmp_path: Path) -> Path:
    root = tmp_path / "sdd_project"
    root.mkdir(parents=True, exist_ok=True)
    return root


# ── (i)+(ii) 모두 성공 ──────────────────────────────────────────────────────


def test_apply_full_success_commits_twice_and_records_done(
    fake_kompound_env: Dict[str, Any], project_root: Path
) -> None:
    kompound = fake_kompound_env["kompound"]
    config = fake_kompound_env["config"]
    before_commits = _commit_count(kompound)

    src = _make_source_file(project_root, "2026-07-02-brandnew-spec.md", "# brand new spec\n")
    record = _record(src, kind="spec", repo_dir="acme-widget")

    result = apply_mod.apply(
        kompound,
        [record],
        prefix_map=config["prefix_map"],
        scan_root=config["scan_root"],
        project_root=project_root,
    )

    assert result["busy"] is False
    assert result["precondition_failed"] is False

    raw_stage = result["raw_stage"]
    assert raw_stage["ok"] is True
    assert raw_stage["new"] == ["acme-brandnew-spec.md"]
    assert raw_stage["updated"] == []
    assert raw_stage["committed"] is True
    assert raw_stage["commit"]

    catalog_stage = result["catalog_stage"]
    assert catalog_stage["attempted"] is True
    assert catalog_stage["ok"] is True
    assert catalog_stage["committed"] is True
    assert catalog_stage["commit"]
    assert catalog_stage["failed_gates"] == []

    # 커밋 2개 (raw 1 + catalog 1)
    assert _commit_count(kompound) == before_commits + 2

    # raw 파일이 verbatim으로 실제 존재
    written = (kompound / "raw" / "acme-brandnew-spec.md").read_text(encoding="utf-8")
    assert written == "# brand new spec\n"

    # C-7: 카운트 문장이 6 -> 7로 갱신됨
    registry_text = (kompound / "wiki" / "sdd-spec-registry.md").read_text(encoding="utf-8")
    assert "raw 7개" in registry_text
    assert "raw/acme-brandnew-spec.md" in registry_text

    # 날짜 박힌 과거 스냅샷 서술은 불변(§6.3.3)
    assert "**2026-07-01 재스냅샷**: 3 feature · raw 6개." in registry_text

    # runtime_state: DONE
    state = _read_state(project_root)
    assert state["status"] == "DONE"

    # 배타 락이 정상 해제됨
    assert not (kompound / ".git" / "kompound-snapshot.lock").exists()

    # kompound 워킹트리가 clean
    assert _git_status_porcelain(kompound) == ""


# ── (ii)만 실패 — raw 유지·clean·CATALOG_PENDING ────────────────────────────


def test_apply_catalog_only_failure_keeps_raw_committed_and_clean(
    fake_kompound_env: Dict[str, Any], project_root: Path
) -> None:
    kompound = fake_kompound_env["kompound"]
    config = fake_kompound_env["config"]

    # "## 결정과 근거" 헤딩을 제거해 새 프로젝트 섹션 신설(_create_new_section)이
    # 실패하도록 만든다 — 등록되지 않은 신규 프로젝트라 반드시 신설 경로를
    # 타게 하고, 그 신설에 필요한 앵커를 없애 catalog_unparsed를 유도한다.
    registry_path = kompound / "wiki" / "sdd-spec-registry.md"
    original_text = registry_path.read_text(encoding="utf-8")
    broken_text = original_text.replace("## 결정과 근거", "## Decisions (renamed)")
    registry_path.write_text(broken_text, encoding="utf-8")
    _git("add", "-A", cwd=kompound)
    _git("commit", "-q", "-m", "test setup: break registry anchor", cwd=kompound)

    before_commits = _commit_count(kompound)

    prefix_map = dict(config["prefix_map"])
    prefix_map["delta-service"] = "delta"  # 등록되지 않은 새 프로젝트

    src = _make_source_file(project_root, "2026-07-02-newfeature-spec.md", "# delta spec\n")
    record = _record(src, kind="spec", repo_dir="delta-service")

    result = apply_mod.apply(
        kompound,
        [record],
        prefix_map=prefix_map,
        scan_root=config["scan_root"],
        project_root=project_root,
    )

    raw_stage = result["raw_stage"]
    assert raw_stage["ok"] is True
    assert raw_stage["new"] == ["delta-newfeature-spec.md"]
    assert raw_stage["committed"] is True
    assert raw_stage["commit"]

    catalog_stage = result["catalog_stage"]
    assert catalog_stage["attempted"] is True
    assert catalog_stage["ok"] is False
    assert catalog_stage["committed"] is False
    assert catalog_stage["unparsed"]

    # raw 커밋만 1개 늘어남(카탈로그 커밋 없음)
    assert _commit_count(kompound) == before_commits + 1

    # 워킹트리 clean — 카탈로그 변경이 실제로 롤백/무기록됨
    assert _git_status_porcelain(kompound) == ""

    # registry 파일 내용이 우리가 세팅한 broken_text 그대로(건드리지 않음)
    assert registry_path.read_text(encoding="utf-8") == broken_text

    # raw 파일 자체는 살아있다(문서 보존)
    assert (kompound / "raw" / "delta-newfeature-spec.md").is_file()

    state = _read_state(project_root)
    assert state["status"] == "CATALOG_PENDING"


# ── (i) 실패 — write_failed, 카탈로그 미시도 ────────────────────────────────


def test_apply_raw_write_failure_reports_write_failed_and_skips_catalog(
    fake_kompound_env: Dict[str, Any], project_root: Path
) -> None:
    kompound = fake_kompound_env["kompound"]
    config = fake_kompound_env["config"]
    before_commits = _commit_count(kompound)

    missing_source = project_root / "sources" / "does-not-exist-spec.md"
    record = {
        "kind": "spec",
        "path": str(missing_source),
        "md5": "0" * 32,
        "mtime": 0.0,
        "repo_dir": "acme-widget",
    }

    result = apply_mod.apply(
        kompound,
        [record],
        prefix_map=config["prefix_map"],
        scan_root=config["scan_root"],
        project_root=project_root,
    )

    raw_stage = result["raw_stage"]
    assert raw_stage["ok"] is False
    assert raw_stage["new"] == []
    assert raw_stage["updated"] == []
    assert raw_stage["committed"] is False
    assert raw_stage["commit"] is None
    assert "raw write failed" in raw_stage["error"]

    catalog_stage = result["catalog_stage"]
    assert catalog_stage["attempted"] is False

    # 커밋이 전혀 늘지 않음(전량 롤백 — 애초에 쓰기 자체가 없었음)
    assert _commit_count(kompound) == before_commits
    assert _git_status_porcelain(kompound) == ""

    state = _read_state(project_root)
    assert state["status"] == "PENDING"


# ── F9 dirty — 박제 시도조차 하지 않음 ──────────────────────────────────────


def test_apply_precondition_failed_dirty_skips_everything(
    fake_kompound_env: Dict[str, Any], project_root: Path
) -> None:
    kompound = fake_kompound_env["kompound"]
    config = fake_kompound_env["config"]

    # kompound를 dirty하게 만든다(미커밋 변경).
    (kompound / "raw" / "untracked-scratch.md").write_text("scratch\n", encoding="utf-8")
    assert _git_status_porcelain(kompound) != ""

    before_commits = _commit_count(kompound)

    src = _make_source_file(project_root, "2026-07-02-shouldnotwrite-spec.md", "# should not write\n")
    record = _record(src, kind="spec", repo_dir="acme-widget")

    result = apply_mod.apply(
        kompound,
        [record],
        prefix_map=config["prefix_map"],
        scan_root=config["scan_root"],
        project_root=project_root,
    )

    assert result["precondition_failed"] is True
    assert result["busy"] is False
    assert result["precondition"] is not None
    assert result["precondition"]["dirty"] is True
    assert result["dirty"]  # 파일 목록 non-empty

    raw_stage = result["raw_stage"]
    assert raw_stage["ok"] is False
    assert "precondition_failed" in raw_stage["error"]
    assert result["catalog_stage"]["attempted"] is False

    # 박제 시도조차 하지 않음 — 새 raw 파일이 생기지 않았다.
    assert not (kompound / "raw" / "acme-shouldnotwrite-spec.md").exists()
    assert _commit_count(kompound) == before_commits

    state = _read_state(project_root)
    assert state["status"] == "PENDING"


# ── D-impl-1: 미링크 문서 자기 치유 ──────────────────────────────────────────


def test_apply_self_heals_missing_registry_link_without_being_in_this_runs_records(
    fake_kompound_env: Dict[str, Any], project_root: Path
) -> None:
    kompound = fake_kompound_env["kompound"]
    config = fake_kompound_env["config"]

    # 과거 실행에서 raw만 커밋되고 카탈로그가 실패했던 상황을 직접 시뮬레이션:
    # registry에 링크가 없는 raw 파일을 미리 심고 커밋해 둔다.
    orphan_name = "acme-orphaned-topic-spec.md"
    (kompound / "raw" / orphan_name).write_text("# orphaned topic\n", encoding="utf-8")
    _git("add", "-A", cwd=kompound)
    _git("commit", "-q", "-m", "snapshot(raw): simulate prior cycle orphan", cwd=kompound)

    registry_text_before = (kompound / "wiki" / "sdd-spec-registry.md").read_text(encoding="utf-8")
    assert "acme-orphaned-topic-spec.md" not in registry_text_before

    # 이번 실행의 canonical_records는 비어 있다 — 이 문서를 스캔하지 않았어도
    # 회수돼야 한다(자기 치유).
    result = apply_mod.apply(
        kompound,
        [],
        prefix_map=config["prefix_map"],
        scan_root=config["scan_root"],
        project_root=project_root,
    )

    assert result["raw_stage"]["ok"] is True
    assert result["raw_stage"]["new"] == []
    assert result["raw_stage"]["updated"] == []

    catalog_stage = result["catalog_stage"]
    assert catalog_stage["attempted"] is True
    assert catalog_stage["ok"] is True, catalog_stage

    registry_text_after = (kompound / "wiki" / "sdd-spec-registry.md").read_text(encoding="utf-8")
    assert "acme-orphaned-topic-spec.md" in registry_text_after
    # 총계가 6 -> 7로 갱신됨(고아 문서도 카운트에 편입)
    assert "raw 7개" in registry_text_after


# ── C-6/C-4: raw_name 충돌 → mtime 최신본 채택 + 충돌 보고 ──────────────────


def test_apply_raw_name_conflict_picks_latest_mtime_and_reports_conflict(
    fake_kompound_env: Dict[str, Any], project_root: Path
) -> None:
    kompound = fake_kompound_env["kompound"]
    config = fake_kompound_env["config"]

    older = _make_source_file(
        project_root, "2026-01-01-collide-spec.md", "# older content\n", mtime=1_700_000_000.0
    )
    newer = _make_source_file(
        project_root, "collide-spec.md", "# newer content\n", mtime=1_800_000_000.0
    )

    older_record = _record(older, kind="spec", repo_dir="acme-widget")
    newer_record = _record(newer, kind="spec", repo_dir="acme-widget")

    result = apply_mod.apply(
        kompound,
        [older_record, newer_record],
        prefix_map=config["prefix_map"],
        scan_root=config["scan_root"],
        project_root=project_root,
    )

    raw_stage = result["raw_stage"]
    assert raw_stage["ok"] is True
    assert raw_stage["new"] == ["acme-collide-spec.md"]

    written = (kompound / "raw" / "acme-collide-spec.md").read_text(encoding="utf-8")
    assert written == "# newer content\n"  # C-4: mtime 최신본 채택

    conflicts = result["raw_name_conflicts"]
    assert len(conflicts) == 1
    assert conflicts[0]["raw_name"] == "acme-collide-spec.md"
    assert conflicts[0]["chosen_path"] == str(newer)
    assert conflicts[0]["discarded"] == [{"path": str(older), "mtime": older_record["mtime"]}]


# ── F6 멱등 — 2회 연속 실행 ──────────────────────────────────────────────────


def test_apply_idempotent_second_run_is_zero_and_git_clean(
    fake_kompound_env: Dict[str, Any], project_root: Path
) -> None:
    kompound = fake_kompound_env["kompound"]
    config = fake_kompound_env["config"]

    src = _make_source_file(project_root, "2026-07-02-repeatable-spec.md", "# repeatable spec\n")
    record = _record(src, kind="spec", repo_dir="acme-widget")

    first = apply_mod.apply(
        kompound, [record], prefix_map=config["prefix_map"], scan_root=config["scan_root"]
    )
    assert first["raw_stage"]["ok"] is True
    assert first["raw_stage"]["new"] == ["acme-repeatable-spec.md"]
    assert first["catalog_stage"]["ok"] is True

    commits_after_first = _commit_count(kompound)

    second = apply_mod.apply(
        kompound, [record], prefix_map=config["prefix_map"], scan_root=config["scan_root"]
    )

    raw_stage = second["raw_stage"]
    assert raw_stage["ok"] is True
    assert raw_stage["new"] == []
    assert raw_stage["updated"] == []
    assert raw_stage["unchanged"] == 1
    assert raw_stage["committed"] is False  # no_changes

    catalog_stage = second["catalog_stage"]
    assert catalog_stage["attempted"] is False  # 이미 링크되어 있어 스킵

    assert _commit_count(kompound) == commits_after_first
    assert _git_status_porcelain(kompound, "raw") == ""
    assert _git_status_porcelain(kompound) == ""


# ── 배타 락 — 이미 잡혀 있으면 시도조차 하지 않고 busy ──────────────────────


def test_apply_busy_when_lock_already_held(fake_kompound_env: Dict[str, Any]) -> None:
    kompound = fake_kompound_env["kompound"]
    config = fake_kompound_env["config"]

    lock_result = git_state.acquire_lock(kompound)
    assert lock_result["acquired"] is True
    try:
        before_commits = _commit_count(kompound)
        result = apply_mod.apply(
            kompound, [], prefix_map=config["prefix_map"], scan_root=config["scan_root"]
        )
        assert result["busy"] is True
        assert result["raw_stage"]["ok"] is False
        assert "busy" in result["raw_stage"]["error"]
        assert result["catalog_stage"]["attempted"] is False
        assert _commit_count(kompound) == before_commits
    finally:
        git_state.release_lock(kompound)
