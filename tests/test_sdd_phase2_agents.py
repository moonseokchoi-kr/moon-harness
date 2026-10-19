"""tests/test_sdd_phase2_agents.py — T-6 (F9, F14 architect 부분) 정적 검사.

architect 3종이 "같은 spec 문서의 설계 결정 섹션 보강 전용"으로 바뀌었는지,
삭제 대상 에이전트 4종이 `agents/`에서 사라졌는지 고정한다.
키워드가 파일 어딘가에 있는지가 아니라 해당 줄/절 안에 있는지를 검사한다.
네트워크/LLM 호출 없음.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
AGENTS = REPO / "agents"

REMOVED = [
    "sdd-ui-designer",
    "sdd-api-designer",
    "sdd-architect-reviewer",
    "sdd-context-manager",
]
ARCHITECTS = ["webapp-architect", "flutter-architect", "native-architect"]


def _body(name: str) -> str:
    """frontmatter(--- ... ---)를 제외한 본문."""
    path = AGENTS / f"{name}.md"
    assert path.is_file(), f"{path.relative_to(REPO)} 없음"
    text = path.read_text(encoding="utf-8")
    m = re.match(r"---\n.*?\n---\n", text, re.DOTALL)
    assert m, f"{name}: frontmatter 없음"
    return text[m.end():]


def _section(body: str, heading_regex: str) -> str:
    """`## ` 헤딩 하나가 heading_regex와 맞는 절의 본문(다음 `## ` 전까지)."""
    lines = body.splitlines()
    start = None
    for i, line in enumerate(lines):
        if re.match(r"##\s", line) and re.search(heading_regex, line):
            start = i + 1
            break
    assert start is not None, f"절 없음: {heading_regex}"
    out = []
    for line in lines[start:]:
        if re.match(r"##\s", line):
            break
        out.append(line)
    return "\n".join(out)


def _lines_matching(body: str, *patterns: str) -> list[str]:
    return [
        ln for ln in body.splitlines()
        if all(re.search(p, ln) for p in patterns)
    ]


@pytest.mark.parametrize("name", REMOVED)
def test_removed_agent_files_absent(name: str) -> None:
    assert not (AGENTS / f"{name}.md").exists()


@pytest.mark.parametrize("name", ARCHITECTS)
def test_architect_exists_with_frontmatter_name(name: str) -> None:
    text = (AGENTS / f"{name}.md").read_text(encoding="utf-8")
    assert re.search(rf"^name:\s*{re.escape(name)}\s*$", text, re.MULTILINE)


@pytest.mark.parametrize("name", ARCHITECTS)
def test_architect_body_has_no_arch_save_path(name: str) -> None:
    assert "docs/sdd/design/arch/" not in _body(name)


@pytest.mark.parametrize("name", ARCHITECTS)
def test_architect_body_has_no_build_profile(name: str) -> None:
    body = _body(name)
    assert "Build Profile" not in body
    assert not re.search(r"^##\s.*빌드 프로파일", body, re.MULTILINE)


@pytest.mark.parametrize("name", ARCHITECTS)
def test_architect_body_has_no_designer_references(name: str) -> None:
    body = _body(name)
    assert "ui-designer" not in body
    assert "api-designer" not in body


@pytest.mark.parametrize("name", ARCHITECTS)
def test_architect_augments_design_decisions_only_no_new_file(name: str) -> None:
    # 한 줄 안에 '설계 결정' + '보강' + '새 파일' + '금지'가 공존해야 한다.
    hits = _lines_matching(_body(name), r"설계 결정", r"보강", r"새 파일", r"금지")
    assert hits, f"{name}: '같은 문서의 설계 결정 섹션만 보강, 새 파일 금지' 줄 없음"


@pytest.mark.parametrize("name", ARCHITECTS)
def test_architect_augments_same_document(name: str) -> None:
    hits = _lines_matching(_body(name), r"같은 문서", r"설계 결정", r"보강")
    assert hits, f"{name}: '같은 문서' 설계 결정 보강 지침 줄 없음"


@pytest.mark.parametrize("name", ARCHITECTS)
def test_architect_targets_main_checkout_spec(name: str) -> None:
    # D18: Phase 2는 worktree 생성 전 -> 메인 체크아웃의 spec 파일을 보강.
    hits = _lines_matching(_body(name), r"worktree", r"메인 체크아웃", r"spec")
    assert hits, f"{name}: worktree 생성 전 메인 체크아웃 spec 보강 문구 없음"


@pytest.mark.parametrize("name", ARCHITECTS)
def test_architect_keeps_test_framework_section(name: str) -> None:
    section = _section(_body(name), r"Test Framework Knowledge")
    assert "|" in section, f"{name}: 프레임워크 표 없음"
    assert re.search(r"Unit", section)
    assert re.search(r"E2E", section)


@pytest.mark.parametrize("name", ARCHITECTS)
def test_architect_keeps_test_strategy_instruction(name: str) -> None:
    hits = _lines_matching(
        _body(name),
        r"Test strategy",
        r"framework per layer",
        r"unit / integration / E2E",
        r"test-automator",
    )
    assert hits, f"{name}: 테스트 전략 지침 줄 없음"
