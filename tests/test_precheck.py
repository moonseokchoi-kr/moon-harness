"""Unit tests for hooks.lib.self_improve.precheck — run_prechecks (spec F10).

Tests cover:
- Return shape always contains required keys
- Duplicate check: candidate keywords already in target → duplicate=True
- Duplicate check: clearly different content → duplicate=False
- Conflict check: negation phrases near candidate keywords → conflict=True
- Conflict check: no negation near keywords → conflict=False
- Sparsity: 1 signal + no repetition phrase → too_sparse=True
- Sparsity: explicit repetition phrase in body → too_sparse=False (override)
- Sparsity: 2+ signals → too_sparse=False
- passed=True iff all three checks clear
- Fail-safe: bad inputs never raise
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from hooks.lib.self_improve.precheck import run_prechecks

FIXTURE_DIR = Path(__file__).parent / "fixtures"
DUPLICATE_FIXTURE = FIXTURE_DIR / "target_file_with_duplicate.md"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_candidate(
    marker: str = "2026-06-10 — auth-refresh / T-12",
    body: str = "Refresh tokens single-flight dedup concurrent rotation.",
    domain: str | None = "auth",
    provenance_repo: str | None = "repo-a",
) -> Dict[str, Any]:
    tags: Dict[str, str] | None = None
    if domain is not None or provenance_repo is not None:
        tags = {}
        if domain is not None:
            tags["domain"] = domain
        if provenance_repo is not None:
            tags["provenance_repo"] = provenance_repo
    return {
        "marker": marker,
        "body": body,
        "tags": tags,
        "raw": f"## {marker}\n{body}",
    }


def make_entries(n: int, domain: str = "auth", repo: str = "repo-a") -> List[Dict[str, Any]]:
    return [
        make_candidate(
            marker=f"2026-06-{10 + i:02d} — entry-{i}",
            domain=domain,
            provenance_repo=repo,
        )
        for i in range(n)
    ]


@pytest.fixture(scope="module")
def duplicate_target_text() -> str:
    return DUPLICATE_FIXTURE.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Return shape contract
# ---------------------------------------------------------------------------

class TestRunPrechecksReturnShape:
    REQUIRED_KEYS = {
        "conflict", "conflict_reason",
        "duplicate", "duplicate_reason",
        "too_sparse", "too_sparse_reason",
        "passed",
    }

    def test_all_keys_present(self):
        candidate = make_candidate()
        result = run_prechecks(candidate, "some target text", entries=make_entries(2))
        assert self.REQUIRED_KEYS.issubset(result.keys())

    def test_bool_types(self):
        candidate = make_candidate()
        result = run_prechecks(candidate, "some target text", entries=make_entries(2))
        assert isinstance(result["conflict"], bool)
        assert isinstance(result["duplicate"], bool)
        assert isinstance(result["too_sparse"], bool)
        assert isinstance(result["passed"], bool)

    def test_reason_strings(self):
        candidate = make_candidate()
        result = run_prechecks(candidate, "some target text", entries=make_entries(2))
        assert isinstance(result["conflict_reason"], str)
        assert isinstance(result["duplicate_reason"], str)
        assert isinstance(result["too_sparse_reason"], str)


# ---------------------------------------------------------------------------
# Duplicate check
# ---------------------------------------------------------------------------

class TestDuplicateCheck:
    def test_duplicate_when_keywords_present(self, duplicate_target_text: str):
        """Candidate about auth refresh → target file already has this content."""
        candidate = make_candidate(
            body="Refresh tokens single-flight dedup concurrent rotation prevent.",
            domain="auth",
        )
        result = run_prechecks(candidate, duplicate_target_text, entries=make_entries(2))
        assert result["duplicate"] is True
        assert result["duplicate_reason"] != ""

    def test_no_duplicate_unrelated_content(self):
        """Candidate about a completely unrelated topic."""
        candidate = make_candidate(
            body="Database index rebuild strategy for large tables fragmentation.",
            domain="db",
        )
        target = "This file talks about CSS animations and React hooks."
        result = run_prechecks(candidate, target, entries=make_entries(2, domain="db"))
        assert result["duplicate"] is False

    def test_duplicate_flag_sets_passed_false(self, duplicate_target_text: str):
        candidate = make_candidate(
            body="Refresh tokens single-flight dedup concurrent rotation prevent.",
            domain="auth",
        )
        result = run_prechecks(candidate, duplicate_target_text, entries=make_entries(2))
        assert result["duplicate"] is True
        assert result["passed"] is False


# ---------------------------------------------------------------------------
# Conflict check
# ---------------------------------------------------------------------------

class TestConflictCheck:
    def test_conflict_when_negation_near_keyword(self):
        """Target file has '절대 ... 금지' near candidate keyword."""
        candidate = make_candidate(
            body="Allow parallel refresh token calls in batch mode.",
            domain=None,
            provenance_repo="repo-a",
        )
        target = (
            "## 금지 규칙\n"
            "절대 refresh token을 병렬로 호출하지 말 것 (금지).\n"
            "concurrent token refresh 하지 말라."
        )
        result = run_prechecks(candidate, target, entries=make_entries(2, domain="unknown"))
        assert result["conflict"] is True

    def test_no_conflict_unrelated_negation(self):
        """Negation exists in target but for a different topic."""
        candidate = make_candidate(
            body="Use lazy loading for images to improve LCP score.",
            domain="perf",
        )
        target = (
            "## Security rules\n"
            "절대 refresh token을 병렬로 호출하지 말 것 (금지).\n"
            "Never call the auth endpoint without credentials."
        )
        result = run_prechecks(candidate, target, entries=make_entries(2, domain="perf"))
        assert result["conflict"] is False

    def test_conflict_sets_passed_false(self):
        candidate = make_candidate(
            body="Allow parallel refresh token calls.",
            domain=None,
            provenance_repo="repo-a",
        )
        target = "절대 refresh token을 병렬로 호출 금지.\nconcurrent token calls never allowed."
        result = run_prechecks(candidate, target, entries=make_entries(2, domain="unknown"))
        assert result["conflict"] is True
        assert result["passed"] is False


# ---------------------------------------------------------------------------
# Sparsity check
# ---------------------------------------------------------------------------

class TestSparsityCheck:
    def test_sparse_when_one_signal_no_repetition(self):
        """Single entry, no repetition phrase in body → too_sparse=True."""
        candidate = make_candidate(
            body="Use explicit type assertion after async boundary.",
            domain="typing",
        )
        entries = make_entries(1, domain="typing")
        result = run_prechecks(candidate, "unrelated target content", entries=entries)
        assert result["too_sparse"] is True

    def test_not_sparse_when_two_signals(self):
        """Two entries for same cluster → enough evidence."""
        candidate = make_candidate(
            body="Use explicit type assertion after async boundary.",
            domain="typing",
        )
        entries = make_entries(2, domain="typing")
        result = run_prechecks(candidate, "unrelated target content", entries=entries)
        assert result["too_sparse"] is False

    def test_not_sparse_when_repetition_phrase_in_body(self):
        """Even with 1 signal, explicit repetition phrase overrides sparsity."""
        candidate = make_candidate(
            body="또 그러네 — type narrowing lost after await boundary. 반복 발생.",
            domain="typing",
        )
        entries = make_entries(1, domain="typing")
        result = run_prechecks(candidate, "unrelated target content", entries=entries)
        assert result["too_sparse"] is False

    def test_not_sparse_english_repetition_keyword(self):
        """'repeated' in body signals recurrence → not sparse."""
        candidate = make_candidate(
            body="Repeated failure of CI check for type narrowing.",
            domain="typing",
        )
        entries = make_entries(1, domain="typing")
        result = run_prechecks(candidate, "unrelated target content", entries=entries)
        assert result["too_sparse"] is False

    def test_sparse_sets_passed_false(self):
        candidate = make_candidate(
            body="One-time note about an obscure edge case.",
            domain="misc",
        )
        entries = make_entries(1, domain="misc")
        result = run_prechecks(candidate, "unrelated target content", entries=entries)
        assert result["too_sparse"] is True
        assert result["passed"] is False


# ---------------------------------------------------------------------------
# passed=True only when all checks clear
# ---------------------------------------------------------------------------

class TestPassedFlag:
    def test_passed_true_when_all_clear(self):
        candidate = make_candidate(
            body="Database connection pool sizing affects throughput significantly.",
            domain="db",
        )
        entries = make_entries(2, domain="db")
        target = "This file is about CSS animations entirely."
        result = run_prechecks(candidate, target, entries=entries)
        assert result["conflict"] is False
        assert result["duplicate"] is False
        assert result["too_sparse"] is False
        assert result["passed"] is True

    def test_passed_false_if_any_check_fails(self):
        """too_sparse alone → passed=False."""
        candidate = make_candidate(
            body="Database connection pool sizing.",
            domain="db",
        )
        entries = make_entries(1, domain="db")
        target = "This file is about CSS animations entirely."
        result = run_prechecks(candidate, target, entries=entries)
        assert result["passed"] is False


# ---------------------------------------------------------------------------
# Default entries=None uses [candidate]
# ---------------------------------------------------------------------------

class TestDefaultEntries:
    def test_none_entries_defaults_to_single_candidate(self):
        """When entries=None, candidate list of 1 → too_sparse=True (no repetition)."""
        candidate = make_candidate(
            body="Single observation, no recurrence signals.",
            domain="misc",
        )
        result = run_prechecks(candidate, "unrelated content")
        # entries defaults to [candidate] → 1 signal → too_sparse=True
        assert result["too_sparse"] is True


# ---------------------------------------------------------------------------
# Fail-safe: bad inputs never raise
# ---------------------------------------------------------------------------

class TestPrecheckFailSafe:
    def test_non_dict_candidate_does_not_raise(self):
        try:
            result = run_prechecks(None, "target text")  # type: ignore[arg-type]
            assert isinstance(result, dict)
        except Exception as exc:
            pytest.fail(f"run_prechecks raised on non-dict candidate: {exc}")

    def test_non_string_target_does_not_raise(self):
        candidate = make_candidate()
        try:
            result = run_prechecks(candidate, None)  # type: ignore[arg-type]
            assert isinstance(result, dict)
        except Exception as exc:
            pytest.fail(f"run_prechecks raised on non-string target: {exc}")

    def test_empty_target_does_not_raise(self):
        candidate = make_candidate()
        result = run_prechecks(candidate, "", entries=make_entries(2))
        assert isinstance(result, dict)
        assert "passed" in result

    def test_empty_candidate_body_does_not_raise(self):
        candidate = make_candidate(body="")
        result = run_prechecks(candidate, "some target", entries=make_entries(2))
        assert isinstance(result, dict)

    def test_bad_entries_list_does_not_raise(self):
        candidate = make_candidate()
        try:
            result = run_prechecks(candidate, "target text", entries=[None, 42, "bad"])  # type: ignore[list-item]
            assert isinstance(result, dict)
        except Exception as exc:
            pytest.fail(f"run_prechecks raised on bad entries list: {exc}")
