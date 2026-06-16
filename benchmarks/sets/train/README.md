# benchmarks/sets/train/ — Frozen Training Golden Set

## 원칙 (F24)

- **Frozen**: 이 디렉토리의 파일은 eval 루프에서 수정되지 않는다. 러너는 읽기 전용으로 접근한다.
- **수동 추가만**: 새 케이스는 사람이 직접 레이블링하여 추가한다. 자동 생성 금지.
- **train vs held-out**: 이 디렉토리는 개선안 개발·튜닝에 사용하는 훈련 셋이다.
  `held-out/` 셋과 달리 candidate 평가 피드백을 train 케이스 기반으로 조정할 수 있다.

## 파일 형식 (JSON)

```json
{
  "id": "tc-NNN",
  "description": "케이스 설명 (사람 레이블)",
  "scenario": "시나리오 분류 (pr-converge | harness-tier | other)",
  "input": { ... },
  "expected_outcome": "CONVERGED | BLOCKED | ESCALATED | ...",
  "label": "pass | fail",
  "human_note": "레이블링 근거 및 주석"
}
```

## 현재 케이스 목록

- `tc-001-pr-converge-success.json`: PR 코멘트 2회 내 수렴 성공 시나리오
- `tc-002-pr-converge-escalate.json`: 서킷브레이커 발동 → 에스컬레이션 시나리오
- `tc-003-pr-converge-multi-signal.json`: 복수 시그널 처리 후 수렴 시나리오
