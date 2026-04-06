---
name: handoff
description: "Generate a HANDOFF.md document that captures full session context so the next agent (or a future you) can resume work without any prior context. Use this skill whenever the user says 'handoff', 'save context', 'write a handoff', 'pass this to the next agent', 'save progress for later', 'create a summary for the next session', or any variation of wanting to preserve conversation state for continuation. Also trigger when the user mentions switching agents, ending a session, or preparing for someone else to pick up the work."
---

# Handoff Document Generator

세션의 전체 컨텍스트를 캡처하여 다음 에이전트가 **이 파일 하나만 읽고** 바로 작업을 이어갈 수 있는 HANDOFF.md를 생성한다.

## 핵심 원칙

Handoff 문서는 **다음 에이전트의 첫 번째 읽기 자료**다. 이 문서만으로 다음을 판단할 수 있어야 한다:

1. 무엇을 만들고 있는가
2. 지금 어디까지 왔는가
3. 무엇이 성공했고, 무엇이 실패했는가
4. 다음에 정확히 무엇을 해야 하는가

코드를 복사하지 않는다 — 파일 경로를 가리킨다. 하지만 "왜 그렇게 했는지", "어디서 막혔는지"처럼 코드에 담기지 않는 맥락은 반드시 기록한다.

## 템플릿

`assets/HANDOFF_TEMPLATE.md` 파일을 읽어서 양식으로 사용한다. 템플릿의 HTML 주석(`<!-- -->`)은 작성 가이드이며, 최종 문서에서는 제거한다. 빈 섹션도 제거한다.

## 생성 프로세스

### Step 1: 프로젝트 상태 스캔

아래 정보를 수집한다. 해당 정보가 없으면 건너뛴다.

```
1. git status + git log --oneline -10    → 커밋 이력, 미커밋 변경사항
2. 프로젝트 루트 파일 목록 (ls)           → 프로젝트 구조 파악
3. package.json / Cargo.toml / etc.      → 의존성, 스크립트
4. docs/sdd/ 스캔                          → SDD 문서 존재 여부 + Phase 판정
5. .claude/plans/ 스캔                    → 활성 플랜 파일
6. CLAUDE.md 확인                         → 프로젝트 규칙
7. 환경 정보 (node -v, python3 -V 등)    → 런타임 버전
```

### Step 2: 대화 컨텍스트 정리

현재 대화에서 다음을 추출한다:

- **시도한 것**: 어떤 접근법을 시도했는가
- **성공한 것**: 어떤 결과물이 만들어졌는가 (파일 경로 포함)
- **실패/주의**: 어디서 막혔는가, 미검증 가정은 무엇인가
- **사용자 결정**: 사용자가 명시적으로 선택/거부한 사항
- **미해결 질문**: 아직 답이 나오지 않은 것

### Step 3: HANDOFF.md 작성

`assets/HANDOFF_TEMPLATE.md`를 읽고, 수집한 정보로 각 섹션을 채운다.

### Step 4: 저장 위치 결정

1. 사용자가 명시한 경로
2. `docs/sdd/` 하위 (SDD 프로젝트인 경우)
3. 프로젝트 루트의 `HANDOFF.md`

---

## 작성 가이드라인

### 반드시 포함
- **실패한 시도와 그 이유** — 같은 실수 반복 방지
- **미검증 가정** — 가정했지만 테스트하지 않은 것
- **사용자의 명시적 선택** — 기술적 결정에서 사용자가 고른 것과 맥락
- **문서 간 불일치** — 어느 것이 최종 확정본인지

### 피할 것
- 코드 통째로 복사 — 파일 경로로 가리킨다
- 모호한 상태 ("거의 완료") — 구체적으로 ("3/5 태스크 완료, T-4 진행 중")
- 대화 원문 옮기기 — 핵심만 요약
- 미확인 사항을 사실처럼 적기 — 명시적으로 "미확인"이라 표기

### SDD 프로젝트 추가 사항
- 현재 SDD Phase + 각 Phase 상태
- blocker-checker / compliance-checker / reviewer 결과 요약
- 사용자 게이트 승인 여부
- worktree 경로 및 브랜치 이름 (Phase 3)

---

## 사용자 확인

문서 생성 후 반드시 사용자에게 보여주고 확인한다:

1. 빠진 맥락이 있는지
2. 저장 위치가 맞는지
3. 추가 주의사항이 있는지
