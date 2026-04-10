# Agent 디스패치 가이드

sdd-orchestrator가 Phase 4(Execute)에서 서브에이전트를 디스패치할 때 참조하는 가이드.

## 디스패치 패턴

### Engineer 디스패치

```
Agent(
  subagent_type: "sdd-flutter-engineer",  // task 문서의 구현자에 맞게 선택
  prompt: "
    develop 문서: <path>
    task 문서: <path>
    태스크: T-<ID> — <내용>
    소유 파일: <file-list>

    위 태스크를 구현해. 소유 파일 범위 안에서만 작업하고,
    완료되면 커밋 메시지에 'feat: T-<ID> <요약>'을 사용해.
  ",
  run_in_background: true  // 병렬 실행 시
)
```

### Reviewer 디스패치

```
Agent(
  subagent_type: "sdd-reviewer",
  prompt: "
    태스크 T-<ID> 리뷰 요청.
    develop 문서: <path>
    task 문서: <path>
    요구사항: <T-ID의 요구사항>

    다음을 확인해:
    1. develop/task 문서의 요구사항이 모두 구현되었는지
    2. 소유 파일 목록의 모든 파일이 실제로 존재하는지
    3. 모든 변경된 파일을 빠짐없이 읽고 코드 품질 확인
    4. 정적 분석 에러 0개 확인

    결과: REVIEW_PASS 또는 REVIEW_FAIL: <피드백>
  "
)
```

### Test Automator 디스패치

```
Agent(
  subagent_type: "sdd-test-automator",
  prompt: "
    태스크 T-<ID> 검증 요청.
    소유 파일: <file-list>

    다음을 실행하고 결과를 보고해:
    1. 프로젝트 빌드 (에러 0개 확인)
    2. 정적 분석 (에러 0개 확인)
    3. 관련 테스트 실행

    결과: TEST_PASS 또는 TEST_FAIL: <실패 원인>
  "
)
```

## subagent_type 매핑

| 기술 스택 | subagent_type |
|----------|---------------|
| Flutter/Dart | sdd-flutter-engineer |
| React/Next.js | sdd-react-specialist / sdd-nextjs-engineer |
| Vue | sdd-vue-engineer |
| TypeScript | sdd-ts-engineer |
| Python | sdd-python-engineer |
| FastAPI | sdd-fastapi-engineer |
| Rust | sdd-rust-engineer |
| C++ | sdd-cpp-engineer |
| Swift | sdd-swift-engineer |
| SQL | sdd-sql-engineer |
| 범용 | sdd-implementer |

## 동시 실행 제한

- **Engineer**: 최대 4개 동시 (Wave 내)
- **Reviewer**: 1개 (순차 리뷰)
- **Test Automator**: 1개 (순차 테스트)
- 5개 이상 태스크가 있는 Wave → 4개 먼저 실행, 완료된 슬롯에 다음 태스크 배정

## 에러 핸들링

### 재시도 정책
- Agent 실패 (에러 반환): 1회 재시도
- 재시도도 실패: iteration +1, 이전 피드백 포함해서 재디스패치
- iteration >= 3: escalated 상태, 사용자 에스컬레이션

### 리밋 감지
- Agent가 리밋 관련 에러 반환 시: 해당 태스크를 interrupted로 변경
- 연속 2개 Agent가 리밋 에러: 전체 리밋 판정
  - 남은 Agent 디스패치 보류
  - ORCHESTRATOR_STATE.md에 현재 상태 저장
  - 상태를 PAUSED_AT_LIMIT으로 변경
  - 사용자에게 알림 (Discord 연결 시)

### 피드백 누적
- iteration 2 이상: 이전 리뷰/테스트 피드백을 전부 Engineer 프롬프트에 포함
- 형식: "이전 피드백 (iteration N): <피드백 내용>"
