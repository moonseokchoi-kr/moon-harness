"""tests/test_sdd_task_docs.py — T-9 (F10, F11, F14) 정적 검사.

`agents/sdd-taskmaster.md`, `skills/sdd-taskrunner/SKILL.md`,
`skills/sdd-taskrunner/assets/templates/task-document.md`가 spec 단일 문서
기준으로 전환됐는지 절/줄 단위로 고정한다. 네트워크/LLM 호출 없음.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
TASKMASTER = REPO / "agents" / "sdd-taskmaster.md"
RUNNER = REPO / "skills" / "sdd-taskrunner" / "SKILL.md"
TEMPLATE = REPO / "skills" / "sdd-taskrunner" / "assets" / "templates" / "task-document.md"

# spec F12 Acceptance의 rg 패턴(이 태스크 소유 파일 범위에서 0건).
F12_PATTERN = re.compile(
    r"docs/sdd/design/arch|Build Profile|arch 문서의 .*## 빌드 프로파일|taskmaster가 복사"
)
DESIGN_PATH = re.compile(r"design/(arch|ui|api)")
ARCH_UI_API = re.compile(r"arch\s*/\s*ui\s*/\s*api")


def _read(path: Path) -> str:
    assert path.is_file(), f"{path.relative_to(REPO)} 없음"
    return path.read_text(encoding="utf-8")


def _split_frontmatter(text: str) -> tuple[str, str]:
    m = re.match(r"---\n(.*?)\n---\n", text, re.DOTALL)
    assert m, "frontmatter 없음"
    return m.group(1), text[m.end():]


def _body(path: Path) -> str:
    text = _read(path)
    if text.startswith("---\n"):
        return _split_frontmatter(text)[1]
    return text


def _section(text: str, heading: str, level: int = 2) -> str:
    """`#`*level + ' ' + heading 으로 시작하는 절 본문(다음 동급 이상 헤딩 전까지)."""
    lines = text.splitlines()
    marker = "#" * level + " "
    start = None
    for i, line in enumerate(lines):
        if line.startswith(marker + heading):
            start = i + 1
            break
    assert start is not None, f"절 없음: {heading}"
    out: list[str] = []
    for line in lines[start:]:
        m = re.match(r"(#+) ", line)
        if m and len(m.group(1)) <= level:
            break
        out.append(line)
    return "\n".join(out)


def _mode_section(text: str, name: str) -> str:
    """`## 모드 N: {name}` 형태 헤딩의 절 본문. 번호는 가정하지 않는다."""
    for line in text.splitlines():
        m = re.match(r"## 모드 \S+:\s*" + re.escape(name) + r"\b", line)
        if m:
            return _section(text, line[3:].strip().split(":")[0])
    raise AssertionError(f"모드 절 없음: {name}")


def _lines(text: str) -> list[str]:
    return text.splitlines()


def _any_line(text: str, *patterns: str) -> bool:
    regs = [re.compile(p) for p in patterns]
    return any(all(r.search(line) for r in regs) for line in _lines(text))


# ---------------------------------------------------------------- taskmaster


def test_taskmaster_frontmatter_valid():
    fm, _ = _split_frontmatter(_read(TASKMASTER))
    assert re.search(r"^name:\s*sdd-taskmaster\s*$", fm, re.M)
    assert re.search(r"^description:", fm, re.M)


def test_taskmaster_frontmatter_has_no_design_docs():
    fm, _ = _split_frontmatter(_read(TASKMASTER))
    assert not ARCH_UI_API.search(fm), "description이 arch/ui/api 설계 문서를 가리킴"
    assert "spec" in fm


@pytest.mark.parametrize("needle", ["design/arch", "design/ui", "design/api", "FULL 모드"])
def test_taskmaster_forbidden_strings_absent(needle):
    assert needle not in _read(TASKMASTER)


def test_taskmaster_has_no_arch_ui_api_document_references():
    body = _body(TASKMASTER)
    offenders = [ln for ln in _lines(body) if ARCH_UI_API.search(ln)]
    assert not offenders, offenders
    offenders = [ln for ln in _lines(body) if re.search(r"(arch|ui|api) (문서|명세) 경로", ln)]
    assert not offenders, offenders


def test_taskmaster_f12_rg_pattern_zero():
    offenders = [ln for ln in _lines(_read(TASKMASTER)) if F12_PATTERN.search(ln)]
    assert not offenders, offenders


def test_taskmaster_no_profile_blocked_line():
    offenders = [ln for ln in _lines(_read(TASKMASTER)) if re.search(r"프로파일.*BLOCKED", ln)]
    assert not offenders, offenders


def test_taskmaster_keeps_general_return_contract():
    assert _any_line(_read(TASKMASTER), r"\*\*Status:\*\*\s*DONE \| NEEDS_CONTEXT \| BLOCKED")


def test_taskmaster_mentions_implementation_plan():
    assert "구현 계획" in _body(TASKMASTER)


def test_taskmaster_input_is_single_spec_worktree_feature_mode():
    section = _section(_body(TASKMASTER), "입력")
    items = [ln for ln in _lines(section) if ln.startswith("- ")]
    assert any(re.search(r"spec.*경로", ln) for ln in items), "spec 경로 입력 없음"
    assert any("worktree 경로" in ln for ln in items)
    assert any("feature" in ln for ln in items)
    assert any(re.search(r"모드.*tasks.*dag", ln) for ln in items)
    assert any(re.search(r"모드", ln) and re.search(r"`plan`", ln) for ln in items), (
        "입력 절의 모드 값에 plan 없음"
    )
    assert not [ln for ln in items if re.search(r"\b(arch|ui|api)\b.*(경로|명세)", ln)]
    assert len(items) == 4, f"입력 항목은 spec/worktree/feature/모드 4개: {items}"


def test_taskmaster_tasks_mode_reads_only_spec():
    section = _section(_body(TASKMASTER), "모드 1")
    assert _any_line(section, r"\*\*문서 읽기\*\*", r"spec")
    assert not _any_line(section, r"\*\*문서 읽기\*\*", r"arch|\bui\b|\bapi\b")


def test_taskmaster_tasks_mode_derives_from_spec_not_design_docs():
    section = _section(_body(TASKMASTER), "모드 1")
    assert not [ln for ln in _lines(section) if re.search(r"\barch\b|\bui\b|\bapi\b", ln)], (
        "tasks 모드 절에 arch/ui/api 설계 문서 참조가 남음"
    )


def test_taskmaster_verification_step_writes_test_scope_only():
    section = _section(_body(TASKMASTER), "모드 1")
    step = [ln for ln in _lines(section) if re.match(r"\s*10\.", ln)]
    assert len(step) == 1, "10번 단계 줄이 하나여야 함"
    line = step[0]
    assert "검증 명령어" in line
    assert "테스트 스코프" in line
    assert re.search(r"(빌드|테스트 실행)[^.]*명령[^.]*(적지|쓰지|기입하지) 않", line), (
        "실제 빌드·테스트 명령을 적지 않는다는 문장 없음"
    )
    assert not re.search(r"arch 문서|프로파일 섹션|{filter}", line)
    assert not re.search(r"프로파일.*(읽어|찾아)", line), "프로파일을 찾지 않아야 함"


def test_taskmaster_does_not_search_build_profile_anywhere():
    body = _body(TASKMASTER)
    offenders = [
        ln for ln in _lines(body)
        if re.search(r"프로파일", ln) and re.search(r"(읽어|읽는다|찾아|찾는다|기입한다|복사한다)", ln)
        and not re.search(r"않", ln)
    ]
    assert not offenders, offenders


def test_taskmaster_dag_mode_does_not_copy_profile_to_state():
    section = _section(_body(TASKMASTER), "모드 2")
    state_step = [ln for ln in _lines(section) if "ORCHESTRATOR_STATE.md 초기 생성" in ln]
    assert state_step, "dag 모드 STATE 생성 단계 없음"
    assert not [ln for ln in _lines(section) if "빌드 프로파일 메타" in ln]
    assert _any_line(section, r"프로파일", r"(복사하지|복사 안|복사를 하지) ?않|STATE로 복사하지")
    assert not [ln for ln in _lines(section) if re.search(r"arch.*프로파일|프로파일.*arch", ln)]


def test_taskmaster_dag_state_meta_points_to_spec_only():
    section = _section(_body(TASKMASTER), "모드 2")
    meta = [ln for ln in _lines(section) if ln.strip().startswith("- 메타 정보")]
    assert len(meta) == 1
    assert "spec" in meta[0]
    assert not re.search(r"arch|\bui\b|\bapi\b", meta[0])


def test_taskmaster_rules_no_design_decisions_outside_spec():
    section = _section(_body(TASKMASTER), "규칙")
    assert _any_line(section, r"spec", r"(없는|벗어난) 설계 결정", r"임의로 하지 않는다")
    assert not [ln for ln in _lines(section) if ARCH_UI_API.search(ln)]


def test_taskmaster_rules_keep_scope_guards():
    section = _section(_body(TASKMASTER), "규칙")
    assert _any_line(section, r"구현 코드를 작성하지 않는다")
    assert _any_line(section, r"spec에 없는 기능의 태스크를 추가하지 않는다")


def test_taskmaster_rules_state_plan_section_ownership():
    section = _section(_body(TASKMASTER), "규칙")
    assert _any_line(section, r"`## 구현 계획`", r"순서", r"위험", r"테스트 스코프"), (
        "구현 계획 작성 범위(순서·위험·테스트 스코프) 규칙 없음"
    )
    assert _any_line(section, r"다른 섹션", r"(수정|변경|덮어쓰|건드리)[^.]*(않|금지)"), (
        "다른 섹션 수정 금지 소유권 규칙 없음"
    )


def test_taskmaster_plan_mode_writes_plan_into_spec():
    """갱신(구 test_taskmaster_tasks_mode_writes_plan_into_spec): 리드 결정으로 구현 계획 작성
    주체가 tasks 모드에서 plan 모드로 이동했다. 같은 요구(spec에 `## 구현 계획`을 쓴다)를
    plan 모드 절로 옮겨 유지한다."""
    section = _mode_section(_body(TASKMASTER), "plan")
    assert _any_line(section, r"`## 구현 계획`", r"spec"), "plan 모드가 spec에 구현 계획을 쓰지 않음"


def test_taskmaster_plan_step_specifies_edit_section_only_and_forbids_spec_write():
    """갱신: Edit 섹션 한정 + Write 금지 단언을 plan 모드 절로 이동(작성 주체 변경)."""
    section = _mode_section(_body(TASKMASTER), "plan")
    assert _any_line(section, r"Edit", r"`## 구현 계획`", r"(섹션만|범위만)"), (
        "구현 계획 작성 단계가 Edit로 `## 구현 계획` 섹션만 갱신한다고 명시하지 않음"
    )
    assert _any_line(section, r"Write", r"spec", r"(쓰지 않|금지)"), (
        "Write로 spec 전체를 재작성하지 않는다는 금지 문장 없음"
    )


def test_taskmaster_plan_written_once_by_plan_mode_alone():
    """갱신(구 test_taskmaster_plan_written_once_per_tasks_mode_with_explicit_owner).
    구 단언은 'tasks 모드 안의 단일 인스턴스(첫 배치/컨트롤러 지정)'가 구현 계획을 1회 쓴다고
    요구했으나, 병렬 tasks 인스턴스 중 누가 쓸지의 결정 주체·신호가 없다는 리뷰 P1 때문에
    리드가 plan 모드(단독 1회 디스패치)로 분리했다. 따라서 '구현 계획은 plan 모드 단독 1회가
    쓴다'는 한 줄 요구로 바꾼다. 작성 주체를 명시한다는 원래 의도는 유지된다."""
    section = _mode_section(_body(TASKMASTER), "plan")
    assert _any_line(section, r"`## 구현 계획`", r"(단독|한 번만|1회)"), (
        "구현 계획은 plan 모드 단독 1회가 쓴다는 문장 없음"
    )


def test_taskmaster_plan_mode_does_not_create_task_documents():
    section = _mode_section(_body(TASKMASTER), "plan")
    assert _any_line(section, r"task 문서", r"(만들지 않|생성하지 않|작성하지 않)"), (
        "plan 모드가 task 문서를 만들지 않는다는 문장 없음"
    )


def test_taskmaster_plan_mode_is_single_dispatch():
    section = _mode_section(_body(TASKMASTER), "plan")
    assert _any_line(section, r"단독", r"(디스패치|호출|실행)"), "plan 모드 단독 디스패치 문장 없음"


def test_taskmaster_tasks_mode_spec_is_read_only():
    section = _mode_section(_body(TASKMASTER), "tasks")
    section = section.split("### 배치 제한")[0]  # 배치 제한 절의 기존 문장과 별개로 작업 순서 쪽에 있어야 함
    assert _any_line(section, r"spec", r"(읽기 전용|읽기만)", r"(쓰지 않|쓰기 금지|금지)"), (
        "tasks 모드 절에 spec 읽기 전용(쓰기 금지) 문장 없음"
    )


def test_taskmaster_tasks_mode_uses_existing_plan_as_input():
    section = _mode_section(_body(TASKMASTER), "tasks")
    assert _any_line(section, r"구현 계획", r"(입력|읽어|읽는다)"), (
        "tasks 모드가 작성된 구현 계획을 입력으로 쓴다는 문장 없음"
    )


def test_taskmaster_tasks_mode_reports_needs_context_when_plan_missing():
    section = _mode_section(_body(TASKMASTER), "tasks")
    assert _any_line(section, r"구현 계획", r"(없|부재)", r"NEEDS_CONTEXT"), (
        "구현 계획 부재 시 NEEDS_CONTEXT 보고 문장 없음"
    )
    assert _any_line(section, r"NEEDS_CONTEXT", r"plan 모드"), "plan 모드 선행 필요 안내 없음"


def test_taskmaster_tasks_mode_does_not_write_plan():
    section = _mode_section(_body(TASKMASTER), "tasks")
    assert not _any_line(section, r"구현 계획", r"(추가|교체|갱신)[^.]*(한다|\.|$)", r"Edit"), (
        "tasks 모드에 구현 계획을 Edit로 쓰는 단계가 남음"
    )


def test_taskmaster_batch_limit_applies_to_tasks_mode_only():
    section = _section(_body(TASKMASTER), "배치 제한", level=3)
    assert _any_line(section, r"tasks 모드", r"(만|에만|한정)"), (
        "배치 제한이 tasks 모드에만 적용된다는 문장 없음"
    )


def test_taskmaster_batch_limit_section_keeps_parallel_instances_spec_read_only():
    section = _section(_body(TASKMASTER), "배치 제한", level=3)
    assert _any_line(section, r"spec", r"(읽기 전용|읽기만)", r"(쓰지 않|쓰기 금지|금지)"), (
        "배치 제한 절에 병렬 인스턴스의 spec 읽기 전용(쓰기 금지) 문장 없음"
    )


def test_taskmaster_no_blocked_on_missing_arch():
    body = _body(TASKMASTER)
    offenders = [ln for ln in _lines(body) if re.search(r"arch.*BLOCKED|BLOCKED.*arch", ln)]
    assert not offenders, offenders


# ---------------------------------------------------------------- taskrunner


def test_taskrunner_skill_frontmatter_valid():
    fm, _ = _split_frontmatter(_read(RUNNER))
    assert re.search(r"^name:\s*sdd-taskrunner\s*$", fm, re.M)


def test_taskrunner_skill_has_no_design_doc_references():
    text = _read(RUNNER)
    assert not DESIGN_PATH.search(text)
    offenders = [ln for ln in _lines(text) if ARCH_UI_API.search(ln)]
    assert not offenders, offenders


def test_taskrunner_skill_f12_rg_pattern_zero():
    offenders = [ln for ln in _lines(_read(RUNNER)) if F12_PATTERN.search(ln)]
    assert not offenders, offenders


def test_taskrunner_generation_rules_reference_spec_single_document():
    section = _section(_body(RUNNER), "task 문서 생성 규칙")
    assert _any_line(section, r"spec", r"(구현 방향|테스트 전략|설계 결정)"), (
        "구현 방향을 spec 단일 문서에서 도출하라는 규칙 없음"
    )
    assert _any_line(section, r"spec.*기능 요구사항.*완료 조건")
    assert not [ln for ln in _lines(section) if re.search(r"\barch\b|\bui\b|\bapi\b", ln)]


def test_taskrunner_skill_keeps_template_pointer_and_complexity():
    section = _section(_body(RUNNER), "task 문서 생성 규칙")
    assert _any_line(section, r"템플릿:.*assets/templates/task-document\.md")
    assert "C++" in _read(RUNNER)
    assert _any_line(_read(RUNNER), r"Background task \+ 큐", r"\+2")


# ------------------------------------------------------------------ template


def test_template_has_spec_reference_line_only():
    section = _section(_read(TEMPLATE), "관련 문서")
    items = [ln for ln in _lines(section) if ln.startswith("- ")]
    assert len(items) == 1, items
    assert re.match(r"- spec: `docs/sdd/spec/\{\{date\}\}-\{\{feature\}\}\.md`", items[0])


def test_template_has_no_design_paths_or_arch_ui_api_refs():
    text = _read(TEMPLATE)
    assert not DESIGN_PATH.search(text)
    assert not [ln for ln in _lines(text) if re.match(r"- (arch|ui|api):", ln)]
    assert not [ln for ln in _lines(text) if re.search(r"arch 문서|ui 문서|api 문서", ln)]
    assert not [ln for ln in _lines(text) if F12_PATTERN.search(ln)]


def test_template_test_type_note_points_to_spec_test_strategy():
    section = _section(_read(TEMPLATE), "테스트 타입")
    assert _any_line(section, r"spec", r"테스트 전략")
    assert _any_line(section, r"test-automator")


def test_template_verification_section_has_test_scope_and_no_build_command_cells():
    section = _section(_read(TEMPLATE), "검증 명령어")
    assert re.search(r"테스트 스코프", section)
    for banned in ("증분 빌드", "verification_command", "빌드 프로파일", "ORCHESTRATOR_STATE", "{filter}"):
        assert banned not in section, banned
    assert "```" not in section, "실제 명령 코드블록 칸이 남음"


def test_template_has_no_incremental_build_or_test_run_command_cells_anywhere():
    text = _read(TEMPLATE)
    for banned in ("증분 빌드", "verification_command", "테스트 실행 명령"):
        assert banned not in text, banned


def test_template_keeps_other_sections():
    text = _read(TEMPLATE)
    for heading in ("구현자", "테스트 타입", "완료 조건", "의존 태스크", "예상 변경 파일", "Steps", "검증 명령어"):
        assert re.search(rf"^## {re.escape(heading)}\s*$", text, re.M), heading
