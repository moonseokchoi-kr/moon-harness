"""hooks/lib/kompound_snapshot/runtime_state.py — F1 런타임 상태 (T-7).

설계 SSOT: `docs/sdd/design/arch/2026-07-29-kompound-snapshot-hook.md`
§5.1.2(확정 사항 — 상태 값 6종·블록 상한·상태 파일 위치),
§5.1.3("박제 미완이면 전진 금지"의 판정 — 4조건 AND, 판정표, T1의 (i)/(ii)
정책, `CATALOG_PENDING` 확정 규칙 D-1), §5.1.4(서킷브레이커와의 조화, A-1
원칙), §5.2.3(T1→T2 승계 노출 표), §6.1 "④ 미설정 안내 1회의 기억 위치"
(M-18).

이 모듈이 **런타임 상태 값 6종의 단일 진실**이다(T-2 확정 사항 #1):

    PENDING | CATALOG_PENDING | DONE | SKIPPED_UNCONFIGURED | FAILED | GIVEN_UP

`report.py`(T-6)의 `RUNTIME_STATUSES` 튜플은 이 값을 참조용으로만 나열할
뿐 재정의가 아니다 — 두 모듈이 병렬 구현이라 서로 import하지 않고, 대신
이름이 정확히 일치하는지는 이 태스크의 회귀 테스트
(`tests/test_kompound_snapshot_runtime_state.py`)가 고정한다.

## 저장 위치 (arch §5.1.2 — 헷갈리지 말 것)

    <project_root>/.claude/state/kompound-snapshot.json   (이 모듈, 런타임 상태)
    <project_root>/.claude/kompound-snapshot.config.json   (T-3 config.py, 설정 — 다른 파일)

## `CATALOG_PENDING`의 핵심 계약 (D-1, arch §5.1.3)

(i) raw 복사는 성공했지만 (ii) 카탈로그 갱신만 실패한 상태. T1 판정에서
**`DONE`과 동일하게 통과** 처리한다 — 재차 block 없음, 블록 예산 미소모.

이 모듈은 `CATALOG_PENDING` 패스스루 검사를 **`pending == 0`(DONE) 판정보다도
앞서** 수행한다(arch 문언은 "조건 4(`pending ≥ 1`)보다 앞서"만 요구하지만,
그보다 먼저 `pending == 0` 검사를 배치하면 (i)가 이미 성공해 해당 문서의
raw 내용이 kompound와 일치하는 순간 `pending` 재계산 값이 자연히 0이 되어
`CATALOG_PENDING`이 `DONE`으로 조용히 덮여 §10.4-11의 drift 관측이 무너진다.
그래서 이 모듈은 `CATALOG_PENDING` 패스스루를 `config` 확인 다음, `pending`
값을 보기 **전에** 배치한다 — 이것이 이 태스크가 arch 위에서 직접 내린
설계 결정이다).

## 블록 예산 (arch §5.1.4, A-1)

`KOMPOUND_MAX_BLOCKS = 3` — 자체 카운터 전용. 기존
`stop-pipeline.py`의 `increment_breaker`/`CB_MAX_BLOCKS=20`을 호출하지도,
그 상태를 읽지도 않는다(상태 공유 시 `pipeline.json` 부재 환경에서
`AttributeError`가 나 조용히 통과해버리는 함정을 피한다).

**A-1 원칙**: "예산을 기록할 수 없으면 예산을 소비하는 결정(block)을 내리지
않는다." 순서는 "판정 → 상태 write → (성공 시에만) block 반환"이다.
`record_and_decide()`는 write 실패 시 항상 `{"action": "pass", "reason":
"state_write_failed"}` 류를 반환한다(block 없음).

## 무장(arming)·서명·블록 예산 스코프 (이 태스크가 arch 위에서 내린 결정)

`baseline_signature`(무장 판정 전용)와 `armed_signature`(진행 중인 사이클을
식별하는 스코프 키)를 분리해서 보유한다. arch는 이 둘의 구현 분리를
명시하지 않았지만, 아래 두 요구를 **동시에** 만족하려면 분리가 필요하다:

1. 같은 COMPLETED 사이클 안에서 여러 번의 Stop 훅 호출에 걸쳐 `blocks`가
   누적돼야 한다(0→1→2→3→GIVEN_UP).
2. `armed_session_id`가 바뀌면 `blocks`가 리셋되고, **STATE 서명이 바뀌면
   (=다음 사이클) `GIVEN_UP`도 자동으로 리셋된다**(arch §5.1.4 마지막 문단).

`baseline_signature`는 "무장 안 됨"(row 1) 분기에서만 갱신되고(즉 STATE가
COMPLETED가 아니거나 오래됐거나 서명이 안 바뀐 동안 계속 최신값을 따라간다),
"무장됨" 분기에서는 건드리지 않는다 — 그래서 같은 COMPLETED 사이클 내내
"현재 서명 != baseline"이 유지돼 반복 무장이 성립한다. `armed_signature`는
무장된 동안의 실제 판정 스코프 키로, 이 값이 이전 호출과 달라지면(=새
사이클이 시작됐다는 뜻) `blocks`와 이전 `status`를 리셋한 뒤 판정을
새로 시작한다.

## Fail-safe 규약 (패키지 전체 규약)

모든 공개 함수는 예외를 밖으로 던지지 않는다. 예기치 못한 오류는 구조화된
dict(`{"action": "pass", "reason": "internal_error", ...}` 류)로 흡수한다.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from hooks.lib.self_improve.state_io import atomic_write, load_state, now_iso, parse_iso

__all__ = [
    "PENDING",
    "CATALOG_PENDING",
    "DONE",
    "SKIPPED_UNCONFIGURED",
    "FAILED",
    "GIVEN_UP",
    "STATUSES",
    "KOMPOUND_MAX_BLOCKS",
    "DEFAULT_STATE_MAX_AGE_HOURS",
    "DEFAULT_NOTICE_WINDOW_HOURS",
    "state_path_for",
    "parse_orchestrator_state",
    "is_state_fresh",
    "compute_signature",
    "record_and_decide",
    "record_apply_outcome",
    "should_emit_unconfigured_notice",
]

PathLike = Union[str, "Path"]

# ── 상태 값 6종 (단일 진실 — arch §5.1.2) ───────────────────────────────────
PENDING = "PENDING"
CATALOG_PENDING = "CATALOG_PENDING"
DONE = "DONE"
SKIPPED_UNCONFIGURED = "SKIPPED_UNCONFIGURED"
FAILED = "FAILED"
GIVEN_UP = "GIVEN_UP"

STATUSES = (PENDING, CATALOG_PENDING, DONE, SKIPPED_UNCONFIGURED, FAILED, GIVEN_UP)

# ── 확정 상수 (arch §5.1.2) ─────────────────────────────────────────────────
KOMPOUND_MAX_BLOCKS = 3
DEFAULT_STATE_MAX_AGE_HOURS = 24
DEFAULT_NOTICE_WINDOW_HOURS = 24  # arch §6.1 ④ — session id 없을 때의 창

_STATE_RELATIVE = Path(".claude") / "state" / "kompound-snapshot.json"
_ENV_SESSION_ID = "CLAUDE_SESSION_ID"

_STATUS_RE = re.compile(r"^-?\s*(?:상태|status)\s*:\s*([A-Za-z0-9_]+)", re.MULTILINE)
_FEATURE_RE_BACKTICK = re.compile(r"^-?\s*feature\s*:\s*`([^`]+)`", re.MULTILINE | re.IGNORECASE)
_FEATURE_RE_PLAIN = re.compile(r"^-?\s*feature\s*:\s*(\S+)", re.MULTILINE | re.IGNORECASE)

# 프로세스 내 안내-1회 플래그 (M-18, 층 1 — 영속 write 실패에도 이 프로세스
# 안에서는 절대 두 번 emit하지 않는다). 키 = 런타임 상태 파일의 str 경로.
_PROCESS_NOTICE_EMITTED: set = set()


# ── 경로 ─────────────────────────────────────────────────────────────────────


def state_path_for(project_root: PathLike) -> Path:
    """`<project_root>/.claude/state/kompound-snapshot.json` 경로를 반환한다.

    T-3 `config.py`의 프로젝트 설정 파일(`.claude/kompound-snapshot.config.json`)과
    **다른 파일**이다 — 이 함수가 만드는 건 런타임 상태(코어 출력)이고,
    설정은 사람이 쓰는 입력이다(arch §6.1 📌).
    """
    return Path(project_root) / _STATE_RELATIVE


def _default_runtime_state() -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "status": None,
        "baseline_signature": None,
        "armed_signature": None,
        "armed_session_id": None,
        "blocks": 0,
        "catalog_lag_count": 0,
        "notice": None,
        "updated_at": None,
    }


def _load_runtime(state_file: Path) -> Dict[str, Any]:
    loaded = load_state(state_file)
    if not isinstance(loaded, dict):
        return _default_runtime_state()
    merged = _default_runtime_state()
    merged.update(loaded)
    return merged


# ── STATE 파서 (`- 상태:` / `status:` 둘 다 허용 — §10.3 발견 사항 계승) ────


def parse_orchestrator_state(text: str) -> Dict[str, Optional[str]]:
    """`ORCHESTRATOR_STATE.md` 텍스트에서 `feature`/`status`를 추출한다.

    - 상태 라벨은 `- 상태: <VALUE>`와 `status: <VALUE>` 둘 다 허용한다.
      값은 첫 word-문자 런(`[A-Za-z0-9_]+`)만 취한다 — 뒤에 괄호로 붙는
      주석·마크다운 서식(`(**2026-07-30 재개** ...)`)에 흔들리지 않는다.
    - feature는 백틱으로 감싼 슬러그(`- feature: \\`slug\\``)를 우선
      시도하고, 없으면 평문 토큰으로 폴백한다.
    - 파싱 실패(라벨 부재)는 예외가 아니라 해당 키 `None`으로 흡수한다.
    """
    feature: Optional[str] = None
    status: Optional[str] = None
    try:
        m = _FEATURE_RE_BACKTICK.search(text)
        if m:
            feature = m.group(1).strip()
        else:
            m2 = _FEATURE_RE_PLAIN.search(text)
            if m2:
                feature = m2.group(1).strip()

        m3 = _STATUS_RE.search(text)
        if m3:
            status = m3.group(1).strip()
    except Exception:  # noqa: BLE001 - fail-safe, 파싱은 절대 던지지 않는다
        return {"feature": feature, "status": status}
    return {"feature": feature, "status": status}


# ── STATE 신선도 (보조 조건, arch §5.1.3 조건 2) ────────────────────────────


def is_state_fresh(
    state_file: PathLike, max_age_hours: float, *, now: Optional[datetime] = None
) -> bool:
    """`state_file`의 mtime이 `max_age_hours` 이내인가(보조 조건, 주 방어 아님).

    stat 실패(파일 부재·권한)는 신선하지 않음(`False`)으로 안전하게 처리한다.
    """
    try:
        mtime = Path(state_file).stat().st_mtime
    except OSError:
        return False
    now_dt = now if now is not None else datetime.now(timezone.utc)
    now_ts = now_dt.timestamp()
    age_hours = (now_ts - mtime) / 3600.0
    return age_hours <= max_age_hours


# ── 서명 (arch §5.1.3 조건 1 — (feature, 상태, result 문서 경로)) ───────────


def _latest_result_doc(project_root: Path, feature: Optional[str]) -> Optional[str]:
    """`docs/sdd/result/*-<feature>.md` 중 가장 최근(사전식 최대 = 최신
    날짜 프리픽스) 경로를 반환한다. 없거나 feature 미상이면 `None`.

    `result 문서 경로`를 서명의 3번째 축으로 쓰는 이유: 동일 feature가
    여러 사이클(재작업)을 거칠 때 result 문서 파일명의 날짜 프리픽스가
    사이클마다 달라지므로, 같은 feature·같은 COMPLETED 상태라도 사이클을
    구분하는 근거가 된다.
    """
    if not feature:
        return None
    result_dir = project_root / "docs" / "sdd" / "result"
    try:
        if not result_dir.is_dir():
            return None
        candidates = sorted(
            str(p) for p in result_dir.glob(f"*-{feature}.md") if p.is_file()
        )
    except OSError:
        return None
    if not candidates:
        return None
    return candidates[-1]


def compute_signature(project_root: PathLike, state_text: str) -> List[Optional[str]]:
    """(feature, status, result_doc_path) 서명을 JSON 직렬화 가능한 리스트로
    반환한다(arch §5.1.3 조건 1)."""
    parsed = parse_orchestrator_state(state_text)
    feature = parsed.get("feature")
    status = parsed.get("status")
    result_doc = _latest_result_doc(Path(project_root), feature)
    return [feature, status, result_doc]


def _effective_session_id(session_id: Optional[str]) -> Optional[str]:
    if session_id is not None:
        return session_id
    return os.environ.get(_ENV_SESSION_ID) or None


# ── 메인 판정 (arch §5.1.3 판정표 + D-1 + A-1) ──────────────────────────────


def record_and_decide(
    project_root: PathLike,
    orchestrator_state_path: PathLike,
    *,
    config_ok: bool,
    pending_count: int,
    unmapped_count: int = 0,
    state_max_age_hours: Optional[float] = None,
    session_id: Optional[str] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """T1 판정의 단일 진입점 — arch §5.1.3 판정표를 그대로 구현한다.

    Args:
        project_root: 프로젝트 루트(런타임 상태 파일 위치 기준).
        orchestrator_state_path: `ORCHESTRATOR_STATE.md` 경로.
        config_ok: F16 `resolve_config()["ok"]` — kompound 경로가
            해석됐는지. `False`면 `SKIPPED_UNCONFIGURED`.
        pending_count: 프리픽스가 매핑된 미박제 문서 수(F12 `unmapped`는
            **포함하지 않는다** — 별도 인자로 분리, arch §5.1.3 J-11).
        unmapped_count: F12 미등록 프리픽스 문서 수. 이 함수의 차단/통과
            판정에는 영향을 주지 않는다(T1은 `pending`만 본다) — 그래도
            시그니처에 별도 인자로 받아 T-11 배선에서 두 카운트가 섞이지
            않도록 강제한다.
        state_max_age_hours: STATE 신선도 상한. 생략 시
            `DEFAULT_STATE_MAX_AGE_HOURS`(24) — 실제로는 T-3
            `config.py`의 `state_max_age_hours`를 호출자가 주입한다.
        session_id: 생략 시 `CLAUDE_SESSION_ID` 환경변수.
        now: 테스트 주입용. 생략 시 UTC 현재시각.

    Returns:
        ``{"action": "block"|"pass", "reason": str, "status": str|None,
        "blocks": int, ...}``. 예외를 던지지 않는다.
    """
    try:
        return _record_and_decide_impl(
            project_root=Path(project_root),
            orchestrator_state_path=Path(orchestrator_state_path),
            config_ok=bool(config_ok),
            pending_count=int(pending_count),
            unmapped_count=int(unmapped_count),
            max_age_hours=(
                float(state_max_age_hours)
                if state_max_age_hours is not None
                else float(DEFAULT_STATE_MAX_AGE_HOURS)
            ),
            session_id=session_id,
            now=now,
        )
    except Exception as exc:  # noqa: BLE001 - fail-safe, 코어 예외는 통과+FAILED
        result = {
            "action": "pass",
            "reason": "internal_error",
            "status": FAILED,
            "blocks": 0,
            "error": str(exc),
        }
        try:
            state_file = state_path_for(project_root)
            runtime = _load_runtime(state_file)
            runtime["status"] = FAILED
            runtime["updated_at"] = now_iso()
            atomic_write(state_file, runtime)
        except Exception:  # noqa: BLE001 - 이중 fail-safe, 기록 실패해도 통과는 유지
            pass
        return result


def _record_and_decide_impl(
    *,
    project_root: Path,
    orchestrator_state_path: Path,
    config_ok: bool,
    pending_count: int,
    unmapped_count: int,
    max_age_hours: float,
    session_id: Optional[str],
    now: Optional[datetime],
) -> Dict[str, Any]:
    now_dt = now if now is not None else datetime.now(timezone.utc)
    state_file = state_path_for(project_root)
    runtime = _load_runtime(state_file)
    sid = _effective_session_id(session_id)

    try:
        state_text = orchestrator_state_path.read_text(encoding="utf-8")
    except OSError:
        return {
            "action": "pass",
            "reason": "state_missing",
            "status": runtime.get("status"),
            "blocks": int(runtime.get("blocks", 0) or 0),
        }

    current_signature = compute_signature(project_root, state_text)
    parsed = parse_orchestrator_state(state_text)
    status_value = parsed.get("status")
    is_completed = status_value == "COMPLETED"

    baseline = runtime.get("baseline_signature")
    is_first_observation = baseline is None
    fresh = is_state_fresh(orchestrator_state_path, max_age_hours, now=now_dt)

    armed = (
        (not is_first_observation)
        and (current_signature != baseline)
        and fresh
        and is_completed
    )

    if not armed:
        if is_first_observation:
            reason = "baseline_registered"
        elif not fresh:
            reason = "state_stale"
        elif not is_completed:
            reason = "state_not_completed"
        else:
            reason = "signature_unchanged"

        new_runtime = dict(runtime)
        new_runtime["baseline_signature"] = current_signature
        new_runtime["updated_at"] = now_iso()
        write_result = atomic_write(state_file, new_runtime)
        return {
            "action": "pass",
            "reason": reason,
            "status": runtime.get("status"),
            "blocks": int(runtime.get("blocks", 0) or 0),
            "write_ok": bool(write_result.get("ok")),
        }

    # ── 무장됨. 사이클 스코프(armed_signature)·세션 스코프를 확인한다. ──
    prev_armed_signature = runtime.get("armed_signature")
    signature_changed = prev_armed_signature != current_signature
    stored_session = runtime.get("armed_session_id")
    session_changed = bool(sid) and stored_session != sid

    if signature_changed or session_changed:
        # 새 사이클(서명 변화) 또는 세션 전환 — blocks·직전 status를 리셋한다
        # (arch §5.1.4: "GIVEN_UP은 STATE 서명이 바뀌면 자동으로 초기화된다",
        # "armed_session_id가 바뀌면 blocks를 0으로 초기화한다").
        blocks = 0
        prev_status: Optional[str] = None
    else:
        blocks = int(runtime.get("blocks", 0) or 0)
        prev_status = runtime.get("status")

    def _persist(status_out: str, *, blocks_out: int, catalog_lag_delta: int = 0) -> Dict[str, Any]:
        payload = dict(runtime)
        payload["status"] = status_out
        payload["baseline_signature"] = baseline  # 무장 상태 동안 baseline은 고정
        payload["armed_signature"] = current_signature
        payload["armed_session_id"] = sid
        payload["blocks"] = blocks_out
        if catalog_lag_delta:
            payload["catalog_lag_count"] = int(runtime.get("catalog_lag_count", 0) or 0) + catalog_lag_delta
        payload["updated_at"] = now_iso()
        return atomic_write(state_file, payload)

    # 2) config 미해석 (F16) → SKIPPED_UNCONFIGURED, block 없음
    if not config_ok:
        write_result = _persist(SKIPPED_UNCONFIGURED, blocks_out=blocks)
        return {
            "action": "pass",
            "reason": "config_unconfigured",
            "status": SKIPPED_UNCONFIGURED,
            "blocks": blocks,
            "unmapped_count": unmapped_count,
            "write_ok": bool(write_result.get("ok")),
        }

    # 3) 직전 상태가 CATALOG_PENDING → DONE과 동일 취급, blocks 미증가 (D-1).
    #    조건 4(pending>=1)는 물론, pending==0(DONE) 판정보다도 앞서
    #    검사한다 — 그렇지 않으면 (i) 성공으로 pending이 자연히 0이 되는
    #    순간 CATALOG_PENDING이 DONE으로 조용히 덮여 drift 관측이 무너진다
    #    (모듈 docstring 참조).
    if prev_status == CATALOG_PENDING:
        write_result = _persist(CATALOG_PENDING, blocks_out=blocks)
        return {
            "action": "pass",
            "reason": "catalog_pending_passthrough",
            "status": CATALOG_PENDING,
            "blocks": blocks,
            "unmapped_count": unmapped_count,
            "write_ok": bool(write_result.get("ok")),
        }

    # 4) pending == 0 → DONE (재진입 시 무동작, F1 멱등)
    if pending_count <= 0:
        write_result = _persist(DONE, blocks_out=blocks, catalog_lag_delta=0)
        return {
            "action": "pass",
            "reason": "no_pending",
            "status": DONE,
            "blocks": blocks,
            "unmapped_count": unmapped_count,
            "write_ok": bool(write_result.get("ok")),
        }

    # 4-b) 직전 상태가 GIVEN_UP → 다음 Stop부터 통과(재블록 없음). pending==0
    #      이었다면 위에서 이미 DONE으로 해소됐으므로, 여기 도달했다는 건
    #      여전히 미완이라는 뜻 — GIVEN_UP을 유지하고 재블록하지 않는다.
    if prev_status == GIVEN_UP:
        write_result = _persist(GIVEN_UP, blocks_out=blocks)
        return {
            "action": "pass",
            "reason": "given_up_passthrough",
            "status": GIVEN_UP,
            "blocks": blocks,
            "unmapped_count": unmapped_count,
            "write_ok": bool(write_result.get("ok")),
        }

    # 5) pending >= 1, blocks < 3 → block, PENDING, blocks += 1
    if blocks < KOMPOUND_MAX_BLOCKS:
        new_blocks = blocks + 1
        write_result = _persist(PENDING, blocks_out=new_blocks)
        if not write_result.get("ok"):
            # A-1: 상태 write가 실패하면 block하지 않는다(영구 블록 방지).
            return {
                "action": "pass",
                "reason": "state_write_failed",
                "status": prev_status,
                "blocks": blocks,
                "unmapped_count": unmapped_count,
                "warning": "runtime state write failed; passing without blocking (A-1)",
            }
        return {
            "action": "block",
            "reason": "pending_blocked",
            "status": PENDING,
            "blocks": new_blocks,
            "unmapped_count": unmapped_count,
            "write_ok": True,
        }

    # 6) pending >= 1, blocks == 3 → 마지막 1회 block 후 GIVEN_UP
    write_result = _persist(GIVEN_UP, blocks_out=blocks)
    if not write_result.get("ok"):
        return {
            "action": "pass",
            "reason": "state_write_failed",
            "status": prev_status,
            "blocks": blocks,
            "unmapped_count": unmapped_count,
            "warning": "runtime state write failed; passing without blocking (A-1)",
        }
    return {
        "action": "block",
        "reason": "budget_exhausted",
        "status": GIVEN_UP,
        "blocks": blocks,
        "unmapped_count": unmapped_count,
        "message": "3회 안내했으나 미완 — T2가 워크트리 삭제 시 재차 막습니다.",
        "write_ok": True,
    }


# ── apply() 결과 반영 — T1의 (i)/(ii) 정책 (arch §5.1.3) ────────────────────


def record_apply_outcome(
    project_root: PathLike,
    *,
    raw_ok: bool,
    catalog_ok: bool,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """`apply()` 실행 결과를 런타임 상태에 반영한다(arch §5.1.3 (i)/(ii) 표).

    - (i) 성공 + (ii) 성공 → `DONE`.
    - (i) 성공 + (ii) 실패 → `CATALOG_PENDING`(`catalog_lag_count` 증가,
      `blocks`는 건드리지 않는다 — D-1).
    - (i) 실패 → `PENDING`(F1의 실패 보고 경로 — 재시도 대상. 블록 예산
      증가는 다음 `record_and_decide()` 호출이 담당한다, 여기서 증가시키지
      않는다).

    카탈로그 재시도의 주체는 이 함수의 호출자가 아니다(다음 사이클의 (ii)
    단계·T2 자동 박제·수동 실행). 이 함수는 상태 기록만 담당한다.
    """
    try:
        root = Path(project_root)
        state_file = state_path_for(root)
        runtime = _load_runtime(state_file)

        if raw_ok and catalog_ok:
            new_status = DONE
            catalog_lag_count = 0
        elif raw_ok and not catalog_ok:
            new_status = CATALOG_PENDING
            catalog_lag_count = int(runtime.get("catalog_lag_count", 0) or 0) + 1
        else:
            new_status = PENDING
            catalog_lag_count = int(runtime.get("catalog_lag_count", 0) or 0)

        payload = dict(runtime)
        payload["status"] = new_status
        payload["catalog_lag_count"] = catalog_lag_count
        payload["updated_at"] = (now.isoformat() if now is not None else now_iso())
        write_result = atomic_write(state_file, payload)
        return {
            "status": new_status,
            "catalog_lag_count": catalog_lag_count,
            "write_ok": bool(write_result.get("ok")),
        }
    except Exception as exc:  # noqa: BLE001 - fail-safe
        return {"status": FAILED, "catalog_lag_count": 0, "write_ok": False, "error": str(exc)}


# ── 안내 1회 (F16, arch §6.1 ④ M-18 — 유일한 소유자) ────────────────────────


def should_emit_unconfigured_notice(
    project_root: PathLike,
    *,
    session_id: Optional[str] = None,
    now: Optional[datetime] = None,
) -> bool:
    """미설정(F16 `disabled`) 안내를 지금 출력해야 하는지 판정한다.

    이 함수가 판정의 **유일한 소유자**다(`config.py`는 "미설정"이라는 사실만
    반환하고 안내 여부를 판단하지 않는다 — M-18).

    - 층 1(프로세스 내): 모듈 레벨 집합. 한 프로세스에서 몇 번 물어도
      `True`는 최초 1회뿐이다(영속 write가 실패해도 이 보장은 유지된다).
    - 층 2(호출 간, 영속): `.claude/state/kompound-snapshot.json`의
      `notice = {"session_id", "at"}`. 동일 `CLAUDE_SESSION_ID`에는 1회만.
      세션 id를 못 얻으면 `at` 기준 24시간 창으로 억제한다.
    """
    try:
        root = Path(project_root)
        state_file = state_path_for(root)
        key = str(state_file)
        if key in _PROCESS_NOTICE_EMITTED:
            return False

        sid = _effective_session_id(session_id)
        now_dt = now if now is not None else datetime.now(timezone.utc)

        runtime = _load_runtime(state_file)
        notice = runtime.get("notice") or {}

        should_emit = True
        if sid:
            if notice.get("session_id") == sid:
                should_emit = False
        else:
            at_raw = notice.get("at")
            at = parse_iso(at_raw) if at_raw else None
            if at is not None:
                if at.tzinfo is None:
                    at = at.replace(tzinfo=timezone.utc)
                age_hours = (now_dt - at).total_seconds() / 3600.0
                if age_hours < DEFAULT_NOTICE_WINDOW_HOURS:
                    should_emit = False

        if not should_emit:
            return False

        _PROCESS_NOTICE_EMITTED.add(key)
        new_runtime = dict(runtime)
        new_runtime["notice"] = {"session_id": sid, "at": now_dt.isoformat()}
        new_runtime["updated_at"] = now_iso()
        atomic_write(state_file, new_runtime)  # best-effort — 실패해도 프로세스 플래그가 방어
        return True
    except Exception:  # noqa: BLE001 - fail-safe, 안내 판정은 절대 던지지 않는다
        return False
