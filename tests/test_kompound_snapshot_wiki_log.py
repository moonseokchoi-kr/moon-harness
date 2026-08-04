"""tests/test_kompound_snapshot_wiki_log.py — F7/F10 index.md·log.md 갱신 (T-8).

`fake_kompound_env`(tests/conftest.py, T-2)의 index/log 골든 텍스트를
재사용한다. F10 "양쪽 보존"은 append-only/prepend-only 쓰기 형태 자체로
성립하므로, 사람의 동시 편집을 흉내낸 텍스트를 먼저 준비하고 그 위에 우리
항목을 얹었을 때 둘 다 유실 없이 남는지를 통합 테스트로 확인한다.
"""

from __future__ import annotations

import pytest

from hooks.lib.kompound_snapshot.wiki_log import (
    append_log,
    build_snapshot_log_line,
    update_index,
)

pytestmark = pytest.mark.offline


# ── update_index ─────────────────────────────────────────────────────────────


def test_update_index_replaces_hook_line_and_prepends_recent_change(fake_kompound_env):
    index_text = (fake_kompound_env["kompound"] / "wiki" / "index.md").read_text(encoding="utf-8")

    new_hook = "- [sdd-spec-registry](sdd-spec-registry.md) — 4 feature · raw 7개 (fake_kompound_env)"
    new_recent = "- 2026-07-02 [snapshot] acme-widget — feature 1개 신규 편입"

    result = update_index(index_text, hook_line=new_hook, recent_change_line=new_recent)

    assert result["ok"] is True
    text = result["text"]
    assert new_hook in text
    assert "테스트 전용 축약 registry (fake_kompound_env)" not in text  # 옛 훅 문장은 대체됨

    recent_heading_idx = text.index("## 최근 변경")
    new_line_idx = text.index(new_recent)
    old_line_idx = text.index("2026-07-01 [bulk-ingest] fake_kompound_env 초기 시드")
    assert recent_heading_idx < new_line_idx < old_line_idx  # prepend — 새 항목이 위


def test_update_index_preserves_other_entries_and_contradictions_section():
    index_text = (
        "# Wiki Index\n"
        "\n"
        "## Entries\n"
        "\n"
        "- [alpha](alpha.md) — 알파 문서\n"
        "- [sdd-spec-registry](sdd-spec-registry.md) — 옛 훅 문장\n"
        "- [beta](beta.md) — 베타 문서\n"
        "\n"
        "## 최근 변경\n"
        "\n"
        "- 2026-06-01 [ingest] 기존 항목\n"
        "\n"
        "## 미해결 모순\n"
        "\n"
        "> ⚠️ 어떤 모순\n"
    )

    result = update_index(
        index_text,
        hook_line="- [sdd-spec-registry](sdd-spec-registry.md) — 새 훅 문장",
        recent_change_line="- 2026-06-02 [snapshot] 새 항목",
    )

    assert result["ok"] is True
    text = result["text"]
    assert "- [alpha](alpha.md) — 알파 문서" in text
    assert "- [beta](beta.md) — 베타 문서" in text
    assert "- [sdd-spec-registry](sdd-spec-registry.md) — 새 훅 문장" in text
    assert "- [sdd-spec-registry](sdd-spec-registry.md) — 옛 훅 문장" not in text
    assert "> ⚠️ 어떤 모순" in text
    assert "- 2026-06-01 [ingest] 기존 항목" in text  # 기존 최근 변경 줄 보존


def test_update_index_does_not_replace_unrelated_entry_that_mentions_hook_target_in_prose():
    """리뷰 [P1] 재현 케이스(it.2) — 회귀 방지.

    알파벳순으로 `sdd-spec-registry`보다 앞서는 Entries 줄이 그 이름을
    **산문으로만 언급**해도(실제 `wiki/index.md`에 흔한 스타일), 그 줄이
    아니라 진짜 링크 앵커(`[sdd-spec-registry](`)를 가진 줄만 교체돼야
    한다. 수정 전에는 `related-topic` 줄이 치환되어 사람이 쓴 설명이
    사라지고 진짜 훅 줄은 옛 카운트로 남아 링크가 중복됐다.
    """
    index_text = (
        "# Wiki Index\n"
        "\n"
        "## Entries\n"
        "\n"
        "- [related-topic](related-topic.md) — 이 페이지는 sdd-spec-registry 관련 배경을 설명한다\n"
        "- [sdd-spec-registry](sdd-spec-registry.md) — 3 feature · raw 6개 (옛 카운트)\n"
        "\n"
        "## 최근 변경\n"
        "\n"
        "- 2026-07-01 [bulk-ingest] 원본 시드\n"
    )
    unrelated_line = "- [related-topic](related-topic.md) — 이 페이지는 sdd-spec-registry 관련 배경을 설명한다"
    new_hook = "- [sdd-spec-registry](sdd-spec-registry.md) — 4 feature · raw 7개 (새 카운트)"

    result = update_index(index_text, hook_line=new_hook, recent_change_line="- 2026-07-02 [snapshot] 항목")

    assert result["ok"] is True
    text = result["text"]
    # ① 관계없는 Entries 줄은 바이트 단위 불변
    assert unrelated_line in text
    # ② 진짜 훅 줄만 갱신됨
    assert new_hook in text
    assert "- [sdd-spec-registry](sdd-spec-registry.md) — 3 feature · raw 6개 (옛 카운트)" not in text
    # ③ 링크 중복 없음 — sdd-spec-registry 링크 앵커는 정확히 1회만 등장
    assert text.count("[sdd-spec-registry](sdd-spec-registry.md)") == 1


def test_update_index_missing_hook_line_fails():
    index_text = "# Wiki Index\n\n## Entries\n\n- [alpha](alpha.md) — 알파\n\n## 최근 변경\n\n- old\n"

    result = update_index(index_text, hook_line="- new hook", recent_change_line="- new recent")

    assert result["ok"] is False
    assert result["reason"] == "catalog_unparsed"


def test_update_index_missing_recent_changes_heading_fails():
    index_text = (
        "# Wiki Index\n\n## Entries\n\n"
        "- [sdd-spec-registry](sdd-spec-registry.md) — 훅\n"
    )

    result = update_index(index_text, hook_line="- new hook", recent_change_line="- new recent")

    assert result["ok"] is False
    assert result["reason"] == "catalog_unparsed"


# ── append_log ───────────────────────────────────────────────────────────────


def test_append_log_appends_single_line_preserving_existing_content(fake_kompound_env):
    log_text = (fake_kompound_env["kompound"] / "wiki" / "log.md").read_text(encoding="utf-8")
    new_line = "2026-07-02 [snapshot] <1 raw> — raw 커밋 abc1234(2026-07-02) · 카탈로그 def5678(2026-07-02) · 재시도 0회"

    result = append_log(log_text, line=new_line)

    assert result["ok"] is True
    text = result["text"]
    assert text.startswith(log_text)  # 기존 내용은 완전 보존(append-only)
    assert text.endswith(new_line + "\n")


def test_append_log_from_empty_string():
    result = append_log("", line="2026-07-02 [snapshot] 첫 배치")

    assert result["ok"] is True
    assert result["text"] == "2026-07-02 [snapshot] 첫 배치\n"


def test_append_log_normalizes_trailing_newline_of_input_line():
    result = append_log("first line\n", line="second line\n")

    assert result["ok"] is True
    assert result["text"] == "first line\nsecond line\n"


# ── F10: index.md / log.md 동시 편집 — 양쪽 보존 ─────────────────────────────


def test_f10_index_concurrent_edit_both_entries_preserved():
    # "사람 편집"이 먼저 최근 변경에 prepend된 상태를 흉내낸다.
    human_line = "- 2026-07-02 [ingest] 사람이 방금 추가한 항목"
    index_text = (
        "# Wiki Index\n\n## Entries\n\n"
        "- [sdd-spec-registry](sdd-spec-registry.md) — 옛 훅\n\n"
        "## 최근 변경\n\n"
        f"{human_line}\n"
        "- 2026-07-01 [bulk-ingest] 원본 시드\n"
    )
    our_line = "- 2026-07-02 [snapshot] 우리 배치 항목"

    result = update_index(
        index_text,
        hook_line="- [sdd-spec-registry](sdd-spec-registry.md) — 새 훅",
        recent_change_line=our_line,
    )

    assert result["ok"] is True
    text = result["text"]
    assert human_line in text
    assert our_line in text
    assert "원본 시드" in text
    # 우리 항목이 최신(맨 위)이고, 사람 편집·원본 시드 둘 다 그 아래 유실 없이 남는다.
    heading_idx = text.index("## 최근 변경")
    our_idx = text.index(our_line)
    human_idx = text.index(human_line)
    seed_idx = text.index("원본 시드")
    assert heading_idx < our_idx < human_idx < seed_idx


def test_f10_log_concurrent_append_both_lines_preserved():
    # "사람 편집"이 먼저 append된 상태(다른 프로세스가 이미 log.md에 한 줄
    # 추가해 둔 상태)를 흉내낸다.
    seed = "2026-07-01 [bulk-ingest] 원본 시드\n"
    human_line = "2026-07-02 [ingest] 사람이 동시에 추가한 항목"
    log_text_with_human_edit = seed + human_line + "\n"

    our_line = build_snapshot_log_line(
        date="2026-07-02",
        total_raw=1,
        raw_commits=[("abc1234", "2026-07-02")],
        catalog_commit=("def5678", "2026-07-02"),
        retries=0,
    )

    result = append_log(log_text_with_human_edit, line=our_line)

    assert result["ok"] is True
    text = result["text"]
    assert seed.strip() in text
    assert human_line in text
    assert our_line in text
    # append-only이므로 순서 = 원본 시드 → 사람 편집 → 우리 배치(시간순)
    assert text.index("원본 시드") < text.index(human_line) < text.index(our_line)


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
    index_path = kompound / "wiki" / "index.md"
    log_path = kompound / "wiki" / "log.md"
    registry_path = kompound / "wiki" / "sdd-spec-registry.md"

    before = {
        "index": index_path.read_text(encoding="utf-8"),
        "log": log_path.read_text(encoding="utf-8"),
        "registry": registry_path.read_text(encoding="utf-8"),
    }

    update_index(before["index"], hook_line="- [sdd-spec-registry](sdd-spec-registry.md) — x", recent_change_line="- y")
    append_log(before["log"], line="z")

    assert index_path.read_text(encoding="utf-8") == before["index"]
    assert log_path.read_text(encoding="utf-8") == before["log"]
    assert registry_path.read_text(encoding="utf-8") == before["registry"]
