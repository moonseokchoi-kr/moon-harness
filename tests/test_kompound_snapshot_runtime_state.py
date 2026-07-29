"""tests/test_kompound_snapshot_runtime_state.py — T-7 (F1 런타임 상태) GREEN 테스트.

설계 SSOT: `docs/sdd/design/arch/2026-07-29-kompound-snapshot-hook.md` §5.1.2~
§5.1.4, §6.1 ④. task: `docs/sdd/task/kompound-snapshot-hook/2026-07-29-T-7-runtime-state.md`.

전부 `tmp_path` 기반이다 — 실제 `.claude/state/`를 절대 건드리지 않는다.
`project_root`는 매 테스트가 `tmp_path` 아래 새로 만드는 가짜 프로젝트
디렉토리이고, `ORCHESTRATOR_STATE.md`도 그 안에 직접 써 넣는다(실제
moon-harness의 STATE가 아니다).
"""

from __future__ import annotations

import os
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import pytest

from hooks.lib.kompound_snapshot import report, runtime_state


# ── 헬퍼 ─────────────────────────────────────────────────────────────────────


def _make_project(tmp_path: Path, name: str = "project") -> Path:
    root = tmp_path / name
    root.mkdir(parents=True, exist_ok=True)
    return root


def _write_state_md(
    project_root: Path,
    *,
    feature: str = "test-feature",
    status: str = "COMPLETED",
    backtick_feature: bool = True,
    status_label: str = "상태",
) -> Path:
    path = project_root / "docs" / "sdd" / "ORCHESTRATOR_STATE.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    feature_line = f"- feature: `{feature}`" if backtick_feature else f"- feature: {feature}"
    status_line = f"- {status_label}: {status} (부가 설명 텍스트)"
    path.write_text(
        "# Orchestrator State\n\n## 메타\n" + feature_line + "\n" + status_line + "\n",
        encoding="utf-8",
    )
    return path


def _touch_mtime(path: Path, *, hours_ago: float) -> None:
    target = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).timestamp()
    os.utime(path, (target, target))


def _seed_result_doc(project_root: Path, feature: str, date: str = "2026-07-29") -> Path:
    result_dir = project_root / "docs" / "sdd" / "result"
    result_dir.mkdir(parents=True, exist_ok=True)
    doc = result_dir / f"{date}-{feature}.md"
    doc.write_text("# result\n", encoding="utf-8")
    return doc


def _decide(
    project_root: Path,
    state_path: Path,
    *,
    config_ok: bool = True,
    pending_count: int = 1,
    unmapped_count: int = 0,
    session_id: Optional[str] = "session-A",
    now: Optional[datetime] = None,
):
    return runtime_state.record_and_decide(
        project_root,
        state_path,
        config_ok=config_ok,
        pending_count=pending_count,
        unmapped_count=unmapped_count,
        session_id=session_id,
        now=now,
    )


# ── 상수 ─────────────────────────────────────────────────────────────────────


def test_constants_match_arch_confirmed_values() -> None:
    assert runtime_state.KOMPOUND_MAX_BLOCKS == 3
    assert runtime_state.DEFAULT_STATE_MAX_AGE_HOURS == 24
    assert runtime_state.STATUSES == (
        "PENDING",
        "CATALOG_PENDING",
        "DONE",
        "SKIPPED_UNCONFIGURED",
        "FAILED",
        "GIVEN_UP",
    )


def test_runtime_statuses_match_report_module() -> None:
    """report.RUNTIME_STATUSES와 이 모듈의 상수 이름이 정확히 일치해야 한다
    (T-11 통합의 전제, 두 모듈은 병렬 구현이라 서로 import하지 않는다)."""
    assert runtime_state.STATUSES == report.RUNTIME_STATUSES


def test_state_path_for_is_distinct_from_config_path() -> None:
    root = Path("/tmp/does-not-need-to-exist")
    state_path = runtime_state.state_path_for(root)
    assert state_path == root / ".claude" / "state" / "kompound-snapshot.json"
    assert "kompound-snapshot.config.json" not in str(state_path)


# ── STATE 파서 ───────────────────────────────────────────────────────────────


def test_parse_orchestrator_state_dash_form() -> None:
    text = "- feature: `my-feature`\n- 상태: COMPLETED (주석)\n"
    parsed = runtime_state.parse_orchestrator_state(text)
    assert parsed == {"feature": "my-feature", "status": "COMPLETED"}


def test_parse_orchestrator_state_status_label_form() -> None:
    text = "feature: other-feature\nstatus: EXECUTING\n"
    parsed = runtime_state.parse_orchestrator_state(text)
    assert parsed["status"] == "EXECUTING"
    assert parsed["feature"] == "other-feature"


def test_parse_orchestrator_state_missing_labels_returns_none() -> None:
    parsed = runtime_state.parse_orchestrator_state("# nothing here\n")
    assert parsed == {"feature": None, "status": None}


# ── STATE 신선도 ─────────────────────────────────────────────────────────────


def test_is_state_fresh_true_for_recent_file(tmp_path: Path) -> None:
    f = tmp_path / "STATE.md"
    f.write_text("x", encoding="utf-8")
    assert runtime_state.is_state_fresh(f, 24) is True


def test_is_state_fresh_false_for_old_file(tmp_path: Path) -> None:
    f = tmp_path / "STATE.md"
    f.write_text("x", encoding="utf-8")
    _touch_mtime(f, hours_ago=30)
    assert runtime_state.is_state_fresh(f, 24) is False


def test_is_state_fresh_false_for_missing_file(tmp_path: Path) -> None:
    assert runtime_state.is_state_fresh(tmp_path / "nope.md", 24) is False


# ── 서명 ─────────────────────────────────────────────────────────────────────


def test_compute_signature_includes_latest_result_doc(tmp_path: Path) -> None:
    root = _make_project(tmp_path)
    _seed_result_doc(root, "my-feature", date="2026-07-29")
    text = "- feature: `my-feature`\n- 상태: COMPLETED\n"
    sig = runtime_state.compute_signature(root, text)
    assert sig[0] == "my-feature"
    assert sig[1] == "COMPLETED"
    assert sig[2] is not None and sig[2].endswith("2026-07-29-my-feature.md")


def test_compute_signature_none_result_doc_when_absent(tmp_path: Path) -> None:
    root = _make_project(tmp_path)
    text = "- feature: `ghost-feature`\n- 상태: COMPLETED\n"
    sig = runtime_state.compute_signature(root, text)
    assert sig == ["ghost-feature", "COMPLETED", None]


# ── 무장 판정 — 첫 관측 / 미신선 / 상태!=COMPLETED ──────────────────────────


def test_first_observation_registers_baseline_without_firing(tmp_path: Path) -> None:
    root = _make_project(tmp_path)
    state_path = _write_state_md(root, status="COMPLETED")
    result = _decide(root, state_path, pending_count=5)
    assert result["action"] == "pass"
    assert result["reason"] == "baseline_registered"


def test_known_miss_first_observation_already_completed_never_fires(tmp_path: Path) -> None:
    """§5.1.3 알려진 미탐 — 세션의 첫 Stop 훅이 이미 COMPLETED를 본 경우
    baseline=COMPLETED가 되어 T1이 발화하지 않는다(문서화된 동작)."""
    root = _make_project(tmp_path)
    state_path = _write_state_md(root, status="COMPLETED")
    first = _decide(root, state_path, pending_count=5)
    assert first["reason"] == "baseline_registered"
    second = _decide(root, state_path, pending_count=5)
    assert second["action"] == "pass"
    assert second["reason"] == "signature_unchanged"


def test_state_stale_does_not_arm_but_updates_baseline(tmp_path: Path) -> None:
    root = _make_project(tmp_path)
    # 1) 비완료 상태로 baseline 등록(첫 관측)
    state_path = _write_state_md(root, status="EXECUTING")
    _decide(root, state_path, pending_count=5)
    # 2) COMPLETED로 전환하되 mtime을 오래된 것으로 위조
    _write_state_md(root, status="COMPLETED")
    _touch_mtime(state_path, hours_ago=48)
    result = _decide(root, state_path, pending_count=5)
    assert result["action"] == "pass"
    assert result["reason"] == "state_stale"


def test_state_not_completed_passes_through_and_updates_baseline(tmp_path: Path) -> None:
    root = _make_project(tmp_path)
    state_path = _write_state_md(root, status="EXECUTING")
    first = _decide(root, state_path, pending_count=5)
    assert first["reason"] == "baseline_registered"
    # 여전히 EXECUTING (서명이 이미 baseline과 같음) — "무장 안됨" 계열.
    # 상태!=COMPLETED가 signature_unchanged보다 먼저 검사되므로(구현 순서),
    # 두 조건이 동시에 성립해도 reason은 "state_not_completed"로 보고된다 —
    # 어느 쪽이든 동작(pass + baseline 갱신)은 동일하다.
    second = _decide(root, state_path, pending_count=5)
    assert second["action"] == "pass"
    assert second["reason"] == "state_not_completed"


# ── 무장됨 — config / pending==0 / CATALOG_PENDING / pending>=1 ────────────


def test_armed_but_config_unresolved_yields_skipped_unconfigured(tmp_path: Path) -> None:
    root = _make_project(tmp_path)
    state_path = _write_state_md(root, status="EXECUTING")
    _decide(root, state_path, pending_count=0)  # baseline 등록(비완료)
    _write_state_md(root, status="COMPLETED")
    result = _decide(root, state_path, config_ok=False, pending_count=5)
    assert result["action"] == "pass"
    assert result["reason"] == "config_unconfigured"
    assert result["status"] == runtime_state.SKIPPED_UNCONFIGURED


def test_armed_pending_zero_yields_done(tmp_path: Path) -> None:
    root = _make_project(tmp_path)
    state_path = _write_state_md(root, status="EXECUTING")
    _decide(root, state_path, pending_count=0)
    _write_state_md(root, status="COMPLETED")
    result = _decide(root, state_path, pending_count=0, unmapped_count=7)
    assert result["action"] == "pass"
    assert result["reason"] == "no_pending"
    assert result["status"] == runtime_state.DONE


def _arm_to_completed(root: Path, session_id: str = "session-A") -> Path:
    """비완료 → COMPLETED 전환까지 마쳐 "armed" 판정 직전 상태로 만든다."""
    state_path = _write_state_md(root, status="EXECUTING")
    _decide(root, state_path, pending_count=1, session_id=session_id)
    _write_state_md(root, status="COMPLETED")
    return state_path


def test_catalog_pending_passthrough_before_pending_zero_check(tmp_path: Path) -> None:
    """D-1 핵심 회귀: 직전 상태가 CATALOG_PENDING이면 pending==0이 되어도
    DONE으로 덮이지 않고 CATALOG_PENDING이 그대로 보존돼야 한다."""
    root = _make_project(tmp_path)
    state_path = _arm_to_completed(root)
    # 실제 흐름에서 apply()는 항상 directive(=block 결정) 뒤에 실행되므로,
    # 먼저 한 번 정상 block을 거쳐 이 사이클의 armed_signature를 확정한다.
    _decide(root, state_path, pending_count=1)
    # apply()가 (i) 성공 + (ii) 실패를 했다고 기록 — CATALOG_PENDING 진입.
    runtime_state.record_apply_outcome(root, raw_ok=True, catalog_ok=False)

    # (i)가 성공했으므로 다음 스캔에서 pending이 0으로 재계산된 상황을
    # 시뮬레이션한다 — 이 경우에도 CATALOG_PENDING이 보존돼야 한다.
    result = _decide(root, state_path, pending_count=0)
    assert result["action"] == "pass"
    assert result["reason"] == "catalog_pending_passthrough"
    assert result["status"] == runtime_state.CATALOG_PENDING


def test_catalog_pending_passthrough_does_not_increment_blocks(tmp_path: Path) -> None:
    """arch D-1 핵심 회귀: CATALOG_PENDING은 DONE과 동일하게 통과 처리되며
    block 전후 `blocks` 값이 절대 증가하지 않는다."""
    root = _make_project(tmp_path)
    state_path = _arm_to_completed(root)
    _decide(root, state_path, pending_count=1)
    runtime_state.record_apply_outcome(root, raw_ok=True, catalog_ok=False)

    before = _decide(root, state_path, pending_count=3)
    assert before["action"] == "pass"
    assert before["reason"] == "catalog_pending_passthrough"
    blocks_before = before["blocks"]

    after = _decide(root, state_path, pending_count=3)
    assert after["action"] == "pass"
    assert after["reason"] == "catalog_pending_passthrough"
    blocks_after = after["blocks"]

    assert blocks_before == blocks_after


def test_catalog_pending_checked_before_condition_four(tmp_path: Path) -> None:
    """CATALOG_PENDING 검사가 조건 4(pending>=1)보다 먼저 일어난다 — pending
    이 여전히 1 이상이어도 CATALOG_PENDING이면 block으로 흐르지 않는다."""
    root = _make_project(tmp_path)
    state_path = _arm_to_completed(root)
    _decide(root, state_path, pending_count=1)
    blocks_before_apply = _decide(root, state_path, pending_count=1)["blocks"]
    runtime_state.record_apply_outcome(root, raw_ok=True, catalog_ok=False)

    result = _decide(root, state_path, pending_count=99)
    assert result["action"] == "pass"
    assert result["status"] == runtime_state.CATALOG_PENDING
    assert result["blocks"] == blocks_before_apply


def test_catalog_pending_transitions_to_done_on_catalog_success(tmp_path: Path) -> None:
    root = _make_project(tmp_path)
    _arm_to_completed(root)
    runtime_state.record_apply_outcome(root, raw_ok=True, catalog_ok=False)
    outcome = runtime_state.record_apply_outcome(root, raw_ok=True, catalog_ok=True)
    assert outcome["status"] == runtime_state.DONE
    assert outcome["catalog_lag_count"] == 0


def test_record_apply_outcome_raw_failure_yields_pending(tmp_path: Path) -> None:
    root = _make_project(tmp_path)
    outcome = runtime_state.record_apply_outcome(root, raw_ok=False, catalog_ok=False)
    assert outcome["status"] == runtime_state.PENDING


def test_record_apply_outcome_catalog_failure_increments_lag_count(tmp_path: Path) -> None:
    root = _make_project(tmp_path)
    first = runtime_state.record_apply_outcome(root, raw_ok=True, catalog_ok=False)
    assert first["catalog_lag_count"] == 1
    second = runtime_state.record_apply_outcome(root, raw_ok=True, catalog_ok=False)
    assert second["catalog_lag_count"] == 2


# ── 블록 예산 3단계 → GIVEN_UP → 이후 통과 ───────────────────────────────────


def test_pending_blocks_accumulate_then_given_up(tmp_path: Path) -> None:
    root = _make_project(tmp_path)
    state_path = _arm_to_completed(root)

    r1 = _decide(root, state_path, pending_count=2)
    assert r1["action"] == "block"
    assert r1["reason"] == "pending_blocked"
    assert r1["status"] == runtime_state.PENDING
    assert r1["blocks"] == 1

    r2 = _decide(root, state_path, pending_count=2)
    assert r2["action"] == "block"
    assert r2["blocks"] == 2

    r3 = _decide(root, state_path, pending_count=2)
    assert r3["action"] == "block"
    assert r3["blocks"] == 3

    r4 = _decide(root, state_path, pending_count=2)
    assert r4["action"] == "block"
    assert r4["reason"] == "budget_exhausted"
    assert r4["status"] == runtime_state.GIVEN_UP
    assert "message" in r4

    r5 = _decide(root, state_path, pending_count=2)
    assert r5["action"] == "pass"
    assert r5["reason"] == "given_up_passthrough"
    assert r5["status"] == runtime_state.GIVEN_UP


def test_given_up_resolves_to_done_once_pending_reaches_zero(tmp_path: Path) -> None:
    root = _make_project(tmp_path)
    state_path = _arm_to_completed(root)
    for _ in range(4):
        _decide(root, state_path, pending_count=2)
    resolved = _decide(root, state_path, pending_count=0)
    assert resolved["status"] == runtime_state.DONE
    assert resolved["reason"] == "no_pending"


def test_signature_change_rearms_with_fresh_budget(tmp_path: Path) -> None:
    """서명 재변경(새 사이클) → GIVEN_UP·blocks가 자동으로 초기화되고
    재무장된다(arch §5.1.4)."""
    root = _make_project(tmp_path)
    state_path = _arm_to_completed(root)
    for _ in range(4):
        given_up = _decide(root, state_path, pending_count=2)
    assert given_up["status"] == runtime_state.GIVEN_UP

    # 새 사이클: 비완료로 되돌아갔다가 다른 result 문서로 다시 COMPLETED.
    _write_state_md(root, status="EXECUTING")
    state_path = root / "docs" / "sdd" / "ORCHESTRATOR_STATE.md"
    _decide(root, state_path, pending_count=1)
    _seed_result_doc(root, "test-feature", date="2026-08-01")
    _write_state_md(root, status="COMPLETED")

    fresh_cycle = _decide(root, state_path, pending_count=2)
    assert fresh_cycle["action"] == "block"
    assert fresh_cycle["reason"] == "pending_blocked"
    assert fresh_cycle["blocks"] == 1


def test_session_change_resets_blocks(tmp_path: Path) -> None:
    root = _make_project(tmp_path)
    state_path = _arm_to_completed(root, session_id="session-A")

    r1 = _decide(root, state_path, pending_count=2, session_id="session-A")
    assert r1["blocks"] == 1
    r2 = _decide(root, state_path, pending_count=2, session_id="session-A")
    assert r2["blocks"] == 2

    r3 = _decide(root, state_path, pending_count=2, session_id="session-B")
    assert r3["action"] == "block"
    assert r3["blocks"] == 1  # 세션 전환으로 리셋


def test_unmapped_count_does_not_affect_decision(tmp_path: Path) -> None:
    """pending_count와 unmapped_count는 별개 인자다 — unmapped가 아무리
    커도 pending==0이면 DONE(차단 아님)이어야 한다."""
    root = _make_project(tmp_path)
    state_path = _arm_to_completed(root)
    result = _decide(root, state_path, pending_count=0, unmapped_count=1000)
    assert result["status"] == runtime_state.DONE
    assert result["unmapped_count"] == 1000


# ── A-1: write 실패 시 무차단 ─────────────────────────────────────────────


def test_write_failure_passes_without_blocking(tmp_path: Path) -> None:
    root = _make_project(tmp_path)
    state_path = _arm_to_completed(root)

    state_dir = root / ".claude" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    original_mode = state_dir.stat().st_mode
    os.chmod(state_dir, stat.S_IREAD | stat.S_IEXEC)
    try:
        result = _decide(root, state_path, pending_count=2)
        assert result["action"] == "pass"
        assert result["reason"] == "state_write_failed"
        assert "warning" in result

        # 반복 호출해도 무한 block 없이 계속 통과해야 한다.
        result2 = _decide(root, state_path, pending_count=2)
        assert result2["action"] == "pass"
        assert result2["reason"] == "state_write_failed"
    finally:
        os.chmod(state_dir, original_mode)


# ── 코어 예외 ────────────────────────────────────────────────────────────────


def test_internal_error_is_absorbed_as_failed_pass(tmp_path: Path) -> None:
    root = _make_project(tmp_path)
    state_path = _write_state_md(root, status="COMPLETED")
    result = runtime_state.record_and_decide(
        root,
        state_path,
        config_ok=True,
        pending_count="not-an-int",  # type: ignore[arg-type]
        session_id="session-A",
    )
    assert result["action"] == "pass"
    assert result["reason"] == "internal_error"
    assert result["status"] == runtime_state.FAILED


def test_state_missing_passes_without_error(tmp_path: Path) -> None:
    root = _make_project(tmp_path)
    missing = root / "docs" / "sdd" / "ORCHESTRATOR_STATE.md"
    result = _decide(root, missing, pending_count=5)
    assert result["action"] == "pass"
    assert result["reason"] == "state_missing"


# ── 안내 1회 (M-18) ──────────────────────────────────────────────────────────


def test_notice_emitted_once_per_process_same_session(tmp_path: Path) -> None:
    root = _make_project(tmp_path)
    first = runtime_state.should_emit_unconfigured_notice(root, session_id="session-A")
    assert first is True
    second = runtime_state.should_emit_unconfigured_notice(root, session_id="session-A")
    assert second is False


def test_notice_emitted_again_for_new_session(tmp_path: Path) -> None:
    """세션이 바뀌면(=영속 계층 관점) 다시 안내해야 한다. 실제로는 매 Claude
    Code 훅 호출이 별도 OS 프로세스이므로, 여기서는 프로세스 내 플래그를
    수동으로 지워 "새 프로세스"를 시뮬레이션한다(프로세스 내 층 자체는
    `test_notice_emitted_once_per_process_same_session`이 검증한다)."""
    root = _make_project(tmp_path)
    assert runtime_state.should_emit_unconfigured_notice(root, session_id="session-A") is True
    state_path = runtime_state.state_path_for(root)
    runtime_state._PROCESS_NOTICE_EMITTED.discard(str(state_path))
    assert runtime_state.should_emit_unconfigured_notice(root, session_id="session-B") is True


def test_notice_without_session_id_uses_24h_window(tmp_path: Path) -> None:
    root = _make_project(tmp_path)
    t0 = datetime(2026, 7, 29, 12, 0, 0, tzinfo=timezone.utc)
    first = runtime_state.should_emit_unconfigured_notice(root, session_id=None, now=t0)
    assert first is True

    # 새 프로세스를 흉내내려면 새 project_root가 필요하므로, 여기서는 대신
    # 영속 계층만 검증하기 위해 process 플래그를 우회할 수 없다 — 그래서
    # 같은 root의 두 번째 호출은 프로세스 내 플래그로도 False가 나오는 게
    # 정상이다. 영속 계층의 24h 창 자체는 아래 별도 root로 검증한다.
    soon = runtime_state.should_emit_unconfigured_notice(root, session_id=None, now=t0 + timedelta(hours=1))
    assert soon is False


def test_notice_persisted_window_allows_reemit_after_24h(tmp_path: Path) -> None:
    root = _make_project(tmp_path)
    t0 = datetime(2026, 7, 29, 12, 0, 0, tzinfo=timezone.utc)
    runtime_state.should_emit_unconfigured_notice(root, session_id=None, now=t0)

    # 영속 계층만 재검증하기 위해 프로세스 플래그를 직접 제거한다(같은
    # 프로세스에서 "새 프로세스"를 시뮬레이션하는 유일한 방법).
    state_path = runtime_state.state_path_for(root)
    runtime_state._PROCESS_NOTICE_EMITTED.discard(str(state_path))

    later = runtime_state.should_emit_unconfigured_notice(
        root, session_id=None, now=t0 + timedelta(hours=25)
    )
    assert later is True
