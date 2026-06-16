"""Unit tests for hooks.lib.self_improve.recurrence (spec F16).

Tests cover:
- count_signals: per-cluster same_repo count + cross_repo_set accumulation
- has_cross_project: True iff cross_repo_set has >= 2 real (non-sentinel) repos
- F16 Acceptance: single repo 5 repeats → has_cross_project=False
- Two distinct repos → has_cross_project=True
- Entries without provenance_repo use sentinel; sentinel does not count
- Degenerate inputs do not raise (fail-safe)
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from hooks.lib.self_improve.recurrence import count_signals, has_cross_project


# ---------------------------------------------------------------------------
# Helpers to build minimal entry dicts
# ---------------------------------------------------------------------------

def make_entry(
    marker: str = "test-marker",
    body: str = "",
    domain: str | None = "test-domain",
    provenance_repo: str | None = "repo-a",
) -> Dict[str, Any]:
    tags: Dict[str, str] | None
    if domain is not None or provenance_repo is not None:
        tags = {}
        if domain is not None:
            tags["domain"] = domain
        if provenance_repo is not None:
            tags["provenance_repo"] = provenance_repo
    else:
        tags = None
    return {
        "marker": marker,
        "body": body,
        "tags": tags,
        "raw": f"## {marker}\n{body}",
    }


# ---------------------------------------------------------------------------
# count_signals basic behaviour
# ---------------------------------------------------------------------------

class TestCountSignalsBasic:
    def test_empty_list_returns_empty_dict(self):
        assert count_signals([]) == {}

    def test_non_list_input_returns_empty(self):
        assert count_signals(None) == {}  # type: ignore[arg-type]
        assert count_signals("not a list") == {}  # type: ignore[arg-type]

    def test_single_entry_counted(self):
        entries = [make_entry(domain="auth", provenance_repo="repo-a")]
        result = count_signals(entries)
        assert "auth" in result
        assert result["auth"]["same_repo"] == 1
        assert "repo-a" in result["auth"]["cross_repo_set"]

    def test_two_entries_same_domain_same_repo(self):
        entries = [
            make_entry(domain="auth", provenance_repo="repo-a"),
            make_entry(domain="auth", provenance_repo="repo-a"),
        ]
        result = count_signals(entries)
        assert result["auth"]["same_repo"] == 2
        assert result["auth"]["cross_repo_set"] == {"repo-a"}

    def test_two_entries_same_domain_different_repos(self):
        entries = [
            make_entry(domain="auth", provenance_repo="repo-a"),
            make_entry(domain="auth", provenance_repo="repo-b"),
        ]
        result = count_signals(entries)
        assert result["auth"]["same_repo"] == 2
        assert result["auth"]["cross_repo_set"] == {"repo-a", "repo-b"}

    def test_multiple_clusters(self):
        entries = [
            make_entry(domain="auth", provenance_repo="repo-a"),
            make_entry(domain="typing", provenance_repo="repo-b"),
            make_entry(domain="auth", provenance_repo="repo-c"),
        ]
        result = count_signals(entries)
        assert result["auth"]["same_repo"] == 2
        assert result["typing"]["same_repo"] == 1


# ---------------------------------------------------------------------------
# count_signals: fallback cluster key (no domain → use marker)
# ---------------------------------------------------------------------------

class TestCountSignalsClusterKeyFallback:
    def test_no_domain_falls_back_to_marker(self):
        entries = [make_entry(marker="my-marker", domain=None, provenance_repo="repo-a")]
        result = count_signals(entries)
        assert "my-marker" in result

    def test_no_tags_at_all_uses_marker(self):
        entry = {"marker": "bare-marker", "body": "text", "tags": None, "raw": ""}
        result = count_signals([entry])
        assert "bare-marker" in result
        assert result["bare-marker"]["same_repo"] == 1

    def test_no_domain_no_marker_uses_unknown_sentinel(self):
        entry = {"marker": "", "body": "text", "tags": None, "raw": ""}
        result = count_signals([entry])
        assert "unknown" in result


# ---------------------------------------------------------------------------
# count_signals: missing provenance_repo uses sentinel
# ---------------------------------------------------------------------------

class TestCountSignalsNoRepo:
    def test_no_repo_uses_sentinel(self):
        entries = [make_entry(domain="auth", provenance_repo=None)]
        result = count_signals(entries)
        # sentinel is "__unknown__"
        assert "__unknown__" in result["auth"]["cross_repo_set"]

    def test_sentinel_plus_real_repo(self):
        entries = [
            make_entry(domain="auth", provenance_repo=None),
            make_entry(domain="auth", provenance_repo="repo-a"),
        ]
        result = count_signals(entries)
        assert "__unknown__" in result["auth"]["cross_repo_set"]
        assert "repo-a" in result["auth"]["cross_repo_set"]


# ---------------------------------------------------------------------------
# has_cross_project
# ---------------------------------------------------------------------------

class TestHasCrossProject:
    def test_two_distinct_repos_is_cross(self):
        entries = [
            make_entry(domain="auth", provenance_repo="repo-a"),
            make_entry(domain="auth", provenance_repo="repo-b"),
        ]
        counter = count_signals(entries)
        assert has_cross_project(counter, "auth") is True

    def test_three_distinct_repos_is_cross(self):
        entries = [
            make_entry(domain="auth", provenance_repo="repo-a"),
            make_entry(domain="auth", provenance_repo="repo-b"),
            make_entry(domain="auth", provenance_repo="repo-c"),
        ]
        counter = count_signals(entries)
        assert has_cross_project(counter, "auth") is True

    def test_single_repo_is_not_cross(self):
        entries = [make_entry(domain="auth", provenance_repo="repo-a")]
        counter = count_signals(entries)
        assert has_cross_project(counter, "auth") is False

    # F16 Acceptance criterion:
    # "단일 repo에서 5회 반복된 패턴이 하네스 티어로 자동 승격되지 않는다"
    def test_single_repo_five_repeats_not_cross(self):
        entries = [make_entry(domain="auth", provenance_repo="repo-a") for _ in range(5)]
        counter = count_signals(entries)
        assert has_cross_project(counter, "auth") is False

    def test_sentinel_only_not_cross(self):
        """Entries without known repo do not count as cross-project evidence."""
        entries = [
            make_entry(domain="auth", provenance_repo=None),
            make_entry(domain="auth", provenance_repo=None),
        ]
        counter = count_signals(entries)
        assert has_cross_project(counter, "auth") is False

    def test_sentinel_plus_one_real_repo_not_cross(self):
        """One real repo + sentinel still only 1 real repo."""
        entries = [
            make_entry(domain="auth", provenance_repo=None),
            make_entry(domain="auth", provenance_repo="repo-a"),
        ]
        counter = count_signals(entries)
        assert has_cross_project(counter, "auth") is False

    def test_missing_cluster_key_returns_false(self):
        entries = [make_entry(domain="auth", provenance_repo="repo-a")]
        counter = count_signals(entries)
        assert has_cross_project(counter, "nonexistent-key") is False

    def test_empty_counter_returns_false(self):
        assert has_cross_project({}, "auth") is False

    def test_non_dict_counter_returns_false(self):
        assert has_cross_project(None, "auth") is False  # type: ignore[arg-type]
        assert has_cross_project("bad", "key") is False  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Fail-safe: no raises on bad inputs
# ---------------------------------------------------------------------------

class TestRecurrenceFailSafe:
    def test_count_signals_bad_items_skipped(self):
        entries: List[Any] = [None, 42, "string", {"marker": "ok", "body": "", "tags": None, "raw": ""}]
        result = count_signals(entries)
        # Only the valid dict should contribute.
        assert isinstance(result, dict)

    def test_has_cross_project_never_raises(self):
        for bad in [None, 42, [], "str"]:
            try:
                has_cross_project(bad, "key")  # type: ignore[arg-type]
            except Exception as exc:
                pytest.fail(f"has_cross_project raised on {bad!r}: {exc}")
