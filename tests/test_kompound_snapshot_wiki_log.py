"""tests/test_kompound_snapshot_wiki_log.py — F7/F10 index.md·log.md 갱신 (T-8).

`fake_kompound_env`(tests/conftest.py, T-2)의 index/log 골든 텍스트를
재사용한다. F10 "양쪽 보존"은 append-only/prepend-only 쓰기 형태 자체로
성립하므로, 사람의 동시 편집을 흉내낸 텍스트를 먼저 준비하고 그 위에 우리
항목을 얹었을 때 둘 다 유실 없이 남는지를 통합 테스트로 확인한다.

2026-10-07 v2 볼트 이관으로 대상이 바뀌었다(v1 `wiki/index.md` Entries·최근 변경
· `wiki/log.md` 한 줄 → 볼트 루트 `index.md`의 `- [[SDD Spec Registry]]` 훅 줄과
`## 📥 Recent Ingests`, 루트 `log.md`의 `## [date] op | title` 엔트리). 이 파일의
기대값도 그에 맞춰 갱신했다.
"""

from __future__ import annotations

import pytest

from hooks.lib.kompound_snapshot.wiki_log import (
    append_log,
    build_log_entry,
    build_snapshot_log_line,
    update_index,
)

pytestmark = pytest.mark.offline

_HOOK = "- [[SDD Spec Registry]]"


# ── update_index ─────────────────────────────────────────────────────────────


def test_update_index_replaces_hook_line_and_prepends_recent_ingest(fake_kompound_env):
    index_text = (fake_kompound_env["kompound"] / "index.md").read_text(encoding="utf-8")

    new_hook = f"{_HOOK} — SDD spec/design/result 카탈로그. 4 feature · raw 7개."
    new_recent = "- 2026-07-02 [snapshot] acme-widget — feature 1개 신규 편입"

    result = update_index(index_text, hook_line=new_hook, recent_change_line=new_recent)

    assert result["ok"] is True
    text = result["text"]
    assert new_hook in text
    assert "테스트 전용 축약 registry (fake_kompound_env)" not in text  # 옛 훅 문장은 대체됨

    recent_heading_idx = text.index("## 📥 Recent Ingests")
    preamble_idx = text.index("> fixture 머리말")
    new_line_idx = text.index(new_recent)
    old_line_idx = text.index("2026-07-01 [bulk-ingest] fake_kompound_env 초기 시드")
    # prepend — 머리말 인용문 뒤, 기존 첫 항목 앞
    assert recent_heading_idx < preamble_idx < new_line_idx < old_line_idx
    # 다음 섹션은 그대로
    assert text.index("## 🔗 Quick Links") > old_line_idx


def test_update_index_preserves_other_lines_and_contradictions_section():
    index_text = (
        "# Index\n"
        "\n"
        "## 🗺 Domain Maps\n"
        "\n"
        "- [[MOC-AI Harness]] — 13 wiki\n"
        f"{_HOOK} — 옛 훅 문장\n"
        "- [[My Action Items]] — 할일\n"
        "\n"
        "## ⚠️ Open Contradictions\n"
        "\n"
        "> [!warning] Contradiction\n"
        "> 어떤 모순\n"
        "\n"
        "## 📥 Recent Ingests\n"
        "\n"
        "- 2026-06-01 [ingest] 기존 항목\n"
    )

    result = update_index(
        index_text,
        hook_line=f"{_HOOK} — 새 훅 문장",
        recent_change_line="- 2026-06-02 [snapshot] 새 항목",
    )

    assert result["ok"] is True
    text = result["text"]
    assert "- [[MOC-AI Harness]] — 13 wiki" in text
    assert "- [[My Action Items]] — 할일" in text
    assert f"{_HOOK} — 새 훅 문장" in text
    assert f"{_HOOK} — 옛 훅 문장" not in text
    assert "> 어떤 모순" in text
    assert "- 2026-06-01 [ingest] 기존 항목" in text  # 기존 Recent Ingests 줄 보존
    assert text.index("- 2026-06-02 [snapshot] 새 항목") < text.index("- 2026-06-01 [ingest] 기존 항목")


def test_update_index_does_not_replace_unrelated_line_that_mentions_hook_target_in_prose():
    """리뷰 [P1] 재현 케이스(it.2)의 v2판 — 회귀 방지.

    다른 항목이 설명 문장 안에서 ``[[SDD Spec Registry]]``를 언급해도, 그 줄이
    아니라 ``- [[SDD Spec Registry]]``로 **시작하는** 진짜 훅 줄만 교체돼야 한다.
    """
    unrelated_line = "- [[Loop Engineering]] — 이 코퍼스([[SDD Spec Registry]])를 모은 동기"
    index_text = (
        "# Index\n"
        "\n"
        "## 🗂 Wiki Pages\n"
        "\n"
        f"{unrelated_line}\n"
        f"{_HOOK} — 3 feature · raw 6개 (옛 카운트)\n"
        "\n"
        "## 📥 Recent Ingests\n"
        "\n"
        "- 2026-07-01 [bulk-ingest] 원본 시드\n"
    )
    new_hook = f"{_HOOK} — 4 feature · raw 7개 (새 카운트)"

    result = update_index(index_text, hook_line=new_hook, recent_change_line="- 2026-07-02 [snapshot] 항목")

    assert result["ok"] is True
    text = result["text"]
    assert unrelated_line in text  # ① 관계없는 줄은 바이트 단위 불변
    assert new_hook in text  # ② 진짜 훅 줄만 갱신됨
    assert f"{_HOOK} — 3 feature · raw 6개 (옛 카운트)" not in text
    assert text.count(_HOOK) == 1  # ③ 훅 줄 중복 없음


def test_update_index_recent_ingests_without_items_inserts_after_preamble():
    index_text = (
        f"# Index\n\n{_HOOK} — 훅\n\n"
        "## 📥 Recent Ingests\n\n> 머리말\n\n"
        "## 🔗 Quick Links\n\n- [[log]]\n"
    )

    result = update_index(index_text, hook_line=f"{_HOOK} — 새 훅", recent_change_line="- 2026-07-02 [snapshot] 첫 항목")

    assert result["ok"] is True
    text = result["text"]
    assert text.index("> 머리말") < text.index("- 2026-07-02 [snapshot] 첫 항목") < text.index("## 🔗 Quick Links")


def test_update_index_missing_hook_line_fails():
    index_text = "# Index\n\n- [[alpha]] — 알파\n\n## 📥 Recent Ingests\n\n- old\n"

    result = update_index(index_text, hook_line="- new hook", recent_change_line="- new recent")

    assert result["ok"] is False
    assert result["reason"] == "catalog_unparsed"


def test_update_index_missing_recent_ingests_heading_fails():
    index_text = f"# Index\n\n{_HOOK} — 훅\n"

    result = update_index(index_text, hook_line="- new hook", recent_change_line="- new recent")

    assert result["ok"] is False
    assert result["reason"] == "catalog_unparsed"


def test_update_index_v1_layout_is_not_recognized():
    """v1 형식(`## Entries` + `[sdd-spec-registry](...)` + `## 최근 변경`)은 더 이상
    인지되지 않는다 — 조용히 엉뚱한 곳을 고치지 않고 catalog_unparsed로 드러낸다."""
    index_text = (
        "# Wiki Index\n\n## Entries\n\n"
        "- [sdd-spec-registry](sdd-spec-registry.md) — 훅\n\n"
        "## 최근 변경\n\n- old\n"
    )

    result = update_index(index_text, hook_line="- new hook", recent_change_line="- new recent")

    assert result["ok"] is False
    assert result["reason"] == "catalog_unparsed"


# ── build_log_entry / append_log ─────────────────────────────────────────────


def test_build_log_entry_matches_v2_format():
    entry = build_log_entry("2026-07-02", "snapshot", "SDD 스냅샷 1건 카탈로그 편입 (acme)", "<1 raw> — 요약")

    assert entry == "## [2026-07-02] snapshot | SDD 스냅샷 1건 카탈로그 편입 (acme)\n\n- <1 raw> — 요약"


def test_append_log_appends_single_entry_preserving_existing_content(fake_kompound_env):
    log_text = (fake_kompound_env["kompound"] / "log.md").read_text(encoding="utf-8")
    entry = build_log_entry("2026-07-02", "snapshot", "t", "s")

    result = append_log(log_text, line=entry)

    assert result["ok"] is True
    text = result["text"]
    assert text.startswith(log_text.rstrip("\n"))  # 기존 내용은 완전 보존(append-only)
    assert text.endswith("\n\n" + entry + "\n")  # 빈 줄 하나로 구분된 새 엔트리
    assert text.count("## [") == 2


def test_append_log_from_empty_string():
    result = append_log("", line="## [2026-07-02] snapshot | 첫 배치\n\n- 요약")

    assert result["ok"] is True
    assert result["text"] == "## [2026-07-02] snapshot | 첫 배치\n\n- 요약\n"


def test_append_log_normalizes_trailing_newlines():
    result = append_log("## [a] x | y\n\n- z\n\n\n", line="## [b] x | y\n\n- w\n")

    assert result["ok"] is True
    assert result["text"] == "## [a] x | y\n\n- z\n\n## [b] x | y\n\n- w\n"


# ── F10: index.md / log.md 동시 편집 — 양쪽 보존 ─────────────────────────────


def test_f10_index_concurrent_edit_both_entries_preserved():
    human_line = "- 2026-07-02 [ingest] 사람이 방금 추가한 항목"
    index_text = (
        f"# Index\n\n{_HOOK} — 옛 훅\n\n"
        "## 📥 Recent Ingests\n\n"
        f"{human_line}\n"
        "- 2026-07-01 [bulk-ingest] 원본 시드\n"
    )
    our_line = "- 2026-07-02 [snapshot] 우리 배치 항목"

    result = update_index(index_text, hook_line=f"{_HOOK} — 새 훅", recent_change_line=our_line)

    assert result["ok"] is True
    text = result["text"]
    heading_idx = text.index("## 📥 Recent Ingests")
    our_idx = text.index(our_line)
    human_idx = text.index(human_line)
    seed_idx = text.index("원본 시드")
    assert heading_idx < our_idx < human_idx < seed_idx


def test_f10_log_concurrent_append_both_entries_preserved():
    seed = "## [2026-07-01] bulk-ingest | 원본 시드\n\n- 시드\n"
    human = "\n## [2026-07-02] ingest | 사람이 동시에 추가한 항목\n\n- 사람\n"
    log_text_with_human_edit = seed + human

    summary = build_snapshot_log_line(
        date="2026-07-02",
        total_raw=1,
        raw_commits=[("abc1234", "2026-07-02")],
        catalog_commit=("def5678", "2026-07-02"),
        retries=0,
        with_prefix=False,
    )
    our_entry = build_log_entry("2026-07-02", "snapshot", "SDD 스냅샷 1건", summary)

    result = append_log(log_text_with_human_edit, line=our_entry)

    assert result["ok"] is True
    text = result["text"]
    assert text.index("원본 시드") < text.index("사람이 동시에 추가한 항목") < text.index(our_entry)


# ── build_snapshot_log_line (arch §6.3.0 리터럴 템플릿) ─────────────────────


def test_build_snapshot_log_line_single_commit_matches_literal_template():
    line = build_snapshot_log_line(
        date="2026-07-30",
        total_raw=5,
        raw_commits=[("a1b2c3d", "2026-07-30")],
        catalog_commit=("e4f5a6b", "2026-07-30"),
        retries=0,
    )

    assert line == (
        "2026-07-30 [snapshot] <5 raw> — raw 커밋 a1b2c3d(2026-07-30) · "
        "카탈로그 e4f5a6b(2026-07-30) · 재시도 0회"
    )


def test_build_snapshot_log_line_without_prefix_for_v2_entry_body():
    line = build_snapshot_log_line(
        date="2026-07-30",
        total_raw=5,
        raw_commits=[("a1b2c3d", "2026-07-30")],
        catalog_commit=("e4f5a6b", "2026-07-30"),
        retries=0,
        with_prefix=False,
    )

    assert line == "<5 raw> — raw 커밋 a1b2c3d(2026-07-30) · 카탈로그 e4f5a6b(2026-07-30) · 재시도 0회"


def test_build_snapshot_log_line_multi_commit_enumerates_all_raw_shas():
    line = build_snapshot_log_line(
        date="2026-07-30",
        total_raw=12,
        raw_commits=[
            ("aaa1111", "2026-07-28"),
            ("bbb2222", "2026-07-29"),
            ("ccc3333", "2026-07-30"),
        ],
        catalog_commit=("ddd4444", "2026-07-30"),
        retries=2,
    )

    assert line == (
        "2026-07-30 [snapshot] <총 12 raw> — raw 커밋 "
        "aaa1111(2026-07-28)·bbb2222(2026-07-29)·ccc3333(2026-07-30) · "
        "카탈로그 ddd4444(2026-07-30) · 재시도 2회"
    )


def test_build_snapshot_log_line_retries_formatting():
    line = build_snapshot_log_line(
        date="2026-08-01",
        total_raw=1,
        raw_commits=[("1234567", "2026-08-01")],
        catalog_commit=("7654321", "2026-08-01"),
        retries=3,
    )

    assert "재시도 3회" in line
    assert line.endswith("재시도 3회")


# ── 부작용 없음 (arch §3.2 "없음(텍스트 변환)") ──────────────────────────────


def test_wiki_log_functions_do_not_touch_filesystem(fake_kompound_env):
    kompound = fake_kompound_env["kompound"]
    index_path = kompound / "index.md"
    log_path = kompound / "log.md"
    registry_path = kompound / "20. Wiki" / "24. Maps" / "SDD Spec Registry.md"

    before = {
        "index": index_path.read_text(encoding="utf-8"),
        "log": log_path.read_text(encoding="utf-8"),
        "registry": registry_path.read_text(encoding="utf-8"),
    }

    update_index(before["index"], hook_line=f"{_HOOK} — x", recent_change_line="- y")
    append_log(before["log"], line="z")

    assert index_path.read_text(encoding="utf-8") == before["index"]
    assert log_path.read_text(encoding="utf-8") == before["log"]
    assert registry_path.read_text(encoding="utf-8") == before["registry"]
