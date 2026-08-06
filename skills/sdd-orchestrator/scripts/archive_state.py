#!/usr/bin/env python3
"""skills/sdd-orchestrator/scripts/archive_state.py — 완료된 사이클의
`docs/sdd/ORCHESTRATOR_STATE.md`를 `docs/sdd/archive/`로 옮기는 결정적 글루.

SDD Phase 4 Step 4의 마지막 스텝에서 호출된다. 판정과 이동이 전부 결정적이므로
프롬프트가 아니라 이 스크립트가 담당한다(CLAUDE.md "결정<->판단 분리").
stdlib-only, 네트워크/LLM 무호출, 예외를 밖으로 던지지 않는다.

## 왜 정리하는가

STATE는 사이클이 머지되면 main에 영구히 남는다. 그러면:

1. `hooks/file-ownership.sh` 이전 버전이 완료된 사이클로 계속 enforce했다
   (상태 게이트 추가로 해소, 그래도 파일이 현역처럼 남는 문제는 남는다).
2. `hooks/enforcement/stop-pipeline.py`의 T1 완료 게이트가 STATE 존재를 진입
   조건으로 쓴다 -> SDD를 한 번이라도 완료한 프로젝트는 그 사이클과 무관한
   모든 이후 세션의 모든 Stop 훅에서 판정 비용을 영구 지불한다
   (콜드 프로세스 실측 +43.5ms). 아카이브하면 `is_file()` 실패로 패키지 import
   **이전에** 조기 반환하므로 그 비용이 사라진다.
3. 다음 사이클 STATE와 구분되지 않아 "현역이 무엇인지"가 파일 목록에서 안 보인다.

## 안전 인터록 (전부 통과해야 옮긴다)

- STATE의 상태가 `COMPLETED`.
- result 문서가 실제로 존재한다(사이클이 정말 끝났다는 증거).
- kompound 박제가 미완 상태가 아니다 — `PENDING`/`CATALOG_PENDING`/`FAILED`면
  **거부**한다. T1 게이트는 STATE 존재를 진입 조건으로 쓰므로, 미뤄진 박제를
  남긴 채 아카이브하면 재시도가 영구히 오지 않는다(비수렴).
- 목적지가 이미 있으면 덮어쓰지 않고 no-op로 보고한다(멱등).

T2 워크트리 삭제 게이트(`hooks/enforcement/kompound-snapshot-gate.sh`)는 STATE를
읽지 않으므로(의존 0건) 이 정리는 그 안전망에 영향을 주지 않는다.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_STATE_RELATIVE = Path("docs") / "sdd" / "ORCHESTRATOR_STATE.md"
_ARCHIVE_RELATIVE = Path("docs") / "sdd" / "archive"

# 박제가 미완이면 아카이브를 거부한다 (T1 비무장 -> 재시도 영구 소실 방지)
_BLOCKING_SNAPSHOT_STATUSES = ("PENDING", "CATALOG_PENDING", "FAILED")

# 마크다운 링크 타깃 / 백틱 경로만 교체한다. 산문 속 맨 파일명 언급
# ("ORCHESTRATOR_STATE.md 상태를 COMPLETED로 변경")은 건드리지 않는다.
_LINK_RE = re.compile(r"\]\(([^)]*ORCHESTRATOR_STATE\.md)\)")
_BACKTICK_PATH_RE = re.compile(r"`((?:[\w./-]*/)?ORCHESTRATOR_STATE\.md)`")


def _fail(reason: str, **extra: Any) -> Dict[str, Any]:
    out = {"ok": False, "archived": False, "reason": reason, "target": None,
           "rewritten": [], "external_refs": []}
    out.update(extra)
    return out


def _ensure_importable(project_root: Path) -> None:
    """`hooks.lib.kompound_snapshot`를 import할 수 있게 프로젝트 루트를 sys.path에 넣는다.

    이 스크립트는 `skills/sdd-orchestrator/scripts/`에서 실행되므로 기본 sys.path에
    프로젝트 루트가 없다. 중복 삽입은 하지 않는다.
    """
    root = str(Path(project_root).resolve())
    if root not in sys.path:
        sys.path.insert(0, root)


def _parse_status(state_text: str) -> Optional[str]:
    """STATE 텍스트에서 상태 값을 읽는다.

    파싱의 단일 진실은 `kompound_snapshot.runtime_state.parse_orchestrator_state`다
    — 같은 패턴을 두 곳에 적으면 서로 드리프트한다(2026-08-04 T-13 교훈:
    프리필터/코어 패턴 분리가 조용히 새는 구멍을 만든다). import에 실패하면
    판정 불가로 보고하고 아무것도 옮기지 않는다.
    """
    from hooks.lib.kompound_snapshot.runtime_state import parse_orchestrator_state

    return parse_orchestrator_state(state_text).get("status")


def _parse_feature(state_text: str) -> Optional[str]:
    from hooks.lib.kompound_snapshot.runtime_state import parse_orchestrator_state

    return parse_orchestrator_state(state_text).get("feature")


def _find_result_doc(project_root: Path, feature: Optional[str]) -> Optional[Path]:
    """`docs/sdd/result/{date}-{feature}.md`를 찾는다(가장 최근 것)."""
    if not feature:
        return None
    result_dir = project_root / "docs" / "sdd" / "result"
    if not result_dir.is_dir():
        return None
    matches = sorted(result_dir.glob(f"*{feature}*.md"))
    return matches[-1] if matches else None


def _snapshot_status(project_root: Path) -> Optional[str]:
    """kompound 박제 런타임 상태. 판정 불가면 None(=인터록 통과)."""
    try:
        _ensure_importable(project_root)
        from hooks.lib.kompound_snapshot import runtime_state as rs

        state = rs.load_state(rs.state_path_for(project_root))
        if not isinstance(state, dict):
            return None
        value = state.get("status")
        return value if isinstance(value, str) else None
    except Exception:  # noqa: BLE001 - fail-safe: 판정 불가는 차단 사유가 아니다
        return None


def _git(project_root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(project_root), capture_output=True, text=True
    )


def _is_tracked(project_root: Path, path: Path) -> bool:
    rel = path.relative_to(project_root).as_posix()
    return _git(project_root, "ls-files", "--error-unmatch", rel).returncode == 0


def _rewrite_links(project_root: Path, old_rel: str, new_rel: str) -> List[str]:
    """`docs/sdd/**`의 마크다운 링크 타깃/백틱 경로만 새 경로로 교체한다.

    범위를 사이클 산출물 트리로 한정한다 — 레포 전체 치환은 부작용이 크고
    되돌리기 어렵다. 트리 밖 참조는 교체하지 않고 호출자에게 보고한다.
    """
    changed: List[str] = []
    sdd_dir = project_root / "docs" / "sdd"
    if not sdd_dir.is_dir():
        return changed

    old_name = Path(old_rel).name
    for md in sorted(sdd_dir.rglob("*.md")):
        try:
            text = md.read_text(encoding="utf-8")
        except OSError:
            continue
        if old_name not in text:
            continue

        def _sub_link(m: "re.Match[str]") -> str:
            target = m.group(1)
            if Path(target).name != old_name:
                return m.group(0)
            depth = len(md.relative_to(sdd_dir).parts) - 1
            prefix = "../" * depth
            return f"]({prefix}archive/{Path(new_rel).name})"

        def _sub_backtick(m: "re.Match[str]") -> str:
            if Path(m.group(1)).name != old_name:
                return m.group(0)
            return f"`{new_rel}`"

        updated = _LINK_RE.sub(_sub_link, text)
        updated = _BACKTICK_PATH_RE.sub(_sub_backtick, updated)
        if updated != text:
            md.write_text(updated, encoding="utf-8")
            changed.append(md.relative_to(project_root).as_posix())
    return changed


# `skills/**`·`agents/**`는 "현재 사이클 STATE가 어디 있는지"라는 **일반 규약**을
# 서술하는 하네스 문서다 — 특정 사이클 인스턴스를 가리키는 게 아니므로 아카이브
# 때마다 보고하면 매번 같은 4~5건이 떠서 신호가 무력해진다.
_REF_REPORT_EXCLUDED_TOPLEVEL = ("skills", "agents")


def _external_refs(project_root: Path) -> List[str]:
    """`docs/sdd/**` 밖에서 STATE 경로를 링크로 참조하는 파일 목록(보고용).

    교체는 하지 않는다 — 사이클 인스턴스 참조인지 일반 규약 서술인지는 이
    스크립트가 판정할 수 없으므로 사람에게 넘긴다.
    """
    refs: List[str] = []
    sdd_dir = project_root / "docs" / "sdd"
    for md in sorted(project_root.rglob("*.md")):
        parts = md.parts
        if ".git" in parts or "worktrees" in parts or "node_modules" in parts:
            continue
        try:
            rel_parts = md.relative_to(project_root).parts
        except ValueError:
            continue
        if rel_parts and rel_parts[0] in _REF_REPORT_EXCLUDED_TOPLEVEL:
            continue
        try:
            if sdd_dir in md.parents:
                continue
        except Exception:  # noqa: BLE001
            pass
        try:
            text = md.read_text(encoding="utf-8")
        except OSError:
            continue
        if _LINK_RE.search(text) or _BACKTICK_PATH_RE.search(text):
            refs.append(md.relative_to(project_root).as_posix())
    return refs


def archive_state(project_root: Path, *, dry_run: bool = False) -> Dict[str, Any]:
    """완료된 사이클의 STATE를 아카이브한다. 예외를 던지지 않는다."""
    try:
        project_root = Path(project_root).resolve()
        _ensure_importable(project_root)
        state_path = project_root / _STATE_RELATIVE

        if not state_path.is_file():
            return {"ok": True, "archived": False, "reason": "state_absent",
                    "target": None, "rewritten": [], "external_refs": []}

        try:
            state_text = state_path.read_text(encoding="utf-8")
        except OSError as exc:
            return _fail(f"state_read_failed: {exc}")

        try:
            status = _parse_status(state_text)
            feature = _parse_feature(state_text)
        except Exception as exc:  # noqa: BLE001 - import/파싱 실패는 판정 불가
            return _fail(f"parse_unavailable: {exc}")

        if status != "COMPLETED":
            return {"ok": True, "archived": False,
                    "reason": f"status_not_completed: {status}",
                    "target": None, "rewritten": [], "external_refs": []}

        result_doc = _find_result_doc(project_root, feature)
        if result_doc is None:
            return _fail("result_doc_missing", feature=feature)

        snap = _snapshot_status(project_root)
        if snap in _BLOCKING_SNAPSHOT_STATUSES:
            return _fail(f"snapshot_incomplete: {snap}", feature=feature)

        # 아카이브 이름의 날짜는 result 문서명에서 가져온다 — 정리를 언제 돌렸는지가
        # 아니라 사이클이 언제 끝났는지를 이름에 남긴다.
        stem = result_doc.stem
        date_match = re.match(r"^(\d{4}-\d{2}-\d{2})-", stem)
        prefix = date_match.group(1) if date_match else "undated"
        archive_dir = project_root / _ARCHIVE_RELATIVE
        target = archive_dir / f"{prefix}-{feature}-ORCHESTRATOR_STATE.md"

        if target.exists():
            return {"ok": True, "archived": False, "reason": "already_archived",
                    "target": target.relative_to(project_root).as_posix(),
                    "rewritten": [], "external_refs": []}

        old_rel = _STATE_RELATIVE.as_posix()
        new_rel = target.relative_to(project_root).as_posix()

        if dry_run:
            return {"ok": True, "archived": False, "reason": "dry_run",
                    "target": new_rel, "feature": feature,
                    "rewritten": [], "external_refs": _external_refs(project_root)}

        archive_dir.mkdir(parents=True, exist_ok=True)

        if _is_tracked(project_root, state_path):
            moved = _git(project_root, "mv", old_rel, new_rel)
            if moved.returncode != 0:
                return _fail(f"git_mv_failed: {moved.stderr.strip()}")
        else:
            try:
                state_path.rename(target)
            except OSError as exc:
                return _fail(f"move_failed: {exc}")

        rewritten = _rewrite_links(project_root, old_rel, new_rel)
        return {"ok": True, "archived": True, "reason": "archived",
                "target": new_rel, "feature": feature,
                "rewritten": rewritten,
                "external_refs": _external_refs(project_root)}
    except Exception as exc:  # noqa: BLE001 - fail-safe
        return _fail(f"unexpected_error: {exc}")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="완료된 SDD 사이클의 ORCHESTRATOR_STATE.md 를 docs/sdd/archive/ 로 옮긴다"
    )
    ap.add_argument("--project-root", default=".", help="프로젝트 루트 (기본: cwd)")
    ap.add_argument("--dry-run", action="store_true", help="옮기지 않고 판정만 보고")
    ap.add_argument("--json", action="store_true", help="JSON 으로 출력")
    args = ap.parse_args(argv)

    result = archive_state(Path(args.project_root), dry_run=args.dry_run)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        if result["archived"]:
            print(f"[sdd-archive] STATE 아카이브 완료 -> {result['target']}")
            if result["rewritten"]:
                print(f"[sdd-archive] docs/sdd 링크 {len(result['rewritten'])}건 갱신")
            if result["external_refs"]:
                print("[sdd-archive] docs/sdd 밖 참조(수동 확인 필요): "
                      + ", ".join(result["external_refs"]))
        elif result["ok"]:
            print(f"[sdd-archive] 아카이브하지 않음 — {result['reason']}")
        else:
            print(f"[sdd-archive] 실패 — {result['reason']}", file=sys.stderr)

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
