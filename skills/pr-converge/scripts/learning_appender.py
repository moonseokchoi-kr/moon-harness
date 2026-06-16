"""learning_appender.py — LEARNING.md에 provenance-tagged 엔트리 append.

F15 결정적 직렬화 단계:
  pattern_detector.py가 생성한 페이로드 dict를 받아
  LEARNING.md 파일에 태그 포맷으로 append한다.

태그 포맷 (spec 해결 1 / arch §6 / hooks/lib/self_improve/parser.py 계약):
  ## {marker}
  <!-- tags: domain={domain}, stage={stage}, provenance_repo={provenance_repo} -->

  {body}

파일 읽기/쓰기만 수행. gh/LLM/네트워크 호출 절대 금지.
Fail-safe: 예외를 raise하지 않고 구조화된 결과 dict 반환.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

PathLike = Union[str, Path]

# LEARNING.md 파일이 없을 때 생성할 기본 헤더
_DEFAULT_HEADER = "# LEARNING\n\nself-improving-harness가 사이클에서 수집한 교훈 모음.\n"


def append_learning_entry(
    learning_path: PathLike,
    entry_dict: Dict[str, Any],
) -> Dict[str, Any]:
    """LEARNING.md에 provenance-tagged 엔트리를 append한다.

    Args:
        learning_path: LEARNING.md 파일 절대/상대 경로.
                       파일이 없으면 생성한다.
        entry_dict: pattern_detector.build_learning_payload가 반환한 페이로드 dict.
                    필수 키: "marker" (str), "tags" (dict), "body" (str).
                    선택 키: "signal_key", "attempt_count" 등.

    Returns:
        성공: {"ok": True, "path": str, "marker": str}
        실패: {"ok": False, "error": str, "detail": str}

    Fail-safe: 어떤 IO 오류도 raise하지 않고 실패 dict 반환.
    동일 marker가 이미 파일에 존재하면 중복 append 없이 {"ok": True, "skipped": True} 반환.
    """
    if not isinstance(entry_dict, dict):
        return {
            "ok": False,
            "error": "invalid_input",
            "detail": "entry_dict가 dict가 아닙니다.",
        }

    marker = entry_dict.get("marker")
    tags = entry_dict.get("tags", {})
    body = entry_dict.get("body", "")

    if not isinstance(marker, str) or not marker.strip():
        return {
            "ok": False,
            "error": "missing_marker",
            "detail": "entry_dict에 유효한 'marker' 필드가 없습니다.",
        }

    if not isinstance(tags, dict):
        tags = {}

    if not isinstance(body, str):
        body = str(body) if body is not None else ""

    try:
        path = Path(learning_path)
    except Exception as e:
        return {
            "ok": False,
            "error": "invalid_path",
            "detail": str(e),
        }

    # 파일 읽기 (없으면 기본 헤더로 초기화)
    existing_text = _read_file(path)
    if existing_text is None:
        existing_text = _DEFAULT_HEADER

    # 중복 체크: 동일 marker가 이미 있으면 skip
    header_line = f"## {marker}"
    if header_line in existing_text:
        return {
            "ok": True,
            "path": str(path),
            "marker": marker,
            "skipped": True,
        }

    # 엔트리 직렬화
    entry_text = _serialize_entry(marker, tags, body)

    # append (파일 끝에 빈 줄 보장 후 엔트리 추가)
    new_text = _join_content(existing_text, entry_text)

    result = _write_file(path, new_text)
    if not result["ok"]:
        return result

    return {
        "ok": True,
        "path": str(path),
        "marker": marker,
        "skipped": False,
    }


def append_learning_entries(
    learning_path: PathLike,
    entry_dicts: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """여러 엔트리를 순서대로 LEARNING.md에 append한다.

    Args:
        learning_path: LEARNING.md 파일 경로.
        entry_dicts: 페이로드 dict 목록.

    Returns:
        {
            "ok": bool,                   # 전체 성공 여부
            "appended": [marker, ...],    # 성공적으로 append된 marker 목록
            "skipped": [marker, ...],     # 중복으로 skip된 marker 목록
            "failed": [(marker, error), ...]  # 실패한 (marker, error) 목록
        }
    """
    if not isinstance(entry_dicts, list):
        return {
            "ok": False,
            "appended": [],
            "skipped": [],
            "failed": [("(all)", "entry_dicts가 list가 아닙니다.")],
        }

    appended: List[str] = []
    skipped: List[str] = []
    failed: List[tuple] = []

    for entry in entry_dicts:
        marker = entry.get("marker", "(unknown)") if isinstance(entry, dict) else "(unknown)"
        result = append_learning_entry(learning_path, entry)
        if not result.get("ok"):
            failed.append((marker, result.get("detail", result.get("error", "unknown error"))))
        elif result.get("skipped"):
            skipped.append(marker)
        else:
            appended.append(marker)

    overall_ok = len(failed) == 0
    return {
        "ok": overall_ok,
        "appended": appended,
        "skipped": skipped,
        "failed": failed,
    }


# ─── 내부 헬퍼 ────────────────────────────────────────────────────

def _serialize_entry(marker: str, tags: Dict[str, str], body: str) -> str:
    """엔트리를 LEARNING.md 마크다운 포맷 문자열로 직렬화한다.

    포맷:
      ## {marker}
      <!-- tags: key=value, ... -->

      {body}
    """
    # 태그 직렬화 (key 순서: domain, stage, provenance_repo, 그 외 알파벳순)
    priority_keys = ["domain", "stage", "provenance_repo"]
    tag_parts: List[str] = []
    for key in priority_keys:
        if key in tags:
            val = str(tags[key]).strip()
            tag_parts.append(f"{key}={val}")
    for key in sorted(tags.keys()):
        if key not in priority_keys:
            val = str(tags[key]).strip()
            tag_parts.append(f"{key}={val}")

    lines = [f"## {marker}"]
    if tag_parts:
        tags_line = "<!-- tags: " + ", ".join(tag_parts) + " -->"
        lines.append(tags_line)
    lines.append("")
    if body:
        lines.append(body.strip())

    return "\n".join(lines)


def _join_content(existing: str, new_entry: str) -> str:
    """기존 내용 끝에 빈 줄 구분 후 새 엔트리를 붙인다."""
    if not existing.endswith("\n"):
        existing = existing + "\n"
    if not existing.endswith("\n\n"):
        existing = existing + "\n"
    return existing + new_entry + "\n"


def _read_file(path: Path) -> Optional[str]:
    """파일을 읽어 str 반환. 파일 없거나 오류 시 None 반환 (fail-safe)."""
    try:
        if path.exists():
            return path.read_text(encoding="utf-8")
        return None
    except Exception:
        return None


def _write_file(path: Path, content: str) -> Dict[str, Any]:
    """파일에 원자적 쓰기. 성공/실패 dict 반환 (fail-safe)."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # 임시 파일 경유 원자적 쓰기
        import tempfile
        import shutil
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=path.parent,
            delete=False,
            suffix=".tmp",
            encoding="utf-8",
        ) as tmp:
            tmp_path = tmp.name
            tmp.write(content)
            tmp.flush()
            os.fsync(tmp.fileno())
        shutil.move(tmp_path, str(path))
        return {"ok": True, "path": str(path)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


__all__ = [
    "append_learning_entry",
    "append_learning_entries",
]
