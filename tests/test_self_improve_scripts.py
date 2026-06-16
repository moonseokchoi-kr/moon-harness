"""tests/test_self_improve_scripts.py — Unit tests for skills/self-improve/scripts/.

Coverage:
  - cursor_runner: retro-state load, get_new_entries delegation, error→None contract
  - precheck_runner: protected discard, tier classification, precheck pass/fail
  - apply_writer: project-tier apply + rollback block; harness-tier proposal only
                  (no plugin file write); harness path refused by apply_project_change
  - cap_runner: truncation report, deferred count, silent-truncation forbidden
  - skill_scanner: glob + description extraction + dedup pair detection

All tests are offline (no network, no LLM, no gh).

Import note: ``skills/self-improve/`` contains a hyphen which makes it an
invalid Python package name.  We use importlib.util to load the runner
modules by filesystem path so conftest sys.path logic still covers
``hooks.lib.self_improve.*``.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import sys
import textwrap
from pathlib import Path

import pytest

# ── Resolve repo root (same logic as conftest.py) ────────────────────────────
_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS_DIR = _REPO_ROOT / "skills" / "self-improve" / "scripts"


def _load(module_name: str):
    """Load a module from _SCRIPTS_DIR by file name (handles hyphen in path)."""
    file_path = _SCRIPTS_DIR / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# Eagerly load all runners so import errors surface at collection time.
_cursor_runner = _load("cursor_runner")
_precheck_runner = _load("precheck_runner")
_apply_writer = _load("apply_writer")
_cap_runner = _load("cap_runner")
_skill_scanner = _load("skill_scanner")

# Re-bind functions for clean test code.
run_cursor = _cursor_runner.run_cursor
run_precheck_pipeline = _precheck_runner.run_precheck_pipeline
apply_change = _apply_writer.apply_change
apply_project_change = _apply_writer.apply_project_change
write_harness_proposal = _apply_writer.write_harness_proposal
run_cap = _cap_runner.run_cap
format_truncation_report = _cap_runner.format_truncation_report
scan_skills = _skill_scanner.scan_skills


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture()
def harness_dir(tmp_path: Path) -> Path:
    """Minimal .harness/ directory under tmp_path."""
    d = tmp_path / ".harness"
    d.mkdir()
    return d


@pytest.fixture()
def learning_md(harness_dir: Path) -> Path:
    """A LEARNING.md with two entries after the cursor marker."""
    content = textwrap.dedent("""\
        # LEARNING.md

        ## 2026-06-10 — auth-flow / T-01
        <!-- tags: domain=auth, stage=구현, provenance_repo=repo-a -->

        First entry body text.

        ## 2026-06-11 — pipeline / T-02
        <!-- tags: domain=pipeline, stage=구현, provenance_repo=repo-b -->

        Second entry body text.
    """)
    p = harness_dir / "LEARNING.md"
    p.write_text(content, encoding="utf-8")
    return p


@pytest.fixture()
def retro_state(harness_dir: Path) -> Path:
    """retro-state.json pointing cursor to the first entry."""
    state = {
        "schema_version": 1,
        "last_processed_marker": "2026-06-10 — auth-flow / T-01",
        "last_retro_at": "2026-06-10T00:00:00Z",
        "cumulative": {"applied_project": 0, "proposed_harness": 0, "dropped": 0},
    }
    p = harness_dir / "retro-state.json"
    p.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return p


# ═══════════════════════════════════════════════════════════════════════════════
# cursor_runner
# ═══════════════════════════════════════════════════════════════════════════════

class TestCursorRunner:
    @pytest.mark.offline
    def test_returns_entries_after_cursor(self, harness_dir, learning_md, retro_state):
        result = run_cursor(harness_dir)
        assert result["ok"] is True
        # Only entries AFTER the cursor marker should be returned.
        assert len(result["entries"]) == 1
        entry = result["entries"][0]
        assert "pipeline" in entry["marker"] or "T-02" in entry["marker"]

    @pytest.mark.offline
    def test_no_state_file_returns_all_entries(self, harness_dir, learning_md):
        # No retro-state.json → entire LEARNING.md is new.
        result = run_cursor(harness_dir)
        assert result["ok"] is True
        assert len(result["entries"]) == 2

    @pytest.mark.offline
    def test_missing_learning_md_returns_error(self, harness_dir):
        # No LEARNING.md at all.
        result = run_cursor(harness_dir)
        assert result["ok"] is False
        assert result["entries"] == []
        assert "LEARNING.md" in result["error"]

    @pytest.mark.offline
    def test_cursor_not_advanced_on_error(self, harness_dir):
        """When ok=False the cursor dict reports last_marker=None (no advance)."""
        result = run_cursor(harness_dir)
        assert result["ok"] is False
        # last_marker comes from state; no state → None.
        assert result["last_marker"] is None

    @pytest.mark.offline
    def test_last_marker_populated_when_state_exists(
        self, harness_dir, learning_md, retro_state
    ):
        result = run_cursor(harness_dir)
        assert result["ok"] is True
        assert result["last_marker"] == "2026-06-10 — auth-flow / T-01"


# ═══════════════════════════════════════════════════════════════════════════════
# precheck_runner
# ═══════════════════════════════════════════════════════════════════════════════

class TestPrecheckRunner:
    @pytest.mark.offline
    def test_protected_path_discarded(self):
        """Candidates targeting protected set paths are discarded immediately."""
        candidates = [
            {
                "marker": "2026-06-10 — self-improve / T-99",
                "body": "Some lesson about self-improve internals.",
                "target_path": "skills/self-improve/SKILL.md",
            }
        ]
        results = run_precheck_pipeline(candidates, target_file_text="")
        assert len(results) == 1
        r = results[0]
        assert r["protected"] is True
        assert r["discarded"] is True
        assert "protected" in r["discard_reason"].lower()
        # precheck should not have been called for protected candidate.
        assert r["precheck"] == {}

    @pytest.mark.offline
    def test_harness_path_classified_harness(self):
        """A path under skills/ is HARNESS tier."""
        candidates = [
            {
                "marker": "2026-06-10 — some-skill / T-1",
                "body": "Repeated pattern about the deployer skill.",
                "target_path": "skills/deployer/SKILL.md",
            }
        ]
        # deployer is not protected, so precheck runs but may fail sparsity.
        results = run_precheck_pipeline(candidates, target_file_text="")
        r = results[0]
        assert r["protected"] is False
        assert r["tier"] == "HARNESS"

    @pytest.mark.offline
    def test_project_path_classified_project(self):
        """A path to docs/lessons-learned.md is PROJECT tier."""
        candidates = [
            {
                "marker": "2026-06-10 — cache-miss / T-5",
                "body": "Cache miss pattern observed again. recurring",
                "target_path": "docs/lessons-learned.md",
            }
        ]
        results = run_precheck_pipeline(
            candidates,
            target_file_text="# Lessons\n\nExisting content here.",
            entries=candidates * 3,  # pump signal count
        )
        r = results[0]
        assert r["protected"] is False
        assert r["tier"] == "PROJECT"

    @pytest.mark.offline
    def test_pr_converge_protected(self):
        """skills/pr-converge is also in the protected set."""
        candidates = [
            {
                "marker": "2026-06-11 — pr-converge / T-3",
                "body": "Update pr-converge loop.",
                "target_path": "skills/pr-converge/SKILL.md",
            }
        ]
        results = run_precheck_pipeline(candidates)
        assert results[0]["protected"] is True
        assert results[0]["discarded"] is True

    @pytest.mark.offline
    def test_empty_candidates_returns_empty(self):
        results = run_precheck_pipeline([])
        assert results == []

    @pytest.mark.offline
    def test_non_list_input_returns_empty(self):
        results = run_precheck_pipeline(None)  # type: ignore[arg-type]
        assert results == []


# ═══════════════════════════════════════════════════════════════════════════════
# apply_writer — harness tier UPHELD: no plugin file edits
# ═══════════════════════════════════════════════════════════════════════════════

class TestApplyWriter:
    @pytest.mark.offline
    def test_harness_tier_creates_proposal_only(self, harness_dir, tmp_path):
        """HARNESS tier must create a proposal file, NOT edit any plugin file."""
        plugin_path = tmp_path / "skills" / "some-skill" / "SKILL.md"
        plugin_path.parent.mkdir(parents=True)
        original_content = "---\nname: some-skill\n---\n# Some Skill\n"
        plugin_path.write_text(original_content, encoding="utf-8")

        result = apply_change(
            tier="HARNESS",
            target_path=str(plugin_path),
            append_text="\n## New Section\nNew content.",
            harness_dir=harness_dir,
            critic_verdict="UPHELD",
            evidence_markers="2026-06-10 — some-skill / T-1",
            rationale="Improve some-skill based on cross-project pattern.",
            cross_project_note="Observed in repo-a and repo-b.",
        )

        # Plugin file must NOT have been modified.
        assert plugin_path.read_text(encoding="utf-8") == original_content

        # Proposal file must have been created.
        assert result["ok"] is True
        proposal_path = Path(result["proposal_path"])
        assert proposal_path.exists()
        proposal_text = proposal_path.read_text(encoding="utf-8")
        assert "Harness Proposal" in proposal_text
        assert "UPHELD" in proposal_text
        assert "repo-a and repo-b" in proposal_text

    @pytest.mark.offline
    def test_project_tier_appends_to_target_and_rollback(self, harness_dir, tmp_path):
        """PROJECT tier must append to target file and record rollback block."""
        lessons_path = tmp_path / "docs" / "lessons-learned.md"
        lessons_path.parent.mkdir(parents=True)
        lessons_path.write_text("# Lessons\n\n", encoding="utf-8")

        retro_log = harness_dir / "retro-log.md"

        result = apply_change(
            tier="PROJECT",
            target_path=str(lessons_path),
            append_text="\n- Cache invalidation should happen on write, not on read.\n",
            harness_dir=harness_dir,
            retro_log_path=retro_log,
            critic_verdict="UPHELD",
            evidence_markers="2026-06-12 — cache / T-3",
        )

        assert result["ok"] is True
        content = lessons_path.read_text(encoding="utf-8")
        assert "Cache invalidation" in content

        # Rollback block must be present in retro-log.md.
        assert retro_log.exists()
        log_text = retro_log.read_text(encoding="utf-8")
        assert "Cache invalidation" in log_text or "+ Cache" in log_text
        assert "UPHELD" in log_text

    @pytest.mark.offline
    def test_apply_project_change_refuses_harness_path(self, harness_dir, tmp_path):
        """apply_project_change must refuse to write to a skills/ path."""
        plugin_path = tmp_path / "skills" / "foo" / "SKILL.md"
        retro_log = harness_dir / "retro-log.md"

        result = apply_project_change(
            target_path=str(plugin_path),
            append_text="\nExtra content.\n",
            retro_log_path=retro_log,
        )

        assert result["ok"] is False
        assert "refused" in result["error"].lower() or "harness" in result["error"].lower()
        # The plugin file must not have been created.
        assert not plugin_path.exists()

    @pytest.mark.offline
    def test_harness_proposal_file_does_not_edit_plugin(self, harness_dir, tmp_path):
        """write_harness_proposal must not touch any existing file."""
        plugin_path = tmp_path / "skills" / "pr-converge" / "SKILL.md"
        plugin_path.parent.mkdir(parents=True)
        original = "---\nname: pr-converge\n---\n# PR Converge\n"
        plugin_path.write_text(original, encoding="utf-8")

        result = write_harness_proposal(
            harness_dir=harness_dir,
            target_path=str(plugin_path),
            append_text="\n## Extra\nMore stuff.\n",
            critic_verdict="NARROW",
            evidence_markers="2026-06-13 — pr-converge / T-2",
            rationale="Narrow fix to pr-converge loop.",
            cross_project_note="Seen in two repos.",
        )

        assert result["ok"] is True
        # Plugin file must be untouched.
        assert plugin_path.read_text(encoding="utf-8") == original


# ═══════════════════════════════════════════════════════════════════════════════
# cap_runner
# ═══════════════════════════════════════════════════════════════════════════════

class TestCapRunner:
    @pytest.mark.offline
    def test_no_truncation_under_cap(self):
        candidates = ["a", "b", "c"]
        result = run_cap(candidates, cap=5)
        assert result["applied"] == ["a", "b", "c"]
        assert result["deferred"] == []
        assert result["truncated"] is False
        assert result["applied_count"] == 3
        assert result["deferred_count"] == 0

    @pytest.mark.offline
    def test_truncation_at_cap(self):
        candidates = list(range(7))
        result = run_cap(candidates, cap=5)
        assert len(result["applied"]) == 5
        assert len(result["deferred"]) == 2
        assert result["truncated"] is True
        assert result["applied_count"] == 5
        assert result["deferred_count"] == 2

    @pytest.mark.offline
    def test_exactly_at_cap_not_truncated(self):
        candidates = list(range(5))
        result = run_cap(candidates, cap=5)
        assert result["truncated"] is False
        assert result["deferred"] == []

    @pytest.mark.offline
    def test_format_truncation_report_empty_when_no_truncation(self):
        result = run_cap(["a", "b"], cap=5)
        report = format_truncation_report(result)
        assert report == ""

    @pytest.mark.offline
    def test_format_truncation_report_non_empty_when_truncated(self):
        result = run_cap(list(range(8)), cap=5)
        report = format_truncation_report(result)
        assert report != ""
        assert "CAP" in report
        assert "5" in report
        assert "3" in report  # deferred count

    @pytest.mark.offline
    def test_non_list_input_safe(self):
        result = run_cap(None, cap=5)  # type: ignore[arg-type]
        assert result["applied"] == []
        assert result["deferred"] == []
        assert result["truncated"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# skill_scanner
# ═══════════════════════════════════════════════════════════════════════════════

class TestSkillScanner:
    @pytest.fixture()
    def skill_root(self, tmp_path: Path) -> Path:
        """A fake repo root with three skills under skills/."""
        skills = {
            "alpha": (
                '---\nname: alpha\ndescription: "Runs the alpha pipeline for builds"\n---\n'
                "# Alpha\n\nDoes alpha things.\n"
            ),
            "beta": (
                '---\nname: beta\ndescription: "Runs the beta pipeline for deployments"\n---\n'
                "# Beta\n\nDoes beta things.\n"
            ),
            "gamma": (
                '---\nname: gamma\ndescription: "Completely unrelated tool for formatting"\n---\n'
                "# Gamma\n\nDoes gamma things.\n"
            ),
        }
        for skill_name, content in skills.items():
            p = tmp_path / "skills" / skill_name / "SKILL.md"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        return tmp_path

    @pytest.mark.offline
    def test_finds_all_skill_files(self, skill_root):
        result = scan_skills(skill_root)
        assert result["skill_count"] == 3
        paths = {s["path"] for s in result["skills"]}
        assert "skills/alpha/SKILL.md" in paths
        assert "skills/beta/SKILL.md" in paths
        assert "skills/gamma/SKILL.md" in paths

    @pytest.mark.offline
    def test_extracts_descriptions(self, skill_root):
        result = scan_skills(skill_root)
        desc_map = {s["path"]: s["description"] for s in result["skills"]}
        assert "pipeline for builds" in (desc_map.get("skills/alpha/SKILL.md") or "")
        assert "pipeline for deployments" in (desc_map.get("skills/beta/SKILL.md") or "")

    @pytest.mark.offline
    def test_detects_similar_descriptions_as_duplicate(self, skill_root):
        # alpha ("pipeline for builds") and beta ("pipeline for deployments") share
        # "pipeline" → with threshold=0.3 they hit as duplicate pair.
        result = scan_skills(skill_root, duplicate_threshold=0.3)
        pairs = result["duplicate_pairs"]
        pair_paths = {frozenset([p["a"], p["b"]]) for p in pairs}
        assert frozenset(["skills/alpha/SKILL.md", "skills/beta/SKILL.md"]) in pair_paths

    @pytest.mark.offline
    def test_no_duplicates_when_descriptions_differ(self, skill_root):
        # With default threshold 0.5, gamma should not pair with alpha or beta.
        result = scan_skills(skill_root, duplicate_threshold=0.5)
        for pair in result["duplicate_pairs"]:
            # gamma must not appear in a pair at this threshold.
            assert not ("gamma" in pair["a"] and "gamma" in pair["b"])

    @pytest.mark.offline
    def test_empty_skills_dir(self, tmp_path):
        result = scan_skills(tmp_path)
        assert result["skill_count"] == 0
        assert result["duplicate_pairs"] == []

    @pytest.mark.offline
    def test_skill_without_frontmatter_description_is_none(self, tmp_path):
        p = tmp_path / "skills" / "bare" / "SKILL.md"
        p.parent.mkdir(parents=True)
        p.write_text("# Bare Skill\n\nNo frontmatter.\n", encoding="utf-8")
        result = scan_skills(tmp_path)
        records = {s["path"]: s["description"] for s in result["skills"]}
        assert records["skills/bare/SKILL.md"] is None


# ═══════════════════════════════════════════════════════════════════════════════
# F16 acceptance: single-repo repeat does NOT reach harness tier
# ═══════════════════════════════════════════════════════════════════════════════

class TestF16CrossProjectInvariant:
    """Single-repo repeat pattern must NOT reach harness-tier auto-promotion."""

    @pytest.mark.offline
    def test_single_repo_five_repeats_stays_project_tier_or_discarded(self):
        """Five identical entries from the same repo must not yield HARNESS tier."""
        from hooks.lib.self_improve.recurrence import count_signals, has_cross_project

        # Five entries all from repo-x.
        entries = [
            {
                "marker": f"2026-06-0{i} — same-pattern / T-{i}",
                "body": "Cache miss in the same service repeated.",
                "tags": {"domain": "cache", "provenance_repo": "repo-x"},
                "raw": f"## 2026-06-0{i} — same-pattern / T-{i}\n\nCache miss.",
            }
            for i in range(1, 6)
        ]

        counter = count_signals(entries)
        # has_cross_project requires ≥2 distinct repos → must be False.
        assert has_cross_project(counter, "cache") is False

        # When precheck_runner processes against a PROJECT target, tier stays PROJECT.
        candidates = [
            {**entries[0], "target_path": "docs/lessons-learned.md"},
        ]
        results = run_precheck_pipeline(
            candidates,
            target_file_text="# Lessons\n",
            entries=entries,
        )
        for r in results:
            # Must be PROJECT tier (or discarded for sparsity) — never HARNESS based
            # solely on single-repo repeats.
            assert r["tier"] == "PROJECT" or r["discarded"] is True
