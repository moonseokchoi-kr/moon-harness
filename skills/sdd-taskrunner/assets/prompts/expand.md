# 태스크 확장 프롬프트

다음 태스크를 {{recommended_steps}}개의 구현 Steps로 분해하세요.

## 입력
- 태스크: {{task_title}}
- 복잡도: {{complexity_score}}/10
- 완료 조건: {{completion_conditions}}
- 아키텍처 결정: {{architecture_decisions}}
- 데이터 모델: {{data_model}}
- 변경 예상 파일: {{expected_files}}

## 분해 원칙

1. **각 Step은 독립 검증 가능** — Step 완료 후 빌드가 깨지지 않아야 한다
2. **순서는 의존성 기반** — 타입 정의 → 인터페이스 → 구현 → 연결 순서
3. **Step당 1개 관심사** — 파일 생성 + 로직 구현을 같은 Step에 넣지 않는다
4. **검증 가능한 체크포인트** — "~를 구현한다"가 아니라 "~가 동작한다"로 서술

## 출력 형식

각 Step을 다음 형식으로:
```
- [ ] Step {N}: {행동} — {검증 방법}
```

예시:
```
- [ ] Step 1: PluginSettings 타입 정의 — tsc --noEmit 통과
- [ ] Step 2: Observable 클래스 구현 — subscribe/set 테스트 통과
- [ ] Step 3: main.ts에서 loadSettings 연결 — 빌드 성공 + 콘솔 로그 확인
```
