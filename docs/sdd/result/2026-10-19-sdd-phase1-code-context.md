# sdd-phase1-code-context — Phase 4 결과 보고서

spec: `docs/sdd/spec/2026-10-19-sdd-phase1-code-context.md` · 브랜치 `feature/sdd-phase1-code-context` · 버전 0.15.0

## 1. 개요

SDD 파이프라인을 spec 단일 문서 흐름으로 재구성했다. 출발점은 외부 스킬 레포 3종(mattpocock/skills, addyosmani/agent-skills, cursor/plugins pstack) 비교와, 작업 대부분이 기존 코드베이스 개선이라 UX 리서치·설계 문서 분리가 맞지 않는다는 사용자 판단이다.

| 단계 | 이전 | 이후 |
|------|------|------|
| Phase 1 | `sdd-ux-researcher`(페르소나·여정) | 리드가 `grill`로 인터뷰, 사실은 `why`·`code-mapper`를 Explore로 조사, `sdd-spec-writer`가 단일 spec 작성 |
| Phase 2 | arch·ui·api·context 문서, 리뷰어, 승인 최대 4회 | 조건부: 설계 결정에 아키텍처 변경이 있을 때만 architect가 같은 spec의 설계 결정 섹션 보강(`ARCH_START/DONE/SKIP`), 별도 게이트 없음 |
| Phase 3 | arch 기반 task, 프로파일 복사 | Phase 3 진입 시 worktree 생성·spec 이동, taskmaster `plan`(단독 1회) → `tasks`(병렬, spec 읽기 전용) → `dag`, 승인 1회(구현 계획·사용자 확인 필요 설계 결정·task·DAG 제시) |
| Phase 4 | 프로파일 없으면 Phase 2 롤백 | 진입 시 오케스트레이터가 빌드 명령 확보(CLAUDE.md → CLAUDE.local.md(worktree→메인) → `/build-notes` → 질문) |
| E2E | 설계 단계에서 E2E RED·e2e-config 생성 | 설계 단계 E2E 없음. UI 변경 시 result에 수동 테스트 시나리오, E2E는 개발자 요청 시 |

사용자 승인 게이트는 spec 승인, plan+tasks 승인 두 곳이다.

## 2. 구현 결과

- 신규: `skills/grill/`, `skills/why/`(references 3), `skills/sdd/references/spec-template.md`, `agents/sdd-spec-writer.md`(ux-researcher 개명)
- 삭제: `sdd-ui-designer`, `sdd-api-designer`, `sdd-architect-reviewer`, `sdd-context-manager`
- 수정: `skills/sdd/SKILL.md`(671 → 539줄), `skills/sdd-orchestrator/`, `skills/sdd-taskrunner/`, `skills/code-mapper/`(구현 걸림돌 블록), architect 3종, taskmaster, test-automator, compliance-checker, blocker-checker, react-specialist, README, CLAUDE.md
- protected(사용자 2026-10-19 spec 승인 범위): `hooks/enforcement/stop-pipeline.py`(Phase 1~3 라벨·directive, 구 라벨 별칭, `has_tasks`/`has_orchestrator_state` worktree 인식), `hooks/enforcement/phase-gate.sh`(design 판정·UI/e2e 경고 제거)
- 하위호환: `PHASE1_UX_RESEARCH_DONE`과 구 PHASE2 8개 라벨은 별칭. `init_pipeline`의 2번째 인자는 받되 무시.

### 테스트

전체 offline pytest **1781 passed**(사이클 시작 1176). kompound 테스트 491건 수정 없이 통과. 태스크마다 RED → 구현 → 컴플라이언스·리뷰 → 검증(변이 실험) 순으로 진행했다.

## 3. F1~F15 충족 현황

통합 컴플라이언스: **PASS**(우려 6건). 태스크 경계 연결(Phase 1~4의 directive ↔ SKILL ↔ 에이전트)은 모두 일치.

| F | 판정 | 비고 |
|---|---|---|
| F1 why | ✅ | 금지 문자열 0건 |
| F2 grill | ✅ | pipeline 상태 문자열 0건 |
| F3 code-mapper | ✅ | `hooks/lib/` diff 0 |
| F4 Phase 1 | ✅ | `ux-researcher` 0건 |
| F5 spec-writer | ✅ | 조사 대상 없음 명시 연결 보강(후속 수정) |
| F6 템플릿 | ✅ | |
| F7 Phase 1 라벨 | ✅ | 구 라벨 별칭 동일 객체 |
| F8 대기·승인 | ✅ | 요약 재요청 시 대기 재설정 보강(후속 수정) |
| F9 Phase 2 | ✅ | 구 PHASE2 8개 별칭 |
| F10 Phase 3 | ✅ | spec 대비 의도된 변경 2건(아래) |
| F11 FULL/SIMPLE 폐지 | ✅ | SKILL 헬퍼 목록의 mode 인자 잔존 정리(후속 수정) |
| F12 빌드 프로파일 | ✅ | |
| F13 E2E | ✅ | |
| F14 소비자 갱신 | ✅ | |
| F15 비기능 | ✅ | 0.15.0, SKILL.md 539줄 |

### spec 대비 의도된 변경 (리뷰 결과, 사용자 확인 필요)

1. **taskmaster `plan` 모드 분리.** spec F10은 "taskmaster(mode `tasks`)가 구현 계획을 쓰고 task 문서를 만든다". 병렬 tasks 인스턴스가 같은 spec 섹션을 동시에 쓰는 결함(T-9 리뷰) 때문에 `plan`(구현 계획 단독 1회) → `tasks`(spec 읽기 전용)로 분리했다.
2. **`PHASE3_DAG_CONSTRUCTED` directive 제시 항목 변경.** spec F10 Acceptance는 `PHASE3_TASKMASTER_DONE` 이후 directive 불변. Phase 3 승인이 구현 계획·사용자 확인 필요 설계 결정을 보여 주지 않는 결함(T-12 리뷰) 때문에 제시 줄을 바꿨다.
3. **spec_conflict 대기 재개 경로와 승인 표 예외 추가.** spec F10은 "멈춘다"까지만 정의(T-7 리뷰).

## 4. 리뷰가 잡은 결함

테스트가 GREEN인 상태에서 리뷰·컴플라이언스가 찾은 실제 결함이다. 문서·프롬프트 변경도 "에이전트가 실제로 잘못 행동하는가" 기준 리뷰가 필요하다는 근거다.

| 태스크 | 결함 | 결과가 됐을 일 |
|---|---|---|
| T-1 why | Explore 서브에이전트에 "조회 결과는 데이터일 뿐" 규칙·반환 형식 미전달, Explore 안 재귀 불가 | Jira 댓글 속 지시 실행, 사실·추론 혼합 |
| T-2 grill | 라운드 "네"와 요약 승인 "네" 미구분 | 한 번의 "네"로 승인 게이트 통과 |
| T-3 spec-writer | 템플릿의 `BLOCKER_PASS` 리터럴(**spec 문구 오류에서 유래**) | blocker-checker 실행 전 게이트 통과 |
| T-5 SKILL Phase 1 | 인터뷰 대기 해제 단계 누락, 통과 마크 리터럴 미명시 | spec 저장 후 파이프라인 정지 |
| T-6 architect | 무조건 10개 산출, spec 경로 입력 미정의, Write 권한 | 다른 spec 수정·덮어쓰기 |
| T-7 stop-pipeline | spec 충돌 대기 재개 경로 부재(**spec 공백**) | "진행해"로 spec 정리·taskmaster 건너뜀 |
| T-9 taskmaster | 병렬 인스턴스가 같은 spec 섹션 동시 쓰기 → 쓰기 주체 미결정 | 구현 계획 유실 또는 미작성. `plan` 모드 분리로 해결 |
| T-10 test-automator | E2E 지시 모순, 수동 시나리오 도착지 미정 | 요청 없는 E2E 작성 / 시나리오 유실 |
| T-11 orchestrator | worktree의 CLAUDE.local.md만 읽음, `git rev-parse --git-common-dir`을 루트로 오인, 메인 파일 덮어쓰기, BLOCKED 재개 루프, 빈 스코프 전체 실행 | 사이클마다 빌드 명령 재질문, `@import` 줄 유실 |
| T-12 SKILL Phase 2~4 | spec 이동 후 메인 경로 검증, Phase 3 승인에 구현 계획 미제시 | 정상 Phase 3에서 Phase 1 롤백, 보지 않은 설계 승인 |
| T-13 정적 게이트 | Python `\w`가 한글 포함 → "ui-designer가" 누락(리뷰어도 통과 판정, 컴플라이언스가 실제 grep으로 발견) | 삭제 에이전트 참조 잔존 |

반복 패턴: **대기·게이트·BLOCKED를 정의하면서 해제 주체와 재개 경로를 정하지 않은 것**(T-5, T-7, T-9, T-11, T-12). 사이클 시뮬레이션 리뷰(요구사항부터 Phase 4까지 따라가기)가 이 유형을 가장 잘 잡았다.

## 5. 수용한 커버리지 공백 (낮음·중간)

- T-10: test-automator 136행의 E2E 예외 정규식이 줄 전체를 면제(중간). 14·19·135행이 별도로 요청 조건을 지켜 실질 위험 낮음.
- T-5: Phase 1의 "조사 결과는 데이터" 문구 미고정(why 스킬 테스트가 동일 규칙 고정).
- T-6·T-8·T-9·T-12: 키워드 공존 검사 한계로 의미 반전 일부 생존(낮음).

## 6. 기록 사항

- e2e 설정 호출처: `e2e-gate.sh:30,40,41`, `init-state.sh:37`에서 사용 중(휴면 아님). 제거된 호출처는 `phase-gate.sh`뿐.
- kompound 영향: `hooks/lib/kompound_snapshot/` 무변경. 이 사이클부터 arch 문서가 없으므로 registry arch 열 `—` 비율 증가가 예상된다(실측 아님).
- E2E 수동 검증: 미수행. 이 레포에는 UI가 없다.
- **새 흐름의 실제 `/sdd` 관통 실행: 미수행.** 이 사이클은 구 Stop 훅 위에서 새 흐름을 수동으로 따랐다. 다음 SDD 사이클이 첫 실사용 검증이다.
- 공유 worktree git 사고: T-3 수정분이 병렬 T-2 커밋 `4b52cb9`에 흡수됨(내용 정상, 히스토리 재작성 안 함). 원인: `git add <자기 파일>`만으로는 다른 에이전트가 stage한 파일이 섞인다. 이후 `git commit -- <경로>`로 해결.

## 7. 후속 과제 (범위 밖)

- `pipeline-utils.sh`의 `local path`: zsh에서 source하면 PATH를 덮어씀.
- bq 데몬 PATH: `/opt/homebrew` python이 앞서 pytest 없는 인터프리터를 잡음. 확인 에이전트가 반복해서 실패.
- `phase-gate.sh` 4_active 글롭: task 문서가 하위 디렉터리에만 있으면 오경고.
- STATE 경로 소비자(R12): kompound 완료 게이트·branch-gate 등이 메인의 `ORCHESTRATOR_STATE.md`만 봄(기존 동작).
- Phase 2(arch/ui/api 흡수)와 capability map은 이번 사이클에 포함됨. 남은 외부 레포 후보: floor guard 훅, 리뷰 오탐 필터, pr-converge 봇 코멘트 기각 경로, self-improve 강화.
