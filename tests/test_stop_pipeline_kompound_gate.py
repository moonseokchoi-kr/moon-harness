"""tests/test_stop_pipeline_kompound_gate.py — T-12 (F1, T1 통합) GREEN 테스트.

설계 SSOT: `docs/sdd/design/arch/2026-07-29-kompound-snapshot-hook.md` §5.1
(F1 — T1: stop-pipeline.py 통합). task:
`docs/sdd/task/kompound-snapshot-hook/2026-07-29-T-12-stop-pipeline-integration.md`.

`tests/test_stop_pipeline_characterization.py`(T-1)와는 별개 파일이다 —
그 파일은 "수정 전 동작 고정"(회귀 안전망)이고, 이 파일은 T-12가 신설한
kompound 완료 게이트(`_kompound_completion_gate` 등) 자체의 "새 기능
GREEN" 테스트다.

전부 `tmp_path` 기반이다. 실제 `.claude/state/`·실제 kompound를 절대
건드리지 않는다. `fake_kompound_env`(tests/conftest.py, T-2가 정의한 단일
공유 fixture)를 재사용해 실제 config→scan→naming→dedup 파이프라인을 통과한
"진짜" pending 계산으로 핵심 경로(차단/통과 대칭)를 검증하고, 나머지
세부 판정 경로(A-1, import 실패, 멱등, 게이트 위치)는 `monkeypatch`로
가볍게 격리한다.
"""

from __future__ import annotations

import importlib.util
import json
import os
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import pytest

from hooks.lib.kompound_snapshot import cli as ks_cli
from hooks.lib.kompound_snapshot import config as ks_config
from hooks.lib.kompound_snapshot import runtime_state as ks_runtime_state

# ── 모듈 로딩 (하이픈 파일명 우회, T-1 선례와 동일 방식) ─────────────────────

_REPO_ROOT = Path(__file__).resolve().parents[1]
_STOP_PIPELINE_PATH = _REPO_ROOT / "hooks" / "enforcement" / "stop-pipeline.py"


def _load_stop_pipeline():
    spec = importlib.util.spec_from_file_location("stop_pipeline_t12", _STOP_PIPELINE_PATH)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


@pytest.fixture()
def stop_pipeline():
    # 함수 스코프 — A-1 등 일부 테스트가 os.environ/파일 권한을 건드리므로
    # 모듈 간 상태 누수를 피하려고 T-1(모듈 스코프)과 달리 매 테스트 재적재한다.
    return _load_stop_pipeline()


# ── 공통 헬퍼 ────────────────────────────────────────────────────────────────


def _write_state_md(
    project_root: Path,
    *,
    feature: str = "demo-feature",
    status: str = "COMPLETED",
) -> Path:
    path = project_root / "docs" / "sdd" / "ORCHESTRATOR_STATE.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Orchestrator State\n\n## 메타\n"
        f"- feature: `{feature}`\n"
        f"- 상태: {status} (테스트 픽스처)\n",
        encoding="utf-8",
    )
    return path


def _write_project_config(project_root: Path, config: Dict[str, Any]) -> None:
    cfg_path = project_root / ".claude" / "kompound-snapshot.config.json"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps(config), encoding="utf-8")


def _decide(
    stop_pipeline,
    project_dir: Path,
    *,
    stop_data: Optional[dict] = None,
    pipeline_path: Optional[Path] = None,
) -> dict:
    pipeline_path = pipeline_path or (project_dir / ".claude" / "state" / "pipeline.json")
    return stop_pipeline.decide(stop_data or {}, project_dir, pipeline_path)


def _arm_to_completed(stop_pipeline, project_root: Path, *, feature: str = "demo-feature") -> None:
    """runtime_state의 무장(arming) 규약(arch §5.1.3 조건 1)을 흉내낸다:
    "첫 관측은 baseline 등록이고 발화하지 않는다" — 그래서 STATE가 처음부터
    COMPLETED이면 그 최초 호출은 baseline만 등록하고 절대 block하지 않는다
    (§10.4 "알려진 미탐"). 실제로 armed 판정을 받으려면 먼저 비완료 상태를
    한 번 관측시켜 baseline을 등록한 뒤 COMPLETED로 전환해야 한다 —
    T-7(`tests/test_kompound_snapshot_runtime_state.py`)의 `_arm_to_completed`
    선례와 동일 패턴."""
    _write_state_md(project_root, feature=feature, status="EXECUTING")
    _decide(stop_pipeline, project_root)
    _write_state_md(project_root, feature=feature, status="COMPLETED")


# ═══════════════════════════════════════════════════════════════════════════
# 1) 대칭 테스트 — 박제 미완(pending>=1) 차단 vs 박제 완료/미설정 통과
#    (fake_kompound_env로 실제 config→scan→naming→dedup 경로를 태운다)
# ═══════════════════════════════════════════════════════════════════════════


def test_gate_blocks_when_pending_documents_exist(stop_pipeline, fake_kompound_env, monkeypatch):
    """spec F1 Acceptance: 박제 미완(pending>=1)에서 Stop 발화 시
    {"decision": "block"} + kompound 박제 directive를 반환한다."""
    project_root = fake_kompound_env["workspace"] / "acme-widget"
    _write_project_config(project_root, fake_kompound_env["config"])
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project_root))
    _arm_to_completed(stop_pipeline, project_root)

    result = _decide(stop_pipeline, project_root)

    assert result["decision"] == "block"
    reason = result["reason"]
    assert "kompound" in reason
    assert "python3 -m hooks.lib.kompound_snapshot apply --json" in reason
    assert "self-improve" in reason


def test_gate_passes_immediately_when_kompound_unconfigured(stop_pipeline, tmp_path):
    """spec F1/F16 Acceptance: kompound 미설정(config_ok=False) 환경에서는
    즉시 통과한다({"decision": "block"}이 아니어야 한다) — pending>=1 케이스와
    대칭인 통과 경로."""
    project_root = tmp_path / "unconfigured-project"
    # HARNESS_KOMPOUND_* 환경변수·설정 파일 전부 없음 → config.resolve_config()
    # 가 ok=False를 반환해야 한다(자동 탐색도 부모 디렉토리에 kompound 서명이
    # 없으므로 실패).
    _arm_to_completed(stop_pipeline, project_root)

    result = _decide(stop_pipeline, project_root)

    assert result.get("decision") != "block"
    assert result == {"continue": True, "suppressOutput": True}
    runtime = ks_runtime_state._load_runtime(ks_runtime_state.state_path_for(project_root))
    assert runtime["status"] == ks_runtime_state.SKIPPED_UNCONFIGURED


def test_gate_passes_when_pending_zero(stop_pipeline, fake_kompound_env, monkeypatch):
    """박제 완료(pending==0)에서는 통과한다 — 실제 raw 내용과 정확히 일치하는
    workspace 문서를 구성해 `check`가 `pending: []`를 내도록 만든다."""
    project_root = fake_kompound_env["workspace"] / "acme-widget"
    _write_project_config(project_root, fake_kompound_env["config"])
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project_root))
    _arm_to_completed(stop_pipeline, project_root)

    # 실제 pending 목록을 먼저 조회해 raw 쪽 파일들을 workspace와 바이트
    # 동일하게 맞춘다(진짜 F6 내용-비교 경로를 태워 pending==0을 만든다).
    original = os.environ.get("CLAUDE_PROJECT_DIR")
    os.environ["CLAUDE_PROJECT_DIR"] = str(project_root)
    import io
    import contextlib

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
        ks_cli.main(["check", "--json"])
    if original is None:
        os.environ.pop("CLAUDE_PROJECT_DIR", None)
    else:
        os.environ["CLAUDE_PROJECT_DIR"] = original
    first_report = json.loads(buf.getvalue())
    assert first_report["pending"], "테스트 전제: fixture는 최초에 pending>=1이어야 한다"

    # scan→dedup→naming을 직접 재현해 각 pending 문서의 raw_name을 정확히
    # 계산하고, 그 경로에 원본 바이트를 그대로 복사해 F6 "동일" 상태로
    # 맞춘다(내용 기반 비교이므로 raw_name만 맞고 바이트가 다르면 여전히
    # pending으로 남는다).
    kompound_raw = fake_kompound_env["kompound"] / "raw"
    from hooks.lib.kompound_snapshot import config as _cfg
    from hooks.lib.kompound_snapshot import scan as _scan
    from hooks.lib.kompound_snapshot import dedup as _dedup
    from hooks.lib.kompound_snapshot import naming as _naming

    cfg = _cfg.resolve_config(project_root)
    scan_result = _scan.scan([project_root], max_anchor_depth=cfg["max_anchor_depth"])
    canonical = _dedup.dedup(scan_result["records"])
    for record in canonical:
        naming_result = _naming.name_document(record, cfg["prefix_map"], cfg["scan_root"])
        if "unmapped" in naming_result:
            continue
        basename = Path(naming_result["raw_name"]).name
        target = kompound_raw / basename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(Path(record["path"]).read_bytes())

    result = _decide(stop_pipeline, project_root)

    assert result == {"continue": True, "suppressOutput": True}


# ═══════════════════════════════════════════════════════════════════════════
# 2) CATALOG_PENDING — 통과 + 블록 예산 미소모
# ═══════════════════════════════════════════════════════════════════════════


def test_catalog_pending_passes_and_does_not_consume_block_budget(stop_pipeline, tmp_path, monkeypatch):
    """직전 상태가 CATALOG_PENDING이면 DONE과 동일하게 통과하고, blocks가
    증가하지 않는다(D-1, arch §5.1.3)."""
    project_root = tmp_path / "project"
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project_root))

    # config는 명시적으로 unconfigured로 둬서 cli.check 호출을 생략시키고
    # (pending_count=0 고정), runtime_state의 CATALOG_PENDING 패스스루
    # 로직만 격리해 검증한다 — config.resolve_config를 그대로 두면
    # ok=False가 되어 record_and_decide는 SKIPPED_UNCONFIGURED로 판정할
    # 것이므로, 여기서는 config_ok=True를 강제로 흉내내기 위해
    # config.resolve_config를 monkeypatch한다.
    monkeypatch.setattr(
        ks_config,
        "resolve_config",
        lambda project_root=None: {
            "ok": True,
            "kompound_repo": str(tmp_path / "fake-kompound"),
            "scan_root": None,
            "max_anchor_depth": 5,
            "state_max_age_hours": 24,
            "prefix_map": {},
            "source": {},
        },
    )

    def _fake_main(argv):
        import sys

        sys.stdout.write(json.dumps({"pending": [], "unmapped": []}))
        return 0

    monkeypatch.setattr(ks_cli, "main", _fake_main)

    # 1차: 비완료 → 완료 전이 후 armed 시켜 한 번 block까지 소모한다.
    _write_state_md(project_root, status="EXECUTING")
    _decide(stop_pipeline, project_root)
    _write_state_md(project_root, status="COMPLETED")

    # pending>=1로 한 번 block을 거쳐 armed_signature를 확정한다.
    monkeypatch.setattr(ks_cli, "main", lambda argv: (__import__("sys").stdout.write(
        json.dumps({"pending": ["x-spec.md"], "unmapped": []})
    ), 0)[1])
    first = _decide(stop_pipeline, project_root)
    assert first["decision"] == "block"

    blocks_before = ks_runtime_state._load_runtime(
        ks_runtime_state.state_path_for(project_root)
    ).get("blocks")

    # apply()가 (i) 성공 + (ii) 실패했다고 기록 → CATALOG_PENDING 진입.
    ks_runtime_state.record_apply_outcome(project_root, raw_ok=True, catalog_ok=False)

    # 다음 스캔에서 pending이 0으로 재계산된 상황(카탈로그만 남음)을 흉내낸다.
    monkeypatch.setattr(ks_cli, "main", _fake_main)  # pending: []
    result = _decide(stop_pipeline, project_root)

    assert result == {"continue": True, "suppressOutput": True}
    blocks_after = ks_runtime_state._load_runtime(
        ks_runtime_state.state_path_for(project_root)
    ).get("blocks")
    assert blocks_after == blocks_before


# ═══════════════════════════════════════════════════════════════════════════
# 3) A-1 — 런타임 상태 write 실패 시 무차단 + 경고
# ═══════════════════════════════════════════════════════════════════════════


def test_write_failure_passes_without_blocking(stop_pipeline, tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project_root))

    monkeypatch.setattr(
        ks_config,
        "resolve_config",
        lambda project_root=None: {
            "ok": True,
            "kompound_repo": str(tmp_path / "fake-kompound"),
            "scan_root": None,
            "max_anchor_depth": 5,
            "state_max_age_hours": 24,
            "prefix_map": {},
            "source": {},
        },
    )

    def _fake_main_pending(argv):
        import sys

        sys.stdout.write(json.dumps({"pending": ["x-spec.md"], "unmapped": []}))
        return 0

    monkeypatch.setattr(ks_cli, "main", _fake_main_pending)

    _write_state_md(project_root, status="COMPLETED")

    state_dir = project_root / ".claude" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    original_mode = state_dir.stat().st_mode
    os.chmod(state_dir, stat.S_IREAD | stat.S_IEXEC)
    try:
        result = _decide(stop_pipeline, project_root)
        assert result == {"continue": True, "suppressOutput": True}

        # 반복 호출해도 무한 block 없이 계속 통과해야 한다.
        result2 = _decide(stop_pipeline, project_root)
        assert result2 == {"continue": True, "suppressOutput": True}
    finally:
        os.chmod(state_dir, original_mode)


# ═══════════════════════════════════════════════════════════════════════════
# 4) pipeline.json 부재(C3)에서도 게이트가 동작한다
# ═══════════════════════════════════════════════════════════════════════════


def test_gate_fires_even_without_pipeline_json(stop_pipeline, tmp_path, monkeypatch):
    """`/sdd-orchestrator` 직접 실행 케이스(C3) — pipeline.json이 아예 없어도
    게이트는 pipeline.json과 무관하게 정상 동작하고 AttributeError가 나지
    않는다."""
    project_root = tmp_path / "project"
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project_root))
    pipeline_path = project_root / ".claude" / "state" / "pipeline.json"
    assert not pipeline_path.exists()

    monkeypatch.setattr(
        ks_config,
        "resolve_config",
        lambda project_root=None: {
            "ok": True,
            "kompound_repo": str(tmp_path / "fake-kompound"),
            "scan_root": None,
            "max_anchor_depth": 5,
            "state_max_age_hours": 24,
            "prefix_map": {},
            "source": {},
        },
    )

    def _fake_main(argv):
        import sys

        sys.stdout.write(json.dumps({"pending": ["x-spec.md"], "unmapped": []}))
        return 0

    monkeypatch.setattr(ks_cli, "main", _fake_main)
    _arm_to_completed(stop_pipeline, project_root)

    result = stop_pipeline.decide({}, project_root, pipeline_path)

    assert not pipeline_path.exists()  # 게이트가 pipeline.json을 만들지 않는다
    assert result["decision"] == "block"


# ═══════════════════════════════════════════════════════════════════════════
# 5) is_stale / 세션 불일치 상황에서도 게이트가 먼저 평가된다(게이트 위치)
# ═══════════════════════════════════════════════════════════════════════════


def test_gate_evaluated_before_stale_and_session_checks(stop_pipeline, tmp_path, monkeypatch):
    """pipeline.json이 2시간 이상 stale하고 session_id도 불일치하는
    상태이더라도(Step 2/3이라면 즉시 통과했을 상황), 게이트가 그보다 먼저
    평가되어 pending>=1이면 여전히 차단한다."""
    project_root = tmp_path / "project"
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project_root))

    monkeypatch.setattr(
        ks_config,
        "resolve_config",
        lambda project_root=None: {
            "ok": True,
            "kompound_repo": str(tmp_path / "fake-kompound"),
            "scan_root": None,
            "max_anchor_depth": 5,
            "state_max_age_hours": 24,
            "prefix_map": {},
            "source": {},
        },
    )

    def _fake_main(argv):
        import sys

        sys.stdout.write(json.dumps({"pending": ["x-spec.md"], "unmapped": []}))
        return 0

    monkeypatch.setattr(ks_cli, "main", _fake_main)
    _arm_to_completed(stop_pipeline, project_root)

    # pipeline.json: 매우 오래된 last_updated + 다른 세션 id (Step 2/3이
    # 먼저였다면 즉시 continue=True로 통과했을 상황).
    from datetime import datetime, timedelta, timezone

    stale_state = {
        "current_label": "PHASE1_UX_RESEARCH_DONE",
        "feature": "demo",
        "session_id": "some-other-session",
        "circuit_breaker": {},
        "last_updated": (datetime.now(timezone.utc) - timedelta(hours=10)).isoformat(),
    }
    pipeline_path = project_root / ".claude" / "state" / "pipeline.json"
    pipeline_path.parent.mkdir(parents=True, exist_ok=True)
    pipeline_path.write_text(json.dumps(stale_state), encoding="utf-8")

    result = stop_pipeline.decide(
        {"session_id": "current-session"}, project_root, pipeline_path
    )

    assert result["decision"] == "block"
    assert "kompound" in result["reason"]


# ═══════════════════════════════════════════════════════════════════════════
# 6) import 실패 시 통과(경고) — block하지 않는다
# ═══════════════════════════════════════════════════════════════════════════


def test_gate_passes_when_core_import_fails(stop_pipeline, tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    _write_state_md(project_root, status="COMPLETED")

    import builtins

    real_import = builtins.__import__

    def _blocking_import(name, *args, **kwargs):
        if name == "hooks.lib.kompound_snapshot" or name.startswith("hooks.lib.kompound_snapshot"):
            raise ModuleNotFoundError(f"simulated import failure for {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _blocking_import)

    result = _decide(stop_pipeline, project_root)

    assert result == {"continue": True, "suppressOutput": True}


# ═══════════════════════════════════════════════════════════════════════════
# 7) 동일 사이클 2회 실행 — 두 번째는 "이미 박제됨"으로 무동작(멱등)
# ═══════════════════════════════════════════════════════════════════════════


def test_second_run_after_done_is_noop(stop_pipeline, tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project_root))

    monkeypatch.setattr(
        ks_config,
        "resolve_config",
        lambda project_root=None: {
            "ok": True,
            "kompound_repo": str(tmp_path / "fake-kompound"),
            "scan_root": None,
            "max_anchor_depth": 5,
            "state_max_age_hours": 24,
            "prefix_map": {},
            "source": {},
        },
    )

    def _fake_main_no_pending(argv):
        import sys

        sys.stdout.write(json.dumps({"pending": [], "unmapped": []}))
        return 0

    monkeypatch.setattr(ks_cli, "main", _fake_main_no_pending)
    _arm_to_completed(stop_pipeline, project_root)

    first = _decide(stop_pipeline, project_root)
    assert first == {"continue": True, "suppressOutput": True}

    runtime_after_first = ks_runtime_state._load_runtime(
        ks_runtime_state.state_path_for(project_root)
    )
    assert runtime_after_first["status"] == ks_runtime_state.DONE

    # 두 번째 호출(같은 사이클, STATE 서명 불변) — 여전히 DONE, block 없음.
    second = _decide(stop_pipeline, project_root)
    assert second == {"continue": True, "suppressOutput": True}
    runtime_after_second = ks_runtime_state._load_runtime(
        ks_runtime_state.state_path_for(project_root)
    )
    assert runtime_after_second["status"] == ks_runtime_state.DONE
    assert runtime_after_second["blocks"] == runtime_after_first["blocks"]


# ═══════════════════════════════════════════════════════════════════════════
# 8) 부트스트랩 후에도 기존 Step 0~9 동작이 불변 (sys.path 부작용만)
# ═══════════════════════════════════════════════════════════════════════════


def test_bootstrap_only_touches_syspath(stop_pipeline):
    """모듈 최상위 부트스트랩은 `sys.path`에 plugin root를 넣는 것 외의
    부작용을 만들지 않는다."""
    import sys

    assert str(stop_pipeline._KOMPOUND_PLUGIN_ROOT) in sys.path
    assert stop_pipeline._KOMPOUND_PLUGIN_ROOT == _REPO_ROOT


def test_non_sdd_project_decide_unaffected_by_gate(stop_pipeline, tmp_path):
    """ORCHESTRATOR_STATE.md가 아예 없는(=SDD를 쓰지 않는) 프로젝트에서는
    게이트가 즉시 개입하지 않고, 기존 pipeline.json 기반 결과가 그대로
    반환된다."""
    pipeline_path = tmp_path / ".claude" / "state" / "pipeline.json"
    pipeline_path.parent.mkdir(parents=True, exist_ok=True)
    pipeline_path.write_text(json.dumps({}), encoding="utf-8")

    result = stop_pipeline.decide({}, tmp_path, pipeline_path)

    # 상태가 falsy dict({})라 Step 1의 "파이프라인 비활성" 경로로 그대로 간다.
    assert result == {"continue": True, "suppressOutput": True}


# ═══════════════════════════════════════════════════════════════════════════
# 9) DIRECTIVES 신규 키 — 존재 + 실행 커맨드 형태
# ═══════════════════════════════════════════════════════════════════════════


def test_directives_has_kompound_pending_key_with_tokens(stop_pipeline):
    directive = stop_pipeline.DIRECTIVES["PHASE4_KOMPOUND_SNAPSHOT_PENDING"]
    assert isinstance(directive, str)
    assert "@@CLI@@" in directive
    assert "@@SCOPE@@" in directive


def test_directive_text_uses_str_replace_not_format(stop_pipeline, tmp_path):
    """치환된 directive에 미치환 토큰이 남지 않아야 하고, 리터럴 중괄호가
    있는 다른 directive 값과 같은 딕셔너리를 str.format()으로 건드리지
    않는다(모듈 전체가 str.format을 쓰지 않아야 이 값도 안전하다)."""
    text = stop_pipeline._kompound_directive_text(tmp_path / "plugin", tmp_path / "proj")
    assert "@@CLI@@" not in text
    assert "@@SCOPE@@" not in text
    assert str(tmp_path / "plugin") in text


# ═══════════════════════════════════════════════════════════════════════════
# 10) 성능 회귀 방지 (T-12 iteration 2, [P1]) — 무장 안 됨 경로는 config/cli를
#     전혀 건드리지 않는다(전체 워크스페이스 스캔 회피). 대칭으로, 무장되면
#     반드시 호출된다(패치 오적용으로 "항상 스킵"이 되는 회귀를 배제).
# ═══════════════════════════════════════════════════════════════════════════


def _install_call_counters(monkeypatch) -> Dict[str, Dict[str, int]]:
    """`ks_cli.main`/`ks_config.resolve_config`를 호출 횟수를 세는 스텁으로
    바꿔치기하고, 카운터 dict를 반환한다."""
    counters = {"cli_main": {"count": 0}, "resolve_config": {"count": 0}}

    def _counting_main(argv):
        counters["cli_main"]["count"] += 1
        import sys

        sys.stdout.write(json.dumps({"pending": ["x-spec.md"], "unmapped": []}))
        return 0

    def _counting_resolve_config(project_root=None):
        counters["resolve_config"]["count"] += 1
        return {
            "ok": True,
            "kompound_repo": "/does/not/matter",
            "scan_root": None,
            "max_anchor_depth": 5,
            "state_max_age_hours": 24,
            "prefix_map": {},
            "source": {},
        }

    monkeypatch.setattr(ks_cli, "main", _counting_main)
    monkeypatch.setattr(ks_config, "resolve_config", _counting_resolve_config)
    return counters


def test_not_armed_skips_core_import_and_scan_status_not_completed(
    stop_pipeline, tmp_path, monkeypatch
):
    """무장 안 됨 케이스 ①: 상태 != COMPLETED. `cli.main`/`config.resolve_config`
    가 단 한 번도 호출되지 않아야 한다(전체 스캔 회피가 이 iteration의 핵심
    성능 수정 사항)."""
    project_root = tmp_path / "project"
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project_root))
    counters = _install_call_counters(monkeypatch)

    _write_state_md(project_root, status="EXECUTING")
    result = _decide(stop_pipeline, project_root)

    assert result == {"continue": True, "suppressOutput": True}
    assert counters["cli_main"]["count"] == 0
    assert counters["resolve_config"]["count"] == 0


def test_not_armed_skips_core_import_and_scan_signature_unchanged(
    stop_pipeline, tmp_path, monkeypatch
):
    """무장 안 됨 케이스 ②: 서명 불변(같은 COMPLETED를 반복 관측). 첫 관측은
    baseline 등록(첫 관측 자체도 무장 아님)이고, 두 번째 동일 관측은
    signature_unchanged로 여전히 무장 아님 — 두 호출 다 스캔 0회."""
    project_root = tmp_path / "project"
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project_root))
    counters = _install_call_counters(monkeypatch)

    _write_state_md(project_root, status="COMPLETED")
    _decide(stop_pipeline, project_root)  # 첫 관측 — baseline 등록, 무장 아님
    _decide(stop_pipeline, project_root)  # 서명 불변 — 여전히 무장 아님

    assert counters["cli_main"]["count"] == 0
    assert counters["resolve_config"]["count"] == 0


def test_not_armed_skips_core_import_and_scan_state_stale(stop_pipeline, tmp_path, monkeypatch):
    """무장 안 됨 케이스 ③: STATE mtime이 `state_max_age_hours`(기본 24h)를
    초과 — 신선도 조건 미충족으로 여전히 무장 아님, 스캔 0회."""
    project_root = tmp_path / "project"
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project_root))
    counters = _install_call_counters(monkeypatch)

    # baseline을 EXECUTING으로 먼저 등록(서명이 이후 COMPLETED와 달라지게).
    _write_state_md(project_root, status="EXECUTING")
    _decide(stop_pipeline, project_root)

    state_path = _write_state_md(project_root, status="COMPLETED")
    old_ts = (datetime.now(timezone.utc) - timedelta(hours=48)).timestamp()
    os.utime(state_path, (old_ts, old_ts))

    result = _decide(stop_pipeline, project_root)

    assert result == {"continue": True, "suppressOutput": True}
    assert counters["cli_main"]["count"] == 0
    assert counters["resolve_config"]["count"] == 0


def test_armed_calls_core_config_and_scan_at_least_once(stop_pipeline, tmp_path, monkeypatch):
    """대칭 확인: 실제로 무장되면 `config.resolve_config`/`cli.main`이 최소
    1회씩 호출된다 — 패치가 "항상 스킵"으로 오적용되는 회귀를 배제한다."""
    project_root = tmp_path / "project"
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project_root))
    counters = _install_call_counters(monkeypatch)

    _arm_to_completed(stop_pipeline, project_root)
    result = _decide(stop_pipeline, project_root)

    assert result["decision"] == "block"
    assert counters["cli_main"]["count"] >= 1
    assert counters["resolve_config"]["count"] >= 1
