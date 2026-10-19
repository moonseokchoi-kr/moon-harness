"""tests/test_sdd_spec_writer.py — T-3 (F5, F6, F13 일부) 정적 검사.

`agents/sdd-spec-writer.md`(개명·축소)와 `skills/sdd/references/spec-template.md`
(단일 문서 템플릿)의 frontmatter·섹션 순서·금지 문자열을 고정한다.
네트워크/LLM 호출 없음.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
WRITER = REPO / "agents" / "sdd-spec-writer.md"
OLD_WRITER = REPO / "agents" / "sdd-ux-researcher.md"
TEMPLATE = REPO / "skills" / "sdd" / "references" / "spec-template.md"

REQUIRED_SECTIONS = [
    "목표",
    "사용자 요구사항(원문)",
    "가정",
    "코드 조사",
    "제약",
    "기능 요구사항",
    "설계 결정",
    "테스트 전략",
    "적용 규칙",
    "빌드·테스트 명령",
    "Boundaries",
    "범위 밖",
    "미결 질문",
]


def _read(path: Path) -> str:
    assert path.is_file(), f"{path.relative_to(REPO)} 없음"
    return path.read_text(encoding="utf-8")


def _frontmatter(text: str) -> dict[str, str]:
    m = re.match(r"---\n(.*?)\n---\n", text, re.DOTALL)
    assert m, "frontmatter 없음"
    out: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def _h2_titles(text: str) -> list[str]:
    return [m.group(1).strip() for m in re.finditer(r"^## (.+)$", text, re.MULTILINE)]


# ---------- F5: agents/sdd-spec-writer.md ----------


def test_writer_file_exists_and_old_file_removed():
    assert WRITER.is_file()
    assert not OLD_WRITER.exists()


def test_writer_frontmatter_name_and_write_tool():
    fm = _frontmatter(_read(WRITER))
    assert fm["name"] == "sdd-spec-writer"
    tools = [t.strip() for t in fm["tools"].split(",")]
    assert "Write" in tools


@pytest.mark.parametrize("forbidden", ["페르소나", "유스케이스", "타겟 사용자"])
def test_writer_body_has_no_removed_procedures(forbidden):
    assert forbidden not in _read(WRITER)


def test_writer_uses_open_questions_not_old_marker():
    text = _read(WRITER)
    assert "미결 질문" in text
    assert "[NEEDS CLARIFICATION]" not in text


def test_writer_saves_spec_with_write_directly():
    text = _read(WRITER)
    assert "docs/sdd/spec/{YYYY-MM-DD}-{feature}.md" in text
    assert "Write" in text


def test_writer_has_no_blocker_pass_literal():
    # has_blocker_pass 는 문자열 포함만 검사 — 리터럴이 있으면 게이트 우회
    assert "BLOCKER_PASS" not in _read(WRITER)


def test_writer_says_controller_adds_mark_after_blocker_checker():
    text = _read(WRITER)
    assert "blocker-checker" in text
    assert "컨트롤러" in text or "리드" in text


def test_writer_missing_input_reports_needs_context_without_write():
    text = _read(WRITER)
    assert "NEEDS_CONTEXT" in text
    assert "원문" in text or "요약" in text
    assert "저장하지" in text or "Write하지" in text


def test_writer_does_not_write_implementation_plan_section():
    text = _read(WRITER)
    # 섹션 소유권(R11): 구현 계획은 taskmaster 소유 — 쓰지 않는다고 명시
    assert "구현 계획" in text
    lines = [ln for ln in text.splitlines() if "구현 계획" in ln]
    assert any(("쓰지" in ln or "작성하지" in ln or "taskmaster" in ln) for ln in lines)


# ---------- F6/F13: spec-template.md ----------


def test_template_exists():
    assert TEMPLATE.is_file()


def test_template_has_13_sections_in_order():
    titles = _h2_titles(_read(TEMPLATE))
    positions = []
    for required in REQUIRED_SECTIONS:
        idx = next((i for i, t in enumerate(titles) if t.startswith(required)), None)
        assert idx is not None, f"섹션 없음: {required} (실제: {titles})"
        positions.append(idx)
    assert positions == sorted(positions), f"섹션 순서 어긋남: {positions}"


@pytest.mark.parametrize(
    "token", ["Preserve", "Change", "Avoid", "Risk", "Always", "Ask first", "Never"]
)
def test_template_has_constraint_and_boundary_tokens(token):
    assert token in _read(TEMPLATE)


@pytest.mark.parametrize("title", ["기능 지도", "UI", "구현 계획"])
def test_template_has_conditional_sections(title):
    assert title in _h2_titles(_read(TEMPLATE))


def test_template_mentions_manual_test_scenario():
    assert "수동 테스트 시나리오" in _read(TEMPLATE)


@pytest.mark.parametrize("forbidden", ["타겟 사용자", "핵심 가치"])
def test_template_has_no_removed_fields(forbidden):
    assert forbidden not in _read(TEMPLATE)


def test_template_has_no_blocker_pass_literal():
    assert "BLOCKER_PASS" not in _read(TEMPLATE)


def test_template_does_not_trip_has_blocker_pass_gate(tmp_path):
    sp = importlib.util.spec_from_file_location(
        "stop_pipeline", REPO / "hooks" / "enforcement" / "stop-pipeline.py"
    )
    mod = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(mod)
    spec_dir = tmp_path / "docs" / "sdd" / "spec"
    spec_dir.mkdir(parents=True)
    (spec_dir / "x.md").write_text(_read(TEMPLATE), encoding="utf-8")
    assert mod.has_blocker_pass(tmp_path, "x") is False


def test_template_links_claude_md_instead_of_copying_commands():
    text = _read(TEMPLATE)
    assert "CLAUDE.md" in text
    assert "pytest" not in text  # 빌드/테스트 명령 복사 금지


@pytest.mark.parametrize(
    "hardcoded", ["/opt/homebrew", "/usr/local", "PATH=", "/Users/", "~/.claude"]
)
def test_template_has_no_hardcoded_paths(hardcoded):
    assert hardcoded not in _read(TEMPLATE)


@pytest.mark.parametrize("old_dir", ["docs/sdd/design/", "docs/sdd/context/"])
def test_new_files_do_not_instruct_old_doc_dirs(old_dir):
    assert old_dir not in _read(TEMPLATE)
    assert old_dir not in _read(WRITER)
