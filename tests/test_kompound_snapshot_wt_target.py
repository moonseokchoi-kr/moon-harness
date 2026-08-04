"""tests/test_kompound_snapshot_wt_target.py

T-6 (SDD Phase 4, kompound-snapshot-hook) — F2 명령 파싱(`wt_target.py`) 단위
테스트. arch §5.2.2의 경계 표를 파라미터화 테스트로 이식한다.

순수 함수 계층(arch §9.1) — 전부 `tmp_path` 위에서 실제 디렉토리/`.git` 파일을
만들어 "이름이 아니라 사실"로 판정되는지 확인한다. 어떤 입력에도 예외를
던지지 않고 항상 `list[str]`(빈 리스트 포함)을 반환함을 함께 고정한다.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import pytest

from hooks.lib.kompound_snapshot.wt_target import (
    find_worktree_removal_targets,
    is_worktree_path,
)


# ── 픽스처 헬퍼 ──────────────────────────────────────────────────────


def _make_linked_worktree(base: Path, name: str, *, main_git_dir: str = "/main/.git") -> Path:
    """`.git`이 ``gitdir:`` 파일인 linked worktree 디렉토리를 만든다((a) 신호)."""
    wt = base / name
    wt.mkdir(parents=True)
    (wt / ".git").write_text(f"gitdir: {main_git_dir}/worktrees/{name}\n", encoding="utf-8")
    return wt


def _make_worktree_remnant(base: Path, name: str) -> Path:
    """`.git`이 이미 지워진 잔해 케이스 — `worktrees/` 세그먼트만 남은 디렉토리((b) 신호)."""
    wt = base / "worktrees" / name
    wt.mkdir(parents=True)
    return wt


def _make_main_repo(base: Path, name: str) -> Path:
    """본체 repo — `.git`이 **디렉토리**(worktree 아님)."""
    repo = base / name
    (repo / ".git").mkdir(parents=True)
    return repo


def _make_plain_dir(base: Path, name: str) -> Path:
    d = base / name
    d.mkdir(parents=True)
    return d


# ── is_worktree_path 사실 판정 단위 테스트 ─────────────────────────────


def test_is_worktree_path_true_for_linked_worktree(tmp_path: Path) -> None:
    wt = _make_linked_worktree(tmp_path, "feature-x")
    assert is_worktree_path(wt) is True


def test_is_worktree_path_true_for_worktrees_segment_remnant(tmp_path: Path) -> None:
    wt = _make_worktree_remnant(tmp_path, "feature-y")
    assert is_worktree_path(wt) is True


def test_is_worktree_path_false_for_main_repo_with_git_dir(tmp_path: Path) -> None:
    """본체 repo는 `.git`이 디렉토리라 워크트리로 오판되지 않는다."""
    repo = _make_main_repo(tmp_path, "main-repo")
    assert is_worktree_path(repo) is False


def test_is_worktree_path_false_for_plain_directory(tmp_path: Path) -> None:
    d = _make_plain_dir(tmp_path, "build")
    assert is_worktree_path(d) is False


def test_is_worktree_path_false_for_nonexistent_path(tmp_path: Path) -> None:
    assert is_worktree_path(tmp_path / "does-not-exist") is False


def test_is_worktree_path_never_raises_on_weird_input() -> None:
    # 이상한 경로도 예외 없이 판정된다(Path()로 안전하게 흡수).
    # (주의: ""는 cwd로 해석되므로 여기서 검증하지 않는다 — cwd 자체가
    # "worktrees/" 세그먼트를 포함하는 개발 환경에서는 (b) 신호로 True가
    # 나올 수 있어 입력값으로 부적절하다.)
    assert is_worktree_path("\x00bad") is False


# ── 패턴 A: git [-C <dir>] worktree remove [--force|-f] <path> ────────


def test_pattern_a_git_worktree_remove_linked(tmp_path: Path) -> None:
    wt = _make_linked_worktree(tmp_path, "feature-a")
    cmd = f"git worktree remove {wt}"
    assert find_worktree_removal_targets(cmd, cwd=tmp_path) == [str(wt)]


def test_pattern_a_git_worktree_remove_force_flag(tmp_path: Path) -> None:
    wt = _make_linked_worktree(tmp_path, "feature-b")
    for flag in ("--force", "-f"):
        cmd = f"git worktree remove {flag} {wt}"
        assert find_worktree_removal_targets(cmd, cwd=tmp_path) == [str(wt)]


def test_pattern_a_git_dash_c_resolves_relative_path(tmp_path: Path) -> None:
    """`-C <dir>`이 있으면 상대경로를 그 디렉토리 기준으로 해석한다."""
    other_dir = tmp_path / "elsewhere"
    other_dir.mkdir()
    wt = _make_linked_worktree(other_dir, "feature-c")
    cmd = f"git -C {other_dir} worktree remove feature-c"
    assert find_worktree_removal_targets(cmd, cwd=tmp_path) == [str(wt.resolve())]


def test_pattern_a_worktree_remove_missing_path_passes_with_zero_targets(tmp_path: Path) -> None:
    """`git worktree remove ../already-gone` — 경로 부재 시 통과(대상 0건)."""
    cmd = "git worktree remove ../already-gone"
    assert find_worktree_removal_targets(cmd, cwd=tmp_path) == []


@pytest.mark.parametrize("subcommand", ["prune", "list"])
def test_pattern_a_non_remove_subcommands_are_no_intervention(
    tmp_path: Path, subcommand: str
) -> None:
    """`git worktree prune`/`git worktree list` — `remove`가 아니므로 무개입."""
    cmd = f"git worktree {subcommand}"
    assert find_worktree_removal_targets(cmd, cwd=tmp_path) == []


# ── 패턴 B: rm + 재귀 플래그 + 경로 오퍼랜드 1개 이상 ───────────────────


@pytest.mark.parametrize("flag", ["-r", "-R", "-rf", "-fr", "-Rf", "--recursive"])
def test_pattern_b_rm_recursive_flag_variants(tmp_path: Path, flag: str) -> None:
    wt = _make_linked_worktree(tmp_path, f"wt-{flag.strip('-')}")
    cmd = f"rm {flag} {wt}"
    assert find_worktree_removal_targets(cmd, cwd=tmp_path) == [str(wt)]


def test_pattern_b_multiple_operands_each_checked_independently(tmp_path: Path) -> None:
    wt1 = _make_linked_worktree(tmp_path, "multi-a")
    wt2 = _make_linked_worktree(tmp_path, "multi-b")
    plain = _make_plain_dir(tmp_path, "not-a-worktree")
    cmd = f"rm -rf {wt1} {plain} {wt2}"
    result = find_worktree_removal_targets(cmd, cwd=tmp_path)
    assert set(result) == {str(wt1), str(wt2)}


# ── arch §5.2.2 경계 표 — 무개입(false) 케이스 ─────────────────────────


@pytest.mark.parametrize(
    "relative_target",
    ["build/", "node_modules", "~/.cache"],
)
def test_boundary_rm_rf_non_worktree_dirs_no_intervention(
    tmp_path: Path, relative_target: str
) -> None:
    """`rm -rf build/`·`rm -rf node_modules`·`rm -rf ~/.cache` — 무개입.

    `.git` gitdir 파일도 없고 `worktrees/` 세그먼트도 없으므로(그리고 `~`는
    셸 확장을 하지 않으므로 리터럴 그대로 다뤄) 어떤 경우에도 워크트리로
    판정되지 않는다.
    """
    cmd = f"rm -rf {relative_target}"
    assert find_worktree_removal_targets(cmd, cwd=tmp_path) == []


def test_boundary_rm_rf_absolute_worktrees_path_intervenes(tmp_path: Path) -> None:
    """`rm -rf /.../worktrees/foo` — worktrees/ 세그먼트 존재 + 디렉토리 → 개입."""
    wt = _make_worktree_remnant(tmp_path, "foo")
    cmd = f"rm -rf {wt}"
    assert find_worktree_removal_targets(cmd, cwd=tmp_path) == [str(wt)]


# ── 세그먼트 분해: `;` `&&` `||` `|` ────────────────────────────────────


@pytest.mark.parametrize("separator", [";", "&&", "||", "|"])
def test_segment_split_finds_target_regardless_of_position(
    tmp_path: Path, separator: str
) -> None:
    wt = _make_linked_worktree(tmp_path, "seg-target")
    cmd = f"echo hi {separator} git worktree remove {wt}"
    assert find_worktree_removal_targets(cmd, cwd=tmp_path) == [str(wt)]


def test_segment_split_respects_quotes() -> None:
    # 따옴표 안의 구분자 문자는 세그먼트 분해 기준이 아니다 — 그 세그먼트
    # 자체는 rm/git 패턴이 아니므로 결과는 빈 리스트여야 한다(오탐 없음).
    cmd = 'echo "a; b && c" '
    assert find_worktree_removal_targets(cmd) == []


# ── 무관한 명령 — 무개입 ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "cmd",
    [
        "ls -la",
        "git status",
        "git commit -m 'rm -rf oops'",  # 문자열 안의 rm -rf는 별도 세그먼트가 아님
        "echo done",
    ],
)
def test_unrelated_commands_no_intervention(tmp_path: Path, cmd: str) -> None:
    assert find_worktree_removal_targets(cmd, cwd=tmp_path) == []


# ── 승인된 미탐(false negative) 4종 — 의도된 동작임을 명시적으로 고정 ────


def test_accepted_miss_variable_expansion_rm_rf(tmp_path: Path) -> None:
    """`rm -rf $WT` — 변수 확장을 하지 않으므로(안전 원칙) 리터럴 `$WT`가
    디렉토리로 존재할 리 없어 워크트리로 판정되지 않는다. **알려진 미탐**이며
    잔여 위험은 T1(stop-pipeline.py)이 흡수한다(arch §5.2.2 경계 표)."""
    cmd = "rm -rf $WT"
    assert find_worktree_removal_targets(cmd, cwd=tmp_path) == []


def test_accepted_miss_glob_rm_rf(tmp_path: Path) -> None:
    """`rm -rf worktrees/*` — 글롭을 확장하지 않으므로 리터럴 `worktrees/*`
    라는 이름의 디렉토리는 존재하지 않아 무개입. **알려진 미탐**."""
    cmd = "rm -rf worktrees/*"
    assert find_worktree_removal_targets(cmd, cwd=tmp_path) == []


def test_accepted_miss_cd_then_rm_rf_dot(tmp_path: Path) -> None:
    """`cd <wt> && rm -rf .` — 세그먼트별 독립 평가라 `cd`의 상태 변화를
    추적하지 않는다. `rm -rf .`의 오퍼랜드는 (cd 대상이 아니라) 원래
    프로세스 cwd로 해석되므로 워크트리가 아닌 한 무개입. **알려진 미탐**."""
    wt = _make_linked_worktree(tmp_path, "cd-target")
    cmd = f"cd {wt} && rm -rf ."
    # cwd(=tmp_path) 자체는 워크트리가 아니므로 결과는 비어 있어야 한다.
    assert find_worktree_removal_targets(cmd, cwd=tmp_path) == []


def test_accepted_miss_find_delete(tmp_path: Path) -> None:
    """`find -delete` — rm/git 패턴이 전혀 아니므로 무개입. **알려진 미탐**."""
    cmd = "find . -type f -delete"
    assert find_worktree_removal_targets(cmd, cwd=tmp_path) == []


def test_accepted_miss_shutil_rmtree(tmp_path: Path) -> None:
    """python `shutil.rmtree(...)` 호출 문자열 — bash 명령 파싱 패턴에
    해당하지 않으므로 무개입. **알려진 미탐**."""
    cmd = 'python3 -c "import shutil; shutil.rmtree(\'/some/worktrees/foo\')"'
    assert find_worktree_removal_targets(cmd, cwd=tmp_path) == []


# ── 예외 없음 / 항상 list 반환 ──────────────────────────────────────────


@pytest.mark.parametrize(
    "cmd",
    [
        "",
        "   ",
        "git worktree remove",  # 오퍼랜드 없음
        "rm -rf",  # 오퍼랜드 없음
        "rm -rf 'unterminated",  # 따옴표 불균형
        "git -C",  # -C 뒤 인자 없음
        None,
    ],
)
def test_malformed_or_edge_case_commands_never_raise(tmp_path: Path, cmd) -> None:
    result: List[str] = find_worktree_removal_targets(cmd, cwd=tmp_path)  # type: ignore[arg-type]
    assert result == []


def test_result_is_deduplicated(tmp_path: Path) -> None:
    wt = _make_linked_worktree(tmp_path, "dup-target")
    cmd = f"git worktree remove {wt} ; rm -rf {wt}"
    assert find_worktree_removal_targets(cmd, cwd=tmp_path) == [str(wt)]
