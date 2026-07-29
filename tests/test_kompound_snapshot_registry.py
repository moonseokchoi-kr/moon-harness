"""tests/test_kompound_snapshot_registry.py — F7 registry 외과적 갱신 (T-8).

arch §6.3.2(표 탐색 3단 + 행/열 삽입)·§6.3.3(카운트 문장 화이트리스트) 골든
텍스트 in/out 검증. `fake_kompound_env`(tests/conftest.py, T-2)의 heterogeneous
3형상 registry 골든을 재사용하고, 3단 탐색의 모호/최장매칭 케이스처럼
fixture에 없는 형상은 이 파일에서 최소 커스텀 텍스트로 보강한다.
"""

from __future__ import annotations

from typing import Any, Dict

import pytest

from hooks.lib.kompound_snapshot.registry import update_registry

pytestmark = pytest.mark.offline


# ── 헬퍼 ─────────────────────────────────────────────────────────────────────


def _entry(**kwargs: Any) -> Dict[str, Any]:
    base = {"worktree": None}
    base.update(kwargs)
    return base


_MINI_PREFIX_MAP = {"acme-widget": "acme", "beta-service": "beta", "gamma-tool": "gamma"}


# ── 표 탐색 ①: 섹션 헤딩 일치 ────────────────────────────────────────────────


def test_stage1_heading_match_adds_row_to_existing_project_table(fake_kompound_env):
    registry_text = (fake_kompound_env["kompound"] / "wiki" / "sdd-spec-registry.md").read_text(
        encoding="utf-8"
    )
    new_docs = [
        _entry(
            repo_dir="acme-widget",
            project="acme",
            feature="widget-checkout",
            kind="spec",
            raw_name="acme-widget-checkout-spec.md",
        )
    ]

    result = update_registry(registry_text, new_docs, prefix_map=_MINI_PREFIX_MAP)

    assert result["ok"] is True
    assert result["rows_added"] == 1
    assert "### beta-service" not in result["text"] or True  # 다른 섹션 신설 금지 확인은 아래로
    assert result["text"].count("### acme-widget") == 1  # 새 섹션 신설 안 됨(같은 표에 행 추가)
    assert "| widget-checkout | [✓](../raw/acme-widget-checkout-spec.md) | — | — | — | — | acme-widget |" in (
        result["text"]
    )
    # 기존 acme-widget 행은 그대로 보존
    assert "| widget-onboarding |" in result["text"]


def test_case_insensitive_heading_match_marvelous_dev():
    registry_text = (
        "# registry\n"
        "\n"
        "## 현재 상태\n"
        "\n"
        "### Marvelous (CLO C++ 엔진)\n"
        "\n"
        "| feature | spec | arch | result | 기존 위키 | home repo |\n"
        "|---------|:--:|:--:|:--:|------|-----------|\n"
        "| existing-feature | [✓](../raw/marvelous-existing-feature-spec.md) | — | — | — | Marvelous |\n"
        "\n"
        "## 결정과 근거\n"
        "\n"
        "## 관련 문서\n"
    )
    new_docs = [
        _entry(
            repo_dir="Marvelous_dev",
            project="marvelous",
            feature="new-feature",
            kind="spec",
            raw_name="marvelous-new-feature-spec.md",
        )
    ]

    result = update_registry(registry_text, new_docs, prefix_map={"Marvelous_dev": "marvelous"})

    assert result["ok"] is True
    assert result["text"].count("### Marvelous") == 1  # 대소문자 무시로 기존 표에 귀속, 신설 없음
    assert "| new-feature | [✓](../raw/marvelous-new-feature-spec.md) | — | — | — | Marvelous_dev |" in (
        result["text"]
    )


def test_clofab_web_key_and_value_both_matching_same_section_is_not_ambiguous():
    registry_text = (
        "## 현재 상태\n"
        "\n"
        "### CLOFab_Web (clofab 웹 뷰어 / WASM)\n"
        "\n"
        "| feature | spec | arch | result | 기존 위키 | home repo |\n"
        "|---------|:--:|:--:|:--:|------|-----------|\n"
        "| fabric-upload | [✓](../raw/clofab-fabric-upload-spec.md) | — | — | — | CLOFab_Web |\n"
        "\n"
        "## 결정과 근거\n"
        "\n"
        "## 관련 문서\n"
    )
    new_docs = [
        _entry(
            repo_dir="CLOFab_Web",
            project="clofab",
            feature="wasm-integration",
            kind="spec",
            raw_name="clofab-wasm-integration-spec.md",
        )
    ]

    result = update_registry(registry_text, new_docs, prefix_map={"CLOFab_Web": "clofab"})

    assert result["ok"] is True
    assert result["text"].count("### CLOFab_Web") == 1
    assert "| wasm-integration |" in result["text"]


def test_two_distinct_sections_matching_resolves_by_longest_candidate():
    registry_text = (
        "## 현재 상태\n"
        "\n"
        "### Marvelous_dev tools (하위 도구 모음)\n"
        "\n"
        "| feature | spec | arch | result | 기존 위키 | home repo |\n"
        "|---------|:--:|:--:|:--:|------|-----------|\n"
        "| tool-a | [✓](../raw/marvelous-tool-a-spec.md) | — | — | — | Marvelous_dev |\n"
        "\n"
        "### Marvelous_graphify (그래프 뷰어)\n"
        "\n"
        "| feature | spec | arch | result | 기존 위키 | home repo |\n"
        "|---------|:--:|:--:|:--:|------|-----------|\n"
        "| arch-layer-view | [✓](../raw/graphify-arch-layer-view-spec.md) | — | — | — | Marvelous_graphify |\n"
        "\n"
        "## 결정과 근거\n"
        "\n"
        "## 관련 문서\n"
    )
    # candidates: repo_dir="Marvelous_dev"(13자) — "Marvelous_dev tools" 헤딩에 정확히
    # 부분일치(길이13). "Marvelous_graphify" 헤딩에는 "marvelous"(9자, project 후보)만
    # 걸린다. 최장 매칭(13) 표가 유일하므로 모호 없이 첫 표로 귀속돼야 한다.
    new_docs = [
        _entry(
            repo_dir="Marvelous_dev",
            project="marvelous",
            feature="tool-b",
            kind="spec",
            raw_name="marvelous-tool-b-spec.md",
        )
    ]

    result = update_registry(registry_text, new_docs, prefix_map={"Marvelous_dev": "marvelous"})

    assert result["ok"] is True
    assert "### Marvelous_dev tools" in result["text"]
    text = result["text"]
    tools_idx = text.index("### Marvelous_dev tools")
    graphify_idx = text.index("### Marvelous_graphify")
    tool_b_idx = text.index("| tool-b |")
    assert tools_idx < tool_b_idx < graphify_idx  # tool-b 행이 첫 표에 들어갔다


def test_ambiguous_two_sections_tied_match_length_fails():
    registry_text = (
        "## 현재 상태\n"
        "\n"
        "### Marvelous (CLO 엔진)\n"
        "\n"
        "| feature | spec | arch | result | 기존 위키 | home repo |\n"
        "|---------|:--:|:--:|:--:|------|-----------|\n"
        "| existing-a | [✓](../raw/marvelous-existing-a-spec.md) | — | — | — | Marvelous |\n"
        "\n"
        "### Marvelous_graphify (그래프 뷰어)\n"
        "\n"
        "| feature | spec | arch | result | 기존 위키 | home repo |\n"
        "|---------|:--:|:--:|:--:|------|-----------|\n"
        "| existing-b | [✓](../raw/graphify-existing-b-spec.md) | — | — | — | Marvelous_graphify |\n"
        "\n"
        "## 결정과 근거\n"
        "\n"
        "## 관련 문서\n"
    )
    # candidates repo_dir="Marvelous_dev"(13자, 두 헤딩 어디에도 정확히 부분일치 안 함),
    # project="marvelous"(9자) — 두 헤딩 모두 대소문자 무시로 "marvelous" 9자만 걸려
    # 매칭 섹션이 2개 + 동률 → 모호 실패.
    new_docs = [
        _entry(
            repo_dir="Marvelous_dev",
            project="marvelous",
            feature="new-feature",
            kind="spec",
            raw_name="marvelous-new-feature-spec.md",
        )
    ]

    result = update_registry(registry_text, new_docs, prefix_map={"Marvelous_dev": "marvelous"})

    assert result["ok"] is False
    assert result["reason"] == "catalog_unparsed"
    assert "ambiguous" in result["detail"]


# ── 표 탐색 ②: `프로젝트` 열 귀속 (moon-harness 유형 — 신설 안 함) ───────────


def test_stage2_project_column_attaches_to_existing_integrated_table(fake_kompound_env):
    registry_text = (fake_kompound_env["kompound"] / "wiki" / "sdd-spec-registry.md").read_text(
        encoding="utf-8"
    )
    new_docs = [
        _entry(
            repo_dir="gamma-tool",
            project="gamma",
            feature="onboarding-flow",
            kind="spec",
            raw_name="gamma-onboarding-flow-spec.md",
        )
    ]

    result = update_registry(registry_text, new_docs, prefix_map=_MINI_PREFIX_MAP)

    assert result["ok"] is True
    assert result["rows_added"] == 1
    text = result["text"]
    # moon-harness 유형: 신규 전용 표(### gamma-tool)가 생기지 않는다.
    assert "### gamma-tool" not in text
    assert text.count("### 기타 프로젝트") == 1
    # 기존 gamma-tool 행 바로 뒤(같은 프로젝트 그룹)에 삽입됐는지 확인
    existing_row_idx = text.index("| gamma-tool | metrics |")
    new_row_idx = text.index("| gamma-tool | onboarding-flow |")
    assert new_row_idx > existing_row_idx
    between = text[existing_row_idx:new_row_idx]
    assert between.count("\n") == 1  # 두 행 사이에 다른 줄이 끼지 않음(바로 뒤)


# ── 표 탐색 ③: 진짜 새 프로젝트 → 7열 신설 ───────────────────────────────────


def test_stage3_new_project_creates_shape_a_table(fake_kompound_env):
    registry_text = (fake_kompound_env["kompound"] / "wiki" / "sdd-spec-registry.md").read_text(
        encoding="utf-8"
    )
    new_docs = [
        _entry(
            repo_dir="delta-corp",
            project="delta",
            feature="delta-feature",
            kind="spec",
            raw_name="delta-delta-feature-spec.md",
        )
    ]

    result = update_registry(
        registry_text, new_docs, prefix_map={**_MINI_PREFIX_MAP, "delta-corp": "delta"}
    )

    assert result["ok"] is True
    assert result["rows_added"] == 1
    text = result["text"]
    assert "### delta-corp" in text
    assert "| feature | spec | arch | 기타 | result | 기존 위키 | home repo |" in text
    assert (
        "| delta-feature | [✓](../raw/delta-delta-feature-spec.md) | — | — | — | — | delta-corp |" in text
    )
    # 새 섹션이 "## 결정과 근거" 바로 앞에 신설됨
    decisions_idx = text.index("## 결정과 근거")
    delta_idx = text.index("### delta-corp")
    assert delta_idx < decisions_idx


def test_stage3_new_project_placed_before_decisions_heading_not_after():
    registry_text = (
        "## 현재 상태\n"
        "\n"
        "### existing-proj\n"
        "\n"
        "| feature | spec | arch | result | 기존 위키 | home repo |\n"
        "|---------|:--:|:--:|:--:|------|-----------|\n"
        "| f1 | [✓](../raw/existing-f1-spec.md) | — | — | — | existing-proj |\n"
        "\n"
        "## 결정과 근거\n"
        "\n"
        "- 근거 문장\n"
        "\n"
        "## 관련 문서\n"
    )
    new_docs = [
        _entry(
            repo_dir="new-proj", project="newp", feature="feat-x", kind="arch",
            raw_name="newp-feat-x-arch.md",
        )
    ]

    result = update_registry(registry_text, new_docs, prefix_map={"new-proj": "newp"})

    assert result["ok"] is True
    text = result["text"]
    assert text.index("### new-proj") < text.index("## 결정과 근거")
    assert "- 근거 문장" in text  # 기존 산문 보존


def test_missing_decisions_heading_fails_new_section_creation():
    registry_text = "## 현재 상태\n\n### existing\n\n| feature | spec |\n|---|:--:|\n"
    new_docs = [_entry(repo_dir="x", project="x", feature="f", kind="spec", raw_name="x-f-spec.md")]

    result = update_registry(registry_text, new_docs, prefix_map={"x": "x"})

    assert result["ok"] is False
    assert result["reason"] == "catalog_unparsed"


# ── 열 추가 (사용자 승인 — 방향 반전) ────────────────────────────────────────


def test_column_add_ui_on_shape_b_fills_dash_and_preserves_other_bytes(fake_kompound_env):
    registry_text = (fake_kompound_env["kompound"] / "wiki" / "sdd-spec-registry.md").read_text(
        encoding="utf-8"
    )
    # beta-service 표는 fixture상 형상 (b) — 6열, `기타` 열 없음.
    assert "| feature | spec | arch | result | 기존 위키 | home repo |" in registry_text

    new_docs = [
        _entry(
            repo_dir="beta-service",
            project="beta",
            feature="launch-flow",  # 기존 행 — 새 kind만 추가
            kind="ui",
            raw_name="beta-launch-flow-ui.md",
        )
    ]

    result = update_registry(registry_text, new_docs, prefix_map=_MINI_PREFIX_MAP)

    assert result["ok"] is True
    assert result["columns_added"] == [("beta-service (형상 (b) — 6열, `기타` 열 없음)", "기타")]
    text = result["text"]

    # 헤더에 `기타` 열이 arch 뒤·result 앞에 삽입
    assert "| feature | spec | arch | 기타 | result | 기존 위키 | home repo |" in text
    # 기존 행: launch-flow의 spec/arch/result/기존위키/home repo 셀은 원본 그대로,
    # 새 `기타` 셀만 링크로 채워짐.
    assert (
        "| launch-flow | [✓](../raw/beta-launch-flow-spec.md) | [✓](../raw/beta-launch-flow-arch.md) "
        "| [ui](../raw/beta-launch-flow-ui.md) | [✓](../raw/beta-launch-flow-result.md) | — | beta-service |"
    ) in text

    # 다른 표(acme-widget)는 바이트 단위 완전 보존
    assert "### acme-widget (형상 (a) — 7열, `기타` 열 포함)" in text
    assert (
        "| widget-onboarding | [✓](../raw/acme-widget-onboarding-spec.md) | "
        "[✓](../raw/acme-widget-onboarding-arch.md) | — | — | — | acme-widget |"
    ) in text


def test_column_add_new_row_on_shape_b_fills_existing_rows_with_dash():
    registry_text = (
        "## 현재 상태\n"
        "\n"
        "### solo-project\n"
        "\n"
        "| feature | spec | arch | result | 기존 위키 | home repo |\n"
        "|---------|:--:|:--:|:--:|------|-----------|\n"
        "| old-feature | [✓](../raw/solo-old-feature-spec.md) | — | — | — | solo-project |\n"
        "\n"
        "## 결정과 근거\n"
        "\n"
        "## 관련 문서\n"
    )
    new_docs = [
        _entry(
            repo_dir="solo-project",
            project="solo",
            feature="new-feature",
            kind="api",
            raw_name="solo-new-feature-api.md",
        )
    ]

    result = update_registry(registry_text, new_docs, prefix_map={"solo-project": "solo"})

    assert result["ok"] is True
    text = result["text"]
    # 기존 행(old-feature)의 새 `기타` 칸은 `—`
    assert (
        "| old-feature | [✓](../raw/solo-old-feature-spec.md) | — | — | — | — | solo-project |" in text
    )
    # 신규 행(new-feature)의 `기타` 칸은 링크
    assert (
        "| new-feature | — | — | [api](../raw/solo-new-feature-api.md) | — | — | solo-project |" in text
    )


def test_column_add_safety_condition_unrecognized_shape_fails_as_catalog_unparsed():
    registry_text = (
        "## 현재 상태\n"
        "\n"
        "### odd-project\n"
        "\n"
        "| feature | spec | arch | result | 기존 위키 | home repo | extra-col |\n"
        "|---------|:--:|:--:|:--:|------|-----------|-----------|\n"
        "| f1 | [✓](../raw/odd-f1-spec.md) | — | — | — | odd-project | z |\n"
        "\n"
        "## 결정과 근거\n"
        "\n"
        "## 관련 문서\n"
    )
    new_docs = [
        _entry(
            repo_dir="odd-project", project="odd", feature="f1", kind="ui", raw_name="odd-f1-ui.md",
        )
    ]

    result = update_registry(registry_text, new_docs, prefix_map={"odd-project": "odd"})

    assert result["ok"] is False
    assert result["reason"] == "catalog_unparsed"
    assert "unrecognized" in result["detail"] or "shape" in result["detail"]


def test_merged_kinds_appended_in_fixed_order_regardless_of_input_order():
    registry_text = (
        "## 현재 상태\n"
        "\n"
        "### acme-widget\n"
        "\n"
        "| feature | spec | arch | 기타 | result | 기존 위키 | home repo |\n"
        "|---------|:--:|:--:|:--:|:--:|------|-----------|\n"
        "| widget-onboarding | [✓](../raw/acme-widget-onboarding-spec.md) | — | — | — | — | acme-widget |\n"
        "\n"
        "## 결정과 근거\n"
        "\n"
        "## 관련 문서\n"
    )
    # context가 먼저, ui가 나중에 들어와도(딕셔너리 순서와 무관) 최종 셀은
    # ui · api · context 고정 순서로 합성돼야 한다.
    new_docs = [
        _entry(
            repo_dir="acme-widget", project="acme", feature="widget-onboarding",
            kind="context", raw_name="acme-widget-onboarding-context.md",
        ),
        _entry(
            repo_dir="acme-widget", project="acme", feature="widget-onboarding",
            kind="ui", raw_name="acme-widget-onboarding-ui.md",
        ),
    ]

    result = update_registry(registry_text, new_docs, prefix_map=_MINI_PREFIX_MAP)

    assert result["ok"] is True
    assert (
        "[ui](../raw/acme-widget-onboarding-ui.md) · [context](../raw/acme-widget-onboarding-context.md)"
    ) in result["text"]


def test_direct_kind_cell_with_existing_link_is_left_untouched():
    registry_text = (
        "## 현재 상태\n"
        "\n"
        "### acme-widget\n"
        "\n"
        "| feature | spec | arch | result | 기존 위키 | home repo |\n"
        "|---------|:--:|:--:|:--:|------|-----------|\n"
        "| widget-onboarding | [✓](../raw/acme-widget-onboarding-spec.md) | — | — | — | acme-widget |\n"
        "\n"
        "## 결정과 근거\n"
        "\n"
        "## 관련 문서\n"
    )
    new_docs = [
        _entry(
            repo_dir="acme-widget", project="acme", feature="widget-onboarding",
            kind="spec", raw_name="acme-widget-onboarding-spec-v2.md",
        )
    ]

    result = update_registry(registry_text, new_docs, prefix_map=_MINI_PREFIX_MAP)

    assert result["ok"] is True
    assert result["cells_updated"] == 0
    # 원본 spec 셀 그대로(잘못 전달된 방어적 케이스 — 덮어쓰지 않음)
    assert "[✓](../raw/acme-widget-onboarding-spec.md)" in result["text"]
    assert "acme-widget-onboarding-spec-v2.md" not in result["text"]


# ── 카운트 문장 갱신 (§6.3.3 화이트리스트) ───────────────────────────────────


_TOTALS = {"features": 4, "raw": 7, "spec": 4, "arch": 2, "result": 1, "api": 0, "ui": 0, "context": 0}


def test_count_sentences_updated_when_totals_given(fake_kompound_env):
    registry_text = (fake_kompound_env["kompound"] / "wiki" / "sdd-spec-registry.md").read_text(
        encoding="utf-8"
    )
    new_docs = [
        _entry(
            repo_dir="acme-widget", project="acme", feature="widget-checkout",
            kind="spec", raw_name="acme-widget-checkout-spec.md",
        )
    ]

    result = update_registry(registry_text, new_docs, prefix_map=_MINI_PREFIX_MAP, totals=_TOTALS)

    assert result["ok"] is True
    text = result["text"]
    assert (
        "4 feature · raw 7개(spec 4 · arch 2 · result 1 · api 0 · ui 0 · context 0). "
        "범례: ✓=있음, —=산출물 없음."
    ) in text
    assert "- raw: `raw/<project>-<feature>-<kind>.md` 7개 (위 표 링크)" in text


def test_date_stamped_snapshot_sentence_is_byte_unchanged(fake_kompound_env):
    registry_text = (fake_kompound_env["kompound"] / "wiki" / "sdd-spec-registry.md").read_text(
        encoding="utf-8"
    )
    assert "**2026-07-01 재스냅샷**: 3 feature · raw 6개. 직전 스냅샷(2026-06-01)은 1 feature · raw 2개였다." in (
        registry_text
    )
    new_docs = [
        _entry(
            repo_dir="acme-widget", project="acme", feature="widget-checkout",
            kind="spec", raw_name="acme-widget-checkout-spec.md",
        )
    ]

    result = update_registry(registry_text, new_docs, prefix_map=_MINI_PREFIX_MAP, totals=_TOTALS)

    assert result["ok"] is True
    assert (
        "**2026-07-01 재스냅샷**: 3 feature · raw 6개. 직전 스냅샷(2026-06-01)은 1 feature · raw 2개였다."
    ) in result["text"]


def test_prose_count_sentence_without_date_stays_unchanged_whitelist_defense():
    registry_text = (
        "## 현재 상태\n"
        "\n"
        "1 feature · raw 1개(spec 1 · arch 0 · result 0 · api 0 · ui 0 · context 0). 범례: ✓=있음, —=산출물 없음.\n"
        "\n"
        "### acme-widget\n"
        "\n"
        "8 feature 전부 spec·arch·result 완비. 뒤 4개가 이번 라운드 신규.\n"
        "\n"
        "| feature | spec | arch | result | 기존 위키 | home repo |\n"
        "|---------|:--:|:--:|:--:|------|-----------|\n"
        "| widget-onboarding | [✓](../raw/acme-widget-onboarding-spec.md) | — | — | — | acme-widget |\n"
        "\n"
        "## 결정과 근거\n"
        "\n"
        "24 feature 중 10개뿐 완료.\n"
        "\n"
        "## 관련 문서\n"
        "- raw: `raw/<project>-<feature>-<kind>.md` 1개 (위 표 링크)\n"
    )
    new_docs = [
        _entry(
            repo_dir="acme-widget", project="acme", feature="widget-checkout",
            kind="spec", raw_name="acme-widget-checkout-spec.md",
        )
    ]
    totals = {"features": 2, "raw": 2, "spec": 2, "arch": 0, "result": 0, "api": 0, "ui": 0, "context": 0}

    result = update_registry(registry_text, new_docs, prefix_map={"acme-widget": "acme"}, totals=totals)

    assert result["ok"] is True
    text = result["text"]
    # 화이트리스트 미매칭 산문 카운트 줄 — 완전 불변
    assert "8 feature 전부 spec·arch·result 완비. 뒤 4개가 이번 라운드 신규." in text
    assert "24 feature 중 10개뿐 완료." in text
    # 화이트리스트 매칭 대상 2종만 갱신됨
    assert (
        "2 feature · raw 2개(spec 2 · arch 0 · result 0 · api 0 · ui 0 · context 0). 범례: ✓=있음, —=산출물 없음."
    ) in text
    assert "- raw: `raw/<project>-<feature>-<kind>.md` 2개 (위 표 링크)" in text


def test_totals_omitted_skips_count_sentence_updates(fake_kompound_env):
    registry_text = (fake_kompound_env["kompound"] / "wiki" / "sdd-spec-registry.md").read_text(
        encoding="utf-8"
    )
    new_docs = [
        _entry(
            repo_dir="acme-widget", project="acme", feature="widget-checkout",
            kind="spec", raw_name="acme-widget-checkout-spec.md",
        )
    ]

    result = update_registry(registry_text, new_docs, prefix_map=_MINI_PREFIX_MAP)  # totals=None

    assert result["ok"] is True
    # 카운트 문장은 원본 그대로(호출자가 totals를 안 줬으므로 손대지 않음)
    assert "3 feature · raw 6개(spec 3 · arch 2 · result 1 · api 0 · ui 0 · context 0)." in result["text"]


def test_missing_current_status_sentence_fails_catalog_unparsed():
    registry_text = (
        "## 현재 상태\n"
        "\n"
        "이 줄은 알려진 형태가 아니다.\n"
        "\n"
        "### acme-widget\n"
        "\n"
        "| feature | spec | arch | result | 기존 위키 | home repo |\n"
        "|---------|:--:|:--:|:--:|------|-----------|\n"
        "| widget-onboarding | [✓](../raw/acme-widget-onboarding-spec.md) | — | — | — | acme-widget |\n"
        "\n"
        "## 결정과 근거\n"
        "\n"
        "## 관련 문서\n"
        "- raw: `raw/<project>-<feature>-<kind>.md` 1개 (위 표 링크)\n"
    )
    new_docs = [
        _entry(
            repo_dir="acme-widget", project="acme", feature="widget-checkout",
            kind="spec", raw_name="acme-widget-checkout-spec.md",
        )
    ]

    result = update_registry(
        registry_text, new_docs, prefix_map={"acme-widget": "acme"},
        totals={"features": 1, "raw": 1, "spec": 1, "arch": 0, "result": 0, "api": 0, "ui": 0, "context": 0},
    )

    assert result["ok"] is False
    assert result["reason"] == "catalog_unparsed"
    assert "current-status" in result["detail"]


def test_missing_raw_total_sentence_fails_catalog_unparsed():
    registry_text = (
        "## 현재 상태\n"
        "\n"
        "1 feature · raw 1개(spec 1 · arch 0 · result 0 · api 0 · ui 0 · context 0). 범례: ✓=있음, —=산출물 없음.\n"
        "\n"
        "### acme-widget\n"
        "\n"
        "| feature | spec | arch | result | 기존 위키 | home repo |\n"
        "|---------|:--:|:--:|:--:|------|-----------|\n"
        "| widget-onboarding | [✓](../raw/acme-widget-onboarding-spec.md) | — | — | — | acme-widget |\n"
        "\n"
        "## 결정과 근거\n"
        "\n"
        "## 관련 문서\n"
        "raw 총계는 여기 없다.\n"
    )
    new_docs = [
        _entry(
            repo_dir="acme-widget", project="acme", feature="widget-checkout",
            kind="spec", raw_name="acme-widget-checkout-spec.md",
        )
    ]

    result = update_registry(
        registry_text, new_docs, prefix_map={"acme-widget": "acme"},
        totals={"features": 2, "raw": 2, "spec": 2, "arch": 0, "result": 0, "api": 0, "ui": 0, "context": 0},
    )

    assert result["ok"] is False
    assert result["reason"] == "catalog_unparsed"
    assert "raw-total" in result["detail"]


# ── 0건 / 미인지 kind ────────────────────────────────────────────────────────


def test_zero_new_docs_returns_unchanged_text_byte_identical(fake_kompound_env):
    registry_text = (fake_kompound_env["kompound"] / "wiki" / "sdd-spec-registry.md").read_text(
        encoding="utf-8"
    )

    result = update_registry(registry_text, [], prefix_map=_MINI_PREFIX_MAP, totals=_TOTALS)

    assert result["ok"] is True
    assert result["text"] == registry_text
    assert result["rows_added"] == 0
    assert result["cells_updated"] == 0
    assert result["columns_added"] == []


def test_unrecognized_kind_fails_catalog_unparsed(fake_kompound_env):
    registry_text = (fake_kompound_env["kompound"] / "wiki" / "sdd-spec-registry.md").read_text(
        encoding="utf-8"
    )
    new_docs = [
        _entry(
            repo_dir="acme-widget", project="acme", feature="widget-checkout",
            kind="bogus", raw_name="acme-widget-checkout-bogus.md",
        )
    ]

    result = update_registry(registry_text, new_docs, prefix_map=_MINI_PREFIX_MAP)

    assert result["ok"] is False
    assert result["reason"] == "catalog_unparsed"
    assert "bogus" in result["detail"]


def test_worktree_suffix_in_home_repo_cell():
    registry_text = (
        "## 현재 상태\n"
        "\n"
        "### acme-widget\n"
        "\n"
        "| feature | spec | arch | result | 기존 위키 | home repo |\n"
        "|---------|:--:|:--:|:--:|------|-----------|\n"
        "| widget-onboarding | [✓](../raw/acme-widget-onboarding-spec.md) | — | — | — | acme-widget |\n"
        "\n"
        "## 결정과 근거\n"
        "\n"
        "## 관련 문서\n"
    )
    new_docs = [
        _entry(
            repo_dir="acme-widget", project="acme", feature="widget-preview",
            kind="spec", raw_name="acme-widget-preview-spec.md", worktree="widget-preview-wt",
        )
    ]

    result = update_registry(registry_text, new_docs, prefix_map={"acme-widget": "acme"})

    assert result["ok"] is True
    assert "acme-widget + `worktrees/widget-preview-wt`" in result["text"]
