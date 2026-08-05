"""tests/test_enforcement_hook_false_positives.py — file-ownership / dangerous-command 오탐 회귀

`.harness/LEARNING.md` 2026-07-01 + 2026-08-05 엔트리(독립 2신호)가 보고한 오탐을 고정한다.
두 훅 모두 bash 스크립트이므로 서브프로세스로 실측한다 — 훅은 매 호출이 콜드 프로세스이고,
in-process 모사는 실제 실행 경로를 검증하지 못한다(2026-08-04 T-12 엔트리).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OWNERSHIP_HOOK = REPO / "hooks" / "file-ownership.sh"
DANGEROUS_HOOK = REPO / "hooks" / "dangerous-command.sh"


def _run(hook: Path, payload: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(hook)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )


# ── file-ownership: 표 픽스처 ──────────────────────────────────────────────────

# 이 repo의 실제 표 방향 (태스크 먼저) — 산문·홀로 선 `/`가 섞인 셀 포함
STATE_TASK_FIRST = """# Orchestrator State

## 메타

- 상태: **{status}**

## 파일 소유권

| 태스크 | 소유 파일 (정확한 경로 — 디렉토리 와일드카드 금지) |
|--------|-------------------|
| T-2 | `hooks/lib/pkg/__init__.py`, `tests/conftest.py`(fixture 추가분만) — 위임됨(`__init__.py`=공개 API 재노출 / 정적검증) |
| T-4 | `hooks/lib/pkg/naming.py`, `tests/test_naming.py` |
| T-8 | `tests/fixtures/` |
"""

# 사용자가 겪은 repo의 표 방향 (파일 먼저) — 설명문에 `pick` 이 섞인 셀 포함
STATE_FILES_FIRST = """# Orchestrator State

## 메타

- 상태: **{status}**

## 파일 소유권

| 파일 경로 | 소유 태스크 | 비고 |
|-----------|-------------|------|
| `src/render/filmap.cpp` | T-3 | RenderFilmap pick 분기 원복 |
| `hooks/lib/pkg/naming.py` | T-4 | — |
"""


def _write_state(tmp_path: Path, template: str, status: str) -> Path:
    state = tmp_path / "docs" / "sdd" / "ORCHESTRATOR_STATE.md"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(template.format(status=status), encoding="utf-8")
    return state


def _edit(cwd: Path, file_path: str) -> dict:
    return {"tool_name": "Edit", "tool_input": {"file_path": file_path}, "cwd": str(cwd)}


# ── (1) 라이프사이클 상태 게이트 ───────────────────────────────────────────────


def test_completed_cycle_does_not_enforce(tmp_path: Path) -> None:
    """완료된 사이클의 STATE는 enforce하지 않는다 (2026-07-01 엔트리)."""
    _write_state(tmp_path, STATE_TASK_FIRST, "COMPLETED")
    r = _run(OWNERSHIP_HOOK, _edit(tmp_path, str(tmp_path / "hooks/lib/pkg/naming.py")))
    assert r.returncode == 0, r.stderr


def test_executing_cycle_still_enforces_real_owner(tmp_path: Path) -> None:
    """활성 구간에서는 실제 소유 파일을 계속 차단한다 (정탐 유지)."""
    _write_state(tmp_path, STATE_TASK_FIRST, "EXECUTING")
    r = _run(OWNERSHIP_HOOK, _edit(tmp_path, str(tmp_path / "hooks/lib/pkg/naming.py")))
    assert r.returncode == 2, r.stdout
    assert "T-4" in r.stderr


def test_unparseable_status_fails_open(tmp_path: Path) -> None:
    """상태를 해석할 수 없으면 통과한다 (fail-open — ownership은 안전 게이트가 아니다)."""
    _write_state(tmp_path, STATE_TASK_FIRST, "???")
    r = _run(OWNERSHIP_HOOK, _edit(tmp_path, str(tmp_path / "hooks/lib/pkg/naming.py")))
    assert r.returncode == 0, r.stderr


def test_missing_status_line_fails_open(tmp_path: Path) -> None:
    state = tmp_path / "docs" / "sdd" / "ORCHESTRATOR_STATE.md"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(
        "# S\n\n## 파일 소유권\n\n| 태스크 | 소유 파일 |\n|---|---|\n| T-4 | `a/b.py` |\n",
        encoding="utf-8",
    )
    r = _run(OWNERSHIP_HOOK, _edit(tmp_path, str(tmp_path / "a/b.py")))
    assert r.returncode == 0, r.stderr


# ── (2) 헤더 기반 컬럼 판별 ────────────────────────────────────────────────────


def test_files_first_table_does_not_parse_prose_as_paths(tmp_path: Path) -> None:
    """`| 파일 경로 | 소유 태스크 | 비고 |` 순서에서 비고 산문이 파일 목록으로 파싱되면 안 된다.

    산문 "RenderFilmap pick 분기 원복"의 `pick`이 무관한 경로에 걸리던 사례.
    """
    _write_state(tmp_path, STATE_FILES_FIRST, "EXECUTING")
    r = _run(
        OWNERSHIP_HOOK,
        _edit(tmp_path, str(tmp_path / "skills/release-cherry-pick/SKILL.md")),
    )
    assert r.returncode == 0, r.stderr


def test_files_first_table_still_enforces_real_owner(tmp_path: Path) -> None:
    """컬럼 순서가 반대여도 실제 소유 파일은 차단한다 (정탐 유지)."""
    _write_state(tmp_path, STATE_FILES_FIRST, "EXECUTING")
    r = _run(OWNERSHIP_HOOK, _edit(tmp_path, str(tmp_path / "src/render/filmap.cpp")))
    assert r.returncode == 2, r.stdout
    assert "T-3" in r.stderr


# ── (3) 경로 형태 토큰만 매칭 + 경계 고정 ─────────────────────────────────────


def test_lone_slash_in_prose_does_not_match_everything(tmp_path: Path) -> None:
    """소유 셀 산문의 홀로 선 `/`가 모든 경로에 걸리던 버그."""
    _write_state(tmp_path, STATE_TASK_FIRST, "EXECUTING")
    r = _run(
        OWNERSHIP_HOOK, _edit(tmp_path, str(tmp_path / ".claude-plugin/marketplace.json"))
    )
    assert r.returncode == 0, r.stderr


def test_substring_match_does_not_block_unrelated_path(tmp_path: Path) -> None:
    """경계 고정 — 소유 경로를 부분문자열로 포함하는 다른 경로는 차단하지 않는다."""
    _write_state(tmp_path, STATE_TASK_FIRST, "EXECUTING")
    r = _run(
        OWNERSHIP_HOOK, _edit(tmp_path, str(tmp_path / "hooks/lib/pkg/naming_helpers.py"))
    )
    assert r.returncode == 0, r.stderr


def test_directory_prefix_ownership_still_enforced(tmp_path: Path) -> None:
    """디렉토리 소유(`tests/fixtures/`)는 그 하위를 계속 차단한다 (정탐 유지)."""
    _write_state(tmp_path, STATE_TASK_FIRST, "EXECUTING")
    r = _run(OWNERSHIP_HOOK, _edit(tmp_path, str(tmp_path / "tests/fixtures/sample.md")))
    assert r.returncode == 2, r.stdout
    assert "T-8" in r.stderr


# ── (4) 레포 밖 경로 즉시 통과 ────────────────────────────────────────────────


def test_path_outside_project_dir_passes(tmp_path: Path) -> None:
    """레포 밖 절대경로(스크래치패드·~/.claude 등)는 소유권 주장 근거가 없다."""
    _write_state(tmp_path, STATE_TASK_FIRST, "EXECUTING")
    r = _run(OWNERSHIP_HOOK, _edit(tmp_path, "/private/tmp/scratch/learning-append.md"))
    assert r.returncode == 0, r.stderr


def test_parent_escape_path_passes(tmp_path: Path) -> None:
    _write_state(tmp_path, STATE_TASK_FIRST, "EXECUTING")
    r = _run(OWNERSHIP_HOOK, _edit(tmp_path, str(tmp_path / "../outside/naming.py")))
    assert r.returncode == 0, r.stderr


# ── dangerous-command: heredoc 싱크 판별 ──────────────────────────────────────


def _bash(cmd: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": cmd}}


HARD_RESET = "git reset " + "--hard HEAD~1"
RM_RF = "rm -rf " + "/important/data"


def test_documented_command_in_file_write_heredoc_is_not_flagged() -> None:
    """파일 쓰기 싱크로 가는 heredoc 본문의 명령 문서화는 실제 명령이 아니다."""
    cmd = f"cat >> notes.md <<'EOF'\n주의: {HARD_RESET} 는 히스토리를 파괴한다\nEOF"
    r = _run(DANGEROUS_HOOK, _bash(cmd))
    assert r.returncode == 0, r.stderr


def test_documented_rm_in_file_write_heredoc_is_not_flagged() -> None:
    cmd = f"cat > doc.md <<'DOC'\n예시 명령: {RM_RF}\nDOC"
    r = _run(DANGEROUS_HOOK, _bash(cmd))
    assert r.returncode == 0, r.stderr


def test_interpreter_heredoc_body_is_still_inspected() -> None:
    """인터프리터로 파이프되는 heredoc 본문은 계속 검사한다 — 무조건 제외는 우회로가 된다."""
    cmd = f"bash <<'EOF'\n{RM_RF}\nEOF"
    r = _run(DANGEROUS_HOOK, _bash(cmd))
    assert r.returncode == 2, f"heredoc 우회 허용됨: {r.stdout}"


def test_python_heredoc_body_is_still_inspected() -> None:
    cmd = f"python3 - <<'PY'\nimport os; os.system(\"{RM_RF}\")\nPY"
    r = _run(DANGEROUS_HOOK, _bash(cmd))
    assert r.returncode == 2, f"heredoc 우회 허용됨: {r.stdout}"


def test_plain_dangerous_command_still_flagged() -> None:
    """heredoc 없는 실제 명령은 그대로 차단 (정탐 유지)."""
    r = _run(DANGEROUS_HOOK, _bash(HARD_RESET))
    assert r.returncode == 2, r.stdout


def test_command_part_of_file_write_heredoc_is_still_inspected() -> None:
    """heredoc의 명령부 자체는 본문 제외와 무관하게 검사한다."""
    cmd = f"{RM_RF} && cat > doc.md <<'DOC'\nharmless\nDOC"
    r = _run(DANGEROUS_HOOK, _bash(cmd))
    assert r.returncode == 2, r.stdout


def test_safe_rm_target_still_passes() -> None:
    r = _run(DANGEROUS_HOOK, _bash("rm -rf node_modules"))
    assert r.returncode == 0, r.stderr
