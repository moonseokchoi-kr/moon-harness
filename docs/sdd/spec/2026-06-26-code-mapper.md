# code-mapper Spec

## 개요

- **한줄 요약:** 구현/문서 작업 전에 건드릴 심볼의 실제 호출·사용 관계를 고정 포맷 **구조적 컨텍스트**로 제공하는 도구 (Aider repo map 류). 목적은 이름 기반 가짜 확신 감소.
- **타겟 사용자:** (1) **버그 수정/근본 원인 분석 워크플로우** — 잘못된 심볼 이해가 엉뚱한 수정으로 직결되는 최고 가치 소비자. (2) SDD 파이프라인 에이전트(sdd-implementer 등). (3) ad-hoc 문서/구현 작업 개발자. 공통 진입점 = `/code-mapper`.
- **핵심 가치:** grep(이름 매칭)만으로 코드를 파악하면 "이름이 맞으니 내가 원하는 동작이겠지"라는 가짜 확신이 생긴다. code-mapper는 작업 직전에 실제 호출/사용 관계를 *컨텍스트로 제공*해 이 확신을 근거 있는 이해로 바꾼다. **게이트가 아니다** — 산출물 준수를 강제하거나 검증하지 않고, 더 나은 컨텍스트를 적시에 줄 뿐이다. (근거: 업계는 코드맵을 휘발성 컨텍스트로 제공하는 패턴만 채택했고, 영속 계약·검증은 스테일·과잉제약 비용 때문에 회피한다.)

---

## 플랫폼 / 스택

| 항목 | 값 |
|------|----|
| 모드 | **SIMPLE** — UI 없음, REST API 계약 없음 |
| SIMPLE 판정 근거 | 산출물은 마크다운 스킬 파일 + 에이전트 프롬프트 단락. 실행 코드는 결정적 로직(가용성 분기)에 한정 |
| 신규 산출물 | `skills/code-mapper/SKILL.md` (절차 SSOT), 기존 SDD 에이전트 프롬프트에 최소 침습 단락 주입 |
| 결정적 로직 | Python stdlib-only (`hooks/lib/` 또는 `skills/code-mapper/` 하위). pytest 검증 |
| 판단 로직 | 스킬/에이전트 프롬프트 — 수동 리뷰, harness-improvement-critic 게이트 |
| 코드 탐색 도구 | codegraph MCP (옵셔널, 없으면 Glob + 구조적 grep 폴백) |
| 하네스 규칙 | 범용 — 레포 특화 하드코딩 금지. 하네스 티어 변경 = 사람 승인 게이트 필요 |

---

## 사용자 요구사항 원문 → 기능 매핑

| # | 사용자 요구 원문 | 기능 |
|---|----------------|------|
| R1 | "SDD 에이전트가 grep(이름 기반)으로만 코드를 파악 → 가짜 확신으로 틀린 작업에 진입 → 원인 찾느라 시간 소비" | F1, F2 |
| R2 | "codegraph는 필수가 아니라 '있으면 쓰는 가속기'. 하네스는 범용이라 codegraph MCP 존재를 가정하면 안 됨. baseline은 grep/Glob 구조 탐색" | F3 |
| R3 | "가용성 판별 = MCP 프로브 (filesystem `.codegraph/` 디렉터리 체크 금지): codegraph가 순수 MCP 형태로 전환 중이라 로컬 인덱스 폴더가 없어도 서빙될 수 있음" | F4 |
| R4 | "3-상태: (a) MCP healthy → codegraph_context → codegraph_trace → codegraph_impact 사용 / (b) MCP 응답하나 'not initialized' → init 제안 또는 폴백 / (c) MCP 없음 → Glob + 구조적 grep 폴백" | F4, F5 |
| R5 | "고정 산출물 포맷 (코드맵): 진입점 → 실제 callers/callees → 호출경로(trace) → blast radius(영향범위) → 건드릴 파일 목록. 매번 같은 모양으로 산출" | F6 |
| R6 | "`skills/code-mapper/SKILL.md` = SSOT 절차 (사람이 `/code-mapper`로 직접 호출 가능 — ad-hoc 문서/구현 작업)" | F7 |
| R7 | "SDD 탐색/구현 에이전트엔 codegraph-awareness + '편집 전 실제 호출관계 검증' 규율 한 단락만 최소 침습 주입. 본체 절차는 스킬에 두고 포인터만. `sdd-implementer`는 protected에 가까우니 최소 침습 엄수" | F8 |
| R8 | "moon-harness의 agents/ + skills/ 전체에 codegraph 언급 0건. codegraph 가이드는 사용자 개인 ~/.claude/CLAUDE.md에만 있고 플러그인엔 안 실림. 그래서 SDD 런타임은 grep으로 떨어짐" | F8 |
| R9 | "결정적 로직(가용성 분기·산출물 포맷 강제 등)은 stdlib-only python 후보, 판단 로직(무엇이 영향범위인지 해석)은 프롬프트" | F4, F9 |

---

## 기능 요구사항

### F1: 가짜 확신 감소 — 작업 전 구조적 컨텍스트 제공

- WHEN 에이전트/사용자가 기존 심볼(함수·클래스·모듈)을 편집하거나 호출하려 할 때, THE SYSTEM SHALL 해당 심볼의 실제 callers/callees를 구조적 컨텍스트로 제공한다.
- WHEN 심볼을 이름 기반 탐색(grep/Glob)만으로 특정했을 때, THE SYSTEM SHALL 구조적 탐색(codegraph 또는 폴백 grep 패턴) 결과를 컨텍스트로 함께 제시해 이름 추측을 실제 관계로 보완할 수 있게 한다.
- **Acceptance:**
  - 코드맵 산출물이 callers/callees 실제 관계를 포함한다.
  - 산출물은 컨텍스트로 제공될 뿐, 준수 여부를 강제·검증·차단하지 않는다(게이트 아님).

### F2: 코드맵 생성 트리거

- WHEN 사용자가 `/code-mapper <심볼-또는-파일>` 를 호출할 때, THE SYSTEM SHALL 해당 심볼/파일에 대한 코드맵을 F6 포맷으로 산출해 컨텍스트로 제공한다.
- WHEN SDD 에이전트(sdd-implementer 등)가 낯선 기존 심볼 수정을 앞두고 있을 때, THE SYSTEM SHALL 코드맵을 구조적 컨텍스트로 확보할 수 있도록 안내한다(자기 판단으로 활용; 강제 게이트 아님).
- **Acceptance:**
  - `/code-mapper <심볼>` 호출 시 항상 F6 포맷의 코드맵이 반환된다.
  - SDD 에이전트 안내는 "컨텍스트 확보 권고"이며, 미수행 시 차단·실패 처리하지 않는다.

### F3: codegraph 옵셔널 — 범용 폴백 보장

- THE SYSTEM SHALL codegraph MCP가 없는 환경(다른 사용자·다른 레포)에서도 동일한 코드맵 포맷을 Glob + 구조적 grep으로 산출할 수 있어야 한다.
- THE SYSTEM SHALL 레포 특화 명령이나 경로를 스킬 절차에 하드코딩하지 않는다.
- **Acceptance:**
  - codegraph MCP가 없는 환경에서 `/code-mapper` 호출 시 폴백 절차로 코드맵이 산출된다.
  - 스킬 파일에 특정 레포 경로·명령이 하드코딩된 문자열이 없다.

### F4: MCP 가용성 3-상태 판별 (결정적 로직)

- WHEN code-mapper 절차가 시작될 때, THE SYSTEM SHALL **`codegraph_status`를 프로브 도구로 호출**하여 응답으로 다음 3-상태 중 하나로 분기한다:
  - **(a) MCP healthy**: `codegraph_status`가 인덱스 통계(노드/엣지 수, ready 등)를 반환 → codegraph_context → codegraph_trace → codegraph_impact 순서로 사용
  - **(b) MCP 응답하나 "not initialized"**: 응답 텍스트에 `not initialized`(또는 동등한 미초기화 신호)가 포함 → 사용자에게 `codegraph init -i` 실행을 제안하고 폴백(상태 c)으로 진행
  - **(c) MCP 없음**: codegraph 도구 자체가 미등록(tool not found / 연결 오류) → Glob + 구조적 grep 폴백으로 진행
- IF filesystem에 `.codegraph/` 디렉터리가 존재하는지 여부로 가용성을 판단하려 할 때, THEN THE SYSTEM SHALL 해당 판단 경로를 거부하고 `codegraph_status` 프로브 결과만을 사용한다. (근거: codegraph가 순수 MCP로 전환 중이라 로컬 인덱스 폴더 없이도 서빙될 수 있음 — filesystem 체크는 false negative를 낸다.)
- **Acceptance:**
  - 스킬 절차에 `.codegraph/` 디렉터리 체크 코드 또는 명령이 없다.
  - 프로브 도구가 `codegraph_status`로 명시되어 있고, 3-상태 분류 기준(통계 반환 / "not initialized" 포함 / 도구 미등록)이 결정적으로 문서화되어 있다.
  - 상태 (b)에서 사용자에게 init 제안 메시지가 출력된다.

### F5: 폴백 탐색 절차 (MCP 없음/초기화 안 됨)

- WHERE codegraph MCP가 가용하지 않을 때, THE SYSTEM SHALL 다음 순서로 구조적 grep 폴백을 실행한다:
  1. 대상 파일 확장자로 언어를 판정해 정의 패턴을 선택 (`.py`→`def/class`, `.ts/.js`→`function/class/=>`, 기타→일반 식별자 패턴). Glob으로 대상 심볼의 정의 파일 탐색.
  2. 정의 파일 기준으로 해당 심볼을 import/호출/상속하는 파일을 grep으로 수집 (callers 근사)
  3. 정의 파일 내에서 호출하는 외부 심볼 grep (callees 근사)
  4. 수집 결과를 F6 포맷에 "(grep 근사, codegraph 미사용)" 표시와 함께 기록
- THE SYSTEM SHALL callers/callees 수집 시 **실제 호출·import·상속·메서드 호출만** 집계하고, 주석·문자열 리터럴·타입 힌트 내 이름 일치는 제외한다(이름 기반 거짓 양성 억제 — code-mapper 정체성과 직결).
- **Acceptance:**
  - 폴백 결과에 "(grep 근사, codegraph 미사용)" 레이블이 포함된다.
  - callers/callees 근사 목록이 비어 있어도 포맷은 동일하게 출력된다.
  - 폴백 산출물에는 "근사값 — 개발자 확인 권장" 주의가 명시된다(폴백 정확도는 best-effort).

### F6: 코드맵 커버리지 체크리스트 (ephemeral)

> 이 "포맷"은 저장되는 문서 양식이 아니라, 매번 컨텍스트에 surface해야 할 **커버리지 항목 체크리스트**다. 빠뜨림(특히 callers/영향범위 미확인 = 원래 실패) 방지가 목적. 산출물은 ephemeral — 저장하지 않는다.

- THE SYSTEM SHALL 모든 호출 경로에서 다음 항목을 컨텍스트로 surface한다(아래는 권장 표현 형태이며, 핵심은 항목 누락 없음):

```markdown
## 코드맵: <심볼-또는-파일>

### 1. 진입점
- 심볼/파일명:
- 위치(파일:라인):
- 역할 한줄 요약:

### 2. Callers (이 심볼을 호출하는 곳)
| 호출자 | 파일:라인 | 호출 목적 |
|--------|-----------|-----------|
| ...    | ...       | ...       |

### 3. Callees (이 심볼이 호출하는 것)
| 피호출자 | 파일:라인 | 호출 목적 |
|---------|-----------|-----------|
| ...     | ...       | ...       |

### 4. 호출 경로 (Trace)
진입점 → [중간 심볼] → 최종 도달점
(codegraph_trace 결과 또는 grep 근사)

### 5. Blast Radius (영향범위)
이 심볼을 변경하면 영향 받는 파일/심볼 목록:
- ...

### 6. 건드릴 파일 (이번 작업 추정)
이번 작업에서 수정이 필요해 보이는 파일 (추정 — 컨텍스트일 뿐, 계약 아님):
- <파일경로> — 수정 이유

---
탐색 방법: codegraph (MCP healthy) | grep 근사 (codegraph 미사용)
```

- THE SYSTEM SHALL 포맷의 섹션 순서(1~6)와 레이블을 변경하지 않는다.
- THE SYSTEM SHALL 섹션 5(Blast Radius)와 섹션 6(건드릴 파일)을 다음과 같이 구분한다: **섹션 5 = 변경 시 영향받는 전체 범위**(codegraph_impact 결과 / 폴백은 callers + 직접 callees 파일), **섹션 6 = 이번 작업에서 수정해 보이는 파일 추정**(섹션 5의 서브셋, 컨텍스트일 뿐 계약 아님).
- IF 특정 섹션(예: Callers)에 해당 항목이 없을 때, THEN THE SYSTEM SHALL 해당 섹션을 "(없음)"으로 채우고 생략하지 않는다.
- **Acceptance:**
  - codegraph 사용 경로와 grep 폴백 경로 모두에서 섹션 1~6이 동일하게 출력된다.
  - "탐색 방법" 레이블이 항상 포함된다.
  - 섹션이 누락되거나 순서가 바뀐 산출물이 없다.

### F7: `/code-mapper` 수동 호출 스킬 (SSOT 절차)

- WHEN 사용자가 `/code-mapper <대상>` 을 실행할 때, THE SYSTEM SHALL `skills/code-mapper/SKILL.md`에 정의된 절차를 실행하고 F6 포맷의 코드맵을 반환한다.
- THE SYSTEM SHALL `skills/code-mapper/SKILL.md`가 code-mapper 절차의 단일 진실 공급원(SSOT)이어야 한다. 중복 절차를 다른 파일에 기술하지 않는다.
- WHERE 사용자 또는 다른 스킬(버그 수정 워크플로우 등)이 SDD 파이프라인 밖에서 `/code-mapper`를 호출할 때, THE SYSTEM SHALL 동일한 스킬 절차로 코드맵을 산출한다.
- THE SYSTEM SHALL `/code-mapper`를 외부 스킬(예: 버그 수정 근본원인 분석 단계)이 호출 가능한 공용 진입점으로 노출한다. (단, moon-harness 외부 스킬에 호출 포인터를 주입하는 것은 이 기능의 범위 밖이다.)
- **Acceptance:**
  - `skills/code-mapper/SKILL.md`가 존재하고 F4(가용성 분기) + F5(폴백) + F6(커버리지 체크리스트) 절차를 모두 포함한다.
  - SDD 에이전트 프롬프트는 절차 본문이 아닌 스킬 포인터만 포함한다.

### F8: SDD 에이전트 최소 침습 주입

- THE SYSTEM SHALL 주입 타겟을 **`agents/sdd-implementer.md` 단일 파일**로 한정한다. (근거: SDD skill의 "Engineer agents 일반 규칙" — sdd-implementer에 정의된 규칙은 sdd-ts-engineer·sdd-rust-engineer 등 모든 engineer agent에 자동 전파된다. 따라서 14개 파일을 각각 건드릴 필요 없이 1개 주입으로 전파 = 최소 침습 극대화.)
- THE SYSTEM SHALL `agents/sdd-implementer.md`에 다음 내용을 담은 단락 하나만을 추가한다:
  1. codegraph MCP 가용 시 구조적 탐색 우선 사용 안내
  2. 낯선 심볼 편집 전 `/code-mapper`(또는 codegraph 직접 호출)로 실제 호출관계를 **구조적 컨텍스트로 확보 권고** (의무·게이트 아님)
  3. 절차 상세는 `skills/code-mapper/SKILL.md` 포인터
- THE SYSTEM SHALL 주입 단락이 해당 에이전트의 기존 절차 흐름을 재구성하거나 다른 섹션을 수정하지 않는다.
- IF `sdd-implementer.md`가 protected set에 준하는 파일로 취급될 때, THEN THE SYSTEM SHALL 최소 침습 원칙을 엄수하여 기존 내용 변경 없이 단락 추가만 수행한다.
- **Acceptance:**
  - 주입된 단락이 1개를 초과하지 않는다.
  - 주입 후 해당 에이전트의 기존 섹션(작업 순서·커밋 규칙·완료 판정 등)이 원문과 동일하다.
  - 주입 단락에 절차 본문이 없고 `skills/code-mapper/SKILL.md` 참조만 있다.

### F9: 결정↔판단 분리 준수

- THE SYSTEM SHALL 가용성 3-상태 분기 판단(F4)과 고정 포맷 강제(F6)를 결정적 절차로 스킬에 기술하고, Python stdlib-only 코드로 검증 가능한 형태로 분리한다.
- THE SYSTEM SHALL "이 심볼의 영향범위가 얼마나 넓은가"와 같은 판단 해석은 스킬/에이전트 프롬프트 영역으로 두고 결정적 로직에 포함하지 않는다.
- **Acceptance:**
  - `tests/`에 가용성 분기 로직을 검증하는 pytest 테스트가 존재한다.
  - 판단 해석 관련 로직이 Python 코드에 없다.

---

## 비목표 (Non-goals)

- **새 코드 분석 엔진 신규 구현 금지**: code-mapper는 codegraph MCP와 grep/Glob을 오케스트레이션할 뿐이다. 자체 AST 파서, 심볼 인덱스, 정적 분석 엔진을 구현하지 않는다.
- **레포 특화 명령 하드코딩 금지**: 특정 레포 빌드 명령·경로·컨벤션을 스킬에 기술하지 않는다.
- **시각화 도구 구현 금지**: 그래프 렌더링, 다이어그램 생성, UI 출력은 이 기능의 범위가 아니다.
- **전체 의존성 트리 자동 완전 추적 금지**: blast radius는 직접 호출 관계 1-2단계로 제한한다. 전이적 의존 전체를 재귀 완전 탐색하는 것은 이 기능의 범위가 아니다.
- **codegraph 초기화 자동화 금지**: `codegraph init -i` 실행은 제안(안내 메시지)에 그치며, code-mapper가 자동으로 실행하지 않는다.
- **protected set 자동 수정 금지**: `self-improve`, `pr-converge`, `harness-improvement-critic`, 게이트 스크립트는 이 기능이 자동으로 생성/수정하지 않는다.
- **컨텍스트 전용 — 계약/검증/종속 금지**: 코드맵은 *구조적 컨텍스트 제공*이 전부다. (a) 산출물을 영속 계약으로 강제하지 않고, (b) 구현 diff가 blast radius 안에 머물렀는지 reviewer가 검증하지 않으며, (c) Phase 3 DAG/Wave의 파일 소유권 입력으로 코드맵에 종속시키지 않는다. 이들은 업계가 스테일·과잉제약 비용으로 회피한 패턴이며, 필요 시 별도 측정 후 v2 실험으로만 검토한다.
- **사용 강제(하드 게이트) 금지**: 코드맵 미생성을 이유로 작업을 차단하거나 실패 처리하지 않는다. SDD 에이전트 주입은 권고이지 게이트가 아니다.
- **영속 금지 (ephemeral 전용)**: 코드맵은 파일로 저장하거나 관리 대상 문서로 남기지 않는다. 매 호출 시점에 재생성되어 컨텍스트로만 소비되고 버려진다(Aider repo map 모델). → 스테일·레거시 문서로 인한 혼란을 원천 차단. `docs/`나 task 문서에 코드맵을 기록하지 않는다.

---

## 검증 전략

| 검증 대상 | 검증 방법 |
|-----------|-----------|
| 가용성 3-상태 분기 로직 | `tests/` — Python stdlib-only pytest (오프라인, LLM 무호출) |
| 고정 포맷 산출 규칙 | `tests/` — 포맷 파서 단위 테스트 |
| 스킬 절차 정합성 | 수동 리뷰 (harness-improvement-critic 게이트) |
| SDD 에이전트 주입 최소 침습 여부 | 수동 리뷰 — 주입 전/후 diff 검토 |
| 폴백 경로 동작 | `evals/` — codegraph 미초기화 테스트 레포에서 `/code-mapper <심볼>` 실행 후 ① 포맷 완전성(섹션 1~6 누락 없음) ② callers/callees 개수>0 또는 "(없음)" 정합성 ③ 수집 파일경로 유효성(존재 파일만) 확인 |

---

## 용어 정의

| 용어 | 정의 |
|------|------|
| **코드맵** | 특정 심볼 또는 파일에 대해 진입점·callers·callees·trace·blast radius·건드릴 파일 목록을 F6 고정 포맷으로 정리한 산출물 |
| **가짜 확신** | 이름 기반 탐색(grep)만으로 심볼을 특정한 뒤 "이름이 맞으니 내가 원하는 동작이겠지"라고 단정하는 인식 오류. 실제 호출관계 확인 없이 작업 진입으로 이어짐 |
| **MCP 프로브** | codegraph 가용성을 판단하기 위해 codegraph MCP 도구를 직접 호출해 응답을 확인하는 행위. filesystem 디렉터리 체크와 구별됨 |
| **Blast Radius** | 특정 심볼을 변경했을 때 직접 영향 받는 파일·심볼의 범위. codegraph_impact 결과 또는 grep 역참조 근사값 |
| **폴백** | codegraph MCP가 가용하지 않을 때 Glob + 구조적 grep으로 코드맵을 산출하는 대체 절차 |
| **최소 침습** | 기존 에이전트 프롬프트의 섹션 구조·내용을 변경하지 않고 단락 하나만 추가하는 방식 |
| **SSOT (단일 진실 공급원)** | 하나의 파일이 해당 절차의 정의를 독점적으로 보유하며, 다른 파일은 포인터(참조)만 두는 원칙 |
| **결정적 로직** | 동일 입력에 항상 동일 출력을 반환하는 로직. Python stdlib-only로 구현하여 pytest로 검증 가능. LLM 호출 없음 |
| **판단 로직** | 컨텍스트 해석·분류·해석이 필요한 로직. 스킬/에이전트 프롬프트로 기술. LLM이 실행 |

---

## Blocker Check

**2026-06-26 — PASS** (sdd-blocker-checker DONE_WITH_CONCERNS → 3건 해소 반영)
- F4: 프로브 도구 `codegraph_status` 명시 + 3-상태 분류 기준 구체화
- F5/F6: callers 의미(주석·문자열 제외) + Blast Radius(섹션5) vs 건드릴 파일(섹션6) 구분
- 검증 전략: 폴백 동작 eval 기준(포맷 완전성/개수/파일 유효성) 구체화
- F8: 주입 타겟을 `sdd-implementer.md` 단일 파일로 한정(engineer agent 전파 규약 활용)

플랫폼/스택 확정. 구현 진입 블로커 없음.
