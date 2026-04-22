# HANDOFF: SDD 스킬 대규모 개선 — TDD + 언어별 엔지니어 + TaskRunner

> 이 문서는 새로운 에이전트가 컨텍스트 없이 이 파일만 읽고 바로 작업을 이어갈 수 있도록 작성되었다.

## 프로젝트 한줄 요약

SDD(Spec-Driven Development) 스킬에 TDD Red-Green-Refactor 패턴, 구현→리뷰 이터레이션 루프, 심각도 기반 판정 체계(P1/P2/P3), 언어별 전문 엔지니어 12개, performance-engineer, taskrunner 스킬을 도입하는 대규모 개선.

## 현재 상태

| 항목 | 상태 |
|------|------|
| SKILL.md TDD 흐름 재설계 | **완료** — RED→GREEN 이터레이션→VERIFY→REFACTOR |
| HARD-GATE 5개 | **완료** — Phase 순서, TDD Iron Law, worktree 격리, 에스컬레이션 한계, 의존 순서 |
| test-automator 삼중 모드 | **완료** — tdd/verify/refactor + RED 상태 판정 기준 |
| implementer 셀프 리뷰 제거 | **완료** — 품질은 reviewer에게 위임 |
| reviewer P1 전담 | **완료** — P1만 판정, DONE/BLOCKED 이진 판정 |
| performance-engineer | **완료** — P2 실측 검증, VERIFY 단계 배치 |
| 언어별 엔지니어 (9 신규 + 2 수정) | **완료** — ts,swift,vue,cpp,flutter,fastapi,python,nextjs,sql + rust,react 수정 |
| 구현자 자동 선택 로직 | **완료** — 12개 스택 감지 규칙 |
| sdd-taskrunner 스킬 | **완료** — taskmaster + 프롬프트 3개 + 템플릿 |
| 이터레이션 카운터 | **완료** — 모든 에이전트에 iteration: N/3 |
| develop 템플릿 확장 | **완료** — 테스트 전략 + 성능 테스트 전략 + TDD 컬럼 |
| SKIP TDD 분기 | **완료** — RED/REFACTOR 건너뜀 명시 |
| 미수정 8번: result 문서 생성 담당 | **미완료** |
| 미수정 9번: 실패 시 worktree 정리 | **미완료** |
| 필드 테스트 | **미실행** — 개선된 흐름을 실제 프로젝트에서 실행한 적 없음 |

## 핵심 문서 위치

| 문서 | 경로 | 용도 |
|------|------|------|
| SDD SKILL.md | `~/.claude/skills/sdd/SKILL.md` | **마스터 워크플로우 — 최우선 읽기** |
| Taskrunner SKILL.md | `~/.claude/skills/sdd-taskrunner/SKILL.md` | taskrunner 스킬 정의 |
| Taskmaster 에이전트 | `~/.claude/skills/sdd-taskrunner/agents/sdd-taskmaster.md` | task 문서 생성 에이전트 |
| 프롬프트 (analyze) | `~/.claude/skills/sdd-taskrunner/assets/prompts/analyze.md` | 복잡도 분석 프롬프트 |
| 프롬프트 (expand) | `~/.claude/skills/sdd-taskrunner/assets/prompts/expand.md` | Steps 분해 프롬프트 |
| 프롬프트 (scenario) | `~/.claude/skills/sdd-taskrunner/assets/prompts/scenario.md` | 테스트 시나리오 생성 프롬프트 |
| Task 문서 템플릿 | `~/.claude/skills/sdd-taskrunner/assets/templates/task-document.md` | task 문서 양식 |
| 에이전트 전체 | `~/.claude/agents/sdd-*.md` (23개) | 모든 SDD 에이전트 |
| 평가 계획 | `~/.claude/plans/atomic-hopping-bengio.md` | TDD 도입 계획 (참고용) |

다음 에이전트는 **SDD SKILL.md만 읽으면** 전체 흐름을 파악할 수 있다. 개별 에이전트 정의는 필요할 때 참조.

## 완료된 작업

### 1. TDD Iron Law + Phase 3 흐름 재설계
- HARD-GATE로 RED 먼저, 테스트 보호, GREEN 필수, 리뷰 필수 강제
- 태스크마다 반복: taskmaster → [TDD FULL] RED → GREEN 이터레이션(구현↔reviewer) → VERIFY(compliance + test-automator verify + performance-engineer) → [TDD FULL] REFACTOR TEST
- SKIP TDD 분기: RED/REFACTOR 건너뜀, 나머지 동일
- **사용자 결정**: implementer 셀프 리뷰 제거 → reviewer가 품질 전담, 이터레이션 루프

### 2. 심각도 체계 (P1/P2/P3)
- [P1] 기능 오류, 아키텍처 위반 → reviewer (정적 코드 리뷰)
- [P2] 성능 문제 → performance-engineer (벤치마크/프로파일링 실측)
- [P3] 스타일, 네이밍 → 린터/포매터 위임 (reviewer가 보고하지 않음)
- **사용자 결정**: P2를 reviewer가 추측하지 않고 performance-engineer가 실측
- **사용자 결정**: P3는 린터/포매터 영역이므로 reviewer가 다루지 않음

### 3. 언어별 엔지니어 에이전트
- VoltAgent/awesome-claude-code-subagents 레퍼런스 기반 9개 신규 생성
- 기존 rust-engineer, react-specialist TDD 패턴 적용
- 구현자 자동 선택 로직: package.json, Cargo.toml, pubspec.yaml 등으로 스택 감지

### 4. sdd-taskrunner 스킬
- Taskmaster AI 심층 분석 → 복잡도 분석(1-10 스코어), Steps 수 매핑, 테스트 시나리오 생성 패턴 차용
- **사용자 결정**: Taskmaster MCP 통합 vs 자체 제작 → 자체 제작 선택 (포맷 불일치, 이중 관리 위험)
- develop 태스크 테이블의 한 줄 → 완전한 task 문서(완료 조건, 테스트 시나리오, Steps, 변경 파일)로 확장

### 5. 이터레이션 카운터 + 에스컬레이션
- 모든 Phase 3 에이전트 입력에 `iteration: N/3`
- HARD-GATE: 3회 초과 시 자동 에스컬레이션 (4회째 자의적 시도 금지)

### 6. develop 템플릿 확장
- `## 테스트 전략` 섹션 (프레임워크, 단위/통합 대상)
- `## 성능 테스트 전략` 섹션 (기준선 테이블, 안티패턴 감시)
- 태스크 목록에 TDD 컬럼 (FULL/SKIP)

## 미완료 작업

### 즉시 필요
1. **미수정 8번: result 문서 생성 담당** — Phase 3 완료 시 누가 result 문서를 생성하는지 SKILL.md에 명시 (컨트롤러가 하면 충분)
2. **미수정 9번: BLOCKED 시 worktree 정리** — Phase 3 실패/중단 시 worktree 처리 정책 추가

### 후속 작업
- **필드 테스트**: 실제 프로젝트에서 개선된 SDD 흐름 실행. 특히 이터레이션 카운터, P1 피드백 전달, taskmaster 문서 생성이 핵심 검증 포인트.
- **평가 재실행**: 스킬 완성도 평가에서 6/10이었던 점수가 개선되었는지 재평가

## 실패하거나 주의가 필요한 점

### FULL 모드 미검증
- **문제**: 개선된 SDD 흐름이 실제 프로젝트에서 실행된 적 없음
- **원인**: 이 세션에서는 스킬 설계/작성만 완료
- **대응**: 다음 SDD 실행 시 흐름이 의도대로 동작하는지 관찰. 특히 GREEN 이터레이션 루프, VERIFY 반려 시 재진입, taskmaster 문서 품질

### reviewer DONE_WITH_CONCERNS 제거됨
- **문제**: reviewer가 P1만 판정하므로 DONE/BLOCKED 이진 판정만 남음. 미묘한 "괜찮지만 개선 여지" 피드백을 전달할 수단이 없음
- **대응**: 실행 시 문제가 되면 P2를 reviewer에게도 부분 허용하거나, DONE_WITH_CONCERNS 복원 고려

### 에이전트 간 피드백 전달 형식
- **문제**: reviewer → implementer 피드백이 마크다운 테이블로 전달되지만, 구조화된 형식(JSON 등)이 아님
- **대응**: 실행 시 implementer가 [P1] 피드백을 정확히 인식하는지 확인. 문제 시 구조화 형식 도입

## 환경 정보

```
SDD 에이전트: 23개 (~/.claude/agents/sdd-*.md)
SDD 스킬: 2개 (~/.claude/skills/sdd/, ~/.claude/skills/sdd-taskrunner/)
SKILL.md: ~650줄
HARD-GATE: 5개
```

## 다음 에이전트가 해야 할 일

1. **이 파일을 읽는다**
2. **SDD SKILL.md를 읽는다** (`~/.claude/skills/sdd/SKILL.md`)
3. **미수정 8,9번을 처리한다** (result 문서 담당 + worktree 정리)
4. **실제 프로젝트에서 SDD를 실행하여 필드 테스트한다**
