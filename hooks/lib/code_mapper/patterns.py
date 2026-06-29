"""code-mapper — 확장자→언어→정의패턴 매핑 + 거짓양성 제외 테이블 (순수 데이터).

arch §7 기준. 레포 특화 경로/명령 하드코딩 0 — 일반 언어 패턴만(.py / .ts·.js
계열 / 기타 generic). 프롬프트(LLM)가 grep에 적용할 *패턴 문자열*만 보유하고,
"이 라인이 정말 주석/문자열인가"의 적용 판단은 LLM 몫 (arch §7.4).

패턴은 ``<sym>`` 자리표시자를 포함한다 — 프롬프트가 대상 심볼로 치환해 grep에
넣는다. 자리표시자 자체로는 유효 정규식이다(``<``, ``>``, ``sym`` 모두 리터럴).
"""

from __future__ import annotations

from typing import Dict, FrozenSet, List

PYTHON: str = "python"
JS_TS: str = "js_ts"
GENERIC: str = "generic"

# --- 확장자 → 언어 (arch §7.1) -------------------------------------------
# 키는 점 없는 소문자 확장자. language_for()가 정규화 후 lookup.
_EXT_TO_LANG: Dict[str, str] = {
    "py": PYTHON,
    "pyi": PYTHON,
    "ts": JS_TS,
    "tsx": JS_TS,
    "js": JS_TS,
    "jsx": JS_TS,
    "mjs": JS_TS,
    "cjs": JS_TS,
}

# --- 언어 → 정의 패턴 (arch §7.1, <sym> 자리표시자 포함) -----------------
_DEF_PATTERNS: Dict[str, List[str]] = {
    PYTHON: [
        r"^\s*(?:async\s+)?def\s+<sym>\b",
        r"^\s*class\s+<sym>\b",
    ],
    JS_TS: [
        r"\bfunction\s+<sym>\b",
        r"\bclass\s+<sym>\b",
        r"\b(?:const|let|var)\s+<sym>\s*=\s*(?:async\s*)?(?:\([^)]*\)|[\w$]+)\s*=>",
        r"\b<sym>\s*\([^)]*\)\s*\{",
    ],
    GENERIC: [
        # 정의/사용 구분 약함 — 식별자 경계 근사 (arch §7.1 명시)
        r"\b<sym>\b",
    ],
}

# --- 거짓양성 제외 패턴 (arch §7.4) --------------------------------------
# 형태 단위로만 단위 테스트. 적용 판단은 LLM이 grep 결과 보고 수행.
EXCLUSION_PATTERNS: Dict[str, List[str]] = {
    # 주석 마커로 시작/감싸이는 라인
    "comment": [
        r"^\s*#",            # python / shell
        r"^\s*//",           # c-family / js / ts
        r"^\s*/\*",          # 블록 주석 시작
        r"\*/\s*$",          # 블록 주석 끝
        r"^\s*\*",           # jsdoc 본문 라인
    ],
    # 따옴표로 감싸인 문자열 리터럴 내부 일치
    "string": [
        r"\"[^\"]*<sym>[^\"]*\"",
        r"'[^']*<sym>[^']*'",
        r"`[^`]*<sym>[^`]*`",
    ],
    # 타입힌트 위치 (호출 아님 — callers/callees에서 제외)
    "type_hint": [
        r":\s*<sym>\b",      # 변수/파라미터 타입 주석
        r"->\s*<sym>\b",     # 반환 타입 주석
    ],
}

# --- 언어 예약어/제어구문 제외 목록 (arch §7.4 m2) -----------------------
# generic callees grep(\b\w+\s*\()이 키워드를 호출로 오집계하지 않도록.
RESERVED_WORDS: FrozenSet[str] = frozenset(
    {
        # 제어 흐름 (공통)
        "if", "else", "elif", "for", "while", "do", "switch", "case",
        "break", "continue", "return", "yield", "goto",
        # 예외 처리
        "try", "catch", "except", "finally", "throw", "raise", "with",
        # 선언/구조 (호출처럼 보이는 키워드)
        "def", "class", "function", "lambda", "import", "from", "as",
        "new", "delete", "typeof", "instanceof", "in", "is", "and", "or",
        "not", "await", "async", "const", "let", "var",
        # 불리언/널 리터럴
        "true", "false", "null", "none", "undefined",
        # 기타 흔한 키워드
        "print",  # 빌트인 — 호출관계 노이즈
        "sizeof", "assert", "pass", "global", "nonlocal",
    }
)


def language_for(ext: str) -> str:
    """파일 확장자를 언어로 매핑한다.

    Args:
        ext: 확장자 (``".py"`` / ``"py"`` / ``".TS"`` 모두 허용). 미지 확장자/
            비문자열/빈 값 → ``"generic"`` (fail-safe).

    Returns:
        ``"python"`` / ``"js_ts"`` / ``"generic"`` 중 하나.
    """
    if not isinstance(ext, str):
        return GENERIC
    key = ext.strip().lower().lstrip(".")
    if not key:
        return GENERIC
    return _EXT_TO_LANG.get(key, GENERIC)


def def_patterns(lang: str) -> List[str]:
    """언어의 정의 패턴 문자열 목록을 반환한다.

    Args:
        lang: ``"python"`` / ``"js_ts"`` / ``"generic"``. 미지 언어 →
            generic 패턴으로 폴백.

    Returns:
        ``<sym>`` 자리표시자를 포함한 유효 정규식 문자열 목록 (새 리스트 복사 —
        호출자가 변형해도 코어 테이블이 오염되지 않는다).
    """
    if not isinstance(lang, str):
        lang = GENERIC
    return list(_DEF_PATTERNS.get(lang, _DEF_PATTERNS[GENERIC]))
