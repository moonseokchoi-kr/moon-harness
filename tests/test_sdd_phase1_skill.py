"""tests/test_sdd_phase1_skill.py — skills/sdd/SKILL.md Phase 1 인터뷰 흐름 정적 검사 (spec F4, F6, F8).

오프라인 전용. 네트워크/LLM 무호출. 키워드가 파일 어딘가가 아니라 해당 절/문장 안에 있는지 검사한다.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SDD_SKILL = REPO_ROOT / "skills" / "sdd" / "SKILL.md"

SCAN_TARGETS = ["skills", "agents", "hooks", ".claude-plugin", "README.md", "CLAUDE.md"]
MAX_LINES = 671


@pytest.fixture(scope="module")
def body() -> str:
    assert SDD_SKILL.is_file(), f"{SDD_SKILL} 가 없다"
    text = SDD_SKILL.read_text(encoding="utf-8")
    return re.sub(r"\A---\n.*?\n---\n", "", text, count=1, flags=re.DOTALL)


def _section(text: str, heading: str) -> str:
    """heading(예: '## Phase 1')으로 시작하는 절 본문. 코드펜스 안의 '#'은 헤딩으로 보지 않는다."""
    level = len(heading) - len(heading.lstrip("#"))
    lines = text.splitlines()
    in_fence = False
    start = None
    out = []
    for line in lines:
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        m = None if in_fence else re.match(r"(#+)\s", line)
        if start is None:
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


@pytest.fixture(scope="module")
def phase1(body) -> str:
    return _section(body, "## Phase 1")


# ── 흐름 순서 (F4) ──────────────────────────────────────────────
def test_phase1_flow_order(phase1):
    steps = [r"grill", r"요약", r"yes|예스|승인", r"sdd-spec-writer", r"sdd-blocker-checker"]
    pos = 0
    for step in steps:
        m = re.compile(step).search(phase1, pos)
        assert m, f"Phase 1 절에서 '{step}' 가 순서대로 나타나지 않는다 (직전 위치 {pos} 이후)"
        pos = m.end()


def test_phase1_explicit_yes_before_spec_writer(phase1):
    assert _lines_matching(phase1, r"명시적", r"yes"), "명시적 yes 게이트 문장이 Phase 1 절에 없다"


def test_phase1_blocker_checker_two_passes(phase1):
    assert _lines_matching(phase1, r"sdd-blocker-checker", r"1차"), "blocker-checker 1차 언급 없음"
    assert _lines_matching(phase1, r"sdd-blocker-checker", r"2차"), "blocker-checker 2차 언급 없음"


def test_phase1_why_code_mapper_run_as_explore(phase1):
    assert "subagent_type: Explore" in phase1
    assert _lines_matching(phase1, r"why|code-mapper", r"Explore"), (
        "why/code-mapper 를 Explore 로 실행한다는 문장이 한 줄에 없다"
    )
    assert _lines_matching(phase1, r"code-mapper"), "code-mapper 언급 없음"


def test_phase1_non_interactive_stops_and_reports(phase1):
    assert _lines_matching(phase1, r"비대화형", r"멈추|중단|중지", r"보고"), (
        "비대화형이면 Phase 1을 멈추고 보고한다는 문장이 없다"
    )


def test_phase1_dispatches_no_ux_researcher(phase1):
    assert "ux-researcher" not in phase1


# ── set_waiting_for_user interview (F8) ─────────────────────────
def test_set_waiting_interview_before_ending_question_turn(body):
    assert _lines_matching(
        body, r"질문", r"set_waiting_for_user true interview", r"전에|먼저"
    ), "질문 턴 종료 전에 set_waiting_for_user true interview 를 먼저 호출한다는 문장이 없다"


# ── 자연어 승인 표 + interview 예외 (F8) ─────────────────────────
def _approval_table_and_next(body: str) -> tuple[list[str], str]:
    sec = _section(body, "### 사용자 승인 감지 (자연어)")
    lines = sec.splitlines()
    i = next((k for k, ln in enumerate(lines) if ln.startswith("|")), None)
    assert i is not None, "승인 감지 절에 표가 없다"
    j = i
    while j < len(lines) and lines[j].startswith("|"):
        j += 1
    nxt = next((ln for ln in lines[j:] if ln.strip()), "")
    return lines[i:j], nxt


def test_approval_table_existing_rows_unchanged(body):
    table, _ = _approval_table_and_next(body)
    joined = "\n".join(table)
    assert '| "승인", "좋아", "진행", "ok", "go" | `advance_label <next>` + `set_waiting_for_user false null` |' in joined
    assert '| "X를 수정해줘", "Y 바꿔줘" | 해당 phase로 롤백 + 수정 요청을 담당 agent에게 전달 |' in joined
    assert '| "취소", "중단" | `cancel_pipeline` |' in joined
    assert len(table) == 5, "표 행 수가 변했다 (헤더+구분선+3행)"


def test_interview_exception_line_right_after_table(body):
    _, nxt = _approval_table_and_next(body)
    assert re.search(r"interview", nxt), f"표 직후 첫 비어있지 않은 줄이 interview 예외가 아니다: {nxt!r}"
    assert re.search(r"네", nxt) and re.search(r"yes", nxt, re.IGNORECASE)
    assert re.search(r"단독", nxt), "요약 승인은 '네'/'yes' 단독만이라는 문구가 없다"


# ── 상태머신 / 에이전트 표 / 진입 전 검증 (F4) ───────────────────
def test_state_machine_first_label_is_interview_start(body):
    sec = _section(body, "## 라벨 기반 상태 머신")
    first = re.search(r"PHASE\d_[A-Z0-9_{}]+", sec)
    assert first and first.group(0) == "PHASE1_INTERVIEW_START", f"첫 라벨: {first and first.group(0)}"


def test_agent_table_has_spec_writer_phase1(body):
    sec = _section(body, "## 에이전트 목록")
    rows = _lines_matching(sec, r"^\|\s*`sdd-spec-writer`\s*\|\s*1\s*\|")
    assert rows, "에이전트 표에 Phase 1 sdd-spec-writer 행이 없다"


def test_phase2_precheck_row1_rolls_back_to_spec_writer(body):
    sec = _section(body, "### Phase 2 진입 전 검증 (필수)")
    rows = _lines_matching(sec, r"^\|\s*1\s*\|")
    assert rows, "검증 1번 행이 없다"
    assert re.search(r"sdd-spec-writer|Phase 1 인터뷰", rows[0]), rows[0]
    assert "ux-researcher" not in rows[0]


# ── spec 템플릿 참조 (F6) ───────────────────────────────────────
def test_phase1_references_spec_template_in_one_line(phase1):
    refs = _lines_matching(phase1, r"references/spec-template\.md")
    assert len(refs) == 1, f"references/spec-template.md 참조는 정확히 한 줄이어야 한다: {len(refs)}"


def test_template_body_not_embedded(body, phase1):
    assert not re.search(r"^##\s+개요", body, re.MULTILINE)
    assert "타겟 사용자" not in body
    assert "핵심 가치" not in body
    assert "# {feature} Spec" not in phase1
    assert "### spec 템플릿" not in phase1


# ── 금지 문자열 / 줄 수 ─────────────────────────────────────────
def _scan_files():
    for target in SCAN_TARGETS:
        p = REPO_ROOT / target
        if p.is_file():
            yield p
        elif p.is_dir():
            for f in p.rglob("*"):
                if f.is_file() and "__pycache__" not in f.parts and f.suffix != ".pyc":
                    yield f


def test_no_ux_researcher_in_scan_scope():
    hits = []
    for f in _scan_files():
        try:
            text = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for n, ln in enumerate(text.splitlines(), 1):
            if "ux-researcher" in ln:
                hits.append(f"{f.relative_to(REPO_ROOT)}:{n}")
    assert not hits, f"ux-researcher 잔존: {hits}"


def test_skill_line_count_within_budget():
    n = len(SDD_SKILL.read_text(encoding="utf-8").splitlines())
    assert n <= MAX_LINES, f"SKILL.md {n}줄 > {MAX_LINES}"
