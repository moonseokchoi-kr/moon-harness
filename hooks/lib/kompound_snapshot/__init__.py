"""hooks.lib.kompound_snapshot — kompound 박제(snapshot) 결정적 코어 패키지.

`hooks/lib/self_improve/`의 형제 패키지다. SDD 사이클이 만든 spec/arch/ui/api
/context/result 문서를 marvelous_kompound(`raw/` + `wiki/sdd-spec-registry.md`
+ `wiki/index.md` + `wiki/log.md`)에 verbatim 박제하는 로직을 담는다.

설계 SSOT: docs/sdd/design/arch/2026-07-29-kompound-snapshot-hook.md
(이하 "arch"로 인용) §3(모듈 분해) · §6(영속화/IO 경계) · §9.3(공용 fixture).

## Fail-safe 규약 (arch §1 원칙 2, CLAUDE.md 결정↔판단 분리)

이 패키지의 모든 공개 함수는 **예외를 밖으로 던지지 않는다.** 무엇이 잘못됐는지는
구조화된 결과 dict(예: ``{"ok": bool, ...}``)로 반환하고, 예상치 못한 예외는 최상위
`cli.main()`이 잡아 F11의 "스캔 실패"(``scan_error``) 신호로 변환한다. 이 패키지는
stdlib만 사용하며 네트워크/LLM 호출을 하지 않는다(F13). `git` 서브프로세스 호출은
예외다 — 로컬 상태 조회/커밋에 한하며 `fetch`/`pull`/`push`는 절대 하지 않는다(A3).

## 12모듈 구성 (arch §3.1 디렉토리 경계 — 각 모듈이 이 파일 아래에 추가된다)

| 모듈 | 책임 (arch §3.2 요약) |
|---|---|
| ``config`` | F16 설정 해석 — env → 프로젝트 파일 → 홈 파일 → 자동 탐색, 키 단위 병합. 단일 진입점 ``resolve_config()`` |
| ``scan`` | F3 앵커 탐색 · 포함/제외 · md5 수집 (read-only) |
| ``naming`` | F4 네이밍 변환 + F12 미등록 프리픽스 판정 (순수 함수) |
| ``dedup`` | F5 md5 그룹핑 · canonical 선택 (순수 함수) |
| ``apply`` | F6 멱등 적용 — (i) raw 복사 (ii) 카탈로그 갱신의 2단 트랜잭션 + 단계별 저널/롤백 |
| ``registry`` | F7 `sdd-spec-registry.md` 표 탐색 3단 · 행/열 외과적 수정 · 카운트 문장 갱신 |
| ``wiki_log`` | F7·F10 `index.md` prepend · `log.md` append (append/prepend-only) |
| ``verify`` | F8 검증 게이트 3종 (read-only) — ``snapshot_set_rule`` 전제 |
| ``git_state`` | F9 dirty/divergence 판정(네트워크 없이) · 커밋 · 배타 락 |
| ``wt_target`` | F2 Bash 명령 문자열 → 워크트리 경로 파싱 (순수 함수) |
| ``report`` | F11 verdict/종료 코드 분리 · human/JSON 리포트 — 종료 코드 표(arch §6.2)의 단일 진실 |
| ``runtime_state`` | T1 멱등·무장·안내 1회 판정 — 런타임 상태 값 6종(arch §5.1.2)의 단일 진실, `.claude/state/kompound-snapshot.json` |

**주의**: 종료 코드 표(0/10/20/30/40/45/50/55/60/70)와 런타임 상태 값 6종
(``PENDING``/``CATALOG_PENDING``/``DONE``/``SKIPPED_UNCONFIGURED``/``FAILED``/
``GIVEN_UP``)은 여러 모듈이 참조하지만 그 정의의 단일 진실은 각각 ``report``와
``runtime_state``다(위 표, arch §11 F1/F11 추적 행). 이 ``__init__.py``는 그
값들을 중복 정의하지 않는다 — 이 파일이 아직 어떤 모듈도 import하지 않기 때문이다.

## 현재 상태 (T-11 — 전 모듈 완비, 공개 API 재노출 완료)

12모듈이 전부 갖춰졌다(위 표). 이 파일은 각 모듈의 공개 함수/상수를
재노출한다(``hooks/lib/self_improve/__init__.py`` 관례 — 하위 모듈을 직접
import하지 않고도 ``from hooks.lib.kompound_snapshot import resolve_config``
형태로 쓸 수 있게 한다). 재노출은 **읽기 전용 별칭**일 뿐 로직을 담지
않는다 — 종료 코드 표·런타임 상태 6종의 단일 진실은 여전히 각각 ``report``/
``runtime_state``다(위 "주의" 문단, 변경 없음).

순환 import 없음: 이 파일은 하위 모듈만 import하고(형제 관계), 하위 모듈은
서로를 import할 뿐(``apply`` → ``git_state``/``naming``/``registry``/
``runtime_state``/``verify``/``wiki_log``, ``cli`` → 전 모듈) 이 파일을
역참조하지 않는다.

> 📌 **`scan`/`dedup`/`apply`는 예외적으로 함수가 아니라 모듈 자체를
> 재노출한다.** 세 모듈 모두 자기 이름과 동일한 이름의 함수를 노출한다
> (``scan.scan``/``dedup.dedup``/``apply.apply``) — 만약 이 파일이 다른
> 모듈들처럼 ``from .scan import scan``으로 함수를 끌어올리면, 패키지
> 속성 ``kompound_snapshot.scan``이 그 함수로 리바인딩되어 서브모듈
> 참조를 잃는다(``from hooks.lib.kompound_snapshot import scan as X``가
> 모듈 대신 함수를 반환하게 됨). 기존 `tests/test_kompound_snapshot_apply.py`
> (T-10, frozen)가 ``from hooks.lib.kompound_snapshot import apply as
> apply_mod`` 뒤 ``apply_mod.apply(...)``로 호출하는 계약을 이미 갖고
> 있으므로, 이 세 이름은 **모듈**로 고정한다. 호출자는
> ``kompound_snapshot.scan.scan(...)``/``kompound_snapshot.dedup.dedup(...)``/
> ``kompound_snapshot.apply.apply(...)`` 형태로 쓴다.

## 의존 방향 (arch §4)

``kompound_snapshot`` → ``hooks.lib.self_improve.state_io`` (단방향, 원자적
write·ISO 시간 유틸 재사용). 역방향 의존은 없다 — ``self_improve``는 이
패키지를 절대 import하지 않는다.
"""

from __future__ import annotations

from hooks.lib.kompound_snapshot.config import DEFAULT_PREFIX_MAP, resolve_config
from hooks.lib.kompound_snapshot.naming import name_document, resolve_prefix
# scan/dedup는 함수가 아니라 모듈 자체를 재노출한다 — 위 "📌" 문단 참조.
from hooks.lib.kompound_snapshot import dedup, scan
from hooks.lib.kompound_snapshot.registry import update_registry
from hooks.lib.kompound_snapshot.wiki_log import append_log, build_snapshot_log_line, update_index
from hooks.lib.kompound_snapshot.verify import (
    build_verify_report,
    effective_prefixes,
    matches_snapshot_rule,
    run_gates,
    snapshot_population,
    snapshot_registry_links,
    snapshot_set_rule,
    should_run_gates,
)
from hooks.lib.kompound_snapshot.git_state import (
    acquire_lock,
    check_dirty,
    check_divergence,
    check_preconditions,
    commit_catalog,
    commit_raw,
    release_lock,
)
from hooks.lib.kompound_snapshot.wt_target import find_worktree_removal_targets, is_worktree_path
from hooks.lib.kompound_snapshot.report import (
    EXIT_BUSY,
    EXIT_CATALOG_UNPARSED,
    EXIT_DISABLED,
    EXIT_OK,
    EXIT_PENDING,
    EXIT_PRECONDITION_FAILED,
    EXIT_SCAN_ERROR,
    EXIT_UNMAPPED_BLOCKING,
    EXIT_VERIFY_FAILED,
    EXIT_WRITE_FAILED,
    RUNTIME_STATUSES,
    VERDICT_TABLE,
    blocks_deletion,
    build_human_text,
    build_inherited_warning,
    build_report,
    emit_report,
    exit_code_for_verdict,
    pending_unmapped_disjoint,
    stage_for_verdict,
)
from hooks.lib.kompound_snapshot.runtime_state import (
    CATALOG_PENDING,
    DONE,
    FAILED,
    GIVEN_UP,
    KOMPOUND_MAX_BLOCKS,
    PENDING,
    SKIPPED_UNCONFIGURED,
    STATUSES,
    record_and_decide,
    record_apply_outcome,
    should_emit_unconfigured_notice,
    state_path_for,
)
# apply/cli는 위 리프 모듈에 의존하므로 마지막에 둔다(가독성 목적 — Python의
# fromlist import 처리는 순서와 무관하게 안전하지만, 의존 순서대로 나열하면
# "무엇이 무엇 위에 조립되는지"가 이 파일만 읽어도 드러난다).
# apply도 scan/dedup와 같은 이유로 모듈 자체를 재노출한다(위 "📌" 문단).
from hooks.lib.kompound_snapshot import apply
from hooks.lib.kompound_snapshot.cli import build_parser, main

__all__ = [
    # config
    "DEFAULT_PREFIX_MAP",
    "resolve_config",
    # scan
    "scan",
    # naming
    "name_document",
    "resolve_prefix",
    # dedup
    "dedup",
    # apply
    "apply",
    # registry
    "update_registry",
    # wiki_log
    "append_log",
    "build_snapshot_log_line",
    "update_index",
    # verify
    "build_verify_report",
    "effective_prefixes",
    "matches_snapshot_rule",
    "run_gates",
    "snapshot_population",
    "snapshot_registry_links",
    "snapshot_set_rule",
    "should_run_gates",
    # git_state
    "acquire_lock",
    "check_dirty",
    "check_divergence",
    "check_preconditions",
    "commit_catalog",
    "commit_raw",
    "release_lock",
    # wt_target
    "find_worktree_removal_targets",
    "is_worktree_path",
    # report
    "EXIT_BUSY",
    "EXIT_CATALOG_UNPARSED",
    "EXIT_DISABLED",
    "EXIT_OK",
    "EXIT_PENDING",
    "EXIT_PRECONDITION_FAILED",
    "EXIT_SCAN_ERROR",
    "EXIT_UNMAPPED_BLOCKING",
    "EXIT_VERIFY_FAILED",
    "EXIT_WRITE_FAILED",
    "RUNTIME_STATUSES",
    "VERDICT_TABLE",
    "blocks_deletion",
    "build_human_text",
    "build_inherited_warning",
    "build_report",
    "emit_report",
    "exit_code_for_verdict",
    "pending_unmapped_disjoint",
    "stage_for_verdict",
    # runtime_state
    "CATALOG_PENDING",
    "DONE",
    "FAILED",
    "GIVEN_UP",
    "KOMPOUND_MAX_BLOCKS",
    "PENDING",
    "SKIPPED_UNCONFIGURED",
    "STATUSES",
    "record_and_decide",
    "record_apply_outcome",
    "should_emit_unconfigured_notice",
    "state_path_for",
    # cli
    "build_parser",
    "main",
]
