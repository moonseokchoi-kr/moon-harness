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


# ---- T-11 iteration 2: 리뷰 P1 반영 ----

def test_step1_claude_local_md_read_order_worktree_then_main_repo(step1: str) -> None:
    hits = _lines_with(step1, r"CLAUDE\.local\.md", r"worktree", r"git rev-parse --git-common-dir|메인 repo")
    assert hits
    assert any(
        re.search(r"worktree", ln).start() < re.search(r"git rev-parse --git-common-dir|메인 repo", ln).start()
        and re.search(r"없으면|이어서|다음", ln)
        for ln in hits
    )


def test_step1_result_persisted_to_main_repo_claude_local_md(step1: str) -> None:
    assert _lines_with(step1, r"CLAUDE\.local\.md", r"메인 repo 루트", r"재사용|사이클 간")
    assert _lines_with(step1, r"CLAUDE\.local\.md", r"worktree에만", r"메인.*(반영|복사|옮)")


def test_step1_state_records_source_file_path(step1: str) -> None:
    assert _lines_with(step1, r"출처", r"(읽은|확보한) 파일 경로", r"STATE|빌드 프로파일")


def test_step1_build_notes_only_in_interactive_context(step1: str) -> None:
    assert _lines_with(step1, r"build-notes", r"사용자 질문이 가능한", r"팀원", r"건너")


def test_step1_build_notes_skill_missing_or_denied_is_failure_and_continues(step1: str) -> None:
    assert _lines_with(step1, r"Skill", r"없음|거부", r"실패", r"다음 단계")


def test_step1_blocked_records_reason_in_state(step1: str) -> None:
    assert _lines_with(step1, r"BLOCKED", r"STATE", r"사유", r"기록")


def test_step1_blocked_resume_via_confirmed_profile_value(step1: str) -> None:
    assert _lines_with(step1, r"리드", r"재디스패치", r"빌드 프로파일 확정값")
    assert _lines_with(step1, r"확정값", r"## 빌드 프로파일", r"기록", r"BLOCKED.*반복|같은 BLOCKED")


def test_test_scope_filter_follows_profile_filter_syntax(skill_text: str) -> None:
    assert _lines_with(skill_text, r"\{filter\}", r"테스트 필터 문법", r"여러 개|복수")


def test_empty_test_scope_reports_task_doc_error_without_full_run(skill_text: str) -> None:
    assert _lines_with(skill_text, r"스코프", r"비(어|면)", r"전체 (테스트 )?실행", r"task 문서 오류", r"디스패치")


def test_step4_ui_criterion_is_spec_ui_section_or_task_test_type(skill_text: str) -> None:
    step4 = _section(_split_frontmatter(skill_text)[1], "Step 4")
    assert _lines_with(step4, r"`## UI`", r"E2E/UI|E2E|UI", r"테스트 타입", r"수동 테스트 시나리오")


# ---- T-11 iteration 3: 재리뷰 P1 반영 ----

def test_step1_main_repo_root_command_is_absolute_dirname_of_git_common_dir(step1: str) -> None:
    """`git rev-parse --git-common-dir`는 루트가 아니라 공통 .git 디렉터리를 반환한다(메인에선 상대경로일 수 있음).
    루트를 구하는 줄은 --path-format=absolute 와 dirname(또는 부모 디렉터리)을 함께 적어야 한다."""
    cmd_lines = _lines_with(step1, r"git-common-dir")
    assert cmd_lines, "메인 repo 루트를 구하는 명령 줄 없음"
    for ln in cmd_lines:
        assert re.search(r"--path-format=absolute", ln), f"절대경로 옵션 없음: {ln}"
        assert re.search(r"dirname|부모 디렉터리", ln), f"dirname/부모 디렉터리 없음: {ln}"


def test_step1_does_not_call_bare_git_common_dir_the_root(step1: str) -> None:
    bare = [
        ln for ln in _lines_with(step1, r"git rev-parse --git-common-dir", r"루트")
        if not re.search(r"--path-format=absolute", ln)
    ]
    assert not bare, f"맨 --git-common-dir를 루트라고 부르는 줄: {bare}"


def test_step1_claude_local_md_reflect_to_main_does_not_overwrite(step1: str) -> None:
    """worktree에만 생긴 CLAUDE.local.md를 '복사'로 반영하면 메인의 기존 CLAUDE.local.md(다른 내용)를 덮어쓴다.
    기존 내용을 보존하고 병합/추가하며, 메인에 파일이 없을 때만 새로 만든다."""
    reflect = _lines_with(step1, r"CLAUDE\.local\.md", r"worktree에만")
    assert reflect
    for ln in reflect:
        assert not re.search(r"복사", ln), f"덮어쓰기 지시(복사): {ln}"
    assert any(
        re.search(r"기존 내용", ln) and re.search(r"병합|append|추가", ln) for ln in reflect
    ), "기존 내용 보존 + 병합/append/추가 지시 없음"
    assert _lines_with(step1, r"메인", r"파일이 없을 때만", r"새로|만든|생성")


# ---- T-11 iteration 4: verify 변이 실험 보강 ----

def test_step4_manual_scenario_input_is_test_automator_report_field_moved_by_orchestrator(skill_text: str) -> None:
    step4 = _section(_split_frontmatter(skill_text)[1], "Step 4")
    hits = _lines_with(
        step4, r"test-automator", r"수동 테스트 시나리오", r"필드|보고", r"옮|result"
    )
    assert hits, "수동 시나리오 입력이 test-automator verify 보고 필드이고 오케스트레이터가 result로 옮긴다는 줄 없음"
    assert any(re.search(r"오케스트레이터", ln) and re.search(r"옮", ln) for ln in hits)


def test_step1_claude_md_precedes_claude_local_md(step1: str) -> None:
    claude = re.search(r"CLAUDE\.md(?!\S)", step1)
    local = re.search(r"CLAUDE\.local\.md", step1)
    assert claude and local
    assert claude.start() < local.start(), "확보 순서는 CLAUDE.md -> CLAUDE.local.md"


def test_step1_state_profile_present_means_no_reacquire(step1: str) -> None:
    assert _lines_with(step1, r"STATE", r"이미 있으면", r"재확보하지 않")
    assert not _lines_with(step1, r"STATE", r"이미 있어도", r"재확보한다")


def test_empty_test_scope_negations_kept(skill_text: str) -> None:
    hits = _lines_with(skill_text, r"스코프", r"비(어|면)", r"전체 (테스트 )?실행")
    assert any(re.search(r"하지 않|대체하지 않|금지", ln) for ln in hits)
    assert any(re.search(r"디스패치하지 않", ln) for ln in hits)
    assert not any(re.search(r"전체 실행으로 대체하고|Engineer를 디스패치한다", ln) for ln in hits)


def test_step4_e2e_only_when_requested(skill_text: str) -> None:
    step4 = _section(_split_frontmatter(skill_text)[1], "Step 4")
    assert _lines_with(step4, r"E2E", r"요청할 때만", r"작성")
    assert not _lines_with(step4, r"E2E", r"항상 작성")


def test_test_stage_forbids_full_run_substitution_and_keeps_no_clean(skill_text: str) -> None:
    stage = re.search(r"^### 2\.4 .*?\n(.*?)(?=^### |^## |\Z)", skill_text, re.DOTALL | re.MULTILINE)
    assert stage, "### 2.4 테스트 절 없음"
    body = stage.group(1)
    assert _lines_with(body, r"전체 테스트 1회 실행", r"대체 금지")
    assert not re.search(r"대체 가능", body)
    assert re.search(r"no-clean", body)
