"""tests/test_sdd_agent_consumers.py — 소비자 에이전트 단일 문서·E2E 정책 정적 검사 (spec F13, F14, T-10).

오프라인 전용. 네트워크/LLM 무호출. 헤딩 단위 절 추출 + 줄 단위 정규식으로 검사한다.
frontmatter는 본문 검사에서 제외한다(description은 별도 절로 검사).
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENTS = REPO_ROOT / "agents"

COMPLIANCE = AGENTS / "sdd-compliance-checker.md"
TEST_AUTOMATOR = AGENTS / "sdd-test-automator.md"
BLOCKER = AGENTS / "sdd-blocker-checker.md"
REACT = AGENTS / "sdd-react-specialist.md"
IMPLEMENTER = AGENTS / "sdd-implementer.md"

DELETED_AGENTS = re.compile(
    r"ui-designer|api-designer|context-manager|architect-reviewer"
)
DESIGN_PATHS = re.compile(r"design/(?:arch|ui|api)\b")
DESIGN_MD = re.compile(r"DESIGN\.md")
E2E_CONFIG = re.compile(r"e2e-config")


def _split(path: Path) -> tuple[str, str]:
    assert path.is_file(), f"{path} 가 없다"
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\n(.*?)\n---\n(.*)\Z", text, re.DOTALL)
    assert match, f"{path.name}: frontmatter가 없다"
    return match.group(1), match.group(2)


def _body_lines(path: Path) -> list[str]:
    return _split(path)[1].splitlines()


def _sections(path: Path) -> dict[str, list[str]]:
    """헤딩(## / ###) 제목 -> 해당 절의 줄 목록(하위 헤딩 전까지)."""
    sections: dict[str, list[str]] = {}
    current = None
    in_code = False
    for line in _body_lines(path):
        if line.lstrip().startswith("```"):
            in_code = not in_code
        heading = None if in_code else re.match(r"^#{2,3}\s+(.*)$", line)
        if heading:
            current = heading.group(1).strip()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    return sections


def _section(path: Path, title_pattern: str) -> list[str]:
    matches = [
        lines
        for title, lines in _sections(path).items()
        if re.search(title_pattern, title)
    ]
    assert matches, f"{path.name}: '{title_pattern}' 헤딩 절이 없다"
    return [line for lines in matches for line in lines]


def _hits(lines: list[str], pattern: re.Pattern) -> list[str]:
    return [line for line in lines if pattern.search(line)]


def _any_line(lines: list[str], *patterns: str) -> bool:
    """한 줄 안에서 모든 정규식이 동시에 매칭되는 줄이 있는가."""
    return any(all(re.search(p, line) for p in patterns) for line in lines)


# ---------------------------------------------------------------- compliance-checker


class TestComplianceChecker:
    def test_no_design_doc_paths(self):
        assert _hits(_body_lines(COMPLIANCE), DESIGN_PATHS) == []

    def test_no_deleted_agents_or_design_md(self):
        lines = _body_lines(COMPLIANCE)
        assert _hits(lines, DELETED_AGENTS) == []
        assert _hits(lines, DESIGN_MD) == []

    def test_no_design_mode_full_branch(self):
        """설계 모드 FULL/SIMPLE 분기가 없다 (TDD FULL은 이 에이전트 대상이 아님)."""
        lines = _body_lines(COMPLIANCE)
        assert _hits(lines, re.compile(r"FULL\s*모드|SIMPLE\s*모드|\(FULL|\(SIMPLE")) == []

    def test_no_separate_arch_doc_input(self):
        lines = _body_lines(COMPLIANCE)
        assert _hits(lines, re.compile(r"arch\s*문서|arch/ui/api|arch/api/ui|ui/api\s*명세")) == []

    def test_description_has_no_separate_design_docs(self):
        frontmatter, _ = _split(COMPLIANCE)
        assert not re.search(r"arch/ui/api|design/", frontmatter)

    def test_input_section_uses_single_spec_document(self):
        lines = _section(COMPLIANCE, r"^입력")
        assert _any_line(lines, r"spec", r"(?:단일|설계 결정)"), "입력에 spec 단일 문서/설계 결정이 없다"

    def test_input_section_has_ui_link_only_when_present(self):
        lines = _section(COMPLIANCE, r"^입력")
        assert _any_line(lines, r"UI", r"(?:링크|섹션)", r"(?:있을 때|있는 경우|있으면)")

    def test_design_compliance_checks_spec_design_decisions(self):
        lines = _section(COMPLIANCE, r"설계 준수")
        assert _any_line(lines, r"spec", r"설계 결정")

    def test_design_compliance_checks_ui_link_and_functional_requirements(self):
        lines = _section(COMPLIANCE, r"설계 준수")
        assert _any_line(lines, r"UI", r"(?:링크|섹션)")
        assert _any_line(lines, r"기능 요구사항")


# ---------------------------------------------------------------- test-automator


class TestTestAutomator:
    def test_no_mandatory_e2e_strings(self):
        text = "\n".join(_body_lines(TEST_AUTOMATOR))
        for needle in ("E2E 필수", "E2E 없이 DONE"):
            assert needle not in text, f"'{needle}' 가 남아 있다"

    def test_no_e2e_config_or_design_paths(self):
        lines = _body_lines(TEST_AUTOMATOR)
        assert _hits(lines, E2E_CONFIG) == []
        assert _hits(lines, DESIGN_PATHS) == []
        assert _hits(lines, DESIGN_MD) == []

    def test_no_e2e_red_first(self):
        """View/UI 구현 전 E2E RED 선행 규칙이 없다."""
        lines = _body_lines(TEST_AUTOMATOR)
        assert _hits(lines, re.compile(r"E2E\s*RED|E2E.{0,20}RED\s*선행|RED.{0,20}E2E\s*선행")) == []

    def test_no_ui_exists_blocks_done_rule(self):
        lines = _body_lines(TEST_AUTOMATOR)
        pattern = re.compile(r"(?:UI|View).{0,40}(?:E2E).{0,40}(?:DONE\s*반환\s*금지|BLOCKED)")
        assert _hits(lines, pattern) == []

    def test_no_e2e_failure_forces_blocked(self):
        verify = _section(TEST_AUTOMATOR, r"verify 모드")
        verify += _section(TEST_AUTOMATOR, r"^작업 순서$")
        pattern = re.compile(r"E2E.{0,30}실패.{0,30}BLOCKED")
        assert _hits(verify, pattern) == []

    def test_inputs_reference_spec_not_arch_or_api_docs(self):
        lines = _body_lines(TEST_AUTOMATOR)
        pattern = re.compile(r"arch\s*문서|api\s*명세|arch\s*테스트\s*전략|arch에\s*명시|api/ui\s*명세|ui/api\s*명세")
        assert _hits(lines, pattern) == []

    def test_common_input_uses_single_spec_document(self):
        lines = _section(TEST_AUTOMATOR, r"^입력$") + _section(TEST_AUTOMATOR, r"^공통$")
        assert _any_line(lines, r"spec", r"(?:단일 문서|테스트 전략|설계 결정)")

    def test_tdd_scenarios_derived_from_spec(self):
        lines = _section(TEST_AUTOMATOR, r"작업 순서")
        assert _any_line(lines, r"시나리오|도출", r"spec")

    def test_manual_scenario_then_e2e_on_request_sentence(self):
        """핵심 행동 문장: E2E는 수동 확인 후 요청 시에만 작성한다."""
        lines = _body_lines(TEST_AUTOMATOR)
        assert _any_line(lines, r"E2E", r"수동", r"요청"), "E2E는 수동 확인 후 요청 시 문장이 없다"

    def test_manual_scenario_goes_to_result_doc(self):
        lines = _body_lines(TEST_AUTOMATOR)
        assert _any_line(lines, r"수동 테스트 시나리오")

    def test_verify_integration_layer_still_mentions_e2e_frameworks(self):
        """E2E 프레임워크 지식 표 자체는 유지된다(요청 시 작성에 필요)."""
        text = "\n".join(_body_lines(TEST_AUTOMATOR))
        assert "Playwright" in text and "Maestro" in text


# ---------------------------------------------------------------- blocker-checker


class TestBlockerChecker:
    def test_no_deleted_agent_names(self):
        assert _hits(_body_lines(BLOCKER), DELETED_AGENTS) == []

    def test_no_design_paths(self):
        lines = _body_lines(BLOCKER)
        assert _hits(lines, DESIGN_PATHS) == []
        assert _hits(lines, DESIGN_MD) == []

    def test_platform_rationale_names_phase_2_3_design_stage(self):
        lines = _section(BLOCKER, r"플랫폼/스택 미확정 판단 기준")
        assert _any_line(lines, r"Phase\s*2", r"3", r"설계 단계")

    def test_platform_blocked_criteria_kept(self):
        lines = _section(BLOCKER, r"플랫폼/스택 미확정 판단 기준")
        assert _any_line(lines, r"BLOCKED")
        assert _any_line(lines, r"대상 플랫폼")


# ---------------------------------------------------------------- react-specialist


class TestReactSpecialist:
    def test_no_design_md_or_deleted_agents(self):
        lines = _body_lines(REACT)
        assert _hits(lines, DESIGN_MD) == []
        assert _hits(lines, DELETED_AGENTS) == []
        assert _hits(lines, DESIGN_PATHS) == []

    def test_no_ui_spec_document_input_assumption(self):
        lines = _body_lines(REACT)
        assert _hits(lines, re.compile(r"UI\s*명세\s*문서")) == []

    def test_ui_conversion_uses_spec_ui_section_link_when_present(self):
        lines = _section(REACT, r"코드 변환")
        assert _any_line(lines, r"spec", r"UI\s*섹션", r"(?:링크)", r"(?:있을 때|있는 경우|있으면)")

    def test_ui_conversion_section_still_exists_with_component_tree(self):
        lines = _section(REACT, r"코드 변환")
        assert _any_line(lines, r"컴포넌트")


# ---------------------------------------------------------------- Preserve (회귀 고정)


class TestPreserve:
    def test_react_specialist_keeps_tdd_full_markers(self):
        lines = _body_lines(REACT)
        assert len(_hits(lines, re.compile(r"\[TDD == FULL\]"))) >= 3

    def test_implementer_keeps_tdd_full_markers(self):
        assert _hits(_body_lines(IMPLEMENTER), re.compile(r"\[TDD == FULL\]"))

    def test_engineer_agents_keep_develop_doc_term(self):
        files = sorted(AGENTS.glob("sdd-*-engineer.md"))
        assert files
        assert any("develop 문서" in p.read_text(encoding="utf-8") for p in files)

    def test_test_automator_tdd_mode_still_defined(self):
        lines = _body_lines(TEST_AUTOMATOR)
        assert _any_line(lines, r"tdd 모드", r"RED")

    @pytest.mark.parametrize("path", [COMPLIANCE, TEST_AUTOMATOR, BLOCKER, REACT])
    def test_agent_frontmatter_has_name_and_description(self, path):
        frontmatter, _ = _split(path)
        assert re.search(r"^name:\s*\S+", frontmatter, re.MULTILINE)
        assert re.search(r"^description:\s*\S+", frontmatter, re.MULTILINE)
