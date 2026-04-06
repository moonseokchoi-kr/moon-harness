# Moon Harness

아이디어에서 배포까지, AI 에이전트의 전체 개발 라이프사이클을 구조화하는 하네스 플러그인.

## 30초 설치

```bash
git clone https://github.com/your-username/moon-harness.git ~/.claude/skills/moon-harness
cd ~/.claude/skills/moon-harness
./setup.sh
```

### Codex 사용자

```bash
./setup.sh --host codex
```

## 파이프라인

```
아이디어                          구현                        배포
─────────────────────────    ──────────────    ──────────────────────
brain-storm                  SDD Phase 1       Phase 4-1: Review
    ↓                            ↓                 ↓
idea-reframe ←→ deep-idea   Phase 2 → 3       Phase 4-2: Ship
    (이터레이션)                                     ↓
                                              Phase 4-3: Verify
```

### 아이디어 단계

| 스킬 | 역할 |
|------|------|
| `/brain-storm` | 씨앗 없음 → 아이디어 발산 |
| `/idea-reframe` | 아이디어를 다중 렌즈로 리프레이밍 |
| `/deep-idea` | 리서치 기반 냉정한 검증 |
| `/idea-workshop` | 위 3개를 오케스트레이션 |

`idea-reframe ↔ deep-idea` 사이에 이터레이션 루프가 있다. 니트픽이 수렴하면 졸업.

### 구현 단계

| 스킬 | 역할 |
|------|------|
| `/sdd` | Spec-Driven Development (3+1 Phase, 하드 게이트) |
| `/adversarial-review` | 리뷰 3회 실패 시 에스컬레이션 |
| `/git-worktree` | 격리된 feature 브랜치 |

### 환경 관리

| 스킬 | 역할 |
|------|------|
| `/harness` | 프로젝트 환경 구성 + 훅 설치 |
| `/harness audit` | 12원칙 기반 하네스 건강도 점검 (L1~L5) |
| `/handoff` | 세션 컨텍스트 보존 |

## 핵심 기능

### 실수 학습 시스템

AI가 실수하면 자동으로 기록하고, 다음 세션에서 반복하지 않는다.

```
Layer 1: CLAUDE.md — 포인터 ("pitfalls는 docs/pitfalls.md 참고")
Layer 2: docs/pitfalls.md + docs/lessons-learned.md — 전체 기록
Layer 3: 훅 — 세션 종료 시 자동 추출 + 관련 작업 시 선택적 주입
```

같은 실수 3회 이상 → CLAUDE.md 핵심 규칙으로 승격.

### 보안 기본선

| 훅 | 역할 |
|----|------|
| S1: 시크릿 탐지 | API 키, 토큰 패턴 감지 |
| S2: 위험 명령 확인 | rm -rf, DROP TABLE, force push 경고 |
| S3: 민감 파일 보호 | .env, .pem, credentials.json 수정 차단 |

### 하네스 12원칙

P1 Agent Entry Point ~ P12 Self-Documentation까지 12개 원칙으로 프로젝트의 에이전트 친화도를 0~100점으로 측정. `/harness audit`으로 실행.

## 설계 철학

> "더 적게 만들되 더 단단하게"

- 10개 코어 스킬 (156개가 아닌)
- 20개 보안 규칙 (1282개가 아닌)
- 2개 호스트 (8개가 아닌)
- 하드 게이트 (advisory 리뷰가 아닌)

ECC와 gstack을 분석한 결과, 스킬 수보다 **각 스킬의 강도**가 더 중요하다는 결론.

## 멀티 호스트

| 호스트 | 설치 명령 |
|--------|----------|
| Claude Code | `./setup.sh` |
| Codex | `./setup.sh --host codex` |

추가 호스트는 요구 시 확장.

## License

MIT
