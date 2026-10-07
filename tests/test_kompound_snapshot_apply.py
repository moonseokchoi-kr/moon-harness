"""tests/test_kompound_snapshot_apply.py — T-10 `apply.py` 통합 테스트.

F6(멱등 적용) + arch §6.3.0((i)/(ii) 2단 분리·커밋 경계)를 `fake_kompound_env`
(tests/conftest.py, T-2) 위에서 검증한다. 전부 `tmp_path` 기반 — 실제
kompound 볼트(`/Users/.../moon_kompound`)에는 절대 쓰지 않는다.

2026-10-07 v2 볼트 이관으로 raw 위치·형식(``10. Raw Sources/17. Specs/<Domain>/
YYYY-MM-DD-<slug>.md``, raw-source frontmatter + ``## Original Content``),
registry 링크(wikilink), log 형식(``## [date] snapshot | ...`` 엔트리), 게이트
(3)(flat → raw_layout)이 바뀌었다 — 이 파일의 기대값도 그에 맞춰 갱신했다
(로직 계약 — 2단 커밋·롤백·멱등·자기치유 — 은 그대로).

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
- F6 멱등 — 2회 연속 실행 시 두 번째 카운트 0 + `git status -- "10. Raw Sources"` 빈 문자열
- 배타 락 — 이미 잡힌 락이 있으면 시도조차 하지 않고 `busy`로 통과

it.2 추가(리뷰어 [P1] #1 + compliance #2/#3, `.harness/LEARNING.md` 2026-07-30
"T-10-apply" 엔트리 반영 — 로직 변경 없음, 테스트만 추가):

- (ii) 실패를 **쓰기 이후**(post-write) 지점에서 유도해 저널 롤백 코드
  자체가 실행됨을 증명(pre-write 조기 리턴이 아님을 `unparsed is None` +
  `failed_gates` 비어있지 않음으로 구분)
- (ii) 실패 → 원인 제거 → 재실행 시 `CATALOG_PENDING` → `DONE`으로 실제
  전이(2회 이상 `apply()` 호출을 잇는 통합 시나리오, D-impl-1 자기치유가
  실제로 이어붙는 증거)
- `wiki/log.md`에 append된 정확한 한 줄을 `wiki_log.build_snapshot_log_line()`
  으로 독립 재구성해 바이트 단위로 대조(다중 raw 커밋 열거·재시도 횟수·
  append-only 보존 포함)
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import patch

import pytest

from hooks.lib.kompound_snapshot import apply as apply_mod
from hooks.lib.kompound_snapshot import git_state, runtime_state, vault, verify, wiki_log

# v2 볼트 경로(테스트 독립 재정의 — vault 상수를 그대로 쓰지 않고 문자열로 고정해
# 레이아웃 계약 자체를 검증한다).
_RAW_ROOT = "10. Raw Sources"
_SPECS_AI = ("10. Raw Sources", "17. Specs", "AI Harness")
_REGISTRY = ("20. Wiki", "24. Maps", "SDD Spec Registry.md")
_TODAY = "2026-07-02"


@pytest.fixture(autouse=True)
def _fixed_today(monkeypatch: pytest.MonkeyPatch) -> None:
    """박제 날짜를 고정해 신규 raw 파일명(`<날짜>-<slug>.md`)을 결정적으로 만든다."""
    monkeypatch.setattr(apply_mod, "_today", lambda: _TODAY)


def _registry_path(kompound: Path) -> Path:
    return kompound.joinpath(*_REGISTRY)


def _new_raw_path(kompound: Path, slug: str, parts=_SPECS_AI) -> Path:
    return kompound.joinpath(*parts) / f"{_TODAY}-{slug}.md"


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


_STRAY_REL = ("10. Raw Sources", "17. Specs", "2026-07-01-acme-stray-layout-spec.md")


def _inject_bad_raw_subdir(kompound: Path) -> None:
    """스냅샷 raw 1건을 도메인 폴더 없이 유형 폴더 바로 아래에 심고 커밋한다 —
    `check_raw_layout` 게이트가 **항상** 실패하도록 만드는 사전 조건(v1의 "raw/
    서브디렉토리" 위반의 v2판). 우리가 새로 추가하는 문서와 무관하게 실패시키므로,
    registry write가 정상 완료된 **이후**에 게이트가 걸린다 — pre-write
    `catalog_unparsed` 조기 리턴과 구분되는 지점."""
    stray = kompound.joinpath(*_STRAY_REL)
    stray.parent.mkdir(parents=True, exist_ok=True)
    stray.write_text("---\ntype: raw-source\n---\n\n# stray\n\n## Original Content\n\nstray\n", encoding="utf-8")
    _git("add", "-A", cwd=kompound)
    _git("commit", "-q", "-m", "test setup: inject raw layout violation", cwd=kompound)


def _remove_bad_raw_subdir(kompound: Path) -> None:
    """`_inject_bad_raw_subdir`이 심은 위반을 제거하고 커밋한다(사람이 레이아웃
    위반을 고쳤다고 가정하는 재시도 시나리오의 전제)."""
    kompound.joinpath(*_STRAY_REL).unlink()
    _git("add", "-A", cwd=kompound)
    _git("commit", "-q", "-m", "test setup: remove raw layout violation", cwd=kompound)


def _raw_commit_shas_in_order(kompound: Path) -> List[str]:
    """kompound git 이력에서 `snapshot(raw):` 커밋들의 abbreviated sha를
    시간순(오래된 것 → 최신)으로 반환한다. `apply.py`의
    `_find_uncataloged_raw_commits`와 **독립적으로**(테스트가 모듈 내부
    구현을 그대로 재사용하지 않고 직접 재조회) 검증하기 위함."""
    proc = subprocess.run(
        ["git", "log", "--format=%h\x01%as\x01%s"],
        cwd=kompound,
        check=True,
        capture_output=True,
        text=True,
    )
    shas: List[str] = []
    for line in proc.stdout.splitlines():
        sha, _date, subject = line.split("\x01")
        if subject.startswith("snapshot(raw):"):
            shas.append(sha)
    shas.reverse()
    return shas


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

    src = _make_source_file(
        project_root, "2026-07-02-brandnew-spec.md", "# brand new spec\n\n## 개요\n- body line\n"
    )
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
    assert raw_stage["new"] == [f"{_TODAY}-acme-brandnew-spec.md"]
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

    # raw 파일이 v2 raw-source 형식으로 실제 존재 — 본문은 verbatim
    written = _new_raw_path(kompound, "acme-brandnew-spec").read_text(encoding="utf-8")
    assert written.startswith("---\ntype: raw-source\n")
    assert 'domain: "AI Harness"' in written  # acme → 미등록 프리픽스 → 폴백 도메인
    assert f"date created: {_TODAY}" in written
    assert 'description: "SDD spec snapshot of acme brandnew."' in written
    assert "\n# brand new spec\n" in written
    assert "> [!info] Source" in written
    assert vault.extract_original_content(written) == "## 개요\n- body line"
    assert "\n## Metadata\n" in written

    # C-7: 카운트 문장이 6 -> 7로 갱신됨 + wikilink 셀
    registry_text = _registry_path(kompound).read_text(encoding="utf-8")
    assert "raw 7개" in registry_text
    assert f"[[{_TODAY}-acme-brandnew-spec\\|✓]]" in registry_text
    # frontmatter source 목록 동기화 + date modified 갱신
    assert f'  - "[[{_TODAY}-acme-brandnew-spec]]"' in registry_text
    assert f"date modified: {_TODAY}" in registry_text

    # index.md 훅 줄 + Recent Ingests prepend, log.md 엔트리 append
    index_text = (kompound / "index.md").read_text(encoding="utf-8")
    assert "- [[SDD Spec Registry]] — SDD spec/design/result 카탈로그. 4 feature · raw 7개." in index_text
    assert f"- {_TODAY} [snapshot] SDD 스냅샷 1건 카탈로그 편입 (acme)" in index_text
    log_text = (kompound / "log.md").read_text(encoding="utf-8")
    assert f"\n## [{_TODAY}] snapshot | SDD 스냅샷 1건 카탈로그 편입 (acme)\n\n- <1 raw> — raw 커밋 " in log_text

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
    registry_path = _registry_path(kompound)
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
    assert raw_stage["new"] == [f"{_TODAY}-delta-newfeature-spec.md"]
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
    assert _new_raw_path(kompound, "delta-newfeature-spec").is_file()

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
    (kompound / _RAW_ROOT / "untracked-scratch.md").write_text("scratch\n", encoding="utf-8")
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
    assert not _new_raw_path(kompound, "acme-shouldnotwrite-spec").exists()
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
    orphan_name = "2026-07-01-acme-orphaned-topic-spec.md"
    (kompound.joinpath(*_SPECS_AI) / orphan_name).write_text("# orphaned topic\n", encoding="utf-8")
    _git("add", "-A", cwd=kompound)
    _git("commit", "-q", "-m", "snapshot(raw): simulate prior cycle orphan", cwd=kompound)

    registry_text_before = _registry_path(kompound).read_text(encoding="utf-8")
    assert "acme-orphaned-topic-spec" not in registry_text_before

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

    registry_text_after = _registry_path(kompound).read_text(encoding="utf-8")
    assert "[[2026-07-01-acme-orphaned-topic-spec\\|✓]]" in registry_text_after
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
    assert raw_stage["new"] == [f"{_TODAY}-acme-collide-spec.md"]

    written = _new_raw_path(kompound, "acme-collide-spec").read_text(encoding="utf-8")
    assert "\n# newer content\n" in written  # C-4: mtime 최신본 채택
    assert "older content" not in written

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
    assert first["raw_stage"]["new"] == [f"{_TODAY}-acme-repeatable-spec.md"]
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
    assert _git_status_porcelain(kompound, _RAW_ROOT) == ""
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


# ── [P1] #1 (리뷰어) — post-write 게이트 실패 → 저널 롤백 코드 실행 증명 ────


def test_apply_catalog_gate_failure_after_write_rolls_back_journal(
    fake_kompound_env: Dict[str, Any], project_root: Path
) -> None:
    """`check_raw_layout`이 **registry/index/log write 이후** 실패하도록
    만든다(도메인 폴더 밖 스냅샷 raw를 사전에 커밋해 둠 — 우리 문서와
    무관한 구조적 위반이므로 registry 텍스트 변환 자체는 정상 성공한 뒤에야
    걸린다). `apply.py:_run_catalog_stage`의 실제 `journal = [...]` 생성 →
    3파일 write → `run_gates` → 실패 → `_rollback_journal` 경로를 실행시켜
    3파일이 **바이트 단위로 완전 복원**됨을 확인한다.

    pre-write 조기 리턴(`test_apply_catalog_only_failure_keeps_raw_committed_and_clean`)
    과 구분하는 결정적 증거: 그 케이스는 `catalog_stage["unparsed"]`가
    채워지고 `failed_gates`가 항상 빈 리스트다. 여기서는 반대로
    `unparsed is None`이고 `failed_gates`가 채워진다 — `_catalog_gate_failure`
    분기(쓰기+게이트 실행 이후에만 도달 가능)에 실제로 진입했다는 뜻이다.
    """
    kompound = fake_kompound_env["kompound"]
    config = fake_kompound_env["config"]

    _inject_bad_raw_subdir(kompound)

    registry_path = _registry_path(kompound)
    index_path = kompound / "index.md"
    log_path = kompound / "log.md"
    registry_bytes_before = registry_path.read_bytes()
    index_bytes_before = index_path.read_bytes()
    log_bytes_before = log_path.read_bytes()

    before_commits = _commit_count(kompound)

    src = _make_source_file(project_root, "2026-07-03-afterwrite-spec.md", "# after write gate failure\n")
    record = _record(src, kind="spec", repo_dir="acme-widget")

    result = apply_mod.apply(
        kompound,
        [record],
        prefix_map=config["prefix_map"],
        scan_root=config["scan_root"],
        project_root=project_root,
    )

    raw_stage = result["raw_stage"]
    assert raw_stage["ok"] is True
    assert raw_stage["new"] == [f"{_TODAY}-acme-afterwrite-spec.md"]
    assert raw_stage["committed"] is True

    catalog_stage = result["catalog_stage"]
    assert catalog_stage["attempted"] is True
    assert catalog_stage["ok"] is False
    # pre-write catalog_unparsed 분기와 구분되는 결정적 증거(모듈 docstring 참조).
    assert catalog_stage["unparsed"] is None
    assert "raw_layout" in catalog_stage["failed_gates"]
    assert catalog_stage["committed"] is False
    assert catalog_stage["commit"] is None

    # 저널 롤백 — 3파일이 실패 전 바이트와 완전히 동일(단정 대상은 dict가
    # 아니라 실제 디스크 바이트).
    assert registry_path.read_bytes() == registry_bytes_before
    assert index_path.read_bytes() == index_bytes_before
    assert log_path.read_bytes() == log_bytes_before

    # 커밋이 raw 1개만 증가(카탈로그 커밋 없음)
    assert _commit_count(kompound) == before_commits + 1

    assert _git_status_porcelain(kompound, "20. Wiki", "index.md", "log.md") == ""
    assert _git_status_porcelain(kompound) == ""

    state = _read_state(project_root)
    assert state["status"] == "CATALOG_PENDING"


# ── compliance #2/#3 — 재시도 이어짐(원인 제거 후 성공) + log.md 내용 검증 ──


def test_apply_retry_after_fixing_catalog_cause_succeeds_and_logs_multiple_raw_commits(
    fake_kompound_env: Dict[str, Any], project_root: Path
) -> None:
    """완료조건 #21("(ii) 실패 후 다음 실행에서 (i)은 unchanged 무동작이고
    (ii)만 재시도됨")을 **실제 2회 이상의 apply() 호출**로 검증하고,
    동시에 F7 "배치 1건 = 로그 1줄"과 §6.3.0 N-2(다중 raw 커밋 열거)를
    `wiki/log.md`의 실제 바이트로 확인한다.

    시나리오: `_inject_bad_raw_subdir`로 flat_structure 위반을 심어둔 채
    서로 다른 문서 2건을 각각 별도 호출로 raw 커밋만 성공시키고(카탈로그는
    매번 실패 → `CATALOG_PENDING` 유지), 위반을 제거한 뒤 3차 호출에서
    두 문서가 **한 번에** 카탈로그로 회수되며 `DONE`으로 전이하는지 확인한다.
    """
    kompound = fake_kompound_env["kompound"]
    config = fake_kompound_env["config"]
    registry_path = _registry_path(kompound)
    log_path = kompound / "log.md"

    log_lines_before = log_path.read_text(encoding="utf-8").splitlines()

    _inject_bad_raw_subdir(kompound)

    # 1차: docA 신규 → raw 커밋 성공, catalog 실패(CATALOG_PENDING).
    src_a = _make_source_file(project_root, "2026-07-03-retry-a-spec.md", "# retry doc A\n")
    record_a = _record(src_a, kind="spec", repo_dir="acme-widget")
    result1 = apply_mod.apply(
        kompound,
        [record_a],
        prefix_map=config["prefix_map"],
        scan_root=config["scan_root"],
        project_root=project_root,
    )
    assert result1["raw_stage"]["ok"] is True
    assert result1["raw_stage"]["new"] == [f"{_TODAY}-acme-retry-a-spec.md"]
    assert result1["raw_stage"]["committed"] is True
    assert result1["catalog_stage"]["ok"] is False
    assert _read_state(project_root)["status"] == "CATALOG_PENDING"

    # 2차: docB 신규(다른 문서) → raw 커밋 성공, catalog 여전히 실패.
    src_b = _make_source_file(project_root, "2026-07-03-retry-b-spec.md", "# retry doc B\n")
    record_b = _record(src_b, kind="spec", repo_dir="acme-widget")
    result2 = apply_mod.apply(
        kompound,
        [record_b],
        prefix_map=config["prefix_map"],
        scan_root=config["scan_root"],
        project_root=project_root,
    )
    assert result2["raw_stage"]["ok"] is True
    assert result2["raw_stage"]["new"] == [f"{_TODAY}-acme-retry-b-spec.md"]
    assert result2["raw_stage"]["committed"] is True
    assert result2["catalog_stage"]["ok"] is False
    assert _read_state(project_root)["status"] == "CATALOG_PENDING"

    # 이 시점까지 raw만 2개 커밋됐고 카탈로그 커밋은 아직 하나도 없다 —
    # 다음 apply() 호출이 만들 log.md 줄이 이 두 raw 커밋을 전부 열거해야 한다.
    raw_shas_before_recovery = _raw_commit_shas_in_order(kompound)
    assert len(raw_shas_before_recovery) == 2

    # 원인 제거(사람이 flat_structure 위반을 고쳤다고 가정) — clean 유지 위해 커밋.
    _remove_bad_raw_subdir(kompound)

    commits_before_retry = _commit_count(kompound)

    # 3차: 이번 호출은 두 문서를 다시 스캔하지 않아도(canonical_records=[])
    # D-impl-1 차집합이 미링크 상태(docA·docB 둘 다)를 회수한다 — F6
    # unchanged 재현이 아니라 자기치유 경로 자체를 검증하는 것이 이 테스트의
    # 목적이다(F6 unchanged 재현은 별도 idempotent 테스트가 이미 커버).
    result3 = apply_mod.apply(
        kompound,
        [],
        prefix_map=config["prefix_map"],
        scan_root=config["scan_root"],
        project_root=project_root,
    )

    assert result3["raw_stage"]["ok"] is True
    assert result3["raw_stage"]["new"] == []
    assert result3["raw_stage"]["updated"] == []
    assert result3["raw_stage"]["committed"] is False  # no_changes — 이번 호출은 raw 커밋 없음

    catalog_stage3 = result3["catalog_stage"]
    assert catalog_stage3["attempted"] is True
    assert catalog_stage3["ok"] is True
    assert catalog_stage3["committed"] is True
    assert catalog_stage3["commit"]

    # raw 커밋 없이 카탈로그 커밋 1개만 증가(재시도가 실제로 (ii)만 이어붙음).
    assert _commit_count(kompound) == commits_before_retry + 1

    registry_text = registry_path.read_text(encoding="utf-8")
    assert f"[[{_TODAY}-acme-retry-a-spec\\|✓]]" in registry_text
    assert f"[[{_TODAY}-acme-retry-b-spec\\|✓]]" in registry_text

    # CATALOG_PENDING -> DONE 실제 전이.
    assert _read_state(project_root)["status"] == "DONE"

    # F7 "배치 1건 = 로그 엔트리 1개" — 기존 내용은 재작성/정렬/중복제거 없이
    # append-only로 보존되고, v2 엔트리 블록(빈 줄 + `## [date] snapshot | ...`
    # + 빈 줄 + `- <요약>`) 정확히 하나만 새로 추가된다.
    log_text_after = log_path.read_text(encoding="utf-8")
    log_lines_after = log_text_after.splitlines()
    assert log_lines_after[: len(log_lines_before)] == log_lines_before
    new_lines = log_lines_after[len(log_lines_before) :]
    assert new_lines[0] == ""
    assert new_lines[1] == f"## [{_TODAY}] snapshot | SDD 스냅샷 2건 카탈로그 편입 (acme)"
    assert new_lines[2] == ""
    assert len(new_lines) == 4
    new_line = new_lines[3]

    # 두 시점 표기 형식·다중 raw 커밋 열거·재시도 횟수를
    # `wiki_log.build_snapshot_log_line()`으로 독립 재구성해 바이트 단위로
    # 대조한다(모듈 내부 함수를 재사용하지 않고 테스트가 직접 재현). raw 커밋
    # 날짜는 git author date(로컬)이다.
    commit_day = datetime.now().strftime("%Y-%m-%d")
    raw_commits: List[Tuple[str, str]] = [(sha, commit_day) for sha in raw_shas_before_recovery]
    expected_summary = wiki_log.build_snapshot_log_line(
        date=_TODAY,
        total_raw=2,
        raw_commits=raw_commits,
        catalog_commit=("HEAD", _TODAY),
        retries=len(raw_commits) - 1,
        with_prefix=False,
    )
    assert new_line == f"- {expected_summary}"
    assert "재시도 1회" in new_line
    for sha in raw_shas_before_recovery:
        assert sha in new_line


# ── 완료조건 #23 — 박제 0건 시 F8 게이트 함수 미호출을 mock call_count로 단정 ──


def test_apply_skips_gate_functions_when_nothing_new_to_catalog(
    fake_kompound_env: Dict[str, Any], project_root: Path
) -> None:
    """task 문서가 명시한 검증 형태 그대로: 박제(카탈로그 갱신 대상)가 0건이면
    `verify.run_gates`가 **호출되지 않음**을 `unittest.mock.patch`의
    `call_count`로 직접 단정한다.

    패치 타깃은 `hooks.lib.kompound_snapshot.verify.run_gates`다 —
    `apply.py`는 `from hooks.lib.kompound_snapshot import ... verify ...`로
    `verify`를 **모듈 객체**로 import하고 `verify.run_gates(...)`처럼 속성
    접근으로 호출한다(`from verify import run_gates` 형태가 아니다). 따라서
    `verify` 모듈 자체의 `run_gates` 속성을 패치해야 `apply.py`가 호출 시점에
    보는 것과 동일한 객체가 치환된다 — `apply` 모듈 네임스페이스에
    `run_gates`라는 별도 바인딩이 없으므로 `apply.run_gates`를 패치하는
    것은 애초에 대상이 없어 아무 효과가 없다.

    **패치가 실제로 걸렸음을 어떻게 확인했는가(대칭 케이스)**: 같은
    context manager 안에서 먼저 신규 문서가 있는 호출을 실행해
    `call_count >= 1`을 확인한다(=패치가 걸리지 않았다면 이 단정 자체가
    실패해 테스트가 즉시 잡아낸다). 그 다음 `reset_mock()` 후 박제 0건
    호출을 실행해 `call_count == 0`을 단정한다 — 같은 패치 컨텍스트·같은
    kompound 위에서 "도는 경우"와 "스킵되는 경우"를 나란히 비교하므로,
    패치 오적용으로 인한 위양성(항상 0)을 이 비교 자체가 배제한다.
    """
    kompound = fake_kompound_env["kompound"]
    config = fake_kompound_env["config"]

    src = _make_source_file(project_root, "2026-07-04-gatecount-spec.md", "# gate count spec\n")
    record = _record(src, kind="spec", repo_dir="acme-widget")

    with patch(
        "hooks.lib.kompound_snapshot.verify.run_gates", wraps=verify.run_gates
    ) as mocked_run_gates:
        # 대칭 케이스 — 신규 문서가 있어 카탈로그가 실제로 시도되는 최초 호출.
        first = apply_mod.apply(
            kompound, [record], prefix_map=config["prefix_map"], scan_root=config["scan_root"]
        )
        assert first["catalog_stage"]["attempted"] is True
        assert first["catalog_stage"]["ok"] is True
        assert mocked_run_gates.call_count >= 1, (
            "패치가 걸리지 않았다면(잘못된 타깃) 이 단정에서 실패해야 정상 —"
            " 이 실패 없이 아래 0-count 단정만 통과하면 그 결과는 신뢰할 수 없다"
        )

        mocked_run_gates.reset_mock()

        # 박제 0건 — 같은 문서를 다시 넣어도 이미 raw·registry 모두 링크됨.
        second = apply_mod.apply(
            kompound, [record], prefix_map=config["prefix_map"], scan_root=config["scan_root"]
        )
        assert second["raw_stage"]["new"] == []
        assert second["raw_stage"]["updated"] == []
        assert second["catalog_stage"]["attempted"] is False

        # 완료조건 #23 핵심 단정 — 박제 0건이면 게이트 함수가 전혀 호출되지 않는다.
        assert mocked_run_gates.call_count == 0


# ── v2 볼트 계약 (2026-10-07) — 기존 raw 제자리 갱신 · legacySlug · 형식 보호 ──


def test_apply_updates_existing_raw_in_place_wherever_it_lives(
    fake_kompound_env: Dict[str, Any], project_root: Path
) -> None:
    """같은 slug의 raw가 다른 도메인 폴더(Pattern API)에 이미 있으면 그 파일의
    `## Original Content`만 교체한다 — 파일명·날짜·도메인·frontmatter 유지,
    `date modified`만 갱신, 두 번째 사본 없음."""
    from tests.conftest import fake_raw_path

    kompound = fake_kompound_env["kompound"]
    config = fake_kompound_env["config"]
    existing = fake_raw_path(kompound, "beta-launch-flow-spec.md")
    before = existing.read_text(encoding="utf-8")

    src = _make_source_file(project_root, "2026-07-02-launch-flow-spec.md", "# launch-flow spec v2\n\n새 본문\n")
    record = _record(src, kind="spec", repo_dir="beta-service")

    result = apply_mod.apply(kompound, [record], prefix_map=config["prefix_map"], scan_root=config["scan_root"])

    raw_stage = result["raw_stage"]
    assert raw_stage["ok"] is True
    assert raw_stage["new"] == []
    assert raw_stage["updated"] == ["2026-07-01-beta-launch-flow-spec.md"]
    assert raw_stage["committed"] is True

    after = existing.read_text(encoding="utf-8")
    assert vault.extract_original_content(after) == "새 본문"
    assert f"date modified: {_TODAY}" in after
    assert "date created: 2026-07-01" in after  # 다른 frontmatter 보존
    assert 'domain: "Pattern API"' in after
    assert "# beta-launch-flow-spec\n" in after  # 파일 H1 보존(원본 H1로 바꾸지 않음)
    assert after.split("## Original Content")[1].split("## Metadata")[1] == before.split("## Metadata")[1]

    # 사본 없음 — 볼트 전체에서 이 slug 파일은 하나뿐
    matches = [p for p in (kompound / _RAW_ROOT).rglob("*beta-launch-flow-spec.md")]
    assert matches == [existing]
    # 이미 링크된 문서라 카탈로그는 스킵
    assert result["catalog_stage"]["attempted"] is False
    assert _git_status_porcelain(kompound) == ""


def test_apply_matches_existing_raw_by_legacy_slug(
    fake_kompound_env: Dict[str, Any], project_root: Path
) -> None:
    kompound = fake_kompound_env["kompound"]
    config = fake_kompound_env["config"]
    legacy = kompound.joinpath(*_SPECS_AI) / "2026-06-30-renamed-by-human.md"
    legacy.write_text(
        "---\ntype: raw-source\nlegacySlug: acme-legacy-thing-spec\n---\n\n# legacy\n\n"
        "## Original Content\n\nold body\n\n---\n\n## Metadata\n\n- x\n",
        encoding="utf-8",
    )
    _git("add", "-A", cwd=kompound)
    _git("commit", "-q", "-m", "seed legacy raw", cwd=kompound)

    src = _make_source_file(project_root, "2026-07-02-legacy-thing-spec.md", "# legacy thing\n\nnew body\n")
    record = _record(src, kind="spec", repo_dir="acme-widget")

    result = apply_mod.apply(kompound, [record], prefix_map=config["prefix_map"], scan_root=config["scan_root"])

    assert result["raw_stage"]["updated"] == ["2026-06-30-renamed-by-human.md"]
    assert result["raw_stage"]["new"] == []
    assert vault.extract_original_content(legacy.read_text(encoding="utf-8")) == "new body"
    assert not _new_raw_path(kompound, "acme-legacy-thing-spec").exists()


def test_apply_refuses_to_overwrite_raw_without_original_content_section(
    fake_kompound_env: Dict[str, Any], project_root: Path
) -> None:
    kompound = fake_kompound_env["kompound"]
    config = fake_kompound_env["config"]
    human = kompound.joinpath(*_SPECS_AI) / "2026-06-30-acme-handwritten-spec.md"
    human.write_text("# 사람이 쓴 문서\n\n구조 없음\n", encoding="utf-8")
    _git("add", "-A", cwd=kompound)
    _git("commit", "-q", "-m", "seed handwritten raw", cwd=kompound)
    before_commits = _commit_count(kompound)

    src = _make_source_file(project_root, "2026-07-02-handwritten-spec.md", "# x\n\ny\n")
    record = _record(src, kind="spec", repo_dir="acme-widget")

    result = apply_mod.apply(kompound, [record], prefix_map=config["prefix_map"], scan_root=config["scan_root"])

    assert result["raw_stage"]["ok"] is False
    assert "Original Content" in result["raw_stage"]["error"]
    assert human.read_text(encoding="utf-8") == "# 사람이 쓴 문서\n\n구조 없음\n"
    assert _commit_count(kompound) == before_commits
    assert _git_status_porcelain(kompound) == ""


def test_apply_domain_map_places_new_raw_in_configured_domain(
    fake_kompound_env: Dict[str, Any], project_root: Path
) -> None:
    kompound = fake_kompound_env["kompound"]
    config = fake_kompound_env["config"]
    src = _make_source_file(project_root, "2026-07-02-placed-spec.md", "# placed\n\nbody\n")
    record = _record(src, kind="spec", repo_dir="acme-widget")

    result = apply_mod.apply(
        kompound,
        [record],
        prefix_map=config["prefix_map"],
        scan_root=config["scan_root"],
        domain_map={"acme": "CLOFab"},
    )

    assert result["raw_stage"]["ok"] is True
    target = _new_raw_path(kompound, "acme-placed-spec", parts=(_RAW_ROOT, "17. Specs", "CLOFab"))
    assert target.is_file()
    text = target.read_text(encoding="utf-8")
    assert 'domain: "CLOFab"' in text
    assert '  - "clofab"' in text
    assert 'collectionPurpose: "Marvelous 개발 — SDD spec 스냅샷 보존"' in text
    assert result["catalog_stage"]["ok"] is True


def test_apply_on_non_v2_vault_is_precondition_failed_and_writes_nothing(tmp_path: Path) -> None:
    """v1 레이아웃(`raw/` + `wiki/`)을 가리키는 오래된 설정 — v2 경로를 만들어 쓰지
    않고 precondition_failed로 보고한다(T2 삭제 차단 대상)."""
    v1 = tmp_path / "old_kompound"
    (v1 / "raw").mkdir(parents=True)
    (v1 / "wiki").mkdir()
    (v1 / "wiki" / "index.md").write_text("# index\n", encoding="utf-8")
    (v1 / "wiki" / "log.md").write_text("", encoding="utf-8")
    _git("init", "-q", cwd=v1)
    src = _make_source_file(tmp_path, "2026-07-02-x-spec.md", "# x\n")
    record = _record(src, kind="spec", repo_dir="acme-widget")

    result = apply_mod.apply(v1, [record], prefix_map={"acme-widget": "acme"})

    assert result["precondition_failed"] is True
    assert "not_v2_vault" in result["precondition"]["reason"]
    assert "v1" in result["precondition"]["reason"]
    assert not (v1 / _RAW_ROOT).exists()
