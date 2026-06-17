# HANDOFF: moon-harness 자가개선 시스템 + 후속 프로세스 개선

> 이 문서는 새 에이전트가 컨텍스트 없이 이 파일만 읽고 바로 이어갈 수 있도록 작성됨.

## 프로젝트 한줄 요약

moon-harness = AI 에이전트 개발 라이프사이클을 구조화하는 Claude Code 플러그인(마크다운 skills/agents + Python `hooks/lib/` stdlib + bash hooks + pytest). 이번 세션에서 **자가개선 시스템(pr-converge + self-improve + 벤치마크 fitness)**을 SDD로 구현해 `main` 0.8.0으로 머지·push 완료. 이어서 **실사용에서 발견한 프로세스 개선 3건**을 `.harness/LEARNING.md`에 캡처(미구현).

## 현재 상태

| 항목 | 상태 |
|------|------|
| 자가개선 시스템 (v0.8.0) | **완료** — 11태스크/5웨이브, 463 pytest 통과, push됨 |
| plugin.json / marketplace.json | **완료** — 둘 다 0.8.0 동기화 |
| `feat/` → `feature/` 브랜치 prefix 수정 | **완료** |
| repo 자체 최소 하네스 (CLAUDE.md + .harness/LEARNING.md) | **완료** |
| **Build-aware TDD (#1)** | **완료** — 빌드 프로파일 추상화 도입, 22파일 수정, 463 pytest 통과 |
| **harness CLAUDE.local.md 폴백 (#2)** | **완료** — skills/harness/SKILL.md Step 3 폴백 |
| **공유 worktree git enforcement 격상 (#3, 선택)** | **미시작** — PreToolUse(Bash) L3 hook 후보. 미구현 |
| **버전 bump + push** | **미결정** — 0.9.0 bump + 커밋/push 사용자 승인 대기 |
| SDD 파이프라인 | COMPLETED. `.claude/state/pipeline.json` 잔여 — 무시/삭제 가능 |

## 핵심 문서 위치

| 문서 | 경로 | 용도 |
|------|------|------|
| **LEARNING 로그 (다음 작업 SSOT)** | `.harness/LEARNING.md` | 구현할 프로세스 개선 3건이 설계까지 확정돼 보존됨. **반드시 먼저 읽기** |
| 자가개선 spec | `docs/sdd/spec/2026-06-16-self-improving-harness.md` | 완료 기능의 EARS 스펙 (참고) |
| 자가개선 arch | `docs/sdd/design/arch/2026-06-16-self-improving-harness.md` | 결정↔판단 분리, 모듈 경계 (참고) |
| 결과 보고 | `docs/sdd/result/2026-06-17-self-improving-harness.md` | 완료 사이클 요약 |
| repo 규칙 | `CLAUDE.md` | 빌드/테스트, 핵심 규칙 |

> 다음 에이전트는 **`.harness/LEARNING.md`만 읽으면 다음 작업에 충분**. docs/sdd/* 는 완료 기능의 참고 자료.

## 완료된 작업

### 1. 자가개선 시스템 구현 (SDD 전체 사이클)
- 요구사항 합의 → `/sdd` 스펙(SIMPLE) → Phase 1~4 → 11태스크/5웨이브 구현·리뷰 → 머지.
- 결과물: `hooks/lib/self_improve/`(결정적 코어 13모듈, stdlib-only), `skills/pr-converge/`·`skills/self-improve/`(+scripts), `agents/harness-improvement-critic.md`, `benchmarks/`·`evals/`·`tests/`(463통과).
- 불변식 전부 리뷰 실측: 오염격리(apply_writer가 protected/하네스 경로 미수정), 단일repo→하네스 승격 차단, 벤치 채택게이트(점수하락/held-out회귀/콜드스타트 거부), 케이던스 300금지.

### 2. 버전 동기화 + push
- plugin.json 0.7.0→0.8.0, marketplace.json 0.5.0→0.8.0 + 설명/태그 갱신.
- push 2장애 해결: (a) gh 활성계정 불일치(403) → 소유자 `moonseokchoi-kr` 임시전환 push 후 `moonchoi-clo` 복구. (b) 원격 분기(`a28cbbf` Windows 수정) → 로컬 20커밋 rebase(충돌 없음) 후 push.

### 3. repo 자체 dogfood
- `CLAUDE.md`(목차형) + `.harness/LEARNING.md` 생성. self-improve 파서로 LEARNING 파싱 검증됨.

## 완료된 후속 작업 (이번 세션, 2026-06-17)

### 1. Build-aware TDD (`sdd-tdd` 엔트리) — 완료
**핵심 추상화**: "빌드 프로파일" (유형 build-required/fast-scoped · 워밍업 · 증분 빌드 · 테스트 실행+필터 문법 · no-clean).
- **발견**(Phase 2, architect): `CLAUDE.md` → `./CLAUDE.local.md` → 사용자 질문. arch 문서 `## 빌드 프로파일` 섹션에 기록.
- **전파**(Phase 3, taskmaster): arch 표를 `ORCHESTRATOR_STATE.md` 메타로 복사 + task 검증 명령어를 프로파일 스코프로 채움.
- **소비**(Phase 4): orchestrator가 진입 시 워밍업 1회 + no-clean 강제 + 디스패치 프롬프트에 프로파일 주입. test-automator/engineer는 증분 빌드 + 스코프 테스트로 RED/GREEN.
- **수정 파일(22)**: `skills/sdd/SKILL.md`(TDD Iron Law·빌드 프로파일 캐노니컬 섹션·Phase 2/3/4 게이트·task 템플릿), `skills/sdd-orchestrator/SKILL.md`(no-clean CRITICAL·Step1 워밍업·디스패치 주입·Step3 통합), `skills/sdd-orchestrator/references/state-schema.md`(프로파일 메타), `agents/{native,flutter,webapp}-architect.md`(발견·기록), `agents/sdd-taskmaster.md`, `agents/sdd-test-automator.md`("전체 실행"→스코프), `agents/sdd-implementer.md` + 11 engineer agents(step6 "전체 테스트 실행"→"GREEN 확인(증분+스코프)"), `skills/sdd-taskrunner/assets/templates/task-document.md`.

### 2. harness CLAUDE.local.md 폴백 (`harness` 엔트리) — 완료
- `skills/harness/SKILL.md` Step 3: CLAUDE.md 있으면 타깃, **없으면 committed 강제 생성 대신 `./CLAUDE.local.md` 타깃**(없으면 생성, .gitignore 추가 제안). 목차화·학습 포인터(`@.harness/LEARNING.md`)·import 라인 주입 모두 동일 타깃 규칙.

## 미완료 — 다음 작업 (선택)

### 3. 공유 worktree git enforcement 격상 (`sdd-orchestration` 엔트리) — 미시작
- PreToolUse(Bash)에서 worktree 내 `git add -A` 차단하는 L3 hook 검토. 현재 프롬프트 지시로만 회피.

### 검증/배포
- `PATH="/opt/homebrew/bin:$PATH" python3 -m pytest tests/ -q` → **463 통과**(회귀 0).
- **미결정**: 0.9.0 bump(plugin.json + marketplace.json 동기화) + 커밋 + push(소유자 `moonseokchoi-kr` 계정). 사용자 승인 대기.

## 실패하거나 주의가 필요한 점

### 공유 worktree 병렬 에이전트 git 충돌 (재발성)
- **문제**: 한 Wave에 병렬 engineer를 같은 worktree에 디스패치 → (a) `git add -A`가 다른 태스크 파일 흡수, (b) engineer가 `git checkout -b`로 자기 브랜치 만들어 feature 브랜치 뒤처짐(머지 시 tip 놓침).
- **대응**: 병렬 프롬프트에 "**소유 파일만 명시적 `git add`** + **브랜치 전환 금지**" 명시. 머지 전 `git branch -vv`로 실제 tip 확인. 근본책 = `isolation: worktree` 또는 오케스트레이터 일괄 커밋.

### pipeline 헬퍼 PATH 의존
- `hooks/enforcement/lib/pipeline-utils.sh`가 `date`/`python3`를 PATH에서 못 찾는 경우 있음 → `export PATH="/opt/homebrew/bin:/usr/bin:/bin:$PATH"` 선행. pytest는 homebrew python3(3.14)에만 설치(Xcode python3엔 없음).

### 미검증 가정
- pr-converge/self-improve 스킬의 **라이브 동작(claude -p, gh 실호출)은 미검증** — 결정적 코어는 pytest 통과, 라이브 eval(`evals/`)은 CLI 필요로 미실행.
- self-improve 루프 자체는 실제 사이클 미실행(코어 함수만 dogfood 파싱 검증).

## 환경 정보

```
OS: macOS (Darwin 25.5.0)
Runtime: python3 3.14.4 (homebrew, pytest 9.0.3) — Xcode python3엔 pytest 없음
pytest: PATH="/opt/homebrew/bin:$PATH" python3 -m pytest tests/ -q
git remote: origin = github.com/moonseokchoi-kr/moon-harness (push는 moonseokchoi-kr 계정 필요)
프로젝트 경로: /Users/moon/workspace/moon-harness
플러그인 캐시: ~/.claude/plugins/cache/moon-harness/moon-harness/0.8.0/ (push 반영됨)
```

## 다음 에이전트가 해야 할 일

1. **이 파일을 읽는다** (지금)
2. **`.harness/LEARNING.md`를 읽는다** — `sdd-tdd`·`harness`·`sdd-orchestration` 3개 엔트리에 설계 확정
3. **Build-aware TDD 구현** (미완료 #1) — 위 5파일. 하드코딩 금지, 프로파일 발견 기반
4. **harness CLAUDE.local.md 폴백 구현** (미완료 #2) — `skills/harness/SKILL.md`
5. 수정은 harness-tier → 사용자 승인 후 진행. 완료 후 `pytest tests/` 회귀 확인, 필요 시 0.9.0 bump(plugin+marketplace 동기화) + push(소유자 계정)
