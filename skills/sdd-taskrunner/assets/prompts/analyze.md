# 복잡도 분석 프롬프트

다음 태스크의 구현 복잡도를 1-10 점으로 평가하세요.

## 입력
- 태스크: {{task_title}}
- 구현자: {{implementer}}
- TDD 수준: {{tdd_level}}
- 의존 태스크: {{dependencies}}
- develop 아키텍처 결정 요약: {{architecture_summary}}

## 평가 기준

| 기준 | 가중치 | 설명 |
|------|--------|------|
| 구현 범위 | 25% | 변경/생성 파일 수, 새 모듈 여부 |
| 기술 난이도 | 25% | 외부 API, 비동기, 복잡한 상태 관리 |
| 의존성 깊이 | 20% | 선행 태스크 수, 공유 타입 변경 |
| 테스트 복잡도 | 15% | TDD FULL 시나리오 수, mock 필요성 |
| 통합 위험 | 15% | 다른 모듈 인터페이스 변경 여부 |

## 출력 형식

```json
{
  "complexityScore": 7,
  "reasoning": "외부 API 연동 + 스트리밍 파싱 + 에러 핸들링 5개 분기",
  "recommendedSteps": 8,
  "keyRisks": ["SSE 파싱 edge case", "네트워크 타임아웃 처리"]
}
```
