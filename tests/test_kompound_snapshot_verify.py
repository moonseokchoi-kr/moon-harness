"""tests/test_kompound_snapshot_verify.py — T-9: F8 검증 게이트 3종.

설계 SSOT: `docs/sdd/design/arch/2026-07-29-kompound-snapshot-hook.md`
§6.3.1(`snapshot_set_rule`) · §3.2(`verify` 모듈 계약). spec F8(S-7·S-8·S-9).

`fake_kompound_env`(tests/conftest.py, T-2 소유)를 재사용한다 — 새로 정의하지
않는다. 전부 `tmp_path` 기반이므로 실제 kompound에는 절대 쓰지 않는다.

fixture 베이스라인(변경 없이 그대로 쓰면):
- ``prefix_map`` 유효 프리픽스 = ``{"acme", "beta", "gamma"}``
- ``raw/``에 스냅샷 집합 6개(acme 2 · beta 3 · gamma 1) + 경계 케이스 1개
  (``notaproject-standalone-topic-ui.md`` — prefix `notaproject`는 유효
  프리픽스 밖이라 스냅샷 집합에서 제외돼야 한다, §6.3.1 CRITICAL 대응)
- registry가 그 6개 전부를 링크한다 → 손대지 않으면 게이트 3종 전부 통과.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch

import pytest

from hooks.lib.kompound_snapshot import verify

_VALID_PREFIXES = ("acme", "beta", "gamma")
_BASELINE_RAW_COUNT = 6  # acme 2 + beta 3 + gamma 1 (경계 케이스 제외)


# ── snapshot_set_rule / 순수 함수 단위 테스트 ───────────────────────────────


def test_effective_prefixes_removes_null_and_dedupes_and_sorts() -> None:
    prefix_map = {"a": "acme", "b": "acme", "c": None, "d": "beta"}
    assert verify.effective_prefixes(prefix_map) == ("acme", "beta")


def test_effective_prefixes_empty_or_none_is_empty_tuple() -> None:
    assert verify.effective_prefixes({}) == ()
    assert verify.effective_prefixes(None) == ()


def test_effective_prefixes_all_null_is_empty_tuple() -> None:
    """prefix_map의 값이 전부 null이면(전 프리픽스 삭제) 유효 프리픽스는 0개다."""
    assert verify.effective_prefixes({"a": None, "b": None}) == ()


@pytest.mark.parametrize(
    "filename,expected",
    [
        ("acme-widget-onboarding-spec.md", True),
        ("beta-launch-flow-result.md", True),
        ("gamma-metrics-spec.md", True),
        ("notaproject-standalone-topic-ui.md", False),  # 프리픽스 미등록 → 제외
        ("acme-spec.md", False),  # feature가 비어있음 (P-kind만, 2 hyphen 아님)
        ("acme-widget-onboarding-spec.txt", False),  # .md 아님
        ("randomfile.md", False),  # 어떤 프리픽스에도 안 걸림
        ("acme-widget-onboarding-development.md", False),  # kind가 canonical 6종 밖
    ],
)
def test_matches_snapshot_rule(filename: str, expected: bool) -> None:
    assert verify.matches_snapshot_rule(filename, _VALID_PREFIXES) is expected


def test_matches_snapshot_rule_handles_non_string_gracefully() -> None:
    assert verify.matches_snapshot_rule(None, _VALID_PREFIXES) is False  # type: ignore[arg-type]


def test_snapshot_set_rule_returns_prefixes_kinds_and_matcher() -> None:
    prefix_map = {"acme-widget": "acme", "beta-service": "beta", "gamma-tool": "gamma"}
    rule = verify.snapshot_set_rule(prefix_map)
    assert rule["prefixes"] == _VALID_PREFIXES
    assert rule["kinds"] == verify.KINDS
    assert rule["matches"]("acme-widget-onboarding-spec.md") is True
    assert rule["matches"]("notaproject-standalone-topic-ui.md") is False


# ── registry 링크 추출 ───────────────────────────────────────────────────────


def test_extract_registry_raw_links_finds_all_raw_links() -> None:
    text = (
        "| [✓](../raw/acme-widget-onboarding-spec.md) | "
        "[✓](../raw/acme-widget-onboarding-arch.md) |\n"
    )
    assert verify.extract_registry_raw_links(text) == {
        "acme-widget-onboarding-spec.md",
        "acme-widget-onboarding-arch.md",
    }


def test_extract_registry_raw_links_empty_text() -> None:
    assert verify.extract_registry_raw_links("") == set()


def test_snapshot_registry_links_filters_to_population_rule() -> None:
    text = (
        "[✓](../raw/acme-widget-onboarding-spec.md) "
        "[✓](../raw/notaproject-standalone-topic-ui.md)"
    )
    links = verify.snapshot_registry_links(text, _VALID_PREFIXES)
    assert links == {"acme-widget-onboarding-spec.md"}


# ── snapshot_population (raw/ 실측) ──────────────────────────────────────────


def test_snapshot_population_excludes_unregistered_prefix_boundary_case(
    fake_kompound_env: Dict[str, Any],
) -> None:
    """§6.3.1 CRITICAL 대응 회귀 테스트 — 프리픽스 미등록 파일이 raw/에
    물리적으로 존재해도(kind 접미사만 우연히 일치) 모집단 집계에서 제외된다.
    """
    kompound = fake_kompound_env["kompound"]
    population = verify.snapshot_population(kompound / "raw", _VALID_PREFIXES)
    assert "notaproject-standalone-topic-ui.md" not in population
    assert len(population) == _BASELINE_RAW_COUNT


def test_snapshot_population_missing_dir_returns_empty_set(tmp_path: Path) -> None:
    assert verify.snapshot_population(tmp_path / "does-not-exist", _VALID_PREFIXES) == set()


# ── 게이트 (1) 링크 무결성 ───────────────────────────────────────────────────


def test_gate1_passes_on_pristine_fixture(fake_kompound_env: Dict[str, Any]) -> None:
    kompound = fake_kompound_env["kompound"]
    prefix_map = fake_kompound_env["config"]["prefix_map"]
    result = verify.check_link_integrity(kompound, prefix_map)
    assert result["gate"] == verify.GATE_LINK_INTEGRITY
    assert result["ok"] is True
    for prefix in _VALID_PREFIXES:
        assert prefix in result["detail"]


def test_gate1_fails_on_broken_link_fixture(fake_kompound_env: Dict[str, Any]) -> None:
    """독립 실패 fixture — 끊긴 링크 1건(스냅샷 집합에 속하지만 실재하지
    않는 raw 파일을 registry가 가리킴)."""
    kompound = fake_kompound_env["kompound"]
    prefix_map = fake_kompound_env["config"]["prefix_map"]
    registry_path = kompound / "wiki" / "sdd-spec-registry.md"

    text = registry_path.read_text(encoding="utf-8")
    text += "\n[broken](../raw/acme-ghost-feature-spec.md)\n"
    registry_path.write_text(text, encoding="utf-8")

    result = verify.check_link_integrity(kompound, prefix_map)
    assert result["ok"] is False
    assert "acme-ghost-feature-spec.md" in result["detail"]


def test_gate1_ignores_broken_link_outside_snapshot_set(fake_kompound_env: Dict[str, Any]) -> None:
    """spec S-8 — 스냅샷 집합 밖(미등록 프리픽스) 링크가 깨져 있어도 게이트
    (1)은 실패하지 않는다(C-1과 동일 구조 함정 회피)."""
    kompound = fake_kompound_env["kompound"]
    prefix_map = fake_kompound_env["config"]["prefix_map"]
    registry_path = kompound / "wiki" / "sdd-spec-registry.md"

    text = registry_path.read_text(encoding="utf-8")
    # "notaproject"는 prefix_map.values() 밖 → 스냅샷 집합 밖 링크.
    text += "\n[broken, out of scope](../raw/notaproject-ghost-topic-ui.md)\n"
    registry_path.write_text(text, encoding="utf-8")

    result = verify.check_link_integrity(kompound, prefix_map)
    assert result["ok"] is True


# ── 게이트 (2) 양방향 카운트 일치 ────────────────────────────────────────────


def test_gate2_passes_on_pristine_fixture_despite_boundary_file_present(
    fake_kompound_env: Dict[str, Any],
) -> None:
    """모집단 한정이 실효적인가 — 경계 케이스 파일이 raw/에 물리적으로
    존재해도(§6.3.1) 게이트 (2)는 정상 통과한다(C-1 회귀 방지 핵심 테스트)."""
    kompound = fake_kompound_env["kompound"]
    prefix_map = fake_kompound_env["config"]["prefix_map"]
    assert any((kompound / "raw").glob("notaproject-*"))  # 경계 파일이 실제로 있음을 전제 확인

    result = verify.check_bidirectional_count(kompound, prefix_map)
    assert result["ok"] is True


def test_gate2_fails_on_count_mismatch_fixture_missing_link(
    fake_kompound_env: Dict[str, Any],
) -> None:
    """독립 실패 fixture — 카운트 불일치 1건: raw에는 있지만 registry에
    링크되지 않은 스냅샷 파일(이 훅의 존재 이유인 "빠짐"). 게이트 (1)에는
    영향 없음(등록된 링크는 전부 실재하므로)."""
    kompound = fake_kompound_env["kompound"]
    prefix_map = fake_kompound_env["config"]["prefix_map"]

    (kompound / "raw" / "acme-extra-feature-spec.md").write_text(
        "# extra feature (미링크)\n", encoding="utf-8"
    )

    gate1 = verify.check_link_integrity(kompound, prefix_map)
    assert gate1["ok"] is True  # 게이트 1은 영향 없음(등록된 링크만 검사)

    gate2 = verify.check_bidirectional_count(kompound, prefix_map)
    assert gate2["ok"] is False
    assert "acme-extra-feature-spec.md" in gate2["detail"]


def test_gate2_cross_case_equal_count_but_mismatched_sets(
    fake_kompound_env: Dict[str, Any],
) -> None:
    """교차 케이스 — 개수는 같고 집합은 어긋남(누락 링크 1건 + 유령 링크
    1건을 동시 주입). 단순 개수 비교였다면 통과했을 케이스를 양방향
    차집합 검사가 정확히 잡아야 한다."""
    kompound = fake_kompound_env["kompound"]
    prefix_map = fake_kompound_env["config"]["prefix_map"]
    registry_path = kompound / "wiki" / "sdd-spec-registry.md"

    # 유령 링크 1건 추가(파일 없음) + raw에 미링크 파일 1건 추가(누락) →
    # 링크 개수(7)와 raw 파일 개수(7)가 같아진다. 하지만 두 집합은 다르다.
    text = registry_path.read_text(encoding="utf-8")
    text += "\n[ghost](../raw/acme-phantom-feature-spec.md)\n"
    registry_path.write_text(text, encoding="utf-8")
    (kompound / "raw" / "beta-untracked-feature-arch.md").write_text(
        "# untracked (미링크)\n", encoding="utf-8"
    )

    rule = verify.snapshot_set_rule(prefix_map)
    links = verify.snapshot_registry_links(text, rule["prefixes"])
    files = verify.snapshot_population(kompound / "raw", rule["prefixes"])
    assert len(links) == len(files), "이 테스트의 전제(개수 동일)가 깨짐 — fixture 재확인 필요"
    assert links != files, "이 테스트의 전제(집합 불일치)가 깨짐 — fixture 재확인 필요"

    result = verify.check_bidirectional_count(kompound, prefix_map)
    assert result["ok"] is False
    assert "acme-phantom-feature-spec.md" in result["detail"]
    assert "beta-untracked-feature-arch.md" in result["detail"]


def test_gate2_prefix_map_null_removes_symmetrically_from_both_sides(
    fake_kompound_env: Dict[str, Any],
) -> None:
    """`prefix_map`에서 값이 `null`로 삭제된 프리픽스는 registry 링크·raw
    파일 양쪽에서 대칭적으로 제외되어 게이트가 여전히 통과한다."""
    kompound = fake_kompound_env["kompound"]
    prefix_map = dict(fake_kompound_env["config"]["prefix_map"])
    prefix_map["acme-widget"] = None  # "acme" 프리픽스를 유효 집합에서 제거

    rule = verify.snapshot_set_rule(prefix_map)
    assert "acme" not in rule["prefixes"]

    result = verify.check_bidirectional_count(kompound, prefix_map)
    assert result["ok"] is True  # acme 쪽 2개가 링크·파일 양쪽에서 동시에 빠짐


# ── 게이트 (3) flat 유지 ─────────────────────────────────────────────────────


def test_gate3_passes_on_pristine_fixture(fake_kompound_env: Dict[str, Any]) -> None:
    kompound = fake_kompound_env["kompound"]
    result = verify.check_flat_structure(kompound)
    assert result["ok"] is True


def test_gate3_allows_assets_subdir(fake_kompound_env: Dict[str, Any]) -> None:
    kompound = fake_kompound_env["kompound"]
    (kompound / "raw" / "assets").mkdir()
    result = verify.check_flat_structure(kompound)
    assert result["ok"] is True


def test_gate3_fails_on_rogue_subdirectory_fixture(fake_kompound_env: Dict[str, Any]) -> None:
    """독립 실패 fixture — raw/ 하위 서브디렉토리 1건 주입. 게이트 (1)(2)에는
    영향 없음(파일 순회 대상이 아니므로)."""
    kompound = fake_kompound_env["kompound"]
    prefix_map = fake_kompound_env["config"]["prefix_map"]
    (kompound / "raw" / "rogue_subdir").mkdir()
    (kompound / "raw" / "rogue_subdir" / "file.md").write_text("x\n", encoding="utf-8")

    gate1 = verify.check_link_integrity(kompound, prefix_map)
    gate2 = verify.check_bidirectional_count(kompound, prefix_map)
    assert gate1["ok"] is True
    assert gate2["ok"] is True

    gate3 = verify.check_flat_structure(kompound)
    assert gate3["ok"] is False
    assert "rogue_subdir" in gate3["detail"]


def test_gate3_missing_raw_dir_passes(tmp_path: Path) -> None:
    """raw/ 자체가 없으면(비정상이지만) 서브디렉토리도 없으므로 통과 —
    다른 게이트가 이 상황을 별도로 취급한다."""
    result = verify.check_flat_structure(tmp_path)
    assert result["ok"] is True


# ── run_gates / should_run_gates — 실행 여부 판단과 실행의 분리 ─────────────


def test_should_run_gates_false_when_no_new_or_updated() -> None:
    assert verify.should_run_gates({"new": [], "updated": []}) is False


def test_should_run_gates_true_when_new_present() -> None:
    assert verify.should_run_gates({"new": ["raw/x-y-spec.md"], "updated": []}) is True


def test_should_run_gates_true_when_updated_present() -> None:
    assert verify.should_run_gates({"new": [], "updated": ["raw/x-y-spec.md"]}) is True


def test_should_run_gates_defaults_true_when_none() -> None:
    assert verify.should_run_gates(None) is True


def test_should_run_gates_defaults_true_on_malformed_shape() -> None:
    assert verify.should_run_gates(["not", "a", "mapping"]) is True  # type: ignore[arg-type]


def test_run_gates_not_called_when_should_run_gates_is_false(tmp_path: Path) -> None:
    """박제 0건 케이스에서 3개 게이트 함수가 호출되지 않음(mock call count 0)
    — T-10(apply.py)이 이 두 함수(should_run_gates/run_gates)를 조합해
    스킵을 결정할 수 있음을 증명하는 오케스트레이션 계약 테스트."""
    with patch.object(verify, "check_link_integrity") as m1, patch.object(
        verify, "check_bidirectional_count"
    ) as m2, patch.object(verify, "check_flat_structure") as m3:
        raw_stage = {"new": [], "updated": []}
        if verify.should_run_gates(raw_stage):
            verify.run_gates(tmp_path, {})

        m1.assert_not_called()
        m2.assert_not_called()
        m3.assert_not_called()


def test_run_gates_called_exactly_once_each_when_should_run_gates_is_true(
    tmp_path: Path,
) -> None:
    with patch.object(verify, "check_link_integrity") as m1, patch.object(
        verify, "check_bidirectional_count"
    ) as m2, patch.object(verify, "check_flat_structure") as m3:
        m1.return_value = {"gate": verify.GATE_LINK_INTEGRITY, "ok": True, "detail": ""}
        m2.return_value = {"gate": verify.GATE_BIDIRECTIONAL_COUNT, "ok": True, "detail": ""}
        m3.return_value = {"gate": verify.GATE_FLAT_STRUCTURE, "ok": True, "detail": ""}

        raw_stage = {"new": ["raw/x-y-spec.md"], "updated": []}
        result: List[Dict[str, Any]] = []
        if verify.should_run_gates(raw_stage):
            result = verify.run_gates(tmp_path, {})

        m1.assert_called_once()
        m2.assert_called_once()
        m3.assert_called_once()
        assert len(result) == 3


def test_run_gates_all_pass_on_pristine_fixture_and_returns_contract_shape(
    fake_kompound_env: Dict[str, Any],
) -> None:
    kompound = fake_kompound_env["kompound"]
    prefix_map = fake_kompound_env["config"]["prefix_map"]

    results = verify.run_gates(kompound, prefix_map)

    assert len(results) == 3
    assert {r["gate"] for r in results} == {
        verify.GATE_LINK_INTEGRITY,
        verify.GATE_BIDIRECTIONAL_COUNT,
        verify.GATE_FLAT_STRUCTURE,
    }
    for r in results:
        assert set(r.keys()) == {"gate", "ok", "detail"}
        assert r["ok"] is True


def test_run_gates_never_raises_on_completely_missing_kompound_repo(tmp_path: Path) -> None:
    """예외 없이 항상 구조화된 반환 — kompound_repo 자체가 없어도 게이트는
    구조화된 실패를 반환하지, 예외를 던지지 않는다."""
    missing = tmp_path / "does-not-exist"
    results = verify.run_gates(missing, {"a": "acme"})
    assert len(results) == 3
    for r in results:
        assert set(r.keys()) == {"gate", "ok", "detail"}
        assert isinstance(r["ok"], bool)


def test_run_gates_never_raises_with_malformed_prefix_map(fake_kompound_env: Dict[str, Any]) -> None:
    kompound = fake_kompound_env["kompound"]
    results = verify.run_gates(kompound, "not-a-mapping")  # type: ignore[arg-type]
    assert len(results) == 3
    for r in results:
        assert isinstance(r["ok"], bool)


# ── build_verify_report — 프리픽스 목록을 항상 함께 노출하는 조립 함수 ─────


def test_build_verify_report_exposes_prefixes_and_preserves_gate_contract(
    fake_kompound_env: Dict[str, Any],
) -> None:
    kompound = fake_kompound_env["kompound"]
    prefix_map = fake_kompound_env["config"]["prefix_map"]

    report = verify.build_verify_report(kompound, prefix_map)

    assert set(report.keys()) == {"prefixes", "gates"}
    assert set(report["prefixes"]) == set(_VALID_PREFIXES)
    assert len(report["gates"]) == 3
    for r in report["gates"]:
        assert set(r.keys()) == {"gate", "ok", "detail"}
        assert r["ok"] is True


def test_build_verify_report_never_raises(tmp_path: Path) -> None:
    report = verify.build_verify_report(tmp_path / "nope", None)
    assert "prefixes" in report and "gates" in report
    assert len(report["gates"]) == 3
