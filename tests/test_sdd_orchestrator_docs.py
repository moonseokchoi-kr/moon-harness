"""T-11 (F12, F14): sdd-orchestrator 문서의 빌드 프로파일 확보 계약을 정적으로 고정한다."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "sdd-orchestrator" / "SKILL.md"
SCHEMA = ROOT / "skills" / "sdd-orchestrator" / "references" / "state-schema.md"
DISPATCH = ROOT / "skills" / "sdd-orchestrator" / "references" / "agent-dispatch-guide.md"


def _split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    match = re.match(r"---\n(.*?)\n---\n(.*)", text, re.DOTALL)
    assert match, "frontmatter 없음"
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip()] = value.strip()
    return fields, match.group(2)


def _section(body: str, heading_prefix: str) -> str:
    """`## <heading_prefix>...` 절 본문을 다음 `## ` 헤딩 전까지 반환한다."""
    pattern = rf"^## {re.escape(heading_prefix)}.*?\n(.*?)(?=^## |\Z)"
    match = re.search(pattern, body, re.DOTALL | re.MULTILINE)
    assert match, f"절 없음: {heading_prefix}"
    return match.group(1)


@pytest.fixture(scope="module")
def skill_text() -> str:
    return SKILL.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def frontmatter(skill_text: str) -> dict[str, str]:
    return _split_frontmatter(skill_text)[0]


@pytest.fixture(scope="module")
def step1(skill_text: str) -> str:
    return _section(_split_frontmatter(skill_text)[1], "Step 1")


@pytest.fixture(scope="module")
def schema_text() -> str:
    return SCHEMA.read_text(encoding="utf-8")


def _lines_with(text: str, *patterns: str) -> list[str]:
    """모든 패턴이 같은 줄에 있는 줄만 반환한다."""
    return [ln for ln in text.splitlines() if all(re.search(p, ln) for p in patterns)]


# ---- frontmatter ----

def test_allowed_tools_includes_skill_and_keeps_existing(frontmatter: dict[str, str]) -> None:
    tokens = frontmatter["allowed-tools"].split()
    assert "Skill" in tokens
    for existing in ("Bash", "Read", "Write", "Edit", "Glob", "Grep", "Agent"):
        assert existing in tokens


# ---- Step 1: 확보 순서 ----

def test_step1_acquisition_order(step1: str) -> None:
    # 확보 절차 줄(번호 항목)에서 네 키워드가 이 순서로 나타나야 한다.
    ordered = [r"CLAUDE\.md(?!\S)", r"CLAUDE\.local\.md", r"/build-notes", r"사용자 질문|사용자에게 질문"]
    pos = -1
    for pat in ordered:
        found = [m.start() for m in re.finditer(pat, step1) if m.start() > pos]
        assert found, f"순서 위반 또는 누락: {pat}"
        pos = found[0]


def test_step1_reuses_state_profile_without_reacquiring(step1: str) -> None:
    hits = _lines_with(step1, r"STATE", r"이미|있으면", r"재확보|다시 확보|확보하지|건너뛴")
    assert hits, "STATE에 프로파일이 이미 있으면 재확보하지 않는다는 문장 없음"


def test_step1_records_profile_into_state(step1: str) -> None:
    assert _lines_with(step1, r"## 빌드 프로파일", r"기록")


def test_step1_build_notes_absence_is_normal_and_falls_back_to_user(step1: str) -> None:
    hits = _lines_with(step1, r"build-notes", r"없|부재|불가", r"사용자")
    assert hits, "build-notes 부재 시 사용자 질문 폴백 문장 없음"


def test_step1_build_notes_is_not_migrated_into_plugin(step1: str) -> None:
    assert _lines_with(step1, r"build-notes", r"전역", r"이관").__len__() >= 1


def test_step1_build_notes_result_goes_via_claude_local(step1: str) -> None:
    assert _lines_with(step1, r"build-notes", r"CLAUDE\.local\.md", r"STATE")


def test_step1_team_context_returns_blocked(step1: str) -> None:
    hits = _lines_with(step1, r"BLOCKED", r"리드|team-leader")
    assert hits, "팀원 컨텍스트 BLOCKED 반환 + 리드 중계 문장 없음"
    assert any(re.search(r"팀원|sdd-team-leader", ln) for ln in hits)
    assert any(re.search(r"중계", ln) for ln in hits)


def test_step1_no_phase2_rollback_language(step1: str) -> None:
    assert not re.search(r"Phase 2 미발견", step1)
    assert not re.search(r"Phase 2(로|으로)? ?롤백", step1)


# ---- build-aware TDD 3원칙 / 스키마 유지 ----

def test_step1_keeps_warmup_once(step1: str) -> None:
    assert _lines_with(step1, r"워밍업", r"1회")
    assert _lines_with(step1, r"워밍업 완료")
    assert _lines_with(step1, r"fast-scoped", r"워밍업", r"생략")


def test_three_principles_kept(skill_text: str) -> None:
    assert _lines_with(skill_text, r"build-aware TDD", r"증분 빌드", r"스코프 테스트", r"no-clean")
    assert _lines_with(skill_text, r"워밍업 빌드 캐시", r"보존|per-task 증분")
    assert _lines_with(skill_text, r"clean 금지", r"증분 빌드만")


def test_state_schema_profile_table_kept(schema_text: str) -> None:
    for field in ("유형", "워밍업 빌드", "증분 빌드", "테스트 실행", "테스트 필터 문법", "clean 정책"):
        assert re.search(rf"^\| {re.escape(field)} \|", schema_text, re.MULTILINE), field
    assert re.search(r"\{filter\}", schema_text)
    assert re.search(r"워밍업 완료", schema_text)


# ---- state-schema.md ----

def test_state_schema_no_taskmaster_copy(schema_text: str) -> None:
    assert "taskmaster가 복사" not in schema_text
    block = schema_text.split("## 빌드 프로파일")[1].split("## 팀 배정")[0]
    assert "taskmaster" not in block


def test_state_schema_profile_recorded_by_orchestrator_at_phase4(schema_text: str) -> None:
    block = schema_text.split("## 빌드 프로파일")[1].split("## 팀 배정")[0]
    assert _lines_with(block, r"오케스트레이터가 Phase 4 진입 시 기록")
    assert not re.search(r"arch 문서의 `## 빌드 프로파일`", block)


def test_state_schema_meta_uses_spec_single_document(schema_text: str) -> None:
    meta = schema_text.split("## 메타")[1].split("## 빌드 프로파일")[0]
    assert not re.search(r"develop 문서", meta)
    assert re.search(r"^- spec 문서:", meta, re.MULTILINE)


# ---- F14: 단일 문서 프롬프트 ----

FORBIDDEN_PATHS = r"design/(arch|ui|api)"


def test_skill_has_no_split_design_doc_paths(skill_text: str) -> None:
    assert not re.search(FORBIDDEN_PATHS, skill_text)


def test_engineer_dispatch_prompt_references_spec(skill_text: str) -> None:
    hits = _lines_with(skill_text, r"prompt:", r"task 문서 경로", r"spec")
    assert hits, "Engineer 디스패치 prompt가 spec 단일 문서를 참조하지 않음"


def test_compliance_dispatch_prompt_references_spec_only(skill_text: str) -> None:
    hits = _lines_with(skill_text, r"sdd-compliance-checker", r"spec", r"변경 파일")
    assert hits
    assert not any(re.search(r"\barch\b|\bui\b|\bapi\b", ln) for ln in hits)


def test_schema_and_dispatch_guide_have_no_split_design_paths(schema_text: str) -> None:
    assert not re.search(FORBIDDEN_PATHS, schema_text)
    if DISPATCH.exists():
        assert not re.search(FORBIDDEN_PATHS, DISPATCH.read_text(encoding="utf-8"))


# ---- F12 스캔 패턴 ----

F12_SCAN = re.compile(
    r"docs/sdd/design/arch|Build Profile|arch 문서의 .*## 빌드 프로파일|taskmaster가 복사"
)


@pytest.mark.parametrize("path", [SKILL, SCHEMA, DISPATCH], ids=lambda p: p.name)
def test_f12_scan_pattern_absent(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    assert not F12_SCAN.search(text)


# ---- 경로 하드코딩 금지 (W4, W6) ----

def test_step1_does_not_hardcode_interpreter_or_home_paths(step1: str) -> None:
    assert not re.search(r"/opt/homebrew|/usr/local|PATH=|/Users/|~/\.claude", step1)


# ---- F13: 수동 테스트 시나리오 ----

def test_step4_result_records_manual_test_scenarios_for_ui(skill_text: str) -> None:
    step4 = _section(_split_frontmatter(skill_text)[1], "Step 4")
    assert _lines_with(step4, r"수동 테스트 시나리오", r"result")
    assert _lines_with(step4, r"UI", r"수동 테스트 시나리오|result")
    assert _lines_with(step4, r"E2E", r"요청", r"작성")
