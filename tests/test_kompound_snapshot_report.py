"""tests/test_kompound_snapshot_report.py

T-6 (SDD Phase 4, kompound-snapshot-hook) — F11 verdict/종료 코드/리포트
(`report.py`) 단위 테스트. arch §6.2(CLI 종료 코드 규약 — 단일 진실)와
§5.2.4(3축 원칙 — 어느 verdict가 차단/통과인지)를 고정한다.

`report.py`가 정의하는 종료 코드 상수·단계(stage)·차단 여부(blocks_deletion)는
T-10(`apply.py`)·T-11(`cli.py`)·T-13(bash 게이트)이 그대로 참조하는 계약이므로,
이 테스트는 값 자체(숫자·이름)를 정확히 고정한다.
"""

from __future__ import annotations

import io
import json
from typing import Any, Dict

import pytest

from hooks.lib.kompound_snapshot import report


# ── 종료 코드 상수 값 자체 고정 (arch §6.2 표) ─────────────────────────


def test_exit_code_constants_match_arch_table() -> None:
    assert report.EXIT_OK == 0
    assert report.EXIT_PENDING == 10
    assert report.EXIT_DISABLED == 20
    assert report.EXIT_SCAN_ERROR == 30
    assert report.EXIT_PRECONDITION_FAILED == 40
    assert report.EXIT_UNMAPPED_BLOCKING == 45
    assert report.EXIT_VERIFY_FAILED == 50
    assert report.EXIT_CATALOG_UNPARSED == 55
    assert report.EXIT_WRITE_FAILED == 60
    assert report.EXIT_BUSY == 70


def test_exit_codes_1_and_2_are_never_used_by_any_verdict() -> None:
    used_codes = {entry["exit_code"] for entry in report.VERDICT_TABLE.values()}
    assert 1 not in used_codes
    assert 2 not in used_codes


# ── 전 verdict × exit_code 매핑 정확성 (파라미터화, arch §6.2) ──────────


@pytest.mark.parametrize(
    "verdict,expected_exit_code",
    [
        ("ok_no_pending", 0),
        ("snapshotted", 0),
        ("no_target", 0),
        ("pending", 10),
        ("disabled", 20),
        ("scan_error", 30),
        ("precondition_failed", 40),
        ("unmapped_blocking", 45),
        ("verify_failed", 50),
        ("catalog_unparsed", 55),
        ("write_failed", 60),
        ("busy", 70),
    ],
)
def test_exit_code_for_verdict_matches_table(verdict: str, expected_exit_code: int) -> None:
    assert report.exit_code_for_verdict(verdict) == expected_exit_code


def test_unknown_verdict_falls_back_to_scan_error_not_silently_zero() -> None:
    """F11 정신 — 모르는 verdict를 조용히 0(성공)으로 취급하면 안 된다."""
    assert report.exit_code_for_verdict("totally_unknown_verdict") == report.EXIT_SCAN_ERROR
    assert report.stage_for_verdict("totally_unknown_verdict") == report.STAGE_SCAN
    assert report.blocks_deletion("totally_unknown_verdict") is True


# ── 단계(stage) 분류 정확성 — arch A-5 (ii)만 통과, 그 외 실패는 차단 ────


@pytest.mark.parametrize(
    "verdict,expected_stage",
    [
        ("ok_no_pending", report.STAGE_NONE),
        ("snapshotted", report.STAGE_NONE),
        ("no_target", report.STAGE_NONE),
        ("pending", report.STAGE_NONE),
        ("disabled", report.STAGE_NONE),
        ("scan_error", report.STAGE_SCAN),
        ("precondition_failed", report.STAGE_PRECONDITION),
        ("unmapped_blocking", report.STAGE_PRECONDITION),
        ("verify_failed", report.STAGE_CATALOG),
        ("catalog_unparsed", report.STAGE_CATALOG),
        ("write_failed", report.STAGE_RAW),
        ("busy", report.STAGE_LOCK),
    ],
)
def test_stage_for_verdict_matches_arch_a5(verdict: str, expected_stage: str) -> None:
    assert report.stage_for_verdict(verdict) == expected_stage


@pytest.mark.parametrize(
    "verdict,expected_blocks",
    [
        ("ok_no_pending", False),
        ("snapshotted", False),
        ("no_target", False),
        ("pending", False),
        ("disabled", False),
        ("scan_error", True),
        ("precondition_failed", True),
        ("unmapped_blocking", True),
        ("verify_failed", False),  # (ii) 실패 — 카탈로그 정합성만, 통과(경고)
        ("catalog_unparsed", False),  # (ii) 실패 — 통과(경고)
        ("write_failed", True),  # (i) 실패 — raw가 없다, 차단
        ("busy", True),
    ],
)
def test_blocks_deletion_matches_arch_axis_1_vs_3(verdict: str, expected_blocks: bool) -> None:
    assert report.blocks_deletion(verdict) is expected_blocks


def test_raw_stage_failure_blocks_but_catalog_stage_failure_does_not() -> None:
    """T-6 보고의 핵심 계약 — (i) 실패(write_failed)는 차단, (ii) 실패
    (verify_failed/catalog_unparsed)는 통과. 이 한 쌍이 A-5의 축을 대표한다.
    """
    assert report.stage_for_verdict("write_failed") == report.STAGE_RAW
    assert report.blocks_deletion("write_failed") is True

    for catalog_verdict in ("verify_failed", "catalog_unparsed"):
        assert report.stage_for_verdict(catalog_verdict) == report.STAGE_CATALOG
        assert report.blocks_deletion(catalog_verdict) is False


# ── JSON 스키마 필드 존재 (arch §6.2) ───────────────────────────────────


_EXPECTED_TOP_LEVEL_KEYS = {
    "verdict",
    "exit_code",
    "config_source",
    "scope_roots",
    "anchors",
    "raw_stage",
    "catalog_stage",
    "unmapped",
    "pending",
    "dirty",
    "errors",
    "runtime_status",
    "catalog_lag_count",
    "inherited_warning",
    "human",
}

_EXPECTED_RAW_STAGE_KEYS = {"ok", "new", "updated", "unchanged", "committed", "commit", "error"}
_EXPECTED_CATALOG_STAGE_KEYS = {
    "ok",
    "attempted",
    "registry",
    "index",
    "log",
    "committed",
    "commit",
    "failed_gates",
    "unparsed",
    "error",
}


def test_build_report_has_exact_top_level_schema_keys() -> None:
    result = report.build_report(verdict="ok_no_pending")
    assert set(result.keys()) == _EXPECTED_TOP_LEVEL_KEYS


def test_build_report_default_raw_stage_and_catalog_stage_schema() -> None:
    result = report.build_report(verdict="ok_no_pending")
    assert set(result["raw_stage"].keys()) == _EXPECTED_RAW_STAGE_KEYS
    assert set(result["catalog_stage"].keys()) == _EXPECTED_CATALOG_STAGE_KEYS


def test_build_report_exit_code_derived_from_verdict() -> None:
    result = report.build_report(verdict="write_failed")
    assert result["exit_code"] == report.EXIT_WRITE_FAILED


def test_build_report_never_raises_on_bad_verdict() -> None:
    result = report.build_report(verdict=object())  # type: ignore[arg-type]
    assert result["exit_code"] == report.EXIT_SCAN_ERROR
    assert isinstance(result["human"], str)


# ── raw_stage / catalog_stage 독립성 (A-5 — 합치면 회귀) ────────────────


def test_raw_stage_and_catalog_stage_are_independent_fields() -> None:
    """`raw_stage.ok=True` + `catalog_stage.ok=False`가 "문서는 보존, 카탈로그만
    실패"를 표현하는 유일한 방법 — 두 값이 서로 간섭하지 않아야 한다.
    """
    raw_stage = {
        "ok": True,
        "new": ["a-b-spec.md"],
        "updated": [],
        "unchanged": 3,
        "committed": True,
        "commit": "abc1234",
        "error": "",
    }
    catalog_stage = {
        "ok": False,
        "attempted": True,
        "registry": False,
        "index": False,
        "log": False,
        "committed": False,
        "commit": None,
        "failed_gates": ["link_integrity"],
        "unparsed": None,
        "error": "gate failed",
    }
    result = report.build_report(
        verdict="verify_failed",
        raw_stage=raw_stage,
        catalog_stage=catalog_stage,
    )
    assert result["raw_stage"]["ok"] is True
    assert result["raw_stage"]["committed"] is True
    assert result["catalog_stage"]["ok"] is False
    assert result["catalog_stage"]["failed_gates"] == ["link_integrity"]
    # 필드가 서로 오염되지 않았는지(카탈로그 값이 raw_stage로 새지 않음)
    assert "failed_gates" not in result["raw_stage"]


def test_build_report_preserves_raw_stage_input_unmutated() -> None:
    raw_stage = {
        "ok": True,
        "new": [],
        "updated": [],
        "unchanged": 0,
        "committed": False,
        "commit": None,
        "error": "",
    }
    original = dict(raw_stage)
    report.build_report(verdict="ok_no_pending", raw_stage=raw_stage)
    assert raw_stage == original


# ── inherited_warning — 3형태 (failure / info / null) ───────────────────


@pytest.mark.parametrize("runtime_status", ["FAILED", "GIVEN_UP"])
def test_build_inherited_warning_failure_tone(runtime_status: str) -> None:
    warning = report.build_inherited_warning(runtime_status, reason="write error")
    assert warning["kind"] == "failure"
    assert "write error" in warning["text"]
    assert isinstance(warning["text"], str) and warning["text"]


def test_build_inherited_warning_info_tone_for_catalog_pending() -> None:
    warning = report.build_inherited_warning("CATALOG_PENDING", catalog_lag_count=3)
    assert warning["kind"] == "info"
    assert "3" in warning["text"]
    assert "안전" in warning["text"]


@pytest.mark.parametrize(
    "runtime_status", ["DONE", "PENDING", "SKIPPED_UNCONFIGURED", "unknown_status"]
)
def test_build_inherited_warning_null_for_non_inherited_statuses(runtime_status: str) -> None:
    warning = report.build_inherited_warning(runtime_status)
    assert warning["kind"] is None
    assert warning["text"] == ""


def test_inherited_warning_is_always_an_object_never_a_bare_string() -> None:
    for status in ("FAILED", "GIVEN_UP", "CATALOG_PENDING", "DONE"):
        warning = report.build_inherited_warning(status)
        assert isinstance(warning, dict)
        assert set(warning.keys()) == {"kind", "text"}


def test_build_report_passes_through_inherited_warning_object() -> None:
    warning = report.build_inherited_warning("CATALOG_PENDING", catalog_lag_count=2)
    result = report.build_report(verdict="snapshotted", inherited_warning=warning)
    assert result["inherited_warning"] == warning
    assert isinstance(result["inherited_warning"], dict)


def test_build_report_default_inherited_warning_is_null_object() -> None:
    result = report.build_report(verdict="ok_no_pending")
    assert result["inherited_warning"] == {"kind": None, "text": ""}


# ── F11 — "변경 없음" vs "스캔 실패" 구분 ───────────────────────────────


def test_no_changes_and_scan_failure_are_distinct_verdicts_and_exit_codes() -> None:
    no_changes = report.build_report(verdict="ok_no_pending")
    scan_failure = report.build_report(verdict="scan_error", errors=["disk read error"])

    assert no_changes["exit_code"] != scan_failure["exit_code"]
    assert no_changes["verdict"] != scan_failure["verdict"]
    assert no_changes["exit_code"] == report.EXIT_OK
    assert scan_failure["exit_code"] == report.EXIT_SCAN_ERROR
    assert scan_failure["errors"] == ["disk read error"]
    assert no_changes["errors"] == []


def test_no_changes_human_text_differs_from_scan_failure_human_text() -> None:
    no_changes = report.build_report(verdict="ok_no_pending")
    scan_failure = report.build_report(verdict="scan_error")
    assert no_changes["human"] != scan_failure["human"]
    assert "차단" in scan_failure["human"]
    assert "차단" not in no_changes["human"]


# ── pending[] / unmapped[] 배타성 (F12/§5.1.3 J-11) ─────────────────────


def test_pending_unmapped_disjoint_true_for_disjoint_lists() -> None:
    assert report.pending_unmapped_disjoint(["a-b-spec.md"], ["c-d-ui.md"]) is True


def test_pending_unmapped_disjoint_false_when_overlapping() -> None:
    assert report.pending_unmapped_disjoint(["a-b-spec.md"], ["a-b-spec.md"]) is False


def test_build_report_keeps_pending_and_unmapped_separate_no_cross_mixing() -> None:
    result = report.build_report(
        verdict="unmapped_blocking",
        pending=["mapped-doc-spec.md"],
        unmapped=["unmapped-doc-ui.md"],
    )
    assert result["pending"] == ["mapped-doc-spec.md"]
    assert result["unmapped"] == ["unmapped-doc-ui.md"]
    assert report.pending_unmapped_disjoint(result["pending"], result["unmapped"]) is True


# ── human 텍스트 3요소 (차단 케이스) / 보존·잔여 (축 3 통과 케이스) ──────


@pytest.mark.parametrize(
    "verdict", ["scan_error", "precondition_failed", "unmapped_blocking", "write_failed", "busy"]
)
def test_blocking_human_text_has_three_required_elements(verdict: str) -> None:
    text = report.build_human_text(verdict)
    assert "차단" in text  # 무엇이 왜 막혔는가
    assert "수동 절차" in text  # 수동 절차
    assert "HARNESS_KOMPOUND_REPO" in text  # 끄는 방법


@pytest.mark.parametrize("verdict", ["verify_failed", "catalog_unparsed"])
def test_axis3_pass_human_text_states_what_is_preserved_and_pending(verdict: str) -> None:
    raw_stage = {
        "ok": True,
        "new": ["a-spec.md"],
        "updated": ["b-arch.md"],
        "unchanged": 0,
        "committed": True,
        "commit": "deadbee",
        "error": "",
    }
    text = report.build_human_text(verdict, raw_stage=raw_stage)
    assert "복사·커밋 완료" in text
    assert "재시도" in text
    assert "안전" in text
    assert "차단" not in text


def test_pass_verdicts_have_no_three_element_block_text() -> None:
    for verdict in ("ok_no_pending", "snapshotted", "no_target", "disabled"):
        text = report.build_human_text(verdict)
        assert "차단" not in text


def test_build_human_text_never_raises() -> None:
    text = report.build_human_text(None)  # type: ignore[arg-type]
    assert isinstance(text, str)


# ── stdout/stderr 라우팅 (arch §6.2 확정 계약) ─────────────────────────


def test_emit_report_json_mode_writes_single_line_json_to_stdout() -> None:
    result = report.build_report(verdict="snapshotted")
    out = io.StringIO()
    err = io.StringIO()
    exit_code = report.emit_report(result, json_mode=True, stdout=out, stderr=err)

    assert exit_code == report.EXIT_OK
    lines = out.getvalue().splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["verdict"] == "snapshotted"
    # human 리포트는 stderr로 간다
    assert err.getvalue().strip() != ""


def test_emit_report_default_mode_writes_human_to_stdout() -> None:
    result = report.build_report(verdict="ok_no_pending")
    out = io.StringIO()
    err = io.StringIO()
    exit_code = report.emit_report(result, json_mode=False, stdout=out, stderr=err)

    assert exit_code == report.EXIT_OK
    assert result["human"] in out.getvalue()
    # inherited_warning이 없으면 기본 모드 stderr는 비어 있다
    assert err.getvalue() == ""


def test_emit_report_default_mode_warns_on_inherited_warning() -> None:
    warning = report.build_inherited_warning("CATALOG_PENDING", catalog_lag_count=1)
    result = report.build_report(verdict="snapshotted", inherited_warning=warning)
    out = io.StringIO()
    err = io.StringIO()
    report.emit_report(result, json_mode=False, stdout=out, stderr=err)
    assert err.getvalue().strip() != ""


def test_emit_report_never_raises_even_with_broken_streams() -> None:
    class _BrokenStream:
        def write(self, _text: str) -> int:
            raise OSError("broken pipe")

    result = report.build_report(verdict="ok_no_pending")
    exit_code = report.emit_report(
        result, json_mode=True, stdout=_BrokenStream(), stderr=_BrokenStream()  # type: ignore[arg-type]
    )
    assert exit_code == report.EXIT_OK


# ── VERDICT_TABLE 완전성 — T-10/T-11/T-13이 의존하는 이름 자체 고정 ──────


def test_verdict_table_contains_exactly_the_arch_verdicts() -> None:
    expected_verdicts = {
        "ok_no_pending",
        "snapshotted",
        "no_target",
        "pending",
        "disabled",
        "scan_error",
        "precondition_failed",
        "unmapped_blocking",
        "verify_failed",
        "catalog_unparsed",
        "write_failed",
        "busy",
    }
    assert set(report.VERDICT_TABLE.keys()) == expected_verdicts


def test_runtime_statuses_tuple_matches_arch_5_1_2_value_set() -> None:
    assert set(report.RUNTIME_STATUSES) == {
        "PENDING",
        "CATALOG_PENDING",
        "DONE",
        "SKIPPED_UNCONFIGURED",
        "FAILED",
        "GIVEN_UP",
    }
