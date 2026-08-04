"""tests/test_kompound_snapshot_naming.py — T-4 (F4/F12 네이밍) 검증.

arch: docs/sdd/design/arch/2026-07-29-kompound-snapshot-hook.md §5.4.3
spec: docs/sdd/spec/2026-07-29-kompound-snapshot-hook.md F4 · F12

`naming.py`는 기본 프리픽스 매핑(spec F4의 10종)을 자체 정의하지 않는다 —
이 파일은 그 매핑을 **테스트 전용 로컬 dict**로 구성해 순수 함수
`name_document`/`resolve_prefix`에 인자로 주입한다(T-3 `config.py`의 실제
`resolve_config()` 출력과는 별개 — 계약만 공유한다).
"""

from __future__ import annotations

from typing import Optional

import pytest

from hooks.lib.kompound_snapshot.naming import name_document, resolve_prefix

# spec F4 기본 매핑(테스트 전용 재현) — 10개 distinct 프리픽스.
_PREFIX_MAP = {
    "Marvelous": "marvelous",
    "Marvelous_dev": "marvelous",
    "Marvelous_feature": "marvelous",
    "Marvelous_code_review": "marvelous",
    "auto-fix-base": "marvelous",
    "CLOFab_Web": "clofab",
    "Marvelous_graphify": "graphify",
    "auto-fix-orchestrator": "autofix",
    "crash-ai-analysis": "crashai",
    "codegraph-clo": "codegraph",
    "ai-code-reviewer-action": "aireview",
    "moon-harness": "harness",
    "rein": "rein",
    "claude-slack-channel": "slack",
}


def _record(repo_dir: str, path: str, kind: str) -> dict:
    return {"repo_dir": repo_dir, "path": path, "kind": kind}


# ── 10개(이상) 프리픽스 각각 ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    "repo_dir,expected_prefix",
    [
        ("Marvelous", "marvelous"),
        ("Marvelous_dev", "marvelous"),
        ("Marvelous_feature", "marvelous"),
        ("Marvelous_code_review", "marvelous"),
        ("auto-fix-base", "marvelous"),
        ("CLOFab_Web", "clofab"),
        ("Marvelous_graphify", "graphify"),
        ("auto-fix-orchestrator", "autofix"),
        ("crash-ai-analysis", "crashai"),
        ("codegraph-clo", "codegraph"),
        ("ai-code-reviewer-action", "aireview"),
        ("moon-harness", "harness"),
        ("rein", "rein"),
        ("claude-slack-channel", "slack"),
    ],
)
def test_name_document_covers_all_default_prefixes(repo_dir: str, expected_prefix: str) -> None:
    record = _record(repo_dir, f"/x/{repo_dir}/docs/sdd/spec/2026-07-29-widget-spec.md", "spec")
    result = name_document(record, _PREFIX_MAP)
    assert result == {"raw_name": f"raw/{expected_prefix}-widget-spec.md"}


# ── 날짜 프리픽스 · 접미사 제거 ──────────────────────────────────────────────


def test_date_prefix_and_suffix_are_stripped() -> None:
    # 접미사 제거 대상은 spec F4가 명시한 -spec/-dev/-result뿐이다(legacy
    # `specs/`·`development/` 디렉토리 관례 — 실측: Marvelous_code_review의
    # `specs/2026-03-17-strain-map-auto-update-spec.md` 등). `-arch`/`-ui`
    # 등은 원본 파일명에 붙지 않는 관례이므로 제거 대상이 아니다.
    record = _record(
        "moon-harness",
        "/x/moon-harness/docs/sdd/specs/2026-07-29-kompound-snapshot-hook-spec.md",
        "spec",
    )
    result = name_document(record, _PREFIX_MAP)
    assert result == {"raw_name": "raw/harness-kompound-snapshot-hook-spec.md"}


def test_kind_suffix_other_than_spec_dev_result_is_not_stripped() -> None:
    # F4는 -spec/-dev/-result만 접미사 제거 대상으로 명시한다. arch kind
    # 파일명에 우연히 "-arch"가 붙어 있어도(관례 밖 입력) 제거하지 않는다.
    record = _record(
        "moon-harness",
        "/x/moon-harness/docs/sdd/design/arch/2026-07-29-something-arch.md",
        "arch",
    )
    result = name_document(record, _PREFIX_MAP)
    assert result == {"raw_name": "raw/harness-something-arch-arch.md"}


def test_dev_suffix_is_stripped() -> None:
    record = _record("rein", "/x/rein/docs/sdd/development/2026-01-01-feature-dev.md", "arch")
    result = name_document(record, _PREFIX_MAP)
    assert result == {"raw_name": "raw/rein-feature-arch.md"}


def test_no_date_prefix_present_is_a_noop() -> None:
    record = _record("moon-harness", "/x/moon-harness/docs/sdd/spec/plain-name-spec.md", "spec")
    result = name_document(record, _PREFIX_MAP)
    assert result == {"raw_name": "raw/harness-plain-name-spec.md"}


# ── 프리픽스 중복 접기 ───────────────────────────────────────────────────────


def test_duplicate_project_prefix_is_folded() -> None:
    # codegraph-codegraph-internal-mcp-result → codegraph-internal-mcp-result
    record = _record(
        "codegraph-clo",
        "/x/codegraph-clo/docs/sdd/result/codegraph-internal-mcp-result.md",
        "result",
    )
    result = name_document(record, _PREFIX_MAP)
    assert result == {"raw_name": "raw/codegraph-internal-mcp-result.md"}


def test_no_duplicate_prefix_is_unaffected() -> None:
    record = _record(
        "codegraph-clo",
        "/x/codegraph-clo/docs/sdd/result/unrelated-feature-result.md",
        "result",
    )
    result = name_document(record, _PREFIX_MAP)
    assert result == {"raw_name": "raw/codegraph-unrelated-feature-result.md"}


# ── 미등록 repo → unmapped (F12) ─────────────────────────────────────────────


def test_unmapped_repo_returns_unmapped_signal_not_exception() -> None:
    record = _record(
        "pptx-template", "/x/pptx-template/Docs/sdd guide/notes-spec.md", "spec"
    )
    result = name_document(record, _PREFIX_MAP)
    assert result == {"unmapped": "pptx-template"}
    assert "raw_name" not in result


def test_explicit_null_prefix_value_is_treated_as_unmapped() -> None:
    prefix_map: dict = dict(_PREFIX_MAP)
    prefix_map["deprecated-repo"] = None
    record = _record("deprecated-repo", "/x/deprecated-repo/docs/sdd/spec/old-spec.md", "spec")
    result = name_document(record, prefix_map)
    assert result == {"unmapped": "deprecated-repo"}


def test_unmapped_and_raw_name_shapes_are_mutually_exclusive() -> None:
    """pending(=raw_name 성공)과 unmapped는 배타적 집합이어야 한다(arch J-11)."""
    mapped = name_document(_record("rein", "/x/rein/docs/sdd/spec/a-spec.md", "spec"), _PREFIX_MAP)
    unmapped = name_document(
        _record("nope", "/x/nope/docs/sdd/spec/b-spec.md", "spec"), _PREFIX_MAP
    )
    assert set(mapped.keys()) == {"raw_name"}
    assert set(unmapped.keys()) == {"unmapped"}


# ── resolve_prefix — 완화 재조회 (arch §5.4.2 규칙5) ─────────────────────────


def test_resolve_prefix_primary_lookup_by_directory_name() -> None:
    assert resolve_prefix("/some/where/moon-harness", _PREFIX_MAP) == "harness"


def test_resolve_prefix_falls_back_to_first_segment_under_scan_root() -> None:
    prefix_map = {"gamma-tool": "gamma"}
    repo_dir = "/scan/root/gamma-tool/nested/unexpected-dirname"
    result = resolve_prefix(repo_dir, prefix_map, scan_root="/scan/root")
    assert result == "gamma"


def test_resolve_prefix_falls_back_to_two_segments_under_scan_root() -> None:
    prefix_map = {"CLOFab_Web/clofab": "clofab"}
    repo_dir = "/scan/root/CLOFab_Web/clofab"
    # 1차 조회(디렉토리 이름 "clofab")는 실패하므로 완화 재조회로 넘어간다.
    result = resolve_prefix(repo_dir, prefix_map, scan_root="/scan/root")
    assert result == "clofab"


def test_resolve_prefix_returns_none_without_scan_root_fallback() -> None:
    assert resolve_prefix("/x/unknown-repo", _PREFIX_MAP) is None


def test_resolve_prefix_returns_none_when_all_fallbacks_exhausted() -> None:
    result: Optional[str] = resolve_prefix(
        "/scan/root/totally-unknown", _PREFIX_MAP, scan_root="/scan/root"
    )
    assert result is None
