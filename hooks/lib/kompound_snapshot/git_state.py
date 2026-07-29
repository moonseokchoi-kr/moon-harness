"""hooks/lib/kompound_snapshot/git_state.py — F9 dirty/divergence 판정 · 커밋 · 배타 락.

설계 SSOT: docs/sdd/design/arch/2026-07-29-kompound-snapshot-hook.md
(이하 "arch") §6.4(F9 네트워크 없이 판정) · §3.2(모듈 계약 — ``git_state`` 행)
· §6.3.0(2단 커밋 경계) · §5.3(동시성/배타 락).
spec: docs/sdd/spec/2026-07-29-kompound-snapshot-hook.md F9.

## Fail-safe 규약

이 모듈의 모든 공개 함수는 예외를 밖으로 던지지 않는다(F13). git 바이너리
부재·비-git 디렉토리·존재하지 않는 경로·권한 오류를 포함한 모든 실패는
구조화된 결과 dict(``{"ok": bool, ...}``)로 보고한다.

## 네트워크 무호출 (F13 ↔ F9, arch §6.4)

이 모듈은 ``fetch``/``pull``/``push``를 **절대 호출하지 않는다**. divergence는
"마지막으로 알려진 remote-tracking ref" 기준으로 오프라인 계산한다
(``git rev-list --left-right --count @{upstream}...HEAD``). "remote가 실제로
앞서 있는지"는 사용자의 마지막 fetch 시점 기준이라는 한계가 있다(arch §6.4).

## ``ok`` 필드의 의미 (계약 — T-10 `apply.py`가 이 규약에 의존)

이 모듈 전반에서 ``ok``는 **판정/커밋/락 시도 자체가 기술적으로 정상
수행됐는지**를 뜻하며, "선행 조건이 통과했는지"를 뜻하지 않는다.

- ``check_dirty`` / ``check_divergence`` / ``check_preconditions``:
  ``ok=True``면 ``dirty``/``diverged``/``ahead``/``behind`` 값을 신뢰할 수
  있다(git 호출이 정상 완료됐다는 뜻이며, ``dirty=True``·``diverged=True``
  여도 ``ok`` 자체는 ``True``다). ``ok=False``면 git 바이너리 부재·비-git
  디렉토리 등으로 판정 자체가 실패한 것이며, 이때 bool 필드들은 신뢰할 수
  없는 기본값(``False``/``0``)이다.
  **호출자(T-10 `apply.py`)는 ``ok``/``dirty``/``diverged``를 직접 조립하지
  말고, ``check_preconditions``가 반환하는 ``precondition_failed`` 필드
  (정확히 ``not ok or dirty or diverged``)를 그대로 써서 "진행해도
  되는가"를 판단해야 한다** — 판단식을 호출자가 손으로 재구현하면 오조립
  위험이 생긴다(review P1 #1, `.harness/LEARNING.md` 2026-07-30).
  ``precondition_failed is True``이면 (i) raw 복사로 진행하지 않는다.
  (``check_dirty``/``check_divergence`` 각각은 이 결합 필드를 갖지 않는다
  — 결합 판정은 ``check_preconditions``의 책임이다.)
- ``commit_raw`` / ``commit_catalog``: ``ok=True``면 커밋 시도 자체(git
  add/commit/rev-parse 호출)가 정상 수행됐다는 뜻이다. 커밋할 변경이
  없었던 경우도 ``ok=True``, ``committed=False``, ``reason="no_changes"``로
  정상 보고한다(에러가 아니다). ``ok=False``면 git 호출 자체가 실패한
  것이다.
- ``acquire_lock`` / ``release_lock``: ``ok=True``면 파일시스템 조작
  자체가 정상 수행됐다는 뜻이다. 락이 이미 잡혀 있어(신선한 락) 획득하지
  못한 경우도 ``ok=True``, ``acquired=False``, ``reason="busy"``로
  정상 보고한다(에러가 아니다).
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

PathLike = Union[str, Path]

# arch §5.3 확정값: stale 락(mtime > 10분)은 무시하고 인수한다.
LOCK_STALE_SECONDS = 10 * 60

_LOCK_FILE_NAME = "kompound-snapshot.lock"

# T-2 확정 사항 #6 (ORCHESTRATOR_STATE.md "T-2 확정 사항"): git identity는
# 로컬 `-c` 플래그로만 주입한다 — 전역/리포 config는 절대 건드리지 않는다.
_COMMIT_IDENTITY_ARGS: List[str] = [
    "-c",
    "user.email=kompound-snapshot@harness.invalid",
    "-c",
    "user.name=kompound-snapshot-hook",
    "-c",
    "commit.gpgsign=false",
]

_GIT_TIMEOUT_SECONDS = 30


# ─── 내부: git 서브프로세스 래퍼 (예외를 밖으로 던지지 않는다) ────────────


def _run_git(args: Sequence[str], cwd: PathLike) -> Dict[str, Any]:
    """``["git", *args]``를 ``cwd``에서 실행한다. 절대 raise하지 않는다.

    반환:
      {"ok": True, "returncode": int, "stdout": str, "stderr": str}
        — 서브프로세스 실행 자체는 성공(“git”이 기동되고 종료 코드를
        받았다). git 자신의 종료 코드가 0이 아닐 수 있다(예: 비-git
        디렉토리, upstream 미설정 등) — 호출부가 returncode/stderr로 분기.
      {"ok": False, "reason": "<message>"}
        — git 바이너리 부재, ``cwd`` 부재, 권한 오류 등으로 서브프로세스
        자체를 띄우지 못했다.

    fetch/pull/push는 이 함수를 포함해 이 모듈 어디에서도 호출하지 않는다
    (F13 네트워크 무호출).
    """
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
        return {
            "ok": True,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    except Exception as exc:  # noqa: BLE001 - fail-safe (F13): 절대 raise하지 않는다
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}


# ─── F9: dirty 판정 ────────────────────────────────────────────────────


def check_dirty(kompound_repo: PathLike) -> Dict[str, Any]:
    """``git status --porcelain``으로 kompound 워킹트리의 dirty 여부를 판정한다.

    반환:
      {"ok": True, "dirty": bool, "dirty_files": [str, ...], "reason": None}
      {"ok": False, "dirty": False, "dirty_files": [], "reason": "<message>"}
        — git 바이너리 부재/비-git 디렉토리/존재하지 않는 경로 등.
    """
    result = _run_git(["status", "--porcelain"], cwd=kompound_repo)
    if not result["ok"]:
        return {
            "ok": False,
            "dirty": False,
            "dirty_files": [],
            "reason": result["reason"],
        }
    if result["returncode"] != 0:
        reason = result["stderr"].strip() or (
            f"git status exited {result['returncode']}"
        )
        return {"ok": False, "dirty": False, "dirty_files": [], "reason": reason}

    dirty_files = [
        line[3:].strip() if len(line) > 3 else line.strip()
        for line in result["stdout"].splitlines()
        if line.strip()
    ]
    return {
        "ok": True,
        "dirty": bool(dirty_files),
        "dirty_files": dirty_files,
        "reason": None,
    }


# ─── F9: divergence 판정 (오프라인, fetch 없음) ────────────────────────


def check_divergence(kompound_repo: PathLike) -> Dict[str, Any]:
    """``@{upstream}`` 기준 ahead/behind를 오프라인으로 계산한다(arch §6.4).

    ``fetch``/``pull``/``push``는 절대 호출하지 않는다 — "마지막으로 알려진
    remote-tracking ref" 기준의 ``git rev-list --left-right --count`` 만
    사용한다.

    반환:
      {"ok": True, "diverged": bool, "ahead": int, "behind": int,
       "upstream": bool, "reason": <"no_upstream" | None>}
        - upstream 미설정: 정상 처리(예외 아님) — ``upstream=False``,
          ``diverged=False``, ``ahead=0``, ``behind=0``,
          ``reason="no_upstream"``.
        - upstream 설정됨: ``diverged`` = ``behind > 0``.
          ``ahead > 0, behind == 0``은 정상(미push 로컬 커밋)이며
          ``diverged=False``다.
      {"ok": False, "diverged": False, "ahead": 0, "behind": 0,
       "upstream": None, "reason": "<message>"}
        — git 바이너리 부재/비-git 디렉토리/기타 git 오류.
    """
    upstream_result = _run_git(
        ["rev-parse", "--abbrev-ref", "@{upstream}"], cwd=kompound_repo
    )
    if not upstream_result["ok"]:
        return {
            "ok": False,
            "diverged": False,
            "ahead": 0,
            "behind": 0,
            "upstream": None,
            "reason": upstream_result["reason"],
        }
    if upstream_result["returncode"] != 0:
        stderr = upstream_result["stderr"]
        if "no upstream configured" in stderr:
            # 로컬 전용 저장소 — 정상 처리(테스트 fixture 포함), 예외 아님.
            return {
                "ok": True,
                "diverged": False,
                "ahead": 0,
                "behind": 0,
                "upstream": False,
                "reason": "no_upstream",
            }
        return {
            "ok": False,
            "diverged": False,
            "ahead": 0,
            "behind": 0,
            "upstream": None,
            "reason": stderr.strip() or "git rev-parse failed to resolve @{upstream}",
        }

    count_result = _run_git(
        ["rev-list", "--left-right", "--count", "@{upstream}...HEAD"],
        cwd=kompound_repo,
    )
    if not count_result["ok"]:
        return {
            "ok": False,
            "diverged": False,
            "ahead": 0,
            "behind": 0,
            "upstream": True,
            "reason": count_result["reason"],
        }
    if count_result["returncode"] != 0:
        reason = count_result["stderr"].strip() or (
            f"git rev-list exited {count_result['returncode']}"
        )
        return {
            "ok": False,
            "diverged": False,
            "ahead": 0,
            "behind": 0,
            "upstream": True,
            "reason": reason,
        }

    parts = count_result["stdout"].split()
    if len(parts) != 2:
        return {
            "ok": False,
            "diverged": False,
            "ahead": 0,
            "behind": 0,
            "upstream": True,
            "reason": f"unexpected rev-list output: {count_result['stdout']!r}",
        }

    try:
        behind, ahead = int(parts[0]), int(parts[1])
    except ValueError:
        return {
            "ok": False,
            "diverged": False,
            "ahead": 0,
            "behind": 0,
            "upstream": True,
            "reason": f"non-integer rev-list output: {count_result['stdout']!r}",
        }

    return {
        "ok": True,
        "diverged": behind > 0,
        "ahead": ahead,
        "behind": behind,
        "upstream": True,
        "reason": None,
    }


def check_preconditions(kompound_repo: PathLike) -> Dict[str, Any]:
    """F9 선행 조건(dirty + divergence)을 한 번에 판정한다(T-10 `apply.py` 진입점).

    ``check_dirty`` + ``check_divergence``를 합쳐 apply.py가 F9
    ``precondition_failed`` 여부를 한 번에 판단할 수 있게 한다.

    반환 (최소 필드 — task 문서 계약):
      {"ok": bool, "dirty": bool, "dirty_files": [str, ...],
       "diverged": bool, "ahead": int, "behind": int,
       "upstream": <bool|None>, "reason": <str|None>,
       "precondition_failed": bool}

    ``ok`` 의미는 모듈 docstring 참조 — "판정 자체가 기술적으로 성공했는가"
    이지 "선행 조건을 통과했는가"가 아니다. ``ok``/``dirty``/``diverged``를
    호출자가 직접 조립(``not ok or dirty or diverged``)하게 두면 오조립
    위험이 있으므로(review P1 #1, `.harness/LEARNING.md` 2026-07-30),
    **이 결합 판정을 ``precondition_failed`` 필드로 미리 계산해 제공한다.**
    ``precondition_failed is True``이면 (i) raw 복사 단계로 진행하지 않고
    F9 ``precondition_failed``로 취급해야 한다. 계산식은 정확히
    ``not ok or dirty or diverged``이며, ``ok=False`` 조기 반환 경로
    (dirty_result 실패 · divergence_result 실패) 모두 ``True``로 고정된다.
    ``reason``은 진단 문자열이다 — ``ok=False``면 오류 메시지, ``ok=True``
    이고 ``dirty``/``diverged`` 중 하나라도 참이면 ``"dirty"``/``"diverged"``
    (둘 다면 ``"dirty"`` 우선), 아니면 ``None``.
    """
    dirty_result = check_dirty(kompound_repo)
    if not dirty_result["ok"]:
        return {
            "ok": False,
            "dirty": False,
            "dirty_files": [],
            "diverged": False,
            "ahead": 0,
            "behind": 0,
            "upstream": None,
            "reason": dirty_result["reason"],
            "precondition_failed": True,
        }

    divergence_result = check_divergence(kompound_repo)
    if not divergence_result["ok"]:
        return {
            "ok": False,
            "dirty": dirty_result["dirty"],
            "dirty_files": dirty_result["dirty_files"],
            "diverged": False,
            "ahead": 0,
            "behind": 0,
            "upstream": None,
            "reason": divergence_result["reason"],
            "precondition_failed": True,
        }

    reason: Optional[str]
    if dirty_result["dirty"]:
        reason = "dirty"
    elif divergence_result["diverged"]:
        reason = "diverged"
    else:
        reason = None

    return {
        "ok": True,
        "dirty": dirty_result["dirty"],
        "dirty_files": dirty_result["dirty_files"],
        "diverged": divergence_result["diverged"],
        "ahead": divergence_result["ahead"],
        "behind": divergence_result["behind"],
        "upstream": divergence_result["upstream"],
        "reason": reason,
        "precondition_failed": dirty_result["dirty"] or divergence_result["diverged"],
    }


# ─── F6/§6.3.0: raw 전용 / 카탈로그 전용 커밋 (독립 2단 커밋 경계) ──────


def _unstage_after_commit_failure(
    kompound_repo: PathLike, paths: Sequence[str], commit_reason: str
) -> Dict[str, Any]:
    """커밋 실패 후 인덱스를 add 이전 상태로 되돌린다(자기 오염 방지).

    arch §6.3.0의 2단 커밋 분리는 "실패해도 워킹트리는 항상 clean"을
    전제한다 — commit이 실패했는데 스테이징만 남으면 다음 실행의
    ``check_dirty``가 그 스테이징을 dirty로 잡아 F9가 영구 차단된다
    (review P1 #2, `.harness/LEARNING.md` 2026-07-30). ``git reset --
    <paths>``로 add를 되돌리며, reset 자체가 실패해도 예외를 던지지 않고
    원래 실패 사유에 unstage 실패 사유를 병기해 보고한다(fail-safe).
    """
    reset_result = _run_git(["reset", "--", *paths], cwd=kompound_repo)
    if not reset_result["ok"]:
        return {
            "ok": False,
            "committed": False,
            "commit": None,
            "reason": f"{commit_reason} (unstage 실패: {reset_result['reason']})",
        }
    if reset_result["returncode"] != 0:
        unstage_reason = reset_result["stderr"].strip() or (
            f"git reset exited {reset_result['returncode']}"
        )
        return {
            "ok": False,
            "committed": False,
            "commit": None,
            "reason": f"{commit_reason} (unstage 실패: {unstage_reason})",
        }
    return {
        "ok": False,
        "committed": False,
        "commit": None,
        "reason": commit_reason,
    }


def _commit_paths(
    kompound_repo: PathLike, paths: Sequence[str], message: str
) -> Dict[str, Any]:
    """``paths``만 스테이징해 로컬 커밋한다(전역/리포 identity 무변경).

    반환: {"ok": bool, "committed": bool, "commit": <sha|None>,
           "reason": <str|None>}
    커밋할 변경이 없으면 에러가 아니라 ``committed=False,
    reason="no_changes"``로 정상 보고한다. **commit 자체가 실패하면 add로
    스테이징된 변경을 되돌려 워킹트리를 add 이전 상태로 복원한다**
    (`_unstage_after_commit_failure` — F9 자기 오염 방지).
    """
    add_result = _run_git(["add", "--", *paths], cwd=kompound_repo)
    if not add_result["ok"]:
        return {
            "ok": False,
            "committed": False,
            "commit": None,
            "reason": add_result["reason"],
        }
    if add_result["returncode"] != 0:
        reason = add_result["stderr"].strip() or (
            f"git add exited {add_result['returncode']}"
        )
        return {"ok": False, "committed": False, "commit": None, "reason": reason}

    # 스테이징된 변경이 없으면(멱등 무동작) 에러가 아니라 정상 무동작이다.
    diff_result = _run_git(["diff", "--cached", "--quiet"], cwd=kompound_repo)
    if not diff_result["ok"]:
        return {
            "ok": False,
            "committed": False,
            "commit": None,
            "reason": diff_result["reason"],
        }
    if diff_result["returncode"] == 0:
        return {
            "ok": True,
            "committed": False,
            "commit": None,
            "reason": "no_changes",
        }

    commit_result = _run_git(
        [*_COMMIT_IDENTITY_ARGS, "commit", "-q", "-m", message], cwd=kompound_repo
    )
    if not commit_result["ok"]:
        return _unstage_after_commit_failure(
            kompound_repo, paths, commit_result["reason"]
        )
    if commit_result["returncode"] != 0:
        reason = (
            commit_result["stderr"].strip()
            or commit_result["stdout"].strip()
            or f"git commit exited {commit_result['returncode']}"
        )
        return _unstage_after_commit_failure(kompound_repo, paths, reason)

    sha_result = _run_git(["rev-parse", "HEAD"], cwd=kompound_repo)
    if not sha_result["ok"] or sha_result["returncode"] != 0:
        # 커밋 자체는 성공했으나 sha 조회만 실패한 드문 경우 — 커밋 성공은
        # 그대로 보고하되 sha는 알 수 없다고 밝힌다(F13 fail-safe).
        return {
            "ok": True,
            "committed": True,
            "commit": None,
            "reason": "commit_succeeded_sha_unknown",
        }

    return {
        "ok": True,
        "committed": True,
        "commit": sha_result["stdout"].strip(),
        "reason": None,
    }


def commit_raw(
    kompound_repo: PathLike,
    new_count: int,
    updated_count: int,
    *,
    paths: Sequence[str] = ("raw",),
) -> Dict[str, Any]:
    """(i) raw 전용 커밋 — ``snapshot(raw): N new, M updated`` (arch §6.3.0).

    ``paths``(기본 ``("raw",)``)만 스테이징한다 — 카탈로그(wiki/*) 변경은
    이 커밋에 포함하지 않는다(F9 자기 오염 회피, §6.3.0 커밋 경계).

    반환: {"ok": bool, "committed": bool, "commit": <sha|None>,
           "reason": <str|None>}
    """
    message = f"snapshot(raw): {new_count} new, {updated_count} updated"
    return _commit_paths(kompound_repo, paths, message)


def commit_catalog(
    kompound_repo: PathLike,
    detail: str,
    *,
    paths: Sequence[str] = ("wiki",),
) -> Dict[str, Any]:
    """(ii) 카탈로그 전용 커밋 — ``snapshot(catalog): <detail>`` (arch §6.3.0).

    ``paths``(기본 ``("wiki",)``)만 스테이징한다 — raw 커밋과 독립적으로
    수행되며, (i)이 이미 커밋된 뒤에만 호출돼야 한다(§6.3.0 2단 분리).

    반환: {"ok": bool, "committed": bool, "commit": <sha|None>,
           "reason": <str|None>}
    """
    message = f"snapshot(catalog): {detail}"
    return _commit_paths(kompound_repo, paths, message)


# ─── §5.3: 배타 락 (동시성 — PreToolUse 게이트 vs Stop 훅) ─────────────


def _lock_path(kompound_repo: PathLike) -> Path:
    return Path(kompound_repo) / ".git" / _LOCK_FILE_NAME


def acquire_lock(
    kompound_repo: PathLike, *, stale_seconds: int = LOCK_STALE_SECONDS
) -> Dict[str, Any]:
    """``<kompound>/.git/kompound-snapshot.lock``을 배타적으로 획득한다.

    ``os.open(O_CREAT | O_EXCL)``로 획득을 시도한다. 이미 존재하는 락이
    ``stale_seconds``(기본 10분)보다 오래됐으면 다른 프로세스의 비정상
    종료로 간주하고 무시·인수한다(제거 후 재획득).

    반환:
      {"ok": True, "acquired": True, "reason": None}
      {"ok": True, "acquired": True, "reason": "stale_lock_reclaimed"}
      {"ok": True, "acquired": False, "reason": "busy"}
        — 다른 프로세스가 신선한 락을 보유 중(에러 아님).
      {"ok": False, "acquired": False, "reason": "<message>"}
        — 파일시스템 오류(권한 등).
    """
    lock_path = _lock_path(kompound_repo)
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return {
            "ok": False,
            "acquired": False,
            "reason": f"{type(exc).__name__}: {exc}",
        }

    def _try_open() -> Optional[Dict[str, Any]]:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return None
        except FileExistsError:
            return {"exists": True}
        except OSError as exc:
            return {"error": f"{type(exc).__name__}: {exc}"}

    first_attempt = _try_open()
    if first_attempt is None:
        return {"ok": True, "acquired": True, "reason": None}
    if "error" in first_attempt:
        return {"ok": False, "acquired": False, "reason": first_attempt["error"]}

    # 락 파일이 이미 존재 — 신선한지(busy) stale인지 판정.
    try:
        age_seconds = time.time() - lock_path.stat().st_mtime
    except OSError as exc:
        return {
            "ok": False,
            "acquired": False,
            "reason": f"{type(exc).__name__}: {exc}",
        }

    if age_seconds <= stale_seconds:
        return {"ok": True, "acquired": False, "reason": "busy"}

    # stale 락 — 무시하고 인수한다: 제거 후 재획득 1회 시도.
    try:
        lock_path.unlink()
    except OSError as exc:
        return {
            "ok": False,
            "acquired": False,
            "reason": f"{type(exc).__name__}: {exc}",
        }

    second_attempt = _try_open()
    if second_attempt is None:
        return {"ok": True, "acquired": True, "reason": "stale_lock_reclaimed"}
    if "error" in second_attempt:
        return {"ok": False, "acquired": False, "reason": second_attempt["error"]}
    # 제거 직후 다른 프로세스가 재획득한 경쟁 상태(드묾) — busy로 보고.
    return {"ok": True, "acquired": False, "reason": "busy"}


def release_lock(kompound_repo: PathLike) -> Dict[str, Any]:
    """``acquire_lock``으로 획득한 락 파일을 해제(삭제)한다.

    반환:
      {"ok": True, "released": True}
      {"ok": True, "released": False, "reason": "not_locked"}
        — 락 파일이 애초에 없었다(에러 아님).
      {"ok": False, "released": False, "reason": "<message>"}
    """
    lock_path = _lock_path(kompound_repo)
    try:
        lock_path.unlink()
        return {"ok": True, "released": True}
    except FileNotFoundError:
        return {"ok": True, "released": False, "reason": "not_locked"}
    except OSError as exc:
        return {
            "ok": False,
            "released": False,
            "reason": f"{type(exc).__name__}: {exc}",
        }
