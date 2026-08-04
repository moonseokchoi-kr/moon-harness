"""tests/test_kompound_snapshot_dedup.py — T-4 (F5 dedup) 검증.

arch: docs/sdd/design/arch/2026-07-29-kompound-snapshot-hook.md §5.4.4
spec: docs/sdd/spec/2026-07-29-kompound-snapshot-hook.md F5

3케이스(spec F5 Acceptance 그대로):
(a) 동일 해시 3사본(main 1 + worktree 2) → non-worktree 선택
(b) 동일 해시 worktree 2사본만 → 짧은 경로 선택
(c) 해시가 다른 main/worktree 쌍 → 별개 문서 2건 반환
"""

from __future__ import annotations

from typing import Any, Dict, List

from hooks.lib.kompound_snapshot.dedup import dedup


def _rec(path: str, kind: str = "spec", md5: str = "aaa", mtime: float = 0.0) -> Dict[str, Any]:
    return {"kind": kind, "path": path, "md5": md5, "mtime": mtime, "repo_dir": "/x/repo"}


# ── (a) 동일 해시 3사본(main 1 + worktree 2) → non-worktree 선택 ────────────


def test_same_hash_three_copies_prefers_non_worktree() -> None:
    records = [
        _rec("/repo/worktrees/wt1/docs/sdd/spec/a.md"),
        _rec("/repo/worktrees/wt2/docs/sdd/spec/a.md"),
        _rec("/repo/docs/sdd/spec/a.md"),
    ]
    result = dedup(records)
    assert len(result) == 1
    assert result[0]["path"] == "/repo/docs/sdd/spec/a.md"


# ── (b) 동일 해시 worktree 2사본만 → 짧은 경로 선택 ─────────────────────────


def test_same_hash_worktree_only_prefers_shorter_path() -> None:
    short = "/repo/worktrees/wt1/docs/sdd/spec/a.md"
    long = "/repo/worktrees/wt-with-a-much-longer-name/docs/sdd/spec/a.md"
    assert len(short) < len(long)

    records = [_rec(long), _rec(short)]
    result = dedup(records)
    assert len(result) == 1
    assert result[0]["path"] == short


# ── (c) 해시가 다른 main/worktree 쌍 → 별개 문서 2건 반환 ───────────────────


def test_different_hash_main_worktree_pair_are_separate_documents() -> None:
    main_doc = _rec("/repo/docs/sdd/spec/a.md", md5="hash-main", mtime=100.0)
    wt_doc = _rec("/repo/worktrees/wt1/docs/sdd/spec/a.md", md5="hash-wt", mtime=200.0)

    result = dedup([main_doc, wt_doc])
    assert len(result) == 2
    paths = {r["path"] for r in result}
    assert paths == {main_doc["path"], wt_doc["path"]}


# ── 그룹핑은 (kind, md5) 단위 — kind가 다르면 md5가 같아도 별개 그룹 ─────────


def test_grouping_is_scoped_by_kind_and_md5() -> None:
    spec_doc = _rec("/repo/docs/sdd/spec/a.md", kind="spec", md5="same-hash")
    arch_doc = _rec("/repo/docs/sdd/design/arch/a.md", kind="arch", md5="same-hash")

    result = dedup([spec_doc, arch_doc])
    assert len(result) == 2
    kinds = {r["kind"] for r in result}
    assert kinds == {"spec", "arch"}


def test_dedup_is_pure_and_does_not_mutate_input() -> None:
    records: List[Dict[str, Any]] = [
        _rec("/repo/docs/sdd/spec/a.md"),
        _rec("/repo/worktrees/wt1/docs/sdd/spec/a.md"),
    ]
    snapshot = [dict(r) for r in records]

    dedup(records)

    assert records == snapshot


def test_dedup_empty_input_returns_empty_list() -> None:
    assert dedup([]) == []
