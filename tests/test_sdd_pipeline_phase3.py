"""T-7 (F10): Phase 3 worktree 전제 검사와 PHASE3_WORKTREE_CREATED 라벨.

has_tasks / has_orchestrator_state 가 pipeline.json 의 worktree_path 를 우선하고
없으면 project_dir 로 폴백하는지, PHASE3_WORKTREE_CREATED 의 선행 검사(has_worktree)와
directive 의 지시 순서·조건을 고정한다. 모듈 전역 mock 없이 tmp_path 두 디렉터리를 주입한다.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_STOP_PIPELINE_PATH = _REPO_ROOT / "hooks" / "enforcement" / "stop-pipeline.py"

WT_CREATED = "PHASE3_WORKTREE_CREATED"
UNMET_PREFIX = "⚠️ 전이 조건 미충족: "


@pytest.fixture(scope="module")
def stop_pipeline():
    spec = importlib.util.spec_from_file_location("stop_pipeline", _STOP_PIPELINE_PATH)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


@pytest.fixture()
def dirs(tmp_path):
    project = tmp_path / "project"
    worktree = tmp_path / "worktree"
    project.mkdir()
    worktree.mkdir()
    return project, worktree


def _write_state(project: Path, mod, label: str, **overrides) -> Path:
    state = {
        "current_label": label,
        "feature": "demo",
        "worktree_path": "",
        "waiting_for_user": False,
        "session_id": "",
        "circuit_breaker": {},
        "last_updated": mod.now_iso(),
    }
    state.update(overrides)
    path = project / ".claude" / "state" / "pipeline.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state), encoding="utf-8")
    return path


def _make_task(root: Path, feature: str = "demo") -> None:
    d = root / "docs" / "sdd" / "task" / feature
    d.mkdir(parents=True)
    (d / "T-1-x.md").write_text("# T-1", encoding="utf-8")


def _make_state_md(root: Path) -> None:
    d = root / "docs" / "sdd"
    d.mkdir(parents=True)
    (d / "ORCHESTRATOR_STATE.md").write_text("# state", encoding="utf-8")


# ── has_tasks: worktree_path 우선, project_dir 폴백 ─────────────────────────


def test_taskmaster_done_met_when_tasks_only_in_worktree(stop_pipeline, dirs):
    project, worktree = dirs
    _make_task(worktree)

    met, _ = stop_pipeline.label_prerequisite_met(
        "PHASE3_TASKMASTER_DONE",
        {"feature": "demo", "worktree_path": str(worktree)},
        project,
    )

    assert met is True


def test_taskmaster_done_met_via_project_dir_when_no_worktree_path(stop_pipeline, dirs):
    project, _ = dirs
    _make_task(project)

    met, _ = stop_pipeline.label_prerequisite_met(
        "PHASE3_TASKMASTER_DONE", {"feature": "demo"}, project
    )

    assert met is True


def test_taskmaster_done_unmet_when_tasks_in_neither(stop_pipeline, dirs):
    project, worktree = dirs

    met, reason = stop_pipeline.label_prerequisite_met(
        "PHASE3_TASKMASTER_DONE",
        {"feature": "demo", "worktree_path": str(worktree)},
        project,
    )

    assert met is False
    assert "PHASE3_TASKMASTER_DONE" in reason


# ── has_orchestrator_state: worktree_path 우선, project_dir 폴백 ────────────


def test_dag_constructed_met_when_state_only_in_worktree(stop_pipeline, dirs):
    project, worktree = dirs
    _make_state_md(worktree)

    met, _ = stop_pipeline.label_prerequisite_met(
        "PHASE3_DAG_CONSTRUCTED",
        {"feature": "demo", "worktree_path": str(worktree)},
        project,
    )

    assert met is True


def test_dag_constructed_met_via_project_dir_when_no_worktree_path(stop_pipeline, dirs):
    project, _ = dirs
    _make_state_md(project)

    met, _ = stop_pipeline.label_prerequisite_met(
        "PHASE3_DAG_CONSTRUCTED", {"feature": "demo"}, project
    )

    assert met is True


def test_dag_constructed_unmet_when_state_in_neither(stop_pipeline, dirs):
    project, worktree = dirs

    met, reason = stop_pipeline.label_prerequisite_met(
        "PHASE3_DAG_CONSTRUCTED",
        {"feature": "demo", "worktree_path": str(worktree)},
        project,
    )

    assert met is False
    assert "PHASE3_DAG_CONSTRUCTED" in reason


def test_decide_taskmaster_done_with_tasks_only_in_worktree_has_no_warning(
    stop_pipeline, dirs
):
    project, worktree = dirs
    _make_task(worktree)
    path = _write_state(
        project, stop_pipeline, "PHASE3_TASKMASTER_DONE", worktree_path=str(worktree)
    )

    result = stop_pipeline.decide({}, project, path)

    assert result == {
        "decision": "block",
        "reason": stop_pipeline.DIRECTIVES["PHASE3_TASKMASTER_DONE"],
    }


# ── PHASE3_WORKTREE_CREATED 선행 검사 (has_worktree) ────────────────────────


def test_worktree_created_prerequisite_met_when_dir_exists(stop_pipeline, dirs):
    project, worktree = dirs

    met, reason = stop_pipeline.label_prerequisite_met(
        WT_CREATED, {"feature": "demo", "worktree_path": str(worktree)}, project
    )

    assert (met, reason) == (True, "")


@pytest.mark.parametrize("missing", ["", "NONEXISTENT"])
def test_worktree_created_prerequisite_unmet_when_path_absent(
    stop_pipeline, dirs, missing
):
    project, _ = dirs
    wt = "" if missing == "" else str(project / "no-such-worktree")

    met, reason = stop_pipeline.label_prerequisite_met(
        WT_CREATED, {"feature": "demo", "worktree_path": wt}, project
    )

    assert met is False
    assert WT_CREATED in reason


def test_decide_worktree_created_unmet_adds_existing_format_warning(
    stop_pipeline, dirs
):
    project, _ = dirs
    path = _write_state(
        project, stop_pipeline, WT_CREATED, worktree_path=str(project / "missing")
    )

    result = stop_pipeline.decide({}, project, path)

    assert result == {
        "decision": "block",
        "reason": (
            f"{stop_pipeline.DIRECTIVES[WT_CREATED]}\n\n"
            f"{UNMET_PREFIX}[{WT_CREATED}] 선행 파일이 아직 없습니다. "
            "directive 를 따라 생성하세요."
        ),
    }


def test_decide_worktree_created_met_has_no_warning(stop_pipeline, dirs):
    project, worktree = dirs
    path = _write_state(project, stop_pipeline, WT_CREATED, worktree_path=str(worktree))

    result = stop_pipeline.decide({}, project, path)

    assert result == {
        "decision": "block",
        "reason": stop_pipeline.DIRECTIVES[WT_CREATED],
    }


# ── 구 has_* 함수 유지 ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "name",
    ["has_spec", "has_blocker_pass", "has_worktree", "has_arch", "has_ui", "has_api", "has_context"],
)
def test_legacy_has_functions_still_exist(stop_pipeline, name):
    assert callable(getattr(stop_pipeline, name))


# ── PHASE3_WORKTREE_CREATED directive: 지시 순서·조건 ───────────────────────


def _lines(text: str) -> list[str]:
    return [ln for ln in text.splitlines() if ln.strip()]


def _line_with(text: str, *needles: str) -> str:
    for ln in _lines(text):
        if all(n in ln for n in needles):
            return ln
    pytest.fail(f"{needles} 를 모두 포함한 줄이 없다:\n{text}")


def test_worktree_created_directive_exists_and_references_taskmaster_done(stop_pipeline):
    text = stop_pipeline.DIRECTIVES.get(WT_CREATED)
    assert isinstance(text, str) and text.startswith("[SDD-PIPELINE]")
    assert "PHASE3_TASKMASTER_DONE" in text


def test_worktree_created_directive_moves_spec_not_copies(stop_pipeline):
    text = stop_pipeline.DIRECTIVES[WT_CREATED]
    assert "이동" in text
    assert "docs/sdd/spec/" in text
    assert "cp " not in text
    for m in re.finditer("복사", text):
        line_end = text.find("\n", m.start())
        tail = text[m.start() : line_end if line_end != -1 else None]
        assert re.search(r"아님|아니|금지|말", tail), f"복사를 지시하는 문장: {tail!r}"


def test_worktree_created_directive_three_cases_in_order(stop_pipeline):
    text = stop_pipeline.DIRECTIVES[WT_CREATED]
    mv_line = _line_with(text, "mv")
    cmp_line = _line_with(text, "cmp")
    differ_line = _line_with(text, "waiting_for_user=true")

    # (a) 파일이 없으면 mv
    assert "없" in mv_line
    # (b) 있고 cmp 동일 -> 메인 사본 삭제 후 진행
    assert "동일" in cmp_line and "삭제" in cmp_line and "메인" in cmp_line
    # (c) 있고 다름 -> 전이 중단 + 사용자 보고
    assert "다르" in differ_line
    assert "중단" in differ_line or "멈" in differ_line
    assert "보고" in differ_line
    # 케이스 순서 a -> b -> c
    assert text.index(mv_line) < text.index(cmp_line) < text.index(differ_line)


def test_worktree_created_directive_forbids_deciding_canonical_arbitrarily(stop_pipeline):
    text = stop_pipeline.DIRECTIVES[WT_CREATED]
    line = _line_with(text, "정본")
    assert "임의" in line
    assert "않" in line or "금지" in line


def test_worktree_created_directive_orders_move_then_taskmaster_then_transition(
    stop_pipeline,
):
    text = stop_pipeline.DIRECTIVES[WT_CREATED]
    move = text.index("mv")
    taskmaster = text.index("sdd-taskmaster")
    transition = text.index("PHASE3_TASKMASTER_DONE")
    assert move < taskmaster < transition


def test_worktree_created_directive_gives_taskmaster_worktree_based_input(stop_pipeline):
    text = stop_pipeline.DIRECTIVES[WT_CREATED]
    line = _line_with(text, "sdd-taskmaster")
    assert "tasks" in line
    assert "worktree" in line
    assert "구현 계획" in text


# ── PHASE3_PLAN_START directive ─────────────────────────────────────────────


def test_plan_start_directive_creates_worktree_then_moves_to_worktree_created(
    stop_pipeline,
):
    text = stop_pipeline.DIRECTIVES["PHASE3_PLAN_START"]
    assert "Skill(git-worktree)" in text
    assert "worktree_path" in text
    assert "sdd-taskmaster" not in text, "taskmaster 디스패치는 PHASE3_WORKTREE_CREATED 로 이동했다"
    assert text.index("Skill(git-worktree)") < text.rindex(WT_CREATED)


def test_plan_start_directive_skips_creation_when_worktree_path_already_exists(
    stop_pipeline,
):
    text = stop_pipeline.DIRECTIVES["PHASE3_PLAN_START"]
    line = _line_with(text, "이미")
    assert "worktree_path" in line
    assert "건너" in line
    assert WT_CREATED in line


# ── spec 충돌 대기: approval_type 과 재개 경로 (T-7 리뷰 P1) ────────────────


def test_worktree_created_conflict_branch_sets_spec_conflict_approval_type(stop_pipeline):
    text = stop_pipeline.DIRECTIVES[WT_CREATED]
    line = _line_with(text, "다르")
    assert "set_waiting_for_user true spec_conflict" in line


def test_worktree_created_directive_resume_keeps_label_and_restarts(stop_pipeline):
    text = stop_pipeline.DIRECTIVES[WT_CREATED]
    release = _line_with(text, "set_waiting_for_user false null")
    assert WT_CREATED in release
    assert "유지" in release
    assert "다시" in release or "처음부터" in release


def test_worktree_created_directive_forbids_advance_label_on_conflict_resolution(
    stop_pipeline,
):
    text = stop_pipeline.DIRECTIVES[WT_CREATED]
    line = _line_with(text, "advance_label")
    assert "하지 않" in line or "금지" in line


def test_decide_spec_conflict_waiting_continues_then_reinjects_after_release(
    stop_pipeline, dirs
):
    project, worktree = dirs
    path = _write_state(
        project,
        stop_pipeline,
        WT_CREATED,
        worktree_path=str(worktree),
        waiting_for_user=True,
        waiting_for_approval_type="spec_conflict",
    )

    waiting = stop_pipeline.decide({}, project, path)
    assert waiting.get("continue") is True

    _write_state(
        project,
        stop_pipeline,
        WT_CREATED,
        worktree_path=str(worktree),
        waiting_for_user=False,
        waiting_for_approval_type=None,
    )

    released = stop_pipeline.decide({}, project, path)
    assert released == {
        "decision": "block",
        "reason": stop_pipeline.DIRECTIVES[WT_CREATED],
    }
