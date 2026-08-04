"""hooks/lib/kompound_snapshot/__main__.py — `python3 -m hooks.lib.kompound_snapshot` 진입점.

설계 SSOT: `docs/sdd/design/arch/2026-07-29-kompound-snapshot-hook.md` §3.1
(`__main__.py` 파일 역할), §6.2("호출 형태": `python3 -m
hooks.lib.kompound_snapshot <subcommand> [opts]`).

`cli.main()`이 반환한 종료 코드를 그대로 프로세스 종료 코드로 전파한다
(`sys.exit(cli.main(...))`) — 종료 코드 변형·재해석을 하지 않는다.
"""

from __future__ import annotations

import sys

from hooks.lib.kompound_snapshot.cli import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
