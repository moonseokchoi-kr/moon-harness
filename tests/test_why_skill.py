"""tests/test_why_skill.py — skills/why 정적 검증 (오프라인, F1).

커버리지:
- SKILL.md 존재 + frontmatter(name/description)
- references/*.md 정확히 3개
- Preserve/Change/Avoid/Risk, 읽기 전용 규칙 키워드, 코드 앵커·MCP 누락·Explore 지침
- 금지 모델명 정규식 / pstack-models / poteto 부재
- 금지 정규식 자체의 샘플 검증

R6: 읽기 전용 규칙은 지침 존재만 검사한다(준수는 보장하지 못함).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_WHY_DIR = _REPO_ROOT / "skills" / "why"
_SKILL_MD = _WHY_DIR / "SKILL.md"
_REFERENCES_DIR = _WHY_DIR / "references"

_MODEL_NAME_RE = re.compile(
    r"(?i)\b(grok|gpt-?\d|gemini|claude[-\w.]*(opus|sonnet|haiku|fable))"
)


def _skill_text() -> str:
    assert _SKILL_MD.is_file(), f"{_SKILL_MD} 없음"
    return _SKILL_MD.read_text(encoding="utf-8")


def _frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
    assert match, "frontmatter 없음"
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" in line and not line.startswith((" ", "\t")):
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip().strip("\"'")
    return fields


def _all_why_markdown() -> list[Path]:
    assert _WHY_DIR.is_dir(), f"{_WHY_DIR} 없음"
    return sorted(_WHY_DIR.rglob("*.md"))


# ── 존재 / frontmatter ────────────────────────────────────────────────────────


def test_skill_md_exists():
    assert _SKILL_MD.is_file()


def test_frontmatter_name_is_why():
    assert _frontmatter(_skill_text()).get("name") == "why"


def test_frontmatter_description_non_empty():
    assert _frontmatter(_skill_text()).get("description", "").strip() != ""


# ── references ────────────────────────────────────────────────────────────────


def test_references_exactly_three_markdown_files():
    assert _REFERENCES_DIR.is_dir()
    assert len(list(_REFERENCES_DIR.glob("*.md"))) == 3


# ── 키워드 ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("keyword", ["Preserve", "Change", "Avoid", "Risk"])
def test_skill_has_translation_keywords(keyword: str):
    assert keyword in _skill_text()


@pytest.mark.parametrize("keyword", ["읽기 전용", "파일 쓰기", "외부 시스템"])
def test_skill_has_read_only_rule_keywords(keyword: str):
    assert keyword in _skill_text()


@pytest.mark.parametrize("keyword", ["git blame", "git log", "gh pr view"])
def test_skill_has_code_anchor_commands(keyword: str):
    assert keyword in _skill_text()


def test_skill_states_missing_mcp_research_gap():
    text = _skill_text()
    assert "MCP" in text
    assert "조사 누락" in text


def test_skill_instructs_explore_subagent():
    text = _skill_text()
    assert "Explore" in text
    assert "subagent_type" in text


def test_skill_has_fact_inference_unknown_split():
    text = _skill_text()
    for word in ("사실", "추론", "모름"):
        assert word in text


# ── 금지 문자열 ───────────────────────────────────────────────────────────────


def test_no_model_names_in_any_why_markdown():
    files = _all_why_markdown()
    assert files, "skills/why 아래 md 파일 없음"
    offenders = {
        str(p.relative_to(_REPO_ROOT)): m.group(0)
        for p in files
        if (m := _MODEL_NAME_RE.search(p.read_text(encoding="utf-8")))
    }
    assert offenders == {}


@pytest.mark.parametrize("banned", ["pstack-models", "poteto"])
def test_no_cursor_specific_strings(banned: str):
    files = _all_why_markdown()
    assert files, "skills/why 아래 md 파일 없음"
    offenders = [
        str(p.relative_to(_REPO_ROOT))
        for p in files
        if banned in p.read_text(encoding="utf-8")
    ]
    assert offenders == []


# ── 정규식 샘플 검증 (구현 무관, 정규식 자체) ─────────────────────────────────


@pytest.mark.parametrize(
    "sample",
    [
        "claude-4.5-opus-high",
        "claude-3-5-sonnet",
        "gpt4o",
        "gpt-5",
        "grok-4",
        "claude-opus-4-1",
        "gemini-2.5-pro",
    ],
)
def test_model_regex_matches_model_names(sample: str):
    assert _MODEL_NAME_RE.search(sample)


@pytest.mark.parametrize(
    "sample", ["claude-code", "Claude Code", "claude-api", "sonnet 모델"]
)
def test_model_regex_ignores_non_model_names(sample: str):
    assert _MODEL_NAME_RE.search(sample) is None
