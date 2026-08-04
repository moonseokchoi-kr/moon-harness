"""tests/test_kompound_snapshot_cli.py — T-11 `cli.py` CLI 통합 테스트.

설계 SSOT: `docs/sdd/design/arch/2026-07-29-kompound-snapshot-hook.md` §6.2
(CLI 계약 — 서브커맨드·종료 코드·JSON 스키마), §5.2.3(`gate` 5개 분기·F9
선행 확인·T1→T2 승계 노출). task: `2026-07-29-T-11-cli-integration.md`.

전부 `tmp_path` 기반이다 — 실제 kompound(`marvelous_kompound`)나 실제 홈
디렉토리에는 절대 쓰지 않는다(`fake_kompound_env`, tests/conftest.py, T-2).

이 파일이 반드시 커버하는 것(task 문서 "테스트" 절 그대로):

- 3개 서브커맨드(`check`/`apply`/`gate`) 각각의 정상 경로
- `check`가 부작용을 남기지 않음(호출 전후 파일·git 상태 동일)
- `gate`가 exit 10을 반환하지 않음
- `gate`의 5개 분기(미설정 통과/0건 통과/자동박제 성공 통과/자동박제 실패
  차단/무관 명령 무개입) — 각각 `report.blocks_deletion()`과 일치하는 종료
  코드인지
- F8 게이트 실패(exit 50)·`catalog_unparsed`(exit 55)가 `gate`에서 차단하지
  않고 통과(A-5 핵심) — `write_failed`(60)·`precondition_failed`(40)·
  `unmapped_blocking`(45)·`busy`(70)·`scan_error`(30)는 차단
- kompound 미설정 → `disabled`(20) 조용히 통과 + 안내 1회
- 종료 코드에 1·2가 절대 나오지 않음
- stdout이 유효한 JSON, stderr에 사람용 텍스트
- 예외 상황에서 크래시하지 않고 종료 코드로 귀결
- F9 우선순위 체인 — `precondition_failed`가 걸리면 `apply.apply()`가
  호출조차 되지 않음(mock 검증)
- 승계 노출 3종 상태(FAILED/GIVEN_UP/CATALOG_PENDING)
- `resolve_config()` 오버라이드로 전체 파이프라인을 실제 실행하는 통합 테스트
  (scan→naming→dedup→apply→registry/wiki_log→verify→git_state)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from unittest.mock import patch

import pytest

from hooks.lib.kompound_snapshot import cli, report, runtime_state
from hooks.lib.kompound_snapshot import git_state as git_state_mod

_REPO_ROOT = Path(__file__).resolve().parents[1]


# ── 테스트 인프라 헬퍼 ───────────────────────────────────────────────────────


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            "git",
            "-c",
            "user.email=fixture@example.invalid",
            "-c",
            "user.name=test-cli",
            "-c",
            "commit.gpgsign=false",
            *args,
        ],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def _git_status_porcelain(repo: Path) -> str:
    result = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo, check=True, capture_output=True, text=True
    )
    return result.stdout


def _seed_repo(root: Path, repo_name: str, feature: str, kinds: Iterable[str] = ("spec",)) -> Path:
    """`root/<repo_name>/docs/sdd/<kind>/2026-08-01-<feature>.md`를 만든다.

    `repo_name`은 `prefix_map`의 키와 일치해야 F4 네이밍이 성공한다(scan.py
    §5.4.2 규칙 5 — 완화 재조회 없이도 1차 조회로 해석되도록). `repo_name`
    디렉토리 자신에 빈 `.git/` 마커를 심어 `derive_repo_dir`(arch §5.4.2
    규칙 2)이 이 디렉토리를 repo 루트로 채택하게 한다 — 마커가 없으면 규칙
    2/3이 실패해 `scope_root` 자체가 repo_dir이 되어(그 basename은
    `prefix_map`에 없다) 모든 문서가 엉뚱하게 `unmapped`로 떨어진다.

    파일명에 **kind 접미사를 붙이지 않는다**(`2026-08-01-<feature>.md`) —
    `naming.py`는 `-spec`/`-dev`/`-result`만 벗겨내고 `-arch`/`-ui`/`-api`/
    `-context`는 벗기지 않으므로, 파일명에 `-arch`를 넣으면
    `<project>-<feature>-arch-arch.md`처럼 kind가 중복된다(실측 확인).
    kind는 `raw_name` 조립 시 `naming.py`가 한 번만 붙인다.
    """
    repo_root = root / repo_name
    (repo_root / ".git").mkdir(parents=True, exist_ok=True)
    for kind in kinds:
        d = repo_root / "docs" / "sdd" / kind
        d.mkdir(parents=True, exist_ok=True)
        (d / f"2026-08-01-{feature}.md").write_text(f"# {feature} {kind} fixture\n", encoding="utf-8")
    return repo_root


def _seed_worktree_repo(
    scope_root: Path, repo_name: str, wt_name: str, feature: str, kinds: Iterable[str] = ("spec",)
) -> Path:
    """`scope_root/<repo_name>/worktrees/<wt_name>/docs/sdd/<kind>/...`를 만든다
    ("워크트리 전용 문서" 케이스, arch §5.4.2 규칙 1). `derive_repo_dir`이
    `worktrees` 세그먼트의 **부모**(= `scope_root/<repo_name>`)를 repo
    루트로 채택하므로, `repo_name`이 `worktrees`보다 **위**에 있어야 한다
    (`_seed_repo`처럼 `worktrees` 세그먼트 아래에 repo_name을 두면 규칙 1이
    먼저 걸려 `scope_root` 자체가 repo_dir이 되어버린다).

    파일명 kind 접미사 생략 이유는 `_seed_repo` docstring 참조. 반환값은
    워크트리 디렉토리 자체(`gate`의 `--command`가 삭제 대상으로 가리킬 경로)다.
    """
    wt_root = scope_root / repo_name / "worktrees" / wt_name
    for kind in kinds:
        d = wt_root / "docs" / "sdd" / kind
        d.mkdir(parents=True, exist_ok=True)
        (d / f"2026-08-01-{feature}.md").write_text(f"# {feature} {kind} fixture\n", encoding="utf-8")
    return wt_root


def _write_config_file(path: Path, cfg: Dict[str, Any]) -> Path:
    path.write_text(json.dumps(cfg), encoding="utf-8")
    return path


@pytest.fixture()
def cli_env(fake_kompound_env: Dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Dict[str, Any]:
    """CLI 통합 테스트 공통 환경 — `fake_kompound_env`의 kompound(git 저장소)를
    재사용하되, 스캔 대상은 이 fixture가 별도로 만드는 격리된 `scope_root`를
    쓴다(fake_kompound_env가 이미 심어둔 `acme-widget` 콘텐츠와 내용이 달라
    "new"/"updated" 카운트가 뒤섞이는 것을 피하기 위함 — 이 fixture는 항상
    새 feature 이름을 쓴다).
    """
    project_root = tmp_path / "project"
    project_root.mkdir()
    scope_root = tmp_path / "scope_root"
    scope_root.mkdir()

    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project_root))
    monkeypatch.delenv("HARNESS_KOMPOUND_REPO", raising=False)
    monkeypatch.delenv("HARNESS_KOMPOUND_SCAN_ROOT", raising=False)
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)

    cfg = dict(fake_kompound_env["config"])
    cfg["scan_root"] = str(scope_root)
    cfg_path = _write_config_file(tmp_path / "kompound-snapshot.config.json", cfg)
    monkeypatch.setenv("HARNESS_KOMPOUND_CONFIG", str(cfg_path))

    return {
        "project_root": project_root,
        "scope_root": scope_root,
        "kompound": fake_kompound_env["kompound"],
        "workspace": fake_kompound_env["workspace"],
        "prefix_map": cfg["prefix_map"],
        "config_path": cfg_path,
    }


def _capture(capsys: pytest.CaptureFixture) -> Any:
    return capsys.readouterr()


# ── 종료 코드에 1·2가 절대 나오지 않음 (모든 verdict 대상) ──────────────────


def test_no_verdict_ever_maps_to_reserved_exit_codes_1_or_2() -> None:
    for verdict in report.VERDICT_TABLE:
        code = report.exit_code_for_verdict(verdict)
        assert code not in (1, 2), f"{verdict} -> exit {code} (1/2는 예약)"


# ── build_parser / main 기본 계약 ───────────────────────────────────────────


def test_build_parser_exposes_three_subcommands() -> None:
    parser = cli.build_parser()
    args = parser.parse_args(["check", "--json"])
    assert args.subcommand == "check"
    assert args.json is True

    args = parser.parse_args(["apply"])
    assert args.subcommand == "apply"
    assert args.json is False

    args = parser.parse_args(["gate", "--command", "git worktree remove x"])
    assert args.subcommand == "gate"
    assert args.command == "git worktree remove x"


def test_main_returns_exit_code_not_none(cli_env: Dict[str, Any], capsys: pytest.CaptureFixture) -> None:
    rc = cli.main(["check", "--json"])
    assert isinstance(rc, int)
    _capture(capsys)


# ── check: 정상 경로 + 부작용 없음 ──────────────────────────────────────────


def test_check_ok_no_pending_when_kompound_repo_empty(
    cli_env: Dict[str, Any], capsys: pytest.CaptureFixture
) -> None:
    rc = cli.main(["check", "--scope-root", str(cli_env["scope_root"]), "--json"])
    out = _capture(capsys)
    payload = json.loads(out.out)
    assert rc == report.EXIT_OK
    assert payload["verdict"] == "ok_no_pending"
    assert payload["pending"] == []


def test_check_reports_pending_for_new_document(
    cli_env: Dict[str, Any], capsys: pytest.CaptureFixture
) -> None:
    _seed_repo(cli_env["scope_root"], "acme-widget", "cli-check-new", kinds=("spec",))

    rc = cli.main(["check", "--scope-root", str(cli_env["scope_root"]), "--json"])
    out = _capture(capsys)
    payload = json.loads(out.out)

    assert rc == report.EXIT_PENDING
    assert payload["verdict"] == "pending"
    assert payload["pending"] == ["acme-cli-check-new-spec.md"]
    assert payload["unmapped"] == []


def test_check_reports_unmapped_for_unregistered_prefix(
    cli_env: Dict[str, Any], capsys: pytest.CaptureFixture
) -> None:
    repo_root = _seed_repo(cli_env["scope_root"], "totally-unknown-repo", "cli-check-unmapped", kinds=("spec",))

    rc = cli.main(["check", "--scope-root", str(cli_env["scope_root"]), "--json"])
    out = _capture(capsys)
    payload = json.loads(out.out)

    # check는 unmapped로 차단하지 않는다(그건 gate 전용) — 0건 통과.
    # naming.py의 unmapped 신호는 repo_dir 전체 경로다(basename만이 아니다).
    assert rc == report.EXIT_OK
    assert payload["verdict"] == "ok_no_pending"
    assert payload["unmapped"] == [str(repo_root)]


def test_check_has_no_side_effects(cli_env: Dict[str, Any], capsys: pytest.CaptureFixture) -> None:
    """완료조건: `check`가 부작용을 남기지 않는다 — 호출 전후 kompound의
    git 상태·raw/wiki 파일이 완전히 동일해야 한다."""
    _seed_repo(cli_env["scope_root"], "acme-widget", "cli-check-side-effect", kinds=("spec", "arch"))
    kompound = cli_env["kompound"]

    before_status = _git_status_porcelain(kompound)
    before_head = _git(*"rev-parse HEAD".split(), cwd=kompound).stdout
    before_raw = sorted(p.name for p in (kompound / "raw").iterdir())
    before_registry = (kompound / "wiki" / "sdd-spec-registry.md").read_bytes()
    before_index = (kompound / "wiki" / "index.md").read_bytes()
    before_log = (kompound / "wiki" / "log.md").read_bytes()

    rc = cli.main(["check", "--scope-root", str(cli_env["scope_root"]), "--json"])
    _capture(capsys)
    assert rc == report.EXIT_PENDING  # 확인: 실제로 뭔가 볼 게 있는 상태에서 검증

    after_status = _git_status_porcelain(kompound)
    after_head = _git(*"rev-parse HEAD".split(), cwd=kompound).stdout
    after_raw = sorted(p.name for p in (kompound / "raw").iterdir())
    after_registry = (kompound / "wiki" / "sdd-spec-registry.md").read_bytes()
    after_index = (kompound / "wiki" / "index.md").read_bytes()
    after_log = (kompound / "wiki" / "log.md").read_bytes()

    assert after_status == before_status
    assert after_head == before_head
    assert after_raw == before_raw
    assert after_registry == before_registry
    assert after_index == before_index
    assert after_log == before_log


def test_check_default_scope_is_project_root_when_no_flags(
    cli_env: Dict[str, Any], capsys: pytest.CaptureFixture
) -> None:
    """플래그 생략 시 기본 스코프 = `project_root` 1개(설계 결정 1)."""
    rc = cli.main(["check", "--json"])
    out = _capture(capsys)
    payload = json.loads(out.out)
    assert rc == report.EXIT_OK
    assert payload["scope_roots"] == [str(cli_env["project_root"])]


def test_check_scope_workspace_uses_configured_scan_root(
    cli_env: Dict[str, Any], capsys: pytest.CaptureFixture
) -> None:
    _seed_repo(cli_env["scope_root"], "acme-widget", "cli-check-workspace", kinds=("spec",))
    rc = cli.main(["check", "--scope=workspace", "--json"])
    out = _capture(capsys)
    payload = json.loads(out.out)
    assert rc == report.EXIT_PENDING
    assert payload["scope_roots"] == [str(cli_env["scope_root"])]


def test_check_scope_workspace_without_scan_root_is_scan_error(
    fake_kompound_env: Dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """설계 결정 2 — `--scope=workspace`인데 `scan_root` 미해석이면 사용법
    오류로 보고 `scan_error`로 귀결한다(조용한 실패 금지, F11)."""
    project_root = tmp_path / "project"
    project_root.mkdir()
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project_root))
    monkeypatch.delenv("HARNESS_KOMPOUND_SCAN_ROOT", raising=False)

    cfg = dict(fake_kompound_env["config"])
    cfg["scan_root"] = None
    cfg_path = _write_config_file(tmp_path / "cfg.json", cfg)
    monkeypatch.setenv("HARNESS_KOMPOUND_CONFIG", str(cfg_path))

    rc = cli.main(["check", "--scope=workspace", "--json"])
    out = _capture(capsys)
    payload = json.loads(out.out)
    assert rc == report.EXIT_SCAN_ERROR
    assert payload["verdict"] == "scan_error"
    assert payload["errors"]


# ── disabled (F16 미설정) — check/apply는 매번 그대로, gate는 안내 1회 ─────


def test_check_disabled_when_kompound_unconfigured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project_root))
    for key in ("HARNESS_KOMPOUND_REPO", "HARNESS_KOMPOUND_SCAN_ROOT", "HARNESS_KOMPOUND_CONFIG"):
        monkeypatch.delenv(key, raising=False)

    rc = cli.main(["check", "--json"])
    out = _capture(capsys)
    payload = json.loads(out.out)
    assert rc == report.EXIT_DISABLED
    assert payload["verdict"] == "disabled"


def test_gate_disabled_shows_notice_once_then_suppresses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """완료조건: kompound 미설정 → `disabled`(20) 조용히 통과 + 안내 1회."""
    project_root = tmp_path / "project"
    project_root.mkdir()
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project_root))
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    for key in ("HARNESS_KOMPOUND_REPO", "HARNESS_KOMPOUND_SCAN_ROOT", "HARNESS_KOMPOUND_CONFIG"):
        monkeypatch.delenv(key, raising=False)

    wt = tmp_path / "workspace" / "worktrees" / "some-wt"
    wt.mkdir(parents=True)
    command = f"rm -rf {wt}"

    rc1 = cli.main(["gate", "--command", command, "--json"])
    out1 = _capture(capsys)
    payload1 = json.loads(out1.out)
    assert rc1 == report.EXIT_DISABLED
    assert payload1["verdict"] == "disabled"
    assert payload1["human"], "1회차는 안내 텍스트가 있어야 한다"
    assert out1.err, "1회차는 stderr에 사람용 텍스트가 있어야 한다"

    rc2 = cli.main(["gate", "--command", command, "--json"])
    out2 = _capture(capsys)
    payload2 = json.loads(out2.out)
    assert rc2 == report.EXIT_DISABLED
    assert payload2["verdict"] == "disabled"
    assert payload2["human"] == "", "2회차는 안내가 억제돼야 한다(안내 1회)"


# ── apply: 정상 경로(2단 커밋) + JSON 스키마 ─────────────────────────────────


def test_apply_snapshots_new_document_and_commits(
    cli_env: Dict[str, Any], capsys: pytest.CaptureFixture
) -> None:
    _seed_repo(cli_env["scope_root"], "acme-widget", "cli-apply-new", kinds=("spec",))
    kompound = cli_env["kompound"]
    before_commits = int(_git("rev-list", "--count", "HEAD", cwd=kompound).stdout.strip())

    rc = cli.main(["apply", "--scope-root", str(cli_env["scope_root"]), "--json"])
    out = _capture(capsys)
    payload = json.loads(out.out)

    assert rc == report.EXIT_OK
    assert payload["verdict"] == "snapshotted"
    assert payload["raw_stage"]["new"] == ["acme-cli-apply-new-spec.md"]
    assert payload["raw_stage"]["committed"] is True
    assert (kompound / "raw" / "acme-cli-apply-new-spec.md").is_file()

    after_commits = int(_git("rev-list", "--count", "HEAD", cwd=kompound).stdout.strip())
    assert after_commits > before_commits

    # runtime_state가 project_root 아래 기록됐다(apply()의 project_root 배선 확인).
    state_file = runtime_state.state_path_for(cli_env["project_root"])
    assert state_file.is_file()


def test_apply_idempotent_second_run_is_ok_no_pending(
    cli_env: Dict[str, Any], capsys: pytest.CaptureFixture
) -> None:
    _seed_repo(cli_env["scope_root"], "acme-widget", "cli-apply-idempotent", kinds=("spec",))

    rc1 = cli.main(["apply", "--scope-root", str(cli_env["scope_root"]), "--json"])
    _capture(capsys)
    assert rc1 == report.EXIT_OK

    rc2 = cli.main(["apply", "--scope-root", str(cli_env["scope_root"]), "--json"])
    out2 = _capture(capsys)
    payload2 = json.loads(out2.out)
    assert rc2 == report.EXIT_OK
    assert payload2["verdict"] == "ok_no_pending"
    assert payload2["raw_stage"]["new"] == []
    assert payload2["raw_stage"]["updated"] == []


def test_apply_json_schema_matches_arch_top_level_keys(
    cli_env: Dict[str, Any], capsys: pytest.CaptureFixture
) -> None:
    _seed_repo(cli_env["scope_root"], "acme-widget", "cli-apply-schema", kinds=("spec",))
    cli.main(["apply", "--scope-root", str(cli_env["scope_root"]), "--json"])
    out = _capture(capsys)
    payload = json.loads(out.out)
    expected_keys = {
        "verdict", "exit_code", "config_source", "scope_roots", "anchors",
        "raw_stage", "catalog_stage", "unmapped", "pending", "dirty", "errors",
        "runtime_status", "catalog_lag_count", "inherited_warning", "human",
    }
    assert set(payload.keys()) == expected_keys
    assert payload["runtime_status"] in runtime_state.STATUSES


def test_apply_human_mode_writes_report_to_stdout(
    cli_env: Dict[str, Any], capsys: pytest.CaptureFixture
) -> None:
    _seed_repo(cli_env["scope_root"], "acme-widget", "cli-apply-human", kinds=("spec",))
    rc = cli.main(["apply", "--scope-root", str(cli_env["scope_root"])])
    out = _capture(capsys)
    assert rc == report.EXIT_OK
    assert out.out.strip() != ""
    with pytest.raises(json.JSONDecodeError):
        json.loads(out.out)  # 사람 모드는 JSON이 아니다


def test_apply_precondition_failed_blocks_and_is_dirty(
    cli_env: Dict[str, Any], capsys: pytest.CaptureFixture
) -> None:
    _seed_repo(cli_env["scope_root"], "acme-widget", "cli-apply-dirty", kinds=("spec",))
    (cli_env["kompound"] / "raw" / "untracked-dirty-file.md").write_text("dirty\n", encoding="utf-8")

    rc = cli.main(["apply", "--scope-root", str(cli_env["scope_root"]), "--json"])
    out = _capture(capsys)
    payload = json.loads(out.out)

    assert rc == report.EXIT_PRECONDITION_FAILED
    assert payload["verdict"] == "precondition_failed"
    assert report.blocks_deletion("precondition_failed") is True


# ── gate: no_target / 무관 명령 무개입 ──────────────────────────────────────


def test_gate_no_target_for_irrelevant_command(
    cli_env: Dict[str, Any], capsys: pytest.CaptureFixture
) -> None:
    rc = cli.main(["gate", "--command", "echo hello world", "--json"])
    out = _capture(capsys)
    payload = json.loads(out.out)
    assert rc == report.EXIT_OK
    assert payload["verdict"] == "no_target"
    assert report.blocks_deletion("no_target") is False


def test_gate_no_target_for_worktree_list(cli_env: Dict[str, Any], capsys: pytest.CaptureFixture) -> None:
    rc = cli.main(["gate", "--command", "git worktree list", "--json"])
    out = _capture(capsys)
    payload = json.loads(out.out)
    assert rc == report.EXIT_OK
    assert payload["verdict"] == "no_target"


# ── gate: 0건 통과 / 자동박제 성공 통과 (실제 파이프라인) ───────────────────


def _worktree_removal_command(wt_path: Path) -> str:
    return f"rm -rf {wt_path}"


def test_gate_ok_no_pending_when_nothing_to_snapshot(
    cli_env: Dict[str, Any], capsys: pytest.CaptureFixture
) -> None:
    wt = cli_env["scope_root"] / "worktrees" / "empty-wt"
    wt.mkdir(parents=True)

    rc = cli.main(["gate", "--command", _worktree_removal_command(wt), "--json"])
    out = _capture(capsys)
    payload = json.loads(out.out)

    assert rc == report.EXIT_OK
    assert payload["verdict"] == "ok_no_pending"
    assert report.blocks_deletion("ok_no_pending") is False


def test_gate_snapshotted_success_for_real_pipeline(
    cli_env: Dict[str, Any], capsys: pytest.CaptureFixture
) -> None:
    """완료조건: `resolve_config()` 오버라이드로 F3~F14 전 파이프라인을
    `gate`로 실제 실행(scan→naming→dedup→apply→registry/wiki_log→verify→
    git_state)."""
    wt = _seed_worktree_repo(
        cli_env["scope_root"], "acme-widget", "wt-with-doc", "cli-gate-snapshot", kinds=("spec", "arch")
    )

    rc = cli.main(["gate", "--command", _worktree_removal_command(wt), "--json"])
    out = _capture(capsys)
    payload = json.loads(out.out)

    assert rc == report.EXIT_OK
    assert payload["verdict"] == "snapshotted"
    assert report.blocks_deletion("snapshotted") is False
    assert set(payload["raw_stage"]["new"]) == {
        "acme-cli-gate-snapshot-spec.md",
        "acme-cli-gate-snapshot-arch.md",
    }
    assert (cli_env["kompound"] / "raw" / "acme-cli-gate-snapshot-spec.md").is_file()


def test_gate_never_returns_exit_10(cli_env: Dict[str, Any], capsys: pytest.CaptureFixture) -> None:
    wt = _seed_worktree_repo(
        cli_env["scope_root"], "acme-widget", "wt-pending-check", "cli-gate-no-pending-exit", kinds=("spec",)
    )

    rc = cli.main(["gate", "--command", _worktree_removal_command(wt), "--json"])
    _capture(capsys)
    assert rc != report.EXIT_PENDING
    assert rc != 10


# ── gate: unmapped_blocking (차단) ──────────────────────────────────────────


def test_gate_unmapped_blocking_when_scope_has_unregistered_prefix(
    cli_env: Dict[str, Any], capsys: pytest.CaptureFixture
) -> None:
    wt = _seed_worktree_repo(
        cli_env["scope_root"], "totally-unknown-repo", "wt-unmapped", "cli-gate-unmapped", kinds=("spec",)
    )

    rc = cli.main(["gate", "--command", _worktree_removal_command(wt), "--json"])
    out = _capture(capsys)
    payload = json.loads(out.out)

    assert rc == report.EXIT_UNMAPPED_BLOCKING
    assert payload["verdict"] == "unmapped_blocking"
    assert report.blocks_deletion("unmapped_blocking") is True


# ── gate: F9 선행 확인 순서 — precondition_failed면 apply()가 호출되지 않음 ─


def test_gate_precondition_failed_blocks_before_calling_apply(
    cli_env: Dict[str, Any], capsys: pytest.CaptureFixture
) -> None:
    wt = _seed_worktree_repo(cli_env["scope_root"], "acme-widget", "wt-dirty", "cli-gate-dirty", kinds=("spec",))
    (cli_env["kompound"] / "raw" / "untracked-dirty-file-gate.md").write_text("dirty\n", encoding="utf-8")

    with patch.object(cli.apply_mod, "apply") as mock_apply:
        rc = cli.main(["gate", "--command", _worktree_removal_command(wt), "--json"])
        out = _capture(capsys)
        payload = json.loads(out.out)

        assert rc == report.EXIT_PRECONDITION_FAILED
        assert payload["verdict"] == "precondition_failed"
        assert report.blocks_deletion("precondition_failed") is True
        mock_apply.assert_not_called()


# ── gate: apply() 결과 매핑 — 통과(경고) vs 차단 (mock, A-5 핵심) ───────────


def _base_apply_result(**overrides: Any) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "busy": False,
        "precondition_failed": False,
        "precondition": None,
        "unmapped": [],
        "dirty": [],
        "raw_name_conflicts": [],
        "raw_stage": {
            "ok": True, "new": ["acme-x-spec.md"], "updated": [], "unchanged": 0,
            "committed": True, "commit": "deadbeef", "error": "",
        },
        "catalog_stage": {
            "ok": True, "attempted": True, "registry": True, "index": True, "log": True,
            "committed": True, "commit": "cafef00d", "failed_gates": [], "unparsed": None, "error": "",
        },
    }
    result.update(overrides)
    return result


@pytest.mark.parametrize(
    "verdict,exit_code,overrides",
    [
        (
            "verify_failed",
            report.EXIT_VERIFY_FAILED,
            {
                "catalog_stage": {
                    "ok": False, "attempted": True, "registry": False, "index": False, "log": False,
                    "committed": False, "commit": None,
                    "failed_gates": ["link_integrity"], "unparsed": None, "error": "gate failed",
                }
            },
        ),
        (
            "catalog_unparsed",
            report.EXIT_CATALOG_UNPARSED,
            {
                "catalog_stage": {
                    "ok": False, "attempted": True, "registry": False, "index": False, "log": False,
                    "committed": False, "commit": None,
                    "failed_gates": [], "unparsed": "unknown table shape", "error": "unknown table shape",
                }
            },
        ),
        (
            "write_failed",
            report.EXIT_WRITE_FAILED,
            {
                "raw_stage": {
                    "ok": False, "new": [], "updated": [], "unchanged": 0,
                    "committed": False, "commit": None, "error": "disk full",
                }
            },
        ),
        ("busy", report.EXIT_BUSY, {"busy": True}),
    ],
)
def test_gate_apply_result_mapping_matches_blocks_deletion(
    cli_env: Dict[str, Any],
    capsys: pytest.CaptureFixture,
    verdict: str,
    exit_code: int,
    overrides: Dict[str, Any],
) -> None:
    """F8 실패(50)·catalog_unparsed(55)는 통과(경고), write_failed(60)·
    busy(70)는 차단 — A-5 핵심을 `report.blocks_deletion()`과 대조한다."""
    wt = _seed_worktree_repo(
        cli_env["scope_root"], "acme-widget", f"wt-{verdict}", f"cli-gate-{verdict}", kinds=("spec",)
    )

    fake_result = _base_apply_result(**overrides)
    with patch.object(cli.apply_mod, "apply", return_value=fake_result) as mock_apply:
        rc = cli.main(["gate", "--command", _worktree_removal_command(wt), "--json"])
        out = _capture(capsys)
        payload = json.loads(out.out)
        mock_apply.assert_called_once()

    assert rc == exit_code
    assert payload["verdict"] == verdict
    expected_blocks = report.blocks_deletion(verdict)
    assert report.blocks_deletion(payload["verdict"]) == expected_blocks
    if expected_blocks:
        assert rc in (
            report.EXIT_SCAN_ERROR, report.EXIT_PRECONDITION_FAILED, report.EXIT_UNMAPPED_BLOCKING,
            report.EXIT_WRITE_FAILED, report.EXIT_BUSY,
        )
    else:
        assert rc in (report.EXIT_OK, report.EXIT_VERIFY_FAILED, report.EXIT_CATALOG_UNPARSED)


def test_gate_scan_error_blocks(cli_env: Dict[str, Any], capsys: pytest.CaptureFixture) -> None:
    wt = cli_env["scope_root"] / "worktrees" / "wt-scan-error"
    wt.mkdir(parents=True)

    def _fake_scan(scope_roots: Any, max_anchor_depth: int) -> Dict[str, Any]:
        return {"records": [], "anchors": 0, "errors": [{"path": str(wt), "error": "boom"}]}

    with patch.object(cli.scan, "scan", side_effect=_fake_scan):
        rc = cli.main(["gate", "--command", _worktree_removal_command(wt), "--json"])
        out = _capture(capsys)
        payload = json.loads(out.out)

    assert rc == report.EXIT_SCAN_ERROR
    assert payload["verdict"] == "scan_error"
    assert report.blocks_deletion("scan_error") is True


# ── gate: 승계 노출 3종 상태 (FAILED/GIVEN_UP/CATALOG_PENDING) ──────────────


def _seed_runtime_status(project_root: Path, status: str, **extra: Any) -> None:
    state_file = runtime_state.state_path_for(project_root)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema_version": 1, "status": status, "catalog_lag_count": 0}
    payload.update(extra)
    state_file.write_text(json.dumps(payload), encoding="utf-8")


@pytest.mark.parametrize(
    "status,expected_kind",
    [
        (runtime_state.FAILED, "failure"),
        (runtime_state.GIVEN_UP, "failure"),
        (runtime_state.CATALOG_PENDING, "info"),
    ],
)
def test_gate_surfaces_inherited_warning_once_per_status(
    cli_env: Dict[str, Any], capsys: pytest.CaptureFixture, status: str, expected_kind: str
) -> None:
    _seed_runtime_status(cli_env["project_root"], status)

    rc1 = cli.main(["gate", "--command", "echo irrelevant", "--json"])
    out1 = _capture(capsys)
    payload1 = json.loads(out1.out)
    assert payload1["inherited_warning"]["kind"] == expected_kind
    assert payload1["inherited_warning"]["text"]

    # 반복 호출 — 같은 status 값에 대해서는 다시 노출하지 않는다(소비/clear).
    rc2 = cli.main(["gate", "--command", "echo irrelevant", "--json"])
    out2 = _capture(capsys)
    payload2 = json.loads(out2.out)
    assert payload2["inherited_warning"]["kind"] is None

    # status 자체(runtime_state.py 소유 필드)는 gate가 되돌리지 않는다.
    state_file = runtime_state.state_path_for(cli_env["project_root"])
    persisted = json.loads(state_file.read_text(encoding="utf-8"))
    assert persisted["status"] == status


def test_gate_failed_inherited_warning_preserves_error_detail(
    cli_env: Dict[str, Any], capsys: pytest.CaptureFixture
) -> None:
    """회귀 — `_consume_inherited_warning`의 연산자 우선순위 실수
    (``A or B if C else D``가 ``(A or B) if C else D``로 파싱돼 `FAILED`
    분기의 `error` 상세가 조용히 버려졌었다)를 고정한다. `FAILED` 상태에
    저장된 `error` 문자열이 승계 텍스트에 그대로 나타나야 한다."""
    _seed_runtime_status(cli_env["project_root"], runtime_state.FAILED, error="ModuleNotFoundError: boom")

    cli.main(["gate", "--command", "echo irrelevant", "--json"])
    out = _capture(capsys)
    payload = json.loads(out.out)

    assert payload["inherited_warning"]["kind"] == "failure"
    assert "ModuleNotFoundError: boom" in payload["inherited_warning"]["text"]


@pytest.mark.parametrize("status", [runtime_state.DONE, runtime_state.PENDING, runtime_state.SKIPPED_UNCONFIGURED])
def test_gate_does_not_surface_non_inherited_statuses(
    cli_env: Dict[str, Any], capsys: pytest.CaptureFixture, status: str
) -> None:
    _seed_runtime_status(cli_env["project_root"], status)
    cli.main(["gate", "--command", "echo irrelevant", "--json"])
    out = _capture(capsys)
    payload = json.loads(out.out)
    assert payload["inherited_warning"]["kind"] is None


# ── 예외 상황에서 크래시하지 않고 종료 코드로 귀결 ──────────────────────────


def test_main_survives_unexpected_exception_in_config_resolution(
    cli_env: Dict[str, Any], capsys: pytest.CaptureFixture
) -> None:
    with patch.object(cli.config, "resolve_config", side_effect=RuntimeError("boom")):
        rc = cli.main(["check", "--json"])
    _capture(capsys)
    assert rc == report.EXIT_SCAN_ERROR


def test_check_on_nonexistent_scope_root_does_not_crash(
    cli_env: Dict[str, Any], capsys: pytest.CaptureFixture
) -> None:
    missing = cli_env["scope_root"] / "does" / "not" / "exist"
    rc = cli.main(["check", "--scope-root", str(missing), "--json"])
    out = _capture(capsys)
    payload = json.loads(out.out)
    assert rc == report.EXIT_OK
    assert payload["verdict"] == "ok_no_pending"


def test_main_help_exits_via_systemexit_not_swallowed(capsys: pytest.CaptureFixture) -> None:
    with pytest.raises(SystemExit):
        cli.main(["--help"])
    _capture(capsys)


# ── 서브프로세스 1세트 (arch §9.1 "CLI 계약") ───────────────────────────────


def test_subprocess_module_entrypoint_check_json(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    env = dict(os.environ)
    env["PYTHONPATH"] = str(_REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    env["CLAUDE_PROJECT_DIR"] = str(project_root)
    for key in ("HARNESS_KOMPOUND_REPO", "HARNESS_KOMPOUND_SCAN_ROOT", "HARNESS_KOMPOUND_CONFIG"):
        env.pop(key, None)

    proc = subprocess.run(
        [sys.executable, "-m", "hooks.lib.kompound_snapshot", "check", "--json"],
        cwd=str(_REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == report.EXIT_DISABLED
    payload = json.loads(proc.stdout)
    assert payload["verdict"] == "disabled"
