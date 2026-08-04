"""hooks.lib.kompound_snapshot.wt_target — F2 명령 파싱 (arch §5.2.2).

Bash 명령 **문자열**에서 "삭제 대상이 될 수 있는 워크트리 경로" 목록을 뽑아낸다.
`hooks/enforcement/kompound-snapshot-gate.sh`(PreToolUse:Bash, T-13)가 이 모듈을
서브프로세스로 호출하고, 반환된 경로들을 스캔해 그 안에 미박제 SDD 문서가
있는지 판정한다(그 판정은 이 모듈의 소관이 아니다 — 여기는 "어디를 볼지"만
정한다).

## 설계 원칙 (arch §5.2.2 그대로)

1. 명령을 `;`/`&&`/`||`/`|`로 세그먼트 분해하고 세그먼트별로 독립 평가한다.
2. **패턴 A** — ``git [-C <dir>] worktree remove [--force|-f] <path>``.
3. **패턴 B** — ``rm`` + 재귀 플래그(`-r`/`-R`/`-rf`/`-fr`/`-Rf`/`--recursive`
   및 그 조합) + 경로 오퍼랜드 1개 이상.
4. 오퍼랜드가 "워크트리인가"는 **이름이 아니라 사실**로 판정한다:
   (a) 디렉토리이고 그 안의 ``.git``이 파일이며 내용이 ``gitdir:``로 시작
       → linked worktree (가장 강한 신호).
   (b) (a)가 아니지만 경로에 ``worktrees/`` 세그먼트가 있고 디렉토리로 존재
       → 워크트리로 취급(``.git``이 이미 지워진 잔해 케이스).
   둘 다 아니면 **무개입**(그 오퍼랜드는 결과에 포함하지 않는다).
5. **변수 확장·`eval`은 절대 하지 않는다** — 토큰은 리터럴 문자열 그대로
   다룬다. 이 때문에 ``rm -rf $WT`` 같은 미확장 변수, ``worktrees/*`` 같은
   글롭, ``cd <wt> && rm -rf .`` 같은 상태 의존 명령, ``find -delete``,
   ``shutil.rmtree`` 같은 비-리터럴 삭제는 **의도적으로 잡지 못한다**(사용자
   승인된 미탐 — arch §5.2.2 경계 표). 이 잔여 위험은 T1(stop-pipeline.py)이
   흡수한다.

## Fail-safe 규약

공개 함수는 예외를 던지지 않는다. 파싱 실패·파일시스템 오류는 전부 "그
세그먼트/오퍼랜드는 무개입"으로 흡수하고 빈 리스트 쪽으로 수렴한다 —
차단 여부를 판단하는 것은 이 모듈이 아니라 상위(`gate`/T2)이므로, 여기서
예외를 던져 상위 판정 전체를 무너뜨리면 안 된다.
"""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import Dict, List, Optional, Union

__all__ = [
    "find_worktree_removal_targets",
    "is_worktree_path",
]

PathLike = Union[str, Path]

# ── 재귀 플래그 판정 ────────────────────────────────────────────────

_RECURSIVE_LONG_FLAGS = {"--recursive"}


def _is_recursive_flag(token: str) -> bool:
    """`token`이 `rm`의 재귀 삭제 플래그(단독 또는 조합)인가.

    ``-r``/``-R``/``-rf``/``-fr``/``-Rf``/``-fR`` 등 짧은 옵션 조합에 `r`/`R`이
    섞여 있으면 재귀로 인정한다(arch가 명시한 6개 리터럴 전부 이 규칙 하나로
    커버된다). ``--recursive``만 긴 옵션으로 인정하고, 그 밖의 ``--foo``는
    재귀 플래그가 아니다.
    """
    if token in _RECURSIVE_LONG_FLAGS:
        return True
    if token.startswith("--"):
        return False
    if token.startswith("-") and len(token) > 1:
        return "r" in token[1:].lower()
    return False


def _is_flag_token(token: str) -> bool:
    return token.startswith("-")


# ── 명령 문자열 → 세그먼트 분해 (`;` `&&` `||` `|`, 따옴표 존중) ────────


def _split_command_segments(command: str) -> List[str]:
    """`command`를 `;`/`&&`/`||`/`|`에서 세그먼트로 쪼갠다.

    작은따옴표/큰따옴표 안의 이런 문자들은 구분자로 취급하지 않는다(리터럴
    보존). 셸 확장(`$()`/backtick/변수치환)은 절대 해석하지 않는다 — 문자
    그대로만 본다.
    """
    segments: List[str] = []
    buf: List[str] = []
    in_single = False
    in_double = False
    i = 0
    n = len(command)

    while i < n:
        ch = command[i]

        if in_single:
            buf.append(ch)
            if ch == "'":
                in_single = False
            i += 1
            continue

        if in_double:
            buf.append(ch)
            if ch == '"':
                in_double = False
            i += 1
            continue

        if ch == "'":
            in_single = True
            buf.append(ch)
            i += 1
            continue

        if ch == '"':
            in_double = True
            buf.append(ch)
            i += 1
            continue

        if command[i : i + 2] in ("&&", "||"):
            segments.append("".join(buf))
            buf = []
            i += 2
            continue

        if ch in (";", "|"):
            segments.append("".join(buf))
            buf = []
            i += 1
            continue

        buf.append(ch)
        i += 1

    segments.append("".join(buf))
    return segments


# ── 패턴 A: git [-C <dir>] worktree remove [--force|-f] <path> ────────


def _match_pattern_a(tokens: List[str]) -> Optional[Dict[str, Optional[str]]]:
    if not tokens or tokens[0] != "git":
        return None

    idx = 1
    cwd_override: Optional[str] = None

    if idx < len(tokens) and tokens[idx] == "-C":
        if idx + 1 >= len(tokens):
            return None
        cwd_override = tokens[idx + 1]
        idx += 2

    if idx + 1 >= len(tokens) or tokens[idx] != "worktree" or tokens[idx + 1] != "remove":
        return None
    idx += 2

    rest = tokens[idx:]
    operand_tokens = [t for t in rest if not _is_flag_token(t)]
    operand = operand_tokens[-1] if operand_tokens else None
    return {"operand": operand, "cwd_override": cwd_override}


# ── 패턴 B: rm + 재귀 플래그 + 경로 오퍼랜드 1개 이상 ───────────────────


def _match_pattern_b(tokens: List[str]) -> Optional[Dict[str, List[str]]]:
    if not tokens or tokens[0] != "rm":
        return None

    rest = tokens[1:]
    if not any(_is_recursive_flag(t) for t in rest):
        return None

    operands = [t for t in rest if not _is_flag_token(t)]
    return {"operands": operands}


# ── 사실 기반 워크트리 판정 (이름이 아니라 .git/gitdir: 또는 worktrees/) ──


def is_worktree_path(path: PathLike) -> bool:
    """`path`가 (a) linked worktree(``.git``이 ``gitdir:`` 파일)이거나
    (b) ``worktrees/`` 세그먼트를 가진 디렉토리(잔해 케이스)인지 사실로
    판정한다. 둘 다 아니면 False. 파일시스템 오류는 전부 False로 흡수한다
    (fail-safe — 무개입 쪽으로 수렴).
    """
    try:
        p = Path(path)
        if not p.is_dir():
            return False

        git_marker = p / ".git"
        if git_marker.is_file():
            try:
                content = git_marker.read_text(encoding="utf-8", errors="replace")
            except OSError:
                content = ""
            if content.startswith("gitdir:"):
                return True

        # (b) .git이 이미 지워진 잔해 케이스 — worktrees/ 세그먼트 존재로 판정
        if "worktrees" in p.parts:
            return True

        return False
    except OSError:
        return False
    except Exception:  # noqa: BLE001 - fail-safe, 절대 예외를 밖으로 던지지 않는다
        return False


def _resolve_operand(operand: str, base: Path) -> Path:
    p = Path(operand)
    joined = p if p.is_absolute() else (base / p)
    try:
        return joined.resolve()
    except OSError:
        return joined


# ── 공개 API ────────────────────────────────────────────────────────


def find_worktree_removal_targets(
    command: str,
    *,
    cwd: Optional[PathLike] = None,
) -> List[str]:
    """`command`(Bash 명령 문자열)에서 삭제 대상 워크트리 경로 목록을 반환한다.

    무관한 명령·미확장 변수/글롭·판정 불가 오퍼랜드는 전부 결과에서
    빠진다(빈 리스트도 정상 반환값). 순서는 첫 발견 순, 중복은 제거된다.
    예외를 던지지 않는다 — 어떤 입력에도 항상 ``list[str]``을 반환한다.

    Args:
        command: 원본 Bash 명령 문자열(그대로 파싱, 셸 확장 없음).
        cwd: 상대경로 오퍼랜드를 해석할 기준 디렉토리. 생략하면
            ``Path.cwd()``(게이트가 실행되는 실제 프로세스 cwd)를 쓴다 —
            테스트에서만 명시적으로 override한다.
    """
    try:
        if not command or not isinstance(command, str):
            return []

        base_cwd = Path(cwd) if cwd is not None else Path.cwd()

        targets: List[str] = []
        seen: set = set()

        for raw_segment in _split_command_segments(command):
            segment = raw_segment.strip()
            if not segment:
                continue

            try:
                tokens = shlex.split(segment, posix=True)
            except ValueError:
                # 따옴표 불균형 등 shlex가 파싱 못 하는 세그먼트 — 무개입.
                continue
            if not tokens:
                continue

            operands: List[str] = []
            operand_base = base_cwd

            match_a = _match_pattern_a(tokens)
            if match_a is not None:
                if match_a["operand"]:
                    operands = [match_a["operand"]]
                if match_a["cwd_override"]:
                    c_path = Path(match_a["cwd_override"])
                    operand_base = c_path if c_path.is_absolute() else (base_cwd / c_path)
            else:
                match_b = _match_pattern_b(tokens)
                if match_b is not None:
                    operands = match_b["operands"]

            for operand in operands:
                resolved = _resolve_operand(operand, operand_base)
                if not is_worktree_path(resolved):
                    continue
                key = str(resolved)
                if key not in seen:
                    seen.add(key)
                    targets.append(key)

        return targets
    except Exception:  # noqa: BLE001 - fail-safe, 절대 예외를 밖으로 던지지 않는다
        return []
