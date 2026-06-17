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

## 2026-06-17 — sdd-process / TDD on large repos
<!-- tags: domain=sdd-tdd, stage=구현, provenance_repo=moon-harness -->

**유형**: 사용자 교정 패턴 (실사용 중 발견)
**발견 맥락**: Phase 4 / 거대 레포(C++/Marvelous급)에서 SDD 실행
**교훈**: 주력 레포는 **빌드 산출물 + `-unittest` 플래그로 테스트**하는 구조라 빌드가 필수다(테스트만 도는 경량 타깃 없음).
per-task로 RED/GREEN마다 풀빌드는 비현실적 → 에이전트가 RED/GREEN을 생략하고 끝에 1회만 빌드 → TDD 무결성 붕괴.
핵심: 비싼 것은 **콜드 캐시 빌드 1회**이고 그 후 증분 빌드는 빠르다. 따라서 입도를 바꿀 필요 없이,
**Phase 4 진입 시 워밍업 빌드 1회** → 이후 **per-task 증분 빌드 + `-unittest=<필터>` 스코프 실행**으로 RED/GREEN을 유지한다.
**no-clean 규율**(태스크 간 clean 금지)로 캐시를 보존하는 게 관건.
**근거**: sdd-test-automator verify "전체 실행", tdd-gate는 RED/GREEN 실행 여부 미검증. 빌드=필수(아티팩트 -unittest), 비용은 콜드 1회.
**조치**: SDD Phase 4를 build-aware로. 단 **레포 특화 하드코딩 금지(하네스는 범용)** — 빌드/유닛테스트 *명령*은
`CLAUDE.md`/`./CLAUDE.local.md`(repo 루트)에서 발견하거나 없으면 사용자에게 질문해 "빌드 프로파일"로 기록한다.
일반 원칙(①진입 워밍업 빌드 1회 ②per-task 증분 빌드+테스트 실행 스코프 ③no-clean 규율)만 하네스가 강제하고,
구체 명령(워밍업/증분/테스트 필터)은 프로파일에서 주입. fast-scoped 레포는 워밍업 생략 등 프로파일이 cadence를 분기.

## 2026-06-17 — harness-skill / CLAUDE.md 자동 업데이트 폴백
<!-- tags: domain=harness, stage=구현, provenance_repo=moon-harness -->

**유형**: 사용자 교정 패턴
**발견 맥락**: harness 스킬의 CLAUDE.md 자동 업데이트(Step 3 목차화 + 학습 포인터 주입) 검토 중
**교훈**: harness 스킬이 CLAUDE.md를 자동 업데이트/생성할 때, **CLAUDE.md가 없으면 committed CLAUDE.md를
강제 생성하지 말고 repo 루트 `./CLAUDE.local.md`를 대신 업데이트**해야 한다. 공유 레포에선 committed CLAUDE.md를
원치 않을 수 있고, CLAUDE.local.md는 로컬/gitignore 관행이기 때문. (빌드 프로파일 발견의 `./CLAUDE.local.md` 폴백과 동일 원칙.)
**근거**: harness/SKILL.md Step 3은 CLAUDE.md만 대상으로 하고 부재 시 동작/폴백이 없음.
**조치**: harness/SKILL.md의 CLAUDE.md 자동 업데이트 로직에 "CLAUDE.md 부재 → ./CLAUDE.local.md 타깃" 폴백 추가. 학습 포인터(@.harness/LEARNING.md 등) 주입도 동일 타깃 규칙 적용.
