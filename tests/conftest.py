"""tests/conftest.py — Wave 1 코어 오프라인 pytest 스위트 공통 인프라.

역할:
1. 리포지토리 루트를 sys.path에 추가 (session scope) — 어느 cwd에서 실행되든 동작.
2. 공통 픽스처: tmp_learning_file, sample_state_json, sample_entries.
3. `offline` 마커 등록 (네트워크/LLM 무호출 테스트 명시).
4. 네트워크 차단 픽스처 (no_network) — 활성화 시 소켓 생성 시도에서 실패.

오프라인 보장 전략
------------------
- 런타임 모듈(hooks/lib/self_improve/)은 stdlib만 사용하므로 별도 차단 없이도
  `pytest tests/ -v --tb=short` 실행이 네트워크 미접촉.
- `no_network` 픽스처를 명시적으로 요청하면 socket.socket 을 패치해
  만약 어떤 코드가 TCP/UDP 연결을 시도할 경우 즉시 RuntimeError를 발생시킴.
- 모든 테스트는 기본적으로 오프라인 전용이므로 `offline` 마커로 문서화함.
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch

import pytest

# ── sys.path: 리포 루트 등록 (session-level 부작용) ─────────────────────────
# conftest.py 위치: tests/conftest.py → parents[1] == repo root
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


# ── 마커 등록 ────────────────────────────────────────────────────────────────

def pytest_configure(config: pytest.Config) -> None:
    """커스텀 마커를 pytest에 등록한다."""
    config.addinivalue_line(
        "markers",
        "offline: 네트워크/LLM 호출이 없는 순수 오프라인 테스트 (CI blocking suite)",
    )


# ── 공통 픽스처 ──────────────────────────────────────────────────────────────

@pytest.fixture()
def sample_learning_text() -> str:
    """골든 LEARNING.md 텍스트 (tests/fixtures/sample_learning.md 내용)."""
    return (_FIXTURES_DIR / "sample_learning.md").read_text(encoding="utf-8")


@pytest.fixture()
def sample_learning_with_markers_text() -> str:
    """마커 경계 케이스 골든 LEARNING.md 텍스트."""
    return (_FIXTURES_DIR / "sample_learning_with_markers.md").read_text(encoding="utf-8")


@pytest.fixture()
def tmp_learning_file(tmp_path: Path) -> Path:
    """tmp_path에 sample_learning.md 내용을 복사한 임시 파일 경로를 반환한다.

    반환된 Path는 tests/fixtures/sample_learning.md 와 동일한 내용이며,
    각 테스트가 독립적인 파일 인스턴스를 얻는다.
    """
    content = (_FIXTURES_DIR / "sample_learning.md").read_text(encoding="utf-8")
    dest = tmp_path / "LEARNING.md"
    dest.write_text(content, encoding="utf-8")
    return dest


@pytest.fixture()
def sample_state_json() -> Dict[str, Any]:
    """골든 pr_converge 상태 dict (tests/fixtures/pr_converge_state_v1.json)."""
    return json.loads(
        (_FIXTURES_DIR / "pr_converge_state_v1.json").read_text(encoding="utf-8")
    )


@pytest.fixture()
def sample_retro_state_json() -> Dict[str, Any]:
    """골든 retro 상태 dict (tests/fixtures/retro_state_v1.json)."""
    return json.loads(
        (_FIXTURES_DIR / "retro_state_v1.json").read_text(encoding="utf-8")
    )


@pytest.fixture()
def sample_entries() -> List[Dict[str, Any]]:
    """파싱된 엔트리 목록 샘플 (parser를 통하지 않는 인라인 dict).

    각 엔트리는 hooks.lib.self_improve.parser.parse_learning_entry 출력
    형식과 동일한 키 구조를 따른다.
    """
    return [
        {
            "marker": "2026-06-10 — auth-refresh / T-12",
            "body": "Refresh tokens single-flight dedup concurrent rotation.",
            "tags": {"domain": "auth", "stage": "구현", "provenance_repo": "moon-harness"},
            "raw": (
                "## 2026-06-10 — auth-refresh / T-12\n"
                "<!-- tags: domain=auth, stage=구현, provenance_repo=moon-harness -->\n\n"
                "Refresh tokens single-flight dedup concurrent rotation."
            ),
        },
        {
            "marker": "2026-06-11 — pr-feedback-dedup / T-7",
            "body": "Reviewer left the same nit on three files; dedup by signal key.",
            "tags": {
                "domain": "pr-converge",
                "stage": "pr-converge",
                "provenance_repo": "marvelous",
            },
            "raw": (
                "## 2026-06-11 — pr-feedback-dedup / T-7\n"
                "<!-- tags: domain=pr-converge, stage=pr-converge, provenance_repo=marvelous -->\n\n"
                "Reviewer left the same nit on three files; dedup by signal key."
            ),
        },
        {
            "marker": "2026-06-12 — quick-note / T-3",
            "body": "This entry has NO tag metablock.",
            "tags": None,
            "raw": "## 2026-06-12 — quick-note / T-3\n\nThis entry has NO tag metablock.",
        },
    ]


# ── 네트워크 차단 픽스처 ─────────────────────────────────────────────────────

@pytest.fixture()
def no_network():
    """활성화 시 socket.socket 생성을 차단한다.

    이 픽스처를 요청하는 테스트에서 TCP/UDP 연결 시도가 발생하면
    RuntimeError("Network access forbidden in offline test")가 발생한다.

    사용 예::

        def test_something_offline(no_network):
            # 이 블록 안에서 소켓 생성 시도 시 즉시 실패
            result = pure_function()
            assert result == expected
    """

    original_socket = socket.socket

    def _blocked_socket(*args: Any, **kwargs: Any) -> None:  # type: ignore[return]
        raise RuntimeError(
            "Network access forbidden in offline test. "
            "If this module makes a network call, it violates F20/F21."
        )

    with patch.object(socket, "socket", side_effect=_blocked_socket):
        yield


# ── kompound_snapshot 공용 fixture (T-2, arch §9.3 / spec F13) ──────────────
#
# `fake_kompound_env(tmp_path)`는 T-3~T-11(코어 12모듈)이 공유하는 **단일**
# 오프라인 fixture다. 여기서만 정의한다 — 다른 태스크는 이 fixture를 재사용만
# 하고 새로 정의하지 않는다(`grep -c "^def fake_kompound_env" tests/conftest.py`
# == 1 이 태스크 완료 조건).
#
# 반환 스키마 (계약 — config.py의 `resolve_config()`이 이 스키마로 수렴해야
# 한다, arch §6.1 JSON 스키마 확정값과 동일):
#   {
#     "kompound": Path,   # git init + 초기 커밋된 가짜 kompound 저장소 루트
#     "workspace": Path,  # 가짜 SDD 워크스페이스(스캔 루트) 루트
#     "config": {
#       "schema_version": 1,
#       "kompound_repo": str,       # == str(kompound)
#       "scan_root": str,          # == str(workspace)
#       "max_anchor_depth": 5,
#       "state_max_age_hours": 24,
#       "prefix_map": {"<repo dir name>": "<prefix>", ...},
#     },
#   }

def _git(*args: str, cwd: Path) -> None:
    """`cwd`에서 git을 조용히 실행한다(로컬 identity 강제, 전역 설정 무시).

    실패 시 CalledProcessError를 그대로 전파한다 — fixture 구성 실패는
    테스트 자체를 실패시켜야 하므로 여기서는 fail-safe를 적용하지 않는다
    (패키지 본체의 fail-safe 규약과는 무관한 테스트 인프라).
    """
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=fixture@example.invalid",
            "-c",
            "user.name=fake-kompound-env",
            "-c",
            "commit.gpgsign=false",
            *args,
        ],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


# registry 골든 텍스트 — heterogeneous 3형상(§6.3.2: (a) 7열 · (b) 6열 · (c) 8열
# 통합표) + 갱신 대상 카운트 문장 2종(§6.3.3: "현재 상태" 첫 문장, "관련 문서"의
# raw 총계) + 날짜 박힌 불변 스냅샷 문장 1종을 실제
# `marvelous_kompound/wiki/sdd-spec-registry.md`의 형상을 그대로 축약 재현한다.
# raw 6개 = snapshot_set_rule(§6.3.1)을 만족하는 문서만 센 값이다 — 경계 케이스
# 파일(`notaproject-standalone-topic-ui.md`, 아래 참조)은 포함하지 않는다.
_FAKE_REGISTRY_TEXT = """\
<!-- AGENT: do not Edit/Write this file directly. This wiki page is a derived registry of raw/ SDD snapshots. To add/refresh entries, copy the source docs into raw/<project>-<feature>-{spec,arch,ui,api,context,result}.md and re-run the SDD-spec ingest, then update this page. Direct content edits will drift from raw/. index.md / log.md remain operationally maintained. -->

# sdd-spec-registry (fixture)

이 문서는 `tests/conftest.py`의 `fake_kompound_env`가 생성하는 테스트 전용
축약 registry다. 실제 `marvelous_kompound/wiki/sdd-spec-registry.md`가 아니다.

## 현재 상태

3 feature · raw 6개(spec 3 · arch 2 · result 1 · api 0 · ui 0 · context 0). 범례: ✓=있음, —=산출물 없음.

### acme-widget (형상 (a) — 7열, `기타` 열 포함)

| feature | spec | arch | 기타 | result | 기존 위키 | home repo |
|---------|:--:|:--:|:--:|:--:|------|-----------|
| widget-onboarding | [✓](../raw/acme-widget-onboarding-spec.md) | [✓](../raw/acme-widget-onboarding-arch.md) | — | — | — | acme-widget |

### beta-service (형상 (b) — 6열, `기타` 열 없음)

| feature | spec | arch | result | 기존 위키 | home repo |
|---------|:--:|:--:|:--:|------|-----------|
| launch-flow | [✓](../raw/beta-launch-flow-spec.md) | [✓](../raw/beta-launch-flow-arch.md) | [✓](../raw/beta-launch-flow-result.md) | — | beta-service |

### 기타 프로젝트 (형상 (c) — `프로젝트` 열이 선행하는 8열 통합표)

| 프로젝트 | feature | spec | arch | 기타 | result | 기존 위키 | home repo |
|---|---|:--:|:--:|:--:|:--:|------|-----------|
| gamma-tool | metrics | [✓](../raw/gamma-metrics-spec.md) | — | — | — | — | gamma-tool |

**2026-07-01 재스냅샷**: 3 feature · raw 6개. 직전 스냅샷(2026-06-01)은 1 feature · raw 2개였다.

## 결정과 근거

- 이 fixture는 테스트 전용이며 실제 kompound `raw/`·프로젝트와 무관하다.

## 관련 문서
- raw: `raw/<project>-<feature>-<kind>.md` 6개 (위 표 링크)
"""

_FAKE_INDEX_TEXT = """\
# Wiki Index (fixture)

## Entries

- [sdd-spec-registry](sdd-spec-registry.md) — 테스트 전용 축약 registry (fake_kompound_env)

## 최근 변경

- 2026-07-01 [bulk-ingest] fake_kompound_env 초기 시드 — 3 feature · raw 6개

## 미해결 모순

(없음 — fixture 전용)
"""

_FAKE_LOG_TEXT = (
    "2026-07-01 [bulk-ingest] fake_kompound_env 초기 시드 — 테스트 전용, "
    "실제 kompound 아님\n"
)

# §6.3.1 경계 케이스: 프리픽스가 등록되지 않은("notaproject"는 아래 prefix_map
# 값 집합 {"acme","beta","gamma"} 밖) 채로 kind 접미사(`-ui`)로 끝나는 raw
# 파일 — 실측 5건(clocv-wasm-api-expansion-spec 등)의 축약판. verify.py의
# `snapshot_set_rule`이 이 파일을 스냅샷 집합에서 제외해야 한다(raw 총계
# 6개에 포함되지 않음).
_FAKE_BOUNDARY_RAW_NAME = "notaproject-standalone-topic-ui.md"
_FAKE_BOUNDARY_RAW_TEXT = (
    "# standalone topic\n\n"
    "사람이 독립적으로 `/ingest`한 주제 문서. 파일명이 우연히 kind 접미사"
    "(`-ui`)로 끝나지만 프리픽스가 매핑돼 있지 않으므로 SDD 스냅샷 집합"
    "(snapshot_set_rule, arch §6.3.1) 밖이다.\n"
)

_FAKE_RAW_DOCS = {
    "acme-widget-onboarding-spec.md": "# widget-onboarding spec (fixture)\n",
    "acme-widget-onboarding-arch.md": "# widget-onboarding arch (fixture)\n",
    "beta-launch-flow-spec.md": "# launch-flow spec (fixture)\n",
    "beta-launch-flow-arch.md": "# launch-flow arch (fixture)\n",
    "beta-launch-flow-result.md": "# launch-flow result (fixture)\n",
    "gamma-metrics-spec.md": "# metrics spec (fixture)\n",
    _FAKE_BOUNDARY_RAW_NAME: _FAKE_BOUNDARY_RAW_TEXT,
}

# workspace 스코프: 스캔 루트 아래 홈 repo 트리 + 워크트리 전용 문서 케이스.
# repo dir 이름(`acme-widget`)은 config["prefix_map"]의 키와 일치해야 한다
# (naming.py의 repo_dir → prefix 조회, arch §5.4.2/§5.4.3의 입력 계약).
_FAKE_WORKSPACE_REPO = "acme-widget"
_FAKE_WORKSPACE_WORKTREE = "widget-onboarding-wt"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture()
def fake_kompound_env(tmp_path: Path) -> Dict[str, Any]:
    """오프라인 kompound + workspace + config 계약 fixture (arch §9.3, spec F13).

    `tmp_path` 아래에 다음을 만들고 ``{"kompound": Path, "workspace": Path,
    "config": dict}``를 반환한다:

    - ``fake_kompound/``: ``git init`` + 초기 커밋된 가짜 kompound. ``raw/``,
      ``wiki/{sdd-spec-registry,index,log}.md``. registry는 heterogeneous
      표 3형상 + 갱신 대상 카운트 문장 2종 + 날짜 박힌 불변 문장을 포함한다
      (§6.3.2·§6.3.3). ``raw/``에는 §6.3.1 경계 케이스(미등록 프리픽스 +
      kind 접미사)가 1건 심어져 있다.
    - ``fake_workspace/<repo>/docs/sdd/{spec,design/arch,result}/``,
      ``<repo>/worktrees/<wt>/docs/sdd/spec/``(워크트리 전용 문서 케이스).
    - ``config``: T-3 ``config.resolve_config()``가 최종 수렴해야 하는
      스키마(§6.1)를 오버라이드 지점으로 미리 고정한 dict. ``kompound_repo``
      /``scan_root``는 이 fixture가 만든 두 디렉토리의 절대경로 문자열이다.

    kompound는 커밋 직후이므로 ``git status --porcelain``이 비어있다(clean)
    — F9(dirty/diverge)·F8(검증 게이트) 케이스는 이 clean 상태 위에 각
    테스트가 결함을 주입해 시뮬레이션한다. 네트워크 호출 없음(F13).
    """
    kompound = tmp_path / "fake_kompound"
    workspace = tmp_path / "fake_workspace"

    # ── fake_kompound: raw/ + wiki/{registry,index,log} ────────────────────
    for name, text in _FAKE_RAW_DOCS.items():
        _write(kompound / "raw" / name, text)
    _write(kompound / "wiki" / "sdd-spec-registry.md", _FAKE_REGISTRY_TEXT)
    _write(kompound / "wiki" / "index.md", _FAKE_INDEX_TEXT)
    _write(kompound / "wiki" / "log.md", _FAKE_LOG_TEXT)

    _git("init", "-q", cwd=kompound)
    _git("add", "-A", cwd=kompound)
    _git("commit", "-q", "-m", "fake_kompound_env: initial seed", cwd=kompound)

    # ── fake_workspace: <repo>/docs/sdd/{spec,design/arch,result} +
    #    <repo>/worktrees/<wt>/docs/sdd/spec (워크트리 전용 문서 케이스) ────
    repo_root = workspace / _FAKE_WORKSPACE_REPO
    _write(
        repo_root / "docs" / "sdd" / "spec" / "2026-07-01-widget-onboarding-spec.md",
        "# widget-onboarding spec (workspace fixture)\n",
    )
    _write(
        repo_root
        / "docs"
        / "sdd"
        / "design"
        / "arch"
        / "2026-07-01-widget-onboarding-arch.md",
        "# widget-onboarding arch (workspace fixture)\n",
    )
    _write(
        repo_root / "docs" / "sdd" / "result" / "2026-07-01-widget-onboarding-result.md",
        "# widget-onboarding result (workspace fixture)\n",
    )
    _write(
        repo_root
        / "worktrees"
        / _FAKE_WORKSPACE_WORKTREE
        / "docs"
        / "sdd"
        / "spec"
        / "2026-07-01-widget-onboarding-wt-only-spec.md",
        "# widget-onboarding wt-only spec (worktree 전용 문서 케이스)\n",
    )

    config: Dict[str, Any] = {
        "schema_version": 1,
        "kompound_repo": str(kompound),
        "scan_root": str(workspace),
        "max_anchor_depth": 5,
        "state_max_age_hours": 24,
        "prefix_map": {
            "acme-widget": "acme",
            "beta-service": "beta",
            "gamma-tool": "gamma",
        },
    }

    return {"kompound": kompound, "workspace": workspace, "config": config}
