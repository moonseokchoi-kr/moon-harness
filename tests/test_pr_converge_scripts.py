"""tests/test_pr_converge_scripts.py — pr-converge scripts/ 단위 테스트.

커버 모듈:
  - skills/pr-converge/scripts/state_machine.py
  - skills/pr-converge/scripts/comment_dedup.py
  - skills/pr-converge/scripts/pattern_detector.py
  - skills/pr-converge/scripts/learning_appender.py

네트워크/LLM/gh 호출 없음 — 오프라인 전용 (conftest.py의 `offline` 마커).

NOTE: skills/pr-converge/ 디렉토리명에 하이픈이 포함되어 Python 표준 패키지 경로로
      직접 import할 수 없음. conftest.py가 repo root를 sys.path에 추가하고,
      여기서 scripts/ 디렉토리를 추가로 sys.path에 등록해 모듈을 import한다.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

# ── scripts/ 디렉토리를 sys.path에 추가 ──────────────────────────────────────
# conftest.py가 repo root를 sys.path[0]으로 추가하므로, 여기서는 scripts/ 경로만 추가.
_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS_DIR = _REPO_ROOT / "skills" / "pr-converge" / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

# ── 임포트 ──────────────────────────────────────────────────────────────────

from state_machine import (  # noqa: E402
    STATUS_BLOCKED,
    STATUS_CONVERGED,
    STATUS_NEEDS_HUMAN,
    STATUS_WAITING,
    STATUS_WORKING,
    transition_status,
)
from comment_dedup import (  # noqa: E402
    filter_new_comments,
    mark_as_processed,
)
from pattern_detector import (  # noqa: E402
    REPEAT_THRESHOLD,
    build_learning_payload,
    detect_repeated_ci_fail,
)
from learning_appender import (  # noqa: E402
    append_learning_entry,
    append_learning_entries,
)

_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


# ════════════════════════════════════════════════════════════════════════════
# state_machine.py 테스트
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.offline
class TestTransitionStatus:
    """transition_status() 상태 전이 경계 테스트."""

    def _base_state(self, **overrides) -> Dict[str, Any]:
        state = {
            "schema_version": 1,
            "pr": "42",
            "branch": "feat/test",
            "processed_comment_ids": [],
            "fix_attempts": {},
            "iterations": 0,
            "status": "WORKING",
            "last_tick_at": "2026-06-16T00:00:00Z",
            "escalations": [],
        }
        state.update(overrides)
        return state

    def test_converged_when_all_clear(self):
        """신호 없음 + 에스컬레이션 0 → CONVERGED."""
        result = transition_status(self._base_state(), signals=[])
        assert result["new_status"] == STATUS_CONVERGED
        assert result["cadence_seconds"] is None

    def test_working_when_push_done(self):
        """push_done=True 신호 있음 → WORKING."""
        signals = [{"signal_key": "ci:unit-tests", "kind": "ci_fail", "push_done": True}]
        result = transition_status(self._base_state(), signals=signals)
        assert result["new_status"] == STATUS_WORKING
        assert result["cadence_seconds"] == 270

    def test_working_when_actionable_comment(self):
        """actionable 코멘트 신호 있음 (push 미완) → WORKING."""
        signals = [{"signal_key": "comment:123", "kind": "comment_actionable", "push_done": False}]
        result = transition_status(self._base_state(), signals=signals)
        assert result["new_status"] == STATUS_WORKING

    def test_waiting_when_ci_pending_no_escalation(self):
        """CI pending + 에스컬레이션 0 → WAITING."""
        signals = [{"signal_key": "ci:unit-tests", "kind": "ci_pending"}]
        result = transition_status(self._base_state(), signals=signals)
        assert result["new_status"] == STATUS_WAITING
        assert result["cadence_seconds"] == 270

    def test_needs_human_when_escalation_only(self):
        """에스컬레이션만 있고 CI green → NEEDS_HUMAN."""
        signals = [{"signal_key": "comment:99", "kind": "comment_escalate"}]
        result = transition_status(self._base_state(), signals=signals)
        assert result["new_status"] == STATUS_NEEDS_HUMAN
        assert result["cadence_seconds"] == 1200

    def test_needs_human_from_state_escalations(self):
        """state.escalations에 기존 에스컬레이션 있음 → NEEDS_HUMAN."""
        state = self._base_state(escalations=["https://github.com/owner/repo/pull/42#discussion_r999"])
        result = transition_status(state, signals=[])
        assert result["new_status"] == STATUS_NEEDS_HUMAN

    def test_blocked_by_fix_attempts_threshold(self):
        """fix_attempts 임계값(3) 도달 → BLOCKED."""
        state = self._base_state(fix_attempts={"ci:unit-tests": 3})
        result = transition_status(state, signals=[])
        assert result["new_status"] == STATUS_BLOCKED
        assert result["cadence_seconds"] is None
        assert result["blocked_reason"] is not None

    def test_blocked_by_iterations_threshold(self):
        """iterations > 15 → BLOCKED."""
        state = self._base_state(iterations=16)
        result = transition_status(state, signals=[])
        assert result["new_status"] == STATUS_BLOCKED

    def test_iterations_exactly_15_not_blocked(self):
        """iterations == 15는 BLOCKED 아님 (> 15 조건)."""
        state = self._base_state(iterations=15)
        result = transition_status(state, signals=[])
        # 15는 임계값 미만 — 서킷브레이커 발동 안 함
        assert result["new_status"] != STATUS_BLOCKED

    def test_cadence_never_300(self):
        """모든 상태에서 cadence_seconds는 절대 300이 아님."""
        all_statuses = [STATUS_WORKING, STATUS_WAITING, STATUS_NEEDS_HUMAN, STATUS_CONVERGED, STATUS_BLOCKED]
        for status in all_statuses:
            from hooks.lib.self_improve.circuit_breaker import compute_cadence
            cadence = compute_cadence(status)
            assert cadence != 300, f"cadence must never be 300 for status={status}"

    def test_invalid_state_returns_waiting(self):
        """state가 dict 아님 → fail-safe WAITING."""
        result = transition_status("not-a-dict", signals=[])
        assert result["new_status"] == STATUS_WAITING

    def test_invalid_signals_treated_as_empty(self):
        """signals가 list 아님 → 빈 리스트로 처리."""
        result = transition_status(self._base_state(), signals=None)
        assert result["new_status"] == STATUS_CONVERGED

    def test_result_has_required_keys(self):
        """결과 dict에 필수 키가 모두 존재."""
        result = transition_status(self._base_state(), signals=[])
        assert "new_status" in result
        assert "cadence_seconds" in result
        assert "blocked_reason" in result
        assert "transition_reason" in result


# ════════════════════════════════════════════════════════════════════════════
# comment_dedup.py 테스트
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.offline
class TestFilterNewComments:
    """filter_new_comments() 중복 코멘트 필터링 테스트."""

    def test_returns_only_new_comments(self):
        """processed_ids에 없는 코멘트만 반환."""
        all_comments = [
            {"id": "IC_001", "body": "First comment"},
            {"id": "IC_002", "body": "Second comment"},
            {"id": "IC_003", "body": "Third comment"},
        ]
        processed_ids = ["IC_001"]
        result = filter_new_comments(all_comments, processed_ids)
        assert len(result) == 2
        ids = {c["id"] for c in result}
        assert ids == {"IC_002", "IC_003"}

    def test_all_processed_returns_empty(self):
        """모두 처리된 경우 빈 리스트."""
        all_comments = [{"id": "IC_001"}, {"id": "IC_002"}]
        result = filter_new_comments(all_comments, ["IC_001", "IC_002"])
        assert result == []

    def test_empty_processed_returns_all(self):
        """처리된 ID 없으면 전부 신규."""
        all_comments = [{"id": "IC_001"}, {"id": "IC_002"}]
        result = filter_new_comments(all_comments, [])
        assert len(result) == 2

    def test_str_int_id_normalization(self):
        """str ID와 int ID 혼용 대응 — 정규화 후 비교."""
        all_comments = [{"id": 1001}, {"id": 1002}]
        processed_ids = ["1001"]  # str로 저장됨
        result = filter_new_comments(all_comments, processed_ids)
        assert len(result) == 1
        assert result[0]["id"] == 1002

    def test_comment_without_id_treated_as_new(self):
        """id 키 없는 코멘트: 신규로 취급 (누락 방지)."""
        all_comments = [{"body": "no id comment"}, {"id": "IC_002"}]
        result = filter_new_comments(all_comments, [])
        assert len(result) == 2

    def test_invalid_all_comments_returns_empty(self):
        """all_comments가 list 아님 → fail-safe 빈 리스트."""
        result = filter_new_comments(None, [])
        assert result == []

    def test_invalid_processed_ids_treats_all_as_new(self):
        """processed_ids가 list 아님 → 전체를 신규로 취급."""
        all_comments = [{"id": "IC_001"}, {"id": "IC_002"}]
        result = filter_new_comments(all_comments, None)
        assert len(result) == 2

    def test_preserves_comment_content(self):
        """필터링 후 코멘트 내용이 변경되지 않음."""
        all_comments = [{"id": "IC_001", "body": "original", "extra": 42}]
        result = filter_new_comments(all_comments, [])
        assert result[0] == {"id": "IC_001", "body": "original", "extra": 42}


@pytest.mark.offline
class TestMarkAsProcessed:
    """mark_as_processed() 병합 테스트."""

    def test_appends_new_ids(self):
        """새 ID를 기존 목록에 추가."""
        result = mark_as_processed(["IC_001"], ["IC_002", "IC_003"])
        assert "IC_001" in result
        assert "IC_002" in result
        assert "IC_003" in result

    def test_no_duplicates(self):
        """중복 ID 추가 시 한 번만 포함."""
        result = mark_as_processed(["IC_001", "IC_002"], ["IC_002", "IC_003"])
        assert result.count("IC_002") == 1 if "IC_002" in result else True

    def test_original_list_not_modified(self):
        """원본 리스트 불변."""
        original = ["IC_001"]
        mark_as_processed(original, ["IC_002"])
        assert original == ["IC_001"]


# ════════════════════════════════════════════════════════════════════════════
# pattern_detector.py 테스트
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.offline
class TestDetectRepeatedCiFail:
    """detect_repeated_ci_fail() 반복 패턴 감지 테스트 (골든 픽스처 포함)."""

    def _load_fixture(self) -> dict:
        return json.loads((_FIXTURES_DIR / "pr_converge_patterns.json").read_text(encoding="utf-8"))

    def test_single_repeat_detected(self):
        """동일 CI 신호 2회 → 패턴 1개 감지."""
        fix_attempts = {"ci:unit-tests": 2, "lint:ruff": 1}
        result = detect_repeated_ci_fail(fix_attempts, provenance_repo="moon-harness", detected_at="2026-06-16")
        assert len(result) == 1
        assert result[0]["signal_key"] == "ci:unit-tests"

    def test_multiple_repeats_detected(self):
        """복수 신호 반복 → 여러 패턴."""
        fix_attempts = {"ci:build": 3, "ci:unit-tests": 2, "comment:10293": 1}
        result = detect_repeated_ci_fail(fix_attempts, provenance_repo="marvelous", detected_at="2026-06-16")
        keys = {r["signal_key"] for r in result}
        assert "ci:build" in keys
        assert "ci:unit-tests" in keys
        assert "comment:10293" not in keys

    def test_no_repeat_returns_empty(self):
        """1회 이하 신호만 있으면 빈 리스트."""
        fix_attempts = {"ci:unit-tests": 1, "lint:ruff": 1}
        result = detect_repeated_ci_fail(fix_attempts, provenance_repo="moon-harness")
        assert result == []

    def test_empty_fix_attempts_returns_empty(self):
        """fix_attempts 비어있음 → 빈 리스트."""
        result = detect_repeated_ci_fail({}, provenance_repo="moon-harness")
        assert result == []

    def test_invalid_fix_attempts_fail_safe(self):
        """fix_attempts가 dict 아님 → fail-safe 빈 리스트."""
        result = detect_repeated_ci_fail(None, provenance_repo="moon-harness")
        assert result == []

    def test_string_count_values_handled(self):
        """횟수가 str로 저장된 경우 int로 변환해 처리."""
        fix_attempts = {"ci:type-check": "2", "ci:lint": "1"}
        result = detect_repeated_ci_fail(fix_attempts, provenance_repo="moon-harness", detected_at="2026-06-16")
        assert len(result) == 1
        assert result[0]["signal_key"] == "ci:type-check"

    def test_payload_has_required_fields(self):
        """페이로드 dict에 필수 필드 모두 존재."""
        fix_attempts = {"ci:unit-tests": 2}
        result = detect_repeated_ci_fail(fix_attempts, provenance_repo="moon-harness", detected_at="2026-06-16")
        assert len(result) == 1
        payload = result[0]
        assert "marker" in payload
        assert "tags" in payload
        assert "body" in payload
        assert "signal_key" in payload
        assert "attempt_count" in payload

    def test_payload_tags_have_provenance_fields(self):
        """페이로드 tags에 F15 Acceptance 필수 필드 존재."""
        fix_attempts = {"ci:unit-tests": 2}
        result = detect_repeated_ci_fail(fix_attempts, provenance_repo="test-repo", detected_at="2026-06-16")
        tags = result[0]["tags"]
        assert tags.get("provenance_repo") == "test-repo"
        assert tags.get("stage") == "pr-converge"
        assert tags.get("domain") == "pr-converge"

    def test_empty_provenance_repo_falls_back_to_unknown(self):
        """provenance_repo 비어있음 → 'unknown' 폴백."""
        fix_attempts = {"ci:unit-tests": 2}
        result = detect_repeated_ci_fail(fix_attempts, provenance_repo="", detected_at="2026-06-16")
        assert result[0]["tags"]["provenance_repo"] == "unknown"

    def test_marker_format(self):
        """marker 포맷: 'YYYY-MM-DD — {signal_key} / pr-converge'."""
        fix_attempts = {"ci:unit-tests": 2}
        result = detect_repeated_ci_fail(fix_attempts, provenance_repo="test", detected_at="2026-06-16")
        marker = result[0]["marker"]
        assert "2026-06-16" in marker
        assert "ci:unit-tests" in marker
        assert "pr-converge" in marker

    def test_golden_fixture(self):
        """골든 픽스처 케이스 전체 검증."""
        fixture = self._load_fixture()
        for case in fixture["cases"]:
            inp = case["input"]
            exp = case["expected"]
            result = detect_repeated_ci_fail(
                inp["fix_attempts"],
                provenance_repo=inp.get("provenance_repo", ""),
                detected_at=inp.get("detected_at"),
            )
            assert len(result) == exp["count"], (
                f"case={case['name']}: expected {exp['count']} patterns, got {len(result)}"
            )
            if "signal_keys" in exp and exp["signal_keys"]:
                result_keys = {r["signal_key"] for r in result}
                for key in exp["signal_keys"]:
                    assert key in result_keys, f"case={case['name']}: expected signal_key={key!r}"
            if exp.get("all_have_provenance_repo") and result:
                for r in result:
                    assert r["tags"]["provenance_repo"], f"case={case['name']}: provenance_repo must be set"
            if exp.get("all_have_stage_pr_converge") and result:
                for r in result:
                    assert r["tags"]["stage"] == "pr-converge", f"case={case['name']}: stage must be pr-converge"
            if "provenance_repo_value" in exp and result:
                assert result[0]["tags"]["provenance_repo"] == exp["provenance_repo_value"]


@pytest.mark.offline
class TestBuildLearningPayload:
    """build_learning_payload() 페이로드 생성 테스트."""

    def test_basic_payload_structure(self):
        payload = build_learning_payload("ci:unit-tests", 2, "moon-harness", "2026-06-16")
        assert payload["marker"] == "2026-06-16 — ci:unit-tests / pr-converge"
        assert payload["tags"]["provenance_repo"] == "moon-harness"
        assert payload["tags"]["stage"] == "pr-converge"
        assert "ci:unit-tests" in payload["body"]

    def test_attempt_count_in_body(self):
        """attempt_count가 body에 반영됨."""
        payload = build_learning_payload("ci:build", 3, "test-repo", "2026-06-16")
        assert "3" in payload["body"]

    def test_extra_context_appended(self):
        payload = build_learning_payload("ci:unit-tests", 2, "repo", "2026-06-16", extra_context="추가 컨텍스트")
        assert "추가 컨텍스트" in payload["body"]


# ════════════════════════════════════════════════════════════════════════════
# learning_appender.py 테스트
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.offline
class TestAppendLearningEntry:
    """append_learning_entry() LEARNING.md append 테스트."""

    def _make_entry(self, signal_key: str = "ci:unit-tests", repo: str = "test-repo") -> Dict[str, Any]:
        return build_learning_payload(signal_key, 2, repo, "2026-06-16")

    def test_creates_file_if_not_exists(self, tmp_path: Path):
        """LEARNING.md 없으면 생성."""
        learning_path = tmp_path / "LEARNING.md"
        assert not learning_path.exists()
        entry = self._make_entry()
        result = append_learning_entry(learning_path, entry)
        assert result["ok"] is True
        assert learning_path.exists()

    def test_appended_content_has_marker(self, tmp_path: Path):
        """append 후 파일에 marker H2 헤더 존재."""
        learning_path = tmp_path / "LEARNING.md"
        entry = self._make_entry()
        append_learning_entry(learning_path, entry)
        content = learning_path.read_text(encoding="utf-8")
        assert f"## {entry['marker']}" in content

    def test_appended_content_has_tags(self, tmp_path: Path):
        """append 후 파일에 tags 메타블록 존재."""
        learning_path = tmp_path / "LEARNING.md"
        entry = self._make_entry(repo="my-repo")
        append_learning_entry(learning_path, entry)
        content = learning_path.read_text(encoding="utf-8")
        assert "<!-- tags:" in content
        assert "provenance_repo=my-repo" in content
        assert "stage=pr-converge" in content

    def test_appended_content_has_body(self, tmp_path: Path):
        """append 후 파일에 body 텍스트 존재."""
        learning_path = tmp_path / "LEARNING.md"
        entry = self._make_entry()
        append_learning_entry(learning_path, entry)
        content = learning_path.read_text(encoding="utf-8")
        assert "반복" in content or entry["body"][:10] in content

    def test_duplicate_marker_skipped(self, tmp_path: Path):
        """동일 marker 재append 시 skip."""
        learning_path = tmp_path / "LEARNING.md"
        entry = self._make_entry()
        r1 = append_learning_entry(learning_path, entry)
        r2 = append_learning_entry(learning_path, entry)
        assert r1["ok"] is True
        assert r1.get("skipped") is not True
        assert r2["ok"] is True
        assert r2.get("skipped") is True
        # 파일 내 동일 헤더가 1개만 존재
        content = learning_path.read_text(encoding="utf-8")
        assert content.count(f"## {entry['marker']}") == 1

    def test_appends_to_existing_file(self, tmp_path: Path):
        """기존 LEARNING.md에 덧붙임 — 기존 내용 보존."""
        learning_path = tmp_path / "LEARNING.md"
        learning_path.write_text("# LEARNING\n\n기존 내용\n", encoding="utf-8")
        entry = self._make_entry()
        append_learning_entry(learning_path, entry)
        content = learning_path.read_text(encoding="utf-8")
        assert "기존 내용" in content
        assert f"## {entry['marker']}" in content

    def test_invalid_entry_dict_returns_error(self, tmp_path: Path):
        """entry_dict가 dict 아님 → 오류 dict 반환."""
        learning_path = tmp_path / "LEARNING.md"
        result = append_learning_entry(learning_path, "not-a-dict")
        assert result["ok"] is False

    def test_missing_marker_returns_error(self, tmp_path: Path):
        """marker 없는 entry → 오류 dict 반환."""
        learning_path = tmp_path / "LEARNING.md"
        entry = {"tags": {"domain": "pr-converge"}, "body": "body"}
        result = append_learning_entry(learning_path, entry)
        assert result["ok"] is False
        assert result["error"] == "missing_marker"

    def test_tags_serialization_order(self, tmp_path: Path):
        """tags 직렬화 순서: domain, stage, provenance_repo 우선."""
        learning_path = tmp_path / "LEARNING.md"
        entry = self._make_entry()
        append_learning_entry(learning_path, entry)
        content = learning_path.read_text(encoding="utf-8")
        # tags 라인에서 domain이 stage보다 먼저 나와야 함
        tags_line = [l for l in content.splitlines() if "<!-- tags:" in l][0]
        domain_pos = tags_line.find("domain=")
        stage_pos = tags_line.find("stage=")
        prov_pos = tags_line.find("provenance_repo=")
        assert domain_pos < stage_pos < prov_pos

    def test_no_network_calls(self, tmp_path: Path, no_network):
        """네트워크 호출 없음 확인 (no_network fixture)."""
        learning_path = tmp_path / "LEARNING.md"
        entry = self._make_entry()
        result = append_learning_entry(learning_path, entry)
        assert result["ok"] is True  # 네트워크 없이 성공


@pytest.mark.offline
class TestAppendLearningEntries:
    """append_learning_entries() 복수 append 테스트."""

    def test_appends_multiple_entries(self, tmp_path: Path):
        """복수 엔트리 모두 append."""
        learning_path = tmp_path / "LEARNING.md"
        entries = [
            build_learning_payload("ci:unit-tests", 2, "repo-a", "2026-06-16"),
            build_learning_payload("ci:build", 3, "repo-b", "2026-06-16"),
        ]
        result = append_learning_entries(learning_path, entries)
        assert result["ok"] is True
        assert len(result["appended"]) == 2
        assert len(result["failed"]) == 0

    def test_skip_counted_separately(self, tmp_path: Path):
        """중복 skip이 'skipped'에 집계됨."""
        learning_path = tmp_path / "LEARNING.md"
        entry = build_learning_payload("ci:unit-tests", 2, "repo", "2026-06-16")
        append_learning_entries(learning_path, [entry])  # 첫 번째
        result = append_learning_entries(learning_path, [entry])  # 두 번째 (중복)
        assert len(result["skipped"]) == 1
        assert len(result["appended"]) == 0

    def test_invalid_entries_list_returns_error(self, tmp_path: Path):
        """entries가 list 아님 → ok=False."""
        learning_path = tmp_path / "LEARNING.md"
        result = append_learning_entries(learning_path, None)
        assert result["ok"] is False
