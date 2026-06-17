# Project Learning Log

SDD 에이전트(sdd-implementer, sdd-reviewer, sdd-compliance-checker 등)와 pr-converge가
사이클 중 발견한 반복 가능한 교훈을 append한다. 사람이 직접 편집하지 않는다.

self-improve 루프의 입력(raw 신호)이다. 검증 게이트를 통과한 항목만 docs/lessons-learned.md로
승격되거나 enforcement(hook)로 격상된다. 상세 규칙: skills/self-improve/SKILL.md.

엔트리 태그 포맷: `<!-- tags: domain=, stage={구현|pr-converge}, provenance_repo= -->`

---

## 2026-06-17 — self-improving-harness / Phase 4 orchestration
<!-- tags: domain=sdd-orchestration, stage=구현, provenance_repo=moon-harness -->

**유형**: 숨은 제약
**발견 맥락**: Phase 4 / sdd-orchestrator (Wave 1-B 병렬 디스패치)
**교훈**: 같은 worktree를 공유하는 병렬 engineer는 `git add -A`/`git add .` 시 다른 태스크의
미완성 파일을 자기 커밋으로 흡수한다. 병렬 디스패치 시 **소유 파일만 명시적으로 `git add`** 하도록 지시할 것.
**근거**: T-3 커밋(25200cd)이 병렬 T-4의 파일을 흡수, T-3 코어가 untracked로 누락됨.
**조치**: 이후 Wave에서 "소유 파일만 stage" 지시로 재발 0건 확인. enforcement(L3) 후보 — PreToolUse(Bash)에서 worktree 내 `git add -A` 차단 검토.

## 2026-06-17 — self-improving-harness / Phase 4 merge
<!-- tags: domain=sdd-orchestration, stage=구현, provenance_repo=moon-harness -->

**유형**: 숨은 제약
**발견 맥락**: Phase 4 / 머지 (worktree 브랜치 ref 이탈)
**교훈**: 공유 worktree에서 engineer가 자기 브랜치를 `git checkout -b`로 만들면 이후 커밋이
거기 쌓이고 원래 feature 브랜치는 뒤처진다. 머지 시 tip을 놓칠 수 있으니 **engineer에게 브랜치 전환 금지**를
지시하고, 머지 전 `git branch -vv`로 실제 tip을 확인할 것.
**근거**: T-2 engineer가 worktree에서 `feat/T-2-tier-guard-parser` 생성 → 전체 작업이 거기 land,
`feat/self-improving-harness`는 T-1(cb8c411)에 고정. ff 머지가 T-1에서 멈춤.
**조치**: 실제 tip으로 머지 재완료. 근본 대응 = 병렬 engineer를 `isolation: worktree`로 격리하거나 오케스트레이터 일괄 커밋.
