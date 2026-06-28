"""tests/test_code_mapper_core.py — code-mapper 결정적 코어 단위 테스트.

오프라인 전용. 네트워크/LLM/MCP 무호출. arch §6/§7/§8 기준.

검증 대상 (순수 함수 3종 + 데이터 테이블):
  - classify_probe_state(text)        : status 텍스트 → 3-상태 분류 (fail-safe unavailable)
  - check_format_completeness(text)   : F6 섹션 1~6 + "탐색 방법" 존재/순서 검사
  - language_for(ext) / def_patterns  : 확장자 → 언어 / 언어 → 정의 패턴(유효 정규식)
  - 거짓양성 제외 패턴 테이블 + 언어 예약어 제외 목록 (패턴 형태 단위)
"""

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from hooks.lib.code_mapper import (  # noqa: E402
    HEALTHY,
    NOT_INITIALIZED,
    UNAVAILABLE,
    EXCLUSION_PATTERNS,
    RESERVED_WORDS,
    check_format_completeness,
    classify_probe_state,
    def_patterns,
    language_for,
)


# =========================================================================
# classify_probe_state — 3-상태 분류 (arch §8)
# =========================================================================

# --- (a) healthy: 인덱스 통계(노드/엣지/ready) 반환 -----------------------

@pytest.mark.parametrize(
    "text",
    [
        "Index ready: 1234 nodes, 5678 edges",
        "nodes: 42, edges: 99, ready",
        "Codegraph status — 12000 symbols indexed, 30000 edges. Index is ready.",
        "ready\nnodes=10\nedges=20",
    ],
)
def test_classify_healthy(text):
    assert classify_probe_state(text) == HEALTHY


# --- (b) not_initialized: "not initialized"(동등 미초기화) 포함 -----------

@pytest.mark.parametrize(
    "text",
    [
        "Codegraph not initialized. Run codegraph init -i.",
        "Error: index not initialized",
        "NOT INITIALIZED",
        "The .codegraph index is not initialized yet.",
    ],
)
def test_classify_not_initialized(text):
    assert classify_probe_state(text) == NOT_INITIALIZED


# --- (c) unavailable: 미등록 / 오류 / fail-safe --------------------------

@pytest.mark.parametrize(
    "text",
    [
        "tool not found: codegraph_status",
        "MCP server connection error",
        "Unknown tool",
        "command not found",
        "unexpected gibberish with no known signal",
        "",
        "   ",
        "\n\t ",
    ],
)
def test_classify_unavailable(text):
    assert classify_probe_state(text) == UNAVAILABLE


def test_classify_fail_safe_on_none():
    # 비문자열 → fail-safe unavailable (예외 던지지 않음)
    assert classify_probe_state(None) == UNAVAILABLE  # type: ignore[arg-type]


def test_classify_returns_one_of_three():
    for t in ["1 nodes 1 edges ready", "not initialized", "garbage", ""]:
        assert classify_probe_state(t) in {HEALTHY, NOT_INITIALIZED, UNAVAILABLE}


def test_not_initialized_precedence_over_stats():
    # 통계 단어가 섞여 있어도 'not initialized' 신호가 우선해야 한다
    text = "index has 0 nodes, 0 edges — not initialized"
    assert classify_probe_state(text) == NOT_INITIALIZED


# =========================================================================
# check_format_completeness — F6 섹션 1~6 + 탐색 방법 (arch §8 / spec F6)
# =========================================================================

COMPLETE_F6 = """## 코드맵: foo

### 1. 진입점
- 심볼/파일명: foo

### 2. Callers (이 심볼을 호출하는 곳)
| 호출자 | 파일:라인 | 호출 목적 |

### 3. Callees (이 심볼이 호출하는 것)
(없음)

### 4. 호출 경로 (Trace)
foo → bar

### 5. Blast Radius (영향범위)
- baz.py

### 6. 건드릴 파일 (이번 작업 추정)
- foo.py — 수정

---
탐색 방법: grep 근사 (codegraph 미사용)
"""


def test_format_complete_returns_true_empty_missing():
    ok, missing = check_format_completeness(COMPLETE_F6)
    assert ok is True
    assert missing == []


def test_format_missing_section_reported():
    # 섹션 4(호출 경로)를 제거
    text = COMPLETE_F6.replace(
        "### 4. 호출 경로 (Trace)\nfoo → bar\n\n", ""
    )
    ok, missing = check_format_completeness(text)
    assert ok is False
    assert any("4" in m or "호출 경로" in m or "Trace" in m for m in missing)


def test_format_missing_probe_label_reported():
    text = COMPLETE_F6.replace("탐색 방법: grep 근사 (codegraph 미사용)", "")
    ok, missing = check_format_completeness(text)
    assert ok is False
    assert any("탐색 방법" in m for m in missing)


def test_format_out_of_order_detected():
    # 섹션 5와 6의 순서를 뒤바꿈
    sec5 = "### 5. Blast Radius (영향범위)\n- baz.py\n\n"
    sec6 = "### 6. 건드릴 파일 (이번 작업 추정)\n- foo.py — 수정\n\n"
    swapped = COMPLETE_F6.replace(sec5 + sec6, sec6 + sec5)
    ok, missing = check_format_completeness(swapped)
    assert ok is False
    assert missing  # 순서 오류가 누락/오류 목록으로 보고됨


def test_format_empty_text_all_missing():
    ok, missing = check_format_completeness("")
    assert ok is False
    # 6 섹션 + 탐색 방법 = 최소 7개 누락 항목
    assert len(missing) >= 7


def test_format_returns_tuple_shape():
    res = check_format_completeness(COMPLETE_F6)
    assert isinstance(res, tuple) and len(res) == 2
    assert isinstance(res[0], bool)
    assert isinstance(res[1], list)


# =========================================================================
# language_for / def_patterns — 확장자 → 언어 → 정의 패턴 (arch §7.1)
# =========================================================================

@pytest.mark.parametrize(
    "ext,lang",
    [
        (".py", "python"),
        ("py", "python"),
        (".ts", "js_ts"),
        (".tsx", "js_ts"),
        (".js", "js_ts"),
        (".jsx", "js_ts"),
        (".mjs", "js_ts"),
    ],
)
def test_language_for_known(ext, lang):
    assert language_for(ext) == lang


@pytest.mark.parametrize(
    "ext",
    [".rs", ".cpp", ".go", ".unknown", "", ".", "noext", None],
)
def test_language_for_unknown_is_generic(ext):
    assert language_for(ext) == "generic"


def test_language_for_case_insensitive():
    assert language_for(".PY") == "python"
    assert language_for(".TS") == "js_ts"


@pytest.mark.parametrize("lang", ["python", "js_ts", "generic"])
def test_def_patterns_nonempty_and_valid_regex(lang):
    pats = def_patterns(lang)
    assert isinstance(pats, list)
    assert len(pats) >= 1
    for p in pats:
        assert isinstance(p, str)
        re.compile(p)  # 유효 정규식이어야 한다 (예외 시 테스트 실패)


def test_def_patterns_unknown_lang_falls_back_to_generic():
    assert def_patterns("klingon") == def_patterns("generic")


def test_def_patterns_contain_symbol_placeholder():
    # 패턴은 심볼 자리표시자를 포함해 프롬프트가 대상 심볼을 끼워넣을 수 있어야 한다
    for lang in ("python", "js_ts", "generic"):
        joined = " ".join(def_patterns(lang))
        assert "<sym>" in joined


# =========================================================================
# 거짓양성 제외 패턴 테이블 + 예약어 제외 목록 (arch §7.4)
# =========================================================================

def test_exclusion_patterns_are_valid_regex():
    assert isinstance(EXCLUSION_PATTERNS, dict)
    # 주석 / 문자열 / 타입힌트 카테고리가 존재
    for key in ("comment", "string", "type_hint"):
        assert key in EXCLUSION_PATTERNS, f"missing exclusion category: {key}"
    for cat, pats in EXCLUSION_PATTERNS.items():
        assert len(pats) >= 1
        for p in pats:
            re.compile(p)  # 유효 정규식


def test_reserved_words_excludes_control_keywords():
    # generic callees grep(\b\w+\s*\()가 제어구문을 잡지 않도록 (arch §7.4 m2)
    assert isinstance(RESERVED_WORDS, (set, frozenset, tuple, list))
    for kw in ("if", "for", "while", "switch", "catch"):
        assert kw in RESERVED_WORDS


def test_comment_pattern_matches_comment_line():
    # 형태 단위 검증: 주석 패턴이 실제 주석 라인을 매치
    comment_pats = EXCLUSION_PATTERNS["comment"]
    matched = any(re.search(p, "# this is a comment") for p in comment_pats)
    assert matched
    matched_slash = any(re.search(p, "// js comment") for p in comment_pats)
    assert matched_slash
