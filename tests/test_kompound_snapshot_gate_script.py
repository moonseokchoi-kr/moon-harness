"""tests/test_kompound_snapshot_gate_script.py — T-13 `kompound-snapshot-gate.sh`
bash 서브프로세스 통합 테스트 (F2/F14).

설계 SSOT: `docs/sdd/design/arch/2026-07-29-kompound-snapshot-hook.md` §5.2
(F2 전체), §5.2.1(확정 사항)·§5.2.2(프리필터)·§5.2.3(11개 분기 제어 흐름)·
§5.2.4(3축 원칙). task: `2026-07-29-T-13-t2-gate-hooks-registration.md`.

이 파일은 실제 bash 스크립트를 `subprocess`로(stdin에 PreToolUse JSON을 넣어)
실행한다 — `worktree-add-gate.sh`류 기존 게이트의 실행 계약(stdin JSON →
exit code/stderr)을 그대로 따르는 관례다. `fake_kompound_env`(tests/conftest.py,
T-2)로 만든 격리 kompound만 사용한다 — 실제 kompound(marvelous_kompound)나
실제 홈 디렉토리는 절대 건드리지 않는다.

핵심적으로 이 파일이 검증하는 것 — bash가 정책(차단/통과)을 재유도하지
않고 코어(`report.blocks_deletion(verdict)`)에 위임한다는 사실을 **exit
code로 자체 판단하면 실패할 수밖에 없는 형태**로 고정한다:
`verify_failed`(50)·`catalog_unparsed`(55)는 exit code가 0이 아니어도 반드시
통과(exit 0)해야 하고, `write_failed`(60)·`precondition_failed`(40)·
`unmapped_blocking`(45)·`busy`(70)·`scan_error`(30)는 반드시 차단(exit 2)해야
한다.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable

import pytest

from hooks.lib.kompound_snapshot import report, runtime_state

_REPO_ROOT = Path(__file__).resolve().parents[1]
_GATE_SCRIPT = _REPO_ROOT / "hooks" / "enforcement" / "kompound-snapshot-gate.sh"
_HOOKS_JSON_PATH = _REPO_ROOT / "hooks" / "hooks.json"


# ── git/fixture 헬퍼 (다른 kompound_snapshot 테스트 파일과 동일한 관례) ──────


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=fixture@example.invalid",
            "-c",
            "user.name=gate-script-test",
            "-c",
            "commit.gpgsign=false",
            *args,
        ],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def _seed_worktree_repo(
    scope_root: Path, repo_name: str, wt_name: str, feature: str, kinds: Iterable[str] = ("spec",)
) -> Path:
    """`scope_root/<repo_name>/worktrees/<wt_name>/docs/sdd/<kind>/...`를 만든다
    (워크트리 전용 문서 케이스, arch §5.4.2 규칙 1). `wt_target`이 `worktrees/`
    세그먼트를 갖는 이 디렉토리를 삭제 대상으로 인식한다."""
    wt_root = scope_root / repo_name / "worktrees" / wt_name
    for kind in kinds:
        d = wt_root / "docs" / "sdd" / kind
        d.mkdir(parents=True, exist_ok=True)
        (d / f"2026-08-01-{feature}.md").write_text(f"# {feature} {kind} fixture\n", encoding="utf-8")
    return wt_root


def _inject_bad_raw_subdir(kompound: Path) -> None:
    """`raw/`에 `assets/` 외 서브디렉토리를 심고 커밋한다 — `check_flat_structure`
    (F8 게이트)가 항상 실패하도록 만드는, 우리 문서와 무관한 구조적 위반
    (test_kompound_snapshot_apply.py와 동일한 기법)."""
    bad_dir = kompound / "raw" / "badsubdir"
    bad_dir.mkdir(parents=True, exist_ok=True)
    (bad_dir / "placeholder.md").write_text("placeholder\n", encoding="utf-8")
    _git("add", "-A", cwd=kompound)
    _git("commit", "-q", "-m", "test setup: inject raw/ subdirectory to fail flat_structure gate", cwd=kompound)


def _write_config_file(path: Path, cfg: Dict[str, Any]) -> Path:
    path.write_text(json.dumps(cfg), encoding="utf-8")
    return path


@pytest.fixture()
def gate_env(fake_kompound_env: Dict[str, Any], tmp_path: Path) -> Dict[str, Any]:
    """게이트 서브프로세스 실행 공통 환경 — `fake_kompound_env`의 kompound을
    재사용하되, 스캔 대상은 이 fixture가 만드는 격리된 `scope_root`를 쓴다.

    `prefix_map`에 `delta-service`(등록됐지만 registry엔 아직 없는 신규
    프로젝트)를 추가해 둔다 — `catalog_unparsed` 유도(신규 섹션 신설 경로)에
    필요하다(`test_kompound_snapshot_apply.py`와 동일한 레시피).
    """
    project_root = tmp_path / "project"
    project_root.mkdir()
    scope_root = tmp_path / "scope_root"
    scope_root.mkdir()

    cfg = dict(fake_kompound_env["config"])
    cfg["scan_root"] = str(scope_root)
    prefix_map = dict(cfg["prefix_map"])
    prefix_map["delta-service"] = "delta"
    cfg["prefix_map"] = prefix_map
    cfg_path = _write_config_file(tmp_path / "kompound-snapshot.config.json", cfg)

    return {
        "project_root": project_root,
        "scope_root": scope_root,
        "kompound": fake_kompound_env["kompound"],
        "config_path": cfg_path,
        "prefix_map": prefix_map,
    }


def _base_env(gate_env: Dict[str, Any], *, configured: bool, home_config_dir: Path) -> Dict[str, str]:
    """서브프로세스 환경을 구성한다. 실제 홈(`~/.claude`)이 아니라 격리된
    `home_config_dir`를 `CLAUDE_CONFIG_DIR`로 지정해 kompound 자동 탐색이
    개발자의 실제 홈 설정을 건드리지 않게 한다."""
    env = dict(os.environ)
    for key in ("HARNESS_KOMPOUND_REPO", "HARNESS_KOMPOUND_SCAN_ROOT", "HARNESS_KOMPOUND_CONFIG"):
        env.pop(key, None)
    env["CLAUDE_PROJECT_DIR"] = str(gate_env["project_root"])
    env["CLAUDE_CONFIG_DIR"] = str(home_config_dir)
    env["HARNESS_DEBUG"] = "1"  # gate_pass도 stderr에 나오게(관측 목적, "조용한 통과 없음" 검증용)
    if configured:
        env["HARNESS_KOMPOUND_CONFIG"] = str(gate_env["config_path"])
    return env


def _run_gate(command: str, env: Dict[str, str], *, tool_name: str = "Bash") -> subprocess.CompletedProcess:
    payload = json.dumps({"tool_name": tool_name, "tool_input": {"command": command}})
    return subprocess.run(
        ["bash", str(_GATE_SCRIPT)],
        input=payload,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _removal_command(path: Path) -> str:
    return f"git worktree remove {path}"


@pytest.fixture()
def configured_env(gate_env: Dict[str, Any], tmp_path: Path) -> Dict[str, str]:
    home_dir = tmp_path / "isolated_home" / ".claude"
    home_dir.mkdir(parents=True)
    return _base_env(gate_env, configured=True, home_config_dir=home_dir)


# ── 스크립트 존재/문법 ───────────────────────────────────────────────────────


def test_gate_script_exists_and_is_executable() -> None:
    assert _GATE_SCRIPT.is_file()
    mode = _GATE_SCRIPT.stat().st_mode
    assert mode & stat.S_IXUSR, "kompound-snapshot-gate.sh는 실행 권한이 있어야 한다"


def test_gate_script_has_valid_bash_syntax() -> None:
    proc = subprocess.run(["bash", "-n", str(_GATE_SCRIPT)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


# ── 분기5: tool_name != Bash / 무관 명령 무개입 ─────────────────────────────


def test_gate_exits_immediately_for_non_bash_tool(configured_env: Dict[str, str]) -> None:
    proc = _run_gate("git worktree remove /tmp/whatever", configured_env, tool_name="Write")
    assert proc.returncode == 0
    assert proc.stderr == ""


def test_gate_no_intervention_for_irrelevant_bash_command(configured_env: Dict[str, str]) -> None:
    """분기5 — 무관한 명령은 개입하지 않는다(빠른 통과, 출력 없음)."""
    proc = _run_gate("echo hello world", configured_env)
    assert proc.returncode == 0
    assert proc.stdout == ""
    assert proc.stderr == ""


def test_gate_no_intervention_for_worktree_list(configured_env: Dict[str, str]) -> None:
    proc = _run_gate("git worktree list", configured_env)
    assert proc.returncode == 0
    assert proc.stderr == ""


def test_gate_no_python_subprocess_spawned_for_irrelevant_command(
    configured_env: Dict[str, str], tmp_path: Path
) -> None:
    """성능 요구(§5.2.2) — 무관한 명령에서는 python3조차 기동되지 않는다.

    PATH 맨 앞에 "실행되면 센티널 파일을 남기는" 가짜 python3를 꽂아 두고,
    무관한 명령을 게이트에 흘려보낸 뒤 센티널이 생기지 않았는지로 검증한다.
    """
    fake_bin = tmp_path / "fake_bin"
    fake_bin.mkdir()
    sentinel = tmp_path / "python3_was_invoked"
    fake_python3 = fake_bin / "python3"
    fake_python3.write_text(
        f"#!/bin/bash\ntouch {sentinel}\nexit 0\n",
        encoding="utf-8",
    )
    fake_python3.chmod(0o755)

    env = dict(configured_env)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"

    proc = _run_gate("echo hello world", env)
    assert proc.returncode == 0
    assert not sentinel.exists(), "무관한 명령인데 python3가 기동됐다(성능 위반)"


# ── 분기1: kompound 미설정 → disabled(20) → 통과 ───────────────────────────


def test_gate_passes_when_kompound_unconfigured(tmp_path: Path) -> None:
    """이 테스트는 의도적으로 `gate_env`/`fake_kompound_env`를 쓰지 않는다 —
    두 fixture 모두 같은 `tmp_path` 밑에 `fake_kompound/`를 만들기 때문에,
    `project_root`의 부모를 그 `tmp_path`로 잡으면 F16 자동 탐색(④)이 그
    kompound을 "발견"해버려 정작 검증하려는 "미설정" 상태를 재현하지 못한다
    (discovery는 `project_root.resolve().parent`의 형제 디렉토리를 스캔한다).
    그래서 여기서는 다른 fixture와 공유하지 않는 격리된 하위 트리를 쓴다.
    """
    isolated = tmp_path / "isolated"
    project_root = isolated / "project"
    project_root.mkdir(parents=True)
    home_dir = isolated / "home" / ".claude"
    home_dir.mkdir(parents=True)
    wt = isolated / "scope" / "acme-widget" / "worktrees" / "wt-disabled"
    wt.mkdir(parents=True)

    env = dict(os.environ)
    for key in ("HARNESS_KOMPOUND_REPO", "HARNESS_KOMPOUND_SCAN_ROOT", "HARNESS_KOMPOUND_CONFIG"):
        env.pop(key, None)
    env["CLAUDE_PROJECT_DIR"] = str(project_root)
    env["CLAUDE_CONFIG_DIR"] = str(home_dir)
    env["HARNESS_DEBUG"] = "1"

    proc = _run_gate(_removal_command(wt), env)

    assert proc.returncode == 0
    assert "✔" in proc.stderr, "통과 경로가 gate_pass를 거치지 않았다(조용한 통과)"
    assert "비활성화" in proc.stderr


# ── 분기2: 0건 통과 ──────────────────────────────────────────────────────────


def test_gate_passes_when_no_pending_documents(configured_env: Dict[str, str], gate_env: Dict[str, Any]) -> None:
    wt = gate_env["scope_root"] / "acme-widget" / "worktrees" / "wt-empty"
    wt.mkdir(parents=True)

    proc = _run_gate(_removal_command(wt), configured_env)

    assert proc.returncode == 0
    assert "✔" in proc.stderr
    assert "박제된 문서" not in proc.stderr  # snapshotted 전용 경고가 섞이면 안 된다


# ── 분기3-a: 자동박제 완전 성공(snapshotted) → 경고 + 통과 ──────────────────


def test_gate_warns_and_passes_on_full_snapshot_success(
    configured_env: Dict[str, str], gate_env: Dict[str, Any]
) -> None:
    wt = _seed_worktree_repo(
        gate_env["scope_root"], "acme-widget", "wt-with-doc", "gate-script-snapshot", kinds=("spec", "arch")
    )

    proc = _run_gate(_removal_command(wt), configured_env)

    assert proc.returncode == 0
    assert report.blocks_deletion("snapshotted") is False
    assert "박제된 문서" in proc.stderr
    assert "acme-gate-script-snapshot-spec.md" in proc.stderr
    assert "✔" in proc.stderr
    raw_file = gate_env["kompound"] / "raw" / "acme-gate-script-snapshot-spec.md"
    assert raw_file.is_file()


# ── 분기3-b: raw만 성공, 카탈로그 뒤처짐(verify_failed/catalog_unparsed) ────
# → 차단하지 않고 경고 후 통과 (A-5 핵심)


def test_gate_warns_and_passes_on_verify_failed_f8_gate_failure(
    configured_env: Dict[str, str], gate_env: Dict[str, Any]
) -> None:
    """F8 검증 게이트(flat_structure) 실패 — raw는 이미 커밋됐으므로 차단하지
    않는다(exit 50, A-5 핵심)."""
    _inject_bad_raw_subdir(gate_env["kompound"])
    wt = _seed_worktree_repo(
        gate_env["scope_root"], "acme-widget", "wt-verify-failed", "gate-script-verifyfailed", kinds=("spec",)
    )

    proc = _run_gate(_removal_command(wt), configured_env)

    assert proc.returncode == 0, f"verify_failed(50)이 차단됐다 — A-5 위반. stderr={proc.stderr!r}"
    assert report.blocks_deletion("verify_failed") is False
    assert "✔" in proc.stderr
    assert "raw" in proc.stderr and "카탈로그" in proc.stderr
    raw_file = gate_env["kompound"] / "raw" / "acme-gate-script-verifyfailed-spec.md"
    assert raw_file.is_file(), "verify_failed여도 raw는 이미 커밋되어 있어야 한다"


def test_gate_warns_and_passes_on_catalog_unparsed(configured_env: Dict[str, str], gate_env: Dict[str, Any]) -> None:
    """registry 신규 섹션 신설 앵커("## 결정과 근거")가 없으면 카탈로그
    갱신을 파싱하지 못한다 — raw는 이미 커밋됐으므로 차단하지 않는다(exit 55)."""
    registry_path = gate_env["kompound"] / "wiki" / "sdd-spec-registry.md"
    original_text = registry_path.read_text(encoding="utf-8")
    broken_text = original_text.replace("## 결정과 근거", "## Decisions (renamed)")
    registry_path.write_text(broken_text, encoding="utf-8")
    _git("add", "-A", cwd=gate_env["kompound"])
    _git("commit", "-q", "-m", "test setup: break registry anchor", cwd=gate_env["kompound"])

    wt = _seed_worktree_repo(
        gate_env["scope_root"], "delta-service", "wt-catalog-unparsed", "gate-script-catalogunparsed", kinds=("spec",)
    )

    proc = _run_gate(_removal_command(wt), configured_env)

    assert proc.returncode == 0, f"catalog_unparsed(55)이 차단됐다 — A-5 위반. stderr={proc.stderr!r}"
    assert report.blocks_deletion("catalog_unparsed") is False
    assert "✔" in proc.stderr
    raw_file = gate_env["kompound"] / "raw" / "delta-gate-script-catalogunparsed-spec.md"
    assert raw_file.is_file(), "catalog_unparsed여도 raw는 이미 커밋되어 있어야 한다"


# ── 분기4: 자동박제 실패 차단 ────────────────────────────────────────────────


def test_gate_blocks_precondition_failed_f9_with_dirty_file_list(
    configured_env: Dict[str, str], gate_env: Dict[str, Any]
) -> None:
    (gate_env["kompound"] / "raw" / "untracked-dirty-file.md").write_text("dirty\n", encoding="utf-8")
    wt = _seed_worktree_repo(
        gate_env["scope_root"], "acme-widget", "wt-dirty", "gate-script-dirty", kinds=("spec",)
    )

    proc = _run_gate(_removal_command(wt), configured_env)

    assert proc.returncode == 2
    assert report.blocks_deletion("precondition_failed") is True
    assert "untracked-dirty-file.md" in proc.stderr, "F9 dirty 파일 목록이 차단 메시지에 없다"
    assert "HARNESS_KOMPOUND_REPO" in proc.stderr, "끄는 방법이 차단 메시지에 없다"


def test_gate_blocks_unmapped_blocking_f12_with_unmapped_list(
    configured_env: Dict[str, str], gate_env: Dict[str, Any]
) -> None:
    wt = _seed_worktree_repo(
        gate_env["scope_root"], "totally-unknown-repo", "wt-unmapped", "gate-script-unmapped", kinds=("spec",)
    )

    proc = _run_gate(_removal_command(wt), configured_env)

    assert proc.returncode == 2
    assert report.blocks_deletion("unmapped_blocking") is True
    assert "totally-unknown-repo" in proc.stderr, "F12 미등록 프리픽스 정보가 차단 메시지에 없다"


def test_gate_blocks_write_failed_raw_copy_failure(configured_env: Dict[str, str], gate_env: Dict[str, Any]) -> None:
    """`raw/`를 쓰기 불가로 만들어 (i) raw 복사 자체가 실패하게 한다(exit 60)."""
    raw_dir = gate_env["kompound"] / "raw"
    wt = _seed_worktree_repo(
        gate_env["scope_root"], "acme-widget", "wt-write-failed", "gate-script-writefailed", kinds=("spec",)
    )

    original_mode = raw_dir.stat().st_mode
    raw_dir.chmod(0o555)
    try:
        proc = _run_gate(_removal_command(wt), configured_env)
    finally:
        raw_dir.chmod(original_mode)

    assert proc.returncode == 2
    assert report.blocks_deletion("write_failed") is True
    assert "raw" in proc.stderr


def test_gate_blocks_busy_lock_held(configured_env: Dict[str, str], gate_env: Dict[str, Any]) -> None:
    """kompound 락 파일을 미리 신선한 상태로 만들어 두면 `busy`(exit 70)로 차단된다."""
    lock_path = gate_env["kompound"] / ".git" / "kompound-snapshot.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text("held-by-test\n", encoding="utf-8")
    wt = _seed_worktree_repo(
        gate_env["scope_root"], "acme-widget", "wt-busy", "gate-script-busy", kinds=("spec",)
    )

    try:
        proc = _run_gate(_removal_command(wt), configured_env)
    finally:
        lock_path.unlink(missing_ok=True)

    assert proc.returncode == 2
    assert report.blocks_deletion("busy") is True


def test_gate_blocks_scan_error(configured_env: Dict[str, str], gate_env: Dict[str, Any]) -> None:
    """스캔 대상 안에 읽을 수 없는 디렉토리를 심어 `scan_error`(exit 30)를 유도한다."""
    wt = _seed_worktree_repo(
        gate_env["scope_root"], "acme-widget", "wt-scan-error", "gate-script-scanerror", kinds=("spec",)
    )
    broken_dir = wt / "docs" / "sdd" / "spec" / "unreadable"
    broken_dir.mkdir(parents=True)
    (broken_dir / "placeholder.md").write_text("placeholder\n", encoding="utf-8")
    original_mode = broken_dir.stat().st_mode
    broken_dir.chmod(0o000)

    try:
        proc = _run_gate(_removal_command(wt), configured_env)
    finally:
        broken_dir.chmod(original_mode)

    assert proc.returncode == 2
    assert report.blocks_deletion("scan_error") is True


# ── T1→T2 실패/지연 승계 노출 (A-2) — 톤 분리 + 반복 억제 ──────────────────


def _seed_runtime_status(project_root: Path, status: str) -> None:
    state_file = runtime_state.state_path_for(project_root)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema_version": 1, "status": status, "catalog_lag_count": 2}
    state_file.write_text(json.dumps(payload), encoding="utf-8")


def test_gate_surfaces_failed_inherited_warning_with_failure_tone(
    configured_env: Dict[str, str], gate_env: Dict[str, Any]
) -> None:
    _seed_runtime_status(gate_env["project_root"], runtime_state.FAILED)

    proc = _run_gate("git worktree remove /tmp/no-such-worktree-path-for-inherited-check", configured_env)

    assert "T1 실패 승계" in proc.stderr
    assert "T1 박제가 실패했습니다" in proc.stderr


def test_gate_surfaces_catalog_pending_inherited_warning_with_info_tone(
    configured_env: Dict[str, str], gate_env: Dict[str, Any]
) -> None:
    _seed_runtime_status(gate_env["project_root"], runtime_state.CATALOG_PENDING)

    proc = _run_gate("git worktree remove /tmp/no-such-worktree-path-for-inherited-check", configured_env)

    assert "T1 카탈로그 지연 승계" in proc.stderr
    assert "삭제는 안전합니다" in proc.stderr


def test_gate_failure_and_info_tones_are_distinct_wording(
    configured_env: Dict[str, str], gate_env: Dict[str, Any]
) -> None:
    _seed_runtime_status(gate_env["project_root"], runtime_state.FAILED)
    proc_failed = _run_gate("git worktree remove /tmp/no-such-worktree-path-for-inherited-check", configured_env)

    _seed_runtime_status(gate_env["project_root"], runtime_state.CATALOG_PENDING)
    proc_pending = _run_gate("git worktree remove /tmp/no-such-worktree-path-for-inherited-check", configured_env)

    assert proc_failed.stderr != proc_pending.stderr
    assert "T1 실패 승계" not in proc_pending.stderr
    assert "T1 카탈로그 지연 승계" not in proc_failed.stderr


def test_gate_does_not_repeat_inherited_warning_after_consumption(
    configured_env: Dict[str, str], gate_env: Dict[str, Any]
) -> None:
    """arch §5.2.3 — 승계 노출은 같은 status 값에 대해 1회만 나온다(반복 노출 방지)."""
    _seed_runtime_status(gate_env["project_root"], runtime_state.FAILED)

    proc1 = _run_gate("git worktree remove /tmp/no-such-worktree-path-for-inherited-check", configured_env)
    assert "T1 실패 승계" in proc1.stderr

    proc2 = _run_gate("git worktree remove /tmp/no-such-worktree-path-for-inherited-check", configured_env)
    assert "T1 실패 승계" not in proc2.stderr


# ── hooks.json 등록 (F14) ────────────────────────────────────────────────────

_EXPECTED_EXISTING_BASH_COMMANDS_PREFIX = [
    "${CLAUDE_PLUGIN_ROOT}/hooks/dangerous-command.sh",
    "${CLAUDE_PLUGIN_ROOT}/hooks/secret-detect.sh",
    "${CLAUDE_PLUGIN_ROOT}/hooks/enforcement/branch-gate.sh",
    "${CLAUDE_PLUGIN_ROOT}/hooks/enforcement/worktree-add-gate.sh",
    "${CLAUDE_PLUGIN_ROOT}/hooks/enforcement/e2e-gate.sh",
]


def _load_hooks_json() -> Dict[str, Any]:
    return json.loads(_HOOKS_JSON_PATH.read_text(encoding="utf-8"))


def _bash_commands(hooks_data: Dict[str, Any]) -> list:
    pre_tool_use = hooks_data["hooks"]["PreToolUse"]
    bash_blocks = [b for b in pre_tool_use if b.get("matcher") == "Bash"]
    assert len(bash_blocks) == 1
    return [entry["command"] for entry in bash_blocks[0]["hooks"]]


def test_hooks_json_is_valid_json() -> None:
    data = _load_hooks_json()
    assert isinstance(data, dict)


def test_hooks_json_registers_kompound_snapshot_gate_as_last_bash_entry() -> None:
    data = _load_hooks_json()
    commands = _bash_commands(data)
    assert commands[-1] == "${CLAUDE_PLUGIN_ROOT}/hooks/enforcement/kompound-snapshot-gate.sh"


def test_hooks_json_preserves_existing_five_commands_in_order() -> None:
    data = _load_hooks_json()
    commands = _bash_commands(data)
    prefix = commands[: len(_EXPECTED_EXISTING_BASH_COMMANDS_PREFIX)]
    assert prefix == _EXPECTED_EXISTING_BASH_COMMANDS_PREFIX
