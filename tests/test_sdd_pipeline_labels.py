"""T-4 (F7, F8 훅 측): Phase 1 라벨 PHASE1_INTERVIEW_START 와 구 라벨 별칭.

새/별칭 라벨 문자열이 DIRECTIVES 와 directive 본문에서 서로 닫혀 있는지 고정한다
(W5). Phase 2·3 라벨은 T-7 소유이므로 여기서 다루지 않는다. 키 집합 동일성은
단정하지 않는다.
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
