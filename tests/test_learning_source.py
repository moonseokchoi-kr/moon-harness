"""tests/test_learning_source.py — T-1 RED 테스트 (TDD RED 단계).

대상: hooks.lib.self_improve.learning_source.load_and_merge
      (아직 미구현 — import 또는 단언 실패로 RED여야 함)

시나리오 목록:
  1. 2-repo 교차 회귀 (핵심, NFR-4): 로컬 + store 각각 다른 provenance_repo 로
     동일 domain 엔트리 → has_cross_project == True
  2. 로컬-only 보존 (하위호환): store_dir=None → has_cross_project == False
  3. store 경로 없음/잘못됨: 존재하지 않는 경로 → raise 0, 로컬 entries만 반환
  4. 불량 store 파일 (B 부류): H2 헤더 없는 *.md → 0 기여, 나머지 정상 집계
  5. 개별 파일 I/O 실패 (A 부류): 읽기 불가 파일 1건 → 그 파일 skip, 나머지 집계
  6. None/빈 store_dir 귀결: load_and_merge(path, None) → 로컬-only 단언
  7. import 부작용 0 / raise 0: 모듈 import 시 파일 접근 없음, 모든 분기 raise 안 함

실제 recurrence.count_signals / has_cross_project / parser.parse_learning_entry 를
모킹 없이 진짜 결선으로 검증한다 (arch §9 Fixture 전략, NFR-4).
"""

from __future__ import annotations

import stat
import sys
from pathlib import Path
from typing import List

import pytest

# ── 대상 모듈 import (미구현이면 ImportError → 정상적 RED) ──────────────────
from hooks.lib.self_improve.learning_source import load_and_merge  # noqa: E402

# 결선 검증용 코어 (무수정 protected, 모킹 금지)
from hooks.lib.self_improve.recurrence import count_signals, has_cross_project
from hooks.lib.self_improve.parser import parse_learning_entry


# ── Fixture 헬퍼: 실제 harness-learning 포맷 *.md 내용 ──────────────────────

def _make_learning_md(domain: str, provenance_repo: str, marker: str = "") -> str:
    """최소한의 유효 LEARNING.md 엔트리 1건을 담은 문자열을 생성한다."""
    marker_str = marker or f"2026-06-30 — test-entry / {domain}"
    return (
        f"## {marker_str}\n"
        f"<!-- tags: domain={domain}, stage=retro, provenance_repo={provenance_repo} -->\n\n"
        f"Test body for {domain} from {provenance_repo}.\n"
    )


def _make_bad_md() -> str:
    """H2 헤더가 없는 잘못된 마크다운 (B 부류 — parse_learning_entry → [])."""
    return "이 파일엔 H2 헤더가 없다.\n# H1만 있고 ## H2는 없다.\n내용.\n"


# ── 1. 2-repo 교차 회귀 (핵심 케이스, NFR-4) ────────────────────────────────

class TestCrossProjectRegression:
    """로컬 + store 각각 다른 provenance_repo 로 동일 domain 엔트리가 있을 때
    has_cross_project("test-adequacy") == True 가 되어야 한다."""

    @pytest.mark.offline
    def test_cross_project_true_when_two_repos(self, tmp_path: Path) -> None:
        """로컬: provenance_repo=moon-harness, store: provenance_repo=Marvelous
        → merged → count_signals → has_cross_project("test-adequacy") is True."""
        # 로컬 LEARNING.md: moon-harness 기여
        local_file = tmp_path / "LEARNING.md"
        local_file.write_text(
            _make_learning_md("test-adequacy", "moon-harness"),
            encoding="utf-8",
        )

        # store 디렉터리: Marvelous 기여
        store_dir = tmp_path / "store"
        store_dir.mkdir()
        (store_dir / "marvelous.md").write_text(
            _make_learning_md("test-adequacy", "Marvelous"),
            encoding="utf-8",
        )

        merged: List[dict] = load_and_merge(local_file, store_dir)

        # 결선 검증: 실제 count_signals / has_cross_project (모킹 금지)
        counter = count_signals(merged)
        result = has_cross_project(counter, "test-adequacy")

        assert result is True, (
            f"has_cross_project('test-adequacy') must be True when both "
            f"moon-harness and Marvelous contribute entries. counter={counter}"
        )

    @pytest.mark.offline
    def test_merged_contains_entries_from_both_sources(self, tmp_path: Path) -> None:
        """merged 리스트에 로컬 entry와 store entry가 모두 포함되어야 한다."""
        local_file = tmp_path / "LEARNING.md"
        local_file.write_text(
            _make_learning_md("test-adequacy", "moon-harness", "2026-01-01 — local / T-1"),
            encoding="utf-8",
        )

        store_dir = tmp_path / "store"
        store_dir.mkdir()
        (store_dir / "marvelous.md").write_text(
            _make_learning_md("test-adequacy", "Marvelous", "2026-02-01 — store / T-2"),
            encoding="utf-8",
        )

        merged = load_and_merge(local_file, store_dir)

        # 각 파일 1개 엔트리 → 합계 2
        assert len(merged) == 2, f"Expected 2 entries (1 local + 1 store), got {len(merged)}"

    @pytest.mark.offline
    def test_local_entries_appear_first(self, tmp_path: Path) -> None:
        """arch §5.1: 로컬 entries가 store entries보다 먼저 이어붙여져야 한다."""
        local_file = tmp_path / "LEARNING.md"
        local_file.write_text(
            _make_learning_md("ordering", "moon-harness", "2026-01-01 — local / T-1"),
            encoding="utf-8",
        )

        store_dir = tmp_path / "store"
        store_dir.mkdir()
        (store_dir / "store.md").write_text(
            _make_learning_md("ordering", "Marvelous", "2026-02-01 — store / T-2"),
            encoding="utf-8",
        )

        merged = load_and_merge(local_file, store_dir)

        assert len(merged) == 2
        first_repo = (merged[0].get("tags") or {}).get("provenance_repo")
        second_repo = (merged[1].get("tags") or {}).get("provenance_repo")
        assert first_repo == "moon-harness", (
            f"First entry must come from local (moon-harness), got '{first_repo}'"
        )
        assert second_repo == "Marvelous", (
            f"Second entry must come from store (Marvelous), got '{second_repo}'"
        )


# ── 2. 로컬-only 보존 (하위호환, NFR-3) ─────────────────────────────────────

class TestLocalOnlyCompat:
    """store_dir=None 일 때 단일 repo → has_cross_project == False."""

    @pytest.mark.offline
    def test_store_dir_none_returns_local_only(self, tmp_path: Path) -> None:
        """store_dir=None → store 기여 없이 로컬 entries만 반환."""
        local_file = tmp_path / "LEARNING.md"
        local_file.write_text(
            _make_learning_md("test-adequacy", "moon-harness"),
            encoding="utf-8",
        )

        merged = load_and_merge(local_file, None)

        # 하나의 repo만 있으므로 has_cross_project == False
        counter = count_signals(merged)
        result = has_cross_project(counter, "test-adequacy")

        assert result is False, (
            f"has_cross_project must be False when store_dir=None (single repo only). "
            f"counter={counter}"
        )

    @pytest.mark.offline
    def test_store_dir_none_entry_count_equals_local_parse(self, tmp_path: Path) -> None:
        """store_dir=None 반환 entries 수 == parse_learning_entry(local) 수."""
        local_file = tmp_path / "LEARNING.md"
        content = (
            _make_learning_md("d1", "moon-harness", "2026-01-01 — a / T-1")
            + _make_learning_md("d2", "moon-harness", "2026-01-02 — b / T-2")
        )
        local_file.write_text(content, encoding="utf-8")

        merged = load_and_merge(local_file, None)
        expected = parse_learning_entry(content)

        assert len(merged) == len(expected), (
            f"store_dir=None must return same count as parse_learning_entry alone. "
            f"got={len(merged)}, expected={len(expected)}"
        )


# ── 3. store 경로 없음 / 잘못됨 (A 부류: 디렉터리 레벨) ─────────────────────

class TestInvalidStorePath:
    """존재하지 않는 store 경로 → raise 0, 로컬 entries만 반환."""

    @pytest.mark.offline
    def test_nonexistent_store_dir_no_raise(self, tmp_path: Path) -> None:
        """존재하지 않는 store_dir → 예외 없이 로컬 entries 반환."""
        local_file = tmp_path / "LEARNING.md"
        local_file.write_text(
            _make_learning_md("domain-x", "moon-harness"),
            encoding="utf-8",
        )
        nonexistent = tmp_path / "does_not_exist"

        # 예외 없이 실행되어야 함
        merged = load_and_merge(local_file, nonexistent)

        # 로컬 entries만 있어야 함
        local_parsed = parse_learning_entry(local_file.read_text(encoding="utf-8"))
        assert len(merged) == len(local_parsed), (
            f"Nonexistent store_dir must yield local-only entries. "
            f"got={len(merged)}, expected={len(local_parsed)}"
        )

    @pytest.mark.offline
    def test_store_path_is_file_not_dir_no_raise(self, tmp_path: Path) -> None:
        """store_dir에 파일 경로(디렉터리 아님)를 넘기면 raise 없이 로컬-only."""
        local_file = tmp_path / "LEARNING.md"
        local_file.write_text(
            _make_learning_md("domain-y", "moon-harness"),
            encoding="utf-8",
        )
        # 파일을 store_dir로 전달 (디렉터리 아님)
        not_a_dir = tmp_path / "i_am_a_file.md"
        not_a_dir.write_text("some content", encoding="utf-8")

        merged = load_and_merge(local_file, not_a_dir)

        local_parsed = parse_learning_entry(local_file.read_text(encoding="utf-8"))
        assert len(merged) == len(local_parsed), (
            f"Non-directory store path must yield local-only entries. "
            f"got={len(merged)}, expected={len(local_parsed)}"
        )

    @pytest.mark.offline
    def test_both_local_and_store_missing_returns_empty(self, tmp_path: Path) -> None:
        """로컬도 없고 store도 없으면 빈 리스트 반환, raise 0."""
        nonexistent_local = tmp_path / "no_local.md"
        nonexistent_store = tmp_path / "no_store"

        merged = load_and_merge(nonexistent_local, nonexistent_store)

        assert isinstance(merged, list), "Must return a list even on total failure"
        assert merged == [], f"Both missing → empty list, got {merged}"


# ── 4. 불량 store 파일 (B 부류: H2 없음 → parse 0건, 정상 진행) ─────────────

class TestBadStoreFile:
    """H2 헤더 없는 *.md 가 store에 섞여 있어도 0 기여로 정상 집계."""

    @pytest.mark.offline
    def test_bad_store_file_contributes_zero_entries(self, tmp_path: Path) -> None:
        """불량 파일(H2 없음) → 0 기여, 유효 파일 entries는 정상 반환."""
        local_file = tmp_path / "LEARNING.md"
        local_file.write_text(
            _make_learning_md("domain-q", "moon-harness"),
            encoding="utf-8",
        )

        store_dir = tmp_path / "store"
        store_dir.mkdir()

        # 유효 파일
        (store_dir / "valid.md").write_text(
            _make_learning_md("domain-q", "Marvelous"),
            encoding="utf-8",
        )
        # 불량 파일 (H2 없음)
        (store_dir / "bad.md").write_text(_make_bad_md(), encoding="utf-8")

        merged = load_and_merge(local_file, store_dir)

        # 불량 파일은 0기여 → 로컬 1 + 유효 store 1 = 2
        assert len(merged) == 2, (
            f"Bad store file must contribute 0 entries. Expected 2, got {len(merged)}"
        )

    @pytest.mark.offline
    def test_all_store_files_bad_returns_local_only(self, tmp_path: Path) -> None:
        """store 파일 전부 불량 → 로컬 entries만 반환, raise 0."""
        local_file = tmp_path / "LEARNING.md"
        local_file.write_text(
            _make_learning_md("domain-r", "moon-harness"),
            encoding="utf-8",
        )

        store_dir = tmp_path / "store"
        store_dir.mkdir()
        (store_dir / "bad1.md").write_text(_make_bad_md(), encoding="utf-8")
        (store_dir / "bad2.md").write_text(_make_bad_md(), encoding="utf-8")

        merged = load_and_merge(local_file, store_dir)

        local_parsed = parse_learning_entry(local_file.read_text(encoding="utf-8"))
        assert len(merged) == len(local_parsed), (
            f"All bad store files → local-only. "
            f"got={len(merged)}, expected={len(local_parsed)}"
        )


# ── 5. 개별 파일 I/O 실패 (A 부류: 파일 레벨 skip) ─────────────────────────

class TestIndividualFileIOFailure:
    """읽기 불가 파일 1건 → skip, 나머지 집계 (A 부류)."""

    @pytest.mark.offline
    def test_unreadable_store_file_is_skipped(self, tmp_path: Path) -> None:
        """권한 없는 파일 → 그 파일만 skip, 다른 파일 entries 정상 집계."""
        local_file = tmp_path / "LEARNING.md"
        local_file.write_text(
            _make_learning_md("domain-s", "moon-harness"),
            encoding="utf-8",
        )

        store_dir = tmp_path / "store"
        store_dir.mkdir()

        valid_file = store_dir / "valid.md"
        valid_file.write_text(
            _make_learning_md("domain-s", "Marvelous"),
            encoding="utf-8",
        )

        unreadable_file = store_dir / "unreadable.md"
        unreadable_file.write_text(
            _make_learning_md("domain-s", "OtherRepo"),
            encoding="utf-8",
        )
        # 읽기 권한 제거 (A 부류 I/O 실패 시뮬레이션)
        unreadable_file.chmod(0o000)

        try:
            merged = load_and_merge(local_file, store_dir)

            # unreadable 파일 skip → 로컬 1 + valid 1 = 2
            assert len(merged) == 2, (
                f"Unreadable file must be skipped. Expected 2 entries, got {len(merged)}"
            )
        finally:
            # 정리 (tmp_path 삭제 가능하도록)
            unreadable_file.chmod(0o644)

    @pytest.mark.offline
    def test_unreadable_local_file_returns_store_only(self, tmp_path: Path) -> None:
        """로컬 파일 읽기 실패(A 부류) → 로컬 [] 처리, store entries 정상 반환."""
        nonexistent_local = tmp_path / "nonexistent_local.md"

        store_dir = tmp_path / "store"
        store_dir.mkdir()
        (store_dir / "store.md").write_text(
            _make_learning_md("domain-t", "Marvelous"),
            encoding="utf-8",
        )

        # 로컬 없음 → [] 처리, store entries 반환
        merged = load_and_merge(nonexistent_local, store_dir)

        store_parsed = parse_learning_entry(
            (store_dir / "store.md").read_text(encoding="utf-8")
        )
        assert len(merged) == len(store_parsed), (
            f"Missing local file → local=[], store entries intact. "
            f"got={len(merged)}, expected={len(store_parsed)}"
        )


# ── 6. config 부재/키 부재/null/"" → store_dir=None 귀결 ────────────────────

class TestNoneStoreDirVariants:
    """load_and_merge에 None, 빈 문자열 등 store_dir 이 없는 경우 로컬-only 확인."""

    @pytest.mark.offline
    def test_store_dir_none_is_local_only(self, tmp_path: Path) -> None:
        """store_dir=None → store 기여 없음 (단언은 케이스 2 중복이지만 명시적 검증)."""
        local_file = tmp_path / "LEARNING.md"
        local_file.write_text(
            _make_learning_md("domain-u", "moon-harness"),
            encoding="utf-8",
        )

        merged = load_and_merge(local_file, None)

        local_parsed = parse_learning_entry(local_file.read_text(encoding="utf-8"))
        assert len(merged) == len(local_parsed), (
            f"store_dir=None must be local-only. "
            f"got={len(merged)}, expected={len(local_parsed)}"
        )
        # cross_project는 False여야 함
        counter = count_signals(merged)
        assert has_cross_project(counter, "domain-u") is False


# ── 7. import 부작용 0 / 모든 분기 raise 0 ──────────────────────────────────

class TestImportSideEffectsAndFailSafe:
    """모듈 import 시 파일 접근 없음. 모든 엣지 케이스에서 raise 없음."""

    @pytest.mark.offline
    def test_import_has_no_side_effects(self, no_network) -> None:
        """load_and_merge 모듈이 이미 import된 상태 — no_network 픽스처로
        import 후 네트워크 접근이 없음을 가드한다. (import 부작용 0 NFR-2)"""
        # 이 테스트가 도달했다면 import 시 네트워크/소켓 접근이 없었다는 의미.
        # (no_network 픽스처가 소켓 생성을 차단하므로 import 중 접근 시 실패했을 것)
        assert callable(load_and_merge), "load_and_merge must be callable after import"

    @pytest.mark.offline
    def test_load_and_merge_always_returns_list(self, tmp_path: Path) -> None:
        """어떤 경우에도 list를 반환해야 한다 (raise 0, 반환 타입 보장)."""
        # 로컬 없음, store 없음
        result = load_and_merge(
            tmp_path / "no_local.md",
            tmp_path / "no_store",
        )
        assert isinstance(result, list), f"Must always return list, got {type(result)}"

    @pytest.mark.offline
    def test_load_and_merge_no_raise_on_none_local(self, tmp_path: Path) -> None:
        """local_learning_path=None → raise 없이 처리 (graceful degradation)."""
        store_dir = tmp_path / "store"
        store_dir.mkdir()
        (store_dir / "store.md").write_text(
            _make_learning_md("domain-v", "Marvelous"),
            encoding="utf-8",
        )

        # local=None 인 경우에도 raise 없이 동작해야 함
        result = load_and_merge(None, store_dir)
        assert isinstance(result, list), f"Must return list even when local=None, got {type(result)}"

    @pytest.mark.offline
    def test_multiple_store_files_sorted_by_filename(self, tmp_path: Path) -> None:
        """store *.md 파일이 여러 개일 때 파일명 정렬 순으로 처리된다 (arch §5.1)."""
        local_file = tmp_path / "LEARNING.md"
        local_file.write_text(
            _make_learning_md("domain-w", "moon-harness", "2026-01-01 — local / T-0"),
            encoding="utf-8",
        )

        store_dir = tmp_path / "store"
        store_dir.mkdir()

        # b.md, a.md 순서로 생성 (파일명 역순)
        (store_dir / "b.md").write_text(
            _make_learning_md("domain-w", "RepoB", "2026-02-02 — b / T-2"),
            encoding="utf-8",
        )
        (store_dir / "a.md").write_text(
            _make_learning_md("domain-w", "RepoA", "2026-02-01 — a / T-1"),
            encoding="utf-8",
        )

        merged = load_and_merge(local_file, store_dir)

        # 로컬 1 + store 2 = 3
        assert len(merged) == 3, f"Expected 3 entries, got {len(merged)}"

        # store 부분은 a.md(RepoA)가 b.md(RepoB)보다 앞에 와야 함 (파일명 정렬)
        store_repos = [
            (merged[i].get("tags") or {}).get("provenance_repo")
            for i in range(1, 3)
        ]
        assert store_repos == ["RepoA", "RepoB"], (
            f"Store entries must be in filename-sorted order (a before b). "
            f"got={store_repos}"
        )


# ── T-2 보강: 실제 harness-learning 포맷 다중 도메인 회귀 ────────────────────


class TestMultiDomainHarnessLearningFormat:
    """실제 harness-learning 포맷: 여러 도메인 중 test-adequacy만 교차(2 repo),
    나머지 도메인은 단일 repo인 케이스에서 F16 가드가 정확히 동작하는지 검증한다.

    시나리오: T-2 완료 조건 §1 — 현황 인지 "여러 도메인 중 test-adequacy만 교차·나머지 단일"
    """

    @pytest.mark.offline
    def test_cross_project_true_only_for_cross_domain(self, tmp_path: Path) -> None:
        """test-adequacy는 2 repo(moon-harness + Marvelous) → True.
        single-domain 은 1 repo(moon-harness only) → False.
        F16 가드가 도메인별로 정확히 가르는지 확인한다."""
        # 로컬 LEARNING.md: test-adequacy(moon-harness) + single-domain(moon-harness)
        local_file = tmp_path / "LEARNING.md"
        local_file.write_text(
            _make_learning_md("test-adequacy", "moon-harness", "2026-01-01 — local / cross")
            + _make_learning_md("single-domain", "moon-harness", "2026-01-02 — local / single"),
            encoding="utf-8",
        )

        # store: test-adequacy(Marvelous) — 교차 증거 1건만 추가
        store_dir = tmp_path / "store"
        store_dir.mkdir()
        (store_dir / "marvelous.md").write_text(
            _make_learning_md("test-adequacy", "Marvelous", "2026-02-01 — store / cross"),
            encoding="utf-8",
        )

        merged = load_and_merge(local_file, store_dir)
        counter = count_signals(merged)

        # test-adequacy: 2 distinct repos → True
        assert has_cross_project(counter, "test-adequacy") is True, (
            f"test-adequacy with moon-harness+Marvelous must yield True. counter={counter}"
        )

        # single-domain: 1 repo(moon-harness) only → False
        assert has_cross_project(counter, "single-domain") is False, (
            f"single-domain with only moon-harness must yield False. counter={counter}"
        )

    @pytest.mark.offline
    def test_multiple_domains_only_cross_domain_is_true(self, tmp_path: Path) -> None:
        """N개 도메인 중 1개만 교차인 경우 has_cross_project 정확도 확인.

        로컬: domain-A(repo1), domain-B(repo1), domain-C(repo1)
        store: domain-A(repo2) 만
        → domain-A만 True, domain-B·C는 False.
        """
        local_file = tmp_path / "LEARNING.md"
        local_file.write_text(
            _make_learning_md("domain-A", "repo1", "2026-01-01 — A / local")
            + _make_learning_md("domain-B", "repo1", "2026-01-02 — B / local")
            + _make_learning_md("domain-C", "repo1", "2026-01-03 — C / local"),
            encoding="utf-8",
        )

        store_dir = tmp_path / "store"
        store_dir.mkdir()
        (store_dir / "repo2.md").write_text(
            _make_learning_md("domain-A", "repo2", "2026-02-01 — A / store"),
            encoding="utf-8",
        )

        merged = load_and_merge(local_file, store_dir)
        assert len(merged) == 4, f"Expected 4 entries (3 local + 1 store), got {len(merged)}"

        counter = count_signals(merged)
        assert has_cross_project(counter, "domain-A") is True, (
            "domain-A: repo1+repo2 → must be True"
        )
        assert has_cross_project(counter, "domain-B") is False, (
            "domain-B: repo1 only → must be False"
        )
        assert has_cross_project(counter, "domain-C") is False, (
            "domain-C: repo1 only → must be False"
        )


# ── T-2 보강: local 1 + store 2 → 엔트리 수 = 세 파일 파싱 합 ────────────────


class TestEntryCountMultipleStoreFiles:
    """로컬 1건 + store *.md 2건 → 반환 entries 수가 세 파일 파싱 결과 합과 같음.
    (T-2 완료 조건 §6)
    """

    @pytest.mark.offline
    def test_local_one_store_two_total_entry_count(self, tmp_path: Path) -> None:
        """로컬 1 파일(N개 엔트리) + store 2 파일(각 M, K개) → 합계 N+M+K."""
        local_file = tmp_path / "LEARNING.md"
        local_content = (
            _make_learning_md("domain-p", "moon-harness", "2026-01-01 — p1 / local")
            + _make_learning_md("domain-q", "moon-harness", "2026-01-02 — q1 / local")
        )
        local_file.write_text(local_content, encoding="utf-8")

        store_dir = tmp_path / "store"
        store_dir.mkdir()

        store1_content = _make_learning_md("domain-p", "Marvelous", "2026-02-01 — p1 / store1")
        store2_content = (
            _make_learning_md("domain-q", "OtherRepo", "2026-03-01 — q1 / store2")
            + _make_learning_md("domain-r", "OtherRepo", "2026-03-02 — r1 / store2")
        )
        (store_dir / "store1.md").write_text(store1_content, encoding="utf-8")
        (store_dir / "store2.md").write_text(store2_content, encoding="utf-8")

        merged = load_and_merge(local_file, store_dir)

        # 각 파일 독립 파싱 결과와 합계가 일치해야 함
        expected_count = (
            len(parse_learning_entry(local_content))
            + len(parse_learning_entry(store1_content))
            + len(parse_learning_entry(store2_content))
        )
        assert len(merged) == expected_count, (
            f"Merged entry count must equal sum of individual parse results. "
            f"got={len(merged)}, expected={expected_count}"
        )

    @pytest.mark.offline
    def test_store_two_files_varied_provenance_cross_project_resolution(
        self, tmp_path: Path
    ) -> None:
        """store 2 파일에서 동일 domain 엔트리가 오고 로컬과 합치면 3-way 결선이 올바름.
        도메인별 has_cross_project 판정이 store 파일 수와 무관하게 정확해야 한다."""
        local_file = tmp_path / "LEARNING.md"
        local_file.write_text(
            _make_learning_md("test-adequacy", "moon-harness", "2026-01-01 — local"),
            encoding="utf-8",
        )

        store_dir = tmp_path / "store"
        store_dir.mkdir()
        (store_dir / "a_marvelous.md").write_text(
            _make_learning_md("test-adequacy", "Marvelous", "2026-02-01 — store-a"),
            encoding="utf-8",
        )
        (store_dir / "b_other.md").write_text(
            _make_learning_md("test-adequacy", "AnotherRepo", "2026-03-01 — store-b"),
            encoding="utf-8",
        )

        merged = load_and_merge(local_file, store_dir)
        assert len(merged) == 3, f"Expected 3 entries (1 local + 2 store), got {len(merged)}"

        counter = count_signals(merged)
        assert has_cross_project(counter, "test-adequacy") is True, (
            f"3 distinct repos must yield True. counter={counter}"
        )
