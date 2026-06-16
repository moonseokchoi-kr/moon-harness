# benchmarks/sets/held-out/ — Frozen Held-Out Golden Set

## 원칙 (F24 — Goodhart 방어)

- **Frozen**: 이 디렉토리의 파일은 eval 루프에서 절대 수정되지 않는다.
- **수동 추가만**: 새 케이스는 사람이 직접 레이블링하여 추가한다. 자동 생성 금지.
- **개선안 최적화 금지**: candidate 평가 루프가 이 셋의 결과를 기반으로 개선안을 조정해서는 안 된다.
  이 셋은 최종 회귀 검증 용도로만 사용한다 (Goodhart 법칙 방어).
- **회귀 판정**: `compute_delta`에서 `held_out_regression=True`가 반환되면 채택 불가.

## 파일 형식 (JSON)

```json
{
  "id": "ho-NNN",
  "description": "케이스 설명 (사람 레이블)",
  "scenario": "시나리오 분류 (pr-converge | harness-tier | other)",
  "input": { ... },
  "expected_outcome": "CONVERGED | BLOCKED | ESCALATED | ...",
  "label": "pass | fail",
  "human_note": "레이블링 근거 및 주석"
}
```

## 현재 케이스 목록

- `ho-001-pr-converge-edge-case.json`: 엣지케이스 — 상태 파일 없는 첫 실행 시나리오
- `ho-002-circuit-breaker-boundary.json`: 서킷브레이커 임계값 경계 시나리오
