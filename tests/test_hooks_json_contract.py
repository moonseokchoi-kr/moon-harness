"""tests/test_hooks_json_contract.py — hooks/hooks.json 유효성 (F17 스코프 5)

CHARACTERIZATION TEST — 현재 동작 고정, 스펙이 아니다.

`hooks/hooks.json` 은 `hooks/enforcement/stop-pipeline.py` 와 함께 F17
회귀 안전망의 대상이다(arch §9.2 스코프 5). 이 파일이 고정하는 성질은:
  (a) `hooks.json` 이 유효한 JSON 이다.
  (b) `PreToolUse` → `matcher: "Bash"` 배열의 **기존** 5개 커맨드
      (`dangerous-command.sh`, `secret-detect.sh`, `branch-gate.sh`,
      `worktree-add-gate.sh`, `e2e-gate.sh`) 가 정확히 이 순서로 존재한다.

**브리틀 방지(중요)** — T-13(F14, `kompound-snapshot-gate.sh` hooks.json
등록)이 이 배열 끝에 6번째 커맨드를 추가할 예정이다(arch §5.2.1: "PreToolUse
→ matcher: Bash 배열의 마지막"). 따라서 이 파일은 "정확히 5개다" 라는 개수
단정을 하지 않는다. **"기존 5개가 이 순서 그대로 처음 5개 자리에 남아있는가"**
(리스트 슬라이스 비교, prefix 부분집합 관계)만 단정한다 — T-13 이후에도 이
테스트는 (신규 항목이 뒤에 붙는 한) 그대로 GREEN 이어야 한다.

스코프 밖(이번 사이클 대상 아님): `SessionStart`/`PostToolUse`/`Stop`/
`Edit|Write` matcher 블록의 내용. 이번 태스크(F17)는 `PreToolUse`→`Bash`
배열만 고정한다(§5.2.1이 T-13의 등록 지점으로 지목한 유일한 배열이므로).
"""

from __future__ import annotations

import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_HOOKS_JSON_PATH = _REPO_ROOT / "hooks" / "hooks.json"

# T-13 이전(현재)의 PreToolUse → matcher:"Bash" 배열 순서. 이 5개가 이 순서로
# 남아있는지만 확인한다 — "정확히 5개"라는 개수 단정은 하지 않는다.
_EXPECTED_EXISTING_BASH_COMMANDS_PREFIX = [
    "${CLAUDE_PLUGIN_ROOT}/hooks/dangerous-command.sh",
    "${CLAUDE_PLUGIN_ROOT}/hooks/secret-detect.sh",
    "${CLAUDE_PLUGIN_ROOT}/hooks/enforcement/branch-gate.sh",
    "${CLAUDE_PLUGIN_ROOT}/hooks/enforcement/worktree-add-gate.sh",
    "${CLAUDE_PLUGIN_ROOT}/hooks/enforcement/e2e-gate.sh",
]


def _load_hooks_json() -> dict:
    return json.loads(_HOOKS_JSON_PATH.read_text(encoding="utf-8"))


def _bash_matcher_block(hooks_data: dict) -> dict:
    pre_tool_use = hooks_data["hooks"]["PreToolUse"]
    bash_blocks = [b for b in pre_tool_use if b.get("matcher") == "Bash"]
    assert len(bash_blocks) == 1, (
        "PreToolUse 에 matcher:'Bash' 블록이 정확히 1개 있어야 한다 "
        "(F2 acceptance: kompound-snapshot-gate.sh 도 이 블록에 합류할 예정, arch §5.2.1)"
    )
    return bash_blocks[0]


def _bash_commands(hooks_data: dict) -> list:
    block = _bash_matcher_block(hooks_data)
    return [entry["command"] for entry in block["hooks"]]


def test_hooks_json_is_valid_json():
    # json.loads 가 예외 없이 끝나면 유효한 JSON 이다.
    data = _load_hooks_json()
    assert isinstance(data, dict)
    assert "hooks" in data


def test_pretooluse_bash_matcher_block_exists():
    data = _load_hooks_json()
    block = _bash_matcher_block(data)
    assert block["matcher"] == "Bash"
    assert isinstance(block["hooks"], list)
    assert len(block["hooks"]) >= len(_EXPECTED_EXISTING_BASH_COMMANDS_PREFIX)


def test_pretooluse_bash_matcher_preserves_existing_five_commands_in_order():
    """부분집합(prefix) 단정 — 신규 게이트(T-13)가 뒤에 추가돼도 GREEN 유지."""
    data = _load_hooks_json()
    commands = _bash_commands(data)

    prefix = commands[: len(_EXPECTED_EXISTING_BASH_COMMANDS_PREFIX)]
    assert prefix == _EXPECTED_EXISTING_BASH_COMMANDS_PREFIX


def test_pretooluse_bash_matcher_commands_are_command_type():
    data = _load_hooks_json()
    block = _bash_matcher_block(data)
    for entry in block["hooks"]:
        assert entry.get("type") == "command"
        assert isinstance(entry.get("command"), str) and entry["command"]
