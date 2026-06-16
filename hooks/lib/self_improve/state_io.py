#!/usr/bin/env python3
"""
hooks/lib/self_improve/state_io.py — 공유 결정적 상태 I/O 유닛

self-improving-harness의 모든 JSON 상태(`pr-converge-state.json`,
`retro-state.json`)는 이 유닛을 통해서만 읽고 쓴다 (arch §6 IO 경계 규칙:
"All JSON state through the shared state-I/O unit — no ad-hoc json.dump").

`stop-pipeline.py`의 load_state / atomic_write / now_iso / parse_iso 패턴을
그대로 차용하고, schema_version guard와 스키마별 초기값 생성 함수를 추가했다.

하드 불변식 (arch §2):
- stdlib only — 외부 import 금지 (requests/yaml/pydantic 등)
- 네트워크/LLM 호출 절대 금지 (순수 결정적 로직)
- 모든 함수는 fail-safe — 예외를 raise 하지 않고 None 또는 구조화된 오류 dict 반환

입력/출력은 전부 JSON 직렬화 가능한 dict와 ISO8601 문자열뿐이다.
"""

import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Union

# ─── 상수 ──────────────────────────────────────────────────────

# spec "상태 파일 계약" 섹션 — 두 상태 파일 모두 schema_version=1
SCHEMA_VERSION = 1

PathLike = Union[str, Path]


# ─── 상태 파일 I/O (stop-pipeline.py 패턴 차용) ────────────────

def load_state(path: PathLike) -> Optional[dict]:
    """JSON 상태 파일을 읽어 dict 반환.

    파일이 없거나 파싱 오류 시 None 반환 (stop-pipeline.py 패턴 동일).
    절대 raise 하지 않는다 — fail-safe.
    """
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        # JSON 최상위가 dict가 아니면 (list/scalar) 상태로 취급하지 않음
        if not isinstance(data, dict):
            return None
        return data
    except Exception:
        return None


def atomic_write(path: PathLike, data: dict) -> dict:
    """torn JSON을 방지하는 원자적 쓰기.

    같은 디렉토리에 임시 파일을 만들어 직렬화한 뒤 `shutil.move`로 교체한다
    (rename은 같은 파일시스템에서 원자적). 부모 디렉토리가 없으면 생성한다.

    반환: 구조화된 결과 dict.
      성공: {"ok": True, "path": "<str>"}
      실패: {"ok": False, "error": "<message>"}  (raise 하지 않음 — fail-safe)
    """
    p = Path(path)
    tmp_path = None
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", dir=p.parent, delete=False, suffix=".tmp", encoding="utf-8"
        ) as tmp:
            # 직렬화가 중간에 실패해도 정리할 수 있도록 이름을 먼저 기록한다.
            tmp_path = tmp.name
            json.dump(data, tmp, indent=2, ensure_ascii=False)
            tmp.flush()
        shutil.move(tmp_path, str(p))
        return {"ok": True, "path": str(p)}
    except Exception as e:
        # 임시 파일이 남았으면 정리 (상태 손상 방지)
        if tmp_path is not None:
            try:
                Path(tmp_path).unlink()
            except Exception:
                pass
        return {"ok": False, "error": str(e)}


# ─── schema_version guard ──────────────────────────────────────

def check_schema_version(
    state: Optional[dict], expected: int = SCHEMA_VERSION
) -> dict:
    """로드된 상태의 schema_version을 검증한다.

    예외를 발생시키지 않고 구조화된 결과 dict를 반환한다 (fail-safe).

    반환:
      {"ok": True, "state": <dict>}                          — 검증 통과
      {"ok": False, "error": "<code>", "detail": "<msg>", ...} — 검증 실패
        error 코드: "missing_state" | "missing_field" | "version_mismatch"
    """
    if state is None:
        return {
            "ok": False,
            "error": "missing_state",
            "detail": "상태가 None입니다 (파일 없음 또는 파싱 오류).",
        }
    if "schema_version" not in state:
        return {
            "ok": False,
            "error": "missing_field",
            "detail": "상태에 schema_version 필드가 없습니다.",
            "expected": expected,
        }
    found = state.get("schema_version")
    if found != expected:
        return {
            "ok": False,
            "error": "version_mismatch",
            "detail": f"schema_version 불일치: 기대 {expected}, 실제 {found}.",
            "expected": expected,
            "found": found,
        }
    return {"ok": True, "state": state}


def load_state_checked(
    path: PathLike, expected: int = SCHEMA_VERSION
) -> dict:
    """load_state + check_schema_version 결합 헬퍼.

    파일 로드와 스키마 검증을 한 번에 수행하고, 어느 단계에서 실패하든
    구조화된 오류 dict를 반환한다 (raise 금지).
    """
    return check_schema_version(load_state(path), expected)


# ─── 시간 유틸 (stop-pipeline.py 패턴 차용) ────────────────────

def now_iso() -> str:
    """현재 UTC 시각을 ISO8601 문자열로 반환."""
    return datetime.now(timezone.utc).isoformat()


def parse_iso(s: Any) -> Optional[datetime]:
    """ISO8601 문자열을 datetime으로 파싱. 실패 시 None 반환 (fail-safe).

    'Z' 접미사(UTC)를 fromisoformat이 처리할 수 있는 '+00:00'으로 정규화한다.
    """
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


# ─── 스키마별 초기값 생성 함수 (spec "상태 파일 계약") ─────────

def initial_pr_converge_state(
    pr: str = "", branch: str = ""
) -> dict:
    """`.harness/pr-converge-state.json` 스키마 초기값 생성.

    spec "상태 파일 계약 → .harness/pr-converge-state.json" 계약과 일치한다.
    last_tick_at은 생성 시각으로 초기화한다.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "pr": pr,
        "branch": branch,
        "processed_comment_ids": [],
        "fix_attempts": {},
        "iterations": 0,
        "status": "WORKING",
        "last_tick_at": now_iso(),
        "escalations": [],
        "learning_entries_appended": [],
    }


def initial_retro_state(last_processed_marker: str = "") -> dict:
    """`.harness/retro-state.json` 스키마 초기값 생성.

    spec "상태 파일 계약 → .harness/retro-state.json" 계약과 일치한다.
    last_processed_marker가 비어 있으면 self-improve는 LEARNING.md 전체를
    신규로 취급한다 (spec F8).
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "last_processed_marker": last_processed_marker,
        "last_retro_at": now_iso(),
        "cumulative": {
            "applied_project": 0,
            "proposed_harness": 0,
            "dropped": 0,
        },
    }


__all__ = [
    "SCHEMA_VERSION",
    "load_state",
    "atomic_write",
    "check_schema_version",
    "load_state_checked",
    "now_iso",
    "parse_iso",
    "initial_pr_converge_state",
    "initial_retro_state",
]
