"""T-4 (F7, F8 훅 측): Phase 1 라벨 PHASE1_INTERVIEW_START 와 구 라벨 별칭.

새/별칭 라벨 문자열이 DIRECTIVES 와 directive 본문에서 서로 닫혀 있는지 고정한다
(W5). 아래 "T-7" 절에서 Phase 2·3 라벨·구 PHASE2 별칭·라벨 그래프 닫힘을 다룬다.
키 집합 동일성은 단정하지 않는다.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_STOP_PIPELINE_PATH = _REPO_ROOT / "hooks" / "enforcement" / "stop-pipeline.py"

NEW_LABEL = "PHASE1_INTERVIEW_START"
OLD_LABEL = "PHASE1_UX_RESEARCH_DONE"
PHASE1_LABELS = [NEW_LABEL, OLD_LABEL]


@pytest.fixture(scope="module")
def stop_pipeline():
    spec = importlib.util.spec_from_file_location("stop_pipeline", _STOP_PIPELINE_PATH)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _write_state(tmp_path: Path, mod, label: str, **overrides) -> Path:
    state = {
        "current_label": label,
        "feature": "demo-feature",
        "worktree_path": "",
        "mode": "SIMPLE",
        "waiting_for_user": False,
        "session_id": "",
        "circuit_breaker": {},
        "last_updated": mod.now_iso(),
    }
    state.update(overrides)
    path = tmp_path / ".claude" / "state" / "pipeline.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state), encoding="utf-8")
    return path


def test_directives_has_new_and_alias_label(stop_pipeline):
    for label in PHASE1_LABELS:
        assert isinstance(stop_pipeline.DIRECTIVES.get(label), str), label


def test_alias_directive_identical_to_new_label(stop_pipeline):
    d = stop_pipeline.DIRECTIVES
    assert d[NEW_LABEL] == d[OLD_LABEL]


@pytest.mark.parametrize("label", PHASE1_LABELS)
def test_directive_has_no_ux_researcher(stop_pipeline, label):
    assert "ux-researcher" not in stop_pipeline.DIRECTIVES[label]


@pytest.mark.parametrize("label", PHASE1_LABELS)
def test_directive_instructs_interview_flow_and_handoff(stop_pipeline, label):
    text = stop_pipeline.DIRECTIVES[label]
    assert text.startswith("[SDD-PIPELINE]")
    assert "set_waiting_for_user true interview" in text
    assert "sdd-spec-writer" in text
    assert "PHASE1_SPEC_DRAFT" in text


def test_directive_body_label_references_are_known_directive_keys(stop_pipeline):
    """W5: 본문이 가리키는 다음 라벨은 DIRECTIVES 키로 존재해야 한다."""
    text = stop_pipeline.DIRECTIVES[NEW_LABEL]
    assert "PHASE1_SPEC_DRAFT" in text
    assert "PHASE1_SPEC_DRAFT" in stop_pipeline.DIRECTIVES


@pytest.mark.parametrize("label", PHASE1_LABELS)
def test_decide_blocks_with_directive_verbatim(stop_pipeline, tmp_path, label):
    path = _write_state(tmp_path, stop_pipeline, label)

    result = stop_pipeline.decide({}, tmp_path, path)

    assert result == {"decision": "block", "reason": stop_pipeline.DIRECTIVES[label]}


def test_decide_old_label_in_stored_pipeline_json_still_blocks_same_as_new(
    stop_pipeline, tmp_path
):
    old_dir, new_dir = tmp_path / "old", tmp_path / "new"
    old = stop_pipeline.decide(
        {}, old_dir, _write_state(old_dir, stop_pipeline, OLD_LABEL)
    )
    new = stop_pipeline.decide(
        {}, new_dir, _write_state(new_dir, stop_pipeline, NEW_LABEL)
    )

    assert old["decision"] == "block"
    assert old == new


@pytest.mark.parametrize("label", PHASE1_LABELS)
def test_decide_continues_when_waiting_for_user(stop_pipeline, tmp_path, label):
    path = _write_state(
        tmp_path,
        stop_pipeline,
        label,
        waiting_for_user=True,
        waiting_for_approval_type="interview",
    )

    result = stop_pipeline.decide({}, tmp_path, path)

    assert result == {"continue": True, "suppressOutput": True}


# ── iteration 2: 인터뷰 대기 해제 ────────────────────────────────
@pytest.mark.parametrize("label", PHASE1_LABELS)
def test_directive_releases_waiting_before_spec_writer_dispatch(stop_pipeline, label):
    text = stop_pipeline.DIRECTIVES[label]
    release = text.find("set_waiting_for_user false")
    dispatch = text.find("sdd-spec-writer")
    assert release != -1, "directive에 `set_waiting_for_user false` 해제 지시가 없다"
    assert release < dispatch, "해제 지시가 sdd-spec-writer 디스패치 지시보다 앞이어야 한다"


@pytest.mark.parametrize("label", PHASE1_LABELS)
def test_decide_returns_to_block_after_interview_wait_released(
    stop_pipeline, tmp_path, label
):
    path = _write_state(
        tmp_path,
        stop_pipeline,
        label,
        waiting_for_user=True,
        waiting_for_approval_type="interview",
    )
    assert stop_pipeline.decide({}, tmp_path, path) == {
        "continue": True,
        "suppressOutput": True,
    }

    # SKILL/directive 지시대로 `set_waiting_for_user false null` 해제를 상태에 반영
    state = json.loads(path.read_text(encoding="utf-8"))
    state["waiting_for_user"] = False
    state["waiting_for_approval_type"] = None
    path.write_text(json.dumps(state), encoding="utf-8")

    result = stop_pipeline.decide({}, tmp_path, path)

    assert result == {"decision": "block", "reason": stop_pipeline.DIRECTIVES[label]}


# ═══════════════════════════════════════════════════════════════════════════
# T-7 (F9, F10): Phase 2 조건부 아키텍처, 구 PHASE2 별칭, Phase 3 worktree
# ═══════════════════════════════════════════════════════════════════════════

import re

NEW_PHASE2 = ["PHASE2_ARCH_START", "PHASE2_ARCH_DONE", "PHASE2_ARCH_SKIP"]
OLD_PHASE2 = [
    "PHASE2_START",
    "PHASE2_WORKTREE_CREATED",
    "PHASE2_ARCH_STRUCTURE_DONE",
    "PHASE2_ARCH_USER_APPROVED",
    "PHASE2_UI_DESIGN_COMPLETE",
    "PHASE2_API_DESIGN_COMPLETE",
    "PHASE2_DESIGN_USER_APPROVED",
    "PHASE2_USER_APPROVED",
]
DELETED_AGENTS = [
    "sdd-ui-designer",
    "sdd-api-designer",
    "sdd-architect-reviewer",
    "sdd-context-manager",
]
# 선행 파일 검사가 걸려 있어 파일이 없으면 경고 접미사가 붙는 구 라벨
OLD_PHASE2_WITH_CHECK = [
    "PHASE2_WORKTREE_CREATED",
    "PHASE2_ARCH_STRUCTURE_DONE",
    "PHASE2_UI_DESIGN_COMPLETE",
    "PHASE2_API_DESIGN_COMPLETE",
]


def _line_with(text: str, *needles: str) -> str:
    for ln in text.splitlines():
        if all(n in ln for n in needles):
            return ln
    pytest.fail(f"{needles} 를 모두 포함한 줄이 없다:\n{text}")


@pytest.mark.parametrize("label", NEW_PHASE2 + OLD_PHASE2 + ["PHASE3_WORKTREE_CREATED"])
def test_t7_label_keys_exist_with_prefix(stop_pipeline, label):
    text = stop_pipeline.DIRECTIVES.get(label)
    assert isinstance(text, str) and text.startswith("[SDD-PIPELINE]"), label


# ── PHASE1_USER_APPROVED: 아키텍처 필요 여부 분기 ───────────────────────────


def test_phase1_user_approved_branches_on_architecture_need(stop_pipeline):
    text = stop_pipeline.DIRECTIVES["PHASE1_USER_APPROVED"]
    start = _line_with(text, "PHASE2_ARCH_START")
    skip = _line_with(text, "PHASE2_ARCH_SKIP")
    assert "불필요" in skip
    assert "불필요" not in start and "필요" in start
    assert "PHASE2_START" not in text
    assert "설계 결정" in text
    # 판단(설계 결정 확인)이 전이 지시보다 먼저 나온다
    assert text.index("설계 결정") < text.index("PHASE2_ARCH_START")


# ── 새 Phase 2 라벨 ─────────────────────────────────────────────────────────


def test_arch_start_directive_dispatches_stack_architect_on_main_checkout(stop_pipeline):
    text = stop_pipeline.DIRECTIVES["PHASE2_ARCH_START"]
    for name in ["webapp-architect", "flutter-architect", "native-architect"]:
        assert name in text
    assert "설계 결정" in text
    assert "메인 체크아웃" in text
    assert "docs/sdd/design/arch" not in text
    assert text.index("architect") < text.index("PHASE2_ARCH_DONE")


@pytest.mark.parametrize("label", ["PHASE2_ARCH_DONE", "PHASE2_ARCH_SKIP"])
def test_arch_done_and_skip_directives_transition_to_phase3_plan_start(
    stop_pipeline, label
):
    text = stop_pipeline.DIRECTIVES[label]
    assert "PHASE3_PLAN_START" in text
    line = _line_with(text, "PHASE3_PLAN_START")
    assert "current_label" in line


@pytest.mark.parametrize("label", NEW_PHASE2 + ["PHASE3_PLAN_START"])
def test_decide_blocks_with_directive_verbatim_for_new_phase2_and_plan_start(
    stop_pipeline, tmp_path, label
):
    path = _write_state(tmp_path, stop_pipeline, label)

    assert stop_pipeline.decide({}, tmp_path, path) == {
        "decision": "block",
        "reason": stop_pipeline.DIRECTIVES[label],
    }


# ── 구 PHASE2 8개 별칭 ──────────────────────────────────────────────────────


def test_old_phase2_aliases_share_one_directive(stop_pipeline):
    d = stop_pipeline.DIRECTIVES
    assert len({d[label] for label in OLD_PHASE2}) == 1


def test_old_phase2_alias_directive_proceeds_to_phase3_plan_start(stop_pipeline):
    text = stop_pipeline.DIRECTIVES["PHASE2_START"]
    assert "하위호환" in text
    assert "수정하지" in text
    assert "PHASE3_PLAN_START" in text
    # 기존 design/·context/ 문서를 건드리지 말라는 지시가 전이 지시보다 먼저
    assert text.index("수정하지") < text.index("PHASE3_PLAN_START")
    assert "current_label" in _line_with(text, "PHASE3_PLAN_START")


@pytest.mark.parametrize("label", OLD_PHASE2)
def test_old_phase2_alias_has_no_deleted_agents_or_mode_branches(stop_pipeline, label):
    text = stop_pipeline.DIRECTIVES[label]
    for name in DELETED_AGENTS:
        assert name not in text
    assert "FULL 모드" not in text
    assert "SIMPLE" not in text
    assert "FULL" not in text


@pytest.mark.parametrize("label", OLD_PHASE2)
def test_decide_old_phase2_label_in_stored_pipeline_blocks_with_alias(
    stop_pipeline, tmp_path, label
):
    path = _write_state(tmp_path, stop_pipeline, label)  # 선행 파일 없음, SIMPLE

    result = stop_pipeline.decide({}, tmp_path, path)

    expected = stop_pipeline.DIRECTIVES[label]
    if label in OLD_PHASE2_WITH_CHECK:
        expected = (
            f"{expected}\n\n⚠️ 전이 조건 미충족: [{label}] "
            "선행 파일이 아직 없습니다. directive 를 따라 생성하세요."
        )
    assert result == {"decision": "block", "reason": expected}
    assert "PHASE3_PLAN_START" in result["reason"]


# ── 삭제된 에이전트 이름 / 라벨 그래프 닫힘 (W5) ────────────────────────────


def test_no_directive_mentions_deleted_agents(stop_pipeline):
    for label, text in stop_pipeline.DIRECTIVES.items():
        if text is None:
            continue
        for name in DELETED_AGENTS:
            assert name not in text, f"{label} 가 삭제된 {name} 을 언급한다"


def test_directive_label_tokens_are_all_directive_keys(stop_pipeline):
    keys = set(stop_pipeline.DIRECTIVES)
    for label, text in stop_pipeline.DIRECTIVES.items():
        if text is None:
            continue
        for token in re.findall(r"PHASE\d_[A-Z_]+", text):
            if token.startswith("PHASE4_") and token not in keys:
                continue  # PHASE4 태스크 라벨 템플릿
            assert token in keys, f"{label} 본문의 {token} 이 DIRECTIVES 키가 아니다"


CHAIN = [
    ("PHASE1_USER_APPROVED", "PHASE2_ARCH_START"),
    ("PHASE1_USER_APPROVED", "PHASE2_ARCH_SKIP"),
    ("PHASE2_ARCH_START", "PHASE2_ARCH_DONE"),
    ("PHASE2_ARCH_DONE", "PHASE3_PLAN_START"),
    ("PHASE2_ARCH_SKIP", "PHASE3_PLAN_START"),
    ("PHASE3_PLAN_START", "PHASE3_WORKTREE_CREATED"),
    ("PHASE3_WORKTREE_CREATED", "PHASE3_TASKMASTER_DONE"),
    ("PHASE3_TASKMASTER_DONE", "PHASE3_DAG_CONSTRUCTED"),
    ("PHASE3_DAG_CONSTRUCTED", "PHASE3_USER_APPROVED"),
]


@pytest.mark.parametrize("src,dst", CHAIN)
def test_label_chain_each_directive_names_next_label(stop_pipeline, src, dst):
    assert dst in stop_pipeline.DIRECTIVES[src]
    assert dst in stop_pipeline.DIRECTIVES


# ── PHASE3_TASKMASTER_DONE 이후 directive 는 기존과 동일 ────────────────────


def test_directives_after_taskmaster_done_unchanged(stop_pipeline):
    d = stop_pipeline.DIRECTIVES
    assert d["PHASE3_TASKMASTER_DONE"] == (
        "[SDD-PIPELINE] 태스크 문서 생성 완료. DAG 구성 필요.\n"
        "Agent(sdd-taskmaster, mode='dag') 를 디스패치하여 ORCHESTRATOR_STATE.md 를 생성하세요.\n"
        "완료 후 current_label=PHASE3_DAG_CONSTRUCTED."
    )
    assert d["PHASE3_DAG_CONSTRUCTED"] == (
        "[SDD-PIPELINE] DAG 구성 완료. 사용자 승인 필요.\n"
        "1. 태스크 목록 + Wave 구성 + 예상 시간을 사용자에게 제시\n"
        "2. waiting_for_user=true, approval_type='plan' 설정\n"
        "3. 승인 시 current_label=PHASE3_USER_APPROVED"
    )
    assert d["PHASE3_USER_APPROVED"] == (
        "[SDD-PIPELINE] Phase 3 완료. Phase 4 진입.\n"
        "다음을 수행하세요:\n"
        "1. git commit --allow-empty -m 'chore: Phase 4 실행 시작'\n"
        "2. pipeline.json 의 current_label=PHASE4_WORKTREE_CREATED 로 갱신\n"
        "3. Skill(sdd-orchestrator) 를 호출하여 Wave/Task 실행을 위임\n"
        "파이프라인은 여기서 종료됩니다. 이후 Stop 훅은 개입하지 않습니다."
    )
