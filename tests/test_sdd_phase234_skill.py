"""tests/test_sdd_phase234_skill.py — skills/sdd/SKILL.md Phase 2~4·문서 구조·정책 정적 검사 (spec F9~F15 SKILL 측).

오프라인 전용. 네트워크/LLM 무호출. 키워드가 파일 어딘가가 아니라 해당 절/줄 안에 있는지,
순서는 위치 비교로 검사한다. Phase 1 절은 T-5 소유이므로 대상이 아니다.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SDD_SKILL = REPO_ROOT / "skills" / "sdd" / "SKILL.md"

MAX_LINES = 671
DELETED_AGENTS = ["sdd-ui-designer", "sdd-api-designer", "sdd-architect-reviewer", "sdd-context-manager"]
NEGATION = r"않|아님|아니|금지|말|없"


@pytest.fixture(scope="module")
def body() -> str:
    assert SDD_SKILL.is_file(), f"{SDD_SKILL} 가 없다"
    text = SDD_SKILL.read_text(encoding="utf-8")
    return re.sub(r"\A---\n.*?\n---\n", "", text, count=1, flags=re.DOTALL)


def _section(text: str, heading: str) -> str:
    """heading 으로 시작하는 절 본문. 코드펜스 안의 '#'은 헤딩이 아니고, 펜스 내용은 절에 포함된다."""
    level = len(heading) - len(heading.lstrip("#"))
    in_fence = False
    start = False
    out = []
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        m = None if in_fence else re.match(r"(#+)\s", line)
        if not start:
            if m and line.startswith(heading):
                start = True
            continue
        if m and len(m.group(1)) <= level:
            break
        out.append(line)
    assert start, f"절 '{heading}' 가 없다"
    return "\n".join(out)


def _lines_matching(text: str, *patterns: str) -> list[str]:
    return [ln for ln in text.splitlines() if all(re.search(p, ln) for p in patterns)]


def _first_pos(text: str, pattern: str, after: int = 0) -> int:
    m = re.compile(pattern).search(text, after)
    assert m, f"'{pattern}' 가 (위치 {after} 이후) 없다"
    return m.start()


@pytest.fixture(scope="module")
def phase2(body) -> str:
    return _section(body, "## Phase 2")


@pytest.fixture(scope="module")
def phase3(body) -> str:
    return _section(body, "## Phase 3")


@pytest.fixture(scope="module")
def phase4(body) -> str:
    return _section(body, "## Phase 4")


# ── 크기 (F15) ───────────────────────────────────────────────────
def test_skill_line_count_within_budget():
    assert len(SDD_SKILL.read_text(encoding="utf-8").splitlines()) <= MAX_LINES


# ── 삭제 대상 문자열 0건 (F9, F11, F13, F14) ──────────────────────
@pytest.mark.parametrize("name", DELETED_AGENTS + ["ui-designer", "api-designer", "architect-reviewer", "context-manager"])
def test_no_deleted_agent_names(body, name):
    assert name not in body


@pytest.mark.parametrize(
    "needle",
    ["docs/sdd/design/", "docs/sdd/context/", "design/arch", "design/ui", "design/api"],
)
def test_no_design_or_context_paths(body, needle):
    assert needle not in body


@pytest.mark.parametrize("needle", ["FULL 모드", "SIMPLE", "설계 모드"])
def test_no_design_mode_strings(body, needle):
    assert needle not in body


@pytest.mark.parametrize("needle", ["E2E 필수", "E2E 없이 DONE", "e2e-config"])
def test_no_e2e_mandatory_strings(body, needle):
    assert needle not in body


def test_no_e2e_red_before_view_ui_rule(body):
    assert not _lines_matching(body, r"View|UI", r"E2E", r"RED"), "View/UI 구현 전 E2E RED 규칙이 남아 있다"


# ── Phase 2: 조건부 아키텍처 (F9) ─────────────────────────────────
def test_phase2_is_conditional_architecture(phase2, body):
    assert "## Phase 2: Design" not in body
    assert re.search(r"조건부", phase2)
    assert "PHASE1_USER_APPROVED" in phase2


def test_phase2_lead_decides_arch_start_or_skip(phase2):
    start = _first_pos(phase2, r"PHASE2_ARCH_START")
    _first_pos(phase2, r"PHASE2_ARCH_SKIP")
    assert _lines_matching(phase2, r"설계 결정", r"판단|판정"), "리드가 spec 설계 결정을 보고 판단한다는 문장이 없다"
    assert start < _first_pos(phase2, r"PHASE2_ARCH_SKIP") or _lines_matching(phase2, r"PHASE2_ARCH_SKIP")


def test_phase2_arch_start_dispatches_three_architects(phase2):
    for name in ["webapp-architect", "flutter-architect", "native-architect"]:
        assert name in phase2, f"{name} 가 Phase 2 절에 없다"


def test_phase2_architect_gets_main_checkout_spec_absolute_path(phase2):
    assert _lines_matching(phase2, r"절대 ?경로", r"spec"), "spec 절대 경로 문장이 없다"
    assert _lines_matching(phase2, r"메인 체크아웃", r"spec"), "메인 체크아웃 spec 문장이 없다"
    assert _lines_matching(phase2, r"디스패치", r"프롬프트|절대 ?경로")


def test_phase2_architect_edits_only_design_decision_section(phase2):
    line = _lines_matching(phase2, r"설계 결정", r"Edit")
    assert line, "설계 결정 섹션만 Edit 한다는 문장이 없다"
    assert _lines_matching(phase2, r"설계 결정", r"만"), "'만' 한정어가 없다"


def test_phase2_has_no_separate_approval_gate(phase2):
    ln = _lines_matching(phase2, r"별도", r"게이트|승인", r"없")
    assert ln, "별도 승인 게이트 없음 문장이 없다"
    assert not _lines_matching(phase2, r"PHASE2_\w*USER_APPROVED")
    assert "waiting_for_user true" not in phase2.replace("set_waiting_for_user true interview", "")


def test_phase2_has_no_arch_file_or_template(phase2):
    assert not _lines_matching(phase2, r"(아키텍처|arch) (문서|템플릿)", r"^(?!.*(않|금지|없|아님))")
    assert "아키텍처 문서 템플릿" not in phase2
    assert not re.search(r"docs/sdd/(design|arch)", phase2)


def test_phase2_skip_and_done_lead_to_phase3_plan_start(phase2):
    assert _lines_matching(phase2, r"PHASE2_ARCH_(DONE|SKIP)", r"PHASE3_PLAN_START")


def test_phase2_does_not_create_worktree(phase2):
    assert not _lines_matching(phase2, r"Skill.*git-worktree|worktree.*생성", r"^(?!.*(않|아님|Phase 3))")


# ── Phase 3: worktree 진입 + spec 이동 (F10) ──────────────────────
def test_phase3_entry_creates_worktree_via_git_worktree_skill(phase3):
    assert _lines_matching(phase3, r"Skill", r"git-worktree"), "Skill git-worktree 호출 문장이 없다"
    a = _first_pos(phase3, r"PHASE3_PLAN_START")
    b = _first_pos(phase3, r"PHASE3_WORKTREE_CREATED", a)
    assert a < b


def test_phase3_spec_moved_not_copied(phase3):
    assert _lines_matching(phase3, r"spec", r"이동"), "spec 이동 문장이 없다"
    for ln in _lines_matching(phase3, r"복사"):
        assert re.search(NEGATION, ln), f"복사를 지시하는 문장: {ln!r}"


def test_phase3_three_branch_spec_move_in_order(phase3):
    mv = _first_pos(phase3, r"\bmv\b")
    cmp_ = _first_pos(phase3, r"\bcmp\b", mv)
    conflict = _first_pos(phase3, r"spec_conflict", cmp_)
    assert mv < cmp_ < conflict
    assert _lines_matching(phase3, r"cmp", r"동일", r"삭제", r"메인")
    assert _lines_matching(phase3, r"다르", r"멈|중단", r"보고")


def test_phase3_spec_conflict_waits_with_approval_type(phase3):
    assert _lines_matching(phase3, r"set_waiting_for_user true spec_conflict")


def test_phase3_conflict_resolution_keeps_label_and_restarts_without_advance(phase3):
    keep = _lines_matching(phase3, r"set_waiting_for_user false null", r"유지")
    assert keep, "해소 후 set_waiting_for_user false null + 라벨 유지 문장이 없다"
    assert any(re.search(r"다시|재수행|처음부터", ln) for ln in keep)
    adv = _lines_matching(phase3, r"advance_label|advance")
    assert any(re.search(NEGATION, ln) for ln in adv), "충돌 해소 시 advance 금지 문장이 없다"


def test_phase3_no_arbitrary_canonical_choice(phase3):
    ln = _lines_matching(phase3, r"정본")
    assert ln and any(re.search(r"임의", x) and re.search(NEGATION, x) for x in ln)


def test_phase3_move_precedes_taskmaster(phase3):
    mv = _first_pos(phase3, r"\bmv\b")
    tm = _first_pos(phase3, r"sdd-taskmaster", mv)
    assert mv < tm


# ── Phase 3: plan 단독 1회 → tasks 병렬 → dag (F10 + T-9 리뷰) ─────
def test_phase3_taskmaster_order_plan_tasks_dag(phase3):
    plan = _first_pos(phase3, r"plan 모드|mode='plan'|mode=\"plan\"")
    tasks = _first_pos(phase3, r"tasks 모드|mode='tasks'|mode=\"tasks\"", plan)
    dag = _first_pos(phase3, r"dag 모드|mode='dag'|mode=\"dag\"", tasks)
    assert plan < tasks < dag


def test_phase3_plan_mode_is_single_standalone_run(phase3):
    ln = _lines_matching(phase3, r"plan 모드|mode='plan'")
    assert any(re.search(r"단독", x) and re.search(r"1회|한 번", x) for x in ln), "plan 모드 단독 1회 문장이 없다"


def test_phase3_tasks_mode_parallel_with_readonly_spec(phase3):
    ln = _lines_matching(phase3, r"tasks 모드|mode='tasks'")
    assert any(re.search(r"병렬", x) for x in ln), "tasks 모드 병렬 문장이 없다"
    ro = _lines_matching(phase3, r"spec", r"읽기 ?전용")
    assert ro, "tasks 모드에서 spec 읽기 전용 문장이 없다"
    assert not any(re.search(r"spec", x) and re.search(r"읽기 ?전용", x) and re.search(r"쓰기 ?가능|수정 가능", x) for x in ro)


def test_phase3_plan_writes_implementation_plan_section_once(phase3):
    assert _lines_matching(phase3, r"구현 계획", r"plan")


def test_phase3_single_approval_covers_plan_and_tasks(phase3):
    assert _lines_matching(phase3, r"승인", r"1회|한 번|한 번만"), "승인 1회 문장이 없다"
    assert _lines_matching(phase3, r"plan", r"tasks", r"승인")


def test_phase3_preentry_checks_use_single_spec_document(phase3):
    sec = _section(phase3, "### 진입 전 검증")
    assert re.search(r"BLOCKER_PASS|blocker", sec)
    assert re.search(r"Phase 1.*승인|PHASE1_USER_APPROVED", sec)
    assert re.search(r"아키텍처 보강|ARCH_(DONE|SKIP)", sec)
    assert re.search(r"spec", sec)
    assert not re.search(r"docs/sdd/(design|context)|design/|arch 문서|ui 문서|api 문서|context", sec)
    assert "Phase 2 진입" not in sec


def test_phase3_task_template_has_test_scope_only(phase3):
    tpl = _section(phase3, "### task 템플릿")
    assert "테스트 스코프" in tpl
    assert not _lines_matching(tpl, r"증분 빌드"), "task 템플릿에 증분 빌드 명령 칸이 남아 있다"
    assert not re.search(r"arch, ui, api|spec, arch", tpl)


# ── Phase 4: 빌드 프로파일 확보는 오케스트레이터 (F12) ─────────────
def test_phase4_no_rollback_to_phase2_for_profile(body):
    assert "Phase 2로 롤백" not in body
    assert "architect가 프로파일 미발견" not in body
    assert not re.search(r"프로파일 발견 \(Phase 2", body)
    assert not _lines_matching(body, r"프로파일", r"architect", r"미발견|발견")


def test_phase4_entry_check5_defers_to_orchestrator_in_order(phase4):
    entry = _section(phase4, "### 진입 전 검증")
    row = _lines_matching(entry, r"^\|\s*5\s*\|")
    assert row, "진입 전 검증 5번 행이 없다"
    assert re.search(r"sdd-orchestrator|오케스트레이터", row[0])
    sec = phase4
    a = _first_pos(sec, r"CLAUDE\.md")
    b = _first_pos(sec, r"CLAUDE\.local\.md", a)
    c = _first_pos(sec, r"/build-notes", b)
    d = _first_pos(sec, r"질문", c)
    assert a < b < c < d


def test_build_aware_tdd_three_principles_kept(body):
    sec = _section(body, "## 빌드 프로파일 (build-aware TDD)")
    assert re.search(r"워밍업", sec) and re.search(r"증분", sec) and re.search(r"no-clean|clean 금지", sec)
    assert _lines_matching(sec, r"sdd-orchestrator|오케스트레이터", r"프로파일|빌드")
    assert "프로파일 스키마" in sec


def test_phase4_entry_worktree_already_exists_from_phase3(phase4):
    assert "Phase 2에서 이미 worktree" not in phase4
    assert _lines_matching(phase4, r"Phase 3", r"worktree")


# ── E2E: 수동 시나리오, 요청 시 (F13) ─────────────────────────────
def test_ui_change_records_manual_scenarios_and_e2e_only_on_request(body):
    ln = _lines_matching(body, r"수동 테스트 시나리오")
    assert ln, "수동 테스트 시나리오 문장이 없다"
    assert any(re.search(r"result", x) and re.search(r"UI", x) for x in ln)
    req = _lines_matching(body, r"E2E", r"요청")
    assert req and any(re.search(r"요청 시|요청할 때|요청한 경우|요청하면", x) for x in req)


# ── 문서 구조 (F14) ──────────────────────────────────────────────
def test_doc_structure_tree_is_single_spec_flow(body):
    tree = _section(body, "## 문서 구조")
    for need in ["spec/", "task/", "ORCHESTRATOR_STATE.md", "result/", "pipeline.json"]:
        assert need in tree, f"문서 구조 트리에 {need} 가 없다"
    for gone in ["design/", "context/", "e2e-config", "arch/", "ui/", "api/"]:
        assert gone not in tree, f"문서 구조 트리에 {gone} 가 남아 있다"


# ── Phase 판정 규칙 (F14) ────────────────────────────────────────
def test_phase_judgement_table_follows_new_flow(body):
    sec = _section(body, "## Phase 판정 규칙 (세션 재개 시)")
    assert not re.search(r"정밀 모드|호환 모드|context", sec)
    assert not re.search(r"design|FULL|SIMPLE|ui-designer|api-designer", sec)
    assert _lines_matching(sec, r"^\|", r"spec 없음", r"P1")
    assert _lines_matching(sec, r"^\|", r"task", r"ORCHESTRATOR_STATE", r"P3")
    assert _lines_matching(sec, r"^\|", r"ORCHESTRATOR_STATE", r"P4")
    assert _lines_matching(sec, r"^\|", r"result", r"완료")
    assert "docs/sdd/archive/" in sec, "아카이브 주석(기존)이 유지되어야 한다"


# ── 상태머신 (F14) ───────────────────────────────────────────────
def test_state_machine_new_label_chain(body):
    sec = _section(body, "## 라벨 기반 상태 머신")
    order = ["PHASE1_USER_APPROVED", "PHASE2_ARCH_START", "PHASE2_ARCH_DONE", "PHASE3_PLAN_START",
             "PHASE3_WORKTREE_CREATED", "PHASE3_TASKMASTER_DONE", "PHASE3_DAG_CONSTRUCTED", "PHASE3_USER_APPROVED"]
    pos = 0
    for label in order:
        pos = _first_pos(sec, re.escape(label), pos)
    assert "PHASE2_ARCH_SKIP" in sec
    assert _first_pos(sec, "PHASE2_ARCH_START") < _first_pos(sec, "PHASE3_PLAN_START")
    assert _first_pos(sec, "PHASE2_ARCH_SKIP") < _first_pos(sec, "PHASE3_PLAN_START")


@pytest.mark.parametrize(
    "old",
    [r"PHASE2_START\b", "PHASE2_ARCH_STRUCTURE_DONE", "PHASE2_ARCH_USER_APPROVED", "PHASE2_UI_DESIGN_COMPLETE",
     "PHASE2_API_DESIGN_COMPLETE", "PHASE2_DESIGN_USER_APPROVED", r"PHASE2_USER_APPROVED"],
)
def test_state_machine_has_no_old_phase2_labels(body, old):
    assert not re.search(old, _section(body, "## 라벨 기반 상태 머신"))


# ── 에이전트 표 (F9, F14) ────────────────────────────────────────
def test_agent_table_has_architects_and_no_deleted_agents(body):
    sec = _section(body, "## 에이전트 목록")
    for name in ["webapp-architect", "flutter-architect", "native-architect", "sdd-taskmaster"]:
        assert name in sec
    for name in DELETED_AGENTS:
        assert name not in sec
    assert not _lines_matching(sec, r"^\|", r"develop 작성")


# ── 게이트 정책 (F14) ────────────────────────────────────────────
def test_gate_policy_table_matches_new_flow(body):
    sec = _section(body, "## 게이트 정책")
    assert not re.search(r"SIMPLE|FULL|design/|context", sec)
    assert _lines_matching(sec, r"^\|", r"Phase 1", r"spec", r"blocker-checker", r"승인")
    p2 = _lines_matching(sec, r"^\|\s*Phase 2")
    assert p2, "Phase 2 행이 없다"
    assert all(re.search(r"게이트 없음|별도 게이트 없음|승인 없음", x) or "조건부" in x for x in p2)
    assert not any(re.search(r"사용자 승인", x) and not re.search(r"없", x) for x in p2)
    p3 = _lines_matching(sec, r"^\|", r"Phase 3 → 4")
    assert p3 and re.search(r"plan", p3[0]) and re.search(r"tasks|task", p3[0]) and re.search(r"승인", p3[0])


# ── 스펙 변경 정책 / 하위호환 (F14) ───────────────────────────────
def test_spec_change_policy_is_single_document(body):
    sec = _section(body, "## 스펙 변경 정책")
    assert not re.search(r"FULL|design|arch/ui/api", sec)
    assert "spec" in sec and "blocker-checker" in sec


def test_backward_compat_section_has_no_simple_or_context_design(body):
    sec = _section(body, "## 멀티 feature / 하위 호환성")
    assert not re.search(r"SIMPLE|context/design|호환 모드", sec)
    assert "worktree" in sec


def test_clause_rule_mapping_snapshot_timing_is_phase4(body):
    sec = _section(body, "## CLAUDE.md 규칙 매핑")
    assert _lines_matching(sec, r"스냅샷", r"Phase 4")


# ── 자연어 승인 표 직후 예외 줄 (T-7 리뷰) ─────────────────────────
def _exception_lines(body: str) -> list[str]:
    sec = _section(body, "### 사용자 승인 감지 (자연어)")
    lines = sec.splitlines()
    i = next(k for k, ln in enumerate(lines) if ln.startswith("|"))
    j = i
    while j < len(lines) and lines[j].startswith("|"):
        j += 1
    return [ln for ln in lines[j:] if ln.strip()]


def test_interview_exception_line_kept(body):
    assert any(re.search(r"interview", x) and re.search(r"적용하지 않", x) for x in _exception_lines(body))


def test_spec_conflict_waiting_exception_line(body):
    ln = [x for x in _exception_lines(body) if "spec_conflict" in x]
    assert ln, "표 직후에 spec_conflict 대기 예외 줄이 없다"
    x = ln[0]
    assert re.search(r"표를 적용하지 않|적용하지 않", x), "표 비적용 문장이 없다"
    assert re.search(r"advance", x) and re.search(r"아님|않|금지", x), "advance 가 아니라는 부정 어휘가 없다"
    assert "set_waiting_for_user false null" in x
    assert re.search(r"라벨", x) and re.search(r"유지", x)
    assert re.search(r"진행", x), "'진행' 예시 어휘가 없다"


def test_spec_conflict_exception_does_not_invert_to_advance(body):
    x = next((x for x in _exception_lines(body) if "spec_conflict" in x), "")
    assert x, "spec_conflict 예외 줄이 없다"
    pos_adv = x.find("advance")
    assert pos_adv >= 0
    tail = x[pos_adv:]
    assert re.search(r"않|아님|금지|하지", tail), "advance 뒤에 부정 어휘가 없어 의미가 반전될 수 있다"


# ── T-12 iter2: spec 위치 판정·Phase 4 검증·Phase 3 승인 제시 항목·심각도 절 단일 ──
def test_phase_judgment_section_states_spec_location_worktree_first(body):
    sec = _section(body, "## Phase 판정")
    ln = _lines_matching(sec, r"spec 위치", r"worktree_path", r"worktree", r"메인")
    assert ln, "Phase 판정 절에 'spec 위치: pipeline.json worktree_path 있으면 worktree 우선, 없으면 메인' 문장이 없다"
    x = ln[0]
    assert "pipeline.json" in x
    assert x.find("worktree") < x.rfind("메인"), "worktree 우선, 없으면 메인 순서가 아니다"
    assert re.search(r"우선", x) and re.search(r"없으면", x)


def test_phase3_entry_validation_scoped_before_worktree_creation(phase3):
    sec = _section(phase3, "### 진입 전 검증")
    assert re.search(r"worktree 생성.{0,10}spec 이동.{0,6}이전", sec), \
        "Phase 3 진입 전 검증이 'worktree 생성·spec 이동 이전'에 적용된다는 한정 문장이 없다"


def test_phase4_entry_check1_checks_worktree_spec_and_blocker_pass_not_phase3_reuse(phase4):
    sec = _section(phase4, "### 진입 전 검증")
    row = next((ln for ln in sec.splitlines() if re.match(r"\|\s*1\s*\|", ln)), "")
    assert row, "Phase 4 진입 전 검증 #1 행이 없다"
    assert "Phase 3 진입 전 검증 전부" not in row, "#1이 Phase 3 진입 전 검증 전부를 재사용한다"
    assert "worktree" in row and "spec" in row and "BLOCKER_PASS" in row
    assert "Phase 1로 롤백" not in row and "Phase 1 롤백" not in row, "#1 실패 조치가 Phase 1 롤백으로 빠진다"


def test_phase3_approval_line_presents_plan_design_decisions_and_tasks_dag(phase3):
    ln = _lines_matching(phase3, r"제시", r"DAG")
    assert ln, "Phase 3 승인 제시 항목 줄이 없다"
    assert any(
        "구현 계획" in x and "설계 결정" in x and "사용자 확인 필요" in x and "task" in x
        for x in ln
    ), f"제시 항목 줄에 구현 계획 + 설계 결정(사용자 확인 필요) + task/DAG 가 함께 없다: {ln}"


def test_gate_policy_phase3_to_4_row_presents_plan_and_design_decisions(body):
    row = next((ln for ln in body.splitlines() if re.match(r"\|\s*Phase 3\s*→\s*4", ln)), "")
    assert row, "게이트 정책 표 Phase 3→4 행이 없다"
    assert "구현 계획" in row and "설계 결정" in row


def test_severity_scheme_heading_appears_exactly_once(body):
    heads = [ln for ln in body.splitlines() if re.match(r"#+\s*심각도 체계", ln)]
    assert len(heads) == 1, f"'심각도 체계' 헤딩이 {len(heads)}회: {heads}"


# ── 통합 검증 후속: 헬퍼 목록의 init_pipeline 인자 (F11 폐지 mode 인자) ─────
def test_helper_list_init_pipeline_has_no_mode_arg(body):
    helpers = _section(body, "### 핵심 헬퍼 함수")
    assert "init_pipeline <feature> <mode>" not in helpers
    assert re.search(r"init_pipeline <feature>(?! <mode>)", helpers)
