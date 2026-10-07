"""tests/test_kompound_snapshot_vault.py — v2 볼트 레이아웃 계약(`vault.py`) 단위 테스트.

2026-10-07 kompound v1(flat `raw/`+`wiki/`) → v2(`moon_kompound`, Obsidian
cmds-llm-wiki 레이아웃) 이관에 맞춰 추가된 모듈이다. 경로 상수·도메인 매핑·
기존 raw 색인(slug/legacySlug)·raw-source 렌더링과 `## Original Content` 본문
추출/교체의 왕복(roundtrip)을 검증한다. 전부 `tmp_path` 기반.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hooks.lib.kompound_snapshot import vault

pytestmark = pytest.mark.offline


def test_layout_constants_match_v2_vault() -> None:
    assert vault.RAW_ROOT.as_posix() == "10. Raw Sources"
    assert vault.SPECS_DIR.as_posix() == "10. Raw Sources/17. Specs"
    assert vault.REGISTRY_RELATIVE.as_posix() == "20. Wiki/24. Maps/SDD Spec Registry.md"
    assert vault.INDEX_RELATIVE.as_posix() == "index.md"
    assert vault.LOG_RELATIVE.as_posix() == "log.md"
    assert len(vault.DOMAINS) == 10 and "CEF & WebView" in vault.DOMAINS


@pytest.mark.parametrize(
    "name, expected",
    [
        ("2026-07-28-harness-code-mapper-spec.md", "harness-code-mapper-spec"),
        ("2026-07-28-harness-code-mapper-spec", "harness-code-mapper-spec"),
        ("some/dir/2026-07-28-x-y-arch.md", "x-y-arch"),
        ("harness-code-mapper-spec.md", "harness-code-mapper-spec"),
    ],
)
def test_slug_of(name: str, expected: str) -> None:
    assert vault.slug_of(name) == expected


def test_domain_for_project_defaults_override_and_fallback() -> None:
    assert vault.domain_for_project("marvelous") == "Marvelous App"
    assert vault.domain_for_project("clofab") == "CLOFab"
    for p in ("graphify", "autofix", "crashai", "codegraph", "aireview", "harness", "rein", "slack"):
        assert vault.domain_for_project(p) == "AI Harness"
    assert vault.domain_for_project("unknown-prefix") == vault.FALLBACK_DOMAIN
    assert vault.domain_for_project("marvelous", {"marvelous": "Pattern API"}) == "Pattern API"
    # 볼트 10종 밖 값은 무시하고 기본으로 떨어진다
    assert vault.domain_for_project("marvelous", {"marvelous": "Nope"}) == "Marvelous App"


@pytest.mark.parametrize(
    "domain, tag",
    [
        ("AI Harness", "ai-harness"),
        ("CEF & WebView", "cef-webview"),
        ("WebGPU & WASM", "webgpu-wasm"),
        ("Marvelous App", "marvelous-app"),
        ("Org & Process", "org-process"),
        ("CLOFab", "clofab"),
    ],
)
def test_domain_tag_matches_vault_convention(domain: str, tag: str) -> None:
    assert vault.domain_tag(domain) == tag


def test_split_source_doc_lifts_h1_and_normalizes_trailing_newlines() -> None:
    title, body = vault.split_source_doc("\n# 제목 Spec\n\n## 개요\n- a\n\n\n")
    assert title == "제목 Spec"
    assert body == "## 개요\n- a"

    title2, body2 = vault.split_source_doc("no heading\nline2\n")
    assert title2 is None
    assert body2 == "no heading\nline2"


def _render(body_source: str, **kw) -> str:
    params = dict(
        slug="harness-demo-feature-spec",
        project="harness",
        feature="demo-feature",
        kind="spec",
        domain="AI Harness",
        date="2026-10-07",
        source_text=body_source,
        source_label="moon-harness/docs/sdd/spec/2026-10-07-demo-feature.md",
        md5="abc",
    )
    params.update(kw)
    return vault.render_raw(**params)


def test_render_raw_shape_and_frontmatter() -> None:
    text = _render("# Demo Feature Spec\n\n## 개요\n- 본문\n")
    lines = text.splitlines()
    assert lines[0] == "---"
    assert "type: raw-source" in lines
    assert '  - "Demo Feature Spec"' in lines
    assert '  - "harness-demo-feature-spec"' in lines
    assert 'description: "SDD spec snapshot of harness demo-feature."' in lines
    assert "model: unknown" in lines and "effort: default" in lines
    for key in ("date created", "date modified", "date ingested"):
        assert f"{key}: 2026-10-07" in lines
    assert '  - "ai-harness"' in lines
    assert 'category: "Specs"' in lines
    assert 'domain: "AI Harness"' in lines
    assert 'collectionPurpose: "AI 하네스·자동화 — SDD spec 스냅샷 보존"' in lines
    assert "status: ingested" in lines
    assert "legacySlug" not in text  # 신규 raw는 legacySlug가 없다
    assert "\n# Demo Feature Spec\n\n> [!info] Source\n> 원본 출처: moon-harness/docs/sdd/spec/" in text
    assert text.index("## Original Content") < text.index("## Metadata")
    assert vault.extract_original_content(text) == "## 개요\n- 본문"


def test_render_raw_marvelous_purpose_axis() -> None:
    text = _render("# x\n\ny\n", domain="Marvelous App", project="marvelous")
    assert 'collectionPurpose: "Marvelous 개발 — SDD spec 스냅샷 보존"' in text
    assert '  - "marvelous-app"' in text


@pytest.mark.parametrize(
    "body",
    [
        "plain",
        "ends with rule\n\n---",
        "has ## Metadata inside\n\n## Metadata\n\nnot the real one\n\nmore",
        "trailing spaces line   ",
    ],
)
def test_original_content_roundtrip(body: str) -> None:
    text = _render(f"# T\n\n{body}\n")
    _, expected = vault.split_source_doc(f"# T\n\n{body}\n")
    assert vault.extract_original_content(text) == expected


def test_replace_original_content_only_touches_body_and_date_modified() -> None:
    text = _render("# T\n\nold body\n")
    out = vault.replace_original_content(text, "new body\nline2", date_modified="2026-12-01")
    assert out is not None
    assert vault.extract_original_content(out) == "new body\nline2"
    assert "date modified: 2026-12-01" in out
    assert "date created: 2026-10-07" in out
    assert out.split("## Metadata")[1] == text.split("## Metadata")[1]
    assert out.split("## Original Content")[0].replace("2026-12-01", "2026-10-07") == text.split("## Original Content")[0]


def test_replace_original_content_returns_none_without_structure() -> None:
    assert vault.replace_original_content("# no structure\n\nbody\n", "x") is None
    assert vault.extract_original_content("# no structure\n") is None


def test_build_raw_index_finds_by_dated_name_anywhere_and_by_legacy_slug(tmp_path: Path) -> None:
    root = tmp_path / "10. Raw Sources"
    a = root / "19. Decisions & Lessons" / "CLOFab" / "2026-01-01-clofab-x-spec.md"
    b = root / "17. Specs" / "AI Harness" / "2026-02-02-renamed.md"
    c = root / "17. Specs" / "AI Harness" / "undated-harness-y-spec.md"
    hidden = root / ".obsidian" / "2026-01-01-harness-hidden-spec.md"
    for p in (a, b, c, hidden):
        p.parent.mkdir(parents=True, exist_ok=True)
    a.write_text("x", encoding="utf-8")
    b.write_text('---\ntype: raw-source\nlegacySlug: harness-legacy-z-spec\n---\n', encoding="utf-8")
    c.write_text("x", encoding="utf-8")
    hidden.write_text("x", encoding="utf-8")

    index = vault.build_raw_index(tmp_path)

    assert index["clofab-x-spec"] == a
    assert index["harness-legacy-z-spec"] == b
    assert "undated-harness-y-spec" not in index  # 날짜 접두 없는 파일은 규칙 밖
    assert "harness-hidden-spec" not in index  # dot-dir 제외
    assert vault.find_raw(tmp_path, "clofab-x-spec") == a
    assert vault.find_raw(tmp_path, "nope") is None


def test_build_raw_index_filename_match_wins_over_legacy_slug(tmp_path: Path) -> None:
    root = tmp_path / "10. Raw Sources" / "17. Specs" / "AI Harness"
    root.mkdir(parents=True)
    by_name = root / "2026-03-03-harness-q-spec.md"
    by_legacy = root / "2026-01-01-other.md"
    by_name.write_text("x", encoding="utf-8")
    by_legacy.write_text("---\nlegacySlug: harness-q-spec\n---\n", encoding="utf-8")

    assert vault.build_raw_index(tmp_path)["harness-q-spec"] == by_name


def test_new_raw_path(tmp_path: Path) -> None:
    p = vault.new_raw_path(tmp_path, "CEF & WebView", "2026-10-07", "marvelous-x-spec")
    assert p == tmp_path / "10. Raw Sources" / "17. Specs" / "CEF & WebView" / "2026-10-07-marvelous-x-spec.md"


def test_is_vault_and_is_v1_layout(tmp_path: Path) -> None:
    v2 = tmp_path / "v2"
    (v2 / ".git").mkdir(parents=True)
    (v2 / "10. Raw Sources").mkdir()
    (v2 / "20. Wiki").mkdir()
    (v2 / "index.md").write_text("", encoding="utf-8")
    (v2 / "log.md").write_text("", encoding="utf-8")
    v1 = tmp_path / "v1"
    (v1 / ".git").mkdir(parents=True)
    (v1 / "raw").mkdir()
    (v1 / "wiki").mkdir()
    (v1 / "wiki" / "index.md").write_text("", encoding="utf-8")

    assert vault.is_vault(v2) is True
    assert vault.is_vault(v1) is False
    assert vault.is_v1_layout(v1) is True
    assert vault.is_v1_layout(v2) is False
    assert vault.is_vault(tmp_path / "missing") is False
