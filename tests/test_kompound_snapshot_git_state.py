"""tests/test_kompound_snapshot_git_state.py — F9 git 상태 판정 통합 테스트.

설계 SSOT: docs/sdd/design/arch/2026-07-29-kompound-snapshot-hook.md
§6.4(F9 오프라인 판정) · §9.1("git 상태" 행 — `git init` fixture, 네트워크
없이 upstream 시뮬) · task
docs/sdd/task/kompound-snapshot-hook/2026-07-29-T-5-git-state.md.

`fake_kompound_env` fixture(T-2, tests/conftest.py)를 재사용한다 — 여기서
새로 정의하지 않는다.

upstream/ahead/behind 시뮬레이션은 실제 `fetch`/`pull`/`push`를 전혀
호출하지 않는다 — 로컬 bare 저장소를 `git remote add`로 등록하고,
`git commit-tree` + `git update-ref`로 remote-tracking ref(refs/remotes/
origin/<branch>)를 직접 조작해 ahead/behind 상태를 오프라인으로 조립한다
(task 문서가 권고한 방식).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Dict

from hooks.lib.kompound_snapshot import git_state


# ─── 테스트 전용 git 헬퍼 (fixture 조작 — 패키지 본체와 무관) ─────────────


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            "git",
            "-c",
            "user.email=test@example.invalid",
            "-c",
            "user.name=test",
            "-c",
            "commit.gpgsign=false",
            *args,
        ],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def _current_branch(kompound: Path) -> str:
    return _git("symbolic-ref", "--short", "HEAD", cwd=kompound).stdout.strip()


def _current_sha(kompound: Path) -> str:
    return _git("rev-parse", "HEAD", cwd=kompound).stdout.strip()


def _current_tree(kompound: Path) -> str:
    return _git("rev-parse", "HEAD^{tree}", cwd=kompound).stdout.strip()


def _commit_tree_only(kompound: Path, parent_sha: str, message: str) -> str:
    """워킹트리를 건드리지 않고 새 커밋 오브젝트만 만든다.

    fetch/push 없이 "원격이 이런 커밋을 갖고 있다"는 상태를 오프라인으로
    조립하기 위한 테스트 전용 헬퍼다 — HEAD의 트리를 그대로 재사용해 새
    부모 관계만 가진 커밋 오브젝트를 생성한다.
    """
    tree = _current_tree(kompound)
    result = _git(
        "commit-tree", tree, "-p", parent_sha, "-m", message, cwd=kompound
    )
    return result.stdout.strip()


def _setup_bare_remote_with_upstream(
    kompound: Path, tmp_path: Path, remote_ref_sha: str
) -> None:
    """``git remote add`` + ``update-ref``로 fetch 없이 upstream을 구성한다."""
    remote = tmp_path / "fake_remote.git"
    subprocess.run(
        ["git", "init", "-q", "--bare", str(remote)],
        check=True,
        capture_output=True,
        text=True,
    )
    branch = _current_branch(kompound)
    _git("remote", "add", "origin", str(remote), cwd=kompound)
    _git(
        "update-ref",
        f"refs/remotes/origin/{branch}",
        remote_ref_sha,
        cwd=kompound,
    )
    _git("config", f"branch.{branch}.remote", "origin", cwd=kompound)
    _git("config", f"branch.{branch}.merge", f"refs/heads/{branch}", cwd=kompound)


# ─── check_dirty ─────────────────────────────────────────────────────────


class TestCheckDirty:
    def test_clean_repo_passes(self, fake_kompound_env: Dict[str, Any]) -> None:
        kompound = fake_kompound_env["kompound"]
        result = git_state.check_dirty(kompound)
        assert result["ok"] is True
        assert result["dirty"] is False
        assert result["dirty_files"] == []
        assert result["reason"] is None

    def test_dirty_modified_and_untracked_reports_file_list(
        self, fake_kompound_env: Dict[str, Any]
    ) -> None:
        kompound: Path = fake_kompound_env["kompound"]
        modified = kompound / "raw" / "acme-widget-onboarding-spec.md"
        modified.write_text("changed content\n", encoding="utf-8")
        untracked = kompound / "raw" / "new-untracked-file.md"
        untracked.write_text("new\n", encoding="utf-8")

        result = git_state.check_dirty(kompound)

        assert result["ok"] is True
        assert result["dirty"] is True
        joined = " ".join(result["dirty_files"])
        assert "acme-widget-onboarding-spec.md" in joined
        assert "new-untracked-file.md" in joined

    def test_nonexistent_path_returns_dict_no_exception(
        self, tmp_path: Path
    ) -> None:
        result = git_state.check_dirty(tmp_path / "does-not-exist")
        assert result["ok"] is False
        assert result["dirty"] is False
        assert result["dirty_files"] == []
        assert result["reason"]

    def test_non_git_directory_returns_dict_no_exception(
        self, tmp_path: Path
    ) -> None:
        plain_dir = tmp_path / "plain"
        plain_dir.mkdir()
        result = git_state.check_dirty(plain_dir)
        assert result["ok"] is False
        assert result["reason"]


# ─── check_divergence ──────────────────────────────────────────────────────


class TestCheckDivergence:
    def test_no_upstream_is_normal_not_an_error(
        self, fake_kompound_env: Dict[str, Any]
    ) -> None:
        kompound = fake_kompound_env["kompound"]
        result = git_state.check_divergence(kompound)
        assert result["ok"] is True
        assert result["diverged"] is False
        assert result["upstream"] is False
        assert result["ahead"] == 0
        assert result["behind"] == 0
        assert result["reason"] == "no_upstream"

    def test_ahead_only_is_normal(
        self, fake_kompound_env: Dict[str, Any], tmp_path: Path
    ) -> None:
        kompound: Path = fake_kompound_env["kompound"]
        base_sha = _current_sha(kompound)
        _setup_bare_remote_with_upstream(kompound, tmp_path, base_sha)

        # 로컬에 미push 커밋 1개 추가 → ahead=1, behind=0.
        (kompound / "raw" / "extra.md").write_text("extra\n", encoding="utf-8")
        _git("add", "-A", cwd=kompound)
        _git("commit", "-q", "-m", "local ahead commit", cwd=kompound)

        result = git_state.check_divergence(kompound)
        assert result["ok"] is True
        assert result["upstream"] is True
        assert result["ahead"] == 1
        assert result["behind"] == 0
        assert result["diverged"] is False

    def test_behind_only_blocks(
        self, fake_kompound_env: Dict[str, Any], tmp_path: Path
    ) -> None:
        kompound: Path = fake_kompound_env["kompound"]
        base_sha = _current_sha(kompound)
        remote_only_sha = _commit_tree_only(kompound, base_sha, "remote-only commit")
        _setup_bare_remote_with_upstream(kompound, tmp_path, remote_only_sha)

        result = git_state.check_divergence(kompound)
        assert result["ok"] is True
        assert result["upstream"] is True
        assert result["ahead"] == 0
        assert result["behind"] == 1
        assert result["diverged"] is True

    def test_both_ahead_and_behind_diverges(
        self, fake_kompound_env: Dict[str, Any], tmp_path: Path
    ) -> None:
        kompound: Path = fake_kompound_env["kompound"]
        base_sha = _current_sha(kompound)
        remote_only_sha = _commit_tree_only(kompound, base_sha, "remote-only commit")
        _setup_bare_remote_with_upstream(kompound, tmp_path, remote_only_sha)

        (kompound / "raw" / "extra.md").write_text("extra\n", encoding="utf-8")
        _git("add", "-A", cwd=kompound)
        _git("commit", "-q", "-m", "local diverging commit", cwd=kompound)

        result = git_state.check_divergence(kompound)
        assert result["ok"] is True
        assert result["ahead"] == 1
        assert result["behind"] == 1
        assert result["diverged"] is True

    def test_nonexistent_path_returns_dict_no_exception(
        self, tmp_path: Path
    ) -> None:
        result = git_state.check_divergence(tmp_path / "does-not-exist")
        assert result["ok"] is False
        assert result["diverged"] is False
        assert result["reason"]

    def test_non_git_directory_returns_dict_no_exception(
        self, tmp_path: Path
    ) -> None:
        plain_dir = tmp_path / "plain"
        plain_dir.mkdir()
        result = git_state.check_divergence(plain_dir)
        assert result["ok"] is False
        assert result["reason"]


# ─── check_preconditions (dirty + divergence 결합, T-10 진입점) ──────────


class TestCheckPreconditions:
    def test_clean_and_no_upstream_passes(
        self, fake_kompound_env: Dict[str, Any]
    ) -> None:
        kompound = fake_kompound_env["kompound"]
        result = git_state.check_preconditions(kompound)
        assert result["ok"] is True
        assert result["dirty"] is False
        assert result["diverged"] is False
        assert result["reason"] is None
        # review P1 #1: 결합 판정 필드 — 안전 경로에서는 False.
        assert result["precondition_failed"] is False

    def test_dirty_precondition_failed_with_file_list(
        self, fake_kompound_env: Dict[str, Any]
    ) -> None:
        kompound: Path = fake_kompound_env["kompound"]
        (kompound / "raw" / "acme-widget-onboarding-spec.md").write_text(
            "dirty\n", encoding="utf-8"
        )

        result = git_state.check_preconditions(kompound)

        assert result["ok"] is True  # 판정 자체는 성공
        assert result["dirty"] is True
        assert result["dirty_files"]
        assert result["reason"] == "dirty"
        # review P1 #1: dirty만으로도 결합 필드가 True여야 한다(ok=True인데도).
        assert result["precondition_failed"] is True

    def test_diverged_behind_precondition_failed(
        self, fake_kompound_env: Dict[str, Any], tmp_path: Path
    ) -> None:
        kompound: Path = fake_kompound_env["kompound"]
        base_sha = _current_sha(kompound)
        remote_only_sha = _commit_tree_only(kompound, base_sha, "remote-only")
        _setup_bare_remote_with_upstream(kompound, tmp_path, remote_only_sha)

        result = git_state.check_preconditions(kompound)

        assert result["ok"] is True
        assert result["dirty"] is False
        assert result["diverged"] is True
        assert result["behind"] == 1
        assert result["reason"] == "diverged"
        # review P1 #1: diverged(behind>0)만으로도 결합 필드가 True여야 한다.
        assert result["precondition_failed"] is True

    def test_nonexistent_path_returns_dict_no_exception(
        self, tmp_path: Path
    ) -> None:
        result = git_state.check_preconditions(tmp_path / "does-not-exist")
        assert result["ok"] is False
        # review P1 #1: ok=False 조기 반환 경로도 결합 필드는 True로 고정.
        assert result["precondition_failed"] is True
        assert result["reason"]


# ─── commit_raw / commit_catalog (독립 2단 커밋) ──────────────────────────


class TestCommits:
    def test_commit_raw_creates_commit_with_expected_message(
        self, fake_kompound_env: Dict[str, Any]
    ) -> None:
        kompound: Path = fake_kompound_env["kompound"]
        before_sha = _current_sha(kompound)
        (kompound / "raw" / "new-doc-spec.md").write_text("new doc\n", encoding="utf-8")

        result = git_state.commit_raw(kompound, new_count=1, updated_count=0)

        assert result["ok"] is True
        assert result["committed"] is True
        assert result["commit"] is not None
        assert result["commit"] != before_sha

        log = _git("log", "-1", "--format=%s", cwd=kompound).stdout.strip()
        assert log == "snapshot(raw): 1 new, 0 updated"
        # 워킹트리가 clean해야 한다 (F9 자기 오염 회피, §6.3.0)
        status = _git("status", "--porcelain", cwd=kompound).stdout
        assert status == ""

    def test_commit_raw_no_changes_is_not_an_error(
        self, fake_kompound_env: Dict[str, Any]
    ) -> None:
        kompound = fake_kompound_env["kompound"]
        result = git_state.commit_raw(kompound, new_count=0, updated_count=0)
        assert result["ok"] is True
        assert result["committed"] is False
        assert result["commit"] is None
        assert result["reason"] == "no_changes"

    def test_commit_failure_unstages_index(
        self, fake_kompound_env: Dict[str, Any]
    ) -> None:
        """review P1 #2: commit 실패(예: pre-commit 훅 거부) 시 인덱스가
        add 이전 상태로 되돌아가야 한다 — 그렇지 않으면 다음 실행의
        `check_dirty`가 남은 스테이징을 dirty로 잡아 F9가 영구 차단된다.

        실패 유도 방식: kompound 저장소에 항상 실패하는 `pre-commit` 훅을
        심는다(``--no-verify``를 쓰지 않으므로 실제로 이 경로를 탄다).
        "인덱스가 되돌아갔음"은 (a) 실패 직전(= add 이전, 파일을 만든
        직후)의 ``git status --porcelain`` 스냅샷과 실패 직후의 스냅샷이
        바이트 동일함 (b) ``git diff --cached --name-only``가 비어 있어
        인덱스에 아무 것도 스테이징돼 있지 않음, 두 가지로 단정한다.
        """
        kompound: Path = fake_kompound_env["kompound"]
        hooks_dir = kompound / ".git" / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        pre_commit = hooks_dir / "pre-commit"
        pre_commit.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        pre_commit.chmod(0o755)

        (kompound / "raw" / "reject-me-spec.md").write_text(
            "reject\n", encoding="utf-8"
        )
        status_before_add = _git("status", "--porcelain", cwd=kompound).stdout

        result = git_state.commit_raw(kompound, new_count=1, updated_count=0)

        assert result["ok"] is False
        assert result["committed"] is False
        assert result["commit"] is None
        assert result["reason"]

        status_after_failed_commit = _git(
            "status", "--porcelain", cwd=kompound
        ).stdout
        assert status_after_failed_commit == status_before_add

        staged = _git(
            "diff", "--cached", "--name-only", cwd=kompound
        ).stdout.strip()
        assert staged == ""

    def test_commit_catalog_creates_independent_commit(
        self, fake_kompound_env: Dict[str, Any]
    ) -> None:
        kompound: Path = fake_kompound_env["kompound"]
        (kompound / "wiki" / "log.md").write_text(
            (kompound / "wiki" / "log.md").read_text(encoding="utf-8")
            + "2026-07-29 [snapshot] test\n",
            encoding="utf-8",
        )

        result = git_state.commit_catalog(kompound, "1 raw · registry+index+log")

        assert result["ok"] is True
        assert result["committed"] is True
        assert result["commit"] is not None

        log = _git("log", "-1", "--format=%s", cwd=kompound).stdout.strip()
        assert log == "snapshot(catalog): 1 raw · registry+index+log"

    def test_raw_then_catalog_produce_two_distinct_commits(
        self, fake_kompound_env: Dict[str, Any]
    ) -> None:
        """2단 커밋: raw 커밋 후 카탈로그 커밋이 별도 sha를 가진다(§6.3.0)."""
        kompound: Path = fake_kompound_env["kompound"]
        (kompound / "raw" / "second-doc-spec.md").write_text(
            "second\n", encoding="utf-8"
        )
        raw_result = git_state.commit_raw(kompound, new_count=1, updated_count=0)
        assert raw_result["committed"] is True

        # raw 커밋 직후 워킹트리가 clean해야 (ii) 진행 전 F9 재판정이 통과한다.
        precheck = git_state.check_preconditions(kompound)
        assert precheck["dirty"] is False

        (kompound / "wiki" / "index.md").write_text(
            (kompound / "wiki" / "index.md").read_text(encoding="utf-8")
            + "\n- 2026-07-29 [snapshot] second-doc\n",
            encoding="utf-8",
        )
        catalog_result = git_state.commit_catalog(kompound, "1 raw · catalog updated")
        assert catalog_result["committed"] is True

        assert raw_result["commit"] != catalog_result["commit"]

        # 최종 워킹트리도 clean해야 한다.
        final_status = _git("status", "--porcelain", cwd=kompound).stdout
        assert final_status == ""


# ─── 배타 락 ────────────────────────────────────────────────────────────


class TestExclusiveLock:
    def test_acquire_then_release(self, fake_kompound_env: Dict[str, Any]) -> None:
        kompound = fake_kompound_env["kompound"]
        acquired = git_state.acquire_lock(kompound)
        assert acquired["ok"] is True
        assert acquired["acquired"] is True

        released = git_state.release_lock(kompound)
        assert released["ok"] is True
        assert released["released"] is True

    def test_second_acquire_while_held_is_busy(
        self, fake_kompound_env: Dict[str, Any]
    ) -> None:
        kompound = fake_kompound_env["kompound"]
        first = git_state.acquire_lock(kompound)
        assert first["acquired"] is True

        second = git_state.acquire_lock(kompound)
        assert second["ok"] is True
        assert second["acquired"] is False
        assert second["reason"] == "busy"

        git_state.release_lock(kompound)

    def test_stale_lock_is_reclaimed(
        self, fake_kompound_env: Dict[str, Any]
    ) -> None:
        kompound: Path = fake_kompound_env["kompound"]
        lock_path = kompound / ".git" / "kompound-snapshot.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text("", encoding="utf-8")
        # stale로 판정되도록 mtime을 11분 전으로 되돌린다.
        stale_time = lock_path.stat().st_mtime - (11 * 60)
        os.utime(lock_path, (stale_time, stale_time))

        result = git_state.acquire_lock(kompound, stale_seconds=10 * 60)

        assert result["ok"] is True
        assert result["acquired"] is True
        assert result["reason"] == "stale_lock_reclaimed"

    def test_release_when_not_locked_is_not_an_error(
        self, fake_kompound_env: Dict[str, Any]
    ) -> None:
        kompound = fake_kompound_env["kompound"]
        result = git_state.release_lock(kompound)
        assert result["ok"] is True
        assert result["released"] is False
        assert result["reason"] == "not_locked"


# ─── 네트워크 무호출 (F13) ─────────────────────────────────────────────


class TestNoNetwork:
    def test_no_source_string_calls_fetch_pull_or_push(self) -> None:
        source = Path(
            "hooks/lib/kompound_snapshot/git_state.py"
        ).read_text(encoding="utf-8")
        for forbidden in ("fetch", "pull", "push"):
            assert (
                f'"{forbidden}"' not in source and f"'{forbidden}'" not in source
            ), f"git_state.py must never call git {forbidden}"

    def test_check_preconditions_makes_no_socket_calls(
        self, fake_kompound_env: Dict[str, Any], no_network: None
    ) -> None:
        kompound = fake_kompound_env["kompound"]
        # no_network가 활성화된 상태에서 소켓 생성 시도가 있으면 즉시
        # RuntimeError로 실패한다 — 예외 없이 통과하면 네트워크 무호출 확인.
        result = git_state.check_preconditions(kompound)
        assert result["ok"] is True

    def test_commit_and_lock_make_no_socket_calls(
        self, fake_kompound_env: Dict[str, Any], no_network: None
    ) -> None:
        kompound: Path = fake_kompound_env["kompound"]
        (kompound / "raw" / "net-check-spec.md").write_text(
            "net check\n", encoding="utf-8"
        )
        commit_result = git_state.commit_raw(kompound, new_count=1, updated_count=0)
        assert commit_result["ok"] is True

        lock_result = git_state.acquire_lock(kompound)
        assert lock_result["ok"] is True
        git_state.release_lock(kompound)
