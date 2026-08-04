"""tests/test_stop_pipeline_characterization.py

CHARACTERIZATION TEST — 현재 동작 고정, 스펙이 아니다.

이 파일은 `hooks/enforcement/stop-pipeline.py`가 T-12(F1, kompound 완료 게이트
삽입)로 수정되기 **전** 시점의 동작을 그대로 사진 찍어 고정한다. 여기 박히는
값 중 일부는 현재 코드의 버그일 수 있으나, 이 파일의 목적은 "옳은 동작"이
아니라 "지금과 동일한 동작"이므로 버그도 함께 고정한다. 어떤 assertion이
틀렸다고 판단되더라도 구현을 그 assertion에 맞추려 하지 말고, 먼저 이 테스트
파일을 의도적으로 갱신할 것(그리고 왜 바뀌었는지 커밋 메시지에 남길 것).

스코프 (docs/sdd/design/arch/2026-07-29-kompound-snapshot-hook.md §9.2, F17):
  1. `decide()` 의 라벨 전이 결과(입력 라벨·상태 → 반환 dict). `pipeline.json`
     부재(C3, `/sdd-orchestrator` 직접 실행 케이스) 케이스, 그리고 "sys.path
     부트스트랩 후에도 기존 Step 0~9 동작이 입력별로 불변" 임을 고정하는
     부트스트랩 무해성 케이스를 포함한다(스코프 1의 일부, 스코프 6이 아니다).
  2. `DIRECTIVES` 선택 로직 — 키 "집합 동일성"은 절대 단정하지 않는다. T-12가
     `PHASE4_KOMPOUND_SNAPSHOT_PENDING` 키를 하나 더 추가하기 때문이다(브리틀
     방지). 여기서는 기존 라벨 각각의 "존재 + 형태"만 단정한다(부분집합 성질).
  3. `label_prerequisite_met()` 의 선행조건 판정 (has_* 검사군, 충족/미충족
     양쪽 + checks에 없는 라벨의 기본값(True, "")).
  4. 서킷브레이커 3함수 — `check_circuit_breaker` / `increment_breaker` /
     `reset_breaker`.

  (hooks.json 유효성은 스코프 5이며 tests/test_hooks_json_contract.py 가
  별도로 담당한다.)

스코프 밖(이번 사이클 대상 아님 — 건드리지 않는다):
  - `is_stale()` 의 staleness 판정(STALE_THRESHOLD_HOURS)
  - `check_session_match()` 의 세션 매칭 로직
  - `atomic_write()` 의 파일 쓰기 원자성
  - `check_context_limit()` 의 컨텍스트 한도 판정
  이 항목들이 우연히 발동해 테스트 결과를 흔들지 않도록, 각 테스트는 이들을
  "발동하지 않는" 중립값으로 고정해 둔다 — `last_updated` 를 항상 신선하게,
  `session_id` 를 빈 문자열로(레거시 호환 경로), `stop_data` 를 `{}` 로.

Import 방식: 파일명에 하이픈이 있어 `import stop-pipeline` 이 불가능하다.
`tests/test_self_improve_scripts.py:35-41` 의 `_load()` 선례를 그대로 따라
`importlib.util.spec_from_file_location("stop_pipeline", <path>)` 로 적재한다
(모듈 이름은 하이픈이 아닌 유효 식별자 `stop_pipeline`). `stop-pipeline.py`
모듈 최상위는 상수 정의와 `def` 뿐이고 `main()` 은 `if __name__ == "__main__"`
가드 안에서만 호출되므로 import 시점 부작용이 없음이 확인됐다(arch §9.2).
"""

from __future__ import annotations

import importlib
import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# ── 모듈 로딩 (하이픈 파일명 우회) ────────────────────────────────────────────

_REPO_ROOT = Path(__file__).resolve().parents[1]
_STOP_PIPELINE_PATH = _REPO_ROOT / "hooks" / "enforcement" / "stop-pipeline.py"


def _load_stop_pipeline():
    spec = importlib.util.spec_from_file_location("stop_pipeline", _STOP_PIPELINE_PATH)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


@pytest.fixture(scope="module")
def stop_pipeline():
    return _load_stop_pipeline()


# ── 공통 헬퍼 ────────────────────────────────────────────────────────────────


def _mk_state(mod, label: str, **overrides) -> dict:
    """스코프 밖 항목(stale/session/context-limit)이 발동하지 않는 중립 상태."""
    state = {
        "current_label": label,
        "feature": "demo-feature",
        "worktree_path": "",
        "mode": "SIMPLE",
        "waiting_for_user": False,
        "session_id": "",  # legacy compat 경로 — check_session_match 는 항상 통과
        "circuit_breaker": {},
        "last_updated": mod.now_iso(),  # 항상 신선 — is_stale 미발동
    }
    state.update(overrides)
    return state


def _write_pipeline(tmp_path: Path, state: dict) -> Path:
    path = tmp_path / ".claude" / "state" / "pipeline.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state), encoding="utf-8")
    return path


# ═══════════════════════════════════════════════════════════════════════════
# 스코프 1 — decide() 라벨 전이 결과
# ═══════════════════════════════════════════════════════════════════════════

# has_* 선행조건 검사가 없는(= checks 딕셔너리에 없는) 라벨들.
# label_prerequisite_met() 이 항상 (True, "") 을 반환하므로 decide() 는
# 항상 directive 를 그대로(경고 접미사 없이) block 으로 반환한다.
_ALWAYS_MET_LABELS = [
    "PHASE1_UX_RESEARCH_DONE",
    "PHASE1_USER_APPROVED",
    "PHASE2_START",
    "PHASE2_ARCH_USER_APPROVED",
    "PHASE2_DESIGN_USER_APPROVED",
    "PHASE3_PLAN_START",
    "PHASE3_USER_APPROVED",
]


@pytest.mark.parametrize("label", _ALWAYS_MET_LABELS)
def test_decide_returns_directive_verbatim_for_labels_without_prerequisite_check(
    stop_pipeline, tmp_path, label
):
    state = _mk_state(stop_pipeline, label)
    pipeline_path = _write_pipeline(tmp_path, state)

    result = stop_pipeline.decide({}, tmp_path, pipeline_path)

    assert result == {
        "decision": "block",
        "reason": stop_pipeline.DIRECTIVES[label],
    }


def test_decide_terminal_label_short_circuits_even_when_waiting_for_user(
    stop_pipeline, tmp_path
):
    """PHASE4_WORKTREE_CREATED 는 Step 5에서 즉시 반환한다 — Step 6(사용자
    대기)·Step 7(선행조건)·Step 8(directive 조회)에 도달하기 전이므로
    waiting_for_user=True 여도 결과가 바뀌지 않는다."""
    label = "PHASE4_WORKTREE_CREATED"
    state = _mk_state(stop_pipeline, label, waiting_for_user=True)
    pipeline_path = _write_pipeline(tmp_path, state)

    result = stop_pipeline.decide({}, tmp_path, pipeline_path)

    assert result == {"continue": True, "suppressOutput": True}


def test_decide_pipeline_json_absent_continues_immediately(stop_pipeline, tmp_path):
    """C3: `/sdd-orchestrator` 직접 실행 시 pipeline.json 이 아예 없을 수
    있다 — Step 1 이 즉시 continue 를 반환한다."""
    pipeline_path = tmp_path / ".claude" / "state" / "pipeline.json"
    assert not pipeline_path.exists()

    result = stop_pipeline.decide({}, tmp_path, pipeline_path)

    assert result == {"continue": True, "suppressOutput": True}


def test_decide_pipeline_json_corrupted_is_treated_like_absent(stop_pipeline, tmp_path):
    pipeline_path = tmp_path / ".claude" / "state" / "pipeline.json"
    pipeline_path.parent.mkdir(parents=True)
    pipeline_path.write_text("{ not valid json", encoding="utf-8")

    result = stop_pipeline.decide({}, tmp_path, pipeline_path)

    assert result == {"continue": True, "suppressOutput": True}


# ── 선행조건이 걸린 라벨 — 충족/미충족 각각 ──────────────────────────────────


def _expected_unmet_reason(mod, label: str) -> str:
    return (
        f"{mod.DIRECTIVES[label]}\n\n"
        f"⚠️ 전이 조건 미충족: [{label}] 선행 파일이 아직 없습니다. directive 를 따라 생성하세요."
    )


def test_decide_phase1_spec_draft_met(stop_pipeline, tmp_path):
    (tmp_path / "docs" / "sdd" / "spec").mkdir(parents=True)
    (tmp_path / "docs" / "sdd" / "spec" / "2026-07-29-demo.md").write_text(
        "# spec", encoding="utf-8"
    )
    label = "PHASE1_SPEC_DRAFT"
    pipeline_path = _write_pipeline(tmp_path, _mk_state(stop_pipeline, label))

    result = stop_pipeline.decide({}, tmp_path, pipeline_path)

    assert result == {"decision": "block", "reason": stop_pipeline.DIRECTIVES[label]}


def test_decide_phase1_spec_draft_unmet(stop_pipeline, tmp_path):
    label = "PHASE1_SPEC_DRAFT"
    pipeline_path = _write_pipeline(tmp_path, _mk_state(stop_pipeline, label))

    result = stop_pipeline.decide({}, tmp_path, pipeline_path)

    assert result == {
        "decision": "block",
        "reason": _expected_unmet_reason(stop_pipeline, label),
    }


def test_decide_phase1_blocker_check_pass_met(stop_pipeline, tmp_path):
    (tmp_path / "docs" / "sdd" / "spec").mkdir(parents=True)
    (tmp_path / "docs" / "sdd" / "spec" / "2026-07-29-demo.md").write_text(
        "# spec\n\nBLOCKER_PASS\n", encoding="utf-8"
    )
    label = "PHASE1_BLOCKER_CHECK_PASS"
    pipeline_path = _write_pipeline(tmp_path, _mk_state(stop_pipeline, label))

    result = stop_pipeline.decide({}, tmp_path, pipeline_path)

    assert result == {"decision": "block", "reason": stop_pipeline.DIRECTIVES[label]}


def test_decide_phase1_blocker_check_pass_unmet(stop_pipeline, tmp_path):
    (tmp_path / "docs" / "sdd" / "spec").mkdir(parents=True)
    (tmp_path / "docs" / "sdd" / "spec" / "2026-07-29-demo.md").write_text(
        "# spec (no marker)", encoding="utf-8"
    )
    label = "PHASE1_BLOCKER_CHECK_PASS"
    pipeline_path = _write_pipeline(tmp_path, _mk_state(stop_pipeline, label))

    result = stop_pipeline.decide({}, tmp_path, pipeline_path)

    assert result == {
        "decision": "block",
        "reason": _expected_unmet_reason(stop_pipeline, label),
    }


def test_decide_phase2_worktree_created_met(stop_pipeline, tmp_path):
    worktree_dir = tmp_path / "worktrees" / "demo"
    worktree_dir.mkdir(parents=True)
    label = "PHASE2_WORKTREE_CREATED"
    state = _mk_state(stop_pipeline, label, worktree_path=str(worktree_dir))
    pipeline_path = _write_pipeline(tmp_path, state)

    result = stop_pipeline.decide({}, tmp_path, pipeline_path)

    assert result == {"decision": "block", "reason": stop_pipeline.DIRECTIVES[label]}


def test_decide_phase2_worktree_created_unmet(stop_pipeline, tmp_path):
    label = "PHASE2_WORKTREE_CREATED"
    state = _mk_state(stop_pipeline, label, worktree_path="")
    pipeline_path = _write_pipeline(tmp_path, state)

    result = stop_pipeline.decide({}, tmp_path, pipeline_path)

    assert result == {
        "decision": "block",
        "reason": _expected_unmet_reason(stop_pipeline, label),
    }


def test_decide_phase2_arch_structure_done_met(stop_pipeline, tmp_path):
    (tmp_path / "docs" / "sdd" / "design" / "arch").mkdir(parents=True)
    (tmp_path / "docs" / "sdd" / "design" / "arch" / "2026-07-29-demo.md").write_text(
        "# arch", encoding="utf-8"
    )
    label = "PHASE2_ARCH_STRUCTURE_DONE"
    pipeline_path = _write_pipeline(tmp_path, _mk_state(stop_pipeline, label))

    result = stop_pipeline.decide({}, tmp_path, pipeline_path)

    assert result == {"decision": "block", "reason": stop_pipeline.DIRECTIVES[label]}


def test_decide_phase2_arch_structure_done_unmet(stop_pipeline, tmp_path):
    label = "PHASE2_ARCH_STRUCTURE_DONE"
    pipeline_path = _write_pipeline(tmp_path, _mk_state(stop_pipeline, label))

    result = stop_pipeline.decide({}, tmp_path, pipeline_path)

    assert result == {
        "decision": "block",
        "reason": _expected_unmet_reason(stop_pipeline, label),
    }


def test_decide_phase2_ui_design_complete_met(stop_pipeline, tmp_path):
    (tmp_path / "docs" / "sdd" / "design" / "ui").mkdir(parents=True)
    (tmp_path / "docs" / "sdd" / "design" / "ui" / "2026-07-29-demo.md").write_text(
        "# ui", encoding="utf-8"
    )
    label = "PHASE2_UI_DESIGN_COMPLETE"
    pipeline_path = _write_pipeline(tmp_path, _mk_state(stop_pipeline, label))

    result = stop_pipeline.decide({}, tmp_path, pipeline_path)

    assert result == {"decision": "block", "reason": stop_pipeline.DIRECTIVES[label]}


def test_decide_phase2_ui_design_complete_unmet(stop_pipeline, tmp_path):
    label = "PHASE2_UI_DESIGN_COMPLETE"
    pipeline_path = _write_pipeline(tmp_path, _mk_state(stop_pipeline, label))

    result = stop_pipeline.decide({}, tmp_path, pipeline_path)

    assert result == {
        "decision": "block",
        "reason": _expected_unmet_reason(stop_pipeline, label),
    }


def test_decide_phase2_api_design_complete_met(stop_pipeline, tmp_path):
    (tmp_path / "docs" / "sdd" / "design" / "api").mkdir(parents=True)
    (tmp_path / "docs" / "sdd" / "design" / "api" / "2026-07-29-demo.md").write_text(
        "# api", encoding="utf-8"
    )
    label = "PHASE2_API_DESIGN_COMPLETE"
    pipeline_path = _write_pipeline(tmp_path, _mk_state(stop_pipeline, label))

    result = stop_pipeline.decide({}, tmp_path, pipeline_path)

    assert result == {"decision": "block", "reason": stop_pipeline.DIRECTIVES[label]}


def test_decide_phase2_api_design_complete_unmet(stop_pipeline, tmp_path):
    label = "PHASE2_API_DESIGN_COMPLETE"
    pipeline_path = _write_pipeline(tmp_path, _mk_state(stop_pipeline, label))

    result = stop_pipeline.decide({}, tmp_path, pipeline_path)

    assert result == {
        "decision": "block",
        "reason": _expected_unmet_reason(stop_pipeline, label),
    }


def test_decide_phase2_user_approved_simple_mode_always_met(stop_pipeline, tmp_path):
    """SIMPLE 모드에선 has_context 검사를 건너뛰고 항상 True (context 문서
    부재에도 met)."""
    label = "PHASE2_USER_APPROVED"
    state = _mk_state(stop_pipeline, label, mode="SIMPLE")
    pipeline_path = _write_pipeline(tmp_path, state)

    result = stop_pipeline.decide({}, tmp_path, pipeline_path)

    assert result == {"decision": "block", "reason": stop_pipeline.DIRECTIVES[label]}


def test_decide_phase2_user_approved_full_mode_met(stop_pipeline, tmp_path):
    (tmp_path / "docs" / "sdd" / "context").mkdir(parents=True)
    (tmp_path / "docs" / "sdd" / "context" / "2026-07-29-demo.md").write_text(
        "# context", encoding="utf-8"
    )
    label = "PHASE2_USER_APPROVED"
    state = _mk_state(stop_pipeline, label, mode="FULL")
    pipeline_path = _write_pipeline(tmp_path, state)

    result = stop_pipeline.decide({}, tmp_path, pipeline_path)

    assert result == {"decision": "block", "reason": stop_pipeline.DIRECTIVES[label]}


def test_decide_phase2_user_approved_full_mode_unmet(stop_pipeline, tmp_path):
    label = "PHASE2_USER_APPROVED"
    state = _mk_state(stop_pipeline, label, mode="FULL")
    pipeline_path = _write_pipeline(tmp_path, state)

    result = stop_pipeline.decide({}, tmp_path, pipeline_path)

    assert result == {
        "decision": "block",
        "reason": _expected_unmet_reason(stop_pipeline, label),
    }


def test_decide_phase3_taskmaster_done_met(stop_pipeline, tmp_path):
    (tmp_path / "docs" / "sdd" / "task" / "demo-feature").mkdir(parents=True)
    (tmp_path / "docs" / "sdd" / "task" / "demo-feature" / "T-1.md").write_text(
        "# T-1", encoding="utf-8"
    )
    label = "PHASE3_TASKMASTER_DONE"
    pipeline_path = _write_pipeline(tmp_path, _mk_state(stop_pipeline, label))

    result = stop_pipeline.decide({}, tmp_path, pipeline_path)

    assert result == {"decision": "block", "reason": stop_pipeline.DIRECTIVES[label]}


def test_decide_phase3_taskmaster_done_unmet(stop_pipeline, tmp_path):
    label = "PHASE3_TASKMASTER_DONE"
    pipeline_path = _write_pipeline(tmp_path, _mk_state(stop_pipeline, label))

    result = stop_pipeline.decide({}, tmp_path, pipeline_path)

    assert result == {
        "decision": "block",
        "reason": _expected_unmet_reason(stop_pipeline, label),
    }


def test_decide_phase3_dag_constructed_met(stop_pipeline, tmp_path):
    (tmp_path / "docs" / "sdd").mkdir(parents=True)
    (tmp_path / "docs" / "sdd" / "ORCHESTRATOR_STATE.md").write_text(
        "# state", encoding="utf-8"
    )
    label = "PHASE3_DAG_CONSTRUCTED"
    pipeline_path = _write_pipeline(tmp_path, _mk_state(stop_pipeline, label))

    result = stop_pipeline.decide({}, tmp_path, pipeline_path)

    assert result == {"decision": "block", "reason": stop_pipeline.DIRECTIVES[label]}


def test_decide_phase3_dag_constructed_unmet(stop_pipeline, tmp_path):
    label = "PHASE3_DAG_CONSTRUCTED"
    pipeline_path = _write_pipeline(tmp_path, _mk_state(stop_pipeline, label))

    result = stop_pipeline.decide({}, tmp_path, pipeline_path)

    assert result == {
        "decision": "block",
        "reason": _expected_unmet_reason(stop_pipeline, label),
    }


# ── 부트스트랩 무해성 (arch §5.1.2/§9.2) ─────────────────────────────────────


@pytest.mark.parametrize(
    "label",
    ["PHASE1_UX_RESEARCH_DONE", "PHASE4_WORKTREE_CREATED"],
)
def test_decide_result_unaffected_by_plugin_root_on_syspath(
    stop_pipeline, tmp_path, monkeypatch, label
):
    """T-12는 모듈 최상위에 `sys.path.insert(0, <plugin root>)` 를 추가할
    예정이다(arch §5.1.2). 그 부트스트랩은 "sys.path 변경 외의 부작용을 만들지
    않아야 한다"는 제약이 걸려 있다. 부트스트랩이 아직 없는 현재 코드를 기준으로,
    sys.path 에 plugin root 항목이 얹혀 있든 없든 decide() 결과가 동일함을
    미리 고정해 둔다 — T-12 이후 이 케이스가 깨지면 부트스트랩이 곁가지 부작용을
    만들었다는 신호다.
    """
    is_terminal = label == "PHASE4_WORKTREE_CREATED"

    baseline_state = _mk_state(stop_pipeline, label, waiting_for_user=is_terminal)
    baseline_path = _write_pipeline(tmp_path / "baseline", baseline_state)
    baseline = stop_pipeline.decide({}, tmp_path / "baseline", baseline_path)

    monkeypatch.syspath_prepend(str(_REPO_ROOT))

    bootstrapped_state = _mk_state(stop_pipeline, label, waiting_for_user=is_terminal)
    bootstrapped_path = _write_pipeline(tmp_path / "bootstrapped", bootstrapped_state)
    bootstrapped = stop_pipeline.decide({}, tmp_path / "bootstrapped", bootstrapped_path)

    assert bootstrapped == baseline


# ═══════════════════════════════════════════════════════════════════════════
# 스코프 2 — DIRECTIVES 선택 로직 (브리틀 방지: 키 집합 동일성 단정 금지)
# ═══════════════════════════════════════════════════════════════════════════

# 현재(수정 전) 코드에 존재하는 비-터미널 라벨 16개. T-12가 여기에 새 키
# (PHASE4_KOMPOUND_SNAPSHOT_PENDING) 를 "추가"할 뿐이므로, 이 목록의 존재를
# 부분집합으로만 단정한다 — `len(DIRECTIVES) == N` 이나
# `set(DIRECTIVES) == {...}` 형태의 전체집합 단정은 절대 하지 않는다.
_KNOWN_NON_TERMINAL_LABELS = [
    "PHASE1_UX_RESEARCH_DONE",
    "PHASE1_SPEC_DRAFT",
    "PHASE1_BLOCKER_CHECK_PASS",
    "PHASE1_USER_APPROVED",
    "PHASE2_START",
    "PHASE2_WORKTREE_CREATED",
    "PHASE2_ARCH_STRUCTURE_DONE",
    "PHASE2_ARCH_USER_APPROVED",
    "PHASE2_UI_DESIGN_COMPLETE",
    "PHASE2_API_DESIGN_COMPLETE",
    "PHASE2_DESIGN_USER_APPROVED",
    "PHASE2_USER_APPROVED",
    "PHASE3_PLAN_START",
    "PHASE3_TASKMASTER_DONE",
    "PHASE3_DAG_CONSTRUCTED",
    "PHASE3_USER_APPROVED",
]


@pytest.mark.parametrize("label", _KNOWN_NON_TERMINAL_LABELS)
def test_directives_known_label_exists_with_sdd_pipeline_prefix(stop_pipeline, label):
    directive = stop_pipeline.DIRECTIVES.get(label)
    assert directive is not None
    assert isinstance(directive, str)
    assert directive.startswith("[SDD-PIPELINE]")


def test_directives_terminal_label_is_none(stop_pipeline):
    assert stop_pipeline.DIRECTIVES["PHASE4_WORKTREE_CREATED"] is None


def test_directives_contains_known_labels_as_subset_not_exact_set(stop_pipeline):
    """브리틀 방지(§9.2): 키 "집합 동일성"은 단정하지 않는다. T-12가
    `PHASE4_KOMPOUND_SNAPSHOT_PENDING` 을 추가해도 이 assertion 은 계속 GREEN
    이어야 한다."""
    known = set(_KNOWN_NON_TERMINAL_LABELS) | {"PHASE4_WORKTREE_CREATED"}
    assert known <= set(stop_pipeline.DIRECTIVES.keys())


# ═══════════════════════════════════════════════════════════════════════════
# 스코프 3 — label_prerequisite_met() 선행조건 판정
# ═══════════════════════════════════════════════════════════════════════════


def test_label_prerequisite_met_defaults_true_for_label_without_check(
    stop_pipeline, tmp_path
):
    """checks 딕셔너리에 없는 라벨(파일 검증 불필요한 user_gate/transition-only
    라벨)은 항상 (True, "") 을 반환한다(L322)."""
    met, reason = stop_pipeline.label_prerequisite_met(
        "PHASE1_UX_RESEARCH_DONE", {"feature": "demo"}, tmp_path
    )
    assert (met, reason) == (True, "")


def test_label_prerequisite_met_spec_draft_met(stop_pipeline, tmp_path):
    (tmp_path / "docs" / "sdd" / "spec").mkdir(parents=True)
    (tmp_path / "docs" / "sdd" / "spec" / "2026-07-29-demo.md").write_text(
        "# spec", encoding="utf-8"
    )
    met, reason = stop_pipeline.label_prerequisite_met(
        "PHASE1_SPEC_DRAFT", {"feature": "demo"}, tmp_path
    )
    assert met is True
    assert reason == ""


def test_label_prerequisite_met_spec_draft_unmet(stop_pipeline, tmp_path):
    met, reason = stop_pipeline.label_prerequisite_met(
        "PHASE1_SPEC_DRAFT", {"feature": "demo"}, tmp_path
    )
    assert met is False
    assert reason == (
        "[PHASE1_SPEC_DRAFT] 선행 파일이 아직 없습니다. directive 를 따라 생성하세요."
    )


def test_label_prerequisite_met_blocker_pass_met(stop_pipeline, tmp_path):
    (tmp_path / "docs" / "sdd" / "spec").mkdir(parents=True)
    (tmp_path / "docs" / "sdd" / "spec" / "2026-07-29-demo.md").write_text(
        "# spec\n\nBLOCKER_PASS\n", encoding="utf-8"
    )
    met, reason = stop_pipeline.label_prerequisite_met(
        "PHASE1_BLOCKER_CHECK_PASS", {"feature": "demo"}, tmp_path
    )
    assert met is True
    assert reason == ""


def test_label_prerequisite_met_blocker_pass_unmet(stop_pipeline, tmp_path):
    met, reason = stop_pipeline.label_prerequisite_met(
        "PHASE1_BLOCKER_CHECK_PASS", {"feature": "demo"}, tmp_path
    )
    assert met is False
    assert "PHASE1_BLOCKER_CHECK_PASS" in reason


def test_label_prerequisite_met_worktree_created_met(stop_pipeline, tmp_path):
    worktree_dir = tmp_path / "worktrees" / "demo"
    worktree_dir.mkdir(parents=True)
    met, reason = stop_pipeline.label_prerequisite_met(
        "PHASE2_WORKTREE_CREATED",
        {"feature": "demo", "worktree_path": str(worktree_dir)},
        tmp_path,
    )
    assert met is True
    assert reason == ""


def test_label_prerequisite_met_worktree_created_unmet_when_path_empty(
    stop_pipeline, tmp_path
):
    met, reason = stop_pipeline.label_prerequisite_met(
        "PHASE2_WORKTREE_CREATED", {"feature": "demo", "worktree_path": ""}, tmp_path
    )
    assert met is False
    assert "PHASE2_WORKTREE_CREATED" in reason


def test_label_prerequisite_met_arch_structure_done_met(stop_pipeline, tmp_path):
    (tmp_path / "docs" / "sdd" / "design" / "arch").mkdir(parents=True)
    (tmp_path / "docs" / "sdd" / "design" / "arch" / "2026-07-29-demo.md").write_text(
        "# arch", encoding="utf-8"
    )
    met, reason = stop_pipeline.label_prerequisite_met(
        "PHASE2_ARCH_STRUCTURE_DONE", {"feature": "demo"}, tmp_path
    )
    assert met is True
    assert reason == ""


def test_label_prerequisite_met_arch_structure_done_unmet(stop_pipeline, tmp_path):
    met, reason = stop_pipeline.label_prerequisite_met(
        "PHASE2_ARCH_STRUCTURE_DONE", {"feature": "demo"}, tmp_path
    )
    assert met is False


def test_label_prerequisite_met_ui_design_complete_met(stop_pipeline, tmp_path):
    (tmp_path / "docs" / "sdd" / "design" / "ui").mkdir(parents=True)
    (tmp_path / "docs" / "sdd" / "design" / "ui" / "2026-07-29-demo.md").write_text(
        "# ui", encoding="utf-8"
    )
    met, reason = stop_pipeline.label_prerequisite_met(
        "PHASE2_UI_DESIGN_COMPLETE", {"feature": "demo"}, tmp_path
    )
    assert met is True
    assert reason == ""


def test_label_prerequisite_met_ui_design_complete_unmet(stop_pipeline, tmp_path):
    met, reason = stop_pipeline.label_prerequisite_met(
        "PHASE2_UI_DESIGN_COMPLETE", {"feature": "demo"}, tmp_path
    )
    assert met is False


def test_label_prerequisite_met_api_design_complete_met(stop_pipeline, tmp_path):
    (tmp_path / "docs" / "sdd" / "design" / "api").mkdir(parents=True)
    (tmp_path / "docs" / "sdd" / "design" / "api" / "2026-07-29-demo.md").write_text(
        "# api", encoding="utf-8"
    )
    met, reason = stop_pipeline.label_prerequisite_met(
        "PHASE2_API_DESIGN_COMPLETE", {"feature": "demo"}, tmp_path
    )
    assert met is True
    assert reason == ""


def test_label_prerequisite_met_api_design_complete_unmet(stop_pipeline, tmp_path):
    met, reason = stop_pipeline.label_prerequisite_met(
        "PHASE2_API_DESIGN_COMPLETE", {"feature": "demo"}, tmp_path
    )
    assert met is False


def test_label_prerequisite_met_user_approved_simple_mode_always_true(
    stop_pipeline, tmp_path
):
    met, reason = stop_pipeline.label_prerequisite_met(
        "PHASE2_USER_APPROVED", {"feature": "demo", "mode": "SIMPLE"}, tmp_path
    )
    assert met is True
    assert reason == ""


def test_label_prerequisite_met_user_approved_full_mode_met(stop_pipeline, tmp_path):
    (tmp_path / "docs" / "sdd" / "context").mkdir(parents=True)
    (tmp_path / "docs" / "sdd" / "context" / "2026-07-29-demo.md").write_text(
        "# context", encoding="utf-8"
    )
    met, reason = stop_pipeline.label_prerequisite_met(
        "PHASE2_USER_APPROVED", {"feature": "demo", "mode": "FULL"}, tmp_path
    )
    assert met is True
    assert reason == ""


def test_label_prerequisite_met_user_approved_full_mode_unmet(stop_pipeline, tmp_path):
    met, reason = stop_pipeline.label_prerequisite_met(
        "PHASE2_USER_APPROVED", {"feature": "demo", "mode": "FULL"}, tmp_path
    )
    assert met is False


def test_label_prerequisite_met_taskmaster_done_met(stop_pipeline, tmp_path):
    (tmp_path / "docs" / "sdd" / "task" / "demo").mkdir(parents=True)
    (tmp_path / "docs" / "sdd" / "task" / "demo" / "T-1.md").write_text(
        "# T-1", encoding="utf-8"
    )
    met, reason = stop_pipeline.label_prerequisite_met(
        "PHASE3_TASKMASTER_DONE", {"feature": "demo"}, tmp_path
    )
    assert met is True
    assert reason == ""


def test_label_prerequisite_met_taskmaster_done_unmet(stop_pipeline, tmp_path):
    met, reason = stop_pipeline.label_prerequisite_met(
        "PHASE3_TASKMASTER_DONE", {"feature": "demo"}, tmp_path
    )
    assert met is False


def test_label_prerequisite_met_dag_constructed_met(stop_pipeline, tmp_path):
    (tmp_path / "docs" / "sdd").mkdir(parents=True)
    (tmp_path / "docs" / "sdd" / "ORCHESTRATOR_STATE.md").write_text(
        "# state", encoding="utf-8"
    )
    met, reason = stop_pipeline.label_prerequisite_met(
        "PHASE3_DAG_CONSTRUCTED", {"feature": "demo"}, tmp_path
    )
    assert met is True
    assert reason == ""


def test_label_prerequisite_met_dag_constructed_unmet(stop_pipeline, tmp_path):
    met, reason = stop_pipeline.label_prerequisite_met(
        "PHASE3_DAG_CONSTRUCTED", {"feature": "demo"}, tmp_path
    )
    assert met is False


# ═══════════════════════════════════════════════════════════════════════════
# 스코프 4 — 서킷브레이커
# ═══════════════════════════════════════════════════════════════════════════


def test_check_circuit_breaker_no_state_allows_no_reset(stop_pipeline):
    allow, should_reset = stop_pipeline.check_circuit_breaker({})
    assert (allow, should_reset) == (False, False)


def test_check_circuit_breaker_below_max_and_future_reset_at_no_reset(stop_pipeline):
    future = (
        datetime.now(timezone.utc) + timedelta(minutes=5)
    ).isoformat()
    state = {"circuit_breaker": {"blocks": 5, "reset_at": future}}
    allow, should_reset = stop_pipeline.check_circuit_breaker(state)
    assert (allow, should_reset) == (False, False)


def test_check_circuit_breaker_ttl_expired_takes_precedence_over_blocks(stop_pipeline):
    """reset_at 이 과거이면, blocks 값이 상한 미만이어도 reset 이 요구된다."""
    past = (
        datetime.now(timezone.utc) - timedelta(minutes=10)
    ).isoformat()
    state = {"circuit_breaker": {"blocks": 5, "reset_at": past}}
    allow, should_reset = stop_pipeline.check_circuit_breaker(state)
    assert (allow, should_reset) == (False, True)


def test_check_circuit_breaker_ttl_expired_even_when_blocks_over_max(stop_pipeline):
    past = (
        datetime.now(timezone.utc) - timedelta(minutes=10)
    ).isoformat()
    state = {"circuit_breaker": {"blocks": 999, "reset_at": past}}
    allow, should_reset = stop_pipeline.check_circuit_breaker(state)
    assert (allow, should_reset) == (False, True)


def test_check_circuit_breaker_max_blocks_reached_allows_and_resets(stop_pipeline):
    future = (
        datetime.now(timezone.utc) + timedelta(minutes=5)
    ).isoformat()
    state = {
        "circuit_breaker": {
            "blocks": stop_pipeline.CB_MAX_BLOCKS,
            "reset_at": future,
        }
    }
    allow, should_reset = stop_pipeline.check_circuit_breaker(state)
    assert (allow, should_reset) == (True, True)


def test_check_circuit_breaker_max_blocks_with_no_reset_at(stop_pipeline):
    state = {"circuit_breaker": {"blocks": stop_pipeline.CB_MAX_BLOCKS, "reset_at": ""}}
    allow, should_reset = stop_pipeline.check_circuit_breaker(state)
    assert (allow, should_reset) == (True, True)


def test_increment_breaker_starts_at_one_from_empty_state(stop_pipeline):
    state = {}
    stop_pipeline.increment_breaker(state)
    cb = state["circuit_breaker"]
    assert cb["blocks"] == 1
    assert cb["max_blocks"] == stop_pipeline.CB_MAX_BLOCKS
    assert isinstance(cb["reset_at"], str) and cb["reset_at"]


def test_increment_breaker_accumulates_across_calls(stop_pipeline):
    state = {"circuit_breaker": {"blocks": 3}}
    stop_pipeline.increment_breaker(state)
    assert state["circuit_breaker"]["blocks"] == 4
    stop_pipeline.increment_breaker(state)
    assert state["circuit_breaker"]["blocks"] == 5


def test_reset_breaker_zeroes_blocks_and_sets_future_reset_at(stop_pipeline):
    state = {"circuit_breaker": {"blocks": 17, "reset_at": "garbage"}}
    stop_pipeline.reset_breaker(state)
    cb = state["circuit_breaker"]
    assert cb == {
        "blocks": 0,
        "max_blocks": stop_pipeline.CB_MAX_BLOCKS,
        "reset_at": cb["reset_at"],
    }
    reset_at = stop_pipeline.parse_iso(cb["reset_at"])
    assert reset_at is not None
    assert reset_at > datetime.now(timezone.utc)
