# HANDOFF: Moon Harness — AI 에이전트 하네스 플러그인

> 이 문서는 새로운 에이전트가 컨텍스트 없이 이 파일만 읽고 바로 작업을 이어갈 수 있도록 작성되었다.

## 프로젝트 한줄 요약

아이디어에서 배포까지 AI 에이전트의 전체 개발 라이프사이클을 구조화하는 하네스 플러그인. ECC/gstack 분석을 기반으로 "더 적게, 더 단단하게" 설계. 10개 스킬 + 22개 SDD 에이전트 + 3개 보안 훅.

## 현재 상태

| 항목 | 상태 |
|------|------|
| 아이디어 파이프라인 | **완료** — brain-storm → idea-reframe ←→ deep-idea (이터레이션 루프) |
| idea-reframe 스킬 | **완료** — 신규 생성, eval 1회 실행 완료 (with/without 비교) |
| deep-idea 구조 변경 | **완료** — 리서치 에이전트 3개(haiku) + 이터레이션 루프 + 졸업/탈출 조건 |
| idea-workshop 라우팅 | **완료** — 3단계 라우팅 (brain-storm/idea-reframe/deep-idea) |
| 실수 학습 시스템 | **완료** — 3계층 (CLAUDE.md 포인터 + docs/pitfalls.md + 훅 추출) |
| 보안 기본선 | **완료** — Hook S1(시크릿), S2(위험명령), S3(민감파일) + security-baseline.md |
| SDD Phase 4 | **완료** — Review → Ship → Verify (선택적) |
| SDD develop 평가 | **완료** — architect-reviewer가 develop 문서 품질 검증 (#7-#11) |
| SDD Stitch 연동 | **완료** — sdd-ui-designer에 Stitch MCP 연동 (ASCII 폴백) |
| develop 폴더 구조 | **완료** — develop 템플릿에 폴더 구조 섹션 추가 |
| 모델 최적화 | **완료** — opus 4개, sonnet 14개, haiku 4개 분배 |
| 패키징 | **완료** — setup.sh (--host claude/codex, --link/--copy) |
| 멀티 호스트 | **완료** — Claude Code + Codex, host-configs.md |
| 플러그인 레포 | **완료** — ~/Workspace/moon-harness/, 커밋 6개 |
| 멀티 에이전트 설계 | **분석 완료, 구현 미시작** — ECC/gstack/CC 네이티브 팀 심층 분석 완료 |

## 핵심 문서 위치

| 문서 | 경로 | 용도 |
|------|------|------|
| 플러그인 레포 | `~/Workspace/moon-harness/` | 배포 가능한 플러그인 전체 |
| README | `~/Workspace/moon-harness/README.md` | 설치 가이드 + 소개 |
| setup.sh | `~/Workspace/moon-harness/setup.sh` | 30초 설치 스크립트 |
| SDD SKILL.md | `~/Workspace/moon-harness/skills/sdd/SKILL.md` | Phase 1-4 전체 워크플로우 |
| harness SKILL.md | `~/Workspace/moon-harness/skills/harness/SKILL.md` | 환경 구성 + 12원칙 + 훅 정의 |
| 보안 기준 | `~/Workspace/moon-harness/skills/harness/references/security-baseline.md` | 20개 규칙 + 3 훅 |
| 호스트 설정 | `~/Workspace/moon-harness/skills/harness/references/host-configs.md` | Claude/Codex 변환 규칙 |
| 프로젝트 메모리 | `~/.claude/projects/-Users-moon--claude-skills/memory/project_harness_plugin.md` | 설계 결정 이력 |
| 원본 스킬 백업 | `~/.claude/skills-backup/` | setup.sh 전환 전 원본 |
| 원본 에이전트 백업 | `~/.claude/agents-backup/` | setup.sh 전환 전 원본 |

다음 에이전트는 **플러그인 레포(~/Workspace/moon-harness/)와 프로젝트 메모리**를 읽으면 충분하다.

## 완료된 작업

### 1. ECC/gstack 심층 분석 + 비판적 평가
- 6개 서브에이전트로 두 레포의 모든 구성요소를 분석
- 비판가 vs 옹호자 변증법적 분석으로 "진짜 필요한 것" 도출
- 결론: "8-15개 스킬이 최적, 하드 게이트가 advisory보다 우위"
- 사용자 기존 강점 확인: SDD 하드 게이트, adversarial-review, Korean-first

### 2. 아이디어 파이프라인 재설계
- idea-reframe 신규 스킬 생성 (7개 렌즈: 역발상, 대상 전환, 인접 전이, 본질 추출, 시장 틈새, 시간축 변경, 관계 재정의)
- deep-idea에 리서치 에이전트 3개(haiku) 추가 — 사용자가 도메인 전문가가 아니어도 데이터 기반 대화 가능
- idea-reframe ←→ deep-idea 이터레이션 루프 (니트픽 수렴 = 졸업, 5회 초과 = 탈출)
- 사용자 결정: "deep-idea에 멀티 에이전트가 필요하다" (도메인 지식 격차 보완)
- 사용자 결정: "brain-storm은 단일 에이전트 유지" (1:1 대화가 본질)

### 3. 실수 학습 시스템
- ECC(5단계 에스컬레이션), gstack(/learn + /retro), 외부 연구(General Knowledge Command, RLHF Feedback Loop) 분석
- 사용자 결정: "memory가 아닌 CLAUDE.md/docs/에 기록" (프로젝트 귀속, 자동 로딩, 팀 공유)
- 사용자 결정: "CLAUDE.md에 다 넣으면 비대해지니 분리" (포인터만 CLAUDE.md에, 본문은 docs/에)
- 3계층: CLAUDE.md 포인터 → docs/pitfalls.md + docs/lessons-learned.md → 훅(세션종료 추출 + 도메인별 주입)
- 3회 반복 실수 → CLAUDE.md 핵심 규칙 승격

### 4. 하네스 플러그인 구성
- 패키징: setup.sh (--host claude|codex, --link|--copy)
- 보안: 3개 훅 스크립트 (secret-detect.sh, dangerous-command.sh, sensitive-file.sh)
- SDD Phase 4: Review → Ship → Verify (선택적, 사용자 명시 요청 시)
- 멀티 호스트: host-configs.md (경로/도구명/프론트매터 변환 규칙)
- 모델 최적화: opus(설계) 4개, sonnet(구현) 14개, haiku(경량) 4개

### 5. SDD 개선
- develop 문서 평가 단계 추가 (architect-reviewer 역할 확장, 검증 항목 #7-#11)
- develop 템플릿에 폴더 구조 섹션 추가 ((NEW)/(MODIFY) 마커)
- Stitch MCP 연동 (sdd-ui-designer가 실제 시각 디자인 생성)
- 사용자 결정: "DDD 등 특정 아키텍처를 강제하지 않는다" (기존 프로젝트 컨벤션 따름)

### 6. 플러그인 레포 생성 + 배포 테스트
- ~/Workspace/moon-harness/ 레포 초기화
- 기존 ~/.claude/skills/ 원본을 백업 후 심링크로 전환
- setup.sh 실행 테스트 완료 (10 skills + 22 agents + 3 hooks)

### 7. 멀티 에이전트 심층 분석 (구현은 미시작)
- Claude Code 네이티브 팀: 태스크 리스트, 직접 메시지, 팀메이트별 모델, 훅(TeammateIdle/TaskCreated/TaskCompleted)
- gstack: 파일시스템 JSONL 큐, 탭별 에이전트 격리, worktree 병렬 스프린트, /freeze 범위 잠금
- ECC: dmux-workflows (tmux pane 병렬), SHARED_TASK_NOTES.md, De-sloppify 패턴, Ralphinho DAG, 루프 오퍼레이터

## 미완료 작업

### 즉시 필요
1. **멀티 에이전트 모드 설계 + 구현** — 분석 완료, 구현 미시작
   - SDD Phase 3 태스크를 팀메이트에 분배
   - worktree 격리 + /freeze 범위 잠금
   - SHARED_TASK_NOTES.md 패턴 도입
   - TeammateIdle/TaskCompleted 훅 활용
   
2. **실제 프로젝트에서 전체 플로우 테스트** — 아직 미실행
   - "가계부 앱" 시나리오로 idea-workshop → sdd Phase 1-4 전체 관통 테스트
   - 실수 학습 훅 동작 확인
   - 보안 훅 동작 확인

### 후속 작업
3. **settings.json에 보안 훅 등록** — setup.sh가 안내만 출력, 실제 등록은 수동
4. **GitHub에 push** — 레포는 로컬에만 존재
5. **skill description 최적화** — skill-creator의 트리거 최적화 루프 미실행
6. **ECC 참고 개선** — instincts 시스템(확신도 YAML), continuous learning v2 등 향후 참고

## 실패하거나 주의가 필요한 점

### 서브에이전트 파일 쓰기 권한 문제
- **문제**: idea-reframe eval 시 서브에이전트가 파일 쓰기 거부됨 (mode: auto, bypassPermissions 모두 실패)
- **원인**: 사용자 settings.json의 permissions가 서브에이전트에 제대로 상속되지 않음
- **대응**: eval은 직접 작성으로 우회. skill-creator의 eval 프로세스를 사용할 때 이 제약을 인지해야 함

### 원본 스킬 백업 존재
- **문제**: ~/.claude/skills-backup/과 ~/.claude/agents-backup/에 원본이 있음
- **대응**: 플러그인이 안정화되면 백업 삭제 가능. 문제 발생 시 복구용으로 유지.

### CRLF 경고
- **문제**: git commit 시 "LF will be replaced by CRLF" 경고 반복
- **원인**: macOS + git 설정 불일치
- **대응**: 기능에는 영향 없으나, .gitattributes로 해결 가능

## 환경 정보

```
OS: macOS Darwin 25.3.0
Model: Claude Opus 4.6 (1M context)
Claude Code: v2.1.92
프로젝트 경로: /Users/moon/Workspace/moon-harness
스킬 경로: /Users/moon/.claude/skills/ (심링크 → 레포)
에이전트 경로: /Users/moon/.claude/agents/ (심링크 → 레포)
훅 경로: /Users/moon/.claude/hooks/moon-harness/ (심링크 → 레포)
teammateMode: tmux
CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS: 1
```

## 다음 에이전트가 해야 할 일

1. **이 파일을 읽는다** (지금 하고 있는 것)
2. **프로젝트 메모리를 읽는다** (`~/.claude/projects/-Users-moon--claude-skills/memory/project_harness_plugin.md`)
3. **멀티 에이전트 모드를 설계하고 구현한다** — 위 "즉시 필요 #1" 참고
   - Claude Code 네이티브 팀 기능 활용 (이미 활성화됨)
   - SDD Phase 3 태스크 병렬 실행
   - worktree 격리 + SHARED_TASK_NOTES.md 패턴
4. **실제 프로젝트에서 전체 플로우를 테스트한다**
5. **커밋하고 GitHub에 push한다**
