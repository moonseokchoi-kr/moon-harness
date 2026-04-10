---
name: harness
description: "프로젝트에 에이전트 친화적 환경(하네스)을 구성하고 자동 유지 시스템을 설치하는 스킬. 새 프로젝트 시작, CLAUDE.md 정리, 아키텍처 규칙 강제, 문서 구조 관리, 코드 품질 유지가 필요할 때 사용한다. 'harness', '하네스', '환경 구성', '프로젝트 셋업', '문서 정리', '아키텍처 검증', '품질 점검' 같은 맥락에서 트리거한다."
---

# Harness Engineering

에이전트가 잘 일할 수 있는 환경을 구성하고, hook으로 자동 유지하는 시스템.

**핵심 철학:** 에이전트가 어려움을 겪으면 "더 분발"이 아니라 환경에 뭐가 빠졌는지 찾아서 추가한다.

## 모드

| 명령 | 용도 |
|------|------|
| `/harness` | 초기 구성 + 유지 시스템 설치 |
| `/harness audit` | 현재 하네스 건강도 점검 |

---

## `/harness` — 초기 구성

### Step 1: 프로젝트 분석

현재 프로젝트의 상태를 파악한다.

**수집 항목:**
1. **스택 감지**: package.json, Cargo.toml, pyproject.toml, go.mod 등으로 기술 스택 판별
2. **디렉터리 구조**: `src/`, `lib/`, `app/` 등의 최상위 구조 + 2단계 깊이까지 스캔
3. **기존 CLAUDE.md**: 줄 수, 목차형인지 백과사전형인지, docs/ 참조 여부
4. **기존 docs/**: 이미 구조화된 문서가 있는지
5. **기존 hooks**: `.claude/settings.json`에 이미 등록된 hook 확인
6. **아키텍처 패턴**: 디렉터리 이름에서 레이어 구조 추론 (commands→services→models, routes→controllers→models 등)

**분석 결과를 사용자에게 요약 보고하고 확인받은 후 다음 단계로 진행한다.**

### Step 2: docs/ 구조 생성

프로젝트에 `docs/` 가 없으면 scaffolding한다. 이미 SDD 등으로 docs/가 있으면 **누락된 부분만 추가**한다.

```
docs/
├── architecture.md        # 아키텍처 맵 (레이어, 의존성 방향, 핵심 모듈)
├── quality-score.md       # 도메인/레이어별 품질 등급 (A~F)
├── tech-debt.md           # 알려진 기술 부채 목록 + 우선순위
├── pitfalls.md            # 프로젝트에서 발견된 함정/실수 기록
├── lessons-learned.md     # 일반화된 교훈 (패턴, 모범 사례)
├── design-docs/           # 설계 문서 (기존 SDD 구조와 공존)
│   └── index.md
├── exec-plans/            # 실행 계획
│   ├── active/
│   └── completed/
└── references/            # 외부 라이브러리 llms.txt, 디자인 시스템 등
```

**이미 있는 파일은 절대 덮어쓰지 않는다.** 누락된 것만 생성.

### Step 3: CLAUDE.md 목차화

CLAUDE.md가 150줄을 넘으면 목차형으로 리팩터링을 **제안**한다 (자동 수정하지 않음).

**목차형 CLAUDE.md 원칙:**
- 100줄 이하 유지
- 프로젝트 개요, 빌드 명령, 핵심 규칙만 직접 포함
- 나머지는 `docs/`로 위임하고 포인터만 남김
- 예: `아키텍처 상세: docs/architecture.md 참조`

**실수 학습 포인터 (반드시 포함):**
```markdown
# Known Pitfalls
이 프로젝트에서 발견된 함정 기록: docs/pitfalls.md
새로운 실수 발견 시 해당 파일의 관련 섹션에 추가할 것.
작업 전 관련 도메인의 pitfalls를 확인할 것.

# Lessons Learned
일반화된 교훈 기록: docs/lessons-learned.md
```
이 포인터는 매 세션 자동 로딩되어, AI가 관련 작업 시 pitfalls.md를 참조하도록 유도한다.

### Step 4: Hook 스크립트 생성 + 등록

프로젝트의 `.claude/hooks/harness/` 디렉터리에 hook 스크립트를 생성하고, `.claude/settings.json`에 등록한다.

**중요:** 기존 settings.json의 다른 hook을 절대 건드리지 않는다. harness hook만 **추가**한다.

#### 설치할 Hook 목록

##### Hook 1: CLAUDE.md 비대화 감지

- **이벤트:** `PostToolUse`
- **매처:** `Edit`
- **조건:** CLAUDE.md 파일이 편집된 경우만
- **동작:** 줄 수가 임계값(기본 150줄)을 넘으면 exit 2로 경고
- **에러 메시지 (= 에이전트 프롬프트):**
  ```
  CLAUDE.md가 {N}줄로 임계값({THRESHOLD}줄)을 초과했습니다.
  상세 내용을 docs/ 하위 파일로 분리하고,
  CLAUDE.md에는 해당 문서의 경로 포인터만 남겨주세요.
  예: "아키텍처 상세: docs/architecture.md 참조"
  ```

##### Hook 2: 아키텍처 의존성 검증

- **이벤트:** `PostToolUse`
- **매처:** `Edit|Write`
- **동작:** 변경된 파일의 import/use 문을 검사하여 금지된 의존성 방향 감지
- **프로젝트별 맞춤:** Step 1에서 감지한 아키텍처 레이어 기반으로 규칙 생성
- **에러 메시지 예시:**
  ```
  아키텍처 위반: src-tauri/src/commands/fs.rs에서 models를 거치지 않고
  외부 크레이트를 직접 사용합니다.
  commands/ 레이어는 services/만 호출해야 합니다.
  의존성 방향: commands → services → models
  ```

##### Hook 3: 문서-코드 동기화 알림

- **이벤트:** `Stop`
- **타입:** `prompt` (Haiku로 경량 판단)
- **프롬프트:**
  ```
  이번 세션에서 수정된 파일 목록과 docs/ 문서를 비교하세요.
  구조적 변경(새 모듈, IPC 추가, 아키텍처 변경)이 있는데
  관련 문서가 갱신되지 않았으면 {"ok": false, "reason": "..."} 응답.
  단순 버그 수정이면 {"ok": true}.
  ```

##### Hook 4: 신규 파일 위치 검증

- **이벤트:** `PreToolUse`
- **매처:** `Write`
- **동작:** 새 파일 생성 시 프로젝트의 디렉터리 규칙에 맞는 위치인지 검증
- **에러 메시지 예시:**
  ```
  파일 위치 의심: src/utils/api.ts
  이 프로젝트에서 API 관련 로직은 src/lib/ 또는 src/services/에 위치합니다.
  의도한 위치가 맞는지 확인하세요.
  ```

##### Hook S1: 시크릿 탐지

- **이벤트:** `PreToolUse`
- **매처:** `Bash`
- **동작:** 커밋/쓰기 명령에 시크릿 패턴이 포함되어 있는지 스캔
- **탐지 패턴:** `sk-`, `ghp_`, `AKIA`, 하드코딩된 password/secret/token
- **에러 메시지:**
  ```
  ⚠️ 시크릿 패턴 감지: {패턴}
  API 키나 토큰을 코드에 직접 포함하지 마세요.
  환경변수(.env)를 사용하고, .env는 .gitignore에 포함하세요.
  ```

##### Hook S2: 위험 명령 확인

- **이벤트:** `PreToolUse`
- **매처:** `Bash`
- **동작:** `rm -rf`, `DROP TABLE`, `git push --force`, `curl|bash` 등 파괴적 명령 감지
- **안전 예외:** `rm -rf node_modules`, `rm -rf .next`, `rm -rf dist`, `rm -rf build`
- **에러 메시지:**
  ```
  ⚠️ 위험 명령 감지: {명령어}
  정말 실행하시겠습니까? 실행 전 영향 범위를 확인하세요.
  ```

##### Hook S3: 민감 파일 보호

- **이벤트:** `PreToolUse`
- **매처:** `Edit|Write`
- **동작:** `.env`, `*.pem`, `*.key`, `credentials.json` 등 민감 파일 수정 시 경고
- **에러 메시지:**
  ```
  ⚠️ 민감 파일 수정 시도: {파일명}
  이 파일에 시크릿이 포함되어 있을 수 있습니다.
  수정이 필요하다면 사용자에게 직접 수정을 요청하세요.
  ```

상세 보안 규칙은 `references/security-baseline.md` 참조.

##### Hook 5: 세션 종료 시 학습 추출

- **이벤트:** `Stop`
- **타입:** `prompt` (Haiku로 경량 판단)
- **프롬프트:**
  ```
  이번 세션을 검토하세요.

  1. 실수/함정(pitfall)이 발견되었나?
     - 사용자가 수정을 요청한 부분
     - 예상과 다르게 동작한 코드
     - 잘못된 가정이나 환각
  
  2. 일반화할 수 있는 교훈(lesson)이 있나?
     - 이 프로젝트에서 반복될 수 있는 패턴
     - 작업 순서나 접근법에 대한 발견

  발견된 것이 있으면:
  {
    "ok": false,
    "pitfalls": [{"domain": "카테고리", "description": "구체적 설명", "date": "YYYY-MM-DD"}],
    "lessons": [{"description": "일반화된 교훈", "date": "YYYY-MM-DD"}]
  }
  
  발견된 것이 없으면: {"ok": true}
  ```
- **후처리:** ok가 false이면 AI가 docs/pitfalls.md와 docs/lessons-learned.md에 항목을 추가.
  이미 동일한 내용이 있으면 중복 추가하지 않는다.

##### Hook 6: 관련 pitfall 선택적 주입 (선택사항)

- **이벤트:** `PreToolUse`
- **매처:** `Edit|Write`
- **동작:** 편집 대상 파일의 도메인을 감지하여, docs/pitfalls.md에서 해당 도메인 섹션만 추출해 stderr로 출력
- **예시:** `src/db/` 파일 편집 시 → pitfalls.md의 `## DB` 섹션만 주입
- **구현:**
  ```bash
  #!/bin/bash
  INPUT=$(cat)
  FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
  PITFALLS="$CLAUDE_PROJECT_DIR/docs/pitfalls.md"
  
  [ ! -f "$PITFALLS" ] && exit 0
  
  # 파일 경로에서 도메인 키워드 추출
  DOMAIN=""
  case "$FILE_PATH" in
    *db*|*database*|*migration*|*model*) DOMAIN="DB" ;;
    *api*|*endpoint*|*route*)            DOMAIN="API" ;;
    *auth*|*login*|*session*)            DOMAIN="Auth" ;;
    *test*|*spec*)                       DOMAIN="Test" ;;
  esac
  
  [ -z "$DOMAIN" ] && exit 0
  
  # 해당 섹션 추출 (## 헤더 기준)
  SECTION=$(sed -n "/^## $DOMAIN/,/^## /p" "$PITFALLS" | head -n -1)
  [ -z "$SECTION" ] && exit 0
  
  echo "⚠️ 관련 pitfall 참고:" >&2
  echo "$SECTION" >&2
  exit 0  # 경고만, 차단하지 않음
  ```

#### Hook 스크립트 생성 규칙

모든 스크립트는 다음 패턴을 따른다:

```bash
#!/bin/bash
# Harness Hook: {hook_name}
# 설치: /harness 스킬에 의해 자동 생성
# 수정 시 .claude/hooks/harness/ 내에서 직접 편집

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# ... 검증 로직 ...

# 위반 시: exit 2 + stderr에 수정 지침
echo "위반 내용 + 구체적 수정 방법" >&2
exit 2

# 통과 시: exit 0
exit 0
```

**핵심: 에러 메시지가 곧 에이전트 프롬프트다.** 무엇이 잘못되었고 어떻게 고쳐야 하는지 구체적으로 쓴다.

#### settings.json 등록 형식

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit",
        "hooks": [{
          "type": "command",
          "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/harness/check-claude-md-size.sh"
        }]
      },
      {
        "matcher": "Edit|Write",
        "hooks": [{
          "type": "command",
          "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/harness/check-architecture.sh"
        }]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Write",
        "hooks": [{
          "type": "command",
          "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/harness/check-file-location.sh"
        }]
      }
    ],
    "Stop": [
      {
        "hooks": [{
          "type": "prompt",
          "prompt": "이번 세션에서 코드에 구조적 변경이 있었는데 docs/ 문서가 갱신되지 않았다면 {\"ok\": false, \"reason\": \"갱신 필요한 문서 목록\"} 응답. 단순 수정이면 {\"ok\": true}.",
          "model": "haiku",
          "timeout": 30
        }]
      }
    ]
  }
}
```

### Step 5: 결과 보고

설치 완료 후 다음을 보고한다:
- 생성된 docs/ 파일 목록
- 등록된 hook 수 + 각 hook의 역할 한 줄 요약
- CLAUDE.md 현재 줄 수 + 목차화 필요 여부
- 다음 단계 제안 (예: architecture.md 작성, quality-score.md 초기 등급 설정)

---

## `/harness audit` — 건강도 점검

12개 하네스 원칙으로 프로젝트의 에이전트 친화도를 점수화한다.

### 진단 깊이

| 깊이 | 대상 원칙 | 용도 |
|------|----------|------|
| `quick` | P1, P3, P10 (핵심 3개) | 빠른 상태 확인 |
| `standard` (기본) | P1~P12 전체 | 정기 점검 |
| `deep` | 전체 + 코드 샘플링 검증 | 정밀 진단 |

### 12개 하네스 원칙

각 원칙은 0~10점으로 평가한다. 상세 기준은 `references/scoring-guide.md` 참조.

| 원칙 | 이름 | 핵심 질문 |
|------|------|----------|
| P1 | Agent Entry Point | CLAUDE.md가 명확한 진입점인가? |
| P2 | Map, Not Manual | 문서가 2단계 이내에 정보를 찾을 수 있는 지도인가? |
| P3 | Invariant Enforcement | 규칙이 도구(hook/lint/CI)로 자동 강제되는가? |
| P4 | Convention Over Configuration | 패턴 복제만으로 올바른 코드가 나오는가? |
| P5 | Progressive Disclosure | 정보가 3단계 계층으로 적절히 분배되는가? |
| P6 | Layered Architecture | 레이어 의존성이 단방향이고 도구로 강제되는가? |
| P7 | Garbage Collection | dead code, stale 문서가 주기적으로 정리되는가? |
| P8 | Observability | 에이전트가 자기 작업 결과를 빠르게 검증할 수 있는가? |
| P9 | Knowledge in Repo | 필수 지식이 repo 안에 있는가? (Slack/머릿속 아님) |
| P10 | Reproducibility | 동일 입력 → 동일 결과가 보장되는가? |
| P11 | Modularity | 한 모듈 수정의 영향 범위가 예측 가능한가? |
| P12 | Self-Documentation | 코드 자체가 의도와 동작을 설명하는가? |

### 4차원 집계 + 가중치

원칙들을 4개 차원으로 그룹화하여 종합 점수를 산출한다.

| 차원 | 가중치 | 포함 원칙 |
|------|--------|---------|
| A. Documentation & Navigation | 30% | P1, P2, P5, P12 |
| B. Enforcement & Consistency | 30% | P3, P4, P10 |
| C. Architecture & Knowledge | 20% | P6, P9, P11 |
| D. Operations & Maintenance | 20% | P7, P8 |

```
DimA = (P1 + P2 + P5 + P12) / 4
DimB = (P3 + P4 + P10) / 3
DimC = (P6 + P9 + P11) / 3
DimD = (P7 + P8) / 2
종합 = (DimA×0.3 + DimB×0.3 + DimC×0.2 + DimD×0.2) × 10
```

### 5단계 성숙도

| 등급 | 점수 | 의미 |
|------|------|------|
| L1 None | 0~19 | 에이전트 협업 고려 없음 |
| L2 Basic | 20~39 | 최소한의 문서화 |
| L3 Structured | 40~59 | 체계적 구조, 부분 자동화 |
| L4 Optimized | 60~79 | 높은 자동화, 낮은 drift |
| L5 Autonomous | 80~100 | 에이전트가 독립적으로 작업 가능 |

### 리포트 형식

```markdown
# Harness Audit Report — {프로젝트명}
날짜: {YYYY-MM-DD} | 깊이: standard | 성숙도: L4 Optimized

## 종합 점수: 72/100

### 차원별 점수
| 차원 | 점수 | 등급 |
|------|------|------|
| A. Documentation & Navigation | 7.5 | L4 |
| B. Enforcement & Consistency | 6.8 | L4 |
| C. Architecture & Knowledge | 7.2 | L4 |
| D. Operations & Maintenance | 5.5 | L3 |

### 원칙별 점수
| 원칙 | 점수 | 근거 |
|------|------|------|
| P1 Agent Entry Point | 8 | CLAUDE.md 존재, 빌드 명령 완비, docs/ 포인터 있음 |
| P2 Map, Not Manual | 7 | 목차형이나 일부 섹션 비대 (IPC 목록 90줄) |
| P3 Invariant Enforcement | 6 | clippy+tsc 있으나 아키텍처 규칙 미강제 |
| ... | ... | ... |

### 우선 개선 항목 (ROI 순)
1. [P3] hook으로 아키텍처 의존성 검증 추가 → 예상 +2점
2. [P7] tech-debt.md 생성 + 정리 프로세스 구축 → 예상 +3점
3. [P2] IPC 커맨드 목록을 docs/로 분리 → 예상 +1점
```

### Evidence-First 원칙

모든 점수에는 **근거(evidence)**를 반드시 첨부한다:
- 파일 경로 + 줄 수 ("CLAUDE.md:132줄")
- 실제 코드 패턴 ("commands/fs.rs에서 services를 거치지 않고 직접 IO")
- 수치 ("30일 이상 미갱신 문서 3개")

근거 없는 점수는 부여하지 않는다.

### 자동 수정 제안

audit에서 발견한 문제 중 자동 수정 가능한 항목은 사용자에게 제안한다:
- "architecture.md를 현재 코드 기준으로 갱신할까요?"
- "tech-debt.md의 완료된 항목을 정리할까요?"
- "CLAUDE.md의 IPC 커맨드 목록을 docs/로 분리할까요?"
- "harness hook이 미설치 — `/harness`로 설치할까요?"

**사용자 승인 없이 자동 수정하지 않는다.**

---

## 실수 학습 파일 형식

### docs/pitfalls.md

도메인별 섹션으로 구분한다. 각 항목은 날짜 + 구체적 설명.

```markdown
# Known Pitfalls

이 프로젝트에서 발견된 함정과 실수 기록.
작업 전 관련 도메인의 항목을 확인할 것.

## DB
- [2026-04-05] PostgreSQL pool 미사용 시 커넥션 고갈 발생. pgBouncer 또는 pool 설정 필수.
- [2026-04-06] migration 파일에서 DROP COLUMN은 되돌릴 수 없음. 항상 별도 배포로 분리.

## API
- [2026-04-05] 오픈뱅킹 API 일 500회 제한. 개발 중 실제 호출 대신 mock 사용할 것.

## Auth
- [2026-04-07] JWT 토큰 만료 시간이 서버 시간대에 의존. UTC로 통일할 것.

## Test
- [2026-04-05] CI에서 테스트 순서가 로컬과 다름. 테스트 간 상태 공유 금지.
```

### docs/lessons-learned.md

일반화된 교훈. 날짜 + 교훈 + 배경(선택).

```markdown
# Lessons Learned

이 프로젝트에서 학습한 일반화 가능한 교훈.

## 개발 프로세스
- [2026-04-05] 테스트 없이 리팩토링하면 반드시 깨진다. 리팩토링 전 커버리지 확인 필수.
- [2026-04-06] API 응답 스키마 변경 시 타입 정의부터 수정해야 영향 범위가 보인다.

## 아키텍처
- [2026-04-07] 서비스 레이어를 건너뛰고 컨트롤러에서 직접 DB 접근하면 나중에 무조건 분리해야 한다.

## 도구
- [2026-04-05] yt-dlp이 없으면 YouTube 자막 추출 불가. WebSearch로 우회 가능.
```

**핵심 규칙:**
- 같은 실수가 3회 이상 기록되면 → CLAUDE.md의 핵심 규칙으로 승격 검토
- 6개월 이상 된 항목 중 더 이상 관련 없는 것은 정리 가능 (삭제가 아닌 아카이브)
- pitfalls는 "하지 마라" (구체적), lessons는 "이렇게 해라" (일반화)

---

## 아키텍처 규칙 파일

프로젝트별 아키텍처 규칙은 JSON으로 관리한다.

`.claude/hooks/harness/architecture-rules.json`:

```json
{
  "layers": {
    "commands": { "can_import": ["services", "models"], "description": "IPC 핸들러" },
    "services": { "can_import": ["models"], "description": "비즈니스 로직" },
    "models": { "can_import": [], "description": "데이터 모델" }
  },
  "directory_rules": [
    { "pattern": "src/components/**", "allowed_imports_from": ["src/stores", "src/lib"] },
    { "pattern": "src/stores/**", "allowed_imports_from": ["src/lib"] }
  ],
  "file_location_rules": [
    { "pattern": "*.store.ts", "expected_dir": "src/stores/" },
    { "pattern": "*.test.ts", "expected_dir": "**/__tests__/" }
  ]
}
```

이 파일은 Step 1의 프로젝트 분석 결과로 자동 생성되며, 사용자가 직접 편집할 수 있다.

---

## 하네스 린트 vs 언어 린트

이 스킬이 설치하는 hook은 **언어 린트(eslint, clippy, pylint)와 다르다.**

| | 하네스 린트 | 언어 린트 |
|---|---|---|
| 대상 | 아키텍처, 구조, 문서 | 문법, 코드 스타일 |
| 언어 의존 | X (파일 경로, 줄 수, import 패턴) | O |
| 목적 | 에이전트가 올바른 판단을 하도록 환경 보장 | 코드 품질 보장 |
| 실행 | Claude Code hook | CI/빌드 |

하네스 린트는 기존 언어 린트를 **대체하지 않고 보완**한다.

---

## 기존 도구와의 관계

| 도구 | 관계 |
|------|------|
| **SDD** | docs/ 구조를 공유. SDD의 spec/develop/task 구조는 유지하고, harness는 architecture.md, quality-score.md, tech-debt.md를 추가 |
| **simplify** | harness audit에서 코드 품질 문제 발견 시 simplify 스킬 사용 제안 가능 |
| **impeccable** | UI 관련 품질은 impeccable이 담당. harness는 구조/아키텍처 수준만 |

---

## 참고

- `references/harness-principles.md` — OpenAI Harness Engineering 원칙 상세
