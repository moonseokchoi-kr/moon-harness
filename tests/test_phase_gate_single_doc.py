"""T-8 (F14): phase-gate.sh 가 단일 문서 흐름(design/ 없음)에서 오경고를 내지 않는다.

임시 CLAUDE_PROJECT_DIR 에 docs/sdd 구조를 만들고 훅을 실제 실행해 stderr 를 검사한다.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_GATE = _REPO_ROOT / "hooks" / "enforcement" / "phase-gate.sh"

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash 필요")


def _run_gate(project_dir: Path) -> subprocess.CompletedProcess:
    env = {
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "HOME": str(project_dir),
        "CLAUDE_PROJECT_DIR": str(project_dir),
    }
    return subprocess.run(
        ["bash", str(_GATE)],
        env=env,
        cwd=project_dir,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def _touch(path: Path, body: str = "# doc\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def test_spec_only_without_design_dir_emits_no_phase2_warning(tmp_path):
    _touch(tmp_path / "docs" / "sdd" / "spec" / "2026-10-19-demo.md")

    proc = _run_gate(tmp_path)

    assert proc.returncode == 0
    assert "Phase 2" not in proc.stderr
    assert "architecture" not in proc.stderr


def test_tasks_without_design_dir_emit_no_architecture_warning(tmp_path):
    _touch(tmp_path / "docs" / "sdd" / "spec" / "2026-10-19-demo.md")
    _touch(tmp_path / "docs" / "sdd" / "task" / "demo" / "T-1-x.md")

    proc = _run_gate(tmp_path)

    assert proc.returncode == 0
    assert "Phase 2" not in proc.stderr
    assert "architecture" not in proc.stderr
    assert "PHASE-GATE" not in proc.stderr


def test_legacy_design_ui_docs_do_not_trigger_ui_or_e2e_warning(tmp_path):
    _touch(tmp_path / "docs" / "sdd" / "spec" / "2026-10-19-demo.md")
    _touch(tmp_path / "docs" / "sdd" / "design" / "ui" / "old-cycle.md")

    proc = _run_gate(tmp_path)

    assert proc.returncode == 0
    assert "UI 명세" not in proc.stderr
    assert "e2e-config" not in proc.stderr
    assert "E2E" not in proc.stderr


def test_sdd_not_started_is_silent(tmp_path):
    proc = _run_gate(tmp_path)

    assert proc.returncode == 0
    assert proc.stderr == ""


def test_context_dir_alone_no_longer_counts_as_sdd_started(tmp_path):
    # 미시작 판정은 SPEC_DIR 기준 — context 만 있고 spec 이 없으면 조용히 종료한다.
    _touch(tmp_path / "docs" / "sdd" / "context" / "old.md")

    proc = _run_gate(tmp_path)

    assert proc.returncode == 0
    assert "PHASE-GATE" not in proc.stderr


def test_tasks_without_spec_still_warn(tmp_path):
    # SPEC_DIR 은 존재하나 spec 문서가 없는 상태 + task 존재 → spec 누락 경고 유지
    (tmp_path / "docs" / "sdd" / "spec").mkdir(parents=True)
    _touch(tmp_path / "docs" / "sdd" / "task" / "T-1-x.md")

    proc = _run_gate(tmp_path)

    assert proc.returncode == 0
    assert "PHASE-GATE" in proc.stderr
    assert "spec" in proc.stderr


def test_orchestrator_state_without_task_docs_still_warns(tmp_path):
    _touch(tmp_path / "docs" / "sdd" / "spec" / "2026-10-19-demo.md")
    _touch(tmp_path / "docs" / "sdd" / "ORCHESTRATOR_STATE.md", "status: EXECUTING\n")

    proc = _run_gate(tmp_path)

    assert proc.returncode == 0
    assert "PHASE-GATE" in proc.stderr
    assert "T-*.md" in proc.stderr


def test_orchestrator_state_with_task_docs_is_quiet(tmp_path):
    _touch(tmp_path / "docs" / "sdd" / "spec" / "2026-10-19-demo.md")
    # 훅의 `ls a b` 는 글롭 하나라도 안 맞으면 실패하므로 평면/하위 디렉터리 두 형태를 모두 둔다.
    _touch(tmp_path / "docs" / "sdd" / "task" / "T-1-x.md")
    _touch(tmp_path / "docs" / "sdd" / "task" / "demo" / "T-2-y.md")
    _touch(tmp_path / "docs" / "sdd" / "ORCHESTRATOR_STATE.md", "status: EXECUTING\n")

    proc = _run_gate(tmp_path)

    assert proc.returncode == 0
    assert "PHASE-GATE" not in proc.stderr


# ── 스크립트 텍스트 (블록 단위) ────────────────────────────────────────

_TEXT = _GATE.read_text(encoding="utf-8")
_CODE = "\n".join(
    line for line in _TEXT.splitlines() if not line.lstrip().startswith("#")
)


@pytest.mark.parametrize(
    "needle",
    ["DESIGN_DIR", "HAS_ARCH", "HAS_UI", "HAS_API", "architecture 설계 문서", "e2e-config", "CONTEXT_DIR", "2_done"],
)
def test_phase_gate_script_has_no_design_block_remnants(needle):
    assert needle not in _TEXT


def test_phase_gate_script_has_no_removed_agent_names():
    for name in ("sdd-ui-designer", "sdd-api-designer", "sdd-context-manager", "sdd-architect-reviewer"):
        assert name not in _TEXT


def test_phase_gate_not_started_check_uses_spec_dir():
    early_exit = [
        line for line in _CODE.splitlines() if "exit 0" in line and "SPEC_DIR" in line
    ]
    assert early_exit, "SPEC_DIR 기준 미시작 조기 종료가 있어야 한다"
    assert all("CONTEXT" not in line for line in early_exit)


def test_phase_gate_remains_warn_only():
    # 차단 exit(2)·차단 JSON 없이 항상 exit 0 으로 끝난다.
    assert not re.search(r"\bexit\s+[12]\b", _CODE)
