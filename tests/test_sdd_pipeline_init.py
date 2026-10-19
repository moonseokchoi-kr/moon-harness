"""T-4 (F7): init_pipeline 의 초기 라벨.

bash 로 pipeline-utils.sh 를 source 해 임시 CLAUDE_PROJECT_DIR 에서 실행한다
(zsh 는 local path 가 PATH 를 덮으므로 사용하지 않는다). mode 처리는 T-8 소관.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_UTILS = _REPO_ROOT / "hooks" / "enforcement" / "lib" / "pipeline-utils.sh"

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash 필요")


def _run_init(project_dir: Path, feature: str = "demo-feature", mode: str = "SIMPLE"):
    env = {
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "HOME": str(project_dir),
        "CLAUDE_PROJECT_DIR": str(project_dir),
    }
    return subprocess.run(
        ["bash", "-c", f'source "{_UTILS}" && init_pipeline "{feature}" "{mode}"'],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def test_init_pipeline_sets_interview_start_label(tmp_path):
    proc = _run_init(tmp_path)

    assert proc.returncode == 0, proc.stderr
    state = json.loads(
        (tmp_path / ".claude" / "state" / "pipeline.json").read_text(encoding="utf-8")
    )
    assert state["current_label"] == "PHASE1_INTERVIEW_START"


def test_init_pipeline_initial_label_not_legacy_alias(tmp_path):
    _run_init(tmp_path)

    state = json.loads(
        (tmp_path / ".claude" / "state" / "pipeline.json").read_text(encoding="utf-8")
    )
    assert state["current_label"] != "PHASE1_UX_RESEARCH_DONE"
    assert state["feature"] == "demo-feature"
    assert state["waiting_for_user"] is False
