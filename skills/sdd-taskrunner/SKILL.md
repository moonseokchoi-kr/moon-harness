---
name: sdd-taskrunner
description: "SDD Phase 3에서 develop 문서의 태스크 테이블을 상세 task 문서로 확장한다. sdd-taskmaster 에이전트 내부에서 호출된다."
---

# SDD Task Runner

sdd-taskmaster 에이전트가 호출하는 스킬. 복잡도 판정 기준, Steps 매핑, task 문서 생성 규칙을 제공한다.

**이 스킬은 메인 컨트롤러에서 직접 호출하지 않는다.** sdd-taskmaster 에이전트가 `Skill(sdd-taskrunner)`로 호출한다.

## 복잡도 → Steps 수 매핑

| 복잡도 점수 | Steps 수 | 근거 |
|------------|---------|------|
| 1-3 (Low) | 2-4 | 단순 설정, 파일 1-2개 변경 |
| 4-6 (Medium) | 4-7 | 로직 구현, 파일 3-5개 변경 |
| 7-10 (High) | 7-12 | 복잡한 로직, 다수 파일, 외부 연동 |

## 복잡도 판정 기준

- **구현 범위**: 변경 예상 파일 수, 새 모듈 생성 여부
- **기술 난이도**: 외부 API 연동, 비동기 패턴, 상태 관리 복잡도
- **의존성 깊이**: 다른 태스크에 의존하는 정도, 공유 타입 변경 여부
- **테스트 복잡도**: TDD FULL인 경우 테스트 시나리오 수
- **통합 위험**: 다른 모듈과의 인터페이스 변경 여부

## task 문서 생성 규칙

- develop 문서의 아키텍처 결정, API 설계, 데이터 모델을 참고하여 완료 조건 도출
- spec 문서의 기능 요구사항과 매핑하여 검증 가능한 완료 조건 작성
- TDD == FULL인 경우 테스트 시나리오 테이블 필수 생성
- Steps는 각각 독립적으로 검증 가능해야 함
- 변경 예상 파일은 프로젝트 구조를 분석하여 구체적 경로로 작성
- 템플릿: `~/.claude/skills/sdd-taskrunner/assets/templates/task-document.md`
