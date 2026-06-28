"""hooks.lib.code_mapper — code-mapper 결정적 코어 패키지.

arch §3/§6의 "결정적 코어 레이어"의 단일 import 지점. stdlib only,
네트워크/LLM/MCP 무호출, side-effect 0, fail-safe.

정체성=ephemeral: 디스크 쓰기/영속/계약/검증게이트 로직 일절 없다. 코어는
순수 함수 3개 + 데이터 테이블뿐이다:
  - classify_probe_state(text)       : status 텍스트 → 3-상태 (probe.py)
  - check_format_completeness(text)  : F6 섹션/순서 검사 (format_check.py)
  - language_for(ext) / def_patterns : 확장자→언어→정의패턴 (patterns.py)

기존 hooks/lib/self_improve/ 와 동일한 결정적-코어 패턴을 따르되, 책임이
다르므로 별도 패키지로 격리한다 (혼입 금지 — arch §3).

코어는 *선택적*이다: 코어가 없거나 import 실패해도 LLM이 SKILL.md 절차만으로
동작 가능해야 한다(arch §4). 코어는 일관성 보조 + 테스트 가능 표면일 뿐이다.
"""

from hooks.lib.code_mapper.format_check import check_format_completeness
from hooks.lib.code_mapper.patterns import (
    EXCLUSION_PATTERNS,
    GENERIC,
    JS_TS,
    PYTHON,
    RESERVED_WORDS,
    def_patterns,
    language_for,
)
from hooks.lib.code_mapper.probe import (
    HEALTHY,
    NOT_INITIALIZED,
    UNAVAILABLE,
    classify_probe_state,
)

__all__ = [
    # probe (3-상태 상수 + 분류)
    "HEALTHY",
    "NOT_INITIALIZED",
    "UNAVAILABLE",
    "classify_probe_state",
    # format check
    "check_format_completeness",
    # patterns (언어 상수 + 매핑 + 테이블)
    "PYTHON",
    "JS_TS",
    "GENERIC",
    "language_for",
    "def_patterns",
    "EXCLUSION_PATTERNS",
    "RESERVED_WORDS",
]
