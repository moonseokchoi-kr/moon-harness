"""tests/test_grill_skill.py — skills/grill/SKILL.md 정적 검사 (spec F2).

오프라인 전용. 네트워크/LLM 무호출. Markdown 키워드 존재/부재만 검사한다.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
GRILL_SKILL = REPO_ROOT / "skills" / "grill" / "SKILL.md"


@pytest.fixture(scope="module")
def grill_text() -> str:
    assert GRILL_SKILL.is_file(), f"{GRILL_SKILL} 가 없다"
    return GRILL_SKILL.read_text(encoding="utf-8")


def _frontmatter(text: str) -> dict:
    match = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
    assert match, "frontmatter(--- ... ---)가 없다"
    fields = {}
    for line in match.group(1).splitlines():
        key, sep, value = line.partition(":")
        if sep and not line.startswith((" ", "\t")):
            fields[key.strip()] = value.strip().strip("\"'")
    return fields


def _body(text: str) -> str:
    return re.sub(r"\A---\n.*?\n---\n", "", text, count=1, flags=re.DOTALL)


def test_skill_file_exists():
    assert GRILL_SKILL.is_file()


def test_frontmatter_name_is_grill(grill_text):
    assert _frontmatter(grill_text).get("name") == "grill"


def test_frontmatter_description_not_empty(grill_text):
    assert _frontmatter(grill_text).get("description", "").strip() != ""


@pytest.mark.parametrize(
    "keyword",
    ["frontier", "하지 않을 것", "비대화형", "/loop", "스케줄", "CI", "yes"],
)
def test_body_contains_required_keyword(grill_text, keyword):
    assert keyword in _body(grill_text)


def test_body_has_termination_example_sentence(grill_text):
    body = _body(grill_text)
    assert "다음에 물을 질문 3개" in body
    assert "추천 답" in body


def test_implicit_agreement_is_not_approval(grill_text):
    body = _body(grill_text)
    assert "좋아 보여" in body
    # 암묵적 동의를 승인으로 취급하지 않는다는 지침이 같은 문서에 있어야 한다.
    assert re.search(r"(승인.{0,20}(않|아니|취급))|(암묵적 동의)", body)


def test_summary_is_5_to_8_lines(grill_text):
    assert re.search(r"5\s*[~-]\s*8\s*줄", _body(grill_text))


@pytest.mark.parametrize(
    "forbidden", ["pipeline.json", "advance_label", "set_waiting_for_user"]
)
def test_no_pipeline_state_handling(grill_text, forbidden):
    assert forbidden not in grill_text


def test_one_question_at_a_time_not_adopted(grill_text):
    # frontier 라운드는 질문을 모아서 묻는다. "한 번에 한 질문"은 부정문으로만 허용.
    for line in grill_text.splitlines():
        if re.search(r"한 번에 (한|1) ?(개의 )?질문|one question at a time", line, re.I):
            assert re.search(r"않|금지|아니|없", line), f"한 질문 방식 채택: {line}"


def test_facts_are_investigated_not_asked(grill_text):
    body = _body(grill_text)
    assert "직접 조사" in body
    assert "Explore" in body


# --- 계약 문장 단위 고정 (refactor 안전망) -----------------------------------


def _section(text: str, heading: str) -> str:
    """`## heading` 절 본문(다음 `## ` 헤딩 직전까지). frontmatter 제외."""
    body = _body(text)
    match = re.search(
        rf"^##[ \t]+{re.escape(heading)}[ \t]*\n(.*?)(?=^##[ \t]|\Z)",
        body,
        re.DOTALL | re.MULTILINE,
    )
    assert match, f"절 '{heading}' 이 없다"
    return match.group(1)


def _lines(section: str) -> list:
    return [line for line in section.splitlines() if line.strip()]


def _line_matching(section: str, *patterns: str) -> str:
    """모든 패턴을 함께 만족하는 한 줄(=한 계약 문장)을 반환. 없으면 실패."""
    for line in _lines(section):
        if all(re.search(p, line) for p in patterns):
            return line
    pytest.fail(f"다음을 모두 만족하는 문장이 없다: {patterns}")


@pytest.fixture(scope="module")
def approval_section(grill_text) -> str:
    return _section(grill_text, "요약과 명시적 yes")


def test_summary_is_standalone_message(approval_section):
    _line_matching(approval_section, r"요약", r"질문 라운드", r"섞지 않", r"단독 메시지")


def test_approval_only_from_immediate_reply_not_round_answer(approval_section):
    _line_matching(approval_section, r"[\"“]네[\"”]", r"yes", r"승인으로 인정", r"요약.{0,10}직후", r"응답")
    _line_matching(approval_section, r"라운드 답변의 [\"“]네[\"”]", r"승인이 아니")


def test_conditional_yes_is_not_approval_and_resummarizes(approval_section):
    _line_matching(
        approval_section,
        r"수정 요청",
        r"조건부 yes",
        r"승인이 아니",
        r"요약을 고쳐",
        r"yes를 요청",
    )


def test_no_follow_up_work_before_approval(approval_section):
    _line_matching(approval_section, r"승인 전", r"후속 작업", r"시작하지 않")


def test_implicit_agreement_literal_and_negation_in_same_sentence(approval_section):
    _line_matching(
        approval_section,
        r"좋아 보여",
        r"암묵적 동의",
        r"승인으로 (보|취급하)지 않",
    )


def test_non_interactive_sentence_refuses_start_and_halts_with_report(grill_text):
    section = _section(grill_text, "사용 조건")
    line = _line_matching(
        section,
        r"비대화형",
        r"/loop",
        r"스케줄",
        r"CI",
        r"시작하지 않",
        r"멈|중단",
        r"사용자 입력이 필요",
    )
    assert re.search(r"보고", line)


def test_termination_condition_three_questions_and_unpredictable_branch(grill_text):
    section = _section(grill_text, "종료 조건")
    _line_matching(section, r"다음에 물을 질문 3개", r"예측할 수 있으면", r"종료")
    _line_matching(section, r"예측할 수 없는 질문", r"그 질문부터", r"라운드로 묻")
