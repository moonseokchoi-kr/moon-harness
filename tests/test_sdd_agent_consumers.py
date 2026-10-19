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


def _sections_list(path: Path) -> list[tuple[str, str, list[str]]]:
    """(상위 모드 헤딩, 제목, 줄 목록) 순서 목록. 같은 제목이 여러 번 나와도 모두 보존한다.

    상위 모드 헤딩 = 가장 가까운 `## ` 제목(`## ` 절 자신은 자기 제목). 줄 목록은 다음 헤딩 전까지.
    """
    sections: list[tuple[str, str, list[str]]] = []
    parent = ""
    in_code = False
    for line in _body_lines(path):
        if line.lstrip().startswith("```"):
            in_code = not in_code
        heading = None if in_code else re.match(r"^(#{2,3})\s+(.*)$", line)
        if heading:
            title = heading.group(2).strip()
            if len(heading.group(1)) == 2:
                parent = title
            sections.append((parent, title, []))
        elif sections:
            sections[-1][2].append(line)
    return sections


def _sections(path: Path) -> dict[str, list[str]]:
    """헤딩 제목 -> 줄 목록. 중복 제목은 덮어쓰지 않고 이어붙인다(모드 구분이 필요하면 _section(mode=))."""
    merged: dict[str, list[str]] = {}
    for _, title, lines in _sections_list(path):
        merged.setdefault(title, []).extend(lines)
    return merged


def _section(path: Path, title_pattern: str, mode: str | None = None) -> list[str]:
    """제목이 title_pattern에 매칭되는 절들의 줄. mode가 있으면 상위 `## ` 헤딩이 mode에 매칭되는 절만."""
    matches = [
        lines
        for parent, title, lines in _sections_list(path)
        if re.search(title_pattern, title) and (mode is None or re.search(mode, parent))
    ]
    assert matches, f"{path.name}: '{title_pattern}' (mode={mode}) 헤딩 절이 없다"
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

    def test_empty_design_decisions_fall_back_to_functional_requirements(self):
        lines = _section(COMPLIANCE, r"설계 준수")
        assert _any_line(lines, r"설계 결정", r"(?:비어|ARCH_SKIP)", r"기능 요구사항")
        assert _any_line(lines, r"헬퍼", r"P1", r"(?:내지 않|제기하지 않|금지)")

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
        """헬퍼 수정 후: verify 모드 절 + verify 모드의 작업 순서만 검사한다(이전엔 마지막 '작업 순서'=refactor를 봤음)."""
        verify = _section(TEST_AUTOMATOR, r"verify 모드")
        verify += _section(TEST_AUTOMATOR, r"^작업 순서$", mode=r"verify 모드")
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
        """헬퍼 수정 후: tdd 모드의 작업 순서를 검사한다(이전엔 마지막 '작업 순서'=refactor를 봐 검사 대상이 틀렸음)."""
        lines = _section(TEST_AUTOMATOR, r"^작업 순서$", mode=r"tdd 모드")
        assert _any_line(lines, r"시나리오|도출", r"spec")

    def test_manual_scenario_then_e2e_on_request_sentence(self):
        """핵심 행동 문장: E2E는 수동 확인 후 요청 시에만 작성한다."""
        lines = _body_lines(TEST_AUTOMATOR)
        assert _any_line(lines, r"E2E", r"수동", r"요청"), "E2E는 수동 확인 후 요청 시 문장이 없다"

    def test_manual_scenario_goes_to_result_doc(self):
        lines = _body_lines(TEST_AUTOMATOR)
        assert _any_line(lines, r"수동 테스트 시나리오")

    def test_verify_framework_selection_is_integration_layer_only(self):
        steps = _section(TEST_AUTOMATOR, r"^작업 순서$", mode=r"verify 모드")
        assert _any_line(steps, r"통합", r"레이어"), "verify 작업 순서에 통합 레이어 선택 줄이 없다"
        bare = [l for l in steps if re.search(r"E2E\s*레이어", l) and "요청" not in l]
        assert bare == [], f"요청 조건 없는 E2E 레이어 선택 지시: {bare}"

    def test_verify_e2e_framework_lines_carry_request_condition(self):
        steps = _section(TEST_AUTOMATOR, r"^작업 순서$", mode=r"verify 모드")
        pat = re.compile(r"Maestro|Playwright|Cypress|integration_test|E2E\s*기기")
        bare = [l for l in steps if pat.search(l) and "요청" not in l]
        assert bare == [], f"요청 조건 없는 E2E 프레임워크 줄: {bare}"

    def test_verify_output_e2e_lines_carry_request_marker(self):
        out = _section(TEST_AUTOMATOR, r"^출력 포맷$", mode=r"verify 모드")
        e2e = [l for l in out if "E2E" in l]
        assert e2e, "verify 출력 포맷에 E2E 항목이 없다"
        bare = [l for l in e2e if "요청 시" not in l]
        assert bare == [], f"'요청 시' 없는 E2E 출력 줄: {bare}"

    def test_missing_e2e_does_not_block_done_sentence(self):
        assert _any_line(_body_lines(TEST_AUTOMATOR), r"E2E", r"DONE", r"막지 않")

    def test_verify_output_has_manual_scenario_field(self):
        out = _section(TEST_AUTOMATOR, r"^출력 포맷$", mode=r"verify 모드")
        assert _any_line(out, r"수동 테스트 시나리오")

    def test_result_doc_written_by_orchestrator_not_automator(self):
        lines = _body_lines(TEST_AUTOMATOR)
        assert _any_line(lines, r"result 문서", r"직접 쓰지 않"), "result 문서 직접 쓰지 않는다는 문장이 없다"
        assert _any_line(lines, r"오케스트레이터", r"(?:옮|전달|기록)")

    def test_manual_scenario_trigger_is_spec_ui_section_or_task_test_type(self):
        steps = _section(TEST_AUTOMATOR, r"^작업 순서$", mode=r"verify 모드")
        assert _any_line(steps, r"spec", r"`## UI`")
        assert _any_line(steps, r"task", r"테스트 타입", r"E2E/UI")

    def test_refactor_edge_case_item_has_no_test_fitted_filler(self):
        steps = _section(TEST_AUTOMATOR, r"^작업 순서$", mode=r"refactor 모드")
        assert _any_line(steps, r"엣지 케이스")
        assert _hits(steps, re.compile(r"추가 시나리오")) == []

    def test_verify_integration_layer_still_mentions_e2e_frameworks(self):
        """E2E 프레임워크 지식 표 자체는 유지된다(요청 시 작성에 필요)."""
        text = "\n".join(_body_lines(TEST_AUTOMATOR))
        assert "Playwright" in text and "Maestro" in text


# ---------------------------------------------------------------- helper self-test


class TestSectionsHelper:
    def _doc(self, tmp_path: Path) -> Path:
        p = tmp_path / "doc.md"
        p.write_text(
            "---\nname: x\n---\n"
            "## A 모드\n### 작업 순서\nA-step\n### 출력 포맷\nA-out\n"
            "## B 모드\n### 작업 순서\nB-step\n### 출력 포맷\nB-out\n",
            encoding="utf-8",
        )
        return p

    def test_duplicate_titles_distinguished_by_mode(self, tmp_path):
        p = self._doc(tmp_path)
        assert _section(p, r"^작업 순서$", mode=r"^A") == ["A-step"]
        assert _section(p, r"^작업 순서$", mode=r"^B") == ["B-step"]
        assert _section(p, r"^출력 포맷$", mode=r"^A") == ["A-out"]

    def test_duplicate_titles_not_overwritten_without_mode(self, tmp_path):
        p = self._doc(tmp_path)
        assert _section(p, r"^작업 순서$") == ["A-step", "B-step"]
        assert _sections(p)["작업 순서"] == ["A-step", "B-step"]


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
