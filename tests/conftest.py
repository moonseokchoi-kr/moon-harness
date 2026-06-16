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
