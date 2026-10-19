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
    mode_arg = f' "{mode}"' if mode else ""
    env = {
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "HOME": str(project_dir),
        "CLAUDE_PROJECT_DIR": str(project_dir),
    }
    return subprocess.run(
        ["bash", "-c", f'source "{_UTILS}" && init_pipeline "{feature}"{mode_arg}'],
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


# ── T-8 (F11): FULL/SIMPLE 설계 모드 폐지 ─────────────────────────────


def _state(project_dir: Path) -> dict:
    return json.loads(
        (project_dir / ".claude" / "state" / "pipeline.json").read_text(encoding="utf-8")
    )


@pytest.mark.parametrize("mode", ["", "FULL", "SIMPLE"])
def test_init_pipeline_does_not_write_mode_key(tmp_path, mode):
    proc = _run_init(tmp_path, mode=mode)

    assert proc.returncode == 0, proc.stderr
    state = _state(tmp_path)
    assert "mode" not in state
    assert state["feature"] == "demo-feature"


@pytest.mark.parametrize("mode", ["", "FULL", "SIMPLE"])
def test_init_pipeline_message_does_not_print_mode(tmp_path, mode):
    proc = _run_init(tmp_path, mode=mode)

    assert proc.returncode == 0, proc.stderr
    assert "초기화 완료: demo-feature" in proc.stdout
    assert "FULL" not in proc.stdout
    assert "SIMPLE" not in proc.stdout


def _run_show(project_dir: Path):
    env = {
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "HOME": str(project_dir),
        "CLAUDE_PROJECT_DIR": str(project_dir),
    }
    return subprocess.run(
        ["bash", "-c", f'source "{_UTILS}" && show_pipeline'],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def test_show_pipeline_omits_mode_when_absent(tmp_path):
    _run_init(tmp_path, mode="")

    proc = _run_show(tmp_path)

    assert proc.returncode == 0, proc.stderr
    assert "demo-feature" in proc.stdout
    assert "mode" not in proc.stdout
    assert "None" not in proc.stdout


def test_show_pipeline_prints_mode_when_legacy_json_has_it(tmp_path):
    _run_init(tmp_path, mode="")
    path = tmp_path / ".claude" / "state" / "pipeline.json"
    state = json.loads(path.read_text(encoding="utf-8"))
    state["mode"] = "FULL"
    path.write_text(json.dumps(state), encoding="utf-8")

    proc = _run_show(tmp_path)

    assert proc.returncode == 0, proc.stderr
    assert "mode" in proc.stdout
    assert "FULL" in proc.stdout


# ── T-8 (F14): 구 라벨/예시 문자열 갱신 ───────────────────────────────


def test_pipeline_utils_header_comment_has_no_legacy_label_or_mode():
    header = _UTILS.read_text(encoding="utf-8").split("export PYTHONUTF8", 1)[0]

    assert "PHASE2_ARCH_STRUCTURE_DONE" not in header
    assert '"FULL"' not in header


def test_logging_sh_example_has_no_legacy_design_api_string():
    logging_sh = _UTILS.parent / "logging.sh"
    text = logging_sh.read_text(encoding="utf-8")

    assert "design/api" not in text
