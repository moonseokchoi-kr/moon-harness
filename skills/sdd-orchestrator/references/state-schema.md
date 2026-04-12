# ORCHESTRATOR_STATE.md Schema

오케스트레이터가 런타임에 프로젝트의 `docs/sdd/ORCHESTRATOR_STATE.md`에 생성하는 상태 파일의 스키마.
git이 추적하므로 손상 시 복구 가능하고, 변경 이력이 commit log에 남는다.

## 파일 위치

```
<project-root>/docs/sdd/ORCHESTRATOR_STATE.md
```

## 스키마

```markdown
# Orchestrator State

## 메타
- develop 문서: <path to develop document>
- spec 문서: <path to spec document>
- 시작 시각: <ISO 8601>
- 마지막 갱신: <ISO 8601>
- 상태: PLANNING | EXECUTING | PAUSED_AT_LIMIT | COMPLETED | FAILED
- resume_at: <ISO 8601, PAUSED_AT_LIMIT일 때만>

## 팀 배정
| Team | 담당 Wave | 선행 팀 | 상태 |
|------|-----------|---------|------|
| 1    | Wave 1~4  | 없음    | PENDING |
| 2    | Wave 5~7  | Team 1  | PENDING |
| 3    | Wave 8~11 | Team 2  | PENDING |

> Wave가 모두 순차 의존이거나 팀이 1개이면 이 섹션을 생략하고 기존 단일 오케스트레이터 모드로 실행.

## Team 상태 (팀별 독립 섹션 — 각 팀 리더만 자기 섹션 씀)

### Team 1
- 상태: PENDING | EXECUTING | COMPLETED | FAILED
- 완료 Wave: -
- 마지막 갱신: -

### Team 2
- 상태: PENDING
- 완료 Wave: -
- 마지막 갱신: -

## Wave 구성
| Wave | 태스크 | 의존성 |
|------|--------|--------|
| 1 | T-1 | 없음 |
| 2 | T-2, T-14 | T-1 |
| 3 | T-3, T-4, T-5, T-6, T-7 | T-1 |
| ... | ... | ... |

## 현재 진행
- 현재 Wave: <N>
- 완료 Wave: <list>

## 태스크 상태
| ID | Wave | Status | Iteration | Agent | 비고 |
|----|------|--------|-----------|-------|------|
| T-1 | 1 | complete | 1 | - | |
| T-3 | 3 | implementing | 1 | sdd-flutter-engineer | 실행 중 |
| T-4 | 3 | reviewing | 1 | sdd-reviewer | 리뷰 중 |
| T-5 | 3 | testing | 2 | sdd-test-automator | 1회차: 타입 불일치 |

### Status 값
- `pending` — 아직 시작 안 됨
- `implementing` — Engineer Agent가 구현 중
- `reviewing` — Reviewer Agent가 리뷰 중
- `fixing` — Engineer Agent가 리뷰 피드백 반영 중
- `testing` — Test Automator Agent가 검증 중
- `complete` — 완료 (리뷰 + 테스트 통과)
- `interrupted` — 리밋/에러로 중단됨
- `escalated` — 3회 실패, 사용자 개입 필요

## 에이전트 배정
- 오케스트레이터: 메인 세션
- Engineer 슬롯 1: <T-ID> | idle
- Engineer 슬롯 2: <T-ID> | idle
- Engineer 슬롯 3: <T-ID> | idle
- Engineer 슬롯 4: <T-ID> | idle
- Reviewer: <T-ID> | idle
- Test Automator: <T-ID> | idle

## 파일 소유권
| 태스크 | 소유 파일/디렉토리 |
|--------|-------------------|
| T-3 | lib/models/ |
| T-4 | lib/repositories/transaction_repository.dart |
| T-5 | lib/repositories/category_repository.dart |

## 이력
- [HH:MM] T-1 구현 완료 → 리뷰 통과 → 테스트 통과
- [HH:MM] T-3 구현 완료 → 리뷰 피드백: "타입 불일치" → 재구현 중
- [HH:MM] 리밋 감지: 연속 2개 Agent 실패, 상태 저장 완료

## 리밋 시 마지막 상태 (리밋/중단 시 자동 기록)
### T-3 (implementing, iteration 1)
마지막 Agent 응답 요약: ...

### T-4 (reviewing, iteration 1)
마지막 Agent 응답 요약: ...
```

## 사용 규칙

1. **Phase 3(Plan)에서 초기 생성**: taskmaster가 Wave 구성, 태스크 상태 테이블을 채움. 상태는 PLANNING
2. **Phase 4(Execute) 진입 시**: 오케스트레이터가 상태를 EXECUTING으로 변경
3. **매 태스크 상태 변경 시 갱신**: implementing → reviewing 등
4. **리밋/에러 시**: 마지막 상태 섹션에 Agent 응답 요약 기록
5. **재개 시**: 새 오케스트레이터가 이 파일을 Read로 읽고 중단 지점 파악
6. **완료 시**: 상태를 COMPLETED로 변경, result 문서 생성 후 아카이브
