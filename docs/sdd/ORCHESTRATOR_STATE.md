# Orchestrator State

## 메타
- spec 문서: docs/sdd/spec/2026-10-19-sdd-phase1-code-context.md (단일 문서, ARCH_SKIP: arch/ui/api 문서 없음. "## 구현 계획" 섹션이 Wave·의존·직렬화 정본)
- task 문서: docs/sdd/task/sdd-phase1-code-context/2026-10-19-T-{1..13}-*.md
- feature: sdd-phase1-code-context
- worktree: /Users/moon/workspace/moon-harness/worktrees/sdd-phase1-code-context (브랜치 feature/sdd-phase1-code-context)
- 시작 시각: 2026-10-19T05:14:00Z
- 마지막 갱신: 2026-10-19T05:14:00Z
- 상태: PLANNING

## 빌드 프로파일
> 출처: CLAUDE.md "빌드 / 테스트" 절 (arch 문서 없음 — ARCH_SKIP. 현 오케스트레이터 요구에 따라 직접 기입)

| 필드 | 값 | 비고 |
|------|-----|------|
| 유형 | fast-scoped | 테스트 직접 실행 |
| 워밍업 빌드 | — | fast-scoped |
| 증분 빌드 | — | fast-scoped |
| 테스트 실행 | `<PY> -m pytest {filter} -q` | bq light lane 경유: `bq submit --wait --lane light -- <PY> -m pytest {filter} -q` |
| 테스트 필터 문법 | `tests/test_x.py` 또는 `tests/test_x.py::test_name` | 태스크별 스코프 지정 |
| clean 정책 | no-clean | 태스크 간 clean 금지 |

> `<PY>`는 경로를 적지 않는다. CLAUDE.md 확정 절차로 정한다: `python3 -m pytest --version`이 실패하면 `which -a python3` 후보마다 `import pytest`를 시도해 pytest를 가진 인터프리터를 확정하고, `<PY> -m pytest ...` 형태로 고정. 인터프리터 절대경로·`PATH=` prefix 하드코딩 금지.
> 워밍업 완료: 미실행(fast-scoped)

## 공유 worktree 병렬 규칙
- 같은 worktree를 공유하는 병렬 태스크는 **소유 파일만 명시적 `git add <파일>`** 한다. `git add -A` / `git add .` 금지.
- **브랜치 전환·생성 금지** (`git checkout -b`, `git switch`, `git branch` 등). 모든 커밋은 feature/sdd-phase1-code-context 에 쌓는다.
- 소유 파일 외 수정 금지. 위반이 타 소유 파일에서 발견되면 해당 소유 태스크로 되돌린다.
- protected 파일(`hooks/enforcement/stop-pipeline.py` T-4·T-7, `hooks/enforcement/phase-gate.sh` T-8)은 spec 승인 기록(2026-10-19) 범위 안에서만 수정. 범위 밖은 Ask first.

## Wave 구성
팀 파티셔닝: 단일 선형 체인(Wave 1 → 2 → 3 → 4 → 5)이라 팀 배정 생략(단일 오케스트레이터 모드).

| Wave | 태스크 | 의존성 | spec 구현 계획 대응 |
|------|--------|--------|--------------------|
| 1 | T-1, T-2, T-3, T-4 (병렬) | 없음 | Wave 1 전반 |
| 2 | T-5 | T-1, T-2, T-3, T-4. 완료 후 Wave 1 게이트: `tests/` 전체 통과 | Wave 1 후반 |
| 3 | T-6, T-7, T-8, T-9, T-10, T-11 (병렬, 소유 파일 비중복) | T-5 (Wave 1 게이트). T-7·T-8은 T-4 포함 | Wave 2 전반 |
| 4 | T-12 | T-5, T-6, T-7, T-9, T-11 | Wave 2 |
| 5 | T-13 | T-6, T-7, T-8, T-9, T-10, T-11, T-12. 완료 후 Wave 2 종료 게이트: `tests/` 전체 통과 | Wave 2 종료 |

## 현재 진행
- 현재 Wave: 1 (미시작)
- 완료 Wave: -

## 태스크 상태
| ID | Wave | Status | Iteration | Agent | 비고 |
|----|------|--------|-----------|-------|------|
| T-1 | 1 | pending | 0 | - | why 스킬 |
| T-2 | 1 | pending | 0 | - | grill + code-mapper 보강 |
| T-3 | 1 | pending | 0 | - | spec-writer(개명) + spec 템플릿 |
| T-4 | 1 | pending | 0 | - | stop-pipeline Phase 1 라벨 + init 초기 라벨 (protected 승인 범위) |
| T-5 | 2 | pending | 0 | - | sdd SKILL Phase 1. 완료 시 Wave 1 게이트 |
| T-6 | 3 | pending | 0 | - | architect 3종 + 에이전트 4종 삭제 |
| T-7 | 3 | pending | 0 | - | stop-pipeline Phase 2·3 라벨 (protected 승인 범위) |
| T-8 | 3 | pending | 0 | - | pipeline-utils mode 폐지 + phase-gate (protected 승인 범위) |
| T-9 | 3 | pending | 0 | - | taskmaster·taskrunner |
| T-10 | 3 | pending | 0 | - | compliance·test-automator·blocker·react |
| T-11 | 3 | pending | 0 | - | 오케스트레이터 빌드 프로파일 확보 |
| T-12 | 4 | pending | 0 | - | sdd SKILL Phase 2~4·정책 (Phase 1 절은 T-5 소유, 수정 금지) |
| T-13 | 5 | pending | 0 | - | README·CLAUDE.md·버전 0.15.0·정적 게이트. 완료 시 Wave 2 종료 게이트 |

## 에이전트 배정
- 오케스트레이터: 메인 세션
- Engineer 슬롯 1: idle
- Engineer 슬롯 2: idle
- Engineer 슬롯 3: idle
- Engineer 슬롯 4: idle
- Reviewer: idle
- Test Automator: idle

## 파일 소유권
같은 Wave 병렬 태스크 간 소유 파일은 겹치지 않는다. 공유 파일은 순차 의존으로 직렬화: SKILL.md(T-5 → T-12), stop-pipeline.py 및 관련 테스트(T-4 → T-7), pipeline-utils.sh·test_sdd_pipeline_init.py(T-4 → T-8).

| 태스크 | 소유 파일/디렉토리 |
|--------|-------------------|
| T-1 | skills/why/SKILL.md, skills/why/references/ (3개), tests/test_why_skill.py |
| T-2 | skills/grill/SKILL.md, skills/code-mapper/SKILL.md, tests/test_grill_skill.py, tests/test_code_mapper_blockers.py |
| T-3 | agents/sdd-spec-writer.md, agents/sdd-ux-researcher.md (삭제/개명), skills/sdd/references/spec-template.md, tests/test_sdd_spec_writer.py |
| T-4 | hooks/enforcement/stop-pipeline.py, hooks/enforcement/lib/pipeline-utils.sh (init_pipeline 초기 라벨 한 줄), tests/test_stop_pipeline_characterization.py, tests/test_stop_pipeline_kompound_gate.py, tests/test_sdd_pipeline_labels.py (신규), tests/test_sdd_pipeline_init.py (신규) |
| T-5 | skills/sdd/SKILL.md (Phase 1·에이전트 표·상태머신·승인 예외·템플릿 참조), tests/test_sdd_phase1_skill.py |
| T-6 | agents/webapp-architect.md, agents/flutter-architect.md, agents/native-architect.md, agents/sdd-ui-designer.md (삭제), agents/sdd-api-designer.md (삭제), agents/sdd-architect-reviewer.md (삭제), agents/sdd-context-manager.md (삭제), tests/test_sdd_phase2_agents.py |
| T-7 | hooks/enforcement/stop-pipeline.py (T-4 이후), tests/test_stop_pipeline_characterization.py (T-4 이후), tests/test_sdd_pipeline_labels.py (T-4 이후 확장), tests/test_sdd_pipeline_phase3.py |
| T-8 | hooks/enforcement/lib/pipeline-utils.sh (T-4 이후), hooks/enforcement/lib/logging.sh, hooks/enforcement/phase-gate.sh, tests/test_sdd_pipeline_init.py (T-4 이후 확장), tests/test_phase_gate_single_doc.py |
| T-9 | agents/sdd-taskmaster.md, skills/sdd-taskrunner/SKILL.md, skills/sdd-taskrunner/assets/templates/task-document.md, tests/test_sdd_task_docs.py |
| T-10 | agents/sdd-compliance-checker.md, agents/sdd-test-automator.md, agents/sdd-blocker-checker.md, agents/sdd-react-specialist.md, tests/test_sdd_agent_consumers.py |
| T-11 | skills/sdd-orchestrator/SKILL.md, skills/sdd-orchestrator/references/state-schema.md, tests/test_sdd_orchestrator_docs.py |
| T-12 | skills/sdd/SKILL.md (T-5 이후, Phase 2~4·문서 구조·정책 절), tests/test_sdd_phase234_skill.py |
| T-13 | README.md, CLAUDE.md, .claude-plugin/plugin.json, .claude-plugin/marketplace.json, tests/test_sdd_static_docs.py |

> 병렬 Wave 3 확인: T-7(stop-pipeline.py + labels/characterization/phase3 테스트), T-8(pipeline-utils.sh·logging.sh·phase-gate.sh + init/phase_gate 테스트)은 서로 다른 파일. T-6/T-9/T-10/T-11은 각자 agents/skills 파일이 달라 비충돌.
> 무변경 대상: hooks/lib/code_mapper/, hooks/lib/kompound_snapshot/, hooks/enforcement/e2e-gate.sh, hooks/hooks.json.

## 이력
- [05:14] STATE 생성 (PLANNING). task 문서 13개, ARCH_SKIP.
