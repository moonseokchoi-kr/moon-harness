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
from hooks.lib.self_improve.cursor import (
    get_new_entries,
)
from hooks.lib.self_improve.recurrence import (
    count_signals,
    has_cross_project,
)
from hooks.lib.self_improve.precheck import (
    run_prechecks,
)
from hooks.lib.self_improve.circuit_breaker import (
    FIX_ATTEMPTS_THRESHOLD,
    ITERATIONS_THRESHOLD,
    check_circuit_breaker,
    compute_cadence,
)
from hooks.lib.self_improve.cap import (
    DEFAULT_CAP,
    apply_cap,
    cap_report,
)
from hooks.lib.self_improve.memory_router import (
    DEFAULT_ALWAYS_ON_BUDGET,
    DEFAULT_ONDEMAND_BUDGET,
    route_memory,
)
from hooks.lib.self_improve.ladder import (
    LADDER_RUNGS,
    get_next_ladder_rung,
)
from hooks.lib.self_improve.metrics import (
    COLD_START_THRESHOLD,
    avg_iterations_to_green,
    compute_metrics,
    convergence_rate,
    recurrence_rate,
    retro_log_parser,
    skill_reuse_rate,
    write_metrics,
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
    # T-3: cursor engine
    "get_new_entries",
    # T-3: recurrence counter
    "count_signals",
    "has_cross_project",
    # T-3: pre-check engine
    "run_prechecks",
    # T-4: circuit breaker + cadence
    "FIX_ATTEMPTS_THRESHOLD",
    "ITERATIONS_THRESHOLD",
    "check_circuit_breaker",
    "compute_cadence",
    # T-4: cap engine
    "DEFAULT_CAP",
    "apply_cap",
    "cap_report",
    # T-4: on-demand memory router
    "DEFAULT_ALWAYS_ON_BUDGET",
    "DEFAULT_ONDEMAND_BUDGET",
    "route_memory",
    # T-4: learning ladder
    "LADDER_RUNGS",
    "get_next_ladder_rung",
    # T-11: metrics telemetry (F23)
    "COLD_START_THRESHOLD",
    "retro_log_parser",
    "convergence_rate",
    "avg_iterations_to_green",
    "recurrence_rate",
    "skill_reuse_rate",
    "compute_metrics",
    "write_metrics",
]
