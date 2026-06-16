# Target File — 중복/충돌 검사용 픽스처

이 파일은 `run_prechecks`의 중복 검사 및 충돌 검사 테스트에 사용된다.

## 기존 규칙 (중복 검사 대상)

Refresh tokens must use single-flight to prevent concurrent rotation.
The token refresh endpoint must be deduplicated before dispatching.

## 타입 좁히기 (TypeScript)

TypeScript type narrowing after await boundaries requires explicit type
assertions. Always apply narrowing guard after awaiting async calls.

## 금지 규칙 (충돌 검사 대상)

절대 refresh token을 병렬로 호출하지 말 것 (금지).
concurrent token refresh 하지 말라. 반드시 단일 요청으로 직렬화.

## 무관한 섹션

이 내용은 어떤 후보와도 겹치지 않는다.
Completely unrelated content about pipeline optimization.
