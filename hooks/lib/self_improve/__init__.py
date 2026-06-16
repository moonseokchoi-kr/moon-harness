"""hooks.lib.self_improve — self-improving-harness 공유 결정적 코어 패키지.

arch §3.1 "Shared deterministic library"의 단일 import 지점. stdlib only,
네트워크/LLM 무호출. 두 스킬(pr-converge, self-improve)이 공유하는 결정적
로직(상태 I/O, schema guard, 커서, 게이트 등)이 이 패키지 아래 모인다.

T-1에서는 state I/O 유닛만 노출한다. 이후 Wave에서 tier classifier,
protected-set guard, cursor engine 등이 추가된다.
"""

from hooks.lib.self_improve.state_io import (
    SCHEMA_VERSION,
    atomic_write,
    check_schema_version,
    initial_pr_converge_state,
    initial_retro_state,
    load_state,
    load_state_checked,
    now_iso,
    parse_iso,
)
from hooks.lib.self_improve.tier import (
    HARNESS,
    PROJECT,
    classify_tier,
)
from hooks.lib.self_improve.guard import (
    PROTECTED_SET,
    is_protected,
)
from hooks.lib.self_improve.parser import (
    extract_provenance,
    parse_learning_entry,
)

__all__ = [
    "SCHEMA_VERSION",
    "load_state",
    "load_state_checked",
    "atomic_write",
    "check_schema_version",
    "now_iso",
    "parse_iso",
    "initial_pr_converge_state",
    "initial_retro_state",
    # T-2: tier classifier
    "classify_tier",
    "PROJECT",
    "HARNESS",
    # T-2: protected-set guard
    "is_protected",
    "PROTECTED_SET",
    # T-2: provenance + tag parser
    "parse_learning_entry",
    "extract_provenance",
]
