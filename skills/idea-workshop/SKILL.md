---
name: idea-workshop
description: "아이디어의 전체 라이프사이클을 관리하는 오케스트레이터 스킬. 사용자가 아이디어를 이야기하면 현재 단계를 판단해서 적절한 모드(브레인스토밍/검증)로 안내한다. '아이디어 회의하자', '아이디어 하나 같이 발전시켜보자', '이거 같이 고민해보자' 같은 포괄적인 요청에 트리거한다. 특정 단계가 명확한 경우(초기 발산이면 brain-storm, 검증이면 deep-idea)에는 해당 스킬이 직접 트리거되지만, 맥락이 불분명하거나 전체 프로세스를 진행하고 싶을 때 이 오케스트레이터가 트리거된다."
---

# Idea Workshop — 아이디어 오케스트레이터

아이디어의 전체 라이프사이클을 관리한다.  
Phase 1~2는 솔로로 진행하고, Phase 3에서 **기획팀 Agent Team**을 생성해 병렬 검증한다.

## 전체 흐름

```
Phase 1: 발산       Phase 2: 방향 탐색    Phase 3: 팀 검증        Phase 4: 문서화 → SDD
[brain-storm]  →  [idea-reframe]  →  [Agent Team 기획팀]  →  [기획서 → sdd]
  아이디어 확장     다각도 탐색          병렬 리서치 + 소통        product-brief.md
  (솔로)           (솔로)               (4명 팀 + 리뷰어)         (솔로)
```

---

## Phase 1: 발산 (솔로)

brain-storm 모드 원칙을 따른다:
- 비판하지 않는다. 키운다. 연결한다. 확장한다.
- 경험에서 씨앗을 찾고, 가지를 뻗고, 구체화한다.
- 아이디어가 구체화되면 Phase 2 전환을 제안한다.

**시작 조건**: 아이디어 자체가 없거나 막연한 경우

---

## Phase 2: 방향 탐색 (솔로)

idea-reframe 모드 원칙을 따른다:
- 씨앗을 분해하고, 고정점을 확인하고, 다중 렌즈로 리프레이밍한다.
- 판단하지 않는다. 방향만 제시한다.
- 사용자가 방향을 선택하면 Phase 3으로 전환한다.

**시작 조건**: 구체적인 아이디어가 있지만 방향이 확정되지 않은 경우

---

## Phase 3: 팀 검증 (Agent Team)

사용자가 방향을 선택하면 **기획팀을 생성**한다.

### 팀 생성

### 팀 생성

```
# 1. 팀 생성
TeamCreate(team_name: "idea-{feature-slug}", description: "{아이디어 한줄 요약}")

# 2. 조사 태스크 4개 등록
TaskCreate(title: "시장 조사", description: "시장 규모, 경쟁사, 트렌드 분석 후 docs/research/market-research.md 저장")
TaskCreate(title: "사용자 조사", description: "페르소나, 페인포인트, JTBD 분석 후 docs/research/user-research.md 저장")
TaskCreate(title: "기술 타당성", description: "기술 스택, 공수, 인프라 비용 분석 후 docs/research/feasibility.md 저장")
TaskCreate(title: "비즈니스 모델", description: "수익 모델, 유닛 이코노믹스 설계 후 docs/research/business-model.md 저장")

# 3. 4명 팀원 스폰 (각자 태스크 자체 선택)
Agent(team_name: "idea-{feature-slug}", name: "market-researcher",   subagent_type: "idea-market-researcher",   prompt: "{아이디어 요약 + 선택 방향}")
Agent(team_name: "idea-{feature-slug}", name: "user-researcher",     subagent_type: "idea-user-researcher",     prompt: "{아이디어 요약 + 선택 방향}")
Agent(team_name: "idea-{feature-slug}", name: "feasibility-checker", subagent_type: "idea-feasibility-checker", prompt: "{아이디어 요약 + 선택 방향}")
Agent(team_name: "idea-{feature-slug}", name: "biz-model-designer",  subagent_type: "idea-biz-model-designer",  prompt: "{아이디어 요약 + 선택 방향}")
```

### 팀 작업 방식

- 4명이 **병렬로** 각자 태스크 선택 후 조사
- 팀원 간 **직접 소통** 가능 — `~/.claude/teams/idea-{slug}/config.json`에서 팀원 이름 확인 후 SendMessage
- 각 팀원은 `docs/research/` 아래 자신의 파일을 저장
- 완료 시 리더에게 유휴 알림 자동 전송

### 리뷰어 디스패치

4명 모두 유휴 상태(완료) 확인 후:

```
Agent(
  team_name: "idea-{feature-slug}",
  name: "idea-reviewer",
  subagent_type: "idea-reviewer",
  prompt: "docs/research/ 아래 4개 파일이 준비되어 있다. 정합성 검증 후 docs/product-brief.md 작성."
)
```

idea-reviewer는:
1. 4개 파일 읽고 정합성 검증
2. Critical 이슈 발견 시 **직접 해당 팀원에게** SendMessage로 수정 요청
3. 모든 이슈 해소 후 `docs/product-brief.md` 작성
4. 완료 시 리더에게 보고

### 팀 정리

idea-reviewer 완료 보고 수신 후 팀원들에게 종료 요청:

```
각 팀원에게 SendMessage(message: {type: "shutdown_request"})
모든 팀원 종료 확인 후 TeamDelete
```

---

## Phase 4: 문서화 (솔로)

팀 정리 후 리더가 마무리한다:

1. `docs/product-brief.md` 내용을 사용자에게 요약 보고
2. SDD 전환 안내:
   ```
   기획서가 완성되었습니다.
   구현을 시작하려면 /sdd 로 스펙을 작성하고 개발을 시작할 수 있어요.
   ```

---

## 단계 판단 기준

사용자의 첫 메시지로 어느 Phase에서 시작할지 판단한다:

| 상황 | 시작 Phase |
|------|-----------|
| 아이디어 없음 / 막연함 | Phase 1 (brain-storm) |
| 아이디어 있음, 방향 미확정 | Phase 2 (idea-reframe) |
| 방향 확정, 검증 요청 | Phase 3 (팀 검증) |
| 검증 완료, 문서화 요청 | Phase 4 (문서화) |

---

## 명시적 전환 명령

사용자가 직접 전환 요청 시 자동 판단보다 우선한다:

- "브레인스토밍 모드로" / "아이디어 더 발산하자" → Phase 1
- "다른 각도로 보자" / "리프레이밍해줘" → Phase 2
- "검증해줘" / "팀 불러줘" / "리서치 시작하자" → Phase 3
- "정리해줘" / "기획서 만들어줘" → Phase 4

---

## 진행률 표시 (cmux)

```bash
# Phase 1
cmux set-status idea "브레인스토밍" --icon "lightbulb" 2>/dev/null || true

# Phase 2
cmux set-status idea "리프레이밍" --icon "arrow.triangle.2.circlepath" 2>/dev/null || true

# Phase 3 - 팀 생성
cmux set-status idea "기획팀 소집 중" --icon "person.3" 2>/dev/null || true

# Phase 3 - 리서치 중
cmux set-status idea "팀 리서치 중" --icon "magnifyingglass" --color "#FF9800" 2>/dev/null || true

# Phase 3 - 리뷰 중
cmux set-status idea "기획서 작성 중" --icon "doc.text" --color "#2196F3" 2>/dev/null || true

# Phase 4 - 완료
cmux set-status idea "기획 완료" --icon "checkmark.circle" --color "#4CAF50" 2>/dev/null || true

# sdd 전환
cmux clear-status idea 2>/dev/null || true
```

---

## 응답 스타일

- 한국어로 응답한다
- Phase별 톤 구분:
  - Phase 1: 호기심 있고 에너지 있는 톤
  - Phase 2: 탐색적이고 열린 톤
  - Phase 3: 팀을 소집하는 리더 톤 — 간결하게 팀 구성과 진행 상황 브리핑
  - Phase 4: 간결하고 구조적인 톤
- Phase 전환 시 이유를 한 문장으로 설명한다
