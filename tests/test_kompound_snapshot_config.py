"""tests/test_kompound_snapshot_config.py — T-3 (F16 설정 해석) GREEN 테스트.

설계 SSOT: `docs/sdd/design/arch/2026-07-29-kompound-snapshot-hook.md` §6.1,
task: `docs/sdd/task/kompound-snapshot-hook/2026-07-29-T-3-config-resolution.md`.

전부 `tmp_path` 기반이다 — 실제 kompound·실제 `~/.claude`를 절대 읽거나
쓰지 않는다. 모든 테스트가 `_isolated_env()`로 3종 환경변수를 지우고
`CLAUDE_CONFIG_DIR`을 빈 tmp 디렉토리로 고정해, 이 머신에 실재하는
`~/.claude/kompound-snapshot.json`(개발자 moon의 실제 kompound 설정)이
어떤 테스트에도 새어 들어오지 않도록 격리한다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import pytest

from hooks.lib.kompound_snapshot.config import DEFAULT_PREFIX_MAP, resolve_config

_ENV_KEYS = (
    "HARNESS_KOMPOUND_REPO",
    "HARNESS_KOMPOUND_SCAN_ROOT",
    "HARNESS_KOMPOUND_CONFIG",
)


def _isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """3종 env를 지우고 `CLAUDE_CONFIG_DIR`을 빈 tmp 디렉토리로 고정한다.

    반환값은 그 홈 설정 디렉토리 경로 — 테스트가 홈 파일을 직접 심고
    싶으면 이 경로 아래 `kompound-snapshot.json`을 쓰면 된다.
    """
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    home_config_dir = tmp_path / "isolated_home_config"
    home_config_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(home_config_dir))
    return home_config_dir


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _make_project_root(tmp_path: Path, name: str = "project") -> Path:
    root = tmp_path / name
    root.mkdir(parents=True, exist_ok=True)
    return root


def _seed_kompound_signature(path: Path) -> None:
    """kompound 서명 4조건(.git, raw/, wiki/index.md, wiki/log.md)을 심는다.

    실제 `git init`은 하지 않는다 — 서명 판정은 `.git` "존재"만 보므로
    (arch §6.1 ③-2), 디렉토리 하나면 충분하고 fixture 생성이 빨라진다.
    """
    (path / ".git").mkdir(parents=True, exist_ok=True)
    (path / "raw").mkdir(parents=True, exist_ok=True)
    (path / "wiki").mkdir(parents=True, exist_ok=True)
    (path / "wiki" / "index.md").write_text("# index\n", encoding="utf-8")
    (path / "wiki" / "log.md").write_text("# log\n", encoding="utf-8")


def _project_config_path(project_root: Path) -> Path:
    return project_root / ".claude" / "kompound-snapshot.config.json"


def _home_config_path(home_config_dir: Path) -> Path:
    return home_config_dir / "kompound-snapshot.json"


# ── ① 환경변수가 최우선 ──────────────────────────────────────────────────────


def test_env_wins_over_project_and_home_files(monkeypatch, tmp_path) -> None:
    home_config_dir = _isolated_env(monkeypatch, tmp_path)
    project_root = _make_project_root(tmp_path)

    _write_json(
        _project_config_path(project_root),
        {"schema_version": 1, "kompound_repo": str(tmp_path / "from-project")},
    )
    _write_json(
        _home_config_path(home_config_dir),
        {"schema_version": 1, "kompound_repo": str(tmp_path / "from-home")},
    )
    monkeypatch.setenv("HARNESS_KOMPOUND_REPO", str(tmp_path / "from-env"))
    monkeypatch.setenv("HARNESS_KOMPOUND_SCAN_ROOT", str(tmp_path / "scan-from-env"))

    result = resolve_config(project_root=project_root)

    assert result["ok"] is True
    assert result["kompound_repo"] == str(tmp_path / "from-env")
    assert result["scan_root"] == str(tmp_path / "scan-from-env")
    assert result["source"]["kompound_repo"] == "env"
    assert result["source"]["scan_root"] == "env"


# ── ②-a 프로젝트 파일이 ②-b 홈 파일을 이긴다(같은 키) ──────────────────────


def test_project_file_wins_over_home_file_for_same_key(monkeypatch, tmp_path) -> None:
    home_config_dir = _isolated_env(monkeypatch, tmp_path)
    project_root = _make_project_root(tmp_path)

    _write_json(
        _project_config_path(project_root),
        {"schema_version": 1, "kompound_repo": str(tmp_path / "from-project")},
    )
    _write_json(
        _home_config_path(home_config_dir),
        {"schema_version": 1, "kompound_repo": str(tmp_path / "from-home")},
    )

    result = resolve_config(project_root=project_root)

    assert result["kompound_repo"] == str(tmp_path / "from-project")
    assert result["source"]["kompound_repo"] == "project"


# ── J-10 핵심 케이스: 키 단위 병합 — 프로젝트 파일이 한 키만 담아도 홈의
#    다른 키를 가리지 않는다(file-first-wins이면 여기서 실패해야 정상) ──────


def test_key_level_merge_project_partial_file_does_not_hide_home_kompound_repo(
    monkeypatch, tmp_path
) -> None:
    home_config_dir = _isolated_env(monkeypatch, tmp_path)
    project_root = _make_project_root(tmp_path)

    # 프로젝트 파일은 max_anchor_depth "만" 담는다 — kompound_repo가 없다.
    _write_json(
        _project_config_path(project_root),
        {"schema_version": 1, "max_anchor_depth": 3},
    )
    _write_json(
        _home_config_path(home_config_dir),
        {"schema_version": 1, "kompound_repo": str(tmp_path / "home-kompound")},
    )

    result = resolve_config(project_root=project_root)

    # file-first-wins라면 kompound_repo가 None(비활성)이 됐어야 한다.
    assert result["ok"] is True
    assert result["kompound_repo"] == str(tmp_path / "home-kompound")
    assert result["source"]["kompound_repo"] == "home"
    # max_anchor_depth는 프로젝트 파일의 값을 그대로 채택.
    assert result["max_anchor_depth"] == 3
    assert result["source"]["max_anchor_depth"] == "project"
    # 홈 파일이 지정하지 않은 state_max_age_hours는 코드 기본값.
    assert result["state_max_age_hours"] == 24
    assert result["source"]["state_max_age_hours"] == "default"


# ── prefix_map: dict 병합 + null 삭제 ───────────────────────────────────────


def test_prefix_map_dict_merge_and_null_deletion(monkeypatch, tmp_path) -> None:
    home_config_dir = _isolated_env(monkeypatch, tmp_path)
    project_root = _make_project_root(tmp_path)

    # 기본 맵에 실재하는 키 하나를 골라 홈에서 값 변경, 프로젝트에서 삭제(null).
    some_default_key = next(iter(DEFAULT_PREFIX_MAP))

    _write_json(
        _home_config_path(home_config_dir),
        {
            "schema_version": 1,
            "prefix_map": {"acme-widget": "acme", some_default_key: "overridden-by-home"},
        },
    )
    _write_json(
        _project_config_path(project_root),
        {
            "schema_version": 1,
            "prefix_map": {some_default_key: None, "beta-service": "beta"},
        },
    )

    result = resolve_config(project_root=project_root)
    merged = result["prefix_map"]

    # 홈이 추가한 키는 남아있다.
    assert merged.get("acme-widget") == "acme"
    # 프로젝트가 null로 지정한 키는 (홈이 덮어썼더라도) 최종 삭제된다.
    assert some_default_key not in merged
    # 프로젝트가 추가한 키도 반영된다.
    assert merged.get("beta-service") == "beta"
    # 건드리지 않은 다른 기본값은 그대로 살아있다.
    untouched_key = next(k for k in DEFAULT_PREFIX_MAP if k != some_default_key)
    assert merged.get(untouched_key) == DEFAULT_PREFIX_MAP[untouched_key]
    assert result["source"]["prefix_map"] == "merged"


def test_custom_prefix_map_11th_repo_merges_with_default(monkeypatch, tmp_path) -> None:
    """11번째 repo 추가 — 커스텀 매핑이 DEFAULT_PREFIX_MAP과 병합되어 그대로 쓰인다."""
    home_config_dir = _isolated_env(monkeypatch, tmp_path)
    project_root = _make_project_root(tmp_path)

    _write_json(
        _home_config_path(home_config_dir),
        {"schema_version": 1, "prefix_map": {"eleventh-repo": "eleventh"}},
    )

    result = resolve_config(project_root=project_root)
    merged = result["prefix_map"]

    assert merged.get("eleventh-repo") == "eleventh"
    for key, value in DEFAULT_PREFIX_MAP.items():
        assert merged.get(key) == value


def test_prefix_map_default_only_when_no_override(monkeypatch, tmp_path) -> None:
    _isolated_env(monkeypatch, tmp_path)
    project_root = _make_project_root(tmp_path)

    result = resolve_config(project_root=project_root)

    assert result["prefix_map"] == DEFAULT_PREFIX_MAP
    assert result["source"]["prefix_map"] == "default"


# ── ③ 자동 탐색 ──────────────────────────────────────────────────────────────


def test_auto_discovery_adopts_single_signature_match(monkeypatch, tmp_path) -> None:
    _isolated_env(monkeypatch, tmp_path)

    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    project_root = workspace_root  # project_root의 부모(tmp_path)에서 탐색한다
    kompound_dir = tmp_path / "marvelous_kompound"
    _seed_kompound_signature(kompound_dir)

    result = resolve_config(project_root=project_root)

    assert result["ok"] is True
    assert result["kompound_repo"] == str(kompound_dir)
    assert result["source"]["kompound_repo"] == "discovery"
    assert result["scan_root"] == str(tmp_path)
    assert result["source"]["scan_root"] == "discovery"


def test_auto_discovery_two_candidates_not_adopted(monkeypatch, tmp_path) -> None:
    _isolated_env(monkeypatch, tmp_path)

    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    _seed_kompound_signature(tmp_path / "kompound-one")
    _seed_kompound_signature(tmp_path / "kompound-two")

    result = resolve_config(project_root=workspace_root)

    assert result["ok"] is False
    assert result["kompound_repo"] is None
    assert "kompound_repo" not in result["source"]


def test_auto_discovery_name_alone_without_signature_not_adopted(monkeypatch, tmp_path) -> None:
    """이름은 kompound스럽지만(marvelous_kompound) 서명 미충족 → 미채택."""
    _isolated_env(monkeypatch, tmp_path)

    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    lookalike = tmp_path / "marvelous_kompound"
    lookalike.mkdir()
    (lookalike / "raw").mkdir()
    # wiki/index.md, wiki/log.md, .git 은 일부러 만들지 않는다 — 서명 미충족.

    result = resolve_config(project_root=workspace_root)

    assert result["ok"] is False
    assert result["kompound_repo"] is None


def test_auto_discovery_zero_candidates_not_adopted(monkeypatch, tmp_path) -> None:
    _isolated_env(monkeypatch, tmp_path)
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    (tmp_path / "unrelated-sibling").mkdir()

    result = resolve_config(project_root=workspace_root)

    assert result["ok"] is False
    assert result["kompound_repo"] is None
    assert result["scan_root"] is None


def test_auto_discovery_reuses_fake_kompound_env_fixture(monkeypatch, tmp_path, fake_kompound_env) -> None:
    """T-2의 `fake_kompound_env` fixture 재사용 — kompound와 workspace가
    같은 tmp_path 아래 형제 디렉토리이므로, workspace를 project_root로 주면
    자동 탐색이 fixture의 kompound를 정확히 채택해야 한다.
    """
    _isolated_env(monkeypatch, tmp_path)

    kompound = fake_kompound_env["kompound"]
    workspace = fake_kompound_env["workspace"]

    result = resolve_config(project_root=workspace)

    assert result["ok"] is True
    assert result["kompound_repo"] == str(kompound)
    assert result["source"]["kompound_repo"] == "discovery"


# ── 스캔 루트 거부 규칙: `/` 또는 홈 디렉토리 자체는 거부한다 ───────────────


def test_discovery_rejects_scan_root_equal_to_home(monkeypatch, tmp_path) -> None:
    _isolated_env(monkeypatch, tmp_path)
    home = Path.home()

    # 진짜 홈 디렉토리를 kompound의 부모로 오인시키는 시나리오는 실제 홈을
    # 건드릴 수 없으므로, discover 내부 판정 함수를 직접 검증한다(단위 성격).
    from hooks.lib.kompound_snapshot.config import _reject_scan_root

    assert _reject_scan_root(home) is True
    assert _reject_scan_root(Path(home.anchor) if home.anchor else Path("/")) is True
    assert _reject_scan_root(tmp_path) is False


# ── 미설정 → 비활성(오류 아님) ───────────────────────────────────────────────


def test_fully_unconfigured_returns_disabled_not_exception(monkeypatch, tmp_path) -> None:
    _isolated_env(monkeypatch, tmp_path)
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    result = resolve_config(project_root=workspace_root)

    assert result["ok"] is False
    assert result["kompound_repo"] is None
    assert result["scan_root"] is None
    # 미설정이어도 스칼라 기본값·prefix_map 기본값은 여전히 채워진다(F13 fail-safe).
    assert result["max_anchor_depth"] == 5
    assert result["state_max_age_hours"] == 24
    assert result["prefix_map"] == DEFAULT_PREFIX_MAP
    assert isinstance(result["source"], dict)


def test_kompound_repo_unresolved_but_scan_root_resolved_is_not_disabled_semantically(
    monkeypatch, tmp_path
) -> None:
    """`scan_root`만 해석돼도 `kompound_repo` 미해석이면 `ok`는 여전히 False —
    두 미해석의 의미가 다르다는 것을 스키마 레벨에서 확인한다(arch §6.1).
    """
    _isolated_env(monkeypatch, tmp_path)
    project_root = _make_project_root(tmp_path)
    monkeypatch.setenv("HARNESS_KOMPOUND_SCAN_ROOT", str(tmp_path / "scan-only"))

    result = resolve_config(project_root=project_root)

    assert result["ok"] is False
    assert result["kompound_repo"] is None
    assert result["scan_root"] == str(tmp_path / "scan-only")
    assert result["source"]["scan_root"] == "env"
    assert "kompound_repo" not in result["source"]


# ── HARNESS_KOMPOUND_CONFIG: 설정 파일 경로 직접 지정이 ②의 탐색을 대체 ─────


def test_harness_kompound_config_env_overrides_project_and_home_search(
    monkeypatch, tmp_path
) -> None:
    home_config_dir = _isolated_env(monkeypatch, tmp_path)
    project_root = _make_project_root(tmp_path)

    # 정상적인 ②-a/②-b 파일도 심어두되, override 파일이 이겨야 한다.
    _write_json(
        _project_config_path(project_root),
        {"schema_version": 1, "kompound_repo": str(tmp_path / "from-project")},
    )
    _write_json(
        _home_config_path(home_config_dir),
        {"schema_version": 1, "kompound_repo": str(tmp_path / "from-home")},
    )

    override_path = tmp_path / "custom-config.json"
    _write_json(override_path, {"schema_version": 1, "kompound_repo": str(tmp_path / "from-override")})
    monkeypatch.setenv("HARNESS_KOMPOUND_CONFIG", str(override_path))

    result = resolve_config(project_root=project_root)

    assert result["kompound_repo"] == str(tmp_path / "from-override")


def test_harness_kompound_config_env_invalid_path_falls_back_to_no_value(
    monkeypatch, tmp_path
) -> None:
    _isolated_env(monkeypatch, tmp_path)
    project_root = _make_project_root(tmp_path)
    monkeypatch.setenv("HARNESS_KOMPOUND_CONFIG", str(tmp_path / "does-not-exist.json"))

    result = resolve_config(project_root=project_root)

    # 파일이 없으면 예외 없이 "값 없음" 처리 — 자동 탐색/기본값으로 계속 진행.
    assert result["ok"] is False
    assert result["kompound_repo"] is None


# ── source 맵 정확성 종합 케이스 ─────────────────────────────────────────────


def test_source_map_reflects_every_scalar_origin(monkeypatch, tmp_path) -> None:
    home_config_dir = _isolated_env(monkeypatch, tmp_path)
    project_root = _make_project_root(tmp_path)

    monkeypatch.setenv("HARNESS_KOMPOUND_REPO", str(tmp_path / "env-repo"))
    _write_json(
        _project_config_path(project_root),
        {"schema_version": 1, "max_anchor_depth": 7},
    )
    _write_json(
        _home_config_path(home_config_dir),
        {"schema_version": 1, "state_max_age_hours": 48},
    )

    result = resolve_config(project_root=project_root)

    assert result["source"] == {
        "kompound_repo": "env",
        "max_anchor_depth": "project",
        "state_max_age_hours": "home",
        "prefix_map": "default",
    }


# ── 순수성: 반복 호출해도 동일 입력 → 동일 출력, 캐시 없음 ──────────────────


def test_resolve_config_is_pure_across_repeated_calls(monkeypatch, tmp_path) -> None:
    home_config_dir = _isolated_env(monkeypatch, tmp_path)
    project_root = _make_project_root(tmp_path)
    _write_json(
        _project_config_path(project_root),
        {"schema_version": 1, "kompound_repo": str(tmp_path / "stable-repo")},
    )

    first = resolve_config(project_root=project_root)
    second = resolve_config(project_root=project_root)

    assert first == second

    # 자동 탐색 결과도 호출마다 재계산된다(캐시 없음) — 후보를 늘리면 즉시 반영.
    workspace_root = tmp_path / "workspace2"
    workspace_root.mkdir()
    before = resolve_config(project_root=workspace_root)
    assert before["kompound_repo"] is None

    _seed_kompound_signature(tmp_path / "newly-appeared-kompound")
    after = resolve_config(project_root=workspace_root)
    assert after["kompound_repo"] == str(tmp_path / "newly-appeared-kompound")


def test_resolve_config_never_raises_on_garbage_config_json(monkeypatch, tmp_path) -> None:
    home_config_dir = _isolated_env(monkeypatch, tmp_path)
    project_root = _make_project_root(tmp_path)
    project_config = _project_config_path(project_root)
    project_config.parent.mkdir(parents=True, exist_ok=True)
    project_config.write_text("{not valid json", encoding="utf-8")

    result = resolve_config(project_root=project_root)

    assert result["ok"] is False
    assert result["kompound_repo"] is None
