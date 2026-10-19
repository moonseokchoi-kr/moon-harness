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
